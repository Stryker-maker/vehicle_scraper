import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from phase1_kijiji_runner import (
    extract_url_region_hint, patch_legacy_source, phase1_filter_kijiji_listings,
    phase1_order_kijiji_results, phase1_prepare_kijiji_listings,
)


class KijijiRunnerTests(unittest.TestCase):
    def test_extracts_unverified_url_region_hint(self):
        self.assertEqual(
            extract_url_region_hint("https://www.kijiji.ca/v-cars-trucks/mississauga-peel-region/vehicle/123"),
            "mississauga-peel-region",
        )
        self.assertEqual(extract_url_region_hint("https://example.invalid/no-region"), "")

    def test_3000_records_survive_without_distance_filter_or_score(self):
        records = [
            {
                "year": 2020, "price": 25000, "fuel": "Gas", "engine": "2.5L",
                "mileage": 100000 + index, "distance_km": 9999,
                "listing_id": str(index),
                "url": f"https://www.kijiji.ca/v-cars-trucks/calgary/vehicle/{index}",
            }
            for index in range(3000)
        ]
        prepared = phase1_prepare_kijiji_listings(records)
        filtered = phase1_filter_kijiji_listings(
            prepared, min_year=2019, max_year=2021, max_price=30000, fuel="Gas",
        )
        ordered = phase1_order_kijiji_results(filtered)
        self.assertEqual(len(ordered), 3000)
        self.assertTrue(all(row["distance_km"] == "" for row in ordered))
        self.assertTrue(all(row["distance_method"] == "disabled_unverified_location" for row in ordered))
        self.assertTrue(all(row["score"] == "" for row in ordered))
        self.assertTrue(all(row["url_region_status"] == "unverified_url_evidence" for row in ordered))

    def test_patch_bypasses_all_legacy_location_and_ranking_calls(self):
        source = '''
    listings = resolve_all_distances(listings)
    matches = filter_listings(listings)
        ranked = rank_listings(matches)
        display_results(ranked)
    update_locations(matches)
        "listing_id", "url", "score", "source"
'''
        patched = patch_legacy_source(source)
        self.assertNotIn("listings = resolve_all_distances(listings)", patched)
        self.assertNotIn("matches = filter_listings(listings)", patched)
        self.assertNotIn("ranked = rank_listings(matches)", patched)
        self.assertNotIn("display_results(ranked)", patched)
        self.assertNotIn("update_locations(matches)", patched)
        self.assertIn("phase1_prepare_kijiji_listings", patched)
        self.assertIn("phase1_filter_kijiji_listings", patched)
        self.assertIn("url_region_hint", patched)


if __name__ == "__main__":
    unittest.main()
