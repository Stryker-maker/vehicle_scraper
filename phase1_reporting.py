from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from phase1_common import (
    MANUAL_REVIEW_FIELDS, SOURCE_FIELDS, SOURCES, expected_output_path, load_json,
    read_csv_rows, row_quality_warnings, source_status_path,
    status_is_current_success, utc_now, write_json,
)


def transform_manual_review_row(row: dict[str, str], status: dict[str, Any]) -> dict[str, str]:
    source = row.get("source", "").strip() or str(status.get("source", ""))
    warnings = row_quality_warnings(row, source)
    transformed = {field: row.get(field, "") for field in SOURCE_FIELDS}
    transformed["source"] = source
    transformed.update({
        "ranking_status": "DISABLED_MANUAL_REVIEW_REQUIRED",
        "review_status": "manual_review_required",
        "collection_status": str(status.get("collection_status", status.get("execution_status", "unknown"))),
        "data_quality_status": "warnings_present" if warnings else "clean",
        "quality_warnings": ";".join(warnings),
        "source_run_status": str(status.get("execution_status", "unknown")),
        "source_completed_at_utc": str(status.get("completed_at_utc", "")),
        "location_status": "source_reported_not_independently_verified",
        "distance_status": "legacy_method_not_yet_disambiguated",
        "unverified_location_value": "", "unverified_distance_value": "",
    })
    if source.lower() == "kijiji":
        transformed.update({
            "review_status": "location_verification_required",
            "location_status": "unverified_search_origin_not_listing_location",
            "distance_status": "disabled_due_to_unverified_location",
            "unverified_location_value": transformed["location"],
            "unverified_distance_value": transformed["distance_km"],
            "dealer_address": "", "location": "", "distance_km": "", "distance_method": "",
        })
    elif warnings:
        transformed["review_status"] = "data_quality_review_required"
    return transformed


def build_manual_review(
    *, root: Path, config_paths: Iterable[Path], run_id: str | None = None
) -> dict[str, Any]:
    root = root.resolve()
    active_run = run_id or os.environ.get("GITHUB_RUN_ID", "local")
    summaries: list[dict[str, Any]] = []
    for raw_path in config_paths:
        config_path = raw_path if raw_path.is_absolute() else root / raw_path
        config = load_json(config_path)
        key = str(config["vehicle_key"])
        rows: list[dict[str, str]] = []
        included: list[str] = []
        excluded: dict[str, str] = {}
        for source in SOURCES:
            status_path = source_status_path(root, config, source)
            if not status_path.exists():
                excluded[source] = "missing_status"
                continue
            status = load_json(status_path)
            if not status_is_current_success(status, active_run):
                excluded[source] = str(status.get("execution_status", "not_current"))
                continue
            rows.extend(
                transform_manual_review_row(row, status)
                for row in read_csv_rows(expected_output_path(root, config, source))
            )
            included.append(source)
        rows.sort(key=lambda row: (
            row.get("source", ""), row.get("year", ""), row.get("make", ""),
            row.get("model", ""), row.get("listing_id", ""),
        ))
        manual_dir = root / "data" / key / "manual_review"
        manual_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
        archive = manual_dir / f"{key}_manual_review_{timestamp}.csv"
        latest = manual_dir / f"{key}_manual_review_latest.csv"
        for output in (archive, latest):
            with output.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=MANUAL_REVIEW_FIELDS, extrasaction="ignore")
                writer.writeheader(); writer.writerows(rows)
        marker = root / "data" / key / "merged" / "RANKING_DISABLED.md"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(
            "# Merged ranking disabled\n\nThe automated cross-source merged ranking is disabled "
            "during Phase 1. Existing merged CSV files are historical and are no longer "
            f"refreshed. Use `../manual_review/{key}_manual_review_latest.csv` for current "
            "unranked, uncapped data.\n", encoding="utf-8",
        )
        warning_rows = sum(1 for row in rows if row["quality_warnings"])
        summaries.append({
            "vehicle_key": key, "row_count": len(rows),
            "quality_warning_rows": warning_rows, "included_sources": included,
            "excluded_sources": excluded, "latest_output": str(latest.relative_to(root)),
            "archive_output": str(archive.relative_to(root)),
            "disabled_ranking_marker": str(marker.relative_to(root)),
        })
        print(f"[{key}] manual review rows={len(rows)} | warnings={warning_rows} | included={','.join(included) or 'none'}")
    return {"run_id": active_run, "vehicles": summaries}


def collect_health(
    *, root: Path, config_paths: Iterable[Path], run_id: str | None = None
) -> dict[str, Any]:
    root = root.resolve()
    active_run = run_id or os.environ.get("GITHUB_RUN_ID", "local")
    entries: list[dict[str, Any]] = []
    for raw_path in config_paths:
        config_path = raw_path if raw_path.is_absolute() else root / raw_path
        config = load_json(config_path)
        for source in SOURCES:
            status_path = source_status_path(root, config, source)
            if status_path.exists():
                status = load_json(status_path)
                entries.append({
                    "vehicle_key": config["vehicle_key"], "source": source,
                    "healthy": status_is_current_success(status, active_run),
                    "current_run": status.get("run_id") == active_run,
                    "execution_status": status.get("execution_status", "unknown"),
                    "collection_status": status.get("collection_status", status.get("execution_status", "unknown")),
                    "data_quality_status": status.get("data_quality_status", "not_evaluated"),
                    "quality_warning_rows": status.get("quality_warning_rows", 0),
                    "quality_warning_count": status.get("quality_warning_count", 0),
                    "quality_warning_summary": status.get("quality_warning_summary", {}),
                    "row_count": status.get("row_count", 0),
                    "failure_reasons": status.get("failure_reasons", []),
                    "status_path": str(status_path.relative_to(root)),
                })
            else:
                entries.append({
                    "vehicle_key": config["vehicle_key"], "source": source,
                    "healthy": False, "current_run": False, "execution_status": "missing",
                    "collection_status": "missing", "data_quality_status": "not_evaluated",
                    "quality_warning_rows": 0, "quality_warning_count": 0,
                    "quality_warning_summary": {}, "row_count": 0,
                    "failure_reasons": ["missing_status"],
                    "status_path": str(status_path.relative_to(root)),
                })
    unhealthy = [entry for entry in entries if not entry["healthy"]]
    warnings = [entry for entry in entries if entry["data_quality_status"] == "warnings_present"]
    overall = "degraded" if unhealthy else "success_with_warnings" if warnings else "success"
    return {
        "schema_version": 2, "run_id": active_run, "generated_at_utc": utc_now(),
        "overall_status": overall, "expected_source_runs": len(entries),
        "healthy_source_runs": len(entries) - len(unhealthy),
        "unhealthy_source_runs": len(unhealthy),
        "source_runs_with_quality_warnings": len(warnings), "sources": entries,
    }


def write_health_report(*, root: Path, report: dict[str, Any]) -> tuple[Path, Path]:
    root = root.resolve(); report_dir = root / "data" / "run_status"
    json_path = report_dir / "latest.json"; markdown_path = report_dir / "latest.md"
    write_json(json_path, report); report_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Vehicle Scrape Run Health", "", f"- Run ID: `{report['run_id']}`",
        f"- Generated: `{report['generated_at_utc']}`",
        f"- Overall status: **{str(report['overall_status']).upper()}**",
        f"- Healthy source runs: {report['healthy_source_runs']}/{report['expected_source_runs']}",
        f"- Source runs with quality warnings: {report.get('source_runs_with_quality_warnings', 0)}",
        "", "| Vehicle | Source | Collection | Data quality | Rows | Warning rows | Failure reasons |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for entry in report["sources"]:
        reasons = ", ".join(entry["failure_reasons"]) or "—"
        lines.append(
            f"| {entry['vehicle_key']} | {entry['source']} | {entry['collection_status']} | "
            f"{entry['data_quality_status']} | {entry['row_count']} | "
            f"{entry['quality_warning_rows']} | {reasons} |"
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, markdown_path
