from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Sequence

from phase1_common import analyze_csv_quality, file_signature, validate_csv


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


def restore_config_if_mutated(config_path: Path, original_config: bytes) -> bool:
    if config_path.read_bytes() == original_config:
        return True
    config_path.write_bytes(original_config)
    return False


def restore_identity_if_unhealthy(
    status_name: str,
    identity_before: Any,
    restore_artifacts: Callable[[Any], None],
) -> None:
    if status_name != "success":
        restore_artifacts(identity_before)


def execute_source_collector(
    command: Sequence[str], *, root: Path, timeout_seconds: float
) -> tuple[int | None, bool, str, str]:
    stdout = stderr = ""
    returncode: int | None = None
    timed_out = False
    try:
        completed = subprocess.run(
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
