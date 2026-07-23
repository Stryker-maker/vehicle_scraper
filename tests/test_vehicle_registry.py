import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vehicle_registry import active_config_paths, active_runs, registry_entries


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
        "enabled_sources": enabled_sources or ["autotrader", "kijiji"],
        "analysis_profile": "f350_purchase",
    }
    if not enabled:
        entry["pause_reason"] = "test pause"
    return entry


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
            ],
        )
        self.assertEqual(paused, ["ford_f150", "toyota_tundra"])
        self.assertEqual(
            [str(path) for path in active_config_paths(root=root)],
            [
                "config_f350.json",
                "config_ram3500.json",
                "config_forester.json",
                "config_odyssey.json",
                "config_carnival.json",
            ],
        )
        runs = [(str(path), source) for path, source in active_runs(root=root)]
        self.assertEqual(len(runs), 10)
        self.assertEqual(
            runs[:2],
            [
                ("config_f350.json", "autotrader"),
                ("config_f350.json", "kijiji"),
            ],
        )
        self.assertFalse(
            any("f150" in path or "tundra" in path for path, _ in runs)
        )
        for entry in entries:
            self.assertEqual(entry["cadence"], "weekly")
            self.assertEqual(entry["enabled_sources"], ["autotrader", "kijiji"])

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


if __name__ == "__main__":
    unittest.main()
