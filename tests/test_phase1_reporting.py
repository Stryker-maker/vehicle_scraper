import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from canonical_evidence import build_canonical_evidence
from identity_lifecycle import (
    IDENTITY_LIFECYCLE_SCHEMA_VERSION,
    update_source_identity_lifecycle,
)
from phase1_pipeline import (
    MANUAL_REVIEW_FIELDS,
    _raise_for_canonical_review_exclusions,
    build_manual_review,
    collect_health,
    expected_output_path,
    source_status_path,
    write_json,
)

FIELDS = [
    "rank", "year", "make", "model", "trim", "trim_tier", "price",
    "price_history", "trend", "weeks_tracked", "price_first_seen",
    "price_last_week", "price_change_week", "price_change_total", "mileage",
    "engine", "fuel", "accident_flag", "days_on_market", "dealer",
    "seller_type", "dealer_address", "location", "distance_km",
    "distance_method", "listing_id", "url_region_hint", "url_region_status",
    "url", "score", "source",
]


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = {
            "vehicle_key": "test_vehicle", "make": "Test", "model": "Vehicle"
        }
        self.config_path = self.root / "config.json"
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def rows(self, source: str, count: int):
        output = expected_output_path(self.root, self.config, source)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            for index in range(count):
                row = {field: "" for field in FIELDS}
                row.update({
                    "rank": str(index + 1), "year": "2020", "make": "Test",
                    "model": "Vehicle", "trim": f"Trim {index}",
                    "price": str(25000 + index * 5000),
                    "mileage": str(100000 + index * 5000),
                    "dealer": f"{source} seller",
                    "dealer_address": "Example, AB", "location": "Example, AB",
                    "distance_km": "100", "distance_method": "address",
                    "listing_id": f"{source}-{index}",
                    "url": f"https://www.kijiji.ca/v-cars-trucks/calgary/2020-{source}-{index}",
                    "url_region_hint": "calgary",
                    "url_region_status": "unverified_url_evidence",
                    "score": ".2",
                    "source": "AutoTrader" if source == "autotrader" else "Kijiji",
                })
                writer.writerow(row)
        return output

    def success(self, source: str, count: int = 1):
        output = self.rows(source, count)
        evidence = build_canonical_evidence(
            root=self.root, config=self.config, source=source,
            csv_path=output, run_id="run-1",
            completed_at_utc="2026-07-22T00:00:00+00:00",
        )
        identity = update_source_identity_lifecycle(
            root=self.root, config=self.config, source=source,
            run_id="run-1", observed_at_utc="2026-07-22T00:00:00+00:00",
            accepted_artifact=evidence["artifacts"]["accepted"],
            adapter_records_artifact=None,
        )
        status = {
            "schema_version": 8,
            "canonical_evidence_schema_version": 1,
            "identity_lifecycle_schema_version": IDENTITY_LIFECYCLE_SCHEMA_VERSION,
            "identity_lifecycle_status": "updated",
            "run_id": "run-1", "vehicle_key": "test_vehicle", "source": source,
            "execution_status": "success", "collection_status": "success",
            "completed_at_utc": "2026-07-22T00:00:00+00:00",
            "output_updated_this_run": True, "schema_valid": True,
            "row_count": count, "current_row_count": count, "stale_row_count": 0,
            "row_cap_disabled": True, "config_isolated": True,
            "fetched_record_count": evidence["fetched_records"],
            "accepted_record_count": evidence["accepted_records"],
            "rejected_record_count": evidence["rejected_records"],
            "parse_failure_count": evidence["parse_failures"],
            "evidence_reconciliation_status": "reconciled",
            "canonical_evidence_artifacts": evidence["artifacts"],
            "identity_lifecycle_artifacts": identity["artifacts"],
            "identity_observed_current_count": identity["observed_current_count"],
            "identity_tracked_listing_count": identity["tracked_listing_count"],
            "identity_new_listing_count": identity["new_listing_count"],
            "identity_reappeared_listing_count": identity["reappeared_listing_count"],
            "identity_missing_listing_count": identity["missing_listing_count"],
            "identity_retired_listing_count": identity["retired_listing_count"],
            "data_quality_status": "warnings_present" if source == "kijiji" else "clean",
            "quality_warning_rows": count if source == "kijiji" else 0,
            "quality_warning_count": count if source == "kijiji" else 0,
            "quality_warning_summary": {"kijiji_location_unknown": count} if source == "kijiji" else {},
            "failure_reasons": [],
            "expected_output": str(output.relative_to(self.root)),
        }
        write_json(source_status_path(self.root, self.config, source), status)

    def test_manual_review_keeps_200_and_uses_identity_fields(self):
        self.success("autotrader", 120)
        self.success("kijiji", 80)
        summary = build_manual_review(
            root=self.root, config_paths=[self.config_path], run_id="run-1"
        )
        result = summary["vehicles"][0]
        self.assertEqual(result["row_count"], 200)
        with (self.root / result["latest_output"]).open(newline="") as handle:
            reader = csv.DictReader(handle); rows = list(reader)
        self.assertEqual(reader.fieldnames, MANUAL_REVIEW_FIELDS)
        for field in ("rank", "score", "weeks_tracked", "source_price_history_text", "legacy_trend_text"):
            self.assertNotIn(field, reader.fieldnames)
        for field in (
            "vin_evidence_status", "lifecycle_state", "first_seen_at_utc",
            "elapsed_since_first_seen_days", "observation_count",
            "price_observation_count", "duplicate_candidate_count",
        ):
            self.assertIn(field, reader.fieldnames)
        self.assertTrue(all(row["canonical_listing_id"] for row in rows))
        self.assertTrue(all(row["lifecycle_state"] == "active" for row in rows))
        self.assertTrue(all(row["observation_count"] == "1" for row in rows))
        self.assertTrue(
            all(
                row["identity_lifecycle_schema_version"]
                == str(IDENTITY_LIFECYCLE_SCHEMA_VERSION)
                for row in rows
            )
        )
        kijiji = next(row for row in rows if row["source"] == "kijiji")
        self.assertEqual(kijiji["location"], "")
        self.assertEqual(kijiji["distance_km"], "")
        self.assertEqual(kijiji["unverified_location_value"], "Example, AB")
        self.assertEqual(kijiji["vin_evidence_status"], "not_reported")

    def test_degraded_source_is_excluded_and_reports_stale_rows(self):
        self.success("autotrader")
        self.rows("kijiji", 1)
        write_json(source_status_path(self.root, self.config, "kijiji"), {
            "run_id": "run-1", "execution_status": "degraded",
            "collection_status": "degraded", "output_updated_this_run": False,
            "schema_valid": True, "row_count": 0, "current_row_count": 0,
            "stale_row_count": 1, "row_cap_disabled": True, "config_isolated": True,
            "canonical_evidence_schema_version": 1,
            "identity_lifecycle_schema_version": IDENTITY_LIFECYCLE_SCHEMA_VERSION,
            "identity_lifecycle_status": "not_updated",
            "accepted_record_count": 0, "rejected_record_count": 0,
            "parse_failure_count": 0, "fetched_record_count": 0,
            "evidence_reconciliation_status": "not_reconciled",
            "data_quality_status": "not_evaluated_stale_output",
            "quality_warning_rows": 0, "quality_warning_count": 0,
            "failure_reasons": ["no_fresh_output"],
        })
        result = build_manual_review(
            root=self.root, config_paths=[self.config_path], run_id="run-1"
        )["vehicles"][0]
        self.assertEqual(result["included_sources"], ["autotrader"])
        self.assertEqual(result["row_count"], 1)
        report = collect_health(
            root=self.root, config_paths=[self.config_path], run_id="run-1"
        )
        stale = next(value for value in report["sources"] if value["source"] == "kijiji")
        self.assertEqual(stale["current_row_count"], 0)
        self.assertEqual(stale["stale_row_count"], 1)
        self.assertEqual(stale["identity_lifecycle_status"], "not_updated")

    def test_quality_warnings_do_not_fail_collection(self):
        self.success("autotrader"); self.success("kijiji")
        report = collect_health(
            root=self.root, config_paths=[self.config_path], run_id="run-1"
        )
        self.assertEqual(report["schema_version"], 6)
        self.assertEqual(report["overall_status"], "success_with_warnings")
        self.assertEqual(report["healthy_source_runs"], 2)
        self.assertEqual(report["identity_tracked_listing_count"], 2)
        self.assertEqual(report["identity_new_listing_count"], 2)

    def test_identity_run_mismatch_excludes_source_and_cli_guard_fails(self):
        self.success("autotrader")
        identity_path = self.root / "data/test_vehicle/identity_lifecycle/autotrader/current_latest.jsonl"
        line = json.loads(identity_path.read_text().splitlines()[0])
        line["run_id"] = "other-run"
        identity_path.write_text(json.dumps(line) + "\n")
        summary = build_manual_review(
            root=self.root, config_paths=[self.config_path], run_id="run-1"
        )
        result = summary["vehicles"][0]
        self.assertEqual(result["included_sources"], [])
        self.assertIn("Identity lifecycle current artifact mismatch", result["excluded_sources"]["autotrader"])
        with self.assertRaisesRegex(RuntimeError, "Canonical evidence integrity"):
            _raise_for_canonical_review_exclusions(summary)


if __name__ == "__main__":
    unittest.main()
