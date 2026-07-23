import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autotrader_run import run_autotrader
from identity_lifecycle import artifact_paths


class AutoTraderRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
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
                    "search_locations": ["Calgary, AB"],
                },
            },
        }
        self.config_path = self.root / "config.json"
        self.config_path.write_text(
            json.dumps(self.config, indent=2), encoding="utf-8"
        )

    def tearDown(self):
        self.temp.cleanup()

    def fake_adapter(self):
        path = self.root / "fake_adapter.py"
        path.write_text(
            r'''
import argparse
import csv
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--run-id", required=True)
parser.add_argument("--report-run-id")
args = parser.parse_args()
root = Path.cwd()
key = "test_vehicle"
row = {
    "year": "2020", "make": "Test", "model": "Vehicle",
    "trim": "Example", "price": "25000", "mileage": "100000",
    "fuel": "Gas", "dealer": "Example Dealer",
    "dealer_address": "1 Main St, Calgary, AB", "location": "Calgary, AB",
    "distance_km": "150", "distance_method": "geodesic_city_center",
    "distance_evidence_status": "straight_line_estimate_from_source_reported_location",
    "listing_id": "listing-1", "url": "https://example.invalid/listing-1",
    "source": "AutoTrader", "query_location": "Calgary, AB",
    "query_page": "1", "query_offset": "0",
    "request_url": "https://example.invalid/search?rcs=0",
}
latest = root / "data" / key / "latest" / f"{key}_autotrader_latest.csv"
latest.parent.mkdir(parents=True, exist_ok=True)
with latest.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(row))
    writer.writeheader(); writer.writerow(row)
base = root / "data" / key / "adapter_evidence" / "autotrader"
base.mkdir(parents=True, exist_ok=True)
request_path = base / "requests_latest.jsonl"
records_path = base / "records_latest.jsonl"
reconciliation_path = base / "reconciliation_latest.json"
request = {
    "adapter_schema_version": 1, "vehicle_key": key, "source": "autotrader",
    "run_id": args.run_id, "query_location": "Calgary, AB", "query_page": 1,
    "query_offset": 0, "request_url": row["request_url"],
    "attempts": [{"attempt": 1, "http_status": 200, "error": None}],
    "outcome": "success", "listing_count": 1,
    "pagination_stop_reason": "short_page",
}
record = {
    "adapter_schema_version": 1, "vehicle_key": key, "source": "autotrader",
    "run_id": args.run_id, "source_record_index": 0, "record_stage": "accepted",
    "provenance": {"query_location": "Calgary, AB", "query_page": 1,
        "query_offset": 0, "request_url": row["request_url"]},
    "raw_payload": {"id": "listing-1", "vehicle": {"vin": "1FT8W3BT1MED12345"}},
    "parsed_row": row, "rejection_reasons": [], "parse_failure_reasons": [],
}
request_path.write_text(json.dumps(request) + "\n", encoding="utf-8")
records_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
report = {
    "adapter_schema_version": 1, "vehicle_key": key, "source": "autotrader",
    "run_id": args.report_run_id or args.run_id,
    "fetched_record_scope": "autotrader_adapter_response_listing_objects",
    "source_fetch_completeness": "pagination_observed_complete_for_configured_queries",
    "page_request_count": 1, "request_attempt_count": 1,
    "successful_page_count": 1, "failed_page_count": 0,
    "pagination_complete": True, "fetched_records": 1, "parsed_records": 1,
    "accepted_records": 1, "rejected_records": 0, "parse_failures": 0,
    "duplicate_records": 0, "reconciled": True,
    "reconciliation_equation": "fetched_records = accepted_records + rejected_records + parse_failures",
    "artifacts": {"requests": str(request_path.relative_to(root)),
        "records": str(records_path.relative_to(root)),
        "reconciliation": str(reconciliation_path.relative_to(root))},
}
reconciliation_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
''',
            encoding="utf-8",
        )
        return path

    def test_direct_runtime_status_identity_and_config_isolation(self):
        original = self.config_path.read_bytes()
        status = run_autotrader(
            root=self.root,
            config_path=self.config_path,
            command=[sys.executable, str(self.fake_adapter()), "--run-id", "run-1"],
            run_id="run-1",
        )
        self.assertEqual(status["execution_status"], "success")
        self.assertEqual(status["schema_version"], 8)
        self.assertEqual(status["source_adapter_schema_version"], 1)
        self.assertEqual(status["identity_lifecycle_schema_version"], 1)
        self.assertEqual(status["identity_lifecycle_status"], "updated")
        self.assertEqual(status["identity_observed_current_count"], 1)
        self.assertEqual(status["identity_new_listing_count"], 1)
        self.assertEqual(status["fetched_record_count"], 1)
        self.assertEqual(status["accepted_record_count"], 1)
        self.assertEqual(status["evidence_reconciliation_status"], "reconciled")
        self.assertTrue(status["pagination_complete"])
        self.assertFalse(status["legacy_price_history_active"])
        self.assertEqual(self.config_path.read_bytes(), original)
        paths = artifact_paths(self.root, self.config, "autotrader")
        self.assertTrue(paths["state"].exists())
        self.assertTrue(paths["current"].exists())

    def test_adapter_run_mismatch_degrades_without_identity_update(self):
        status = run_autotrader(
            root=self.root,
            config_path=self.config_path,
            command=[
                sys.executable, str(self.fake_adapter()), "--run-id", "run-1",
                "--report-run-id", "other-run",
            ],
            run_id="run-1",
        )
        self.assertEqual(status["execution_status"], "degraded")
        self.assertIn("canonical_evidence_failed", status["failure_reasons"])
        self.assertIn("run_id mismatch", status["canonical_evidence_error"])
        self.assertEqual(status["identity_lifecycle_status"], "not_updated")
        self.assertFalse(
            artifact_paths(self.root, self.config, "autotrader")["state"].exists()
        )


if __name__ == "__main__":
    unittest.main()
