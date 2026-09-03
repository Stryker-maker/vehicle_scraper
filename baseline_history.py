from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from workflow_anomalies import _select_compatible_baseline


def _git_executable() -> str:
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("git executable is required for historical baseline discovery")
    return executable


def _git_history_paths(root: Path, path: str, limit: int) -> list[str]:
    if limit <= 0:
        raise ValueError("history_limit must be greater than zero")
    result = subprocess.run(
        [_git_executable(), "log", f"-{limit}", "--format=%H", "--", path],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _read_git_json(root: Path, revision: str, path: str) -> dict[str, Any] | None:
    result = subprocess.run(
        [_git_executable(), "show", f"{revision}:{path}"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _is_successful_report(report: dict[str, Any]) -> bool:
    return report.get("overall_status") in {"success", "success_with_warnings"}


def _candidate_is_complete(candidate: dict[str, Any], current: dict[str, Any]) -> bool:
    current_sources = [
        entry for entry in current.get("sources", []) if isinstance(entry, dict)
    ]
    candidate_sources = {
        (str(entry.get("vehicle_key") or ""), str(entry.get("source") or "")): entry
        for entry in candidate.get("sources", [])
        if isinstance(entry, dict)
    }
    if not current_sources:
        return False
    for current_entry in current_sources:
        key = (
            str(current_entry.get("vehicle_key") or ""),
            str(current_entry.get("source") or ""),
        )
        candidate_entry = candidate_sources.get(key)
        if not candidate_entry:
            return False
        if not isinstance(candidate_entry.get("compatibility_fingerprint"), str):
            return False
        if not candidate_entry["compatibility_fingerprint"].strip():
            return False
    return True


def discover_compatible_baseline(
    *,
    root: Path,
    current: dict[str, Any],
    path: str = "data/run_status/latest.json",
    history_limit: int = 50,
) -> dict[str, Any] | None:
    """Return the newest successful historical report compatible with current."""
    current_run_id = current.get("run_id")
    try:
        revisions = _git_history_paths(root, path, history_limit)
    except (OSError, subprocess.CalledProcessError, RuntimeError, ValueError):
        return None

    for revision in revisions:
        candidate = _read_git_json(root, revision, path)
        if not candidate:
            continue
        if candidate.get("run_id") == current_run_id:
            continue
        if not _is_successful_report(candidate):
            continue
        if not _candidate_is_complete(candidate, current):
            continue
        selected = _select_compatible_baseline(
            baseline_candidates=[candidate], current=current
        )
        if selected is not None:
            return selected
    return None


def write_selected_baseline(
    *, root: Path, current_path: Path, output_path: Path, history_limit: int = 50
) -> dict[str, Any]:
    """Select and write a compatible historical baseline, or an empty object."""
    current = json.loads(current_path.read_text(encoding="utf-8"))
    if not isinstance(current, dict):
        raise ValueError("Current health report must be a JSON object")
    selected = discover_compatible_baseline(
        root=root, current=current, history_limit=history_limit
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(selected or {}, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return selected or {}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Select a compatible historical health baseline")
    result.add_argument("--current", required=True)
    result.add_argument("--output", required=True)
    result.add_argument("--history-limit", type=int, default=50)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = Path.cwd()
    selected = write_selected_baseline(
        root=root,
        current_path=Path(args.current),
        output_path=Path(args.output),
        history_limit=args.history_limit,
    )
    print(json.dumps({"selected_run_id": selected.get("run_id")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
