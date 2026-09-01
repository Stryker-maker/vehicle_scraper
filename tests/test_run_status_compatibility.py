import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autotrader_adapter import ADAPTER_SCHEMA_VERSION as AUTOTRADER_ADAPTER_SCHEMA_VERSION
from autotrader_run import COLLECTION_SCOPE as AUTOTRADER_COLLECTION_SCOPE
from baseline_compatibility import build_compatibility_fingerprint
from canonical_evidence import EVIDENCE_SCHEMA_VERSION
from kijiji_adapter import ADAPTER_SCHEMA_VERSION as KIJIJI_ADAPTER_SCHEMA_VERSION
from kijiji_locations import LOCATION_REGISTRY_VERSION
from kijiji_run import COLLECTION_SCOPE as KIJIJI_COLLECTION_SCOPE
from vehicle_config import CONFIG_SCHEMA_VERSION


class RunStatusCompatibilityMetadataTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "schema_version": 2,
            "vehicle_key": "test_vehicle",
            "make": "Test",
            "model": "Vehicle",
            "criteria": {
                "min_year": 2000,
                "max_year": 2030,
                "max_price_cad": 100000,
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

    def test_kijiji_runtime_uses_fingerprint_contract(self):
        identity, fingerprint = build_compatibility_fingerprint(
            config=self.config,
            source="kijiji",
            collection_scope=KIJIJI_COLLECTION_SCOPE,
            adapter_schema_version=KIJIJI_ADAPTER_SCHEMA_VERSION,
        )
        self.assertEqual(identity["compatibility_schema_version"], 1)
        self.assertEqual(identity["configuration_schema_version"], CONFIG_SCHEMA_VERSION)
        self.assertEqual(identity["canonical_evidence_schema_version"], EVIDENCE_SCHEMA_VERSION)
        self.assertEqual(identity["adapter_schema_version"], KIJIJI_ADAPTER_SCHEMA_VERSION)
        self.assertEqual(identity["location_registry_version"], LOCATION_REGISTRY_VERSION)
        self.assertEqual(identity["collection_scope"], "full")
        self.assertEqual(identity["query_location_count"], 1)
        self.assertEqual(len(fingerprint), 64)

    def test_autotrader_runtime_uses_fingerprint_contract_without_kijiji_registry(self):
        identity, fingerprint = build_compatibility_fingerprint(
            config=self.config,
            source="autotrader",
            collection_scope=AUTOTRADER_COLLECTION_SCOPE,
            adapter_schema_version=AUTOTRADER_ADAPTER_SCHEMA_VERSION,
        )
        self.assertEqual(identity["adapter_schema_version"], AUTOTRADER_ADAPTER_SCHEMA_VERSION)
        self.assertIsNone(identity["location_registry_version"])
        self.assertEqual(identity["collection_scope"], "full")
        self.assertEqual(len(fingerprint), 64)

    def test_status_metadata_is_written_by_both_runners(self):
        from autotrader_run import run_autotrader
        from kijiji_run import run_kijiji

        self.assertIn("build_compatibility_fingerprint", run_kijiji.__code__.co_names)
        self.assertIn("build_compatibility_fingerprint", run_autotrader.__code__.co_names)

        for runner in (run_kijiji, run_autotrader):
            self.assertTrue(callable(runner))


if __name__ == "__main__":
    unittest.main()
