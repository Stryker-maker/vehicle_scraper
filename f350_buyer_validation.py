from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Sequence

from canonical_evidence import read_jsonl
from f350_buyer_intelligence import BUYER_SCHEMA_VERSION, CSV_FIELDS, artifact_paths
from vehicle_config import load_vehicle_config

BUYER_VALIDATION_SCHEMA_VERSION = 1
FORBIDDEN_KEYS = {"rank", "score"}
SUPPORTED_SOURCES = {"autotrader", "kijiji"}


def _forbidden_key_paths(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key).casefold() in FORBIDDEN_KEYS:
                found.append(child_path)
            found.extend(_forbidden_key_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_forbidden_key_paths(child, f"{path}[{index}]"))
    return found


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def validate_buyer_artifacts(
    *,
    root: Path,
    config_path: Path = Path("config_f350.json"),
    run_id: str | None = None,
    expected_sources: Sequence[str] | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    config_path = config_path if config_path.is_absolute() else root / config_path
    config = load_vehicle_config(config_path)
    if config.get("vehicle_key") != "ford_f350":
        raise ValueError("F-350 buyer validation requires config_f350")
    paths = artifact_paths(root, config)
    errors: list[str] = []
    for name, path in paths.items():
        if not path.is_file():
            errors.append(f"missing_artifact:{name}:{path.relative_to(root)}")
    if errors:
        return {
            "buyer_validation_schema_version": BUYER_VALIDATION_SCHEMA_VERSION,
            "validation_status": "fail",
            "run_id": run_id,
            "validation_errors": errors,
            "listing_count": 0,
            "question_record_count": 0,
            "csv_row_count": 0,
        }

    summary = _json(paths["market_summary_json"])
    active_run = run_id or str(summary.get("run_id") or "")
    sources = list(expected_sources or summary.get("sources") or [])
    if not active_run:
        errors.append("missing_run_id")
    if not sources or any(source not in SUPPORTED_SOURCES for source in sources):
        errors.append("invalid_source_scope")
    if len(sources) != len(set(sources)):
        errors.append("duplicate_source_scope")
    if summary.get("buyer_intelligence_schema_version") != BUYER_SCHEMA_VERSION:
        errors.append("summary_schema_mismatch")
    if summary.get("run_id") != active_run:
        errors.append("summary_run_id_mismatch")
    if summary.get("vehicle_key") != "ford_f350":
        errors.append("summary_vehicle_mismatch")
    if list(summary.get("sources") or []) != sources:
        errors.append("summary_source_scope_mismatch")
    errors.extend(
        f"summary_forbidden_key:{path}"
        for path in _forbidden_key_paths(summary)
    )

    listings = read_jsonl(paths["investigation_jsonl"])
    questions = read_jsonl(paths["seller_questions"])
    question_by_id: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(questions):
        canonical_id = str(record.get("canonical_listing_id") or "")
        if record.get("buyer_intelligence_schema_version") != BUYER_SCHEMA_VERSION:
            errors.append(f"question_schema_mismatch:{index}")
        if record.get("run_id") != active_run:
            errors.append(f"question_run_id_mismatch:{index}")
        if record.get("vehicle_key") != "ford_f350":
            errors.append(f"question_vehicle_mismatch:{index}")
        if record.get("source") not in sources:
            errors.append(f"question_source_mismatch:{index}")
        if not canonical_id or canonical_id in question_by_id:
            errors.append(f"question_canonical_id_invalid_or_duplicate:{index}")
        else:
            question_by_id[canonical_id] = record
        values = record.get("questions")
        if not isinstance(values, list):
            errors.append(f"question_list_missing:{index}")
        else:
            for question_index, question in enumerate(values):
                if not isinstance(question, dict) or not all(
                    str(question.get(field) or "").strip()
                    for field in ("category", "priority", "question", "reason")
                ):
                    errors.append(
                        f"question_entry_invalid:{index}:{question_index}"
                    )
        errors.extend(
            f"question_forbidden_key:{index}:{path}"
            for path in _forbidden_key_paths(record)
        )

    listing_ids: set[str] = set()
    for index, record in enumerate(listings):
        canonical_id = str(record.get("canonical_listing_id") or "")
        if record.get("buyer_intelligence_schema_version") != BUYER_SCHEMA_VERSION:
            errors.append(f"listing_schema_mismatch:{index}")
        if record.get("run_id") != active_run:
            errors.append(f"listing_run_id_mismatch:{index}")
        if record.get("vehicle_key") != "ford_f350":
            errors.append(f"listing_vehicle_mismatch:{index}")
        if record.get("source") not in sources:
            errors.append(f"listing_source_mismatch:{index}")
        if not canonical_id or canonical_id in listing_ids:
            errors.append(f"listing_canonical_id_invalid_or_duplicate:{index}")
        listing_ids.add(canonical_id)
        if canonical_id not in question_by_id:
            errors.append(f"listing_question_record_missing:{canonical_id}")
        if record.get("decision_contract") != (
            "explainable_classification_not_rank_not_score_"
            "manual_override_preserves_source_evidence"
        ):
            errors.append(f"listing_decision_contract_mismatch:{canonical_id}")
        owner = record.get("owner_annotation")
        if not isinstance(owner, dict):
            errors.append(f"listing_owner_annotation_missing:{canonical_id}")
        else:
            if owner.get("override_applied") is True and not str(
                owner.get("override_reason") or ""
            ).strip():
                errors.append(f"listing_override_reason_missing:{canonical_id}")
            if owner.get("override_contract") != (
                "owner_classification_only_source_evidence_unchanged"
            ):
                errors.append(f"listing_override_contract_mismatch:{canonical_id}")
        market = record.get("market_context")
        if not isinstance(market, dict) or market.get("market_scope") != (
            "configured_query_accepted_listing_claims_not_complete_market"
        ):
            errors.append(f"listing_market_scope_mismatch:{canonical_id}")
        regression = market.get("mileage_adjusted_asking_price_projection", {}) if isinstance(market, dict) else {}
        if regression.get("meaning") != (
            "asking_price_context_not_appraisal_or_future_value"
        ):
            errors.append(f"listing_projection_contract_mismatch:{canonical_id}")
        errors.extend(
            f"listing_forbidden_key:{index}:{path}"
            for path in _forbidden_key_paths(record)
        )

    if set(question_by_id) != listing_ids:
        errors.append("listing_question_id_set_mismatch")
    if int(summary.get("listing_claim_count", -1)) != len(listings):
        errors.append("summary_listing_count_mismatch")
    expected_source_counts = {
        source: sum(record.get("source") == source for record in listings)
        for source in sources
    }
    if summary.get("source_listing_claim_counts") != expected_source_counts:
        errors.append("summary_source_count_mismatch")

    with paths["investigation_csv"].open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        reader = csv.DictReader(handle)
        csv_rows = list(reader)
        fieldnames = tuple(reader.fieldnames or ())
    if fieldnames != CSV_FIELDS:
        errors.append("csv_field_order_mismatch")
    if any(field.casefold() in FORBIDDEN_KEYS for field in fieldnames):
        errors.append("csv_contains_rank_or_score_column")
    if len(csv_rows) != len(listings):
        errors.append("csv_listing_count_mismatch")
    csv_ids: set[str] = set()
    for index, row in enumerate(csv_rows):
        canonical_id = str(row.get("canonical_listing_id") or "")
        csv_ids.add(canonical_id)
        if row.get("buyer_intelligence_schema_version") != str(BUYER_SCHEMA_VERSION):
            errors.append(f"csv_schema_mismatch:{index}")
        if row.get("run_id") != active_run:
            errors.append(f"csv_run_id_mismatch:{index}")
        if row.get("vehicle_key") != "ford_f350":
            errors.append(f"csv_vehicle_mismatch:{index}")
        if row.get("source") not in sources:
            errors.append(f"csv_source_mismatch:{index}")
    if csv_ids != listing_ids:
        errors.append("csv_listing_id_set_mismatch")

    markdown = paths["market_summary_markdown"].read_text(encoding="utf-8")
    if "# F-350 Buyer Intelligence" not in markdown:
        errors.append("markdown_title_missing")
    if f"`{active_run}`" not in markdown:
        errors.append("markdown_run_id_missing")

    expected_artifacts = {
        name: str(path.relative_to(root)) for name, path in paths.items()
    }
    if summary.get("artifacts") != expected_artifacts:
        errors.append("summary_artifact_map_mismatch")

    return {
        "buyer_validation_schema_version": BUYER_VALIDATION_SCHEMA_VERSION,
        "validation_status": "pass" if not errors else "fail",
        "run_id": active_run,
        "vehicle_key": "ford_f350",
        "sources": sources,
        "listing_count": len(listings),
        "question_record_count": len(questions),
        "csv_row_count": len(csv_rows),
        "validation_errors": errors,
        "artifacts": expected_artifacts,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Validate current F-350 buyer-intelligence artifacts"
    )
    result.add_argument("--config", default="config_f350.json")
    result.add_argument("--run-id")
    result.add_argument("--source", action="append", choices=sorted(SUPPORTED_SOURCES))
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    report = validate_buyer_artifacts(
        root=Path.cwd(),
        config_path=Path(args.config),
        run_id=args.run_id,
        expected_sources=args.source,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["validation_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
