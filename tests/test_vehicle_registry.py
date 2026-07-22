import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vehicle_registry import active_config_paths, registry_entries


class VehicleRegistryTests(unittest.TestCase):
    def test_repository_registry_matches_audit_00_scope(self):
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

    def test_registry_rejects_duplicate_vehicle_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {"vehicle_key": "duplicate"}
            (root / "config_a.json").write_text(json.dumps(config), encoding="utf-8")
            (root / "config_b.json").write_text(json.dumps(config), encoding="utf-8")
            registry = {
                "schema_version": 1,
                "profile": "test",
                "vehicles": [
                    {
                        "vehicle_key": "duplicate",
                        "config_path": "config_a.json",
                        "enabled": True,
                        "purpose": "test",
                    },
                    {
                        "vehicle_key": "duplicate",
                        "config_path": "config_b.json",
                        "enabled": False,
                        "purpose": "test",
                    },
                ],
            }
            (root / "vehicle_registry.json").write_text(
                json.dumps(registry), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "Duplicate vehicle_key"):
                registry_entries(root=root)

    def test_registry_rejects_config_key_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(
                json.dumps({"vehicle_key": "actual"}), encoding="utf-8"
            )
            registry = {
                "schema_version": 1,
                "profile": "test",
                "vehicles": [
                    {
                        "vehicle_key": "declared",
                        "config_path": "config.json",
                        "enabled": True,
                        "purpose": "test",
                    }
                ],
            }
            (root / "vehicle_registry.json").write_text(
                json.dumps(registry), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "does not match"):
                registry_entries(root=root)


if __name__ == "__main__":
    unittest.main()
