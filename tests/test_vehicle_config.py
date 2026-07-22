import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vehicle_config import legacy_runtime_config, load_vehicle_config, validate_vehicle_config


def config_fixture() -> dict:
    return {
        "schema_version": 2,
        "vehicle_key": "test_vehicle",
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
                "search_locations": ["Calgary, AB"],
            },
            "kijiji": {
                "make": "Test",
                "model": "Vehicle",
                "search_locations": ["Edmonton, AB"],
            },
        },
    }


class VehicleConfigTests(unittest.TestCase):
    def test_repository_configs_use_schema_v2_without_legacy_controls(self):
        root = Path(__file__).resolve().parents[1]
        paths = sorted(root.glob("config_*.json"))
        self.assertEqual(len(paths), 7)
        for path in paths:
            config = load_vehicle_config(path)
            self.assertEqual(config["schema_version"], 2)
            self.assertNotIn("max_results", config)
            self.assertNotIn("ranking_weights", config)
            self.assertNotIn("search_locations", config)
            self.assertEqual(set(config["sources"]), {"autotrader", "kijiji"})

    def test_projection_uses_selected_source_locations(self):
        config = config_fixture()
        autotrader = legacy_runtime_config(config, source="autotrader", max_results=999)
        kijiji = legacy_runtime_config(config, source="kijiji", max_results=999)
        self.assertEqual(autotrader["search_locations"], ["Calgary, AB"])
        self.assertEqual(kijiji["search_locations"], ["Edmonton, AB"])
        self.assertEqual(autotrader["max_results"], 999)
        self.assertIn("ranking_weights", autotrader)
        self.assertNotIn("criteria", autotrader)
        self.assertNotIn("sources", autotrader)

    def test_rejects_obsolete_flat_fields(self):
        config = config_fixture()
        config["max_results"] = 50
        with self.assertRaisesRegex(ValueError, "unsupported field"):
            validate_vehicle_config(config)

    def test_rejects_duplicate_locations(self):
        config = config_fixture()
        config["sources"]["kijiji"]["search_locations"] = [
            "Edmonton, AB", "Edmonton, AB"
        ]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_vehicle_config(config)

    def test_rejects_invalid_location_naming(self):
        config = config_fixture()
        config["sources"]["autotrader"]["search_locations"] = ["Calgary Alberta"]
        with self.assertRaisesRegex(ValueError, "City, PROVINCE"):
            validate_vehicle_config(config)

    def test_rejects_invalid_ranges_and_coordinates(self):
        config = config_fixture()
        config["criteria"]["min_year"] = 2026
        with self.assertRaisesRegex(ValueError, "must not exceed"):
            validate_vehicle_config(config)
        config = config_fixture()
        config["origin"]["home_coords"] = [200, -113]
        with self.assertRaisesRegex(ValueError, "coordinate bounds"):
            validate_vehicle_config(config)

    def test_load_validates_file_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            invalid = copy.deepcopy(config_fixture())
            invalid["schema_version"] = 1
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unsupported vehicle config schema"):
                load_vehicle_config(path)


if __name__ == "__main__":
    unittest.main()
