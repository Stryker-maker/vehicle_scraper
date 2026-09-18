from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from phase1_common import utc_now, write_json
from storage_retention import validate_generated_data_paths
from vehicle_registry import DEFAULT_REGISTRY_PATH, registry_entries

PUBLICATION_SCHEMA_VERSION = 1
MANIFEST_PATH = Path("data/run_status/publication_latest.json")


def staged_name_status(root: Path) -> list[tuple[str, str]]:
    completed = subprocess.run(
        ["git", "diff", "--cached", "--name-status", "--diff-filter=ACDMRTUXB"],
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


def governed_keys(root: Path, registry_path: Path) -> tuple[list[str], list[str]]:
    entries = registry_entries(root=root, registry_path=registry_path)
    active = [str(entry["vehicle_key"]) for entry in entries if entry["enabled"]]
    paused = [str(entry["vehicle_key"]) for entry in entries if not entry["enabled"]]
    return active, paused


def _parse_isolated_items(isolated: Any) -> list[dict[str, str]]:
    """Validate and parse list of isolated collection entries."""
    if not isinstance(isolated, list):
        raise ValueError("isolated_collections must be a list in anomalies_latest.json")

    pattern = __import__("re").compile(r"^[a-z0-9_]+$")
    parsed: list[dict[str, str]] = []
    for item in isolated:
        if not isinstance(item, dict):
            raise ValueError(f"Invalid entry in isolated_collections: {item!r}")
        vk = str(item.get("vehicle_key") or "").strip()
        src = str(item.get("source") or "").strip()
        if not vk or not src or not pattern.match(vk) or not pattern.match(src):
            raise ValueError(f"Invalid collection identifier in isolated_collections: {item!r}")
        parsed.append({"vehicle_key": vk, "source": src})

    return parsed


def _extract_isolated_collections(root: Path) -> list[dict[str, str]]:
    """Extract and validate isolated collection identifiers from anomalies_latest.json if present."""
    anomaly_path = root / "data" / "run_status" / "anomalies_latest.json"
    if not anomaly_path.exists():
        return []

    try:
        anom_data = json.loads(anomaly_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Unreadable or malformed anomaly report: {exc}") from exc

    if not isinstance(anom_data, dict) or anom_data.get("anomaly_schema_version") != 1:
        raise ValueError("Invalid anomaly report schema in anomalies_latest.json")

    return _parse_isolated_items(anom_data.get("isolated_collections"))


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
    isolated_collections = _extract_isolated_collections(root)

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
    if manifest.get("publication_schema_version") != PUBLICATION_SCHEMA_VERSION:
        raise ValueError("Publication manifest schema mismatch")
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
    raise AssertionError(args.action)


if __name__ == "__main__":
    raise SystemExit(main())
