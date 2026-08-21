import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from identity_lifecycle import IDENTITY_LIFECYCLE_SCHEMA_VERSION, artifact_paths
from kijiji_adapter import collect_kijiji
from kijiji_run import run_kijiji
from workflow_anomalies import compare_health_reports


class KijijiResponseStubSession:
    def __init__(self, responses):
        self.responses = list(responses)

    def get(self, url, headers, timeout):
        res = self.responses.pop(0)
        return res


class StubResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


class KijijiRuntimeTests(unittest.TestCase):
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
                    "make": "test", "model": "vehicle",
                    "search_locations": ["Calgary, AB"],
                },
                "kijiji": {
                    "make": "Test", "model": "Vehicle",
                    "search_locations": ["Edmonton, AB"],
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
        path = self.root / "fake_kijiji_adapter.py"
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
root = Path.cwd(); key = "test_vehicle"
row = {
    "year": "2020", "make": "Test", "model": "Vehicle", "trim": "Example",
    "price": "25000", "mileage": "100000", "fuel": "Gas",
    "dealer": "Example Seller", "dealer_address": "",
    "dealer_address_evidence_status": "unknown", "location": "",
    "location_evidence_status": "unknown", "distance_km": "",
    "distance_method": "disabled_listing_location_not_routed",
    "distance_evidence_status": "disabled_no_verified_route",
    "listing_id": "listing-1", "url_region_hint": "calgary",
    "url_region_status": "unverified_url_evidence",
    "url": "https://example.invalid/listing-1", "source": "Kijiji",
    "query_location": "Edmonton, AB", "query_location_id": "1700202",
    "query_page": "1", "request_url": "https://example.invalid/search",
}
latest = root / "data" / key / "latest" / f"{key}_kijiji_latest.csv"
latest.parent.mkdir(parents=True, exist_ok=True)
with latest.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(row)); writer.writeheader(); writer.writerow(row)
base = root / "data" / key / "adapter_evidence" / "kijiji"
base.mkdir(parents=True, exist_ok=True)
request_path = base / "requests_latest.jsonl"
records_path = base / "records_latest.jsonl"
reconciliation_path = base / "reconciliation_latest.json"
request = {
    "adapter_schema_version": 1, "vehicle_key": key, "source": "kijiji",
    "run_id": args.run_id, "query_location": "Edmonton, AB",
    "query_location_id": "1700202", "query_page": 1,
    "request_url": row["request_url"],
    "attempts": [{"attempt": 1, "http_status": 200, "error": None}],
    "page_status": "success", "returned_listing_objects": 1,
    "stop_reason": "short_page",
}
record = {
    "adapter_schema_version": 1, "vehicle_key": key, "source": "kijiji",
    "run_id": args.run_id, "source_record_index": 0, "record_stage": "accepted",
    "provenance": {"query_location": "Edmonton, AB", "query_location_id": "1700202",
        "query_page": 1, "request_url": row["request_url"]},
    "raw_payload": {"sku": "listing-1", "vin": "1FT8W3BT1MED12345"},
    "parsed_row": row, "rejection_reasons": [], "parse_failure_reasons": [],
}
request_path.write_text(json.dumps(request) + "\n", encoding="utf-8")
records_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
report = {
    "adapter_schema_version": 1, "location_registry_version": 1,
    "vehicle_key": key, "source": "kijiji",
    "run_id": args.report_run_id or args.run_id,
    "fetched_record_scope": "kijiji_adapter_json_ld_listing_objects",
    "source_fetch_completeness": "configured_validated_hub_queries_only_not_marketplace_complete",
    "query_location_count": 1, "page_request_count": 1,
    "request_attempt_count": 1, "successful_page_count": 1,
    "failed_page_count": 0, "pagination_complete": True,
    "fetched_records": 1, "accepted_records": 1,
    "rejected_records": 0, "parse_failures": 0,
    "listing_specific_location_records": 0, "unknown_location_records": 1,
    "reconciled": True,
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
        status = run_kijiji(
            root=self.root,
            config_path=self.config_path,
            command=[sys.executable, str(self.fake_adapter()), "--run-id", "run-1"],
            run_id="run-1",
        )
        self.assertEqual(status["execution_status"], "success")
        self.assertEqual(status["schema_version"], 8)
        self.assertEqual(status["source_adapter_schema_version"], 1)
        self.assertEqual(
            status["identity_lifecycle_schema_version"],
            IDENTITY_LIFECYCLE_SCHEMA_VERSION,
        )
        self.assertEqual(status["identity_lifecycle_status"], "updated")
        self.assertEqual(status["identity_observed_current_count"], 1)
        self.assertEqual(status["identity_new_listing_count"], 1)
        self.assertEqual(status["location_registry_version"], 1)
        self.assertEqual(status["unknown_location_record_count"], 1)
        self.assertEqual(status["evidence_reconciliation_status"], "reconciled")
        self.assertTrue(status["distance_processing_disabled"])
        self.assertFalse(status["legacy_price_history_active"])
        self.assertEqual(self.config_path.read_bytes(), original)
        self.assertTrue(
            artifact_paths(self.root, self.config, "kijiji")["state"].exists()
        )

    def test_adapter_run_mismatch_degrades_without_identity_update(self):
        status = run_kijiji(
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
            artifact_paths(self.root, self.config, "kijiji")["state"].exists()
        )

    def test_suspected_block_triggers_pagination_incomplete_and_anomaly(self):
        block_html = "<html><head><title>Access Denied</title></head><body>Captcha</body></html>"
        session = KijijiResponseStubSession([StubResponse(200, block_html)])
        report = collect_kijiji(
            root=self.root,
            config_path=self.config_path,
            run_id="run-block-integration",
            session=session,
            sleep=lambda _s: None,
        )
        self.assertFalse(report["pagination_complete"])
        self.assertEqual(report["failed_page_count"], 1)

        health_report = {
            "run_id": "run-block-integration",
            "sources": [
                {
                    "vehicle_key": "test_vehicle",
                    "source": "kijiji",
                    "healthy": report["pagination_complete"] and report["reconciled"],
                    "execution_status": "degraded",
                    "pagination_complete": report["pagination_complete"],
                    "failed_page_count": report["failed_page_count"],
                    "fetched_record_count": report["fetched_records"],
                    "parse_failure_count": report["parse_failures"],
                    "accepted_record_count": report["accepted_records"],
                    "request_attempt_count": report["request_attempt_count"],
                    "quality_warning_rows": 0,
                }
            ],
        }
        anomalies = compare_health_reports(
            baseline=None, current=health_report, run_id="run-block-integration"
        )
        codes = [item["code"] for item in anomalies["anomalies"]]
        self.assertIn("pagination_incomplete", codes)
        self.assertIn("failed_source_pages", codes)

    def test_legitimate_empty_page_completes_pagination_normally(self):
        empty_html = (
            '<html><head><script id="__NEXT_DATA__" type="application/json">{}</script>'
            '<script type="application/ld+json">{"@type":"ItemList","itemListElement":[]}'
            '</script></head><body></body></html>'
        )
        session = KijijiResponseStubSession([StubResponse(200, empty_html)])
        report = collect_kijiji(
            root=self.root,
            config_path=self.config_path,
            run_id="run-empty-integration",
            session=session,
            sleep=lambda _s: None,
        )
        self.assertTrue(report["pagination_complete"])
        self.assertEqual(report["failed_page_count"], 0)


if __name__ == "__main__":
    unittest.main()
