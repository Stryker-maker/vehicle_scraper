from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence

from canonical_evidence import EVIDENCE_SCHEMA_VERSION, build_canonical_evidence
from phase1_common import (
    DEFAULT_TIMEOUT_SECONDS, UNBOUNDED_MAX_RESULTS, analyze_csv_quality,
    expected_output_path, file_signature, price_history_path, source_status_path,
    utc_date, utc_now, validate_csv, write_json,
)
from vehicle_config import CONFIG_SCHEMA_VERSION, legacy_runtime_config, load_vehicle_config


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
        with path.open("r", encoding="utf-8") as handle:
            history = json.load(handle)
    except (OSError, ValueError, json.JSONDecodeError):
        return 0
    if not isinstance(history, dict):
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
        with path.open("r", encoding="utf-8") as handle:
            history = json.load(handle)
    except (OSError, ValueError, json.JSONDecodeError):
        return 0
    if not isinstance(history, dict):
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


def _empty_evidence() -> dict[str, Any]:
    return {
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "fetched_records": 0,
        "normalized_records": 0,
        "accepted_records": 0,
        "rejected_records": 0,
        "parse_failures": 0,
        "reconciled": False,
        "fetched_record_scope": "not_evaluated",
        "source_fetch_completeness": "not_evaluated",
        "artifacts": {},
    }


def run_source(
    *, root: Path, source: str, config_path: Path, command: Sequence[str],
    run_id: str | None = None, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    root = root.resolve()
    config_path = config_path if config_path.is_absolute() else root / config_path
    original_config = config_path.read_bytes()
    config = load_vehicle_config(config_path)
    active_run = run_id or os.environ.get("GITHUB_RUN_ID", "local")
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

    runtime_config = legacy_runtime_config(
        config, source=source, max_results=UNBOUNDED_MAX_RESULTS
    )
    with tempfile.TemporaryDirectory(prefix=".phase1_runtime_", dir=root) as temp_dir:
        runtime_path = Path(temp_dir) / config_path.name
        write_json(runtime_path, runtime_config)
        isolated_command = replace_config_argument(
            command, root=root, original=config_path, runtime=runtime_path
        )
        environment = os.environ.copy()
        if source == "kijiji":
            environment["PHASE1_KIJIJI_DISTANCE_DISABLED"] = "1"
        try:
            completed = subprocess.run(
                isolated_command, cwd=root, text=True, capture_output=True,
                check=False, timeout=timeout_seconds, env=environment,
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
    completed_at = utc_now()
    if fresh and validation["schema_valid"]:
        try:
            evidence = build_canonical_evidence(
                root=root, config=config, source=source, csv_path=output_path,
                run_id=active_run, completed_at_utc=completed_at,
            )
        except Exception as exc:
            evidence_error = f"{type(exc).__name__}: {exc}"
            failures.append("canonical_evidence_failed")
        else:
            if evidence.get("reconciled") is not True:
                failures.append("evidence_reconciliation_failed")
            if int(evidence.get("accepted_records", 0)) < 1:
                failures.append("no_accepted_records")

    config_isolated = config_path.read_bytes() == original_config
    if not config_isolated:
        config_path.write_bytes(original_config)
        failures.append("approved_config_mutated")

    status_name = (
        "timed_out" if timed_out else "failed" if returncode != 0
        else "degraded" if failures else "success"
    )
    if status_name == "success":
        deduped_after = dedupe_history_observations_for_date(history_path, today)
    else:
        restore_history(history_path, snapshot)
        deduped_after = 0

    if fresh and validation["schema_valid"]:
        quality = analyze_csv_quality(output_path, source)
    elif stale_rows:
        quality = {
            "data_quality_status": "not_evaluated_stale_output",
            "quality_warning_rows": 0, "quality_warning_count": 0,
            "quality_warning_summary": {},
        }
    else:
        quality = {
            "data_quality_status": "not_evaluated", "quality_warning_rows": 0,
            "quality_warning_count": 0, "quality_warning_summary": {},
        }

    status = {
        "schema_version": 5,
        "configuration_schema_version": CONFIG_SCHEMA_VERSION,
        "canonical_evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "runtime_config_projection": "legacy_collector_v1",
        "approved_config_contains_legacy_controls": False,
        "run_id": active_run,
        "vehicle_key": config["vehicle_key"], "source": source,
        "config_path": str(config_path.relative_to(root)), "command": list(command),
        "started_at_utc": started_at, "completed_at_utc": completed_at,
        "execution_status": status_name, "collection_status": status_name,
        "exit_code": returncode, "timed_out": timed_out,
        "timeout_seconds": timeout_seconds, "failure_reasons": failures,
        "expected_output": str(output_path.relative_to(root)),
        "output_exists": output_path.exists(), "output_updated_this_run": fresh,
        "configured_max_results": None,
        "effective_max_results": "unbounded", "row_cap_disabled": True,
        "config_isolated": config_isolated,
        "distance_processing_disabled": source == "kijiji",
        "distance_filter_disabled": source == "kijiji",
        "legacy_source_ranking_disabled": source == "kijiji",
        "row_count": current_rows, "current_row_count": current_rows,
        "stale_row_count": stale_rows, "stale_output_available": stale_rows > 0,
        "observed_file_row_count": observed_rows,
        "same_day_history_removed_before_run": removed_before,
        "same_day_history_duplicates_removed_after_run": deduped_after,
        "fetched_record_scope": evidence.get("fetched_record_scope"),
        "source_fetch_completeness": evidence.get("source_fetch_completeness"),
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
        "canonical_evidence_error": evidence_error,
        **{**validation, "row_count": current_rows}, **quality,
        "stdout_tail": stdout[-4000:], "stderr_tail": stderr[-4000:],
    }
    write_json(status_path, status)
    print(
        f"[{config['vehicle_key']}:{source}] {status_name} | emitted={current_rows} "
        f"| accepted={status['accepted_record_count']} | rejected={status['rejected_record_count']} "
        f"| parse_failures={status['parse_failure_count']} | "
        f"reconciliation={status['evidence_reconciliation_status']}"
    )
    return status
