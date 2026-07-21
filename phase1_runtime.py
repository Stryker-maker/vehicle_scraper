from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Sequence

from phase1_common import (
    DEFAULT_TIMEOUT_SECONDS, UNBOUNDED_MAX_RESULTS, analyze_csv_quality,
    expected_output_path, file_signature, load_json, price_history_path,
    source_status_path, utc_date, utc_now, validate_csv, write_json,
)


def history_snapshot(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def restore_history(path: Path, snapshot: bytes | None) -> None:
    if snapshot is None:
        path.unlink(missing_ok=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(snapshot)


def remove_history_observations_for_date(path: Path, date_value: str) -> int:
    if not path.exists():
        return 0
    try:
        history = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return 0
    removed = 0
    for listing_id, records in list(history.items()):
        if not isinstance(records, list):
            continue
        retained = [
            record for record in records
            if not (isinstance(record, dict) and record.get("date") == date_value)
        ]
        removed += len(records) - len(retained)
        history[listing_id] = retained
    if removed:
        write_json(path, history)
    return removed


def dedupe_history_observations_for_date(path: Path, date_value: str) -> int:
    if not path.exists():
        return 0
    try:
        history = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return 0
    removed = 0
    for listing_id, records in list(history.items()):
        if not isinstance(records, list):
            continue
        final_today: dict[str, Any] | None = None
        retained: list[Any] = []
        for record in records:
            if isinstance(record, dict) and record.get("date") == date_value:
                if final_today is not None:
                    removed += 1
                final_today = record
            else:
                retained.append(record)
        if final_today is not None:
            retained.append(final_today)
        history[listing_id] = retained
    if removed:
        write_json(path, history)
    return removed


def process_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


def replace_config_argument(
    command: Sequence[str], *, root: Path, original: Path, runtime: Path
) -> list[str]:
    candidates = {str(original), original.name}
    try:
        candidates.add(str(original.relative_to(root)))
    except ValueError:
        pass
    runtime_arg = str(runtime.relative_to(root))
    return [runtime_arg if arg in candidates else arg for arg in command]


def run_source(
    *, root: Path, source: str, config_path: Path, command: Sequence[str],
    run_id: str | None = None, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    root = root.resolve()
    config_path = config_path if config_path.is_absolute() else root / config_path
    original_config = config_path.read_bytes()
    config = load_json(config_path)
    output_path = expected_output_path(root, config, source)
    status_path = source_status_path(root, config, source)
    history_path = price_history_path(root, config, source)
    snapshot = history_snapshot(history_path)
    today = utc_date()
    removed_before = remove_history_observations_for_date(history_path, today)
    before_signature = file_signature(output_path)
    started_at = utc_now()
    started_ns = time.time_ns()
    stdout = stderr = ""
    returncode: int | None = None
    timed_out = False

    runtime_config = deepcopy(config)
    runtime_config["max_results"] = UNBOUNDED_MAX_RESULTS
    with tempfile.TemporaryDirectory(prefix=".phase1_runtime_", dir=root) as temp_dir:
        runtime_path = Path(temp_dir) / config_path.name
        write_json(runtime_path, runtime_config)
        isolated_command = replace_config_argument(
            command, root=root, original=config_path, runtime=runtime_path
        )
        try:
            completed = subprocess.run(
                isolated_command, cwd=root, text=True, capture_output=True,
                check=False, timeout=timeout_seconds,
            )
            returncode = completed.returncode
            stdout, stderr = completed.stdout or "", completed.stderr or ""
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout, stderr = process_text(exc.stdout), process_text(exc.stderr)

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
    failures: list[str] = []
    if timed_out:
        failures.append("collector_timed_out")
    elif returncode != 0:
        failures.append("collector_command_failed")
    if not fresh:
        failures.append("no_fresh_output")
    if not validation["schema_valid"]:
        failures.append("invalid_output_schema")
    if validation["row_count"] < 1:
        failures.append("empty_output")
    status_name = (
        "timed_out" if timed_out else "failed" if returncode != 0
        else "degraded" if failures else "success"
    )

    if status_name == "success":
        deduped_after = dedupe_history_observations_for_date(history_path, today)
    else:
        restore_history(history_path, snapshot)
        deduped_after = 0

    quality = analyze_csv_quality(output_path, source) if validation["schema_valid"] else {
        "data_quality_status": "not_evaluated", "quality_warning_rows": 0,
        "quality_warning_count": 0, "quality_warning_summary": {},
    }
    config_isolated = config_path.read_bytes() == original_config
    if not config_isolated:
        config_path.write_bytes(original_config)
        failures.append("approved_config_mutated")
        if status_name == "success":
            status_name = "degraded"

    status = {
        "schema_version": 2, "run_id": run_id or os.environ.get("GITHUB_RUN_ID", "local"),
        "vehicle_key": config["vehicle_key"], "source": source,
        "config_path": str(config_path.relative_to(root)), "command": list(command),
        "started_at_utc": started_at, "completed_at_utc": utc_now(),
        "execution_status": status_name, "collection_status": status_name,
        "exit_code": returncode, "timed_out": timed_out,
        "timeout_seconds": timeout_seconds, "failure_reasons": failures,
        "expected_output": str(output_path.relative_to(root)),
        "output_exists": output_path.exists(), "output_updated_this_run": fresh,
        "configured_max_results": config.get("max_results"),
        "effective_max_results": "unbounded", "row_cap_disabled": True,
        "config_isolated": config_isolated,
        "same_day_history_removed_before_run": removed_before,
        "same_day_history_duplicates_removed_after_run": deduped_after,
        **validation, **quality, "stdout_tail": stdout[-4000:], "stderr_tail": stderr[-4000:],
    }
    write_json(status_path, status)
    print(
        f"[{config['vehicle_key']}:{source}] {status_name} | rows={validation['row_count']} "
        f"| fresh={fresh} | quality={quality['data_quality_status']}"
    )
    return status
