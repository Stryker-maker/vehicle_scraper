import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from canonical_evidence import (
    build_canonical_evidence, canonical_artifact_paths, read_jsonl,
)


class CanonicalEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = {"vehicle_key": "test_vehicle"}

    def tearDown(self):
        self.temp.cleanup()

    def output(self, source="autotrader"):
        path = (
            self.root / "data" / "test_vehicle" / "latest" /
            f"test_vehicle_{source}_latest.csv"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def test_reconciles_accepted_rejected_and_parse_failure(self):
        path = self.output()
        fields = [
            "listing_id", "url", "source", "year", "price", "mileage",
            "location", "distance_km",
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(fields)
            writer.writerow([
                "accepted-1", "https://example.invalid/2020", "AutoTrader",
                "2020", "$25,000", "999999", "Calgary, AB", "100",
            ])
            writer.writerow([
                "", "https://example.invalid/2021", "AutoTrader",
                "2021", "30000", "Unknown", "Edmonton, AB", "200",
            ])
            writer.writerow([
                "broken", "https://example.invalid/broken", "AutoTrader",
                "2022", "35000", "80000", "Red Deer, AB", "5", "EXTRA",
            ])
        result = build_canonical_evidence(
            root=self.root, config=self.config, source="autotrader",
            csv_path=path, run_id="run-1",
        )
        self.assertTrue(result["reconciled"])
        self.assertEqual(result["fetched_records"], 3)
        self.assertEqual(result["accepted_records"], 1)
        self.assertEqual(result["rejected_records"], 1)
        self.assertEqual(result["parse_failures"], 1)
        self.assertEqual(
            result["fetched_records"],
            result["accepted_records"] + result["rejected_records"] + result["parse_failures"],
        )

        paths = canonical_artifact_paths(self.root, self.config, "autotrader")
        raw = read_jsonl(paths["raw"])
        accepted = read_jsonl(paths["accepted"])
        rejected = read_jsonl(paths["rejected"])
        failures = read_jsonl(paths["parse_failures"])
        self.assertEqual(len(raw), 3)
        self.assertEqual(accepted[0]["normalized"]["mileage_km"], None)
        self.assertEqual(
            accepted[0]["field_evidence"]["mileage_km"]["raw_value"], "999999"
        )
        self.assertEqual(rejected[0]["rejection_reasons"], ["missing_source_listing_id"])
        self.assertEqual(failures[0]["parse_failure_reasons"], ["malformed_column_count"])

    def test_listing_id_is_stable_and_observation_id_is_run_specific(self):
        path = self.output()
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "listing_id", "url", "source", "price", "mileage",
                "location", "distance_km",
            ])
            writer.writeheader()
            writer.writerow({
                "listing_id": "same", "url": "https://example.invalid/same",
                "source": "AutoTrader", "price": "1", "mileage": "2",
                "location": "Calgary, AB", "distance_km": "3",
            })
        first = build_canonical_evidence(
            root=self.root, config=self.config, source="autotrader",
            csv_path=path, run_id="run-1",
        )
        first_record = read_jsonl(self.root / first["artifacts"]["accepted"])[0]
        second = build_canonical_evidence(
            root=self.root, config=self.config, source="autotrader",
            csv_path=path, run_id="run-2",
        )
        second_record = read_jsonl(self.root / second["artifacts"]["accepted"])[0]
        self.assertEqual(
            first_record["canonical_listing_id"], second_record["canonical_listing_id"]
        )
        self.assertNotEqual(first_record["observation_id"], second_record["observation_id"])
        self.assertEqual(
            first_record["source_listing_id_status"], "source_identifier_claim_not_vin"
        )

    def test_kijiji_location_is_preserved_raw_but_quarantined(self):
        path = self.output("kijiji")
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "listing_id", "url", "source", "price", "mileage",
                "location", "distance_km", "dealer_address",
            ])
            writer.writeheader()
            writer.writerow({
                "listing_id": "k1", "url": "https://www.kijiji.ca/v/x/1",
                "source": "Kijiji", "price": "1", "mileage": "2",
                "location": "Search Origin, AB", "distance_km": "999",
                "dealer_address": "Search Origin, AB",
            })
        result = build_canonical_evidence(
            root=self.root, config=self.config, source="kijiji",
            csv_path=path, run_id="run-1",
        )
        record = read_jsonl(self.root / result["artifacts"]["accepted"])[0]
        self.assertIsNone(record["normalized"]["location"])
        self.assertIsNone(record["normalized"]["distance_km"])
        self.assertEqual(
            record["field_evidence"]["location"]["raw_value"], "Search Origin, AB"
        )
        self.assertEqual(
            record["field_evidence"]["location"]["evidence_status"],
            "quarantined_unverified_search_origin",
        )


if __name__ == "__main__":
    unittest.main()
