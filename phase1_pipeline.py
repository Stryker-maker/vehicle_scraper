"""Phase 1 uncapped, fail-visible vehicle collection pipeline."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from phase1_common import (
    DEFAULT_TIMEOUT_SECONDS, MANUAL_REVIEW_FIELDS, SOURCES, expected_output_path,
    load_json, row_quality_warnings, source_status_path, write_json,
)
from phase1_reporting import build_manual_review, collect_health, write_health_report
from phase1_runtime import (
    dedupe_history_observations_for_date, remove_history_observations_for_date,
    run_source,
)

__all__ = [
    "MANUAL_REVIEW_FIELDS", "build_manual_review", "collect_health",
    "dedupe_history_observations_for_date", "expected_output_path",
    "remove_history_observations_for_date", "row_quality_warnings", "run_source",
    "source_status_path", "write_json",
]


def config_paths(values: Sequence[str]) -> list[Path]:
    if not values:
        raise ValueError("At least one --configs path is required")
    return [Path(value) for value in values]


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    actions = root.add_subparsers(dest="action", required=True)
    run = actions.add_parser("run-source")
    run.add_argument("--source", choices=SOURCES, required=True)
    run.add_argument("--config", required=True)
    run.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    run.add_argument("command", nargs=argparse.REMAINDER)
    manual = actions.add_parser("build-manual-review")
    manual.add_argument("--configs", nargs="+", required=True)
    report = actions.add_parser("report-health")
    report.add_argument("--configs", nargs="+", required=True)
    check = actions.add_parser("check-health")
    check.add_argument("--report", default="data/run_status/latest.json")
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = Path.cwd()
    if args.action == "run-source":
        command = list(args.command)
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            raise ValueError("Collector command is required after --")
        run_source(
            root=root, source=args.source, config_path=Path(args.config),
            command=command, timeout_seconds=args.timeout_seconds,
        )
        return 0
    if args.action == "build-manual-review":
        build_manual_review(root=root, config_paths=config_paths(args.configs))
        return 0
    if args.action == "report-health":
        report = collect_health(root=root, config_paths=config_paths(args.configs))
        json_path, md_path = write_health_report(root=root, report=report)
        print(f"Health JSON: {json_path.relative_to(root)}")
        print(f"Health summary: {md_path.relative_to(root)}")
        return 0
    if args.action == "check-health":
        report = load_json(root / args.report)
        if report.get("overall_status") not in {"success", "success_with_warnings"}:
            print(
                f"Run health is {report.get('overall_status', 'unknown')}: "
                f"{report.get('unhealthy_source_runs', '?')} source run(s) unhealthy.",
                file=sys.stderr,
            )
            return 1
        message = (
            "All expected source runs produced fresh, uncapped output; data-quality "
            "warnings require manual review."
            if report.get("overall_status") == "success_with_warnings"
            else "All expected source runs produced fresh, uncapped, valid output."
        )
        print(message)
        return 0
    raise AssertionError(f"Unhandled action: {args.action}")


if __name__ == "__main__":
    raise SystemExit(main())
