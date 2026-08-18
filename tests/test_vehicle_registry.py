import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vehicle_registry import (
    active_config_paths,
    active_entries,
    active_runs,
    active_source_plan,
    load_registry,
    main,
    parser,
    registry_entries,
    validate_registry,
)


def governed_config(vehicle_key: str) -> dict:
    return {
        "schema_version": 2,
        "vehicle_key": vehicle_key,
        "make": "Test",
        "model": "Vehicle",
        "criteria": {
            "min_year": 2020,
            "max_year": 2025,
            "max_price_cad": 60000,
            "fuel": "Gas",
            "engine": "",
        },
        "origin": {
            "home_city": "Red Deer, AB",
            "home_coords": [52.2681, -113.8112],
            "max_distance_km": 800,
        },
        "sources": {
            "autotrader": {
                "make": "test",
                "model": "vehicle",
                "search_locations": ["Red Deer, AB"],
            },
            "kijiji": {
                "make": "Test",
                "model": "Vehicle",
                "search_locations": ["Edmonton, AB"],
            },
        },
    }


def registry_entry(
    vehicle_key: str,
    config_path: str,
    *,
    enabled: bool = True,
    enabled_sources: list[str] | None = None,
) -> dict:
    entry = {
        "vehicle_key": vehicle_key,
        "config_path": config_path,
        "enabled": enabled,
        "purpose": "primary_purchase",
        "priority": 1,
        "cadence": "weekly",
        "enabled_sources": (
            enabled_sources
            if enabled_sources is not None
            else ["autotrader", "kijiji"]
        ),
        "analysis_profile": "f350_purchase",
    }
    if not enabled:
        entry["pause_reason"] = "test pause"
    return entry


def minimal_registry(vehicles: list | None = None) -> dict:
    return {
        "schema_version": 2,
        "profile": "test",
        "vehicles": vehicles if vehicles is not None else [],
    }


class VehicleRegistryTests(unittest.TestCase):
    def test_repository_registry_matches_approved_audit_scope(self):
        root = Path(__file__).resolve().parents[1]
        entries = registry_entries(root=root)
        active = [entry["vehicle_key"] for entry in entries if entry["enabled"]]
        paused = [entry["vehicle_key"] for entry in entries if not entry["enabled"]]

        self.assertEqual(
            active,
            [
                "ford_f350",
                "ram_3500",
                "subaru_forester",
                "honda_odyssey",
                "kia_carnival",
                "ford_f150",
            ],
        )
        self.assertEqual(paused, ["toyota_tundra"])
        self.assertEqual(
            [str(path) for path in active_config_paths(root=root)],
            [
                "config_f350.json",
                "config_ram3500.json",
                "config_forester.json",
                "config_odyssey.json",
                "config_carnival.json",
                "config_f150.json",
            ],
        )
        runs = [(str(path), source) for path, source in active_runs(root=root)]
        self.assertEqual(len(runs), 12)
        self.assertEqual(
            runs[:2],
            [
                ("config_f350.json", "autotrader"),
                ("config_f350.json", "kijiji"),
            ],
        )
        self.assertFalse(any("tundra" in path for path, _ in runs))

    def test_registry_rejects_duplicate_vehicle_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config_a.json").write_text(json.dumps(governed_config("duplicate")))
            (root / "config_b.json").write_text(json.dumps(governed_config("duplicate")))
            registry = {
                "schema_version": 2,
                "profile": "test",
                "vehicles": [
                    registry_entry("duplicate", "config_a.json"),
                    registry_entry("duplicate", "config_b.json", enabled=False),
                ],
            }
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "Duplicate vehicle_key"):
                registry_entries(root=root)

    def test_registry_rejects_config_key_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("actual")))
            registry = {
                "schema_version": 2,
                "profile": "test",
                "vehicles": [registry_entry("declared", "config.json")],
            }
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "does not match"):
                registry_entries(root=root)

    def test_registry_rejects_invalid_operational_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(
                json.dumps(governed_config("test_vehicle"))
            )
            entry = registry_entry("test_vehicle", "config.json")
            entry["cadence"] = "sometimes"
            registry = {
                "schema_version": 2,
                "profile": "test",
                "vehicles": [entry],
            }
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "invalid cadence"):
                registry_entries(root=root)

    def test_registry_source_plan_honors_enabled_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(
                json.dumps(governed_config("test_vehicle"))
            )
            registry = {
                "schema_version": 2,
                "profile": "test",
                "vehicles": [
                    registry_entry(
                        "test_vehicle",
                        "config.json",
                        enabled_sources=["autotrader"],
                    )
                ],
            }
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            self.assertEqual(
                [(str(path), source) for path, source in active_runs(root=root)],
                [("config.json", "autotrader")],
            )

    def test_paused_vehicle_requires_reason(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(
                json.dumps(governed_config("test_vehicle"))
            )
            entry = registry_entry("test_vehicle", "config.json", enabled=False)
            entry.pop("pause_reason")
            registry = {
                "schema_version": 2,
                "profile": "test",
                "vehicles": [entry],
            }
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "requires pause_reason"):
                registry_entries(root=root)

    def test_enabled_vehicle_with_pause_reason_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json", enabled=True)
            entry["pause_reason"] = "should not be present"
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "must not have pause_reason"):
                registry_entries(root=root)

    def test_duplicate_config_paths_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("vehicle_a")))
            registry = minimal_registry(
                [
                    registry_entry("vehicle_a", "config.json"),
                    registry_entry("vehicle_b", "config.json", enabled=False),
                ]
            )
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "Duplicate config_path"):
                registry_entries(root=root)

    def test_absolute_config_path_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "/absolute/path/config.json")
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "must stay inside the repository"):
                registry_entries(root=root)

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "../config.json")
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "must stay inside the repository"):
                registry_entries(root=root)

    def test_missing_config_file_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = registry_entry("test_vehicle", "nonexistent.json")
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "does not exist"):
                registry_entries(root=root)

    def test_enabled_source_missing_from_config_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = governed_config("test_vehicle")
            del config["sources"]["kijiji"]
            (root / "config.json").write_text(json.dumps(config))
            entry = registry_entry("test_vehicle", "config.json", enabled_sources=["autotrader", "kijiji"])
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "enables source.*without config"):
                registry_entries(root=root)

    def test_registry_with_no_enabled_vehicles_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json", enabled=False)
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "must enable at least one vehicle"):
                registry_entries(root=root)

    def test_valid_multi_vehicle_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config_a.json").write_text(json.dumps(governed_config("vehicle_a")))
            (root / "config_b.json").write_text(json.dumps(governed_config("vehicle_b")))
            (root / "config_c.json").write_text(json.dumps(governed_config("vehicle_c")))
            registry = minimal_registry(
                [
                    registry_entry("vehicle_a", "config_a.json"),
                    registry_entry("vehicle_b", "config_b.json", enabled=False),
                    registry_entry("vehicle_c", "config_c.json"),
                ]
            )
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            entries = registry_entries(root=root)
            self.assertEqual(len(entries), 3)
            self.assertEqual([e["vehicle_key"] for e in entries], ["vehicle_a", "vehicle_b", "vehicle_c"])
            active = [e for e in entries if e["enabled"]]
            self.assertEqual(len(active), 2)
            self.assertEqual([e["vehicle_key"] for e in active], ["vehicle_a", "vehicle_c"])


class LoadRegistryTests(unittest.TestCase):
    def test_valid_registry_loads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = minimal_registry([])
            registry["vehicles"] = [{"dummy": "entry"}]  # Won't validate but will load
            (root / "registry.json").write_text(json.dumps(registry))
            loaded = load_registry(root / "registry.json")
            self.assertEqual(loaded["schema_version"], 2)
            self.assertEqual(loaded["profile"], "test")
            self.assertIsInstance(loaded["vehicles"], list)

    def test_non_object_json_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "registry.json").write_text(json.dumps([1, 2, 3]))
            with self.assertRaisesRegex(ValueError, "Expected a JSON object"):
                load_registry(root / "registry.json")

    def test_missing_schema_version_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = {"profile": "test", "vehicles": []}
            (root / "registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "missing required field.*schema_version"):
                load_registry(root / "registry.json")

    def test_missing_profile_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = {"schema_version": 2, "vehicles": []}
            (root / "registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "missing required field.*profile"):
                load_registry(root / "registry.json")

    def test_missing_vehicles_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = {"schema_version": 2, "profile": "test"}
            (root / "registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "missing required field.*vehicles"):
                load_registry(root / "registry.json")

    def test_unsupported_top_level_field_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = minimal_registry([{}])
            registry["unknown_field"] = "should not be here"
            (root / "registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "unsupported field.*unknown_field"):
                load_registry(root / "registry.json")

    def test_unsupported_schema_version_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = minimal_registry([{}])
            registry["schema_version"] = 999
            (root / "registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "Unsupported registry schema version: 999"):
                load_registry(root / "registry.json")

    def test_invalid_profile_non_string_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = minimal_registry([{}])
            registry["profile"] = 123
            (root / "registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "profile must be a non-empty string"):
                load_registry(root / "registry.json")

    def test_empty_profile_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = minimal_registry([{}])
            registry["profile"] = "  "
            (root / "registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "profile must be a non-empty string"):
                load_registry(root / "registry.json")

    def test_non_list_vehicles_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = {
                "schema_version": 2,
                "profile": "test",
                "vehicles": {"not": "a list"},
            }
            (root / "registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "must contain a non-empty vehicles list"):
                load_registry(root / "registry.json")

    def test_empty_vehicles_list_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = minimal_registry([])
            (root / "registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "must contain a non-empty vehicles list"):
                load_registry(root / "registry.json")


class ValidateEnabledSourcesTests(unittest.TestCase):
    def test_valid_single_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json", enabled_sources=["autotrader"])
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            entries = registry_entries(root=root)
            self.assertEqual(entries[0]["enabled_sources"], ["autotrader"])

    def test_valid_multiple_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json", enabled_sources=["autotrader", "kijiji"])
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            entries = registry_entries(root=root)
            self.assertEqual(entries[0]["enabled_sources"], ["autotrader", "kijiji"])

    def test_empty_enabled_sources_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json", enabled_sources=[])
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "must enable at least one source"):
                registry_entries(root=root)

    def test_non_list_enabled_sources_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json")
            entry["enabled_sources"] = "autotrader"
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "must enable at least one source"):
                registry_entries(root=root)

    def test_non_string_source_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json")
            entry["enabled_sources"] = ["autotrader", 123]
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "enabled_sources must be strings"):
                registry_entries(root=root)

    def test_duplicate_enabled_sources_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json")
            entry["enabled_sources"] = ["autotrader", "autotrader"]
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "duplicate enabled_sources"):
                registry_entries(root=root)

    def test_unsupported_source_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json")
            entry["enabled_sources"] = ["autotrader", "invalid_source"]
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "unsupported source.*invalid_source"):
                registry_entries(root=root)


class ValidateRegistryEntryFieldsTests(unittest.TestCase):
    def test_non_object_vehicle_entry_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = minimal_registry(["not an object"])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "vehicle entry 0 must be an object"):
                registry_entries(root=root)

    def test_missing_required_field_vehicle_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = registry_entry("test_vehicle", "config.json")
            del entry["vehicle_key"]
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "missing field.*vehicle_key"):
                registry_entries(root=root)

    def test_missing_required_field_config_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = registry_entry("test_vehicle", "config.json")
            del entry["config_path"]
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "missing field.*config_path"):
                registry_entries(root=root)

    def test_missing_required_field_enabled(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = registry_entry("test_vehicle", "config.json")
            del entry["enabled"]
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "missing field.*enabled"):
                registry_entries(root=root)

    def test_missing_required_field_purpose(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = registry_entry("test_vehicle", "config.json")
            del entry["purpose"]
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "missing field.*purpose"):
                registry_entries(root=root)

    def test_missing_required_field_priority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = registry_entry("test_vehicle", "config.json")
            del entry["priority"]
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "missing field.*priority"):
                registry_entries(root=root)

    def test_missing_required_field_cadence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = registry_entry("test_vehicle", "config.json")
            del entry["cadence"]
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "missing field.*cadence"):
                registry_entries(root=root)

    def test_missing_required_field_enabled_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = registry_entry("test_vehicle", "config.json")
            del entry["enabled_sources"]
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "missing field.*enabled_sources"):
                registry_entries(root=root)

    def test_missing_required_field_analysis_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = registry_entry("test_vehicle", "config.json")
            del entry["analysis_profile"]
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "missing field.*analysis_profile"):
                registry_entries(root=root)

    def test_unsupported_field_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json")
            entry["unsupported_field"] = "should not be here"
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "unsupported field.*unsupported_field"):
                registry_entries(root=root)

    def test_invalid_vehicle_key_non_string(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = registry_entry("test_vehicle", "config.json")
            entry["vehicle_key"] = 123
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "invalid vehicle_key"):
                registry_entries(root=root)

    def test_invalid_vehicle_key_empty_string(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = registry_entry("test_vehicle", "config.json")
            entry["vehicle_key"] = "  "
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "invalid vehicle_key"):
                registry_entries(root=root)

    def test_invalid_config_path_non_string(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = registry_entry("test_vehicle", "config.json")
            entry["config_path"] = 123
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "invalid config_path"):
                registry_entries(root=root)

    def test_invalid_config_path_empty_string(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = registry_entry("test_vehicle", "config.json")
            entry["config_path"] = "  "
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "invalid config_path"):
                registry_entries(root=root)

    def test_non_boolean_enabled_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = registry_entry("test_vehicle", "config.json")
            entry["enabled"] = "yes"
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "must have boolean enabled"):
                registry_entries(root=root)

    def test_invalid_purpose_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json")
            entry["purpose"] = "invalid_purpose"
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "invalid purpose"):
                registry_entries(root=root)

    def test_priority_must_be_positive_integer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json")
            entry["priority"] = 0
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "priority must be a positive integer"):
                registry_entries(root=root)

    def test_priority_negative_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json")
            entry["priority"] = -1
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "priority must be a positive integer"):
                registry_entries(root=root)

    def test_priority_non_integer_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json")
            entry["priority"] = "high"
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "priority must be a positive integer"):
                registry_entries(root=root)

    def test_priority_boolean_true_rejected(self):
        # Test the boolean-as-int edge case: True == 1 in Python
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json")
            entry["priority"] = True
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "priority must be a positive integer"):
                registry_entries(root=root)

    def test_priority_boolean_false_rejected(self):
        # Test the boolean-as-int edge case: False == 0 in Python
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json")
            entry["priority"] = False
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "priority must be a positive integer"):
                registry_entries(root=root)

    def test_invalid_cadence_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json")
            entry["cadence"] = "daily"
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "invalid cadence"):
                registry_entries(root=root)

    def test_valid_cadence_weekly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json")
            entry["cadence"] = "weekly"
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            entries = registry_entries(root=root)
            self.assertEqual(entries[0]["cadence"], "weekly")

    def test_valid_cadence_manual(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json")
            entry["cadence"] = "manual"
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            entries = registry_entries(root=root)
            self.assertEqual(entries[0]["cadence"], "manual")

    def test_valid_cadence_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json", enabled=False)
            entry["cadence"] = "disabled"
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            entries = registry_entries(root=root)
            self.assertEqual(entries[0]["cadence"], "disabled")


class AnalysisProfileTests(unittest.TestCase):
    def test_primary_purchase_requires_f350_purchase_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json")
            entry["purpose"] = "primary_purchase"
            entry["analysis_profile"] = "wrong_profile"
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "analysis_profile must be 'f350_purchase'"):
                registry_entries(root=root)

    def test_owned_vehicle_value_monitoring_requires_owned_vehicle_value_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json")
            entry["purpose"] = "owned_vehicle_value_monitoring"
            entry["analysis_profile"] = "wrong_profile"
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "analysis_profile must be 'owned_vehicle_value'"):
                registry_entries(root=root)

    def test_family_friend_purchase_search_requires_family_friend_purchase_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json")
            entry["purpose"] = "family_friend_purchase_search"
            entry["analysis_profile"] = "wrong_profile"
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "analysis_profile must be 'family_friend_purchase'"):
                registry_entries(root=root)

    def test_optional_curiosity_requires_optional_curiosity_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json")
            entry["purpose"] = "optional_curiosity"
            entry["analysis_profile"] = "wrong_profile"
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "analysis_profile must be 'optional_curiosity'"):
                registry_entries(root=root)

    def test_valid_primary_purchase_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json")
            entry["purpose"] = "primary_purchase"
            entry["analysis_profile"] = "f350_purchase"
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            entries = registry_entries(root=root)
            self.assertEqual(entries[0]["analysis_profile"], "f350_purchase")

    def test_valid_owned_vehicle_value_monitoring_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json")
            entry["purpose"] = "owned_vehicle_value_monitoring"
            entry["analysis_profile"] = "owned_vehicle_value"
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            entries = registry_entries(root=root)
            self.assertEqual(entries[0]["analysis_profile"], "owned_vehicle_value")

    def test_valid_family_friend_purchase_search_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json")
            entry["purpose"] = "family_friend_purchase_search"
            entry["analysis_profile"] = "family_friend_purchase"
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            entries = registry_entries(root=root)
            self.assertEqual(entries[0]["analysis_profile"], "family_friend_purchase")

    def test_valid_optional_curiosity_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json")
            entry["purpose"] = "optional_curiosity"
            entry["analysis_profile"] = "optional_curiosity"
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            entries = registry_entries(root=root)
            self.assertEqual(entries[0]["analysis_profile"], "optional_curiosity")


class PauseReasonValidationTests(unittest.TestCase):
    def test_paused_vehicle_with_valid_pause_reason(self):
        """Test that a paused vehicle with valid pause_reason is accepted.
        
        Note: Registry requires at least one enabled vehicle, so we include
        a second vehicle to satisfy that global constraint while testing
        the pause_reason behavior of the paused vehicle.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            (root / "helper.json").write_text(json.dumps(governed_config("helper_vehicle")))
            
            subject = registry_entry("test_vehicle", "config.json", enabled=False)
            helper = registry_entry("helper_vehicle", "helper.json", enabled=True)
            
            registry = minimal_registry([subject, helper])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            entries = registry_entries(root=root)
            
            subject_result = [item for item in entries if item["vehicle_key"] == "test_vehicle"][0]
            self.assertEqual(subject_result["pause_reason"], "test pause")

    def test_paused_vehicle_empty_pause_reason_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json", enabled=False)
            entry["pause_reason"] = "  "
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "requires pause_reason"):
                registry_entries(root=root)

    def test_paused_vehicle_non_string_pause_reason_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            entry = registry_entry("test_vehicle", "config.json", enabled=False)
            entry["pause_reason"] = 123
            registry = minimal_registry([entry])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "requires pause_reason"):
                registry_entries(root=root)


class DerivedBehaviorTests(unittest.TestCase):
    def test_registry_entries_returns_all_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config_a.json").write_text(json.dumps(governed_config("vehicle_a")))
            (root / "config_b.json").write_text(json.dumps(governed_config("vehicle_b")))
            registry = minimal_registry(
                [
                    registry_entry("vehicle_a", "config_a.json"),
                    registry_entry("vehicle_b", "config_b.json", enabled=False),
                ]
            )
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            entries = registry_entries(root=root)
            self.assertEqual(len(entries), 2)
            self.assertEqual([e["vehicle_key"] for e in entries], ["vehicle_a", "vehicle_b"])

    def test_active_entries_filters_enabled_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config_a.json").write_text(json.dumps(governed_config("vehicle_a")))
            (root / "config_b.json").write_text(json.dumps(governed_config("vehicle_b")))
            (root / "config_c.json").write_text(json.dumps(governed_config("vehicle_c")))
            registry = minimal_registry(
                [
                    registry_entry("vehicle_a", "config_a.json"),
                    registry_entry("vehicle_b", "config_b.json", enabled=False),
                    registry_entry("vehicle_c", "config_c.json"),
                ]
            )
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            entries = active_entries(root=root)
            self.assertEqual(len(entries), 2)
            self.assertEqual([e["vehicle_key"] for e in entries], ["vehicle_a", "vehicle_c"])

    def test_active_config_paths_returns_enabled_configs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config_a.json").write_text(json.dumps(governed_config("vehicle_a")))
            (root / "config_b.json").write_text(json.dumps(governed_config("vehicle_b")))
            registry = minimal_registry(
                [
                    registry_entry("vehicle_a", "config_a.json"),
                    registry_entry("vehicle_b", "config_b.json", enabled=False),
                ]
            )
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            paths = active_config_paths(root=root)
            self.assertEqual(len(paths), 1)
            self.assertEqual([str(p) for p in paths], ["config_a.json"])

    def test_active_source_plan_returns_config_and_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config_a.json").write_text(json.dumps(governed_config("vehicle_a")))
            (root / "config_b.json").write_text(json.dumps(governed_config("vehicle_b")))
            registry = minimal_registry(
                [
                    registry_entry("vehicle_a", "config_a.json", enabled_sources=["autotrader"]),
                    registry_entry("vehicle_b", "config_b.json", enabled_sources=["kijiji"], enabled=False),
                ]
            )
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            plan = active_source_plan(root=root)
            self.assertEqual(len(plan), 1)
            self.assertEqual(str(plan[0][0]), "config_a.json")
            self.assertEqual(plan[0][1], ("autotrader",))

    def test_active_runs_expands_to_individual_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config_a.json").write_text(json.dumps(governed_config("vehicle_a")))
            (root / "config_b.json").write_text(json.dumps(governed_config("vehicle_b")))
            registry = minimal_registry(
                [
                    registry_entry("vehicle_a", "config_a.json", enabled_sources=["autotrader", "kijiji"]),
                    registry_entry("vehicle_b", "config_b.json", enabled_sources=["autotrader"], enabled=False),
                ]
            )
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            runs = active_runs(root=root)
            self.assertEqual(len(runs), 2)
            self.assertEqual([(str(p), s) for p, s in runs], [("config_a.json", "autotrader"), ("config_a.json", "kijiji")])

    def test_active_runs_respects_enabled_sources_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            registry = minimal_registry([registry_entry("test_vehicle", "config.json", enabled_sources=["kijiji", "autotrader"])])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            runs = active_runs(root=root)
            self.assertEqual([(str(p), s) for p, s in runs], [("config.json", "kijiji"), ("config.json", "autotrader")])


class CLITests(unittest.TestCase):
    def test_parser_accepts_validate_command(self):
        p = parser()
        args = p.parse_args(["validate"])
        self.assertEqual(args.action, "validate")

    def test_parser_accepts_active_configs_command(self):
        p = parser()
        args = p.parse_args(["active-configs"])
        self.assertEqual(args.action, "active-configs")

    def test_parser_accepts_active_runs_command(self):
        p = parser()
        args = p.parse_args(["active-runs"])
        self.assertEqual(args.action, "active-runs")

    def test_parser_accepts_summary_command(self):
        p = parser()
        args = p.parse_args(["summary"])
        self.assertEqual(args.action, "summary")

    def test_parser_accepts_custom_registry_path(self):
        p = parser()
        args = p.parse_args(["validate", "--registry", "custom_registry.json"])
        self.assertEqual(args.registry, "custom_registry.json")

    def test_parser_uses_default_registry_path(self):
        p = parser()
        args = p.parse_args(["validate"])
        self.assertEqual(args.registry, "vehicle_registry.json")

    def test_main_validate_command_succeeds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            registry = minimal_registry([registry_entry("test_vehicle", "config.json")])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with patch("vehicle_registry.Path.cwd", return_value=root):
                result = main(["validate"])
            self.assertEqual(result, 0)

    def test_main_active_configs_command_prints_configs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config_a.json").write_text(json.dumps(governed_config("vehicle_a")))
            (root / "config_b.json").write_text(json.dumps(governed_config("vehicle_b")))
            registry = minimal_registry(
                [
                    registry_entry("vehicle_a", "config_a.json"),
                    registry_entry("vehicle_b", "config_b.json", enabled=False),
                ]
            )
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with patch("vehicle_registry.Path.cwd", return_value=root):
                with patch("builtins.print") as mock_print:
                    result = main(["active-configs"])
            self.assertEqual(result, 0)
            mock_print.assert_called_once_with("config_a.json")

    def test_main_active_runs_command_prints_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            registry = minimal_registry([registry_entry("test_vehicle", "config.json", enabled_sources=["autotrader"])])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with patch("vehicle_registry.Path.cwd", return_value=root):
                with patch("builtins.print") as mock_print:
                    result = main(["active-runs"])
            self.assertEqual(result, 0)
            mock_print.assert_called_once_with("config.json\tautotrader")

    def test_main_summary_command_prints_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config_a.json").write_text(json.dumps(governed_config("vehicle_a")))
            (root / "config_b.json").write_text(json.dumps(governed_config("vehicle_b")))
            registry = minimal_registry(
                [
                    registry_entry("vehicle_a", "config_a.json"),
                    registry_entry("vehicle_b", "config_b.json", enabled=False),
                ]
            )
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with patch("vehicle_registry.Path.cwd", return_value=root):
                with patch("builtins.print") as mock_print:
                    result = main(["summary"])
            self.assertEqual(result, 0)
            self.assertEqual(mock_print.call_count, 2)
            # First call for vehicle_a (ACTIVE)
            first_call = mock_print.call_args_list[0][0][0]
            self.assertIn("ACTIVE", first_call)
            self.assertIn("vehicle_a", first_call)
            # Second call for vehicle_b (PAUSED)
            second_call = mock_print.call_args_list[1][0][0]
            self.assertIn("PAUSED", second_call)
            self.assertIn("vehicle_b", second_call)
            self.assertIn("test pause", second_call)

    def test_main_default_validate_action_prints_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            registry = minimal_registry([registry_entry("test_vehicle", "config.json")])
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with patch("vehicle_registry.Path.cwd", return_value=root):
                with patch("builtins.print") as mock_print:
                    result = main(["validate"])
            self.assertEqual(result, 0)
            mock_print.assert_called_once()
            output = mock_print.call_args[0][0]
            self.assertIn("Vehicle registry valid", output)
            self.assertIn("1 active", output)
            self.assertIn("0 paused", output)

    def test_main_with_custom_registry_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps(governed_config("test_vehicle")))
            registry = minimal_registry([registry_entry("test_vehicle", "config.json")])
            (root / "custom.json").write_text(json.dumps(registry))
            with patch("vehicle_registry.Path.cwd", return_value=root):
                result = main(["validate", "--registry", "custom.json"])
            self.assertEqual(result, 0)

    def test_main_invalid_registry_raises_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = {"schema_version": 2, "profile": "test", "vehicles": []}
            (root / "vehicle_registry.json").write_text(json.dumps(registry))
            with patch("vehicle_registry.Path.cwd", return_value=root):
                with self.assertRaises(ValueError):
                    main(["validate"])


if __name__ == "__main__":
    unittest.main()