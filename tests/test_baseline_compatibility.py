import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from baseline_compatibility import (
    COMPATIBILITY_SCHEMA_VERSION,
    build_compatibility_fingerprint,
    build_compatibility_identity,
    compatibility_fingerprint,
)


class BaselineCompatibilityFingerprintTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "schema_version": 2,
            "vehicle_key": "subaru_forester",
            "make": "Subaru",
            "model": "Forester",
            "criteria": {
                "min_year": 2019,
                "max_year": 2024,
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
                    "make": "subaru",
                    "model": "forester",
                    "search_locations": [
                        "Edmonton, AB",
                        "Calgary, AB",
                        "Saskatoon, SK",
                        "Regina, SK",
                    ],
                },
                "kijiji": {
                    "make": "Subaru",
                    "model": "Forester",
                    "search_locations": [
                        "Edmonton, AB",
                        "Calgary, AB",
                        "Saskatoon, SK",
                        "Regina, SK",
                    ],
                },
            },
        }

    def test_identity_contains_contract_fields(self):
        identity = build_compatibility_identity(
            config=self.config,
            source="kijiji",
            collection_scope="full",
            adapter_schema_version=1,
        )
        self.assertEqual(identity["compatibility_schema_version"], COMPATIBILITY_SCHEMA_VERSION)
        self.assertEqual(identity["vehicle"], "subaru_forester")
        self.assertEqual(identity["source"], "kijiji")
        self.assertEqual(identity["collection_scope"], "full")
        self.assertEqual(identity["query_location_count"], 4)
        self.assertEqual(identity["location_registry_version"], 1)
        self.assertEqual(identity["adapter_schema_version"], 1)
        self.assertEqual(identity["canonical_evidence_schema_version"], 1)
        self.assertEqual(identity["configuration_schema_version"], 2)

    def test_location_order_does_not_change_fingerprint(self):
        _, first = build_compatibility_fingerprint(
            config=self.config,
            source="kijiji",
            collection_scope="full",
            adapter_schema_version=1,
        )
        reordered = copy.deepcopy(self.config)
        reordered["sources"]["kijiji"]["search_locations"] = list(
            reversed(reordered["sources"]["kijiji"]["search_locations"])
        )
        _, second = build_compatibility_fingerprint(
            config=reordered,
            source="kijiji",
            collection_scope="full",
            adapter_schema_version=1,
        )
        self.assertEqual(first, second)

    def test_adding_a_location_changes_fingerprint(self):
        _, baseline = build_compatibility_fingerprint(
            config=self.config,
            source="kijiji",
            collection_scope="full",
            adapter_schema_version=1,
        )
        changed = copy.deepcopy(self.config)
        changed["sources"]["kijiji"]["search_locations"].append("Kelowna, BC")
        _, current = build_compatibility_fingerprint(
            config=changed,
            source="kijiji",
            collection_scope="full",
            adapter_schema_version=1,
        )
        self.assertNotEqual(baseline, current)

    def test_removing_a_location_changes_fingerprint(self):
        _, baseline = build_compatibility_fingerprint(
            config=self.config,
            source="kijiji",
            collection_scope="full",
            adapter_schema_version=1,
        )
        changed = copy.deepcopy(self.config)
        changed["sources"]["kijiji"]["search_locations"] = changed["sources"]["kijiji"]["search_locations"][:-1]
        _, current = build_compatibility_fingerprint(
            config=changed,
            source="kijiji",
            collection_scope="full",
            adapter_schema_version=1,
        )
        self.assertNotEqual(baseline, current)

    def test_population_affecting_configuration_changes_fingerprint(self):
        _, baseline = build_compatibility_fingerprint(
            config=self.config,
            source="kijiji",
            collection_scope="full",
            adapter_schema_version=1,
        )
        changed = copy.deepcopy(self.config)
        changed["criteria"]["max_price_cad"] = 65000
        _, current = build_compatibility_fingerprint(
            config=changed,
            source="kijiji",
            collection_scope="full",
            adapter_schema_version=1,
        )
        self.assertNotEqual(baseline, current)

    def test_scope_and_versions_change_fingerprint(self):
        _, baseline = build_compatibility_fingerprint(
            config=self.config,
            source="kijiji",
            collection_scope="full",
            adapter_schema_version=1,
        )
        _, single_pair = build_compatibility_fingerprint(
            config=self.config,
            source="kijiji",
            collection_scope="single_pair",
            adapter_schema_version=1,
        )
        self.assertNotEqual(baseline, single_pair)
        identity = build_compatibility_identity(
            config=self.config,
            source="kijiji",
            collection_scope="full",
            adapter_schema_version=1,
        )
        changed_version = copy.deepcopy(identity)
        changed_version["adapter_schema_version"] = 2
        self.assertNotEqual(
            compatibility_fingerprint(identity),
            compatibility_fingerprint(changed_version),
        )

    def test_autotrader_does_not_depend_on_kijiji_registry_version(self):
        identity = build_compatibility_identity(
            config=self.config,
            source="autotrader",
            collection_scope="full",
            adapter_schema_version=1,
        )
        self.assertIsNone(identity["location_registry_version"])

    def test_unsupported_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported source"):
            build_compatibility_identity(
                config=self.config,
                source="unknown",
                collection_scope="full",
                adapter_schema_version=1,
            )


if __name__ == "__main__":
    unittest.main()
