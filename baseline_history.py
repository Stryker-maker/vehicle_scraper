from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from workflow_anomalies import _candidate_is_eligible

BASELINE_SELECTION_SCHEMA_VERSION = 1


def _validated_path(path: Path, *, label: str) -> Path:
    """Resolve a CLI path while rejecting traversal components and NUL bytes."""
    if "\x00" in str(path):
        raise ValueError(f"{label} path contains a NUL byte")
    if ".." in path.parts:
        raise ValueError(f"{label} path must not contain parent traversal")
    return path.resolve(strict=False)


def _validated_git_path(path: str) -> str:
    """Validate the repository-relative path supplied to Git history commands."""
    candidate = Path(path)
    if not path or "\x00" in path or candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("historical report path must be a safe repository-relative path")
    return path


def _git_executable() -> str:
    """Return the resolved Git executable required for historical discovery."""
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("git executable is required for historical baseline discovery")
    return executable


def _git_history_paths(root: Path, path: str, limit: int) -> list[str]:
    """Return revisions containing the historical report, newest first."""
    if limit <= 0:
        raise ValueError("history_limit must be greater than zero")
    path = _validated_git_path(path)
    result = subprocess.run(
        [_git_executable(), "log", f"-{limit}", "--format=%H", "--", path],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _read_git_json(root: Path, revision: str, path: str) -> dict[str, Any] | None:
    """Read and parse one historical JSON report, returning None when unavailable."""
    path = _validated_git_path(path)
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
    """Return whether a historical health report is eligible for comparison."""
    return report.get("overall_status") in {"success", "success_with_warnings"}


def _candidate_is_complete(candidate: dict[str, Any], current: dict[str, Any]) -> bool:
    """Return whether a historical report covers every current source with a fingerprint."""
    current_sources = [entry for entry in current.get("sources", []) if isinstance(entry, dict)]
    candidate_sources = {
        (str(entry.get("vehicle_key") or ""), str(entry.get("source") or "")): entry
        for entry in candidate.get("sources", [])
        if isinstance(entry, dict)
    }
    if not current_sources:
        return False
    for current_entry in current_sources:
        key = (str(current_entry.get("vehicle_key") or ""), str(current_entry.get("source") or ""))
        candidate_entry = candidate_sources.get(key)
        if not candidate_entry:
            return False
        if not isinstance(candidate_entry.get("compatibility_fingerprint"), str):
            return False
        if not candidate_entry["compatibility_fingerprint"].strip():
            return False
    return True


def _discover_selection(*, root: Path, current: dict[str, Any], path: str, history_limit: int) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Discover a baseline and retain enough rejection state for fail-closed reporting."""
    current_run_id = current.get("run_id")
    try:
        revisions = _git_history_paths(root, path, history_limit)
    except (OSError, subprocess.CalledProcessError, RuntimeError, ValueError):
        return None, {"schema_version": BASELINE_SELECTION_SCHEMA_VERSION, "status": "unavailable", "reason": "git_history_unavailable", "historical_candidate_count": 0}

    seen = 0
    reasons: dict[str, int] = {}
    for revision in revisions:
        candidate = _read_git_json(root, revision, path)
        if not candidate:
            reasons["missing_or_malformed"] = reasons.get("missing_or_malformed", 0) + 1
            continue
        seen += 1
        if candidate.get("run_id") == current_run_id:
            reasons["same_run"] = reasons.get("same_run", 0) + 1
            continue
        if not _is_successful_report(candidate):
            reasons["unsuccessful"] = reasons.get("unsuccessful", 0) + 1
            continue
        if not _candidate_is_complete(candidate, current):
            reasons["incomplete"] = reasons.get("incomplete", 0) + 1
            continue
        if _candidate_is_eligible(candidate=candidate, current=current):
            return candidate, {
                "schema_version": BASELINE_SELECTION_SCHEMA_VERSION,
                "status": "selected",
                "historical_candidate_count": seen,
                "rejection_reasons": reasons,
            }
        reasons["incompatible"] = reasons.get("incompatible", 0) + 1

    return None, {
        "schema_version": BASELINE_SELECTION_SCHEMA_VERSION,
        "status": "incompatible" if seen else "unavailable",
        "reason": "no_compatible_historical_baseline" if seen else "no_historical_reports",
        "historical_candidate_count": seen,
        "rejection_reasons": reasons,
    }


def discover_compatible_baseline(*, root: Path, current: dict[str, Any], path: str = "data/run_status/latest.json", history_limit: int = 50) -> dict[str, Any] | None:
    """Return the newest successful historical report compatible with current."""
    selected, _ = _discover_selection(root=root, current=current, path=path, history_limit=history_limit)
    return selected


def write_selected_baseline(*, root: Path, current_path: Path, output_path: Path, history_limit: int = 50) -> dict[str, Any]:
    """Select and write a baseline artifact that preserves selection outcome metadata."""
    current_path = _validated_path(current_path, label="current")
    output_path = _validated_path(output_path, label="output")
    current = json.loads(current_path.read_text(encoding="utf-8"))
    if not isinstance(current, dict):
        raise ValueError("Current health report must be a JSON object")
    selected, metadata = _discover_selection(
        root=root, current=current, path="data/run_status/latest.json", history_limit=history_limit
    )
    if selected is not None:
        artifact = dict(selected)
        artifact["_baseline_selection"] = metadata
    else:
        artifact = {"_baseline_selection": metadata, "sources": []}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def parser() -> argparse.ArgumentParser:
    """Build the command-line parser for historical baseline discovery."""
    result = argparse.ArgumentParser(description="Select a compatible historical health baseline")
    result.add_argument("--current", required=True)
    result.add_argument("--output", required=True)
    result.add_argument("--history-limit", type=int, default=50)
    return result


def main(argv: list[str] | None = None) -> int:
    """Run historical baseline selection from command-line arguments."""
    args = parser().parse_args(argv)
    root = Path.cwd()
    selected = write_selected_baseline(root=root, current_path=Path(args.current), output_path=Path(args.output), history_limit=args.history_limit)
    print(json.dumps({"selected_run_id": selected.get("run_id"), "selection_status": selected.get("_baseline_selection", {}).get("status")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
