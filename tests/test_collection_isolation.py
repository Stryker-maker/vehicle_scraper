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
        from phase1_common import utc_now
        run_start = utc_now()

        f350_autotrader = self._source_entry("ford_f350", "autotrader", healthy=True, accepted=25, fetched=100)
        f350_autotrader["run_id"] = run_id
        f150_autotrader = self._source_entry("ford_f150", "autotrader", healthy=False, accepted=0, fetched=0, execution_status="failed")
        f150_autotrader["run_id"] = run_id

        current_health = {
            "schema_version": 6,
            "run_id": run_id,
            "generated_at_utc": run_start,
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

        # Mock CSV outputs on disk:
        # For ford_f150 (anomalous in current run):
        # - Two pre-existing trusted historical archives (older mtime)
        # - One newly generated timestamped archive from current run (current mtime)
        # - One latest CSV output
        f150_old_archive_1 = self.root / "data" / "ford_f150" / "autotrader" / "ford_f150_autotrader_2026-07-01_00-00-00.csv"
        f150_old_archive_2 = self.root / "data" / "ford_f150" / "autotrader" / "ford_f150_autotrader_2026-07-08_00-00-00.csv"
        f150_new_archive = self.root / "data" / "ford_f150" / "autotrader" / "ford_f150_autotrader_2026-08-01_00-00-00.csv"
        f150_latest_csv = self.root / "data" / "ford_f150" / "latest" / "ford_f150_autotrader_latest.csv"

        # For ford_f350 (healthy):
        f350_latest_csv = self.root / "data" / "ford_f350" / "latest" / "ford_f350_autotrader_latest.csv"
        f350_archive_csv = self.root / "data" / "ford_f350" / "autotrader" / "ford_f350_autotrader_2026-08-01_00-00-00.csv"

        for p in (f150_old_archive_1, f150_latest_csv, f350_latest_csv, f350_archive_csv):
            p.parent.mkdir(parents=True, exist_ok=True)

        f150_old_archive_1.write_text("year,make,model,price_cad\n2022,Ford,F-150,52000\n", encoding="utf-8")
        f150_old_archive_2.write_text("year,make,model,price_cad\n2022,Ford,F-150,51000\n", encoding="utf-8")
        f150_new_archive.write_text("year,make,model,price_cad\n2022,Ford,F-150,50000\n", encoding="utf-8")
        f150_latest_csv.write_text("year,make,model,price_cad\n2022,Ford,F-150,50000\n", encoding="utf-8")

        f350_latest_csv.write_text("year,make,model,price_cad\n2023,Ford,F-350,75000\n", encoding="utf-8")
        f350_archive_csv.write_text("year,make,model,price_cad\n2023,Ford,F-350,75000\n", encoding="utf-8")

        # Set older mtimes for pre-existing archives (e.g. 100 seconds before current run)
        import os, time
        now_ts = time.time()
        os.utime(f150_old_archive_1, (now_ts - 100, now_ts - 100))
        os.utime(f150_old_archive_2, (now_ts - 100, now_ts - 100))

        # Mock diagnostic evidence artifacts on disk for the anomalous source
        f150_status_file = self.root / "data" / "ford_f150" / "run_status" / "autotrader_latest.json"
        f150_status_file.parent.mkdir(parents=True, exist_ok=True)
        f150_autotrader["started_at_utc"] = run_start
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

        # Prove:
        # 1. Both pre-existing trusted archives remain in trusted path
        self.assertTrue(f150_old_archive_1.exists())
        self.assertTrue(f150_old_archive_2.exists())

        # 2. Anomalous newly generated archive is excluded from trusted publication path
        self.assertFalse(f150_new_archive.exists())

        # 3. Anomalous raw CSV data is preserved in run-specific quarantine directory
        quarantine_dir = self.root / "data" / "ford_f150" / "quarantine" / "autotrader" / run_id
        quarantined_files = [f.name for f in quarantine_dir.glob("*.csv")]
        self.assertIn("ford_f150_autotrader_2026-08-01_00-00-00.csv", quarantined_files)
        self.assertIn("ford_f150_autotrader_latest_quarantined.csv", quarantined_files)

        # 4. Anomalous latest trusted CSV is excluded from latest path
        self.assertFalse(f150_latest_csv.exists())

        # 5. Diagnostic/evidence artifacts remain preserved for investigation
        self.assertTrue(f150_status_file.exists())

        # 6. Healthy collection's latest and historical data remain untouched
        self.assertTrue(f350_latest_csv.exists())
        self.assertTrue(f350_archive_csv.exists())

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
        # Successful vehicle data (latest and historical archive) is published
        self.assertIn("data/ford_f350/latest/ford_f350_autotrader_latest.csv", manifest["published_paths"])
        self.assertIn("data/ford_f350/autotrader/ford_f350_autotrader_2026-08-01_00-00-00.csv", manifest["published_paths"])
        # Anomalous CSV outputs (latest and timestamped archive) are excluded
        self.assertNotIn("data/ford_f150/latest/ford_f150_autotrader_latest.csv", manifest["published_paths"])
        self.assertNotIn("data/ford_f150/autotrader/ford_f150_autotrader_2026-08-01_00-00-00.csv", manifest["published_paths"])
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

        # Also exercise purpose_outputs.build partial-source path
        ram_config = {
            "schema_version": 2,
            "vehicle_key": "ram_3500",
            "make": "Ram",
            "model": "3500",
            "criteria": {
                "min_year": 2020,
                "max_year": 2024,
                "max_price_cad": 100000,
                "fuel": "Diesel",
                "engine": "6.7L Cummins",
            },
            "origin": {"home_city": "Calgary, AB", "home_coords": [51.0447, -114.0719], "max_distance_km": 1000},
            "sources": {
                "autotrader": {"make": "Ram", "model": "3500", "search_locations": ["Calgary, AB"]},
                "kijiji": {"make": "Ram", "model": "3500", "search_locations": ["Calgary, AB"]},
            },
        }
        ram_config_path = self.root / "config_ram3500.json"
        ram_config_path.write_text(json.dumps(ram_config), encoding="utf-8")

        # Create valid autotrader status & artifacts for ram_3500
        ram_at_status = self._source_entry("ram_3500", "autotrader", healthy=True, accepted=1, fetched=1)
        ram_at_status["schema_version"] = 8
        ram_at_status["run_id"] = run_id
        ram_at_status["output_updated_this_run"] = True
        ram_at_status["schema_valid"] = True
        ram_at_status["canonical_evidence_schema_version"] = 1
        ram_at_status["identity_lifecycle_schema_version"] = 2
        ram_at_status["identity_lifecycle_status"] = "updated"
        ram_at_status["identity_observed_current_count"] = 1
        ram_at_status["row_cap_disabled"] = True
        ram_at_status["config_isolated"] = True
        ram_at_status["canonical_evidence_artifacts"] = {"accepted": "data/ram_3500/evidence/autotrader/accepted.jsonl"}
        ram_at_status["source_adapter_artifacts"] = {"records": "data/ram_3500/adapter_evidence/autotrader/records.jsonl"}

        ram_status_path = self.root / "data" / "ram_3500" / "run_status" / "autotrader_latest.json"
        ram_status_path.parent.mkdir(parents=True, exist_ok=True)
        ram_status_path.write_text(json.dumps(ram_at_status), encoding="utf-8")

        ram_accepted_path = self.root / "data" / "ram_3500" / "evidence" / "autotrader" / "accepted.jsonl"
        ram_accepted_path.parent.mkdir(parents=True, exist_ok=True)
        ram_accepted_record = {
            "evidence_schema_version": 1,
            "run_id": run_id,
            "vehicle_key": "ram_3500",
            "source": "autotrader",
            "canonical_listing_id": "autotrader-222",
            "source_listing_id": "222",
            "record_stage": "accepted",
            "source_record_index": 0,
            "raw_record_ref": "ref1",
            "source_adapter_record_ref": "ref2",
            "normalized": {
                "year": 2022,
                "make": "Ram",
                "model": "3500",
                "price_cad": 75000,
                "mileage_km": 40000,
                "listing_url": "https://autotrader.ca/222",
            },
        }
        ram_accepted_path.write_text(json.dumps(ram_accepted_record) + "\n", encoding="utf-8")

        ram_adapter_path = self.root / "data" / "ram_3500" / "adapter_evidence" / "autotrader" / "records.jsonl"
        ram_adapter_path.parent.mkdir(parents=True, exist_ok=True)
        ram_adapter_record = {
            "run_id": run_id,
            "source": "autotrader",
            "source_record_index": 0,
            "raw_payload": {"trim": "Limited"},
        }
        ram_adapter_path.write_text(json.dumps(ram_adapter_record) + "\n", encoding="utf-8")

        ram_identity_path = self.root / "data" / "ram_3500" / "identity_lifecycle" / "autotrader" / "current_latest.jsonl"
        ram_identity_path.parent.mkdir(parents=True, exist_ok=True)
        ram_identity_record = {
            "identity_lifecycle_schema_version": 2,
            "run_id": run_id,
            "vehicle_key": "ram_3500",
            "source": "autotrader",
            "canonical_listing_id": "autotrader-222",
            "lifecycle_state": "new",
            "vin_evidence_status": "not_reported",
        }
        ram_identity_path.write_text(json.dumps(ram_identity_record) + "\n", encoding="utf-8")

        # Mock inputs file for purpose outputs
        inputs_data = {
            "schema_version": 1,
            "vehicles": {
                "ram_3500": {
                    "analysis_profile": "owned_vehicle_value",
                    "subject_profile": {
                        "year": {"value": 2022, "evidence_status": "owner_reported_historical_unverified"},
                        "trim": {"value": "Limited", "evidence_status": "owner_reported_historical_unverified"},
                        "fuel": {"value": "Diesel", "evidence_status": "owner_reported_historical_unverified"},
                        "engine": {"value": "6.7L Cummins", "evidence_status": "owner_reported_historical_unverified"},
                        "drivetrain": {"value": "4wd", "evidence_status": "owner_reported_historical_unverified"},
                        "current_odometer_km": {"value": 40000, "evidence_status": "owner_reported_historical_unverified"},
                        "odometer_context": {"value": "personal", "evidence_status": "owner_reported_historical_unverified"},
                    },
                    "sale_goal": "monitor",
                },
                "subaru_forester": {
                    "analysis_profile": "owned_vehicle_value",
                    "subject_profile": {
                        "year": {"value": 2021, "evidence_status": "owner_reported_historical_unverified"},
                        "trim": {"value": "Touring", "evidence_status": "owner_reported_historical_unverified"},
                        "fuel": {"value": "Gas", "evidence_status": "owner_reported_historical_unverified"},
                        "engine": {"value": "2.5L", "evidence_status": "owner_reported_historical_unverified"},
                        "drivetrain": {"value": "AWD", "evidence_status": "owner_reported_historical_unverified"},
                        "current_odometer_km": {"value": 30000, "evidence_status": "owner_reported_historical_unverified"},
                        "odometer_context": {"value": "personal", "evidence_status": "owner_reported_historical_unverified"},
                    },
                    "sale_goal": "monitor",
                },
                "honda_odyssey": {
                    "analysis_profile": "family_friend_purchase",
                    "preferences": {
                        "budget_max_cad": {"value": 40000, "evidence_status": "friend_reported_unverified"},
                        "min_year": {"value": 2018, "evidence_status": "friend_reported_unverified"},
                        "max_year": {"value": 2023, "evidence_status": "friend_reported_unverified"},
                        "max_mileage_km": {"value": 80000, "evidence_status": "friend_reported_unverified"},
                        "minimum_seating": {"value": 7, "evidence_status": "friend_reported_unverified"},
                        "cargo_requirements": {"value": [], "evidence_status": "friend_reported_unverified"},
                        "max_distance_km": {"value": 500, "evidence_status": "friend_reported_unverified"},
                        "accident_title_requirement": {"value": "clean", "evidence_status": "friend_reported_unverified"},
                        "service_history_requirement": {"value": "available", "evidence_status": "friend_reported_unverified"},
                        "acceptable_seller_types": {"value": [], "evidence_status": "friend_reported_unverified"},
                        "availability_constraints": {"value": None, "evidence_status": "friend_input_required"},
                    },
                },
                "kia_carnival": {
                    "analysis_profile": "family_friend_purchase",
                    "preferences": {
                        "budget_max_cad": {"value": 45000, "evidence_status": "friend_reported_unverified"},
                        "min_year": {"value": 2021, "evidence_status": "friend_reported_unverified"},
                        "max_year": {"value": 2024, "evidence_status": "friend_reported_unverified"},
                        "max_mileage_km": {"value": 60000, "evidence_status": "friend_reported_unverified"},
                        "minimum_seating": {"value": 7, "evidence_status": "friend_reported_unverified"},
                        "cargo_requirements": {"value": [], "evidence_status": "friend_reported_unverified"},
                        "max_distance_km": {"value": 500, "evidence_status": "friend_reported_unverified"},
                        "accident_title_requirement": {"value": "clean", "evidence_status": "friend_reported_unverified"},
                        "service_history_requirement": {"value": "available", "evidence_status": "friend_reported_unverified"},
                        "acceptable_seller_types": {"value": [], "evidence_status": "friend_reported_unverified"},
                        "availability_constraints": {"value": None, "evidence_status": "friend_input_required"},
                    },
                },
            },
        }
        inputs_path = self.root / "purpose_inputs.json"
        inputs_path.write_text(json.dumps(inputs_data), encoding="utf-8")

        # Kijiji status is missing/unhealthy for ram_3500
        ram_kijiji_status_path = self.root / "data" / "ram_3500" / "run_status" / "kijiji_latest.json"
        ram_kijiji_status_path.write_text(json.dumps({"schema_version": 8, "run_id": run_id, "execution_status": "failed"}), encoding="utf-8")

        purpose_summary = build_purpose(
            root=self.root,
            config_path=ram_config_path,
            run_id=run_id,
            sources=["autotrader", "kijiji"],
            inputs_path=inputs_path,
        )

        self.assertEqual(purpose_summary["record_count"], 1)
        self.assertEqual(purpose_summary["sources"], ["autotrader"])
        self.assertEqual(purpose_summary["scope"], "single_source")

    def test_repeated_anomalous_runs_quarantine_separately(self):
        """
        Prove that two repeated anomalous runs produce two separately preserved quarantined raw datasets
        without overwriting each other.
        """
        from phase1_common import utc_now
        import os, time

        for run_id in ("run_1", "run_2"):
            run_start = utc_now()
            health = {
                "schema_version": 6,
                "run_id": run_id,
                "generated_at_utc": run_start,
                "overall_status": "degraded",
                "expected_source_runs": 1,
                "healthy_source_runs": 0,
                "unhealthy_source_runs": 1,
                "sources": [self._source_entry("ford_f150", "autotrader", healthy=False, accepted=0, fetched=0, execution_status="failed")],
            }
            f150_status = self._source_entry("ford_f150", "autotrader", healthy=False, accepted=0, fetched=0, execution_status="failed")
            f150_status["started_at_utc"] = run_start
            f150_status["run_id"] = run_id

            status_file = self.root / "data" / "ford_f150" / "run_status" / "autotrader_latest.json"
            status_file.parent.mkdir(parents=True, exist_ok=True)
            status_file.write_text(json.dumps(f150_status), encoding="utf-8")

            latest_csv = self.root / "data" / "ford_f150" / "latest" / "ford_f150_autotrader_latest.csv"
            archive_csv = self.root / "data" / "ford_f150" / "autotrader" / f"ford_f150_autotrader_{run_id}.csv"
            latest_csv.parent.mkdir(parents=True, exist_ok=True)
            archive_csv.parent.mkdir(parents=True, exist_ok=True)
            latest_csv.write_text(f"content_latest_{run_id}", encoding="utf-8")
            archive_csv.write_text(f"content_archive_{run_id}", encoding="utf-8")

            report = compare_health_reports(baseline=None, current=health, run_id=run_id)
            isolate_anomalous_collections(root=self.root, report=report)

        q1 = self.root / "data" / "ford_f150" / "quarantine" / "autotrader" / "run_1"
        q2 = self.root / "data" / "ford_f150" / "quarantine" / "autotrader" / "run_2"
        self.assertTrue(q1.exists())
        self.assertTrue(q2.exists())

        q1_files = {f.name: f.read_text(encoding="utf-8") for f in q1.glob("*.csv")}
        q2_files = {f.name: f.read_text(encoding="utf-8") for f in q2.glob("*.csv")}

        self.assertIn("ford_f150_autotrader_run_1.csv", q1_files)
        self.assertEqual(q1_files["ford_f150_autotrader_run_1.csv"], "content_archive_run_1")

        self.assertIn("ford_f150_autotrader_run_2.csv", q2_files)
        self.assertEqual(q2_files["ford_f150_autotrader_run_2.csv"], "content_archive_run_2")

    def test_missing_provenance_refuses_archive_movement(self):
        """
        Prove that if current-run provenance is missing or invalid (e.g. status run_id mismatch or
        missing started_at_utc), isolate_anomalous_collections refuses historical archive movement
        and leaves existing trusted historical archives untouched.
        """
        run_id = "run_no_provenance"
        health = {
            "schema_version": 6,
            "run_id": run_id,
            "generated_at_utc": "2026-08-01T00:00:00Z",
            "overall_status": "degraded",
            "expected_source_runs": 1,
            "healthy_source_runs": 0,
            "unhealthy_source_runs": 1,
            "sources": [self._source_entry("ford_f150", "autotrader", healthy=False, accepted=0, fetched=0, execution_status="failed")],
        }

        # Create trusted historical archive
        trusted_archive = self.root / "data" / "ford_f150" / "autotrader" / "ford_f150_autotrader_2026-07-01_00-00-00.csv"
        trusted_archive.parent.mkdir(parents=True, exist_ok=True)
        trusted_archive.write_text("trusted_archive_data", encoding="utf-8")

        # Status file lacks started_at_utc / has mismatched run_id
        status_file = self.root / "data" / "ford_f150" / "run_status" / "autotrader_latest.json"
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text(json.dumps({"schema_version": 8, "run_id": "wrong_run_id"}), encoding="utf-8")

        report = compare_health_reports(baseline=None, current=health, run_id=run_id)
        isolate_anomalous_collections(root=self.root, report=report)

        # Trusted archive remains untouched in data/ford_f150/autotrader/
        self.assertTrue(trusted_archive.exists())
        self.assertEqual(trusted_archive.read_text(encoding="utf-8"), "trusted_archive_data")


if __name__ == "__main__":
    unittest.main()
