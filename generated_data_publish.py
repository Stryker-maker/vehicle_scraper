from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from phase1_common import utc_now, write_json
from storage_retention import validate_generated_data_paths
from vehicle_registry import DEFAULT_REGISTRY_PATH, registry_entries

PUBLICATION_SCHEMA_VERSION = 1
MANIFEST_PATH = Path("data/run_status/publication_latest.json")


def _git_executable() -> str:
    """Return Git's resolved executable path or fail clearly when Git is unavailable."""
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("git executable is required for staged publication validation")
    return str(Path(executable).resolve())


def staged_name_status(root: Path) -> list[tuple[str, str]]:
    git = _git_executable()
    completed = subprocess.run(
        [git, "diff", "--cached", "--name-status", "--diff-filter=ACDMRTUXB"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git_diff_cached_failed")
    result: list[tuple[str, str]] = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        paths = parts[1:]
        if status.startswith("R") or status.startswith("C"):
            if len(paths) != 2:
                raise ValueError(f"Invalid staged rename/copy row: {line}")
            result.append((status, paths[1]))
        elif len(paths) == 1:
            result.append((status, paths[0]))
        else:
            raise ValueError(f"Invalid staged diff row: {line}")
    return result


def _csv_physical_line_errors(
    path: str, line_number: int, physical: list[str], *, check_line_ending: bool = True
) -> list[str]:
    """Return formatting errors detected on one physical CSV line."""
    errors: list[str] = []
    line = "".join(physical)
    is_conflict_marker = line.startswith(("<<<<<<< ", "||||||| ", ">>>>>>> ")) or line == "======="
    if is_conflict_marker:
        errors.append(f"{path}:{line_number}: unresolved merge conflict marker")
    if physical and physical[-1] in {" ", "\t"}:
        errors.append(f"{path}:{line_number}: trailing whitespace")
    if check_line_ending and physical and physical[-1] == "\r":
        errors.append(f"{path}:{line_number}: CRLF line terminator")
    return errors


def _csv_consume_quote(
    text: str,
    index: int,
    physical: list[str],
    in_quotes: bool,
    quoted_field_start_line: int | None,
    line_start: int,
) -> tuple[int, bool, int | None, bool]:
    """Consume a quote or escaped quote and return the updated parser state."""
    if in_quotes and index + 1 < len(text) and text[index + 1] == '"':
        physical.extend(('"', '"'))
        return index + 2, in_quotes, quoted_field_start_line, True
    if in_quotes:
        return index, False, None, False
    return index, True, line_start, False


def _csv_handle_carriage_return(
    path: str,
    text: str,
    index: int,
    line_start: int,
    physical: list[str],
    errors: list[str],
    in_quotes: bool,
) -> None:
    """Record a carriage return as quoted content, CRLF, or a bare CR error."""
    is_crlf = index + 1 < len(text) and text[index + 1] == "\n"
    if in_quotes or is_crlf:
        physical.append("\r")
    else:
        errors.append(f"{path}:{line_start}: bare CR outside quoted field")
        physical.append("\r")


def _csv_handle_line_feed(
    path: str, line_start: int, physical: list[str], errors: list[str], in_quotes: bool
) -> tuple[int, list[str]]:
    """Validate a record-ending line feed or retain it inside a quoted field."""
    if not in_quotes:
        errors.extend(_csv_physical_line_errors(path, line_start, physical))
        physical = []
    else:
        physical.append("\n")
    return line_start + 1, physical


def _csv_final_text_errors(
    path: str,
    line_start: int,
    physical: list[str],
    in_quotes: bool,
    quoted_field_start_line: int | None,
) -> list[str]:
    """Validate remaining text and report an unterminated quoted field."""
    errors: list[str] = []
    if not in_quotes and physical:
        errors.extend(_csv_physical_line_errors(path, line_start, physical, check_line_ending=False))
    if in_quotes:
        errors.append(f"{path}:{quoted_field_start_line}: unterminated quoted field")
    return errors


def _csv_scan_character(
    path: str,
    text: str,
    index: int,
    line_start: int,
    physical: list[str],
    errors: list[str],
    in_quotes: bool,
    quoted_field_start_line: int | None,
    at_field_start: bool,
) -> tuple[int, int, list[str], bool, int | None, bool]:
    """Process one CSV character while tracking valid quoted-field boundaries."""
    char = text[index]
    if char == '"' and (in_quotes or at_field_start):
        was_in_quotes = in_quotes
        index, in_quotes, quoted_field_start_line, escaped_quote = _csv_consume_quote(
            text, index, physical, in_quotes, quoted_field_start_line, line_start
        )
        if escaped_quote:
            return (
                index,
                line_start,
                physical,
                in_quotes,
                quoted_field_start_line,
                False,
            )
        physical.append(char)
        if not was_in_quotes:
            at_field_start = False
    elif char == '"':
        # A quote inside an unquoted field is ordinary data, not a quote-state change.
        physical.append(char)
        at_field_start = False
    elif char == "\r":
        _csv_handle_carriage_return(
            path, text, index, line_start, physical, errors, in_quotes
        )
        if not in_quotes:
            at_field_start = False
    elif char == "\n":
        line_start, physical = _csv_handle_line_feed(
            path, line_start, physical, errors, in_quotes
        )
        if not in_quotes:
            at_field_start = True
    elif char == "," and not in_quotes:
        physical.append(char)
        at_field_start = True
    else:
        physical.append(char)
        if not in_quotes:
            at_field_start = False
    return (
        index + 1,
        line_start,
        physical,
        in_quotes,
        quoted_field_start_line,
        at_field_start,
    )


def _staged_csv_text_errors(path: str, text: str) -> list[str]:
    """Return staged CSV formatting errors with physical line numbers."""
    return _scan_csv_text_errors(path, text)


def _scan_csv_text_errors(path: str, text: str) -> list[str]:
    """Scan CSV text while delegating each character to the focused state handlers."""
    errors: list[str] = []
    in_quotes = False
    line_start = 1
    quoted_field_start_line: int | None = None
    at_field_start = True
    physical: list[str] = []
    index = 0
    while index < len(text):
        (
            index,
            line_start,
            physical,
            in_quotes,
            quoted_field_start_line,
            at_field_start,
        ) = _csv_scan_character(
            path,
            text,
            index,
            line_start,
            physical,
            errors,
            in_quotes,
            quoted_field_start_line,
            at_field_start,
        )
    errors.extend(
        _csv_final_text_errors(path, line_start, physical, in_quotes, quoted_field_start_line)
    )
    return errors


def verify_staged_csv_whitespace(root: Path) -> None:
    """Validate staged CSV whitespace without rejecting embedded newlines in quoted fields."""
    git = _git_executable()
    completed = subprocess.run(
        [git, "diff", "--cached", "--name-only", "--diff-filter=ACMRTUXB", "--",
         ":(glob)**/*.csv"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git_diff_cached_csv_list_failed")
    errors: list[str] = []
    for path in filter(None, completed.stdout.splitlines()):
        blob = subprocess.run([git, "show", f":{path}"], cwd=root, capture_output=True, check=False)
        if blob.returncode != 0:
            raise RuntimeError(blob.stderr.decode("utf-8", errors="replace").strip() or f"git_show_failed:{path}")
        errors.extend(_staged_csv_text_errors(path, blob.stdout.decode("utf-8")))
    if errors:
        raise ValueError("Invalid staged CSV whitespace: " + "; ".join(errors))


def governed_keys(root: Path, registry_path: Path) -> tuple[list[str], list[str]]:
    entries = registry_entries(root=root, registry_path=registry_path)
    active = [str(entry["vehicle_key"]) for entry in entries if entry["enabled"]]
    paused = [str(entry["vehicle_key"]) for entry in entries if not entry["enabled"]]
    return active, paused


def _parse_isolated_items(
    isolated: Any, *, field: str = "isolated_collections"
) -> list[dict[str, str]]:
    """Validate and parse one collection-classification list, checking for duplicates."""
    if not isinstance(isolated, list):
        raise ValueError(f"{field} must be a list")

    pattern = __import__("re").compile(r"^[a-z0-9_]+$")
    parsed: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in isolated:
        if not isinstance(item, dict):
            raise ValueError(f"Invalid entry in {field}: {item!r}")
        vk = str(item.get("vehicle_key") or "").strip()
        src = str(item.get("source") or "").strip()
        if not vk or not src or not pattern.match(vk) or not pattern.match(src):
            raise ValueError(f"Invalid collection identifier in {field}: {item!r}")
        pair = (vk, src)
        if pair in seen:
            raise ValueError(f"Duplicate collection identity in {field}: {vk}:{src}")
        seen.add(pair)
        parsed.append({"vehicle_key": vk, "source": src})

    return parsed


def _load_same_run_anomaly_report(root: Path, run_id: str) -> dict[str, Any] | None:
    """Load and validate the anomaly report once for a publication operation."""
    anomaly_path = root / "data" / "run_status" / "anomalies_latest.json"
    if not anomaly_path.exists():
        return None
    try:
        anom_data = json.loads(anomaly_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Unreadable or malformed anomaly report: {exc}") from exc
    if not isinstance(anom_data, dict) or anom_data.get("anomaly_schema_version") != 1:
        raise ValueError("Invalid anomaly report schema in anomalies_latest.json")
    report_run_id = str(anom_data.get("run_id") or "").strip()
    if report_run_id != run_id:
        raise ValueError(
            f"Anomaly report run_id mismatch: expected {run_id!r}, found {report_run_id!r}"
        )
    return anom_data


def _extract_anomaly_collection_field(
    root: Path, run_id: str, field: str, *, default: list[dict[str, str]] | None = None
) -> list[dict[str, str]]:
    """Extract and validate one collection classification from the same-run anomaly report."""
    anom_data = _load_same_run_anomaly_report(root, run_id)
    if anom_data is None:
        return []
    if field in anom_data:
        value = anom_data[field]
    elif default is not None:
        value = default
    else:
        value = []
    return _parse_isolated_items(value, field=field)


def _extract_isolated_collections(root: Path, run_id: str) -> list[dict[str, str]]:
    """Extract and validate actually isolated collection identifiers from the anomaly report."""
    return _extract_anomaly_collection_field(root, run_id, "isolated_collections")


def _extract_no_output_collections(root: Path, run_id: str) -> list[dict[str, str]]:
    """Extract and validate collections that had no current-run outputs to quarantine."""
    return _extract_anomaly_collection_field(root, run_id, "no_output_collections")


def _extract_requested_isolation_collections(root: Path, run_id: str) -> list[dict[str, str]]:
    """Extract the complete requested set, falling back only for older reports."""
    anomaly_data = _load_same_run_anomaly_report(root, run_id)
    if anomaly_data is None:
        return []
    if "isolation_requested_collections" in anomaly_data:
        return _parse_isolated_items(
            anomaly_data["isolation_requested_collections"],
            field="isolation_requested_collections",
        )
    return (
        _parse_isolated_items(
            anomaly_data.get("isolated_collections", []), field="isolated_collections"
        )
        + _parse_isolated_items(
            anomaly_data.get("no_output_collections", []), field="no_output_collections"
        )
    )


def prepare_manifest(
    *,
    root: Path,
    registry_path: Path,
    run_id: str,
    source_sha: str,
    event_name: str,
    ref_name: str,
) -> dict[str, Any]:
    """Prepare and validate publication manifest for staged generated-data paths."""
    root = root.resolve()
    active, paused = governed_keys(root, registry_path)
    staged = [
        (status, path)
        for status, path in staged_name_status(root)
        if path != MANIFEST_PATH.as_posix()
    ]
    paths = [path for _, path in staged]
    errors = validate_generated_data_paths(
        changed_paths=paths,
        active_vehicle_keys=active,
        paused_vehicle_keys=paused,
    )
    if errors:
        raise ValueError("Invalid generated-data paths: " + ", ".join(errors))
    counts = Counter(status[0] for status, _ in staged)
    isolated_collections = _extract_isolated_collections(root, run_id)
    no_output_collections = _extract_no_output_collections(root, run_id)
    isolation_requested_collections = _extract_requested_isolation_collections(root, run_id)

    manifest = {
        "publication_schema_version": PUBLICATION_SCHEMA_VERSION,
        "publication_status": "prepared_for_commit",
        "run_id": run_id,
        "generated_at_utc": utc_now(),
        "source_commit_sha": source_sha,
        "workflow_event": event_name,
        "target_ref": ref_name,
        "manifest_path": MANIFEST_PATH.as_posix(),
        "published_path_count": len(paths),
        "published_paths": sorted(paths),
        "change_type_counts": dict(sorted(counts.items())),
        "active_vehicle_keys": sorted(active),
        "paused_vehicle_keys": sorted(paused),
        "isolated_collections": isolated_collections,
        "no_output_collections": no_output_collections,
        "isolation_requested_collections": isolation_requested_collections,
    }
    write_json(root / MANIFEST_PATH, manifest)
    return manifest


def verify_staged_manifest(
    *, root: Path, registry_path: Path = DEFAULT_REGISTRY_PATH
) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = root / MANIFEST_PATH
    if not manifest_path.exists():
        raise ValueError("Publication manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("publication_schema_version") != PUBLICATION_SCHEMA_VERSION:
        raise ValueError("Publication manifest schema mismatch")

    manifest_run_id = str(manifest.get("run_id") or "").strip()
    if not manifest_run_id:
        raise ValueError("Publication manifest missing run_id")

    # Validate each isolation outcome in the staged manifest itself.
    staged_isolated = _parse_isolated_items(manifest.get("isolated_collections"))
    staged_no_output = _parse_isolated_items(
        manifest.get("no_output_collections", []), field="no_output_collections"
    )
    staged_requested = _parse_isolated_items(
        manifest.get("isolation_requested_collections", staged_isolated + staged_no_output),
        field="isolation_requested_collections",
    )

    # Each manifest classification must match the same-run anomaly report.
    expected_isolated = _extract_isolated_collections(root, manifest_run_id)
    expected_no_output = _extract_no_output_collections(root, manifest_run_id)
    expected_requested = _extract_requested_isolation_collections(root, manifest_run_id)

    if staged_isolated != expected_isolated:
        raise ValueError(
            "Staged publication manifest isolated_collections metadata mismatch with same-run anomaly report"
        )
    if staged_no_output != expected_no_output:
        raise ValueError(
            "Staged publication manifest no_output_collections metadata mismatch with same-run anomaly report"
        )
    if staged_requested != expected_requested:
        raise ValueError(
            "Staged publication manifest isolation_requested_collections metadata mismatch with same-run anomaly report"
        )
    isolated_keys = {(item["vehicle_key"], item["source"]) for item in staged_isolated}
    no_output_keys = {(item["vehicle_key"], item["source"]) for item in staged_no_output}
    requested_keys = {(item["vehicle_key"], item["source"]) for item in staged_requested}
    if isolated_keys & no_output_keys:
        raise ValueError("Publication manifest classifies a collection as both isolated and no-output")
    if requested_keys != isolated_keys | no_output_keys:
        raise ValueError("Publication manifest isolation outcome classifications do not cover the requested set")

    active, paused = governed_keys(root, registry_path)
    staged = staged_name_status(root)
    staged_paths = sorted(path for _, path in staged)
    errors = validate_generated_data_paths(
        changed_paths=staged_paths,
        active_vehicle_keys=active,
        paused_vehicle_keys=paused,
    )
    if errors:
        raise ValueError("Invalid staged generated-data paths: " + ", ".join(errors))
    expected = sorted(
        path for path in staged_paths if path != MANIFEST_PATH.as_posix()
    )
    if expected != sorted(manifest.get("published_paths", [])):
        raise ValueError("Publication manifest does not match staged generated-data paths")
    if MANIFEST_PATH.as_posix() not in staged_paths:
        raise ValueError("Publication manifest is not staged")
    return {
        "publication_schema_version": PUBLICATION_SCHEMA_VERSION,
        "verification_status": "pass",
        "staged_path_count": len(staged_paths),
        "published_path_count": len(expected),
        "manifest_path": MANIFEST_PATH.as_posix(),
        "isolated_collections": staged_isolated,
        "no_output_collections": staged_no_output,
        "isolation_requested_collections": staged_requested,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Prepare governed generated-data publication")
    sub = result.add_subparsers(dest="action", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH))
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--source-sha", required=True)
    prepare.add_argument("--event-name", required=True)
    prepare.add_argument("--ref-name", required=True)
    verify = sub.add_parser("verify-staged")
    verify.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH))
    sub.add_parser("verify-staged-csv-whitespace")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = Path.cwd()
    if args.action == "prepare":
        report = prepare_manifest(
            root=root,
            registry_path=Path(args.registry),
            run_id=args.run_id,
            source_sha=args.source_sha,
            event_name=args.event_name,
            ref_name=args.ref_name,
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    if args.action == "verify-staged":
        report = verify_staged_manifest(root=root, registry_path=Path(args.registry))
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    if args.action == "verify-staged-csv-whitespace":
        verify_staged_csv_whitespace(root)
        return 0
    raise AssertionError(args.action)


if __name__ == "__main__":
    raise SystemExit(main())
