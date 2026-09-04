from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Sequence

from autotrader_adapter import ADAPTER_SCHEMA_VERSION
from autotrader_canonical import build_autotrader_canonical_evidence
from baseline_compatibility import build_compatibility_fingerprint
from canonical_evidence import EVIDENCE_SCHEMA_VERSION
from identity_lifecycle import (
    IDENTITY_LIFECYCLE_SCHEMA_VERSION,
    restore_artifacts,
    snapshot_artifacts,
    update_source_identity_lifecycle,
)
from phase1_common import (
    DEFAULT_TIMEOUT_SECONDS, analyze_csv_quality, expected_output_path,
    file_signature, source_status_path, utc_now, validate_csv, write_json,
)
from vehicle_config import CONFIG_SCHEMA_VERSION, load_vehicle_config

SOURCE_STATUS_SCHEMA_VERSION = 8
COLLECTION_SCOPE = "full"
VALID_COLLECTION_SCOPES = ("full", "single_pair")


def _empty_evidence() -> dict[str, Any]:
    return {
        "source_adapter_schema_version": ADAPTER_SCHEMA_VERSION,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "fetched_records": 0,
        "normalized_records": 0,
        "accepted_records": 0,
        "rejected_records": 0,
        "parse_failures": 0,
        "reconciled": False,
        "fetched_record_scope": "not_evaluated",
        "source_fetch_completeness": "not_evaluated",
        "pagination_complete": False,
        "page_request_count": 0,
        "request_attempt_count": 0,
        "successful_page_count": 0,
        "failed_page_count": 0,
        "artifacts": {},
        "source_adapter_artifacts": {},
    }


def _empty_identity() -> dict[str, Any]:
    return {
        "identity_lifecycle_schema_version": IDENTITY_LIFECYCLE_SCHEMA_VERSION,
        "observed_current_count": 0,
        "tracked_listing_count": 0,
        "new_listing_count": 0,
        "reappeared_listing_count": 0,
        "active_listing_count": 0,
        "current_reappeared_listing_count": 0,
        "missing_listing_count": 0,
        "retired_listing_count": 0,
        "transition_event_count": 0,
        "artifacts": {},
    }


def run_autotrader(
    *, root: Path, config_path: Path, command: Sequence[str] | None = None,
    run_id: str | None = None, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    root = root.resolve()
    config_path = config_path if config_path.is_absolute() else root / config_path
    original_config = config_path.read_bytes()
    config = load_vehicle_config(config_path)
    collection_scope = os.environ.get("COLLECTION_SCOPE", COLLECTION_SCOPE)
    if collection_scope not in VALID_COLLECTION_SCOPES:
        raise ValueError(f"Unsupported collection scope: {collection_scope}")
    compatibility_identity, compatibility_fingerprint = build_compatibility_fingerprint(
        config=config,
        source="autotrader",
        collection_scope=collection_scope,
        adapter_schema_version=ADAPTER_SCHEMA_VERSION,
    )
    active_run = run_id or os.environ.get("GITHUB_RUN_ID", "local")
    output_path = expected_output_path(root, config, "autotrader")
    status_path = source_status_path(root, config, "autotrader")
    identity_before = snapshot_artifacts(root, config, "autotrader")
    before_signature = file_signature(output_path)
    started_at = utc_now()
    started_ns = time.time_ns()
    command = list(command or [
        sys.executable, "autotrader_adapter.py", "--config",
        str(config_path.relative_to(root)),
    ])

    stdout = stderr = ""
    returncode: int | None = None
    timed_out = False
    try:
        completed = subprocess.run(
            command, cwd=root, text=True, capture_output=True,
            check=False, timeout=timeout_seconds, env=os.environ.copy(),
        )
        returncode = completed.returncode
        stdout, stderr = completed.stdout or "", completed.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = (exc.stdout or "").decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = (exc.stderr or "").decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")

    for text, stream in ((stdout, sys.stdout), (stderr, sys.stderr)):
        if text:
            tail = text[-4000:]
            print(tail, file=stream, end="" if tail.endswith("\n") else "\n")

    after_signature = file_signature(output_path)
    fresh = bool(after_signature and (
        before_signature is None or after_signature != before_signature
        or after_signature[0] >= started_ns
    ))
    validation = validate_csv(output_path)
    observed_rows = int(validation["row_count"])
    current_rows = observed_rows if fresh else 0
    stale_rows = observed_rows if output_path.exists() and not fresh else 0

    failures: list[str] = []
    if timed_out:
        failures.append("collector_timed_out")
    elif returncode != 0:
        failures.append("collector_command_failed")
    if not fresh:
        failures.append("no_fresh_output")
    if fresh and not validation["schema_valid"]:
        failures.append("invalid_output_schema")
    if fresh and current_rows < 1:
        failures.append("empty_output")

    evidence = _empty_evidence()
    evidence_error: str | None = None
    identity = _empty_identity()
    identity_error: str | None = None
    completed_at = utc_now()
    if fresh and validation["schema_valid"]:
        try:
            evidence = build_autotrader_canonical_evidence(
                root=root, config=config, run_id=active_run,
                completed_at_utc=completed_at,
            )
        except Exception as exc:
            evidence_error = f"{type(exc).__name__}: {exc}"
            failures.append("canonical_evidence_failed")
        else:
            if evidence.get("reconciled") is not True:
                failures.append("evidence_reconciliation_failed")
            if evidence.get("pagination_complete") is not True:
                failures.append("pagination_incomplete")
            if int(evidence.get("accepted_records", 0)) < 1:
                failures.append("no_accepted_records")
            if int(evidence.get("accepted_records", 0)) != current_rows:
                failures.append("accepted_output_count_mismatch")
            if not failures:
                try:
                    identity = update_source_identity_lifecycle(
                        root=root, config=config, source="autotrader",
                        run_id=active_run, observed_at_utc=completed_at,
                        accepted_artifact=str(evidence["artifacts"]["accepted"]),
                        adapter_records_artifact=str(
                            evidence.get("source_adapter_artifacts", {}).get("records")
                            or ""
                        ) or None,
                    )
                except Exception as exc:
                    identity_error = f"{type(exc).__name__}: {exc}"
                    failures.append("identity_lifecycle_failed")
                else:
                    if int(identity.get("observed_current_count", -1)) != current_rows:
                        failures.append("identity_current_count_mismatch")

    config_isolated = config_path.read_bytes() == original_config
    if not config_isolated:
        config_path.write_bytes(original_config)
        failures.append("approved_config_mutated")

    status_name = (
        "timed_out" if timed_out else "failed" if returncode not in (0, None)
        else "degraded" if failures else "success"
    )
    if status_name != "success":
        restore_artifacts(identity_before)

    if fresh and validation["schema_valid"]:
        quality = analyze_csv_quality(output_path, "autotrader")
    elif stale_rows:
        quality = {
            "data_quality_status": "not_evaluated_stale_output",
            "quality_warning_rows": 0, "quality_warning_count": 0,
            "quality_warning_summary": {},
        }
    else:
        quality = {
            "data_quality_status": "not_evaluated",
            "quality_warning_rows": 0, "quality_warning_count": 0,
            "quality_warning_summary": {},
        }

    status = {
        "schema_version": SOURCE_STATUS_SCHEMA_VERSION,
        "configuration_schema_version": CONFIG_SCHEMA_VERSION,
        "canonical_evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "source_adapter_schema_version": ADAPTER_SCHEMA_VERSION,
        "identity_lifecycle_schema_version": IDENTITY_LIFECYCLE_SCHEMA_VERSION,
        "runtime_config_projection": "direct_schema_v2",
        "approved_config_contains_legacy_controls": False,
        "run_id": active_run,
        "vehicle_key": config["vehicle_key"], "source": "autotrader",
        "collection_scope": collection_scope,
        "compatibility_identity": compatibility_identity,
        "compatibility_fingerprint": compatibility_fingerprint,
        "config_path": str(config_path.relative_to(root)), "command": command,
        "started_at_utc": started_at, "completed_at_utc": completed_at,
        "execution_status": status_name, "collection_status": status_name,
        "exit_code": returncode, "timed_out": timed_out,
        "timeout_seconds": timeout_seconds, "failure_reasons": failures,
        "expected_output": str(output_path.relative_to(root)),
        "output_exists": output_path.exists(), "output_updated_this_run": fresh,
        "configured_max_results": None,
        "effective_max_results": "unbounded", "row_cap_disabled": True,
        "config_isolated": config_isolated,
        "distance_processing_disabled": False,
        "distance_filter_disabled": False,
        "legacy_source_ranking_disabled": True,
        "legacy_price_history_active": False,
        "legacy_price_history_status": "retired_not_used_by_supported_output",
        "distance_evidence_contract": "explicit_route_api_or_geodesic_or_unavailable",
        "row_count": current_rows, "current_row_count": current_rows,
        "stale_row_count": stale_rows, "stale_output_available": stale_rows > 0,
        "observed_file_row_count": observed_rows,
        "fetched_record_scope": evidence.get("fetched_record_scope"),
        "source_fetch_completeness": evidence.get("source_fetch_completeness"),
        "pagination_complete": evidence.get("pagination_complete") is True,
        "page_request_count": int(evidence.get("page_request_count", 0)),
        "request_attempt_count": int(evidence.get("request_attempt_count", 0)),
        "successful_page_count": int(evidence.get("successful_page_count", 0)),
        "failed_page_count": int(evidence.get("failed_page_count", 0)),
        "fetched_record_count": int(evidence.get("fetched_records", 0)),
        "normalized_record_count": int(evidence.get("normalized_records", 0)),
        "accepted_record_count": int(evidence.get("accepted_records", 0)),
        "rejected_record_count": int(evidence.get("rejected_records", 0)),
        "parse_failure_count": int(evidence.get("parse_failures", 0)),
        "evidence_reconciliation_status": (
            "reconciled" if evidence.get("reconciled") is True else "not_reconciled"
        ),
        "evidence_reconciliation_equation": evidence.get(
            "reconciliation_equation",
            "fetched_records = accepted_records + rejected_records + parse_failures",
        ),
        "canonical_evidence_artifacts": evidence.get("artifacts", {}),
        "source_adapter_artifacts": evidence.get("source_adapter_artifacts", {}),
        "canonical_evidence_error": evidence_error,
        "identity_lifecycle_status": (
            "updated" if status_name == "success" and not identity_error else "not_updated"
        ),
        "identity_lifecycle_error": identity_error,
        "identity_lifecycle_artifacts": identity.get("artifacts", {}),
        "identity_observed_current_count": int(identity.get("observed_current_count", 0)),
        "identity_tracked_listing_count": int(identity.get("tracked_listing_count", 0)),
        "identity_new_listing_count": int(identity.get("new_listing_count", 0)),
        "identity_reappeared_listing_count": int(identity.get("reappeared_listing_count", 0)),
        "identity_missing_listing_count": int(identity.get("missing_listing_count", 0)),
        "identity_retired_listing_count": int(identity.get("retired_listing_count", 0)),
        "identity_transition_event_count": int(identity.get("transition_event_count", 0)),
        **{**validation, "row_count": current_rows}, **quality,
        "stdout_tail": stdout[-4000:], "stderr_tail": stderr[-4000:],
    }
    write_json(status_path, status)
    print(
        f"[{config['vehicle_key']}:autotrader] {status_name} | fetched={status['fetched_record_count']} "
        f"| accepted={status['accepted_record_count']} | rejected={status['rejected_record_count']} "
        f"| parse_failures={status['parse_failure_count']} "
        f"| lifecycle={status['identity_lifecycle_status']} "
        f"| new={status['identity_new_listing_count']} "
        f"| reappeared={status['identity_reappeared_listing_count']}"
    )
    return status


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Run the direct AutoTrader adapter with bounded status evidence"
    )
    result.add_argument("--config", required=True)
    result.add_argument(
        "--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS
    )
    result.add_argument("--fail-on-unhealthy", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    status = run_autotrader(
        root=Path.cwd(),
        config_path=Path(args.config),
        timeout_seconds=args.timeout_seconds,
    )
    return (
        1
        if args.fail_on_unhealthy
        and status["execution_status"] != "success"
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
