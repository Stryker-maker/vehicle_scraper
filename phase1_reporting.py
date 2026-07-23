from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from canonical_evidence import read_jsonl
from identity_lifecycle import (
    build_duplicate_candidates,
    candidate_index,
    load_current_identity_records,
)
from phase1_common import (
    MANUAL_REVIEW_FIELDS, SOURCES, load_json, source_status_path,
    status_is_current_success, utc_now, write_json,
)

SourcePlan = Iterable[tuple[Path, Sequence[str]]]


def _resolved_plan(
    *, config_paths: Iterable[Path] | None, source_plan: SourcePlan | None,
) -> list[tuple[Path, tuple[str, ...]]]:
    if source_plan is not None:
        if config_paths is not None:
            raise ValueError("Provide config_paths or source_plan, not both")
        plan = [(Path(path), tuple(sources)) for path, sources in source_plan]
    elif config_paths is not None:
        plan = [(Path(path), SOURCES) for path in config_paths]
    else:
        raise ValueError("A config_paths or source_plan value is required")
    if not plan:
        raise ValueError("Reporting source plan must not be empty")
    for path, sources in plan:
        if not sources:
            raise ValueError(f"Reporting source plan has no sources for {path}")
        unsupported = sorted(set(sources) - set(SOURCES))
        if unsupported:
            raise ValueError(f"Unsupported reporting source(s): {', '.join(unsupported)}")
        if len(sources) != len(set(sources)):
            raise ValueError(f"Reporting source plan has duplicate sources for {path}")
    return plan


def _string(value: Any) -> str:
    return "" if value is None else str(value)


def _field_status(record: dict[str, Any], field: str) -> str:
    evidence = record.get("field_evidence", {}).get(field, {})
    return _string(evidence.get("evidence_status", "unknown"))


def _field_raw(record: dict[str, Any], field: str) -> str:
    evidence = record.get("field_evidence", {}).get(field, {})
    return _string(evidence.get("raw_value"))


def _highest_confidence(candidates: Sequence[dict[str, Any]]) -> str:
    order = {"high": 3, "medium": 2, "low": 1}
    return max(
        (str(value.get("confidence") or "") for value in candidates),
        key=lambda value: order.get(value, 0),
        default="",
    )


def transform_manual_review_record(
    record: dict[str, Any],
    status: dict[str, Any],
    identity: dict[str, Any] | None = None,
    duplicate_candidates: Sequence[dict[str, Any]] | None = None,
) -> dict[str, str]:
    normalized = record.get("normalized", {})
    source = _string(record.get("source"))
    identity = identity or {}
    duplicate_candidates = list(duplicate_candidates or [])
    warnings = [
        _string(warning)
        for warning in record.get("quality_warnings", [])
        if _string(warning)
    ]
    review_status = (
        "duplicate_candidate_review_required"
        if duplicate_candidates
        else "location_verification_required"
        if source == "kijiji"
        else "data_quality_review_required"
        if warnings
        else "manual_review_required"
    )
    candidate_ids = sorted(
        str(value.get("candidate_id"))
        for value in duplicate_candidates
        if value.get("candidate_id")
    )
    candidate_reasons = sorted(
        {
            str(reason)
            for value in duplicate_candidates
            for reason in value.get("reasons", [])
        }
    )
    row = {
        "evidence_schema_version": _string(record.get("evidence_schema_version")),
        "identity_lifecycle_schema_version": _string(
            identity.get("identity_lifecycle_schema_version")
        ),
        "vehicle_key": _string(record.get("vehicle_key")),
        "source": source,
        "canonical_listing_id": _string(record.get("canonical_listing_id")),
        "observation_id": _string(record.get("observation_id")),
        "source_listing_id": _string(record.get("source_listing_id")),
        "source_listing_id_status": _string(record.get("source_listing_id_status")),
        "vin_claim": _string(identity.get("vin_claim")),
        "vin_evidence_status": _string(
            identity.get("vin_evidence_status", "not_reported")
        ),
        "source_claim_status": _string(record.get("source_claim_status")),
        "raw_record_ref": _string(record.get("raw_record_ref")),
        "normalized_record_ref": _string(record.get("normalized_record_ref")),
        "identity_fingerprint_strict": _string(
            identity.get("identity_fingerprint_strict")
        ),
        "identity_fingerprint_loose": _string(
            identity.get("identity_fingerprint_loose")
        ),
        "lifecycle_state": _string(identity.get("lifecycle_state")),
        "lifecycle_state_reason": _string(identity.get("lifecycle_state_reason")),
        "first_seen_at_utc": _string(identity.get("first_seen_at_utc")),
        "last_seen_at_utc": _string(identity.get("last_seen_at_utc")),
        "elapsed_since_first_seen_days": _string(
            identity.get("elapsed_since_first_seen_days")
        ),
        "elapsed_since_last_seen_days": _string(
            identity.get("elapsed_since_last_seen_days")
        ),
        "missing_run_count": _string(identity.get("missing_run_count")),
        "reappearance_count": _string(identity.get("reappearance_count")),
        "duplicate_candidate_count": _string(len(duplicate_candidates)),
        "highest_duplicate_confidence": _highest_confidence(duplicate_candidates),
        "duplicate_candidate_ids": ";".join(candidate_ids),
        "duplicate_candidate_reasons": ";".join(candidate_reasons),
        "ranking_status": "DISABLED_MANUAL_REVIEW_REQUIRED",
        "review_status": review_status,
        "collection_status": _string(
            status.get("collection_status", status.get("execution_status", "unknown"))
        ),
        "data_quality_status": "warnings_present" if warnings else "clean",
        "quality_warnings": ";".join(warnings),
        "source_run_status": _string(status.get("execution_status", "unknown")),
        "source_completed_at_utc": _string(status.get("completed_at_utc")),
        "year": _string(normalized.get("year")),
        "year_evidence_status": _field_status(record, "year"),
        "make": _string(normalized.get("make")),
        "make_evidence_status": _field_status(record, "make"),
        "model": _string(normalized.get("model")),
        "model_evidence_status": _field_status(record, "model"),
        "trim": _string(normalized.get("trim")),
        "trim_evidence_status": _field_status(record, "trim"),
        "price_cad": _string(normalized.get("price_cad")),
        "price_evidence_status": _field_status(record, "price_cad"),
        "mileage_km": _string(normalized.get("mileage_km")),
        "mileage_evidence_status": _field_status(record, "mileage_km"),
        "engine": _string(normalized.get("engine")),
        "engine_evidence_status": _field_status(record, "engine"),
        "fuel": _string(normalized.get("fuel")),
        "fuel_evidence_status": _field_status(record, "fuel"),
        "accident_claim": _string(normalized.get("accident_claim")),
        "accident_evidence_status": _field_status(record, "accident_claim"),
        "dealer": _string(normalized.get("dealer")),
        "dealer_evidence_status": _field_status(record, "dealer"),
        "seller_type_claim": _string(normalized.get("seller_type_claim")),
        "seller_type_evidence_status": _field_status(record, "seller_type_claim"),
        "dealer_address": _string(normalized.get("dealer_address")),
        "dealer_address_evidence_status": _field_status(record, "dealer_address"),
        "location": _string(normalized.get("location")),
        "location_evidence_status": _field_status(record, "location"),
        "unverified_location_value": (
            _field_raw(record, "location") if source == "kijiji" else ""
        ),
        "distance_km": _string(normalized.get("distance_km")),
        "distance_evidence_status": _field_status(record, "distance_km"),
        "distance_method": _string(normalized.get("distance_method")),
        "url_region_hint": _string(normalized.get("url_region_hint")),
        "url_region_evidence_status": _field_status(record, "url_region_hint"),
        "listing_url": _string(normalized.get("listing_url")),
        "listing_url_evidence_status": _field_status(record, "listing_url"),
        "observation_count": _string(identity.get("observation_count")),
        "price_observation_count": _string(identity.get("price_observation_count")),
        "first_observed_price_cad": _string(
            identity.get("first_observed_price_cad")
        ),
        "previous_observation_price_cad": _string(
            identity.get("previous_observation_price_cad")
        ),
        "change_from_previous_observation_cad": _string(
            identity.get("change_from_previous_observation_cad")
        ),
        "change_from_first_observation_cad": _string(
            identity.get("change_from_first_observation_cad")
        ),
        "days_on_market_claim": _string(normalized.get("days_on_market_claim")),
    }
    return {field: row.get(field, "") for field in MANUAL_REVIEW_FIELDS}


def _accepted_records(
    *, root: Path, status: dict[str, Any], active_run: str,
) -> list[dict[str, Any]]:
    artifacts = status.get("canonical_evidence_artifacts", {})
    accepted_path = artifacts.get("accepted")
    if not accepted_path:
        raise ValueError("missing_accepted_evidence_artifact")
    path = root / str(accepted_path)
    records = read_jsonl(path)
    for record in records:
        if record.get("run_id") != active_run:
            raise ValueError("accepted_evidence_run_id_mismatch")
        if record.get("record_stage") != "accepted":
            raise ValueError("accepted_evidence_contains_nonaccepted_record")
    if len(records) != int(status.get("accepted_record_count", -1)):
        raise ValueError("accepted_evidence_count_mismatch")
    return records


def build_manual_review(
    *, root: Path, config_paths: Iterable[Path] | None = None,
    source_plan: SourcePlan | None = None, run_id: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    active_run = run_id or os.environ.get("GITHUB_RUN_ID", "local")
    summaries: list[dict[str, Any]] = []
    for raw_path, enabled_sources in _resolved_plan(
        config_paths=config_paths, source_plan=source_plan
    ):
        config_path = raw_path if raw_path.is_absolute() else root / raw_path
        config = load_json(config_path)
        key = str(config["vehicle_key"])
        included: list[str] = []
        excluded: dict[str, str] = {}
        source_evidence: dict[str, dict[str, int]] = {}
        bundles: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
        identities: list[dict[str, Any]] = []
        for source in enabled_sources:
            status_path = source_status_path(root, config, source)
            if not status_path.exists():
                excluded[source] = "missing_status"
                continue
            status = load_json(status_path)
            if not status_is_current_success(status, active_run):
                excluded[source] = str(status.get("execution_status", "not_current"))
                continue
            try:
                records = _accepted_records(
                    root=root, status=status, active_run=active_run
                )
                identity_records = load_current_identity_records(
                    root=root,
                    config=config,
                    source=source,
                    run_id=active_run,
                )
                if len(identity_records) != len(records):
                    raise ValueError("identity_current_count_mismatch")
                identity_by_id = {
                    str(value["canonical_listing_id"]): value
                    for value in identity_records
                }
                for record in records:
                    canonical_id = str(record.get("canonical_listing_id") or "")
                    if canonical_id not in identity_by_id:
                        raise ValueError("identity_record_missing_for_accepted_listing")
                    bundles.append((record, status, identity_by_id[canonical_id]))
                identities.extend(identity_records)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                excluded[source] = str(exc)
                continue
            source_evidence[source] = {
                "fetched_records": int(status.get("fetched_record_count", 0)),
                "accepted_records": int(status.get("accepted_record_count", 0)),
                "rejected_records": int(status.get("rejected_record_count", 0)),
                "parse_failures": int(status.get("parse_failure_count", 0)),
                "tracked_listings": int(status.get("identity_tracked_listing_count", 0)),
                "missing_listings": int(status.get("identity_missing_listing_count", 0)),
                "retired_listings": int(status.get("identity_retired_listing_count", 0)),
            }
            included.append(source)

        duplicate_summary = build_duplicate_candidates(
            root=root,
            config=config,
            run_id=active_run,
            identity_records=identities,
        )
        by_listing = candidate_index(duplicate_summary["candidates"])
        rows = [
            transform_manual_review_record(
                record,
                status,
                identity,
                by_listing.get(str(record.get("canonical_listing_id") or ""), []),
            )
            for record, status, identity in bundles
        ]
        rows.sort(key=lambda row: (
            row.get("source", ""), row.get("year", ""), row.get("make", ""),
            row.get("model", ""), row.get("canonical_listing_id", ""),
        ))
        manual_dir = root / "data" / key / "manual_review"
        manual_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
        archive = manual_dir / f"{key}_manual_review_{timestamp}.csv"
        latest = manual_dir / f"{key}_manual_review_latest.csv"
        for output in (archive, latest):
            with output.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=MANUAL_REVIEW_FIELDS, extrasaction="ignore"
                )
                writer.writeheader()
                writer.writerows(rows)
        marker = root / "data" / key / "merged" / "RANKING_DISABLED.md"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(
            "# Merged ranking disabled\n\nThe automated cross-source merged ranking is "
            "disabled. Existing merged CSV files are historical and are no longer "
            f"refreshed. Use `../manual_review/{key}_manual_review_latest.csv` for "
            "current accepted records with identity and lifecycle evidence. Duplicate "
            "matches are non-destructive candidates under `../identity_lifecycle/`; "
            "they never merge canonical records. Legacy `price_history_*.json` files "
            "are historical and are not used by supported output.\n",
            encoding="utf-8",
        )
        warning_rows = sum(1 for row in rows if row["quality_warnings"])
        summaries.append({
            "vehicle_key": key,
            "row_count": len(rows),
            "accepted_record_count": len(rows),
            "expected_sources": list(enabled_sources),
            "quality_warning_rows": warning_rows,
            "included_sources": included,
            "excluded_sources": excluded,
            "source_evidence": source_evidence,
            "duplicate_candidate_count": duplicate_summary["candidate_count"],
            "high_confidence_duplicate_candidate_count": duplicate_summary[
                "high_confidence_count"
            ],
            "medium_confidence_duplicate_candidate_count": duplicate_summary[
                "medium_confidence_count"
            ],
            "low_confidence_duplicate_candidate_count": duplicate_summary[
                "low_confidence_count"
            ],
            "duplicate_candidate_artifact": duplicate_summary["artifact"],
            "latest_output": str(latest.relative_to(root)),
            "archive_output": str(archive.relative_to(root)),
            "disabled_ranking_marker": str(marker.relative_to(root)),
        })
        print(
            f"[{key}] manual review accepted={len(rows)} | warnings={warning_rows} "
            f"| duplicate_candidates={duplicate_summary['candidate_count']} "
            f"| included={','.join(included) or 'none'}"
        )
    return {"run_id": active_run, "vehicles": summaries}


def collect_health(
    *, root: Path, config_paths: Iterable[Path] | None = None,
    source_plan: SourcePlan | None = None, run_id: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    active_run = run_id or os.environ.get("GITHUB_RUN_ID", "local")
    entries: list[dict[str, Any]] = []
    for raw_path, enabled_sources in _resolved_plan(
        config_paths=config_paths, source_plan=source_plan
    ):
        config_path = raw_path if raw_path.is_absolute() else root / raw_path
        config = load_json(config_path)
        for source in enabled_sources:
            status_path = source_status_path(root, config, source)
            if status_path.exists():
                status = load_json(status_path)
                current_run = status.get("run_id") == active_run
                current_rows = int(
                    status.get("current_row_count", status.get("row_count", 0))
                ) if current_run else 0
                stale_rows = int(status.get("stale_row_count", 0))
                entries.append({
                    "vehicle_key": config["vehicle_key"], "source": source,
                    "healthy": status_is_current_success(status, active_run),
                    "current_run": current_run,
                    "execution_status": status.get("execution_status", "unknown"),
                    "collection_status": status.get(
                        "collection_status", status.get("execution_status", "unknown")
                    ),
                    "data_quality_status": status.get(
                        "data_quality_status", "not_evaluated"
                    ),
                    "quality_warning_rows": status.get("quality_warning_rows", 0),
                    "quality_warning_count": status.get("quality_warning_count", 0),
                    "quality_warning_summary": status.get(
                        "quality_warning_summary", {}
                    ),
                    "row_count": current_rows, "current_row_count": current_rows,
                    "stale_row_count": stale_rows,
                    "fetched_record_count": int(status.get("fetched_record_count", 0)) if current_run else 0,
                    "accepted_record_count": int(status.get("accepted_record_count", 0)) if current_run else 0,
                    "rejected_record_count": int(status.get("rejected_record_count", 0)) if current_run else 0,
                    "parse_failure_count": int(status.get("parse_failure_count", 0)) if current_run else 0,
                    "evidence_reconciliation_status": status.get(
                        "evidence_reconciliation_status", "not_evaluated"
                    ),
                    "identity_lifecycle_status": status.get(
                        "identity_lifecycle_status", "not_evaluated"
                    ),
                    "identity_tracked_listing_count": int(
                        status.get("identity_tracked_listing_count", 0)
                    ) if current_run else 0,
                    "identity_new_listing_count": int(
                        status.get("identity_new_listing_count", 0)
                    ) if current_run else 0,
                    "identity_reappeared_listing_count": int(
                        status.get("identity_reappeared_listing_count", 0)
                    ) if current_run else 0,
                    "identity_missing_listing_count": int(
                        status.get("identity_missing_listing_count", 0)
                    ) if current_run else 0,
                    "identity_retired_listing_count": int(
                        status.get("identity_retired_listing_count", 0)
                    ) if current_run else 0,
                    "failure_reasons": status.get("failure_reasons", []),
                    "status_path": str(status_path.relative_to(root)),
                })
            else:
                entries.append({
                    "vehicle_key": config["vehicle_key"], "source": source,
                    "healthy": False, "current_run": False,
                    "execution_status": "missing", "collection_status": "missing",
                    "data_quality_status": "not_evaluated",
                    "quality_warning_rows": 0, "quality_warning_count": 0,
                    "quality_warning_summary": {}, "row_count": 0,
                    "current_row_count": 0, "stale_row_count": 0,
                    "fetched_record_count": 0, "accepted_record_count": 0,
                    "rejected_record_count": 0, "parse_failure_count": 0,
                    "evidence_reconciliation_status": "missing",
                    "identity_lifecycle_status": "missing",
                    "identity_tracked_listing_count": 0,
                    "identity_new_listing_count": 0,
                    "identity_reappeared_listing_count": 0,
                    "identity_missing_listing_count": 0,
                    "identity_retired_listing_count": 0,
                    "failure_reasons": ["missing_status"],
                    "status_path": str(status_path.relative_to(root)),
                })
    unhealthy = [entry for entry in entries if not entry["healthy"]]
    warnings = [
        entry for entry in entries
        if entry["data_quality_status"] == "warnings_present"
    ]
    overall = (
        "degraded" if unhealthy else
        "success_with_warnings" if warnings else
        "success"
    )
    return {
        "schema_version": 6, "run_id": active_run,
        "generated_at_utc": utc_now(), "overall_status": overall,
        "expected_source_runs": len(entries),
        "healthy_source_runs": len(entries) - len(unhealthy),
        "unhealthy_source_runs": len(unhealthy),
        "source_runs_with_quality_warnings": len(warnings),
        "fetched_record_count": sum(entry["fetched_record_count"] for entry in entries),
        "accepted_record_count": sum(entry["accepted_record_count"] for entry in entries),
        "rejected_record_count": sum(entry["rejected_record_count"] for entry in entries),
        "parse_failure_count": sum(entry["parse_failure_count"] for entry in entries),
        "identity_tracked_listing_count": sum(
            entry["identity_tracked_listing_count"] for entry in entries
        ),
        "identity_new_listing_count": sum(
            entry["identity_new_listing_count"] for entry in entries
        ),
        "identity_reappeared_listing_count": sum(
            entry["identity_reappeared_listing_count"] for entry in entries
        ),
        "identity_missing_listing_count": sum(
            entry["identity_missing_listing_count"] for entry in entries
        ),
        "identity_retired_listing_count": sum(
            entry["identity_retired_listing_count"] for entry in entries
        ),
        "sources": entries,
    }


def write_health_report(
    *, root: Path, report: dict[str, Any],
) -> tuple[Path, Path]:
    root = root.resolve()
    report_dir = root / "data" / "run_status"
    json_path = report_dir / "latest.json"
    markdown_path = report_dir / "latest.md"
    write_json(json_path, report)
    report_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Vehicle Scrape Run Health", "",
        f"- Run ID: `{report['run_id']}`",
        f"- Generated: `{report['generated_at_utc']}`",
        f"- Overall status: **{str(report['overall_status']).upper()}**",
        f"- Healthy source runs: {report['healthy_source_runs']}/{report['expected_source_runs']}",
        f"- Source runs with quality warnings: {report.get('source_runs_with_quality_warnings', 0)}",
        f"- Canonical reconciliation: {report.get('fetched_record_count', 0)} fetched = "
        f"{report.get('accepted_record_count', 0)} accepted + "
        f"{report.get('rejected_record_count', 0)} rejected + "
        f"{report.get('parse_failure_count', 0)} parse failures",
        f"- Lifecycle: {report.get('identity_tracked_listing_count', 0)} tracked; "
        f"{report.get('identity_new_listing_count', 0)} new; "
        f"{report.get('identity_reappeared_listing_count', 0)} reappeared; "
        f"{report.get('identity_missing_listing_count', 0)} missing; "
        f"{report.get('identity_retired_listing_count', 0)} retired",
        "",
        "| Vehicle | Source | Collection | Evidence | Identity | Fetched | Accepted | Rejected | Parse failures | Tracked | New | Reappeared | Missing | Retired | Warnings | Failure reasons |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for entry in report["sources"]:
        reasons = ", ".join(entry["failure_reasons"]) or "—"
        lines.append(
            f"| {entry['vehicle_key']} | {entry['source']} | "
            f"{entry['collection_status']} | "
            f"{entry['evidence_reconciliation_status']} | "
            f"{entry['identity_lifecycle_status']} | "
            f"{entry['fetched_record_count']} | {entry['accepted_record_count']} | "
            f"{entry['rejected_record_count']} | {entry['parse_failure_count']} | "
            f"{entry['identity_tracked_listing_count']} | "
            f"{entry['identity_new_listing_count']} | "
            f"{entry['identity_reappeared_listing_count']} | "
            f"{entry['identity_missing_listing_count']} | "
            f"{entry['identity_retired_listing_count']} | "
            f"{entry['quality_warning_rows']} | {reasons} |"
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, markdown_path
