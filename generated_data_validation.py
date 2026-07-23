from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from generated_data_publish import MANIFEST_PATH, PUBLICATION_SCHEMA_VERSION
from storage_retention import validate_generated_data_paths, verify_retention
from vehicle_registry import DEFAULT_REGISTRY_PATH, registry_entries

GENERATED_DATA_VALIDATION_SCHEMA_VERSION = 1


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else None


def _read_paths(path: Path) -> list[str]:
    return sorted(
        {
            line.strip().replace("\\", "/")
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
    )


def validate_generated_data_change(
    *,
    root: Path,
    paths_file: Path,
    registry_path: Path = DEFAULT_REGISTRY_PATH,
) -> dict[str, Any]:
    root = root.resolve()
    entries = registry_entries(root=root, registry_path=registry_path)
    active = [str(entry["vehicle_key"]) for entry in entries if entry["enabled"]]
    paused = [str(entry["vehicle_key"]) for entry in entries if not entry["enabled"]]
    changed_paths = _read_paths(paths_file)
    errors = validate_generated_data_paths(
        changed_paths=changed_paths,
        active_vehicle_keys=active,
        paused_vehicle_keys=paused,
    )
    if not changed_paths:
        errors.append("no_generated_data_paths")

    manifest = _load_json(root / MANIFEST_PATH)
    if MANIFEST_PATH.as_posix() in changed_paths:
        if manifest is None:
            errors.append("publication_manifest_missing")
        elif manifest.get("publication_schema_version") != PUBLICATION_SCHEMA_VERSION:
            errors.append("publication_manifest_schema_mismatch")
        else:
            published = set(str(value) for value in manifest.get("published_paths", []))
            changed_without_manifest = set(changed_paths) - {MANIFEST_PATH.as_posix()}
            if not published:
                errors.append("publication_manifest_has_no_paths")
            if not published.issubset(changed_without_manifest):
                errors.append("publication_manifest_paths_not_in_pull_request_diff")

    health_path = Path("data/run_status/latest.json")
    if health_path.as_posix() in changed_paths:
        health = _load_json(root / health_path)
        if health is None:
            errors.append("health_report_missing")
        else:
            if health.get("schema_version") != 6:
                errors.append("health_report_schema_mismatch")
            if health.get("overall_status") == "degraded":
                errors.append("health_report_degraded")
            if int(health.get("unhealthy_source_runs", 0)) != 0:
                errors.append("health_report_contains_unhealthy_sources")

    anomaly_path = Path("data/run_status/anomalies_latest.json")
    if anomaly_path.as_posix() in changed_paths:
        anomaly = _load_json(root / anomaly_path)
        if anomaly is None:
            errors.append("anomaly_report_missing")
        else:
            if anomaly.get("anomaly_schema_version") != 1:
                errors.append("anomaly_report_schema_mismatch")
            if int(anomaly.get("critical_anomaly_count", 0)) > 0:
                errors.append("anomaly_report_contains_critical_anomalies")

    for changed in changed_paths:
        parts = changed.split("/")
        if (
            len(parts) == 4
            and parts[0] == "data"
            and parts[2] == "run_status"
            and parts[3].endswith("_latest.json")
        ):
            status = _load_json(root / changed)
            if status is None:
                errors.append(f"source_status_missing:{changed}")
            elif status.get("execution_status") != "success":
                errors.append(f"source_status_not_success:{changed}")
            elif status.get("schema_version") != 8:
                errors.append(f"source_status_schema_mismatch:{changed}")

    retention = verify_retention(root=root, registry_path=registry_path)
    if retention.get("verification_status") != "pass":
        errors.extend(
            f"retention:{value}" for value in retention.get("verification_errors", [])
        )

    return {
        "generated_data_validation_schema_version": GENERATED_DATA_VALIDATION_SCHEMA_VERSION,
        "validation_status": "pass" if not errors else "fail",
        "changed_path_count": len(changed_paths),
        "changed_paths": changed_paths,
        "validation_errors": errors,
        "retention_verification_status": retention.get("verification_status"),
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Validate a pull-request generated-data diff")
    result.add_argument("--paths-file", required=True)
    result.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH))
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    report = validate_generated_data_change(
        root=Path.cwd(),
        paths_file=Path(args.paths_file),
        registry_path=Path(args.registry),
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["validation_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
