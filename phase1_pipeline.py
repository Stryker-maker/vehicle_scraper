"""Phase 1 reliability controls for the vehicle scraper workflow.

The existing source scrapers remain responsible for collection. This module wraps
those scrapers with explicit run-status evidence, builds an unranked manual-review
file from fresh outputs, and makes degraded runs visible without stopping the
remaining source collectors.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

SOURCES = ("autotrader", "kijiji")
REQUIRED_COLUMNS = {
    "listing_id",
    "url",
    "source",
    "price",
    "mileage",
    "location",
    "distance_km",
}

SOURCE_FIELDS = [
    "year",
    "make",
    "model",
    "trim",
    "trim_tier",
    "price",
    "price_history",
    "trend",
    "weeks_tracked",
    "price_first_seen",
    "price_last_week",
    "price_change_week",
    "price_change_total",
    "mileage",
    "engine",
    "fuel",
    "accident_flag",
    "days_on_market",
    "dealer",
    "seller_type",
    "dealer_address",
    "location",
    "distance_km",
    "distance_method",
    "listing_id",
    "url",
    "source",
]

MANUAL_REVIEW_FIELDS = [
    "ranking_status",
    "review_status",
    "source_run_status",
    "source_completed_at_utc",
    "location_status",
    "distance_status",
    "unverified_location_value",
    "unverified_distance_value",
    *SOURCE_FIELDS,
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    temporary.replace(path)


def expected_output_path(root: Path, config: dict[str, Any], source: str) -> Path:
    if source not in SOURCES:
        raise ValueError(f"Unsupported source: {source}")
    vehicle_key = str(config["vehicle_key"])
    return root / "data" / vehicle_key / "latest" / f"{vehicle_key}_{source}_latest.csv"


def source_status_path(root: Path, config: dict[str, Any], source: str) -> Path:
    vehicle_key = str(config["vehicle_key"])
    return root / "data" / vehicle_key / "run_status" / f"{source}_latest.json"


def file_signature(path: Path) -> tuple[int, int] | None:
    if not path.exists():
        return None
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size


def validate_csv(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_valid": False,
        "row_count": 0,
        "missing_columns": sorted(REQUIRED_COLUMNS),
        "validation_error": None,
    }
    if not path.exists():
        result["validation_error"] = "output_file_missing"
        return result

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = set(reader.fieldnames or [])
            missing = sorted(REQUIRED_COLUMNS - fieldnames)
            row_count = sum(1 for _ in reader)
        result.update(
            {
                "schema_valid": not missing,
                "row_count": row_count,
                "missing_columns": missing,
            }
        )
    except (OSError, csv.Error, UnicodeError) as exc:
        result["validation_error"] = f"{type(exc).__name__}: {exc}"
    return result


def run_source(
    *,
    root: Path,
    source: str,
    config_path: Path,
    command: Sequence[str],
    run_id: str | None = None,
) -> dict[str, Any]:
    """Run one source collector and persist explicit success/degradation evidence.

    The returned process status is recorded, but this function does not raise for a
    collector failure. That lets the workflow continue collecting from other
    sources before the final health gate marks the overall run degraded.
    """

    root = root.resolve()
    config_path = config_path if config_path.is_absolute() else root / config_path
    config = load_json(config_path)
    output_path = expected_output_path(root, config, source)
    status_path = source_status_path(root, config, source)
    before_signature = file_signature(output_path)
    started_at = utc_now()
    started_ns = time.time_ns()

    completed = subprocess.run(
        list(command),
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="" if completed.stderr.endswith("\n") else "\n")

    after_signature = file_signature(output_path)
    output_updated = bool(
        after_signature
        and (
            before_signature is None
            or after_signature != before_signature
            or after_signature[0] >= started_ns
        )
    )
    validation = validate_csv(output_path)

    failure_reasons: list[str] = []
    if completed.returncode != 0:
        failure_reasons.append("collector_command_failed")
    if not output_updated:
        failure_reasons.append("no_fresh_output")
    if not validation["schema_valid"]:
        failure_reasons.append("invalid_output_schema")
    if validation["row_count"] < 1:
        failure_reasons.append("empty_output")

    if completed.returncode != 0:
        execution_status = "failed"
    elif failure_reasons:
        execution_status = "degraded"
    else:
        execution_status = "success"

    status = {
        "schema_version": 1,
        "run_id": run_id or os.environ.get("GITHUB_RUN_ID", "local"),
        "vehicle_key": config["vehicle_key"],
        "source": source,
        "config_path": str(config_path.relative_to(root)),
        "command": list(command),
        "started_at_utc": started_at,
        "completed_at_utc": utc_now(),
        "execution_status": execution_status,
        "exit_code": completed.returncode,
        "failure_reasons": failure_reasons,
        "expected_output": str(output_path.relative_to(root)),
        "output_exists": output_path.exists(),
        "output_updated_this_run": output_updated,
        **validation,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }
    write_json(status_path, status)

    print(
        f"[{config['vehicle_key']}:{source}] {execution_status} | "
        f"rows={validation['row_count']} | fresh={output_updated}"
    )
    return status


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def status_is_current_success(status: dict[str, Any], run_id: str) -> bool:
    return (
        status.get("run_id") == run_id
        and status.get("execution_status") == "success"
        and status.get("output_updated_this_run") is True
        and status.get("schema_valid") is True
        and int(status.get("row_count", 0)) > 0
    )


def transform_manual_review_row(
    row: dict[str, str], status: dict[str, Any]
) -> dict[str, str]:
    source = row.get("source", "").strip() or str(status.get("source", ""))
    transformed = {field: row.get(field, "") for field in SOURCE_FIELDS}
    transformed["source"] = source
    transformed.update(
        {
            "ranking_status": "DISABLED_MANUAL_REVIEW_REQUIRED",
            "review_status": "manual_review_required",
            "source_run_status": str(status.get("execution_status", "unknown")),
            "source_completed_at_utc": str(status.get("completed_at_utc", "")),
            "location_status": "source_reported_not_independently_verified",
            "distance_status": "legacy_method_not_yet_disambiguated",
            "unverified_location_value": "",
            "unverified_distance_value": "",
        }
    )

    if source.lower() == "kijiji":
        transformed["review_status"] = "location_verification_required"
        transformed["location_status"] = "unverified_search_origin_not_listing_location"
        transformed["distance_status"] = "disabled_due_to_unverified_location"
        transformed["unverified_location_value"] = transformed["location"]
        transformed["unverified_distance_value"] = transformed["distance_km"]
        transformed["dealer_address"] = ""
        transformed["location"] = ""
        transformed["distance_km"] = ""
        transformed["distance_method"] = ""

    return transformed


def build_manual_review(
    *, root: Path, config_paths: Iterable[Path], run_id: str | None = None
) -> dict[str, Any]:
    root = root.resolve()
    active_run_id = run_id or os.environ.get("GITHUB_RUN_ID", "local")
    summaries: list[dict[str, Any]] = []

    for raw_config_path in config_paths:
        config_path = raw_config_path if raw_config_path.is_absolute() else root / raw_config_path
        config = load_json(config_path)
        vehicle_key = str(config["vehicle_key"])
        rows: list[dict[str, str]] = []
        included_sources: list[str] = []
        excluded_sources: dict[str, str] = {}

        for source in SOURCES:
            status_path = source_status_path(root, config, source)
            if not status_path.exists():
                excluded_sources[source] = "missing_status"
                continue
            status = load_json(status_path)
            if not status_is_current_success(status, active_run_id):
                excluded_sources[source] = str(status.get("execution_status", "not_current"))
                continue
            output_path = expected_output_path(root, config, source)
            for row in read_csv_rows(output_path):
                rows.append(transform_manual_review_row(row, status))
            included_sources.append(source)

        rows.sort(
            key=lambda row: (
                row.get("source", ""),
                row.get("year", ""),
                row.get("make", ""),
                row.get("model", ""),
                row.get("listing_id", ""),
            )
        )

        manual_dir = root / "data" / vehicle_key / "manual_review"
        manual_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
        archive_path = manual_dir / f"{vehicle_key}_manual_review_{timestamp}.csv"
        latest_path = manual_dir / f"{vehicle_key}_manual_review_latest.csv"
        for output_path in (archive_path, latest_path):
            with output_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=MANUAL_REVIEW_FIELDS, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)

        disabled_marker = root / "data" / vehicle_key / "merged" / "RANKING_DISABLED.md"
        disabled_marker.parent.mkdir(parents=True, exist_ok=True)
        disabled_marker.write_text(
            "# Merged ranking disabled\n\n"
            "The automated cross-source merged ranking is disabled during Phase 1 "
            "because the source scores are not comparable and Kijiji locations are "
            "not yet trustworthy. Existing merged CSV files in this directory are "
            "historical and are no longer refreshed.\n\n"
            f"Use `../manual_review/{vehicle_key}_manual_review_latest.csv` for the "
            "current unranked data collected from fresh, validated source runs.\n",
            encoding="utf-8",
        )

        summaries.append(
            {
                "vehicle_key": vehicle_key,
                "row_count": len(rows),
                "included_sources": included_sources,
                "excluded_sources": excluded_sources,
                "latest_output": str(latest_path.relative_to(root)),
                "archive_output": str(archive_path.relative_to(root)),
                "disabled_ranking_marker": str(disabled_marker.relative_to(root)),
            }
        )
        print(
            f"[{vehicle_key}] manual review rows={len(rows)} | "
            f"included={','.join(included_sources) or 'none'}"
        )

    return {"run_id": active_run_id, "vehicles": summaries}


def collect_health(
    *, root: Path, config_paths: Iterable[Path], run_id: str | None = None
) -> dict[str, Any]:
    root = root.resolve()
    active_run_id = run_id or os.environ.get("GITHUB_RUN_ID", "local")
    entries: list[dict[str, Any]] = []

    for raw_config_path in config_paths:
        config_path = raw_config_path if raw_config_path.is_absolute() else root / raw_config_path
        config = load_json(config_path)
        for source in SOURCES:
            status_path = source_status_path(root, config, source)
            if status_path.exists():
                status = load_json(status_path)
                current = status.get("run_id") == active_run_id
                healthy = status_is_current_success(status, active_run_id)
                entries.append(
                    {
                        "vehicle_key": config["vehicle_key"],
                        "source": source,
                        "healthy": healthy,
                        "current_run": current,
                        "execution_status": status.get("execution_status", "unknown"),
                        "row_count": status.get("row_count", 0),
                        "failure_reasons": status.get("failure_reasons", []),
                        "status_path": str(status_path.relative_to(root)),
                    }
                )
            else:
                entries.append(
                    {
                        "vehicle_key": config["vehicle_key"],
                        "source": source,
                        "healthy": False,
                        "current_run": False,
                        "execution_status": "missing",
                        "row_count": 0,
                        "failure_reasons": ["missing_status"],
                        "status_path": str(status_path.relative_to(root)),
                    }
                )

    unhealthy = [entry for entry in entries if not entry["healthy"]]
    return {
        "schema_version": 1,
        "run_id": active_run_id,
        "generated_at_utc": utc_now(),
        "overall_status": "success" if not unhealthy else "degraded",
        "expected_source_runs": len(entries),
        "healthy_source_runs": len(entries) - len(unhealthy),
        "unhealthy_source_runs": len(unhealthy),
        "sources": entries,
    }


def write_health_report(*, root: Path, report: dict[str, Any]) -> tuple[Path, Path]:
    root = root.resolve()
    report_dir = root / "data" / "run_status"
    json_path = report_dir / "latest.json"
    markdown_path = report_dir / "latest.md"
    write_json(json_path, report)

    report_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Vehicle Scrape Run Health",
        "",
        f"- Run ID: `{report['run_id']}`",
        f"- Generated: `{report['generated_at_utc']}`",
        f"- Overall status: **{str(report['overall_status']).upper()}**",
        f"- Healthy source runs: {report['healthy_source_runs']}/{report['expected_source_runs']}",
        "",
        "| Vehicle | Source | Status | Rows | Failure reasons |",
        "|---|---|---:|---:|---|",
    ]
    for entry in report["sources"]:
        reasons = ", ".join(entry["failure_reasons"]) or "—"
        lines.append(
            f"| {entry['vehicle_key']} | {entry['source']} | "
            f"{entry['execution_status']} | {entry['row_count']} | {reasons} |"
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, markdown_path


def parse_config_paths(values: Sequence[str]) -> list[Path]:
    if not values:
        raise ValueError("At least one --configs path is required")
    return [Path(value) for value in values]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)

    run_parser = subparsers.add_parser("run-source")
    run_parser.add_argument("--source", choices=SOURCES, required=True)
    run_parser.add_argument("--config", required=True)
    run_parser.add_argument("command", nargs=argparse.REMAINDER)

    manual_parser = subparsers.add_parser("build-manual-review")
    manual_parser.add_argument("--configs", nargs="+", required=True)

    report_parser = subparsers.add_parser("report-health")
    report_parser.add_argument("--configs", nargs="+", required=True)

    check_parser = subparsers.add_parser("check-health")
    check_parser.add_argument("--report", default="data/run_status/latest.json")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path.cwd()

    if args.action == "run-source":
        command = list(args.command)
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            raise ValueError("Collector command is required after --")
        run_source(
            root=root,
            source=args.source,
            config_path=Path(args.config),
            command=command,
        )
        return 0

    if args.action == "build-manual-review":
        build_manual_review(root=root, config_paths=parse_config_paths(args.configs))
        return 0

    if args.action == "report-health":
        report = collect_health(root=root, config_paths=parse_config_paths(args.configs))
        json_path, markdown_path = write_health_report(root=root, report=report)
        print(f"Health JSON: {json_path.relative_to(root)}")
        print(f"Health summary: {markdown_path.relative_to(root)}")
        return 0

    if args.action == "check-health":
        report_path = root / args.report
        report = load_json(report_path)
        if report.get("overall_status") != "success":
            print(
                f"Run health is {report.get('overall_status', 'unknown')}: "
                f"{report.get('unhealthy_source_runs', '?')} source run(s) unhealthy.",
                file=sys.stderr,
            )
            return 1
        print("All expected source runs produced fresh, valid output.")
        return 0

    raise AssertionError(f"Unhandled action: {args.action}")


if __name__ == "__main__":
    raise SystemExit(main())
