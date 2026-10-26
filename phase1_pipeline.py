"""Phase 1 uncapped, fail-visible vehicle collection pipeline."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

from canonical_evidence import (
    EVIDENCE_SCHEMA_VERSION, build_canonical_evidence, canonical_artifact_paths,
    read_jsonl,
)
from identity_lifecycle import IDENTITY_LIFECYCLE_SCHEMA_VERSION
from phase1_common import (
    DEFAULT_TIMEOUT_SECONDS, MANUAL_REVIEW_FIELDS, SOURCES, expected_output_path,
    load_json, row_quality_warnings, source_status_path, write_json,
)
from phase1_reporting import build_manual_review, collect_health, write_health_report
from phase1_runtime import (
    dedupe_history_observations_for_date, remove_history_observations_for_date,
    run_source,
)
from vehicle_registry import DEFAULT_REGISTRY_PATH, active_source_plan, registry_entries
from workflow_anomalies import isolate_anomalous_collections

__all__ = [
    "EVIDENCE_SCHEMA_VERSION", "IDENTITY_LIFECYCLE_SCHEMA_VERSION",
    "MANUAL_REVIEW_FIELDS", "build_canonical_evidence",
    "canonical_artifact_paths", "read_jsonl", "build_manual_review",
    "collect_health", "dedupe_history_observations_for_date",
    "expected_output_path", "remove_history_observations_for_date",
    "row_quality_warnings", "run_source", "source_status_path", "write_json",
]


def config_paths(values: Sequence[str]) -> list[Path]:
    if not values:
        raise ValueError("At least one --configs path is required")
    return [Path(value) for value in values]


def add_reporting_scope_arguments(action: argparse.ArgumentParser) -> None:
    scope = action.add_mutually_exclusive_group(required=True)
    scope.add_argument("--registry")
    scope.add_argument("--configs", nargs="+")


def reporting_source_plan(args: argparse.Namespace, *, root: Path):
    if args.registry:
        event_name = os.environ.get("GITHUB_EVENT_NAME", "local")
        entries = registry_entries(root=root, registry_path=Path(args.registry))
        if event_name == "schedule":
            return [
                (Path(entry["config_path"]), tuple(entry["enabled_sources"]))
                for entry in entries
                if entry["enabled"] and entry["cadence"] == "weekly"
            ]
        else:
            return [
                (Path(entry["config_path"]), tuple(entry["enabled_sources"]))
                for entry in entries
                if entry["enabled"]
            ]
    return [(path, SOURCES) for path in config_paths(args.configs)]


def _raise_for_canonical_review_exclusions(summary: dict) -> None:
    failures: list[str] = []
    integrity_tokens = (
        "evidence", "accepted_", "identity", "lifecycle", "canonical_listing",
    )
    for vehicle in summary.get("vehicles", []):
        for source, reason in vehicle.get("excluded_sources", {}).items():
            reason_text = str(reason)
            if any(token in reason_text.casefold() for token in integrity_tokens):
                failures.append(
                    f"{vehicle.get('vehicle_key', 'unknown')}:{source}:{reason_text}"
                )
    if failures:
        raise RuntimeError(
            "Canonical evidence integrity prevented manual-review generation: "
            + ", ".join(failures)
        )


def _source_key(value: dict) -> tuple[str, str]:
    return str(value.get("vehicle_key") or ""), str(value.get("source") or "")


def _collection_keys(entries: list[dict], field: str) -> set[tuple[str, str]]:
    """Validate collection identities and return their unique keys."""
    keys = [_source_key(entry) for entry in entries]
    if any(not vehicle_key.strip() or not source.strip() for vehicle_key, source in keys):
        raise RuntimeError(f"{field} contains an empty collection identity")
    if len(set(keys)) != len(keys):
        raise RuntimeError(f"{field} contains duplicate collection identities")
    return set(keys)


def _validate_isolation_for_health_gate(*, health: dict, anomaly: dict) -> None:
    """Fail closed unless every unhealthy source is explicitly and successfully isolated."""
    if anomaly.get("run_id") != health.get("run_id"):
        raise RuntimeError("Anomaly report run_id does not match the current health report")

    isolation_failures = [
        item for item in anomaly.get("anomalies", [])
        if isinstance(item, dict) and item.get("code") == "collection_isolation_failed"
    ]
    if isolation_failures:
        raise RuntimeError("Collection isolation reported one or more failures")

    unhealthy = {
        _source_key(entry)
        for entry in health.get("sources", [])
        if isinstance(entry, dict) and not entry.get("healthy")
    }
    raw_isolated = anomaly.get("isolated_collections", [])
    raw_no_output = anomaly.get("no_output_collections", [])
    if not isinstance(raw_isolated, list) or any(not isinstance(item, dict) for item in raw_isolated):
        raise RuntimeError("isolated_collections must be a list of objects")
    if not isinstance(raw_no_output, list) or any(not isinstance(item, dict) for item in raw_no_output):
        raise RuntimeError("no_output_collections must be a list of objects")

    isolated = _collection_keys(raw_isolated, "isolated_collections")
    no_output = _collection_keys(raw_no_output, "no_output_collections")
    if isolated & no_output:
        raise RuntimeError("Isolation outcome contains collections classified as both isolated and no-output")

    classified = isolated | no_output
    raw_requested = anomaly.get("isolation_requested_collections", raw_isolated)
    if not isinstance(raw_requested, list) or any(
        not isinstance(item, dict) for item in raw_requested
    ):
        raise RuntimeError("isolation_requested_collections must be a list of objects")
    requested = _collection_keys(raw_requested, "isolation_requested_collections")
    if requested != classified:
        raise RuntimeError(
            "isolation_requested_collections does not match the classified isolation outcomes"
        )
    if unhealthy != classified:
        missing = sorted(unhealthy - classified)
        unexpected = sorted(classified - unhealthy)
        raise RuntimeError(
            "Unhealthy source isolation is incomplete: "
            f"missing={missing}, unexpected={unexpected}"
        )


def _validate_post_isolation_outcomes(
    *, result: object, anomaly: dict, requested_keys: set[tuple[str, str]]
) -> None:
    """Check the isolator return value against its post-mutation outcome report."""
    reported_isolated = anomaly.get("isolated_collections", [])
    reported_no_output = anomaly.get("no_output_collections", [])
    if (
        not isinstance(reported_isolated, list)
        or any(not isinstance(item, dict) for item in reported_isolated)
        or not isinstance(reported_no_output, list)
        or any(not isinstance(item, dict) for item in reported_no_output)
    ):
        raise RuntimeError(
            "Collection anomaly isolation produced malformed outcome classifications"
        )

    if not isinstance(result, list) or any(not isinstance(item, dict) for item in result):
        raise RuntimeError(
            "Collection anomaly isolation returned a malformed isolated collection list"
        )
    returned_keys = [_source_key(item) for item in result]
    isolated_keys = _collection_keys(reported_isolated, "isolated_collections")
    no_output_keys = _collection_keys(reported_no_output, "no_output_collections")
    if (
        len(returned_keys) != len(set(returned_keys))
        or set(returned_keys) != isolated_keys
        or isolated_keys & no_output_keys
        or isolated_keys | no_output_keys != requested_keys
    ):
        raise RuntimeError(
            "Collection anomaly isolation did not produce consistent outcomes "
            "for the requested isolation set"
        )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    actions = root.add_subparsers(dest="action", required=True)
    run = actions.add_parser("run-source")
    run.add_argument("--source", choices=SOURCES, required=True)
    run.add_argument("--config", required=True)
    run.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    run.add_argument("command", nargs=argparse.REMAINDER)
    manual = actions.add_parser("build-manual-review")
    add_reporting_scope_arguments(manual)
    report = actions.add_parser("report-health")
    add_reporting_scope_arguments(report)
    check = actions.add_parser("check-health")
    check.add_argument("--report", default="data/run_status/latest.json")
    check.add_argument(
        "--anomaly-report", default="data/run_status/anomalies_latest.json"
    )
    return root


def _handle_run_source(args: argparse.Namespace, root: Path) -> int:
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


def _handle_build_manual_review(args: argparse.Namespace, root: Path) -> int:
    summary = build_manual_review(
        root=root, source_plan=reporting_source_plan(args, root=root)
    )
    _raise_for_canonical_review_exclusions(summary)
    return 0


def _handle_report_health(args: argparse.Namespace, root: Path) -> int:
    report = collect_health(
        root=root, source_plan=reporting_source_plan(args, root=root)
    )
    json_path, md_path = write_health_report(root=root, report=report)
    print(f"Health JSON: {json_path.relative_to(root)}")
    print(f"Health summary: {md_path.relative_to(root)}")
    return 0


def _handle_check_health(args: argparse.Namespace, root: Path) -> int:
    report = load_json(root / args.report)
    if report.get("overall_status") not in {"success", "success_with_warnings"}:
        if not args.anomaly_report:
            print(
                f"Run health is {report.get('overall_status', 'unknown')}: "
                f"{report.get('unhealthy_source_runs', '?')} source run(s) unhealthy.",
                file=sys.stderr,
            )
            return 1
        anomaly_path = root / args.anomaly_report
        if not anomaly_path.exists():
            print(
                f"Run health is {report.get('overall_status', 'unknown')}, but the "
                f"required anomaly report is missing: {args.anomaly_report}",
                file=sys.stderr,
            )
            return 1
        anomaly = load_json(anomaly_path)
        if anomaly.get("run_id") != report.get("run_id"):
            print(
                "Collection anomaly isolation failed: Anomaly report run_id does "
                "not match the current health report",
                file=sys.stderr,
            )
            return 1
        raw_isolated_collections = anomaly.get("isolated_collections", [])
        if (
            not isinstance(raw_isolated_collections, list)
            or any(not isinstance(item, dict) for item in raw_isolated_collections)
        ):
            print(
                "Collection anomaly isolation failed: "
                "isolated_collections must be a list of objects",
                file=sys.stderr,
            )
            return 1
        try:
            _validate_isolation_for_health_gate(health=report, anomaly=anomaly)
            requested_entries = anomaly.get(
                "isolation_requested_collections", raw_isolated_collections
            )
            requested_keys = {_source_key(item) for item in requested_entries}
            isolated = isolate_anomalous_collections(root=root, report=anomaly)

            # Isolation may reclassify entries as no-output, so validate the
            # post-call report rather than comparing against the pre-call isolated list.
            _validate_post_isolation_outcomes(
                result=isolated, anomaly=anomaly, requested_keys=requested_keys
            )
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"Collection anomaly isolation failed: {exc}", file=sys.stderr)
            return 1
        print(
            f"Run health is {report.get('overall_status', 'unknown')}, but all "
            f"{report.get('unhealthy_source_runs', 0)} unhealthy source run(s) "
            "are either quarantined or confirmed to have no current-run output to quarantine; "
            "healthy collections may continue."
        )
        return 0
    message = (
        "All expected source runs produced fresh, uncapped output with reconciled "
        "canonical and identity/lifecycle evidence; data-quality warnings require manual review."
        if report.get("overall_status") == "success_with_warnings"
        else "All expected source runs produced fresh, uncapped output with reconciled canonical and identity/lifecycle evidence."
    )
    print(message)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = Path.cwd()
    handlers = {
        "run-source": _handle_run_source,
        "build-manual-review": _handle_build_manual_review,
        "report-health": _handle_report_health,
        "check-health": _handle_check_health,
    }
    handler = handlers.get(args.action)
    if handler is None:
        raise ValueError(f"Unknown action: {args.action}")
    return handler(args, root)


if __name__ == "__main__":
    raise SystemExit(main())
