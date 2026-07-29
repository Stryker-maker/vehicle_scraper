from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Iterable

from phase1_common import source_status_path, status_is_current_success
from vehicle_config import SUPPORTED_SOURCES, load_vehicle_config
from vehicle_registry import DEFAULT_REGISTRY_PATH, active_runs, registry_entries

WORKFLOW_CONTROL_SCHEMA_VERSION = 1
COLLECTION_SCOPES = ("full", "single_pair")
SOURCE_STATUS_SCHEMA_VERSION = 8
IDENTITY_LIFECYCLE_SCHEMA_VERSION = 2


def build_collection_plan(
    *,
    root: Path,
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    scope: str,
    vehicle_key: str | None = None,
    source: str | None = None,
) -> list[tuple[Path, str]]:
    root = root.resolve()
    if scope not in COLLECTION_SCOPES:
        raise ValueError(f"Unsupported collection scope: {scope}")
        
    event_name = os.environ.get("GITHUB_EVENT_NAME", "local")
    
    if scope == "full":
        entries = registry_entries(root=root, registry_path=registry_path)
        if event_name == "schedule":
            plan = [
                (Path(entry["config_path"]), str(source_name))
                for entry in entries
                if entry["enabled"] and entry["cadence"] == "weekly"
                for source_name in entry["enabled_sources"]
            ]
        else:
            plan = [
                (Path(entry["config_path"]), str(source_name))
                for entry in entries
                if entry["enabled"]
                for source_name in entry["enabled_sources"]
            ]
    else:
        if not vehicle_key:
            raise ValueError("single_pair requires vehicle_key")
        if source not in SUPPORTED_SOURCES:
            raise ValueError(f"single_pair source must be one of {SUPPORTED_SOURCES}")
        matches = [
            entry
            for entry in registry_entries(root=root, registry_path=registry_path)
            if entry["vehicle_key"] == vehicle_key
        ]
        if len(matches) != 1:
            raise ValueError(f"Unknown governed vehicle_key: {vehicle_key}")
        entry = matches[0]
        if not entry["enabled"]:
            raise ValueError(f"Vehicle is paused and cannot be collected: {vehicle_key}")
        if source not in entry["enabled_sources"]:
            raise ValueError(
                f"Source {source} is not enabled for governed vehicle {vehicle_key}"
            )
        plan = [(Path(entry["config_path"]), str(source))]
        
    if not plan:
        raise ValueError("Collection plan must not be empty")
    return plan


def write_plan(path: Path, plan: Iterable[tuple[Path, str]]) -> None:
    rows = [f"{config_path.as_posix()}\t{source}" for config_path, source in plan]
    if not rows:
        raise ValueError("Collection plan must not be empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def read_plan(path: Path) -> list[tuple[Path, str]]:
    rows: list[tuple[Path, str]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 2:
            raise ValueError(f"Invalid plan row {line_number}")
        config_path, source = parts
        if source not in SUPPORTED_SOURCES:
            raise ValueError(f"Unsupported source in plan row {line_number}: {source}")
        rows.append((Path(config_path), source))
    if not rows:
        raise ValueError("Collection plan must not be empty")
    return rows


def validate_single_pair_status(
    *, root: Path, plan_path: Path, run_id: str
) -> dict[str, Any]:
    root = root.resolve()
    plan = read_plan(plan_path)
    if len(plan) != 1:
        raise ValueError("single_pair validation requires exactly one plan row")
    config_path, source = plan[0]
    config = load_vehicle_config(root / config_path)
    status_path = source_status_path(root, config, source)
    status = json.loads(status_path.read_text(encoding="utf-8"))
    if not status_is_current_success(status, run_id):
        raise ValueError(f"Single-pair source status is unhealthy: {status_path}")
    requirements: dict[str, Any] = {
        "schema_version": SOURCE_STATUS_SCHEMA_VERSION,
        "source_adapter_schema_version": 1,
        "identity_lifecycle_schema_version": IDENTITY_LIFECYCLE_SCHEMA_VERSION,
        "identity_lifecycle_status": "updated",
        "runtime_config_projection": "direct_schema_v2",
        "pagination_complete": True,
        "legacy_source_ranking_disabled": True,
        "legacy_price_history_active": False,
    }
    if source == "kijiji":
        requirements.update(
            location_registry_version=1,
            distance_processing_disabled=True,
            distance_filter_disabled=True,
            location_evidence_contract=(
                "listing_specific_source_geography_or_unknown_"
                "query_origin_never_location"
            ),
        )
    mismatches = {
        key: {"expected": expected, "actual": status.get(key)}
        for key, expected in requirements.items()
        if status.get(key) != expected
    }
    if mismatches:
        raise ValueError(
            f"{source} smoke contract failed: " + json.dumps(mismatches, sort_keys=True)
        )
    if int(status.get("identity_observed_current_count", -1)) != int(
        status.get("accepted_record_count", -2)
    ):
        raise ValueError("Identity current count does not match accepted records")
    if source == "kijiji" and int(status.get("query_location_count", 0)) < 1:
        raise ValueError("Kijiji smoke contract has no governed query locations")
    return {
        "workflow_control_schema_version": WORKFLOW_CONTROL_SCHEMA_VERSION,
        "run_id": run_id,
        "vehicle_key": config["vehicle_key"],
        "source": source,
        "status_path": str(status_path.relative_to(root)),
        "fetched_record_count": int(status.get("fetched_record_count", 0)),
        "accepted_record_count": int(status.get("accepted_record_count", 0)),
        "identity_tracked_listing_count": int(
            status.get("identity_tracked_listing_count", 0)
        ),
        "identity_new_listing_count": int(status.get("identity_new_listing_count", 0)),
        "identity_reappeared_listing_count": int(
            status.get("identity_reappeared_listing_count", 0)
        ),
        "validation_status": "pass",
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Govern collection workflow inputs")
    sub = result.add_subparsers(dest="action", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH))
    plan.add_argument("--scope", choices=COLLECTION_SCOPES, required=True)
    plan.add_argument("--vehicle-key")
    plan.add_argument("--source", choices=SUPPORTED_SOURCES)
    plan.add_argument("--output", required=True)
    validate = sub.add_parser("validate-single-pair")
    validate.add_argument("--plan", required=True)
    validate.add_argument("--run-id", required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = Path.cwd()
    if args.action == "plan":
        plan = build_collection_plan(
            root=root,
            registry_path=Path(args.registry),
            scope=args.scope,
            vehicle_key=args.vehicle_key,
            source=args.source,
        )
        output = Path(args.output)
        write_plan(output, plan)
        print(output.read_text(encoding="utf-8"), end="")
        return 0
    if args.action == "validate-single-pair":
        report = validate_single_pair_status(
            root=root, plan_path=Path(args.plan), run_id=args.run_id
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    raise AssertionError(args.action)


if __name__ == "__main__":
    raise SystemExit(main())