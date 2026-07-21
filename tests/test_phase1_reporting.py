import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from phase1_pipeline import (
    MANUAL_REVIEW_FIELDS, build_manual_review, collect_health,
    expected_output_path, source_status_path, write_json,
)

FIELDS=["rank","year","make","model","trim","trim_tier","price","price_history","trend","weeks_tracked","price_first_seen","price_last_week","price_change_week","price_change_total","mileage","engine","fuel","accident_flag","days_on_market","dealer","seller_type","dealer_address","location","distance_km","distance_method","listing_id","url","score","source"]


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = {"vehicle_key":"test_vehicle","make":"Test","model":"Vehicle"}
        self.config_path = self.root / "config.json"
        self.config_path.write_text(json.dumps(self.config))

    def tearDown(self):
        self.temp.cleanup()

    def rows(self, source, count):
        output = expected_output_path(self.root, self.config, source)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            for index in range(count):
                row = {field:"" for field in FIELDS}
                row.update({
                    "rank":str(index+1), "year":"2020", "make":"Test",
                    "model":"Vehicle", "price":"25000", "mileage":"100000",
                    "dealer_address":"Example, AB", "location":"Example, AB",
                    "distance_km":"100", "distance_method":"address",
                    "listing_id":f"{source}-{index}", "url":f"https://x/2020-{index}",
                    "score":".2", "source":"AutoTrader" if source=="autotrader" else "Kijiji",
                })
                writer.writerow(row)
        return output

    def success(self, source, count=1):
        output = self.rows(source, count)
        status = {
            "run_id":"run-1", "vehicle_key":"test_vehicle", "source":source,
            "execution_status":"success", "collection_status":"success",
            "completed_at_utc":"now", "output_updated_this_run":True,
            "schema_valid":True, "row_count":count, "row_cap_disabled":True,
            "config_isolated":True,
            "data_quality_status":"warnings_present" if source=="kijiji" else "clean",
            "quality_warning_rows":count if source=="kijiji" else 0,
            "quality_warning_count":count if source=="kijiji" else 0,
            "quality_warning_summary":{"unverified_kijiji_location":count} if source=="kijiji" else {},
            "failure_reasons":[], "expected_output":str(output.relative_to(self.root)),
        }
        write_json(source_status_path(self.root, self.config, source), status)

    def test_manual_review_keeps_200_and_removes_ranking(self):
        self.success("autotrader", 120)
        self.success("kijiji", 80)
        summary = build_manual_review(
            root=self.root, config_paths=[self.config_path], run_id="run-1"
        )
        self.assertEqual(summary["vehicles"][0]["row_count"], 200)
        with (self.root / summary["vehicles"][0]["latest_output"]).open(newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
        self.assertEqual(reader.fieldnames, MANUAL_REVIEW_FIELDS)
        self.assertNotIn("rank", reader.fieldnames)
        self.assertNotIn("score", reader.fieldnames)
        kijiji = next(row for row in rows if row["source"] == "Kijiji")
        self.assertEqual(kijiji["location"], "")
        self.assertEqual(kijiji["distance_km"], "")
        self.assertEqual(kijiji["unverified_location_value"], "Example, AB")

    def test_degraded_source_is_excluded(self):
        self.success("autotrader")
        self.rows("kijiji", 1)
        write_json(source_status_path(self.root, self.config, "kijiji"), {
            "run_id":"run-1", "execution_status":"degraded",
            "output_updated_this_run":False, "schema_valid":True, "row_count":1,
            "row_cap_disabled":True, "config_isolated":True,
            "failure_reasons":["no_fresh_output"],
        })
        result = build_manual_review(
            root=self.root, config_paths=[self.config_path], run_id="run-1"
        )["vehicles"][0]
        self.assertEqual(result["included_sources"], ["autotrader"])
        self.assertEqual(result["row_count"], 1)

    def test_missing_source_degrades_health(self):
        self.success("autotrader")
        report = collect_health(
            root=self.root, config_paths=[self.config_path], run_id="run-1"
        )
        self.assertEqual(report["overall_status"], "degraded")
        self.assertEqual(report["unhealthy_source_runs"], 1)

    def test_quality_warnings_do_not_fail_collection(self):
        self.success("autotrader")
        self.success("kijiji")
        report = collect_health(
            root=self.root, config_paths=[self.config_path], run_id="run-1"
        )
        self.assertEqual(report["overall_status"], "success_with_warnings")
        self.assertEqual(report["healthy_source_runs"], 2)


if __name__ == "__main__":
    unittest.main()
