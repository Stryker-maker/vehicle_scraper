import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from generated_data_publish import prepare_manifest
from phase1_common import utc_now
from purpose_outputs import build as build_purpose, read_jsonl
from workflow_anomalies import compare_health_reports, isolate_anomalous_collections


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

    def _setup_git_repo(self):
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "core.excludesfile", ""], cwd=self.root, check=True)

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

        health_dir = self.root / "data" / "run_status"
        health_dir.mkdir(parents=True, exist_ok=True)
        (health_dir / "latest.json").write_text(json.dumps(current_health), encoding="utf-8")

        f150_old_archive_1 = self.root / "data" / "ford_f150" / "autotrader" / "ford_f150_autotrader_2026-07-01_00-00-00.csv"
        f150_old_archive_2 = self.root / "data" / "ford_f150" / "autotrader" / "ford_f150_autotrader_2026-07-08_00-00-00.csv"
        f150_new_archive = self.root / "data" / "ford_f150" / "autotrader" / "ford_f150_autotrader_2026-08-01_00-00-00.csv"
        f150_latest_csv = self.root / "data" / "ford_f150" / "latest" / "ford_f150_autotrader_latest.csv"

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

        now_ts = time.time()
        os.utime(f150_old_archive_1, (now_ts - 100, now_ts - 100))
        os.utime(f150_old_archive_2, (now_ts - 100, now_ts - 100))

        f150_status_file = self.root / "data" / "ford_f150" / "run_status" / "autotrader_latest.json"
        f150_status_file.parent.mkdir(parents=True, exist_ok=True)
        f150_autotrader["started_at_utc"] = run_start
        f150_status_file.write_text(json.dumps(f150_autotrader), encoding="utf-8")

        anomaly_report = compare_health_reports(
            baseline=None,
            current=current_health,
            run_id=run_id,
        )

        self.assertGreater(anomaly_report["critical_anomaly_count"], 0)
        self.assertEqual(anomaly_report["anomaly_status"], "critical")
        self.assertIn(
            {"vehicle_key": "ford_f150", "source": "autotrader"},
            anomaly_report["isolated_collections"],
        )

        isolated = isolate_anomalous_collections(root=self.root, report=anomaly_report)
        self.assertEqual(len(isolated), 1)

        self.assertTrue(f150_old_archive_1.exists())
        self.assertTrue(f150_old_archive_2.exists())
        self.assertFalse(f150_new_archive.exists())

        quarantine_dir = self.root / "data" / "ford_f150" / "quarantine" / "autotrader" / run_id
        quarantined_files = [f.name for f in quarantine_dir.glob("*.csv")]
        self.assertIn("ford_f150_autotrader_2026-08-01_00-00-00.csv", quarantined_files)
        self.assertIn("ford_f150_autotrader_latest_quarantined.csv", quarantined_files)

        self.assertFalse(f150_latest_csv.exists())
        self.assertTrue(f150_status_file.exists())
        self.assertTrue(f350_latest_csv.exists())
        self.assertTrue(f350_archive_csv.exists())

        (health_dir / "anomalies_latest.json").write_text(json.dumps(anomaly_report), encoding="utf-8")

        self._setup_git_repo()
        subprocess.run(["git", "add", "data/"], cwd=self.root, check=True)

        manifest = prepare_manifest(
            root=self.root,
            registry_path=Path("vehicle_registry.json"),
            run_id=run_id,
            source_sha="a" * 40,
            event_name="schedule",
            ref_name="main",
        )

        self.assertEqual(manifest["publication_status"], "prepared_for_commit")
        self.assertIn("ford_f350", manifest["active_vehicle_keys"])
        self.assertEqual(
            manifest["isolated_collections"],
            [{"vehicle_key": "ford_f150", "source": "autotrader"}],
        )
        self.assertIn("data/ford_f350/latest/ford_f350_autotrader_latest.csv", manifest["published_paths"])
        self.assertIn("data/ford_f350/autotrader/ford_f350_autotrader_2026-08-01_00-00-00.csv", manifest["published_paths"])
        self.assertNotIn("data/ford_f150/latest/ford_f150_autotrader_latest.csv", manifest["published_paths"])
        self.assertNotIn("data/ford_f150/autotrader/ford_f150_autotrader_2026-08-01_00-00-00.csv", manifest["published_paths"])
        self.assertIn("data/ford_f150/run_status/autotrader_latest.json", manifest["published_paths"])

    def test_valid_collection_followed_by_invalid_provenance_zero_filesystem_mutations(self):
        """
        Prove that a collection with invalid current-run provenance raises ValueError and produces
        zero filesystem mutations (trusted archives and latest CSV remain in place).
        """
        run_id = "run_invalid_prov_123"
        report = {
            "run_id": run_id,
            "isolated_collections": [{"vehicle_key": "ford_f150", "source": "autotrader"}],
        }

        f150_latest = self.root / "data" / "ford_f150" / "latest" / "ford_f150_autotrader_latest.csv"
        f150_archive = self.root / "data" / "ford_f150" / "autotrader" / "ford_f150_autotrader_2026-08-01_00-00-00.csv"
        f150_latest.parent.mkdir(parents=True, exist_ok=True)
        f150_archive.parent.mkdir(parents=True, exist_ok=True)
        f150_latest.write_text("latest_data", encoding="utf-8")
        f150_archive.write_text("archive_data", encoding="utf-8")

        status_file = self.root / "data" / "ford_f150" / "run_status" / "autotrader_latest.json"
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text(json.dumps({"schema_version": 8, "run_id": "mismatched_run_id"}), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "Reliable current-run provenance missing or invalid"):
            isolate_anomalous_collections(root=self.root, report=report)

        self.assertTrue(f150_latest.exists())
        self.assertTrue(f150_archive.exists())
        self.assertEqual(f150_latest.read_text(encoding="utf-8"), "latest_data")
        self.assertEqual(f150_archive.read_text(encoding="utf-8"), "archive_data")

    def test_valid_collection_followed_by_invalid_identifier_zero_filesystem_mutations(self):
        """
        Prove that an invalid collection identifier raises ValueError and produces zero filesystem mutations.
        """
        run_id = "run_invalid_id_123"
        report = {
            "run_id": run_id,
            "isolated_collections": [{"vehicle_key": "../invalid_vehicle", "source": "autotrader"}],
        }

        f150_latest = self.root / "data" / "ford_f150" / "latest" / "ford_f150_autotrader_latest.csv"
        f150_latest.parent.mkdir(parents=True, exist_ok=True)
        f150_latest.write_text("latest_data", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "Rejected invalid collection identifier"):
            isolate_anomalous_collections(root=self.root, report=report)

        self.assertTrue(f150_latest.exists())
        self.assertEqual(f150_latest.read_text(encoding="utf-8"), "latest_data")

    def test_valid_multi_collection_isolation_moves_all_intended_files(self):
        """
        Prove that valid multi-collection isolation moves files for all intended collections.
        """
        run_id = "run_multi_123"
        run_start = utc_now()
        report = {
            "run_id": run_id,
            "isolated_collections": [
                {"vehicle_key": "ford_f150", "source": "autotrader"},
                {"vehicle_key": "subaru_forester", "source": "kijiji"},
            ],
        }

        for vk, src in (("ford_f150", "autotrader"), ("subaru_forester", "kijiji")):
            status = self._source_entry(vk, src, healthy=False, accepted=0, fetched=0, execution_status="failed")
            status["started_at_utc"] = run_start
            status["run_id"] = run_id
            status_file = self.root / "data" / vk / "run_status" / f"{src}_latest.json"
            status_file.parent.mkdir(parents=True, exist_ok=True)
            status_file.write_text(json.dumps(status), encoding="utf-8")

            latest = self.root / "data" / vk / "latest" / f"{vk}_{src}_latest.csv"
            archive = self.root / "data" / vk / src / f"{vk}_{src}_2026-08-01_00-00-00.csv"
            latest.parent.mkdir(parents=True, exist_ok=True)
            archive.parent.mkdir(parents=True, exist_ok=True)
            latest.write_text(f"latest_{vk}_{src}", encoding="utf-8")
            archive.write_text(f"archive_{vk}_{src}", encoding="utf-8")

        isolated = isolate_anomalous_collections(root=self.root, report=report)
        self.assertEqual(len(isolated), 2)

        for vk, src in (("ford_f150", "autotrader"), ("subaru_forester", "kijiji")):
            q_dir = self.root / "data" / vk / "quarantine" / src / run_id
            self.assertTrue(q_dir.exists())
            q_files = [f.name for f in q_dir.glob("*.csv")]
            self.assertIn(f"{vk}_{src}_latest_quarantined.csv", q_files)
            self.assertIn(f"{vk}_{src}_2026-08-01_00-00-00.csv", q_files)

    def test_malformed_unreadable_anomaly_report_causes_publication_to_fail_closed(self):
        """
        Prove that an unreadable or malformed anomalies_latest.json causes prepare_manifest() to fail closed.
        """
        self._setup_git_repo()
        anomaly_path = self.root / "data" / "run_status" / "anomalies_latest.json"
        anomaly_path.parent.mkdir(parents=True, exist_ok=True)
        anomaly_path.write_text("{corrupt_json: invalid", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "Unreadable or malformed anomaly report"):
            prepare_manifest(
                root=self.root,
                registry_path=Path("vehicle_registry.json"),
                run_id="run_test",
                source_sha="a" * 40,
                event_name="schedule",
                ref_name="main",
            )

    def test_invalid_isolated_collection_schema_causes_publication_to_fail_closed(self):
        """
        Prove that invalid isolated_collections schema causes prepare_manifest() to fail closed.
        """
        self._setup_git_repo()
        anomaly_path = self.root / "data" / "run_status" / "anomalies_latest.json"
        anomaly_path.parent.mkdir(parents=True, exist_ok=True)
        bad_report = {
            "anomaly_schema_version": 1,
            "isolated_collections": [{"vehicle_key": "../bad", "source": "autotrader"}],
        }
        anomaly_path.write_text(json.dumps(bad_report), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "Invalid collection identifier in isolated_collections"):
            prepare_manifest(
                root=self.root,
                registry_path=Path("vehicle_registry.json"),
                run_id="run_test",
                source_sha="a" * 40,
                event_name="schedule",
                ref_name="main",
            )

    def test_purpose_output_data_integrity_error_fails_closed(self):
        """
        Prove that a data integrity/validation error (e.g. accepted/identity count mismatch)
        is NOT silently converted into an unavailable source, but instead fails closed by raising ValueError.
        """
        run_id = "run_integrity_err_123"
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

        # Create status marking success
        ram_at_status = self._source_entry("ram_3500", "autotrader", healthy=True, accepted=2, fetched=2)
        ram_at_status["schema_version"] = 8
        ram_at_status["run_id"] = run_id
        ram_at_status["output_updated_this_run"] = True
        ram_at_status["schema_valid"] = True
        ram_at_status["canonical_evidence_schema_version"] = 1
        ram_at_status["identity_lifecycle_schema_version"] = 2
        ram_at_status["identity_lifecycle_status"] = "updated"
        ram_at_status["identity_observed_current_count"] = 2
        ram_at_status["accepted_record_count"] = 2
        ram_at_status["row_cap_disabled"] = True
        ram_at_status["config_isolated"] = True
        ram_at_status["canonical_evidence_artifacts"] = {"accepted": "data/ram_3500/evidence/autotrader/accepted.jsonl"}
        ram_at_status["source_adapter_artifacts"] = {"records": "data/ram_3500/adapter_evidence/autotrader/records.jsonl"}

        ram_status_path = self.root / "data" / "ram_3500" / "run_status" / "autotrader_latest.json"
        ram_status_path.parent.mkdir(parents=True, exist_ok=True)
        ram_status_path.write_text(json.dumps(ram_at_status), encoding="utf-8")

        # Corrupt data integrity: 2 accepted records but 0 identity records
        ram_accepted_path = self.root / "data" / "ram_3500" / "evidence" / "autotrader" / "accepted.jsonl"
        ram_accepted_path.parent.mkdir(parents=True, exist_ok=True)
        ram_accepted_path.write_text('{"record_stage": "accepted", "run_id": "run_integrity_err_123"}\n', encoding="utf-8")

        ram_identity_path = self.root / "data" / "ram_3500" / "identity_lifecycle" / "autotrader" / "current_latest.jsonl"
        ram_identity_path.parent.mkdir(parents=True, exist_ok=True)
        ram_identity_path.write_text("", encoding="utf-8")

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

        # Must raise ValueError due to count mismatch, failing closed
        with self.assertRaisesRegex(ValueError, "accepted/identity count mismatch"):
            build_purpose(
                root=self.root,
                config_path=ram_config_path,
                run_id=run_id,
                sources=["autotrader"],
                inputs_path=inputs_path,
            )

    def test_execution_time_isolation_failure_exercises_rollback_and_reports_unrecovered_paths(self):
        """
        Prove that when an execution-time move fails and rollback also encounters a path failure,
        the original exception is preserved and unrecovered paths are identified in the error message.
        """
        run_id = "run_rollback_fail_123"
        run_start = utc_now()

        status = self._source_entry("ford_f150", "autotrader", healthy=False, accepted=0, fetched=0, execution_status="failed")
        status["started_at_utc"] = run_start
        status["run_id"] = run_id
        status_file = self.root / "data" / "ford_f150" / "run_status" / "autotrader_latest.json"
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text(json.dumps(status), encoding="utf-8")

        latest = self.root / "data" / "ford_f150" / "latest" / "ford_f150_autotrader_latest.csv"
        archive = self.root / "data" / "ford_f150" / "autotrader" / "ford_f150_autotrader_2026-08-01_00-00-00.csv"
        latest.parent.mkdir(parents=True, exist_ok=True)
        archive.parent.mkdir(parents=True, exist_ok=True)
        latest.write_text("latest_content", encoding="utf-8")
        archive.write_text("archive_content", encoding="utf-8")

        report = {
            "run_id": run_id,
            "isolated_collections": [{"vehicle_key": "ford_f150", "source": "autotrader"}],
        }

        # Mock Path.replace to succeed on first move (latest), fail on second move (archive),
        # and fail on rollback of first move to trigger unrecovered paths reporting.
        original_replace = Path.replace
        replace_call_count = [0]

        def mock_replace(self, target):
            replace_call_count[0] += 1
            if replace_call_count[0] == 1:
                # Move latest CSV successfully
                return original_replace(self, target)
            elif replace_call_count[0] == 2:
                # Move archive CSV fails with OSError
                raise OSError("Simulated execution move error")
            else:
                # Rollback move fails with OSError
                raise OSError("Simulated rollback error")

        from unittest.mock import patch
        with patch.object(Path, "replace", new=mock_replace):
            with self.assertRaises(RuntimeError) as ctx:
                isolate_anomalous_collections(root=self.root, report=report)

        err_msg = str(ctx.exception)
        self.assertIn("Atomic anomaly isolation failed during file movement", err_msg)
        self.assertIn("Rollback failed to restore paths", err_msg)

    def test_emitted_purpose_output_record_scope_matches_effective_scope_when_one_source_unavailable(self):
        """
        Prove that emitted purpose-output records match the summary's effective scope when one source is unavailable.
        """
        run_id = "run_purpose_scope_123"
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

        # Valid autotrader
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

        # Kijiji status is missing for ram_3500
        summary = build_purpose(
            root=self.root,
            config_path=ram_config_path,
            run_id=run_id,
            sources=["autotrader", "kijiji"],
            inputs_path=inputs_path,
        )

        self.assertEqual(summary["scope"], "single_source")
        records = read_jsonl(self.root / "data" / "ram_3500" / "purpose_output" / "value_monitor" / "comparables_latest.jsonl")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["scope"], "single_source")


if __name__ == "__main__":
    unittest.main()
