from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from vehicle_config import SUPPORTED_SOURCES, load_vehicle_config

REGISTRY_SCHEMA_VERSION = 2
DEFAULT_REGISTRY_PATH = Path("vehicle_registry.json")
ALLOWED_PURPOSES = {
    "primary_purchase",
    "owned_vehicle_value_monitoring",
    "family_friend_purchase_search",
    "optional_curiosity",
}
ALLOWED_CADENCES = {"weekly", "manual"}
PURPOSE_ANALYSIS_PROFILES = {
    "primary_purchase": "f350_purchase",
    "owned_vehicle_value_monitoring": "owned_vehicle_value",
    "family_friend_purchase_search": "family_friend_purchase",
    "optional_curiosity": "optional_curiosity",
}
REQUIRED_ENTRY_FIELDS = {
    "vehicle_key",
    "config_path",
    "enabled",
    "purpose",
    "priority",
    "cadence",
    "enabled_sources",
    "analysis_profile",
}
OPTIONAL_ENTRY_FIELDS = {"pause_reason"}


def load_registry(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        registry = json.load(handle)
    if not isinstance(registry, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    unknown = sorted(set(registry) - {"schema_version", "profile", "vehicles"})
    missing = sorted({"schema_version", "profile", "vehicles"} - set(registry))
    if missing:
        raise ValueError(f"Registry is missing required field(s): {', '.join(missing)}")
    if unknown:
        raise ValueError(f"Registry contains unsupported field(s): {', '.join(unknown)}")
    if registry.get("schema_version") != REGISTRY_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported registry schema version: {registry.get('schema_version')!r}"
        )
    profile = registry.get("profile")
    if not isinstance(profile, str) or not profile.strip():
        raise ValueError("Registry profile must be a non-empty string")
    vehicles = registry.get("vehicles")
    if not isinstance(vehicles, list) or not vehicles:
        raise ValueError("Registry must contain a non-empty vehicles list")
    return registry


def _validate_enabled_sources(value: Any, vehicle_key: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"Registry vehicle {vehicle_key!r} must enable at least one source")
    if any(not isinstance(source, str) for source in value):
        raise ValueError(f"Registry vehicle {vehicle_key!r} enabled_sources must be strings")
    if len(value) != len(set(value)):
        raise ValueError(f"Registry vehicle {vehicle_key!r} has duplicate enabled_sources")
    unsupported = sorted(set(value) - set(SUPPORTED_SOURCES))
    if unsupported:
        raise ValueError(
            f"Registry vehicle {vehicle_key!r} has unsupported source(s): {', '.join(unsupported)}"
        )
    return list(value)


def validate_registry(*, root: Path, registry: dict[str, Any]) -> list[dict[str, Any]]:
    root = root.resolve()
    seen_keys: set[str] = set()
    seen_configs: set[str] = set()
    validated: list[dict[str, Any]] = []

    for index, raw_entry in enumerate(registry["vehicles"]):
        if not isinstance(raw_entry, dict):
            raise ValueError(f"Registry vehicle entry {index} must be an object")
        missing = sorted(REQUIRED_ENTRY_FIELDS - set(raw_entry))
        unknown = sorted(set(raw_entry) - REQUIRED_ENTRY_FIELDS - OPTIONAL_ENTRY_FIELDS)
        if missing:
            raise ValueError(
                f"Registry vehicle entry {index} is missing field(s): {', '.join(missing)}"
            )
        if unknown:
            raise ValueError(
                f"Registry vehicle entry {index} has unsupported field(s): {', '.join(unknown)}"
            )
        entry = dict(raw_entry)
        vehicle_key = entry["vehicle_key"]
        config_path_value = entry["config_path"]
        enabled = entry["enabled"]
        purpose = entry["purpose"]
        priority = entry["priority"]
        cadence = entry["cadence"]
        analysis_profile = entry["analysis_profile"]

        if not isinstance(vehicle_key, str) or not vehicle_key.strip():
            raise ValueError(f"Registry vehicle entry {index} has an invalid vehicle_key")
        if not isinstance(config_path_value, str) or not config_path_value.strip():
            raise ValueError(f"Registry vehicle {vehicle_key!r} has an invalid config_path")
        if not isinstance(enabled, bool):
            raise ValueError(f"Registry vehicle {vehicle_key!r} must have boolean enabled")
        if purpose not in ALLOWED_PURPOSES:
            raise ValueError(f"Registry vehicle {vehicle_key!r} has invalid purpose: {purpose!r}")
        if isinstance(priority, bool) or not isinstance(priority, int) or priority < 1:
            raise ValueError(f"Registry vehicle {vehicle_key!r} priority must be a positive integer")
        if cadence not in ALLOWED_CADENCES:
            raise ValueError(f"Registry vehicle {vehicle_key!r} has invalid cadence: {cadence!r}")
        expected_profile = PURPOSE_ANALYSIS_PROFILES[purpose]
        if analysis_profile != expected_profile:
            raise ValueError(
                f"Registry vehicle {vehicle_key!r} analysis_profile must be {expected_profile!r}"
            )
        enabled_sources = _validate_enabled_sources(entry["enabled_sources"], vehicle_key)
        entry["enabled_sources"] = enabled_sources

        pause_reason = entry.get("pause_reason")
        if not enabled and (not isinstance(pause_reason, str) or not pause_reason.strip()):
            raise ValueError(f"Paused registry vehicle {vehicle_key!r} requires pause_reason")
        if enabled and pause_reason is not None:
            raise ValueError(f"Enabled registry vehicle {vehicle_key!r} must not have pause_reason")
        if vehicle_key in seen_keys:
            raise ValueError(f"Duplicate vehicle_key in registry: {vehicle_key}")
        if config_path_value in seen_configs:
            raise ValueError(f"Duplicate config_path in registry: {config_path_value}")

        config_path = Path(config_path_value)
        if config_path.is_absolute() or ".." in config_path.parts:
            raise ValueError(
                f"Registry config_path must stay inside the repository: {config_path_value}"
            )
        resolved_config = root / config_path
        if not resolved_config.is_file():
            raise ValueError(f"Registry config does not exist: {config_path_value}")
        config = load_vehicle_config(resolved_config)
        if config.get("vehicle_key") != vehicle_key:
            raise ValueError(
                f"Registry vehicle_key {vehicle_key!r} does not match "
                f"{config_path_value}: {config.get('vehicle_key')!r}"
            )
        missing_source_config = sorted(set(enabled_sources) - set(config["sources"]))
        if missing_source_config:
            raise ValueError(
                f"Registry vehicle {vehicle_key!r} enables source(s) without config: "
                f"{', '.join(missing_source_config)}"
            )

        seen_keys.add(vehicle_key)
        seen_configs.add(config_path_value)
        validated.append(entry)

    if not any(entry["enabled"] for entry in validated):
        raise ValueError("Registry must enable at least one vehicle")
    return validated


def registry_entries(
    *, root: Path, registry_path: Path = DEFAULT_REGISTRY_PATH
) -> list[dict[str, Any]]:
    path = registry_path if registry_path.is_absolute() else root / registry_path
    registry = load_registry(path)
    return validate_registry(root=root, registry=registry)


def enabled_entries(
    *, root: Path, registry_path: Path = DEFAULT_REGISTRY_PATH
) -> list[dict[str, Any]]:
    return [
        entry
        for entry in registry_entries(root=root, registry_path=registry_path)
        if entry["enabled"]
    ]


def active_entries(
    *, root: Path, registry_path: Path = DEFAULT_REGISTRY_PATH
) -> list[dict[str, Any]]:
    return enabled_entries(root=root, registry_path=registry_path)


def cadence_entries(
    *, root: Path, cadence: str, registry_path: Path = DEFAULT_REGISTRY_PATH
) -> list[dict[str, Any]]:
    if cadence not in ALLOWED_CADENCES:
        raise ValueError(f"Unsupported registry cadence: {cadence}")
    return [
        entry
        for entry in enabled_entries(root=root, registry_path=registry_path)
        if entry["cadence"] == cadence
    ]


def active_config_paths(
    *, root: Path, registry_path: Path = DEFAULT_REGISTRY_PATH
) -> list[Path]:
    return [
        Path(entry["config_path"])
        for entry in enabled_entries(root=root, registry_path=registry_path)
    ]


def active_source_plan(
    *, root: Path, registry_path: Path = DEFAULT_REGISTRY_PATH
) -> list[tuple[Path, tuple[str, ...]]]:
    return [
        (Path(entry["config_path"]), tuple(entry["enabled_sources"]))
        for entry in enabled_entries(root=root, registry_path=registry_path)
    ]


def source_plan_for_cadence(
    *, root: Path, cadence: str, registry_path: Path = DEFAULT_REGISTRY_PATH
) -> list[tuple[Path, tuple[str, ...]]]:
    return [
        (Path(entry["config_path"]), tuple(entry["enabled_sources"]))
        for entry in cadence_entries(
            root=root, cadence=cadence, registry_path=registry_path
        )
    ]


def active_runs(
    *, root: Path, registry_path: Path = DEFAULT_REGISTRY_PATH
) -> list[tuple[Path, str]]:
    return [
        (config_path, source)
        for config_path, sources in active_source_plan(
            root=root, registry_path=registry_path
        )
        for source in sources
    ]


def runs_for_cadence(
    *, root: Path, cadence: str, registry_path: Path = DEFAULT_REGISTRY_PATH
) -> list[tuple[Path, str]]:
    return [
        (config_path, source)
        for config_path, sources in source_plan_for_cadence(
            root=root, cadence=cadence, registry_path=registry_path
        )
        for source in sources
    ]


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Validate governed vehicle scope and source plans."
    )
    result.add_argument(
        "action",
        choices=(
            "validate",
            "active-configs",
            "active-runs",
            "weekly-runs",
            "manual-runs",
            "summary",
        ),
    )
    result.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH))
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = Path.cwd()
    registry_path = Path(args.registry)
    entries = registry_entries(root=root, registry_path=registry_path)
    enabled = [entry for entry in entries if entry["enabled"]]

    if args.action == "active-configs":
        for entry in enabled:
            print(entry["config_path"])
    elif args.action == "active-runs":
        for config_path, source in active_runs(
            root=root, registry_path=registry_path
        ):
            print(f"{config_path}\t{source}")
    elif args.action in {"weekly-runs", "manual-runs"}:
        cadence = args.action.removesuffix("-runs")
        for config_path, source in runs_for_cadence(
            root=root, cadence=cadence, registry_path=registry_path
        ):
            print(f"{config_path}\t{source}")
    elif args.action == "summary":
        for entry in entries:
            state = "ENABLED" if entry["enabled"] else "PAUSED"
            reason = (
                f" — {entry.get('pause_reason')}" if entry.get("pause_reason") else ""
            )
            sources = ",".join(entry["enabled_sources"])
            print(
                f"{state}: {entry['vehicle_key']} | purpose={entry['purpose']} | "
                f"priority={entry['priority']} | cadence={entry['cadence']} | "
                f"sources={sources}{reason}"
            )
    else:
        weekly_count = len(
            runs_for_cadence(
                root=root, cadence="weekly", registry_path=registry_path
            )
        )
        manual_count = len(
            runs_for_cadence(
                root=root, cadence="manual", registry_path=registry_path
            )
        )
        print(
            f"Vehicle registry valid: {len(enabled)} enabled, "
            f"{len(entries) - len(enabled)} paused, {weekly_count} weekly source runs, "
            f"{manual_count} manual source runs."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
