import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

from phase1_pipeline import (
    MANUAL_REVIEW_FIELDS,
    build_manual_review,
    collect_health,
    expected_output_path,
    run_source,
    source_status_path,
    write_json,
)


CSV_FIELDS = [
    "rank",
    "year",
    "make",
    "model",
    "trim",
    "trim_tier",
    "price",
    "price_history",
    "trend",
    "weeks_tracked",
    "price_first_seen",
    "price_last_week",
    "price_change_week",
    "price_change_total",
    "mileage",
    "engine",
    "fuel",
    "accident_flag",
    "days_on_market",
    "dealer",
    "seller_type",
    "dealer_address",
    "location",
    "distance_km",
    "distance_method",
    "listing_id",
    "url",
    "score",
    "source",
]


class Phase1PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.config_path = self.root / "config_test.json"
        self.config = {
            "vehicle_key": "test_vehicle",
            "make": "Test",
            "model": "Vehicle",
        }
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_csv(self, source: str, location: str = "Example, AB", distance: str = "100"):
        output = expected_output_path(self.root, self.config, source)
        output.parent.mkdir(parents=True, exist_ok=True)
        row = {field: "" for field in CSV_FIELDS}
        row.update(
            {
                "rank": "1",
                "year": "2020",
                "make": "Test",
                "model": "Vehicle",
                "price": "25000",
                "mileage": "100000",
                "dealer_address": location,
                "location": location,
                "distance_km": distance,
                "distance_method": "address",
                "listing_id": f"{source}-1",
                "url": f"https://example.invalid/{source}-1",
                "score": "0.25",
                "source": "AutoTrader" if source == "autotrader" else "Kijiji",
            }
        )
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerow(row)
        return output

    def _success_status(self, source: str, run_id: str = "run-1"):
        output = self._write_csv(source)
        status = {
            "run_id": run_id,
            "vehicle_key": self.config["vehicle_key"],
            "source": source,
            "execution_status": "success",
            "completed_at_utc": "2026-07-21T12:00:00+00:00",
            "output_updated_this_run": True,
            "schema_valid": True,
            "row_count": 1,
            "expected_output": str(output.relative_to(self.root)),
            "failure_reasons": [],
        }
        write_json(source_status_path(self.root, self.config, source), status)
        return status

    def test_run_source_records_fresh_valid_success(self):
        script = """
import csv, json
from pathlib import Path
cfg = json.loads(Path('config_test.json').read_text())
out = Path('data') / cfg['vehicle_key'] / 'latest' / (cfg['vehicle_key'] + '_autotrader_latest.csv')
out.parent.mkdir(parents=True, exist_ok=True)
fields = ['listing_id','url','source','price','mileage','location','distance_km']
with out.open('w', newline='', encoding='utf-8') as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerow({'listing_id':'1','url':'https://example.invalid/1','source':'AutoTrader','price':'1','mileage':'1','location':'A','distance_km':'1'})
"""
        status = run_source(
            root=self.root,
            source="autotrader",
            config_path=self.config_path,
            command=[sys.executable, "-c", script],
            run_id="run-1",
        )
        self.assertEqual(status["execution_status"], "success")
        self.assertTrue(status["output_updated_this_run"])
        self.assertEqual(status["row_count"], 1)
        self.assertEqual(status["failure_reasons"], [])

    def test_run_source_marks_stale_output_degraded_but_does_not_raise(self):
        self._write_csv("autotrader")
        status = run_source(
            root=self.root,
            source="autotrader",
            config_path=self.config_path,
            command=[sys.executable, "-c", "pass"],
            run_id="run-1",
        )
        self.assertEqual(status["execution_status"], "degraded")
        self.assertIn("no_fresh_output", status["failure_reasons"])

    def test_run_source_records_collector_failure(self):
        status = run_source(
            root=self.root,
            source="kijiji",
            config_path=self.config_path,
            command=[sys.executable, "-c", "raise SystemExit(7)"],
            run_id="run-1",
        )
        self.assertEqual(status["execution_status"], "failed")
        self.assertEqual(status["exit_code"], 7)
        self.assertIn("collector_command_failed", status["failure_reasons"])

    def test_manual_review_disables_ranking_and_quarantines_kijiji_location(self):
        self._success_status("autotrader")
        self._success_status("kijiji")
        kijiji_output = expected_output_path(self.root, self.config, "kijiji")
        with kijiji_output.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        rows[0]["location"] = "Search Origin, AB"
        rows[0]["dealer_address"] = "Search Origin, AB"
        rows[0]["distance_km"] = "42"
        with kijiji_output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

        summary = build_manual_review(
            root=self.root,
            config_paths=[self.config_path],
            run_id="run-1",
        )
        self.assertEqual(summary["vehicles"][0]["row_count"], 2)
        marker = self.root / summary["vehicles"][0]["disabled_ranking_marker"]
        self.assertIn("Merged ranking disabled", marker.read_text(encoding="utf-8"))
        latest = self.root / summary["vehicles"][0]["latest_output"]
        with latest.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            self.assertEqual(reader.fieldnames, MANUAL_REVIEW_FIELDS)
            self.assertNotIn("rank", reader.fieldnames)
            self.assertNotIn("score", reader.fieldnames)
            output_rows = list(reader)

        kijiji = next(row for row in output_rows if row["source"] == "Kijiji")
        autotrader = next(row for row in output_rows if row["source"] == "AutoTrader")
        self.assertEqual(kijiji["ranking_status"], "DISABLED_MANUAL_REVIEW_REQUIRED")
        self.assertEqual(kijiji["location"], "")
        self.assertEqual(kijiji["distance_km"], "")
        self.assertEqual(kijiji["unverified_location_value"], "Search Origin, AB")
        self.assertEqual(kijiji["unverified_distance_value"], "42")
        self.assertEqual(autotrader["location"], "Example, AB")
        self.assertEqual(autotrader["distance_km"], "100")

    def test_manual_review_excludes_degraded_or_stale_source(self):
        self._success_status("autotrader")
        self._write_csv("kijiji")
        degraded = {
            "run_id": "run-1",
            "vehicle_key": self.config["vehicle_key"],
            "source": "kijiji",
            "execution_status": "degraded",
            "completed_at_utc": "2026-07-21T12:00:00+00:00",
            "output_updated_this_run": False,
            "schema_valid": True,
            "row_count": 1,
            "failure_reasons": ["no_fresh_output"],
        }
        write_json(source_status_path(self.root, self.config, "kijiji"), degraded)

        summary = build_manual_review(
            root=self.root,
            config_paths=[self.config_path],
            run_id="run-1",
        )
        vehicle = summary["vehicles"][0]
        self.assertEqual(vehicle["included_sources"], ["autotrader"])
        self.assertEqual(vehicle["excluded_sources"]["kijiji"], "degraded")
        self.assertEqual(vehicle["row_count"], 1)

    def test_health_is_degraded_when_expected_status_is_missing(self):
        self._success_status("autotrader")
        report = collect_health(
            root=self.root,
            config_paths=[self.config_path],
            run_id="run-1",
        )
        self.assertEqual(report["overall_status"], "degraded")
        self.assertEqual(report["healthy_source_runs"], 1)
        self.assertEqual(report["unhealthy_source_runs"], 1)

    def test_health_is_success_only_when_all_sources_are_current_and_valid(self):
        self._success_status("autotrader")
        self._success_status("kijiji")
        report = collect_health(
            root=self.root,
            config_paths=[self.config_path],
            run_id="run-1",
        )
        self.assertEqual(report["overall_status"], "success")
        self.assertEqual(report["healthy_source_runs"], 2)
        self.assertEqual(report["unhealthy_source_runs"], 0)


if __name__ == "__main__":
    unittest.main()
