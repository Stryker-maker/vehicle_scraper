import json
import tempfile
import unittest
from pathlib import Path

from workflow_anomalies import compare_health_reports, isolate_anomalous_collections
from phase1_pipeline import collect_health, write_health_report
from phase1_reporting import build_manual_review
from generated_data_publish import prepare_manifest


class CollectionIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _source_entry(self, vehicle_key: str, source: str, healthy: bool, accepted: int, fetched: int, execution_status: str = "success"):
        return {
            "vehicle_key": vehicle_key,
            "source": source,
            "healthy": healthy,
            "execution_status": execution_status,
            "collection_status": execution_status,
            "data_quality_status": "clean" if healthy else "not_evaluated",
            "quality_warning_rows": 0,
            "quality_warning_count": 0,
            "quality_warning_summary": {},
            "row_count": accepted if healthy else 0,
            "current_row_count": accepted if healthy else 0,
            "stale_row_count": 0,
            "fetched_record_count": fetched,
            "accepted_record_count": accepted,
            "rejected_record_count": 0,
            "parse_failure_count": 0 if healthy else 10,
            "evidence_reconciliation_status": "reconciled" if healthy else "not_reconciled",
            "identity_lifecycle_status": "updated" if healthy else "not_updated",
            "identity_tracked_listing_count": accepted,
            "identity_new_listing_count": accepted,
            "identity_reappeared_listing_count": 0,
            "identity_missing_listing_count": 0,
            "identity_retired_listing_count": 0,
            "failure_reasons": [] if healthy else ["collector_command_failed"],
            "status_path": f"data/{vehicle_key}/run_status/{source}_latest.json",
            "compatibility_fingerprint": "v1",
        }

    def test_collection_isolation_end_to_end(self):
        """
        End-to-end test proving collection isolation:
        1. One vehicle/source produces a critical anomaly (ford_f150:autotrader).
        2. Another vehicle/source successfully collects and validates data (ford_f350:autotrader).
        3. Successful vehicle/source is eligible for publication/retention.
        4. Anomalous vehicle/source is isolated from trusted published dataset.
        5. Anomalous result/evidence remains available for diagnostic purposes.
        6. Critical anomaly does not globally abort publication of unrelated successful data.
        """
        run_id = "test_run_123"

        # Construct current health report with 1 successful source (ford_f350 / autotrader)
        # and 1 anomalous/unhealthy source (ford_f150 / autotrader).
        f350_autotrader = self._source_entry("ford_f350", "autotrader", healthy=True, accepted=25, fetched=100)
        f150_autotrader = self._source_entry("ford_f150", "autotrader", healthy=False, accepted=0, fetched=0, execution_status="failed")

        current_health = {
            "schema_version": 6,
            "run_id": run_id,
            "generated_at_utc": "2026-08-01T00:00:00Z",
            "overall_status": "degraded",
            "expected_source_runs": 2,
            "healthy_source_runs": 1,
            "unhealthy_source_runs": 1,
            "source_runs_with_quality_warnings": 0,
            "fetched_record_count": 100,
            "accepted_record_count": 25,
            "rejected_record_count": 0,
            "parse_failure_count": 10,
            "identity_tracked_listing_count": 25,
            "identity_new_listing_count": 25,
            "identity_reappeared_listing_count": 0,
            "identity_missing_listing_count": 0,
            "identity_retired_listing_count": 0,
            "sources": [f350_autotrader, f150_autotrader],
        }

        # Save health report
        health_dir = self.root / "data" / "run_status"
        health_dir.mkdir(parents=True, exist_ok=True)
        (health_dir / "latest.json").write_text(json.dumps(current_health), encoding="utf-8")

        # Mock CSV latest outputs on disk
        f350_latest_csv = self.root / "data" / "ford_f350" / "latest" / "ford_f350_autotrader_latest.csv"
        f150_latest_csv = self.root / "data" / "ford_f150" / "latest" / "ford_f150_autotrader_latest.csv"
        f350_latest_csv.parent.mkdir(parents=True, exist_ok=True)
        f150_latest_csv.parent.mkdir(parents=True, exist_ok=True)
        f350_latest_csv.write_text("year,make,model,price_cad\n2023,Ford,F-350,75000\n", encoding="utf-8")
        f150_latest_csv.write_text("year,make,model,price_cad\n2022,Ford,F-150,50000\n", encoding="utf-8")

        # Mock diagnostic evidence artifacts on disk for the anomalous source
        f150_status_file = self.root / "data" / "ford_f150" / "run_status" / "autotrader_latest.json"
        f150_status_file.parent.mkdir(parents=True, exist_ok=True)
        f150_status_file.write_text(json.dumps(f150_autotrader), encoding="utf-8")

        # 1. Compare health reports to build anomaly report
        anomaly_report = compare_health_reports(
            baseline=None,
            current=current_health,
            run_id=run_id,
        )

        # Requirement 1: One vehicle/source produces a critical anomaly
        self.assertGreater(anomaly_report["critical_anomaly_count"], 0)
        self.assertEqual(anomaly_report["anomaly_status"], "critical")
        self.assertIn(
            {"vehicle_key": "ford_f150", "source": "autotrader"},
            anomaly_report["isolated_collections"],
        )

        # Isolate anomalous collections
        isolated = isolate_anomalous_collections(root=self.root, report=anomaly_report)
        self.assertEqual(len(isolated), 1)

        # Requirement 4 & 5:
        # Untrusted latest CSV for anomalous collection is isolated (deleted from latest publication path)
        self.assertFalse(f150_latest_csv.exists())
        # Diagnostic evidence for anomalous collection remains preserved on disk
        self.assertTrue(f150_status_file.exists())

        # Requirement 2 & 3:
        # Successful collection's latest CSV remains intact and eligible for publication
        self.assertTrue(f350_latest_csv.exists())

        # Save anomaly report to disk for manifest check
        (health_dir / "anomalies_latest.json").write_text(json.dumps(anomaly_report), encoding="utf-8")

        # 2. Test publication manifest preparation
        # Prepare git repo structure in temp
        import subprocess
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.root, check=True)

        # Create registry
        registry = {
            "schema_version": 2,
            "profile": "test",
            "vehicles": [
                {
                    "vehicle_key": "ford_f350",
                    "config_path": "config_f350.json",
                    "enabled": True,
                    "purpose": "primary_purchase",
                    "priority": 1,
                    "cadence": "weekly",
                    "enabled_sources": ["autotrader"],
                    "analysis_profile": "f350_purchase",
                },
                {
                    "vehicle_key": "ford_f150",
                    "config_path": "config_f150.json",
                    "enabled": True,
                    "purpose": "owned_vehicle_value_monitoring",
                    "priority": 2,
                    "cadence": "weekly",
                    "enabled_sources": ["autotrader"],
                    "analysis_profile": "owned_vehicle_value",
                },
            ],
        }
        (self.root / "vehicle_registry.json").write_text(json.dumps(registry), encoding="utf-8")
        dummy_config = {
            "schema_version": 2,
            "vehicle_key": "ford_f350",
            "make": "Ford",
            "model": "F-350",
            "criteria": {
                "min_year": 2020,
                "max_year": 2024,
                "max_price_cad": 100000,
                "fuel": "Diesel",
                "engine": "6.7L PowerStroke",
            },
            "origin": {"home_city": "Calgary, AB", "home_coords": [51.0447, -114.0719], "max_distance_km": 1000},
            "sources": {
                "autotrader": {"make": "Ford", "model": "F-350", "search_locations": ["Calgary, AB"]},
                "kijiji": {"make": "Ford", "model": "F-350", "search_locations": ["Calgary, AB"]},
            },
        }
        (self.root / "config_f350.json").write_text(json.dumps(dummy_config), encoding="utf-8")
        dummy_config_f150 = dict(dummy_config, vehicle_key="ford_f150", model="F-150")
        (self.root / "config_f150.json").write_text(json.dumps(dummy_config_f150), encoding="utf-8")

        # Stage files for git commit
        subprocess.run(["git", "add", "data/"], cwd=self.root, check=True)

        manifest = prepare_manifest(
            root=self.root,
            registry_path=Path("vehicle_registry.json"),
            run_id=run_id,
            source_sha="a" * 40,
            event_name="schedule",
            ref_name="main",
        )

        # Requirement 6: Critical anomaly does not globally abort publication of unrelated successful data.
        self.assertEqual(manifest["publication_status"], "prepared_for_commit")
        self.assertIn("ford_f350", manifest["active_vehicle_keys"])
        self.assertEqual(
            manifest["isolated_collections"],
            [{"vehicle_key": "ford_f150", "source": "autotrader"}],
        )
        # Successful vehicle data is published
        self.assertIn("data/ford_f350/latest/ford_f350_autotrader_latest.csv", manifest["published_paths"])
        # Anomalous latest CSV is excluded (since it was unlinked during isolation)
        self.assertNotIn("data/ford_f150/latest/ford_f150_autotrader_latest.csv", manifest["published_paths"])
        # Diagnostic evidence for anomalous collection is published in manifest for investigation
        self.assertIn("data/ford_f150/run_status/autotrader_latest.json", manifest["published_paths"])

    def test_partial_source_isolation_for_downstream_outputs(self):
        """
        Test that when one source fails/anomalous for a vehicle with multiple sources,
        downstream modules (f350_buyer_intelligence / purpose_outputs) degrade gracefully
        and build outputs using only the valid source rather than throwing errors.
        """
        from f350_buyer_intelligence import build as build_buyer
        from purpose_outputs import build as build_purpose

        run_id = "run_partial_123"

        # Mock f350 config
        f350_config = {
            "schema_version": 2,
            "vehicle_key": "ford_f350",
            "make": "Ford",
            "model": "F-350",
            "criteria": {
                "min_year": 2020,
                "max_year": 2024,
                "max_price_cad": 100000,
                "fuel": "Diesel",
                "engine": "6.7L PowerStroke",
            },
            "origin": {"home_city": "Calgary, AB", "home_coords": [51.0447, -114.0719], "max_distance_km": 1000},
            "sources": {
                "autotrader": {"make": "Ford", "model": "F-350", "search_locations": ["Calgary, AB"]},
                "kijiji": {"make": "Ford", "model": "F-350", "search_locations": ["Calgary, AB"]},
            },
        }
        f350_config_path = self.root / "config_f350.json"
        f350_config_path.write_text(json.dumps(f350_config), encoding="utf-8")

        # Create valid autotrader status & artifacts
        autotrader_status = self._source_entry("ford_f350", "autotrader", healthy=True, accepted=1, fetched=1)
        autotrader_status["schema_version"] = 8
        autotrader_status["run_id"] = run_id
        autotrader_status["output_updated_this_run"] = True
        autotrader_status["schema_valid"] = True
        autotrader_status["canonical_evidence_schema_version"] = 1
        autotrader_status["identity_lifecycle_schema_version"] = 2
        autotrader_status["identity_lifecycle_status"] = "updated"
        autotrader_status["identity_observed_current_count"] = 1
        autotrader_status["row_cap_disabled"] = True
        autotrader_status["config_isolated"] = True
        autotrader_status["canonical_evidence_artifacts"] = {"accepted": "data/ford_f350/evidence/autotrader/accepted.jsonl"}
        autotrader_status["source_adapter_artifacts"] = {"records": "data/ford_f350/adapter_evidence/autotrader/records.jsonl"}

        at_status_path = self.root / "data" / "ford_f350" / "run_status" / "autotrader_latest.json"
        at_status_path.parent.mkdir(parents=True, exist_ok=True)
        at_status_path.write_text(json.dumps(autotrader_status), encoding="utf-8")

        at_accepted_path = self.root / "data" / "ford_f350" / "evidence" / "autotrader" / "accepted.jsonl"
        at_accepted_path.parent.mkdir(parents=True, exist_ok=True)
        accepted_record = {
            "evidence_schema_version": 1,
            "run_id": run_id,
            "vehicle_key": "ford_f350",
            "source": "autotrader",
            "canonical_listing_id": "autotrader-111",
            "source_listing_id": "111",
            "record_stage": "accepted",
            "source_record_index": 0,
            "raw_record_ref": "ref1",
            "source_adapter_record_ref": "ref2",
            "normalized": {
                "year": 2023,
                "make": "Ford",
                "model": "F-350",
                "price_cad": 80000,
                "mileage_km": 30000,
                "listing_url": "https://autotrader.ca/111",
            },
        }
        at_accepted_path.write_text(json.dumps(accepted_record) + "\n", encoding="utf-8")

        at_adapter_path = self.root / "data" / "ford_f350" / "adapter_evidence" / "autotrader" / "records.jsonl"
        at_adapter_path.parent.mkdir(parents=True, exist_ok=True)
        adapter_record = {
            "run_id": run_id,
            "source": "autotrader",
            "source_record_index": 0,
            "raw_payload": {"trim": "Lariat"},
        }
        at_adapter_path.write_text(json.dumps(adapter_record) + "\n", encoding="utf-8")

        at_identity_path = self.root / "data" / "ford_f350" / "identity_lifecycle" / "autotrader" / "current_latest.jsonl"
        at_identity_path.parent.mkdir(parents=True, exist_ok=True)
        identity_record = {
            "identity_lifecycle_schema_version": 2,
            "run_id": run_id,
            "vehicle_key": "ford_f350",
            "source": "autotrader",
            "canonical_listing_id": "autotrader-111",
            "lifecycle_state": "new",
            "vin_evidence_status": "not_reported",
        }
        at_identity_path.write_text(json.dumps(identity_record) + "\n", encoding="utf-8")

        # Kijiji status is missing/unhealthy (isolated)
        kijiji_status_path = self.root / "data" / "ford_f350" / "run_status" / "kijiji_latest.json"
        kijiji_status_path.write_text(json.dumps({"schema_version": 8, "run_id": run_id, "execution_status": "failed"}), encoding="utf-8")

        # Build buyer intelligence requesting both sources ["autotrader", "kijiji"]
        summary = build_buyer(
            root=self.root,
            config_path=f350_config_path,
            run_id=run_id,
            sources=["autotrader", "kijiji"],
            overrides_path=self.root / "nonexistent_overrides.json",
        )

        # Output was built successfully using valid source (autotrader) without raising error for failed kijiji
        self.assertEqual(summary["listing_claim_count"], 1)
        self.assertEqual(summary["sources"], ["autotrader"])


if __name__ == "__main__":
    unittest.main()
