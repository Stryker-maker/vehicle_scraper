from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from phase1_common import (
    analyze_csv_quality,
    file_signature,
    validate_csv,
    validate_invocation_archive_output,
)


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
    file_signature_func: Callable[[Path], tuple[int, int] | None] = file_signature,
    validate_csv_func: Callable[[Path], dict[str, Any]] = validate_csv,
) -> tuple[bool, dict[str, Any], int, int, int, list[str]]:
    after_signature = file_signature_func(output_path)
    fresh = bool(
        after_signature
        and (
            before_signature is None
            or after_signature != before_signature
            or after_signature[0] >= started_ns
        )
    )
    validation = validate_csv_func(output_path)
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
    analyze_csv_quality_func: Callable[[Path, str], dict[str, Any]] = analyze_csv_quality,
) -> dict[str, Any]:
    if fresh and schema_valid:
        return analyze_csv_quality_func(output_path, source)
    status = "not_evaluated_stale_output" if stale_rows else "not_evaluated"
    return {
        "data_quality_status": status,
        "quality_warning_rows": 0,
        "quality_warning_count": 0,
        "quality_warning_summary": {},
    }
