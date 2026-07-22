from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

REGISTRY_SCHEMA_VERSION = 1
DEFAULT_REGISTRY_PATH = Path("vehicle_registry.json")


def load_registry(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        registry = json.load(handle)
    if not isinstance(registry, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    if registry.get("schema_version") != REGISTRY_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported registry schema version: {registry.get('schema_version')!r}"
        )
    vehicles = registry.get("vehicles")
    if not isinstance(vehicles, list) or not vehicles:
        raise ValueError("Registry must contain a non-empty vehicles list")
    return registry


def validate_registry(*, root: Path, registry: dict[str, Any]) -> list[dict[str, Any]]:
    root = root.resolve()
    seen_keys: set[str] = set()
    seen_configs: set[str] = set()
    validated: list[dict[str, Any]] = []

    for index, raw_entry in enumerate(registry["vehicles"]):
        if not isinstance(raw_entry, dict):
            raise ValueError(f"Registry vehicle entry {index} must be an object")
        entry = dict(raw_entry)
        vehicle_key = entry.get("vehicle_key")
        config_path_value = entry.get("config_path")
        enabled = entry.get("enabled")

        if not isinstance(vehicle_key, str) or not vehicle_key.strip():
            raise ValueError(f"Registry vehicle entry {index} has an invalid vehicle_key")
        if not isinstance(config_path_value, str) or not config_path_value.strip():
            raise ValueError(f"Registry vehicle {vehicle_key!r} has an invalid config_path")
        if not isinstance(enabled, bool):
            raise ValueError(f"Registry vehicle {vehicle_key!r} must have boolean enabled")
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
        with resolved_config.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
        if not isinstance(config, dict):
            raise ValueError(f"Expected a JSON object in {config_path_value}")
        if config.get("vehicle_key") != vehicle_key:
            raise ValueError(
                f"Registry vehicle_key {vehicle_key!r} does not match "
                f"{config_path_value}: {config.get('vehicle_key')!r}"
            )

        seen_keys.add(vehicle_key)
        seen_configs.add(config_path_value)
        validated.append(entry)

    if not any(entry["enabled"] for entry in validated):
        raise ValueError("Registry must enable at least one vehicle")
    return validated


def registry_entries(*, root: Path, registry_path: Path = DEFAULT_REGISTRY_PATH) -> list[dict[str, Any]]:
    path = registry_path if registry_path.is_absolute() else root / registry_path
    registry = load_registry(path)
    return validate_registry(root=root, registry=registry)


def active_entries(*, root: Path, registry_path: Path = DEFAULT_REGISTRY_PATH) -> list[dict[str, Any]]:
    return [entry for entry in registry_entries(root=root, registry_path=registry_path) if entry["enabled"]]


def active_config_paths(*, root: Path, registry_path: Path = DEFAULT_REGISTRY_PATH) -> list[Path]:
    return [Path(entry["config_path"]) for entry in active_entries(root=root, registry_path=registry_path)]


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Validate the vehicle registry and select enabled configs.")
    result.add_argument("action", choices=("validate", "active-configs", "summary"))
    result.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH))
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = Path.cwd()
    entries = registry_entries(root=root, registry_path=Path(args.registry))
    active = [entry for entry in entries if entry["enabled"]]

    if args.action == "active-configs":
        for entry in active:
            print(entry["config_path"])
    elif args.action == "summary":
        for entry in entries:
            state = "ACTIVE" if entry["enabled"] else "PAUSED"
            reason = f" — {entry.get('pause_reason')}" if entry.get("pause_reason") else ""
            print(f"{state}: {entry['vehicle_key']} ({entry['purpose']}){reason}")
    else:
        print(
            f"Vehicle registry valid: {len(active)} active, "
            f"{len(entries) - len(active)} paused."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
