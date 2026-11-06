from __future__ import annotations

from pathlib import Path
from typing import Any

from phase1_common import analyze_csv_quality, file_signature, validate_csv


def empty_identity(schema_version: int) -> dict[str, Any]:
    return {
        "identity_lifecycle_schema_version": schema_version,
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


def assess_source_output(
    output_path: Path,
    *,
    before_signature: tuple[int, int] | None,
    started_ns: int,
    returncode: int | None,
    timed_out: bool,
) -> tuple[bool, dict[str, Any], int, int, int, list[str]]:
    after_signature = file_signature(output_path)
    fresh = bool(
        after_signature
        and (
            before_signature is None
            or after_signature != before_signature
            or after_signature[0] >= started_ns
        )
    )
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
    return fresh, validation, observed_rows, current_rows, stale_rows, failures


def collector_status_name(
    timed_out: bool, returncode: int | None, failures: list[str]
) -> str:
    if timed_out:
        return "timed_out"
    if returncode not in (0, None):
        return "failed"
    return "degraded" if failures else "success"


def restore_config_if_mutated(
    config_path: Path, original_config: bytes, failures: list[str]
) -> bool:
    config_isolated = config_path.read_bytes() == original_config
    if not config_isolated:
        config_path.write_bytes(original_config)
        failures.append("approved_config_mutated")
    return config_isolated


def collector_quality_report(
    output_path: Path,
    source: str,
    fresh: bool,
    schema_valid: bool,
    stale_rows: int,
) -> dict[str, Any]:
    if fresh and schema_valid:
        return analyze_csv_quality(output_path, source)
    status = "not_evaluated_stale_output" if stale_rows else "not_evaluated"
    return {
        "data_quality_status": status,
        "quality_warning_rows": 0,
        "quality_warning_count": 0,
        "quality_warning_summary": {},
    }
