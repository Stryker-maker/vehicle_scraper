from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Sequence

from canonical_evidence import read_jsonl
from purpose_outputs import (
    FAMILY_CSV_FIELDS,
    FORBIDDEN_KEYS,
    OWNED_CSV_FIELDS,
    PURPOSE_OUTPUT_SCHEMA_VERSION,
    SUPPORTED_SOURCES,
    artifact_paths,
    load_purpose_inputs,
    load_source_bundles,
)
from vehicle_config import load_vehicle_config

PURPOSE_OUTPUT_VALIDATION_SCHEMA_VERSION = 1


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


def validate_purpose_output(
    *,
    root: Path,
    config_path: Path,
    inputs_path: Path = Path("purpose_inputs.json"),
    run_id: str | None = None,
    expected_sources: Sequence[str] | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    config_path = config_path if config_path.is_absolute() else root / config_path
    inputs_path = inputs_path if inputs_path.is_absolute() else root / inputs_path
    config = load_vehicle_config(config_path)
    purpose_inputs = load_purpose_inputs(inputs_path)
    vehicle_key = str(config["vehicle_key"])
    entry = purpose_inputs["vehicles"].get(vehicle_key)
    if not isinstance(entry, dict):
        raise ValueError(f"{vehicle_key}: no governed purpose input")
    profile = str(entry["analysis_profile"])
    paths = artifact_paths(root, config, profile)
    errors: list[str] = []
    for name, path in paths.items():
        if not path.is_file():
            errors.append(f"missing_artifact:{name}:{path.relative_to(root)}")
    if errors:
        return {
            "purpose_output_validation_schema_version": PURPOSE_OUTPUT_VALIDATION_SCHEMA_VERSION,
            "validation_status": "fail",
            "run_id": run_id,
            "vehicle_key": vehicle_key,
            "analysis_profile": profile,
            "validation_errors": errors,
            "record_count": 0,
            "csv_row_count": 0,
        }

    summary = _json(paths["summary_json"])
    active_run = run_id or str(summary.get("run_id") or "")
    sources = list(expected_sources or summary.get("sources") or [])
    if not active_run:
        errors.append("missing_run_id")
    if not sources or len(sources) != len(set(sources)) or any(source not in SUPPORTED_SOURCES for source in sources):
        errors.append("invalid_source_scope")
    if summary.get("purpose_output_schema_version") != PURPOSE_OUTPUT_SCHEMA_VERSION:
        errors.append("summary_schema_mismatch")
    if summary.get("run_id") != active_run:
        errors.append("summary_run_id_mismatch")
    if summary.get("vehicle_key") != vehicle_key:
        errors.append("summary_vehicle_mismatch")
    if summary.get("analysis_profile") != profile:
        errors.append("summary_profile_mismatch")
    if list(summary.get("sources") or []) != sources:
        errors.append("summary_source_scope_mismatch")
    errors.extend(f"summary_forbidden_key:{path}" for path in _forbidden_key_paths(summary))

    records = read_jsonl(paths["records_jsonl"])
    expected_bundles: list[dict[str, Any]] = []
    for source in sources:
        try:
            expected_bundles.extend(load_source_bundles(root, config, source, active_run))
        except Exception as exc:
            errors.append(f"underlying_evidence_invalid:{source}:{type(exc).__name__}:{exc}")
    expected_ids = {
        str(bundle["record"].get("canonical_listing_id"))
        for bundle in expected_bundles
    }
    expected_source_by_id = {
        str(bundle["record"].get("canonical_listing_id")): str(bundle["record"].get("source"))
        for bundle in expected_bundles
    }
    record_ids: set[str] = set()
    for index, record in enumerate(records):
        canonical_id = str(record.get("canonical_listing_id") or "")
        if record.get("purpose_output_schema_version") != PURPOSE_OUTPUT_SCHEMA_VERSION:
            errors.append(f"record_schema_mismatch:{index}")
        if record.get("run_id") != active_run:
            errors.append(f"record_run_id_mismatch:{index}")
        if record.get("vehicle_key") != vehicle_key:
            errors.append(f"record_vehicle_mismatch:{index}")
        if record.get("analysis_profile") != profile:
            errors.append(f"record_profile_mismatch:{index}")
        if record.get("source") not in sources:
            errors.append(f"record_source_mismatch:{index}")
        if not canonical_id or canonical_id in record_ids:
            errors.append(f"record_canonical_id_invalid_or_duplicate:{index}")
        record_ids.add(canonical_id)
        if expected_source_by_id.get(canonical_id) != record.get("source"):
            errors.append(f"record_underlying_source_mismatch:{canonical_id}")
        if not str(record.get("raw_record_ref") or "").strip():
            errors.append(f"record_raw_ref_missing:{canonical_id}")
        if not str(record.get("source_adapter_record_ref") or "").strip():
            errors.append(f"record_adapter_ref_missing:{canonical_id}")
        errors.extend(
            f"record_forbidden_key:{index}:{path}"
            for path in _forbidden_key_paths(record)
        )
        if profile == "owned_vehicle_value":
            if record.get("interpretation_contract") != "observed_asking_price_context_not_appraisal_not_sale_probability":
                errors.append(f"owned_interpretation_contract_mismatch:{canonical_id}")
            if not isinstance(record.get("subject_comparability_reasons"), list):
                errors.append(f"owned_comparability_reasons_missing:{canonical_id}")
        else:
            if record.get("decision_contract") != "purpose_specific_candidate_classification_not_rank_not_score":
                errors.append(f"family_decision_contract_mismatch:{canonical_id}")
            if not isinstance(record.get("candidate_classification_reasons"), list):
                errors.append(f"family_classification_reasons_missing:{canonical_id}")

    if record_ids != expected_ids:
        errors.append("record_underlying_canonical_id_set_mismatch")
    if int(summary.get("record_count", -1)) != len(records):
        errors.append("summary_record_count_mismatch")
    expected_source_counts = {
        source: sum(record.get("source") == source for record in records)
        for source in sources
    }
    if summary.get("source_record_counts") != expected_source_counts:
        errors.append("summary_source_count_mismatch")

    expected_fields = OWNED_CSV_FIELDS if profile == "owned_vehicle_value" else FAMILY_CSV_FIELDS
    with paths["records_csv"].open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        csv_rows = list(reader)
        fieldnames = tuple(reader.fieldnames or ())
    if fieldnames != expected_fields:
        errors.append("csv_field_order_mismatch")
    if any(field.casefold() in FORBIDDEN_KEYS for field in fieldnames):
        errors.append("csv_contains_rank_or_score_column")
    if len(csv_rows) != len(records):
        errors.append("csv_record_count_mismatch")
    csv_ids = {str(row.get("canonical_listing_id") or "") for row in csv_rows}
    if csv_ids != record_ids:
        errors.append("csv_record_id_set_mismatch")
    for index, row in enumerate(csv_rows):
        if row.get("purpose_output_schema_version") != str(PURPOSE_OUTPUT_SCHEMA_VERSION):
            errors.append(f"csv_schema_mismatch:{index}")
        if row.get("run_id") != active_run:
            errors.append(f"csv_run_id_mismatch:{index}")
        if row.get("vehicle_key") != vehicle_key:
            errors.append(f"csv_vehicle_mismatch:{index}")
        if row.get("analysis_profile") != profile:
            errors.append(f"csv_profile_mismatch:{index}")

    if profile == "owned_vehicle_value":
        gaps = _json(paths["input_gaps"])
        if gaps.get("purpose_output_schema_version") != PURPOSE_OUTPUT_SCHEMA_VERSION:
            errors.append("input_gaps_schema_mismatch")
        if gaps.get("run_id") != active_run or gaps.get("vehicle_key") != vehicle_key:
            errors.append("input_gaps_identity_mismatch")
        if gaps.get("subject_profile_missing_fields") != summary.get("subject_profile_missing_fields"):
            errors.append("input_gaps_field_set_mismatch")
        if summary.get("interpretation_contract") != "asking_price_context_not_appraisal_not_transaction_price_not_sale_probability":
            errors.append("owned_summary_interpretation_contract_mismatch")
    else:
        questions = read_jsonl(paths["questions_jsonl"])
        question_ids: set[str] = set()
        for index, record in enumerate(questions):
            canonical_id = str(record.get("canonical_listing_id") or "")
            if record.get("purpose_output_schema_version") != PURPOSE_OUTPUT_SCHEMA_VERSION:
                errors.append(f"question_schema_mismatch:{index}")
            if record.get("run_id") != active_run or record.get("vehicle_key") != vehicle_key:
                errors.append(f"question_identity_mismatch:{index}")
            if record.get("source") not in sources:
                errors.append(f"question_source_mismatch:{index}")
            if not canonical_id or canonical_id in question_ids:
                errors.append(f"question_canonical_id_invalid_or_duplicate:{index}")
            question_ids.add(canonical_id)
            values = record.get("questions")
            if not isinstance(values, list) or not values:
                errors.append(f"question_list_missing_or_empty:{canonical_id}")
            else:
                for question_index, question in enumerate(values):
                    if not isinstance(question, dict) or not all(
                        str(question.get(field) or "").strip()
                        for field in ("category", "priority", "question", "reason")
                    ):
                        errors.append(f"question_entry_invalid:{index}:{question_index}")
            errors.extend(
                f"question_forbidden_key:{index}:{path}"
                for path in _forbidden_key_paths(record)
            )
        if question_ids != record_ids:
            errors.append("question_record_id_set_mismatch")
        if summary.get("interpretation_contract") != "candidate_review_not_rank_not_recommendation_not_condition_verification":
            errors.append("family_summary_interpretation_contract_mismatch")

    markdown = paths["summary_markdown"].read_text(encoding="utf-8")
    if f"`{active_run}`" not in markdown:
        errors.append("markdown_run_id_missing")
    if vehicle_key not in markdown:
        errors.append("markdown_vehicle_key_missing")

    expected_artifacts = {name: str(path.relative_to(root)) for name, path in paths.items()}
    if summary.get("artifacts") != expected_artifacts:
        errors.append("summary_artifact_map_mismatch")

    return {
        "purpose_output_validation_schema_version": PURPOSE_OUTPUT_VALIDATION_SCHEMA_VERSION,
        "validation_status": "pass" if not errors else "fail",
        "run_id": active_run,
        "vehicle_key": vehicle_key,
        "analysis_profile": profile,
        "sources": sources,
        "record_count": len(records),
        "csv_row_count": len(csv_rows),
        "validation_errors": errors,
        "artifacts": expected_artifacts,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Validate governed secondary-purpose outputs")
    result.add_argument("--config", required=True)
    result.add_argument("--inputs", default="purpose_inputs.json")
    result.add_argument("--run-id")
    result.add_argument("--source", action="append", choices=SUPPORTED_SOURCES)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    report = validate_purpose_output(
        root=Path.cwd(),
        config_path=Path(args.config),
        inputs_path=Path(args.inputs),
        run_id=args.run_id,
        expected_sources=args.source,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["validation_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
