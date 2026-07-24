from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from phase1_common import write_json
from vehicle_registry import (
    ALLOWED_CADENCES, DEFAULT_REGISTRY_PATH, cadence_entries, registry_entries,
)

STORAGE_RETENTION_SCHEMA_VERSION = 1
SOURCE_ARCHIVES_TO_KEEP = 8
MANUAL_REVIEW_ARCHIVES_TO_KEEP = 4
MAX_RECENT_FILE_DELETIONS = 100
MAX_MANAGED_FILE_BYTES = 50 * 1024 * 1024
MAX_ACTIVE_DATA_BYTES = 500 * 1024 * 1024


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _chain_digest(previous: str, records: Iterable[dict[str, Any]]) -> str:
    digest = previous or ("0" * 64)
    for record in records:
        payload = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(bytes.fromhex(digest) + payload).hexdigest()
    return digest


def _relative(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def _archive_candidates(directory: Path, pattern: str, latest_name: str | None = None) -> list[Path]:
    if not directory.exists():
        return []
    values = [
        path
        for path in directory.glob(pattern)
        if path.is_file() and (latest_name is None or path.name != latest_name)
    ]
    return sorted(values, key=lambda path: path.name, reverse=True)


def _deletion_record(
    *,
    root: Path,
    path: Path,
    category: str,
    reason: str,
    run_id: str,
    deleted_at_utc: str,
) -> dict[str, Any]:
    content = path.read_bytes()
    return {
        "storage_retention_schema_version": STORAGE_RETENTION_SCHEMA_VERSION,
        "run_id": run_id,
        "deleted_at_utc": deleted_at_utc,
        "path": _relative(path, root),
        "category": category,
        "reason": reason,
        "size_bytes": len(content),
        "sha256": _sha256_bytes(content),
    }


def _ledger_path(root: Path, vehicle_key: str) -> Path:
    return root / "data" / vehicle_key / "retention" / "deletion_ledger.json"


def _latest_report_path(root: Path, vehicle_key: str) -> Path:
    return root / "data" / vehicle_key / "retention" / "latest.json"


def _load_ledger(path: Path, vehicle_key: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "storage_retention_schema_version": STORAGE_RETENTION_SCHEMA_VERSION,
            "vehicle_key": vehicle_key,
            "deleted_file_count_total": 0,
            "deleted_bytes_total": 0,
            "deletion_chain_sha256": "0" * 64,
            "recent_deletions": [],
        }
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        value = {}
    if (
        not isinstance(value, dict)
        or value.get("storage_retention_schema_version")
        != STORAGE_RETENTION_SCHEMA_VERSION
        or value.get("vehicle_key") != vehicle_key
    ):
        return {
            "storage_retention_schema_version": STORAGE_RETENTION_SCHEMA_VERSION,
            "vehicle_key": vehicle_key,
            "deleted_file_count_total": 0,
            "deleted_bytes_total": 0,
            "deletion_chain_sha256": "0" * 64,
            "recent_deletions": [],
        }
    return value


def _record_file_deletions(
    *, root: Path, vehicle_key: str, deletions: list[dict[str, Any]], run_id: str
) -> dict[str, Any]:
    path = _ledger_path(root, vehicle_key)
    ledger = _load_ledger(path, vehicle_key)
    recent = [
        dict(value)
        for value in ledger.get("recent_deletions", [])
        if isinstance(value, dict)
    ]
    recent.extend(deletions)
    recent = recent[-MAX_RECENT_FILE_DELETIONS:]
    updated = {
        "storage_retention_schema_version": STORAGE_RETENTION_SCHEMA_VERSION,
        "vehicle_key": vehicle_key,
        "last_updated_run_id": run_id,
        "last_updated_at_utc": utc_now(),
        "deleted_file_count_total": int(ledger.get("deleted_file_count_total", 0))
        + len(deletions),
        "deleted_bytes_total": int(ledger.get("deleted_bytes_total", 0))
        + sum(int(value.get("size_bytes", 0)) for value in deletions),
        "deletion_chain_sha256": _chain_digest(
            str(ledger.get("deletion_chain_sha256") or "0" * 64), deletions
        ),
        "recent_deletions": recent,
        "recent_deletion_limit": MAX_RECENT_FILE_DELETIONS,
    }
    write_json(path, updated)
    return updated


def _paths_to_delete(root: Path, vehicle_key: str) -> list[tuple[Path, str, str]]:
    base = root / "data" / vehicle_key
    deletions: list[tuple[Path, str, str]] = []
    for source in ("autotrader", "kijiji"):
        directory = base / source
        archive_files = _archive_candidates(
            directory,
            f"{vehicle_key}_{source}_*.csv",
            latest_name=f"{vehicle_key}_{source}_latest.csv",
        )
        for path in archive_files[SOURCE_ARCHIVES_TO_KEEP:]:
            deletions.append(
                (path, f"{source}_source_archive", "archive_count_limit_exceeded")
            )
    manual_files = _archive_candidates(
        base / "manual_review",
        f"{vehicle_key}_manual_review_*.csv",
        latest_name=f"{vehicle_key}_manual_review_latest.csv",
    )
    for path in manual_files[MANUAL_REVIEW_ARCHIVES_TO_KEEP:]:
        deletions.append(
            (path, "manual_review_archive", "archive_count_limit_exceeded")
        )
    for name in ("price_history_autotrader.json", "price_history_kijiji.json"):
        path = base / name
        if path.exists() and path.is_file():
            deletions.append(
                (path, "legacy_price_history", "retired_unsupported_history")
            )
    merged = base / "merged"
    if merged.exists():
        for path in sorted(merged.glob("*.csv")):
            if path.is_file():
                deletions.append(
                    (path, "legacy_merged_csv", "disabled_misleading_legacy_output")
                )
    return deletions


def _managed_metrics(root: Path, active_vehicle_keys: Iterable[str]) -> dict[str, Any]:
    files: list[Path] = []
    for vehicle_key in active_vehicle_keys:
        base = root / "data" / vehicle_key
        if base.exists():
            files.extend(path for path in base.rglob("*") if path.is_file())
    global_dirs = [root / "data" / "run_status", root / "data" / "retention"]
    for directory in global_dirs:
        if directory.exists():
            files.extend(path for path in directory.rglob("*") if path.is_file())
    unique = sorted({path.resolve() for path in files})
    oversized = [
        {
            "path": _relative(path, root),
            "size_bytes": path.stat().st_size,
        }
        for path in unique
        if path.stat().st_size > MAX_MANAGED_FILE_BYTES
    ]
    return {
        "managed_file_count": len(unique),
        "managed_bytes": sum(path.stat().st_size for path in unique),
        "largest_file_bytes": max((path.stat().st_size for path in unique), default=0),
        "oversized_files": oversized,
    }


def _verify_archive_limits(root: Path, vehicle_key: str) -> list[str]:
    errors: list[str] = []
    base = root / "data" / vehicle_key
    for source in ("autotrader", "kijiji"):
        count = len(
            _archive_candidates(
                base / source,
                f"{vehicle_key}_{source}_*.csv",
                latest_name=f"{vehicle_key}_{source}_latest.csv",
            )
        )
        if count > SOURCE_ARCHIVES_TO_KEEP:
            errors.append(
                f"{vehicle_key}:{source}:archive_count={count}>{SOURCE_ARCHIVES_TO_KEEP}"
            )
    manual_count = len(
        _archive_candidates(
            base / "manual_review",
            f"{vehicle_key}_manual_review_*.csv",
            latest_name=f"{vehicle_key}_manual_review_latest.csv",
        )
    )
    if manual_count > MANUAL_REVIEW_ARCHIVES_TO_KEEP:
        errors.append(
            f"{vehicle_key}:manual_review:archive_count={manual_count}>"
            f"{MANUAL_REVIEW_ARCHIVES_TO_KEEP}"
        )
    for name in ("price_history_autotrader.json", "price_history_kijiji.json"):
        if (base / name).exists():
            errors.append(f"{vehicle_key}:{name}:legacy_file_present")
    merged = base / "merged"
    if merged.exists() and any(path.is_file() for path in merged.glob("*.csv")):
        errors.append(f"{vehicle_key}:merged:legacy_csv_present")
    return errors


def apply_retention(
    *,
    root: Path,
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    run_id: str = "local",
    deleted_at_utc: str | None = None,
    cadence: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    registry_path = (
        registry_path if registry_path.is_absolute() else root / registry_path
    )
    entries = (
        cadence_entries(root=root, cadence=cadence, registry_path=registry_path)
        if cadence is not None
        else registry_entries(root=root, registry_path=registry_path)
    )
    active_keys = [str(entry["vehicle_key"]) for entry in entries if entry["enabled"]]
    deleted_at_utc = deleted_at_utc or utc_now()
    vehicle_reports: list[dict[str, Any]] = []
    for vehicle_key in active_keys:
        deletions: list[dict[str, Any]] = []
        for path, category, reason in _paths_to_delete(root, vehicle_key):
            record = _deletion_record(
                root=root,
                path=path,
                category=category,
                reason=reason,
                run_id=run_id,
                deleted_at_utc=deleted_at_utc,
            )
            path.unlink()
            deletions.append(record)
        ledger = _record_file_deletions(
            root=root, vehicle_key=vehicle_key, deletions=deletions, run_id=run_id
        )
        report = {
            "storage_retention_schema_version": STORAGE_RETENTION_SCHEMA_VERSION,
            "run_id": run_id,
            "generated_at_utc": deleted_at_utc,
            "vehicle_key": vehicle_key,
            "deleted_file_count": len(deletions),
            "deleted_bytes": sum(int(value["size_bytes"]) for value in deletions),
            "deletions": deletions,
            "source_archive_keep_count": SOURCE_ARCHIVES_TO_KEEP,
            "manual_review_archive_keep_count": MANUAL_REVIEW_ARCHIVES_TO_KEEP,
            "legacy_price_history_removed": True,
            "legacy_merged_csv_removed": True,
            "ledger": str(_ledger_path(root, vehicle_key).relative_to(root)),
            "ledger_deleted_file_count_total": ledger["deleted_file_count_total"],
            "ledger_deleted_bytes_total": ledger["deleted_bytes_total"],
            "ledger_chain_sha256": ledger["deletion_chain_sha256"],
        }
        write_json(_latest_report_path(root, vehicle_key), report)
        vehicle_reports.append(report)
    metrics = _managed_metrics(root, active_keys)
    verification_errors = [
        error
        for vehicle_key in active_keys
        for error in _verify_archive_limits(root, vehicle_key)
    ]
    if metrics["oversized_files"]:
        verification_errors.append("managed_file_size_limit_exceeded")
    if int(metrics["managed_bytes"]) > MAX_ACTIVE_DATA_BYTES:
        verification_errors.append("active_data_size_limit_exceeded")
    global_report = {
        "storage_retention_schema_version": STORAGE_RETENTION_SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at_utc": deleted_at_utc,
        "active_vehicle_keys": active_keys,
        "source_archive_keep_count": SOURCE_ARCHIVES_TO_KEEP,
        "manual_review_archive_keep_count": MANUAL_REVIEW_ARCHIVES_TO_KEEP,
        "max_managed_file_bytes": MAX_MANAGED_FILE_BYTES,
        "max_active_data_bytes": MAX_ACTIVE_DATA_BYTES,
        "deleted_file_count": sum(
            int(value["deleted_file_count"]) for value in vehicle_reports
        ),
        "deleted_bytes": sum(int(value["deleted_bytes"]) for value in vehicle_reports),
        **metrics,
        "verification_status": "pass" if not verification_errors else "fail",
        "verification_errors": verification_errors,
        "vehicle_reports": [
            {
                "vehicle_key": value["vehicle_key"],
                "deleted_file_count": value["deleted_file_count"],
                "deleted_bytes": value["deleted_bytes"],
                "latest_report": str(
                    _latest_report_path(root, value["vehicle_key"]).relative_to(root)
                ),
                "ledger": value["ledger"],
            }
            for value in vehicle_reports
        ],
    }
    global_path = root / "data" / "retention" / "latest.json"
    write_json(global_path, global_report)
    return global_report


def verify_retention(
    *,
    root: Path,
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    cadence: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    registry_path = (
        registry_path if registry_path.is_absolute() else root / registry_path
    )
    entries = (
        cadence_entries(root=root, cadence=cadence, registry_path=registry_path)
        if cadence is not None
        else registry_entries(root=root, registry_path=registry_path)
    )
    active_keys = [str(entry["vehicle_key"]) for entry in entries if entry["enabled"]]
    errors = [
        error
        for vehicle_key in active_keys
        for error in _verify_archive_limits(root, vehicle_key)
    ]
    metrics = _managed_metrics(root, active_keys)
    if metrics["oversized_files"]:
        errors.append("managed_file_size_limit_exceeded")
    if int(metrics["managed_bytes"]) > MAX_ACTIVE_DATA_BYTES:
        errors.append("active_data_size_limit_exceeded")
    return {
        "storage_retention_schema_version": STORAGE_RETENTION_SCHEMA_VERSION,
        "verification_status": "pass" if not errors else "fail",
        "verification_errors": errors,
        "active_vehicle_keys": active_keys,
        **metrics,
    }


def validate_generated_data_paths(
    *,
    changed_paths: Iterable[str],
    active_vehicle_keys: Iterable[str],
    paused_vehicle_keys: Iterable[str],
) -> list[str]:
    active = set(active_vehicle_keys)
    paused = set(paused_vehicle_keys)
    errors: list[str] = []
    for raw_path in changed_paths:
        path = raw_path.strip().replace("\\", "/")
        if not path:
            continue
        if not path.startswith("data/"):
            errors.append(f"outside_data:{path}")
            continue
        parts = path.split("/")
        if len(parts) < 2:
            errors.append(f"invalid_data_path:{path}")
            continue
        scope = parts[1]
        if scope in {"run_status", "retention"}:
            continue
        if scope in paused:
            errors.append(f"paused_vehicle_changed:{path}")
        elif scope not in active:
            errors.append(f"ungoverned_vehicle_path:{path}")
    return errors


def _staged_paths(root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACDMRTUXB"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git_diff_cached_failed")
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def validate_staged_diff(
    *, root: Path, registry_path: Path = DEFAULT_REGISTRY_PATH
) -> dict[str, Any]:
    root = root.resolve()
    registry_path = (
        registry_path if registry_path.is_absolute() else root / registry_path
    )
    entries = registry_entries(root=root, registry_path=registry_path)
    active = [str(entry["vehicle_key"]) for entry in entries if entry["enabled"]]
    paused = [str(entry["vehicle_key"]) for entry in entries if not entry["enabled"]]
    paths = _staged_paths(root)
    errors = validate_generated_data_paths(
        changed_paths=paths,
        active_vehicle_keys=active,
        paused_vehicle_keys=paused,
    )
    return {
        "storage_retention_schema_version": STORAGE_RETENTION_SCHEMA_VERSION,
        "changed_path_count": len(paths),
        "changed_paths": paths,
        "validation_status": "pass" if not errors else "fail",
        "validation_errors": errors,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Apply and verify bounded generated-data retention"
    )
    sub = result.add_subparsers(dest="action", required=True)
    for name in ("apply", "verify", "validate-staged"):
        action = sub.add_parser(name)
        action.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH))
        if name != "validate-staged":
            action.add_argument("--cadence", choices=sorted(ALLOWED_CADENCES))
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = Path.cwd()
    registry = Path(args.registry)
    run_id = __import__("os").environ.get("GITHUB_RUN_ID", "local")
    if args.action == "apply":
        report = apply_retention(
            root=root,
            registry_path=registry,
            run_id=run_id,
            cadence=args.cadence,
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["verification_status"] == "pass" else 1
    if args.action == "verify":
        report = verify_retention(
            root=root, registry_path=registry, cadence=args.cadence
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["verification_status"] == "pass" else 1
    if args.action == "validate-staged":
        report = validate_staged_diff(root=root, registry_path=registry)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["validation_status"] == "pass" else 1
    raise AssertionError(args.action)


if __name__ == "__main__":
    raise SystemExit(main())
