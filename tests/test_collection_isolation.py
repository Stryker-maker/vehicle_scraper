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
    """Automated tests proving collection anomaly isolation, evidence preservation, and fail-closed behavior."""

    def setUp(self):
        """Create isolated temporary directory for isolation test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        """Clean up temporary test directory."""
        self.temp_dir.cleanup()

    @staticmethod
    def _source_entry(vehicle_key: str, source: str, healthy: bool, accepted: int, fetched: int, execution_status: str = "success"):
        """Build structured health/status entry for collection isolation tests."""
        return {
            "schema_version": 8,
            "identity_lifecycle_schema_version": 2,
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
            "latest_output": f"data/{vehicle_key}/latest/{vehicle_key}_{source}_latest.csv",
            "compatibility_fingerprint": "v1",
        }

    def _setup_git_repo(self):
        """Initialize temporary git repository for publication manifest verification tests."""
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
        f150_autotrader["archive_output"] = "data/ford_f150/autotrader/ford_f150_autotrader_2026-08-01_00-00-00.csv"
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
            "baseline_status": "unavailable",
            "anomaly_status": "critical",
            "critical_anomaly_count": 1,
            "warning_anomaly_count": 0,
            "informational_anomaly_count": 0,
            "anomalies": [],
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

        self.assertEqual(report["isolated_collections"], [])
        isolation_anomalies = [a for a in report["anomalies"] if a.get("code") == "collection_isolation_failed"]
        self.assertEqual(len(isolation_anomalies), 1)
        self.assertEqual(isolation_anomalies[0]["vehicle_key"], "ford_f150")

        from workflow_anomalies import write_anomaly_report
        write_anomaly_report(root=self.root, report=report)
        persisted = json.loads((self.root / "data" / "run_status" / "anomalies_latest.json").read_text(encoding="utf-8"))
        self.assertEqual(persisted["isolated_collections"], [])
        self.assertIn("collection_isolation_failed", [a["code"] for a in persisted["anomalies"]])

        self.assertTrue(f150_latest.exists())
        self.assertTrue(f150_archive.exists())
        self.assertEqual(f150_latest.read_text(encoding="utf-8"), "latest_data")
        self.assertEqual(f150_archive.read_text(encoding="utf-8"), "archive_data")

    def test_multi_collection_isolation_atomicity_valid_collection_and_invalid_identifier_zero_filesystem_mutations(self):
        """
        Prove that when isolating multiple collections (valid Collection A + Collection B with invalid identifier),
        Phase 1 validation rejects the invalid identifier BEFORE any file moves, leaving Collection A untouched.
        """
        run_id = "run_invalid_id_123"
        run_start = utc_now()

        # Collection A: valid ford_f350
        status_f350 = self._source_entry("ford_f350", "autotrader", healthy=False, accepted=0, fetched=0, execution_status="failed")
        status_f350["started_at_utc"] = run_start
        status_f350["run_id"] = run_id
        status_f350["archive_output"] = "data/ford_f350/autotrader/ford_f350_autotrader_2026-08-01_00-00-00.csv"
        status_f350_path = self.root / "data" / "ford_f350" / "run_status" / "autotrader_latest.json"
        status_f350_path.parent.mkdir(parents=True, exist_ok=True)
        status_f350_path.write_text(json.dumps(status_f350), encoding="utf-8")

        f350_latest = self.root / "data" / "ford_f350" / "latest" / "ford_f350_autotrader_latest.csv"
        f350_archive = self.root / "data" / "ford_f350" / "autotrader" / "ford_f350_autotrader_2026-08-01_00-00-00.csv"
        f350_latest.parent.mkdir(parents=True, exist_ok=True)
        f350_archive.parent.mkdir(parents=True, exist_ok=True)
        f350_latest.write_text("f350_latest_data", encoding="utf-8")
        f350_archive.write_text("f350_archive_data", encoding="utf-8")

        report = {
            "run_id": run_id,
            "isolated_collections": [
                {"vehicle_key": "ford_f350", "source": "autotrader"},
                {"vehicle_key": "../invalid_vehicle", "source": "autotrader"},
            ],
        }

        with self.assertRaisesRegex(ValueError, "Rejected invalid collection identifier"):
            isolate_anomalous_collections(root=self.root, report=report)

        # ZERO filesystem mutations: Collection A files MUST remain 100% in place!
        self.assertTrue(f350_latest.exists())
        self.assertTrue(f350_archive.exists())
        self.assertEqual(f350_latest.read_text(encoding="utf-8"), "f350_latest_data")
        self.assertEqual(f350_archive.read_text(encoding="utf-8"), "f350_archive_data")

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
            status["archive_output"] = f"data/{vk}/{src}/{vk}_{src}_2026-08-01_00-00-00.csv"
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
            "run_id": "run_test",
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

    def test_publication_manifest_fails_closed_when_anomaly_report_run_id_mismatches(self):
        """
        Prove that a valid anomaly report whose run_id differs from the publication run_id
        causes prepare_manifest() to fail closed.
        """
        self._setup_git_repo()
        anomaly_path = self.root / "data" / "run_status" / "anomalies_latest.json"
        anomaly_path.parent.mkdir(parents=True, exist_ok=True)
        mismatched_report = {
            "anomaly_schema_version": 1,
            "run_id": "stale_run_id_999",
            "isolated_collections": [],
        }
        anomaly_path.write_text(json.dumps(mismatched_report), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "Anomaly report run_id mismatch"):
            prepare_manifest(
                root=self.root,
                registry_path=Path("vehicle_registry.json"),
                run_id="current_run_id_123",
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
        status["archive_output"] = "data/ford_f150/autotrader/ford_f150_autotrader_2026-08-01_00-00-00.csv"
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
            """Mock Path.replace to simulate execution and rollback path failures."""
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
        quarantine_latest = self.root / "data" / "ford_f150" / "quarantine" / "autotrader" / run_id / "ford_f150_autotrader_latest_quarantined.csv"

        with patch.object(Path, "replace", new=mock_replace), self.assertRaises(RuntimeError) as ctx:
            isolate_anomalous_collections(root=self.root, report=report)

        err_msg = str(ctx.exception)
        self.assertIn("Atomic anomaly isolation failed during file movement", err_msg)
        self.assertIn("Rollback failed to restore paths", err_msg)
        self.assertIn(str(quarantine_latest), err_msg)
        self.assertIn(str(latest), err_msg)

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

    def test_repeated_isolation_runs_preserve_both_quarantine_evidence_sets(self):
        """
        Prove that two separate anomaly-isolation runs for the same collection
        preserve both run-specific quarantine evidence sets without overwriting or destroying each other.
        """
        vk = "ford_f150"
        src = "autotrader"

        # Run 1
        run_id_1 = "run_repeated_101"
        run_start_1 = utc_now()
        status_1 = self._source_entry(vk, src, healthy=False, accepted=0, fetched=0, execution_status="failed")
        status_1["started_at_utc"] = run_start_1
        status_1["run_id"] = run_id_1
        status_1["archive_output"] = f"data/{vk}/{src}/{vk}_{src}_2026-08-01_00-00-00.csv"
        status_file = self.root / "data" / vk / "run_status" / f"{src}_latest.json"
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text(json.dumps(status_1), encoding="utf-8")

        latest_csv = self.root / "data" / vk / "latest" / f"{vk}_{src}_latest.csv"
        archive_csv_1 = self.root / "data" / vk / src / f"{vk}_{src}_2026-08-01_00-00-00.csv"
        latest_csv.parent.mkdir(parents=True, exist_ok=True)
        archive_csv_1.parent.mkdir(parents=True, exist_ok=True)
        latest_csv.write_text("run1_latest_data", encoding="utf-8")
        archive_csv_1.write_text("run1_archive_data", encoding="utf-8")

        report_1 = {
            "run_id": run_id_1,
            "isolated_collections": [{"vehicle_key": vk, "source": src}],
        }
        isolated_1 = isolate_anomalous_collections(root=self.root, report=report_1)
        self.assertEqual(len(isolated_1), 1)

        q1_dir = self.root / "data" / vk / "quarantine" / src / run_id_1
        q1_files = {f.name: f.read_text(encoding="utf-8") for f in q1_dir.glob("*.csv")}
        self.assertIn(f"{vk}_{src}_latest_quarantined.csv", q1_files)
        self.assertEqual(q1_files[f"{vk}_{src}_latest_quarantined.csv"], "run1_latest_data")
        self.assertIn(f"{vk}_{src}_2026-08-01_00-00-00.csv", q1_files)
        self.assertEqual(q1_files[f"{vk}_{src}_2026-08-01_00-00-00.csv"], "run1_archive_data")

        # Run 2
        run_id_2 = "run_repeated_102"
        run_start_2 = utc_now()
        status_2 = self._source_entry(vk, src, healthy=False, accepted=0, fetched=0, execution_status="failed")
        status_2["started_at_utc"] = run_start_2
        status_2["run_id"] = run_id_2
        status_2["archive_output"] = f"data/{vk}/{src}/{vk}_{src}_2026-08-02_00-00-00.csv"
        status_file.write_text(json.dumps(status_2), encoding="utf-8")

        archive_csv_2 = self.root / "data" / vk / src / f"{vk}_{src}_2026-08-02_00-00-00.csv"
        latest_csv.write_text("run2_latest_data", encoding="utf-8")
        archive_csv_2.write_text("run2_archive_data", encoding="utf-8")

        report_2 = {
            "run_id": run_id_2,
            "isolated_collections": [{"vehicle_key": vk, "source": src}],
        }
        isolated_2 = isolate_anomalous_collections(root=self.root, report=report_2)
        self.assertEqual(len(isolated_2), 1)

        q2_dir = self.root / "data" / vk / "quarantine" / src / run_id_2
        q2_files = {f.name: f.read_text(encoding="utf-8") for f in q2_dir.glob("*.csv")}
        self.assertIn(f"{vk}_{src}_latest_quarantined.csv", q2_files)
        self.assertEqual(q2_files[f"{vk}_{src}_latest_quarantined.csv"], "run2_latest_data")
        self.assertIn(f"{vk}_{src}_2026-08-02_00-00-00.csv", q2_files)
        self.assertEqual(q2_files[f"{vk}_{src}_2026-08-02_00-00-00.csv"], "run2_archive_data")

        # Verify run 1 evidence remains untouched in its separate quarantine directory
        q1_files_after = {f.name: f.read_text(encoding="utf-8") for f in q1_dir.glob("*.csv")}
        self.assertEqual(q1_files_after[f"{vk}_{src}_latest_quarantined.csv"], "run1_latest_data")
        self.assertEqual(q1_files_after[f"{vk}_{src}_2026-08-01_00-00-00.csv"], "run1_archive_data")

    def test_explicit_current_archive_provenance_preserves_older_archive_with_recent_mtime(self):
        """
        Prove that isolation relies on explicit status['archive_output'] provenance rather than mtime,
        preserving an older archive file even if its mtime is recent.
        """
        vk = "ford_f150"
        src = "autotrader"
        run_id = "run_prov_mtime_123"
        run_start = utc_now()

        status = self._source_entry(vk, src, healthy=False, accepted=0, fetched=0, execution_status="failed")
        status["started_at_utc"] = run_start
        status["run_id"] = run_id
        current_archive_rel = f"data/{vk}/{src}/{vk}_{src}_2026-08-01_00-00-00.csv"
        status["archive_output"] = current_archive_rel

        status_file = self.root / "data" / vk / "run_status" / f"{src}_latest.json"
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text(json.dumps(status), encoding="utf-8")

        older_archive = self.root / "data" / vk / src / f"{vk}_{src}_2026-07-01_00-00-00.csv"
        current_archive = self.root / current_archive_rel
        latest_csv = self.root / "data" / vk / "latest" / f"{vk}_{src}_latest.csv"

        for p in (older_archive, current_archive, latest_csv):
            p.parent.mkdir(parents=True, exist_ok=True)

        older_archive.write_text("older_archive_content", encoding="utf-8")
        current_archive.write_text("current_archive_content", encoding="utf-8")
        latest_csv.write_text("latest_content", encoding="utf-8")

        # Set older_archive mtime to NOW (a misleading recent mtime)
        now_ts = time.time()
        os.utime(older_archive, (now_ts, now_ts))

        report = {
            "run_id": run_id,
            "isolated_collections": [{"vehicle_key": vk, "source": src}],
        }

        isolated = isolate_anomalous_collections(root=self.root, report=report)
        self.assertEqual(len(isolated), 1)

        # Older archive with recent mtime MUST remain preserved in its original location
        self.assertTrue(older_archive.exists())
        self.assertEqual(older_archive.read_text(encoding="utf-8"), "older_archive_content")

        # Current archive and latest CSV MUST be quarantined
        self.assertFalse(current_archive.exists())
        self.assertFalse(latest_csv.exists())
        q_dir = self.root / "data" / vk / "quarantine" / src / run_id
        self.assertTrue((q_dir / current_archive.name).exists())
        self.assertTrue((q_dir / f"{vk}_{src}_latest_quarantined.csv").exists())

    def test_multi_collection_isolation_atomicity_first_valid_second_invalid_provenance_zero_mutation(self):
        """
        Prove that when isolating multiple collections, if a later collection fails provenance validation,
        Phase 1 validation catches the error BEFORE any file moves, leaving the filesystem 100% untouched.
        """
        run_id = "run_atomicity_123"
        run_start = utc_now()

        # Collection 1: valid ford_f350
        status_f350 = self._source_entry("ford_f350", "autotrader", healthy=False, accepted=0, fetched=0, execution_status="failed")
        status_f350["started_at_utc"] = run_start
        status_f350["run_id"] = run_id
        status_f350["archive_output"] = "data/ford_f350/autotrader/ford_f350_autotrader_2026-08-01_00-00-00.csv"
        status_f350_path = self.root / "data" / "ford_f350" / "run_status" / "autotrader_latest.json"
        status_f350_path.parent.mkdir(parents=True, exist_ok=True)
        status_f350_path.write_text(json.dumps(status_f350), encoding="utf-8")

        f350_latest = self.root / "data" / "ford_f350" / "latest" / "ford_f350_autotrader_latest.csv"
        f350_latest.parent.mkdir(parents=True, exist_ok=True)
        f350_latest.write_text("f350_latest_data", encoding="utf-8")

        # Collection 2: invalid ford_f150 (missing started_at_utc / run_id mismatch)
        status_f150_path = self.root / "data" / "ford_f150" / "run_status" / "autotrader_latest.json"
        status_f150_path.parent.mkdir(parents=True, exist_ok=True)
        status_f150_path.write_text(json.dumps({"schema_version": 8, "run_id": "wrong_run_id"}), encoding="utf-8")

        f150_latest = self.root / "data" / "ford_f150" / "latest" / "ford_f150_autotrader_latest.csv"
        f150_latest.parent.mkdir(parents=True, exist_ok=True)
        f150_latest.write_text("f150_latest_data", encoding="utf-8")

        report = {
            "run_id": run_id,
            "isolated_collections": [
                {"vehicle_key": "ford_f350", "source": "autotrader"},
                {"vehicle_key": "ford_f150", "source": "autotrader"},
            ],
        }

        with self.assertRaisesRegex(ValueError, "Reliable current-run provenance missing or invalid"):
            isolate_anomalous_collections(root=self.root, report=report)

        # ZERO filesystem mutations: both latest files MUST remain in place!
        self.assertTrue(f350_latest.exists())
        self.assertTrue(f150_latest.exists())
        self.assertEqual(f350_latest.read_text(encoding="utf-8"), "f350_latest_data")
        self.assertEqual(f150_latest.read_text(encoding="utf-8"), "f150_latest_data")

    def test_valid_provenance_with_no_output_files_omitted_from_isolated_collections(self):
        """
        Prove that a collection with valid provenance but no latest CSV and no archive CSV
        is omitted from isolated_collections and receives a no_isolation_outputs_present diagnostic.
        """
        vk = "ford_f150"
        src = "autotrader"
        run_id = "run_no_files_123"
        run_start = utc_now()

        status = self._source_entry(vk, src, healthy=False, accepted=0, fetched=0, execution_status="failed")
        status["started_at_utc"] = run_start
        status["run_id"] = run_id
        status_file = self.root / "data" / vk / "run_status" / f"{src}_latest.json"
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text(json.dumps(status), encoding="utf-8")

        report = {
            "run_id": run_id,
            "isolated_collections": [{"vehicle_key": vk, "source": src}],
        }

        isolated = isolate_anomalous_collections(root=self.root, report=report)

        # Empty move plan MUST NOT claim successful isolation
        self.assertEqual(isolated, [])
        self.assertEqual(report["isolated_collections"], [])

        no_output_anomalies = [a for a in report["anomalies"] if a.get("code") == "no_isolation_outputs_present"]
        self.assertEqual(len(no_output_anomalies), 1)
        self.assertEqual(no_output_anomalies[0]["vehicle_key"], vk)

    def test_archive_path_escaping_collection_directory_raises_value_error_and_prevents_moves(self):
        """
        Prove that an archive_output path attempting to escape the collection directory
        (e.g. traversal ../../outside.csv) raises ValueError and moves zero files.
        """
        vk = "ford_f150"
        src = "autotrader"
        run_id = "run_escape_123"
        run_start = utc_now()

        outside_file = self.root / "data" / "outside_secret.csv"
        outside_file.parent.mkdir(parents=True, exist_ok=True)
        outside_file.write_text("secret_content", encoding="utf-8")

        status = self._source_entry(vk, src, healthy=False, accepted=0, fetched=0, execution_status="failed")
        status["started_at_utc"] = run_start
        status["run_id"] = run_id
        status["archive_output"] = "data/outside_secret.csv"

        status_file = self.root / "data" / vk / "run_status" / f"{src}_latest.json"
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text(json.dumps(status), encoding="utf-8")

        f150_latest = self.root / "data" / vk / "latest" / f"{vk}_{src}_latest.csv"
        f150_latest.parent.mkdir(parents=True, exist_ok=True)
        f150_latest.write_text("f150_latest_content", encoding="utf-8")

        report = {
            "run_id": run_id,
            "isolated_collections": [{"vehicle_key": vk, "source": src}],
        }

        with self.assertRaisesRegex(ValueError, "escapes collection directory"):
            isolate_anomalous_collections(root=self.root, report=report)

        # File containment check MUST prevent any file moves!
        self.assertTrue(outside_file.exists())
        self.assertEqual(outside_file.read_text(encoding="utf-8"), "secret_content")
        self.assertTrue(f150_latest.exists())
        self.assertEqual(f150_latest.read_text(encoding="utf-8"), "f150_latest_content")

    def test_check_action_rejects_malformed_and_duplicate_isolated_collections(self):
        """
        Prove that _run_check_action rejects malformed isolated_collections and duplicate entries,
        failing closed (returning exit code 1).
        """
        from workflow_anomalies import _run_check_action
        import argparse

        report_file = self.root / "anomalies_test.json"
        report_file.write_text(
            json.dumps({
                "anomaly_schema_version": 1,
                "isolated_collections": [
                    {"vehicle_key": "ford_f150", "source": "autotrader"},
                    {"vehicle_key": "ford_f150", "source": "autotrader"},
                ],
            }),
            encoding="utf-8",
        )
        args = argparse.Namespace(report=str(report_file), policy="report_only")
        exit_code = _run_check_action(self.root, args)
        self.assertEqual(exit_code, 1)

    def test_source_status_schema_version_mismatch_raises_value_error(self):
        """
        Prove that a source status JSON with an invalid schema_version raises ValueError (integrity error).
        """
        from f350_buyer_intelligence import SourceUnavailableError, _load_and_validate_source_status

        vk = "ford_f350"
        src = "autotrader"
        run_id = "run_schema_mismatch_123"

        config = {"vehicle_key": vk, "sources": {src: {}}}
        status = self._source_entry(vk, src, healthy=True, accepted=5, fetched=5)
        status["schema_version"] = 99  # Corrupt / invalid schema version
        status["run_id"] = run_id

        status_file = self.root / "data" / vk / "run_status" / f"{src}_latest.json"
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text(json.dumps(status), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "status schema_version mismatch"):
            _load_and_validate_source_status(self.root, config, src, run_id)

    def test_valid_but_non_success_source_status_raises_source_unavailable_error(self):
        """
        Prove that a source status JSON that is non-success / degraded raises SourceUnavailableError.
        """
        from f350_buyer_intelligence import SourceUnavailableError, _load_and_validate_source_status

        vk = "ford_f350"
        src = "autotrader"
        run_id = "run_degraded_123"

        config = {"vehicle_key": vk, "sources": {src: {}}}
        status = self._source_entry(vk, src, healthy=False, accepted=0, fetched=0, execution_status="failed")
        status["run_id"] = run_id

        status_file = self.root / "data" / vk / "run_status" / f"{src}_latest.json"
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text(json.dumps(status), encoding="utf-8")

        with self.assertRaises(SourceUnavailableError):
            _load_and_validate_source_status(self.root, config, src, run_id)

    def test_verify_staged_manifest_valid_matching_isolation_metadata_passes(self):
        """
        Prove that verify_staged_manifest passes when staged manifest and same-run anomaly report
        have matching isolated_collections metadata.
        """
        from generated_data_publish import verify_staged_manifest

        self._setup_git_repo()
        run_id = "run_verify_match_123"

        # Write anomaly report
        anomaly_path = self.root / "data" / "run_status" / "anomalies_latest.json"
        anomaly_path.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "anomaly_schema_version": 1,
            "run_id": run_id,
            "isolated_collections": [{"vehicle_key": "ford_f150", "source": "autotrader"}],
        }
        anomaly_path.write_text(json.dumps(report), encoding="utf-8")

        # Create valid published data for ford_f350
        f350_latest = self.root / "data" / "ford_f350" / "latest" / "ford_f350_autotrader_latest.csv"
        f350_latest.parent.mkdir(parents=True, exist_ok=True)
        f350_latest.write_text("f350_data", encoding="utf-8")

        subprocess.run(["git", "add", "data/"], cwd=self.root, check=True)
        prepare_manifest(
            root=self.root,
            registry_path=Path("vehicle_registry.json"),
            run_id=run_id,
            source_sha="a" * 40,
            event_name="schedule",
            ref_name="main",
        )

        subprocess.run(["git", "add", "data/"], cwd=self.root, check=True)

        res = verify_staged_manifest(root=self.root, registry_path=Path("vehicle_registry.json"))
        self.assertEqual(res["verification_status"], "pass")
        self.assertEqual(res["isolated_collections"], [{"vehicle_key": "ford_f150", "source": "autotrader"}])

    def test_verify_staged_manifest_mismatched_isolation_metadata_fails_closed(self):
        """
        Prove that verify_staged_manifest fails closed if staged manifest isolated_collections
        differs from the same-run anomaly report.
        """
        from generated_data_publish import MANIFEST_PATH, verify_staged_manifest

        self._setup_git_repo()
        run_id = "run_verify_mismatch_123"

        # Anomaly report has NO isolated collections
        anomaly_path = self.root / "data" / "run_status" / "anomalies_latest.json"
        anomaly_path.parent.mkdir(parents=True, exist_ok=True)
        anomaly_path.write_text(
            json.dumps({"anomaly_schema_version": 1, "run_id": run_id, "isolated_collections": []}),
            encoding="utf-8",
        )

        f350_latest = self.root / "data" / "ford_f350" / "latest" / "ford_f350_autotrader_latest.csv"
        f350_latest.parent.mkdir(parents=True, exist_ok=True)
        f350_latest.write_text("f350_data", encoding="utf-8")

        subprocess.run(["git", "add", "data/"], cwd=self.root, check=True)
        manifest = prepare_manifest(
            root=self.root,
            registry_path=Path("vehicle_registry.json"),
            run_id=run_id,
            source_sha="a" * 40,
            event_name="schedule",
            ref_name="main",
        )

        # Tamper with manifest to inject mismatched isolated_collections
        manifest["isolated_collections"] = [{"vehicle_key": "ford_f150", "source": "autotrader"}]
        manifest_path = self.root / MANIFEST_PATH
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        subprocess.run(["git", "add", "data/"], cwd=self.root, check=True)

        with self.assertRaisesRegex(ValueError, "isolated_collections metadata mismatch"):
            verify_staged_manifest(root=self.root, registry_path=Path("vehicle_registry.json"))

    def test_verify_staged_manifest_malformed_isolation_metadata_fails_closed(self):
        """
        Prove that verify_staged_manifest fails closed if staged manifest contains malformed isolated_collections.
        """
        from generated_data_publish import MANIFEST_PATH, verify_staged_manifest

        self._setup_git_repo()
        run_id = "run_verify_malformed_123"

        f350_latest = self.root / "data" / "ford_f350" / "latest" / "ford_f350_autotrader_latest.csv"
        f350_latest.parent.mkdir(parents=True, exist_ok=True)
        f350_latest.write_text("f350_data", encoding="utf-8")

        subprocess.run(["git", "add", "data/"], cwd=self.root, check=True)
        manifest = prepare_manifest(
            root=self.root,
            registry_path=Path("vehicle_registry.json"),
            run_id=run_id,
            source_sha="a" * 40,
            event_name="schedule",
            ref_name="main",
        )

        manifest["isolated_collections"] = "not_a_list"
        manifest_path = self.root / MANIFEST_PATH
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        subprocess.run(["git", "add", "data/"], cwd=self.root, check=True)

        with self.assertRaisesRegex(ValueError, "isolated_collections must be a list"):
            verify_staged_manifest(root=self.root, registry_path=Path("vehicle_registry.json"))

    def test_verify_staged_manifest_duplicate_isolation_identities_fails_closed(self):
        """
        Prove that verify_staged_manifest fails closed if staged manifest contains duplicate isolated_collections.
        """
        from generated_data_publish import MANIFEST_PATH, verify_staged_manifest

        self._setup_git_repo()
        run_id = "run_verify_dup_123"

        f350_latest = self.root / "data" / "ford_f350" / "latest" / "ford_f350_autotrader_latest.csv"
        f350_latest.parent.mkdir(parents=True, exist_ok=True)
        f350_latest.write_text("f350_data", encoding="utf-8")

        manifest = prepare_manifest(
            root=self.root,
            registry_path=Path("vehicle_registry.json"),
            run_id=run_id,
            source_sha="a" * 40,
            event_name="schedule",
            ref_name="main",
        )

        manifest["isolated_collections"] = [
            {"vehicle_key": "ford_f150", "source": "autotrader"},
            {"vehicle_key": "ford_f150", "source": "autotrader"},
        ]
        manifest_path = self.root / MANIFEST_PATH
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        subprocess.run(["git", "add", "data/"], cwd=self.root, check=True)

        with self.assertRaisesRegex(ValueError, "Duplicate collection identity in isolated_collections"):
            verify_staged_manifest(root=self.root, registry_path=Path("vehicle_registry.json"))

    def test_stale_latest_csv_is_not_quarantined_when_current_run_latest_output_is_none(self):
        """
        Prove that a stale latest CSV from a previous run is NOT moved/quarantined
        when the current run's validated status_data records latest_output as None.
        """
        vk = "ford_f150"
        src = "autotrader"
        run_id = "run_stale_latest_123"
        run_start = utc_now()

        status = self._source_entry(vk, src, healthy=False, accepted=0, fetched=0, execution_status="failed")
        status["started_at_utc"] = run_start
        status["run_id"] = run_id
        status["latest_output"] = None  # Current run produced NO latest output
        status["archive_output"] = f"data/{vk}/{src}/{vk}_{src}_2026-08-01_00-00-00.csv"

        status_file = self.root / "data" / vk / "run_status" / f"{src}_latest.json"
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text(json.dumps(status), encoding="utf-8")

        stale_latest_csv = self.root / "data" / vk / "latest" / f"{vk}_{src}_latest.csv"
        archive_csv = self.root / "data" / vk / src / f"{vk}_{src}_2026-08-01_00-00-00.csv"
        stale_latest_csv.parent.mkdir(parents=True, exist_ok=True)
        archive_csv.parent.mkdir(parents=True, exist_ok=True)
        stale_latest_csv.write_text("stale_previous_run_data", encoding="utf-8")
        archive_csv.write_text("current_archive_data", encoding="utf-8")

        report = {
            "run_id": run_id,
            "isolated_collections": [{"vehicle_key": vk, "source": src}],
        }

        isolated = isolate_anomalous_collections(root=self.root, report=report)
        self.assertEqual(len(isolated), 1)

        # Stale latest CSV MUST remain untouched in its original location
        self.assertTrue(stale_latest_csv.exists())
        self.assertEqual(stale_latest_csv.read_text(encoding="utf-8"), "stale_previous_run_data")

        # Current-run archive CSV MUST be quarantined
        self.assertFalse(archive_csv.exists())
        q_dir = self.root / "data" / vk / "quarantine" / src / run_id
        self.assertTrue((q_dir / archive_csv.name).exists())
        self.assertFalse((q_dir / f"{vk}_{src}_latest_quarantined.csv").exists())

    def test_check_action_policy_enforce_fails_closed_when_critical_anomalies_exist_without_quarantined_files(self):
        """
        Prove that _run_check_action with --policy enforce fails closed (returns 1)
        when all expected sources have critical anomalies, even if isolated_collections is empty
        because no output files were present to quarantine.
        """
        from workflow_anomalies import _run_check_action
        import argparse

        run_id = "run_enforce_no_files_123"

        health_file = self.root / "data" / "run_status" / "latest.json"
        health_file.parent.mkdir(parents=True, exist_ok=True)
        health_file.write_text(
            json.dumps({"schema_version": 6, "run_id": run_id, "expected_source_runs": 2}),
            encoding="utf-8",
        )

        report_file = self.root / "anomalies_no_files.json"
        report_file.write_text(
            json.dumps({
                "anomaly_schema_version": 1,
                "run_id": run_id,
                "critical_anomaly_count": 2,
                "isolated_collections": [],
                "anomalies": [
                    {
                        "severity": "critical",
                        "code": "collector_command_failed",
                        "vehicle_key": "ford_f150",
                        "source": "autotrader",
                    },
                    {
                        "severity": "critical",
                        "code": "collector_command_failed",
                        "vehicle_key": "ford_f150",
                        "source": "kijiji",
                    },
                ],
            }),
            encoding="utf-8",
        )

        args = argparse.Namespace(report=str(report_file), policy="enforce")
        exit_code = _run_check_action(self.root, args)
        self.assertEqual(exit_code, 1)

    def test_downstream_builders_exclude_critically_isolated_sources(self):
        """
        Prove that f350_buyer_intelligence and purpose_outputs exclude sources marked
        with critical anomalies / isolated in anomalies_latest.json for the current run_id.
        """
        from f350_buyer_intelligence import SourceUnavailableError, _load_and_validate_source_status

        vk = "ford_f350"
        src = "autotrader"
        run_id = "run_downstream_iso_123"

        # Create status indicating current success
        config = {"vehicle_key": vk, "sources": {src: {}}}
        status = self._source_entry(vk, src, healthy=True, accepted=5, fetched=5)
        status["run_id"] = run_id

        status_file = self.root / "data" / vk / "run_status" / f"{src}_latest.json"
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text(json.dumps(status), encoding="utf-8")

        # Mark ford_f350:autotrader as critically anomalous in anomalies_latest.json
        anomalies_file = self.root / "data" / "run_status" / "anomalies_latest.json"
        anomalies_file.parent.mkdir(parents=True, exist_ok=True)
        anomalies_file.write_text(
            json.dumps({
                "anomaly_schema_version": 1,
                "run_id": run_id,
                "isolated_collections": [{"vehicle_key": vk, "source": src}],
                "anomalies": [
                    {
                        "severity": "critical",
                        "code": "collector_command_failed",
                        "vehicle_key": vk,
                        "source": src,
                    }
                ],
            }),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(SourceUnavailableError, "isolated due to critical anomaly"):
            _load_and_validate_source_status(self.root, config, src, run_id)


if __name__ == "__main__":
    unittest.main()
