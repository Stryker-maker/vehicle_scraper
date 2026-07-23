from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from phase1_common import utc_now, write_json

ANOMALY_SCHEMA_VERSION = 1
ANOMALY_POLICIES = ("enforce", "report_only")


def _source_key(value: dict[str, Any]) -> tuple[str, str]:
    return str(value.get("vehicle_key") or ""), str(value.get("source") or "")


def _number(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _anomaly(
    *,
    severity: str,
    code: str,
    vehicle_key: str,
    source: str,
    message: str,
    baseline: Any = None,
    current: Any = None,
    threshold: Any = None,
) -> dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "vehicle_key": vehicle_key,
        "source": source,
        "message": message,
        "baseline": baseline,
        "current": current,
        "threshold": threshold,
    }


def compare_health_reports(
    *, baseline: dict[str, Any] | None, current: dict[str, Any], run_id: str
) -> dict[str, Any]:
    anomalies: list[dict[str, Any]] = []
    baseline_status = "available"
    if not baseline or not isinstance(baseline.get("sources"), list):
        baseline_status = "unavailable"
    elif baseline.get("run_id") == current.get("run_id"):
        baseline_status = "same_run_not_compared"

    baseline_sources = {
        _source_key(entry): entry
        for entry in (baseline or {}).get("sources", [])
        if isinstance(entry, dict)
    }
    current_sources = [
        entry for entry in current.get("sources", []) if isinstance(entry, dict)
    ]

    for entry in current_sources:
        vehicle_key, source = _source_key(entry)
        if not entry.get("healthy"):
            anomalies.append(
                _anomaly(
                    severity="critical",
                    code="source_unhealthy",
                    vehicle_key=vehicle_key,
                    source=source,
                    message="Current source run is unhealthy.",
                    current=entry.get("execution_status"),
                    threshold="healthy=true",
                )
            )
        if entry.get("pagination_complete") is False:
            anomalies.append(
                _anomaly(
                    severity="critical",
                    code="pagination_incomplete",
                    vehicle_key=vehicle_key,
                    source=source,
                    message="Current source pagination is incomplete.",
                    current=False,
                    threshold=True,
                )
            )
        failed_pages = _number(entry.get("failed_page_count"))
        if failed_pages > 0:
            anomalies.append(
                _anomaly(
                    severity="critical",
                    code="failed_source_pages",
                    vehicle_key=vehicle_key,
                    source=source,
                    message="One or more source pages failed.",
                    current=failed_pages,
                    threshold=0,
                )
            )
        fetched = _number(entry.get("fetched_record_count"))
        parse_failures = _number(entry.get("parse_failure_count"))
        parse_rate = parse_failures / fetched if fetched else 0.0
        if parse_failures >= 5 and parse_rate >= 0.20:
            anomalies.append(
                _anomaly(
                    severity="critical",
                    code="parse_failure_rate_critical",
                    vehicle_key=vehicle_key,
                    source=source,
                    message="Parse failures exceed the critical rate.",
                    current={"count": parse_failures, "rate": round(parse_rate, 6)},
                    threshold={"minimum_count": 5, "minimum_rate": 0.20},
                )
            )
        elif parse_failures >= 3 and parse_rate >= 0.05:
            anomalies.append(
                _anomaly(
                    severity="warning",
                    code="parse_failure_rate_elevated",
                    vehicle_key=vehicle_key,
                    source=source,
                    message="Parse failures exceed the warning rate.",
                    current={"count": parse_failures, "rate": round(parse_rate, 6)},
                    threshold={"minimum_count": 3, "minimum_rate": 0.05},
                )
            )

        if baseline_status != "available":
            continue
        previous = baseline_sources.get((vehicle_key, source))
        if previous is None:
            anomalies.append(
                _anomaly(
                    severity="info",
                    code="source_has_no_baseline",
                    vehicle_key=vehicle_key,
                    source=source,
                    message="No prior source baseline is available.",
                )
            )
            continue

        for metric, minimum, warning_ratio, critical_ratio in (
            ("accepted_record_count", 10, 0.50, 0.25),
            ("fetched_record_count", 20, 0.50, 0.25),
        ):
            old = _number(previous.get(metric))
            new = _number(entry.get(metric))
            if old >= minimum:
                ratio = new / old
                if ratio < critical_ratio:
                    anomalies.append(
                        _anomaly(
                            severity="critical",
                            code=f"{metric}_collapse",
                            vehicle_key=vehicle_key,
                            source=source,
                            message=f"{metric} fell below the critical baseline ratio.",
                            baseline=old,
                            current=new,
                            threshold=critical_ratio,
                        )
                    )
                elif ratio < warning_ratio:
                    anomalies.append(
                        _anomaly(
                            severity="warning",
                            code=f"{metric}_drop",
                            vehicle_key=vehicle_key,
                            source=source,
                            message=f"{metric} fell below the warning baseline ratio.",
                            baseline=old,
                            current=new,
                            threshold=warning_ratio,
                        )
                    )
                elif new >= old * 3 and new - old >= minimum * 2:
                    anomalies.append(
                        _anomaly(
                            severity="warning",
                            code=f"{metric}_surge",
                            vehicle_key=vehicle_key,
                            source=source,
                            message=f"{metric} increased to at least three times baseline.",
                            baseline=old,
                            current=new,
                            threshold=3.0,
                        )
                    )

        old_attempts = _number(previous.get("request_attempt_count"))
        new_attempts = _number(entry.get("request_attempt_count"))
        if old_attempts >= 1 and new_attempts >= old_attempts * 3 and new_attempts - old_attempts >= 5:
            anomalies.append(
                _anomaly(
                    severity="warning",
                    code="request_attempt_surge",
                    vehicle_key=vehicle_key,
                    source=source,
                    message="Request attempts increased sharply from baseline.",
                    baseline=old_attempts,
                    current=new_attempts,
                    threshold=3.0,
                )
            )

        old_warnings = _number(previous.get("quality_warning_rows"))
        new_warnings = _number(entry.get("quality_warning_rows"))
        if new_warnings >= max(5, old_warnings * 2 + 1):
            anomalies.append(
                _anomaly(
                    severity="warning",
                    code="quality_warning_growth",
                    vehicle_key=vehicle_key,
                    source=source,
                    message="Rows with quality warnings increased materially.",
                    baseline=old_warnings,
                    current=new_warnings,
                    threshold=max(5, old_warnings * 2 + 1),
                )
            )

    counts = {
        severity: sum(value["severity"] == severity for value in anomalies)
        for severity in ("critical", "warning", "info")
    }
    status = (
        "critical" if counts["critical"] else
        "warning" if counts["warning"] else
        "clean" if baseline_status == "available" else
        "no_baseline"
    )
    return {
        "anomaly_schema_version": ANOMALY_SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at_utc": utc_now(),
        "baseline_status": baseline_status,
        "baseline_run_id": (baseline or {}).get("run_id"),
        "current_health_run_id": current.get("run_id"),
        "anomaly_status": status,
        "critical_anomaly_count": counts["critical"],
        "warning_anomaly_count": counts["warning"],
        "informational_anomaly_count": counts["info"],
        "anomalies": anomalies,
    }


def write_anomaly_report(
    *, root: Path, report: dict[str, Any]
) -> tuple[Path, Path]:
    root = root.resolve()
    report_dir = root / "data" / "run_status"
    json_path = report_dir / "anomalies_latest.json"
    markdown_path = report_dir / "anomalies_latest.md"
    write_json(json_path, report)
    report_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Vehicle Collection Anomaly Report",
        "",
        f"- Run ID: `{report['run_id']}`",
        f"- Baseline status: `{report['baseline_status']}`",
        f"- Status: **{str(report['anomaly_status']).upper()}**",
        f"- Critical: {report['critical_anomaly_count']}",
        f"- Warnings: {report['warning_anomaly_count']}",
        f"- Informational: {report['informational_anomaly_count']}",
        "",
        "| Severity | Vehicle | Source | Code | Message | Baseline | Current | Threshold |",
        "|---|---|---|---|---|---:|---:|---:|",
    ]
    for anomaly in report["anomalies"]:
        lines.append(
            f"| {anomaly['severity']} | {anomaly['vehicle_key'] or '—'} | "
            f"{anomaly['source'] or '—'} | {anomaly['code']} | {anomaly['message']} | "
            f"{json.dumps(anomaly.get('baseline'), sort_keys=True)} | "
            f"{json.dumps(anomaly.get('current'), sort_keys=True)} | "
            f"{json.dumps(anomaly.get('threshold'), sort_keys=True)} |"
        )
    if not report["anomalies"]:
        lines.append("| — | — | — | none | No anomalies detected. | — | — | — |")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, markdown_path


def load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else None


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Compare collection health with baseline")
    sub = result.add_subparsers(dest="action", required=True)
    build = sub.add_parser("build")
    build.add_argument("--baseline", required=True)
    build.add_argument("--current", required=True)
    build.add_argument("--run-id", required=True)
    check = sub.add_parser("check")
    check.add_argument("--report", default="data/run_status/anomalies_latest.json")
    check.add_argument("--policy", choices=ANOMALY_POLICIES, required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = Path.cwd()
    if args.action == "build":
        baseline = load_optional_json(Path(args.baseline))
        current = load_optional_json(Path(args.current))
        if current is None:
            raise SystemExit("Current health report is missing or invalid")
        report = compare_health_reports(
            baseline=baseline, current=current, run_id=args.run_id
        )
        paths = write_anomaly_report(root=root, report=report)
        print(json.dumps({"report": report, "artifacts": [str(path) for path in paths]}, indent=2, sort_keys=True))
        return 0
    if args.action == "check":
        report = load_optional_json(Path(args.report))
        if report is None or report.get("anomaly_schema_version") != ANOMALY_SCHEMA_VERSION:
            print("Anomaly report is missing or invalid")
            return 1
        print(json.dumps(report, indent=2, sort_keys=True))
        if args.policy == "enforce" and int(report.get("critical_anomaly_count", 0)) > 0:
            return 1
        return 0
    raise AssertionError(args.action)


if __name__ == "__main__":
    raise SystemExit(main())
