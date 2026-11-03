from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from identity_lifecycle import (
    IDENTITY_LIFECYCLE_SCHEMA_VERSION,
    update_source_identity_lifecycle,
)
from phase1_common import (
    analyze_csv_quality,
    file_signature,
    validate_csv,
    validate_invocation_archive_output,
)


def empty_source_evidence(
    adapter_schema_version: int,
    evidence_schema_version: int,
    additional_defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence = {
        "source_adapter_schema_version": adapter_schema_version,
        "evidence_schema_version": evidence_schema_version,
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
    evidence.update(additional_defaults or {})
    return evidence


def empty_source_identity() -> dict[str, Any]:
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


def build_source_evidence_and_identity(
    *,
    root: Path,
    config: dict[str, Any],
    source: str,
    active_run: str,
    completed_at: str,
    fresh: bool,
    validation: dict[str, Any],
    current_rows: int,
    failures: list[str],
    adapter_schema_version: int,
    evidence_schema_version: int,
    build_canonical_evidence: Callable[..., dict[str, Any]],
    additional_evidence_defaults: dict[str, Any] | None = None,
    update_identity: Callable[..., dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], str | None, dict[str, Any], str | None]:
    evidence = empty_source_evidence(
        adapter_schema_version,
        evidence_schema_version,
        additional_evidence_defaults,
    )
    evidence_error: str | None = None
    identity = empty_source_identity()
    identity_error: str | None = None
    if fresh and validation["schema_valid"]:
        try:
            evidence = build_canonical_evidence(
                root=root,
                config=config,
                run_id=active_run,
                completed_at_utc=completed_at,
            )
        except Exception as exc:  # noqa: BLE001 - preserve source-level failure isolation
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
                    identity = (update_identity or update_source_identity_lifecycle)(
                        root=root,
                        config=config,
                        source=source,
                        run_id=active_run,
                        observed_at_utc=completed_at,
                        accepted_artifact=str(evidence["artifacts"]["accepted"]),
                        adapter_records_artifact=str(
                            evidence.get("source_adapter_artifacts", {}).get("records")
                            or ""
                        )
                        or None,
                    )
                except Exception as exc:  # noqa: BLE001 - preserve identity rollback behavior
                    identity_error = f"{type(exc).__name__}: {exc}"
                    failures.append("identity_lifecycle_failed")
                else:
                    if int(identity.get("observed_current_count", -1)) != current_rows:
                        failures.append("identity_current_count_mismatch")
    return evidence, evidence_error, identity, identity_error


def validate_collection_scope(
    collection_scope: str, valid_scopes: Sequence[str]
) -> None:
    if collection_scope not in valid_scopes:
        raise ValueError(f"Unsupported collection scope: {collection_scope}")


def snapshot_archive_signatures(
    archive_dir: Path,
) -> dict[Path, tuple[int, int] | None]:
    signatures: dict[Path, tuple[int, int] | None] = {}
    if archive_dir.exists():
        for archive_file in archive_dir.glob("*.csv"):
            signatures[archive_file.resolve()] = file_signature(archive_file)
    return signatures


def restore_config_if_mutated(
    config_path: Path, original_config: bytes, failures: list[str]
) -> bool:
    if config_path.read_bytes() == original_config:
        return True
    config_path.write_bytes(original_config)
    failures.append("approved_config_mutated")
    return False


def snapshot_reconciliation_signature(
    reconciliation_path: Path,
) -> tuple[int, int] | None:
    try:
        stat = reconciliation_path.stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


def resolve_collector_command(
    command: Sequence[str] | None, default_command: Sequence[str]
) -> list[str]:
    return list(command or default_command)


def restore_identity_if_unhealthy(
    status_name: str,
    identity_before: Any,
    restore_artifacts: Callable[[Any], None],
) -> None:
    if status_name != "success":
        restore_artifacts(identity_before)


def execute_source_collector(
    command: Sequence[str],
    *,
    root: Path,
    timeout_seconds: float,
    subprocess_module: Any = subprocess,
) -> tuple[int | None, bool, str, str]:
    stdout = stderr = ""
    returncode: int | None = None
    timed_out = False
    try:
        completed = subprocess_module.run(
            command,
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
            env=os.environ.copy(),
        )
        returncode = completed.returncode
        stdout, stderr = completed.stdout or "", completed.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = (
            (exc.stdout or "").decode("utf-8", errors="replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        stderr = (
            (exc.stderr or "").decode("utf-8", errors="replace")
            if isinstance(exc.stderr, bytes)
            else (exc.stderr or "")
        )
    for output, stream in ((stdout, sys.stdout), (stderr, sys.stderr)):
        if output:
            tail = output[-4000:]
            print(tail, file=stream, end="" if tail.endswith("\n") else "\n")
    return returncode, timed_out, stdout, stderr


def assess_source_output(
    output_path: Path,
    *,
    before_signature: tuple[int, int] | None,
    started_ns: int,
    returncode: int | None,
    timed_out: bool,
    file_signature_func: Callable[[Path], tuple[int, int] | None] | None = None,
    validate_csv_func: Callable[[Path], dict[str, Any]] | None = None,
) -> tuple[bool, dict[str, Any], int, int, int, list[str]]:
    after_signature = (file_signature_func or file_signature)(output_path)
    fresh = bool(
        after_signature
        and (
            before_signature is None
            or after_signature != before_signature
            or after_signature[0] >= started_ns
        )
    )
    validation = (validate_csv_func or validate_csv)(output_path)
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
    return fresh, validation, observed_rows, current_rows, stale_rows, failures


def source_status_decision_fields(
    *,
    root: Path,
    config: dict[str, Any],
    source: str,
    active_run: str,
    started_ns: int,
    rec_before_sig: tuple[int, int] | None,
    archive_before_sigs: dict[Path, tuple[int, int] | None],
    fresh: bool,
    output_path: Path,
    status_name: str,
    identity_error: str | None,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "latest_output": str(output_path.relative_to(root)) if fresh else None,
        "archive_output": (
            validate_invocation_archive_output(
                root,
                config,
                source,
                active_run,
                started_ns,
                rec_before_sig,
                archive_before_sigs,
            )
            if fresh
            else None
        ),
        "evidence_reconciliation_status": (
            "reconciled" if evidence.get("reconciled") is True else "not_reconciled"
        ),
        "identity_lifecycle_status": (
            "updated"
            if status_name == "success" and not identity_error
            else "not_updated"
        ),
    }








def source_schema_version_fields(
    *,
    config_schema_version: int,
    evidence_schema_version: int,
    adapter_schema_version: int,
    identity_schema_version: int,
) -> dict[str, Any]:
    return {
        "configuration_schema_version": config_schema_version,
        "canonical_evidence_schema_version": evidence_schema_version,
        "source_adapter_schema_version": adapter_schema_version,
        "identity_lifecycle_schema_version": identity_schema_version,
    }


def source_status_metrics(
    *,
    current_rows: int,
    stale_rows: int,
    fetched_record_count: int,
    accepted_record_count: int,
    rejected_record_count: int,
    parse_failure_count: int,
    identity_tracked_listing_count: int,
    identity_new_listing_count: int,
    identity_reappeared_listing_count: int,
    identity_missing_listing_count: int,
    identity_retired_listing_count: int,
    failure_reasons: list[str],
) -> dict[str, Any]:
    return {
        "row_count": current_rows,
        "current_row_count": current_rows,
        "stale_row_count": stale_rows,
        "fetched_record_count": fetched_record_count,
        "accepted_record_count": accepted_record_count,
        "rejected_record_count": rejected_record_count,
        "parse_failure_count": parse_failure_count,
        "identity_tracked_listing_count": identity_tracked_listing_count,
        "identity_new_listing_count": identity_new_listing_count,
        "identity_reappeared_listing_count": identity_reappeared_listing_count,
        "identity_missing_listing_count": identity_missing_listing_count,
        "identity_retired_listing_count": identity_retired_listing_count,
        "failure_reasons": failure_reasons,
    }


def source_status_metrics_from_context(
    context: Mapping[str, Any],
) -> dict[str, Any]:
    evidence = context["evidence"]
    identity = context["identity"]
    return source_status_metrics(
        current_rows=context["current_rows"],
        stale_rows=context["stale_rows"],
        fetched_record_count=int(evidence.get("fetched_records", 0)),
        accepted_record_count=int(evidence.get("accepted_records", 0)),
        rejected_record_count=int(evidence.get("rejected_records", 0)),
        parse_failure_count=int(evidence.get("parse_failures", 0)),
        identity_tracked_listing_count=int(identity.get("tracked_listing_count", 0)),
        identity_new_listing_count=int(identity.get("new_listing_count", 0)),
        identity_reappeared_listing_count=int(
            identity.get("reappeared_listing_count", 0)
        ),
        identity_missing_listing_count=int(identity.get("missing_listing_count", 0)),
        identity_retired_listing_count=int(identity.get("retired_listing_count", 0)),
        failure_reasons=context["failures"],
    )


def source_evidence_status_fields(
    context: Mapping[str, Any],
) -> dict[str, Any]:
    evidence = context["evidence"]
    identity = context["identity"]
    return {
        "stale_output_available": context["stale_rows"] > 0,
        "observed_file_row_count": context["observed_rows"],
        "fetched_record_scope": evidence.get("fetched_record_scope"),
        "source_fetch_completeness": evidence.get("source_fetch_completeness"),
        "pagination_complete": evidence.get("pagination_complete") is True,
        "page_request_count": int(evidence.get("page_request_count", 0)),
        "request_attempt_count": int(evidence.get("request_attempt_count", 0)),
        "successful_page_count": int(evidence.get("successful_page_count", 0)),
        "failed_page_count": int(evidence.get("failed_page_count", 0)),
        "normalized_record_count": int(evidence.get("normalized_records", 0)),
        "evidence_reconciliation_equation": evidence.get(
            "reconciliation_equation",
            "fetched_records = accepted_records + rejected_records + parse_failures",
        ),
        "source_adapter_artifacts": evidence.get("source_adapter_artifacts", {}),
        "canonical_evidence_error": context["evidence_error"],
        "identity_lifecycle_error": context["identity_error"],
        "identity_lifecycle_artifacts": identity.get("artifacts", {}),
        "identity_observed_current_count": int(
            identity.get("observed_current_count", 0)
        ),
        "identity_transition_event_count": int(
            identity.get("transition_event_count", 0)
        ),
    }


def source_execution_outcome_fields(
    context: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "command": context["command"],
        "collection_scope": context["collection_scope"],
        "started_at_utc": context["started_at"],
        "exit_code": context["returncode"],
        "timed_out": context["timed_out"],
        "timeout_seconds": context["timeout_seconds"],
        "expected_output": str(
            context["output_path"].relative_to(context["root"])
        ),
        "output_exists": context["output_path"].exists(),
        "output_updated_this_run": context["fresh"],
        "stdout_tail": context["stdout"][-4000:],
        "stderr_tail": context["stderr"][-4000:],
    }


def source_runtime_contract_fields(
    context: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "runtime_config_projection": "direct_schema_v2",
        "approved_config_contains_legacy_controls": False,
        "configured_max_results": None,
        "effective_max_results": "unbounded",
        "row_cap_disabled": True,
        "config_isolated": context["config_isolated"],
        "legacy_source_ranking_disabled": True,
        "legacy_price_history_active": False,
        "legacy_price_history_status": "retired_not_used_by_supported_output",
    }


def finalize_source_status_from_context(
    status: dict[str, Any],
    context: Mapping[str, Any],
    *,
    source: str,
) -> None:
    status.update(
        source_status_decision_fields(
            root=context["root"],
            config=context["config"],
            source=source,
            active_run=context["active_run"],
            started_ns=context["started_ns"],
            rec_before_sig=context["rec_before_sig"],
            archive_before_sigs=context["archive_before_sigs"],
            fresh=context["fresh"],
            output_path=context["output_path"],
            status_name=context["status_name"],
            identity_error=context["identity_error"],
            evidence=context["evidence"],
        )
    )


def print_source_summary(
    vehicle_key: str,
    source: str,
    status_name: str,
    status: dict[str, Any],
) -> None:
    print(
        f"[{vehicle_key}:{source}] {status_name} "
        f"| fetched={status['fetched_record_count']} "
        f"| accepted={status['accepted_record_count']} "
        f"| rejected={status['rejected_record_count']} "
        f"| parse_failures={status['parse_failure_count']} "
        f"| lifecycle={status['identity_lifecycle_status']} "
        f"| new={status['identity_new_listing_count']} "
        f"| reappeared={status['identity_reappeared_listing_count']}"
    )


def collector_status_name(
    timed_out: bool, returncode: int | None, failures: list[str]
) -> str:
    if timed_out:
        return "timed_out"
    if returncode not in (0, None):
        return "failed"
    return "degraded" if failures else "success"


def collector_quality_report(
    output_path: Path,
    source: str,
    fresh: bool,
    schema_valid: bool,
    stale_rows: int,
    analyze_csv_quality_func: Callable[[Path, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if fresh and schema_valid:
        return (analyze_csv_quality_func or analyze_csv_quality)(output_path, source)
    status = "not_evaluated_stale_output" if stale_rows else "not_evaluated"
    return {
        "data_quality_status": status,
        "quality_warning_rows": 0,
        "quality_warning_count": 0,
        "quality_warning_summary": {},
    }
