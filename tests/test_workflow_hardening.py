import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dependency_lock import validate_lock
from generated_data_publish import MANIFEST_PATH, prepare_manifest, verify_staged_manifest
from workflow_anomalies import compare_health_reports
from workflow_control import build_collection_plan


class DependencyLockTests(unittest.TestCase):
    def test_repository_lock_is_exact(self):
        root = Path(__file__).resolve().parents[1]
        report = validate_lock(root / "requirements.lock")
        self.assertEqual(report["validation_status"], "pass")
        self.assertGreaterEqual(report["package_count"], 9)

    def test_ranges_and_duplicate_packages_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "requirements.lock"
            path.write_text("requests>=2\nrequests==2.34.2\nrequests==2.34.2\n", encoding="utf-8")
            report = validate_lock(path)
            self.assertEqual(report["validation_status"], "fail")
            self.assertTrue(any(value.startswith("non_exact_pin:") for value in report["validation_errors"]))
            self.assertIn("duplicate_package:requests", report["validation_errors"])


class WorkflowControlTests(unittest.TestCase):
    def test_full_and_single_pair_plans_are_registry_governed(self):
        root = Path(__file__).resolve().parents[1]
        import os
        os.environ["GITHUB_EVENT_NAME"] = "schedule"
        full_schedule = build_collection_plan(root=root, scope="full", registry_path=Path("vehicle_registry.json"))
        self.assertEqual(len(full_schedule), 10)
        self.assertFalse(any("f150" in str(p) for p, _ in full_schedule))
        os.environ["GITHUB_EVENT_NAME"] = "workflow_dispatch"
        full_manual = build_collection_plan(root=root, scope="full", registry_path=Path("vehicle_registry.json"))
        self.assertEqual(len(full_manual), 12)
        self.assertTrue(any("f150" in str(p) for p, _ in full_manual))
        del os.environ["GITHUB_EVENT_NAME"]
        single = build_collection_plan(root=root, scope="single_pair", registry_path=Path("vehicle_registry.json"), vehicle_key="ford_f350", source="kijiji")
        self.assertEqual(single, [(Path("config_f350.json"), "kijiji")])
        with self.assertRaisesRegex(ValueError, "paused"):
            build_collection_plan(root=root, scope="single_pair", registry_path=Path("vehicle_registry.json"), vehicle_key="toyota_tundra", source="autotrader")


class AnomalyTests(unittest.TestCase):
    def source(self, accepted: int, fetched: int, **extra):
        value = {
            "vehicle_key": "ford_f350", "source": "autotrader", "healthy": True,
            "execution_status": "success", "accepted_record_count": accepted,
            "fetched_record_count": fetched, "parse_failure_count": 0,
            "quality_warning_rows": 0, "compatibility_fingerprint": "fingerprint-v1",
        }
        value.update(extra)
        return value

    def test_material_count_collapse_is_critical(self):
        baseline = {"run_id": "old", "sources": [self.source(40, 200)]}
        current = {"run_id": "new", "sources": [self.source(5, 30)]}
        report = compare_health_reports(baseline=baseline, current=current, run_id="new")
        self.assertEqual(report["anomaly_status"], "critical")
        codes = {value["code"] for value in report["anomalies"]}
        self.assertIn("accepted_record_count_collapse", codes)
        self.assertIn("fetched_record_count_collapse", codes)

    def test_parse_rate_and_quality_growth_are_visible(self):
        baseline = {"run_id": "old", "sources": [self.source(20, 100)]}
        current = {"run_id": "new", "sources": [self.source(18, 100, parse_failure_count=6, quality_warning_rows=7)]}
        report = compare_health_reports(baseline=baseline, current=current, run_id="new")
        codes = {value["code"] for value in report["anomalies"]}
        self.assertIn("parse_failure_rate_elevated", codes)
        self.assertIn("quality_warning_growth", codes)
        self.assertEqual(report["warning_anomaly_count"], 2)

    def test_missing_baseline_is_visible_but_not_critical(self):
        current = {"run_id": "new", "sources": [self.source(20, 100)]}
        report = compare_health_reports(baseline=None, current=current, run_id="new")
        self.assertEqual(report["anomaly_status"], "no_baseline")
        self.assertEqual(report["critical_anomaly_count"], 0)

    def test_incompatible_baseline_cannot_drive_count_anomalies(self):
        baseline = {"run_id": "old", "sources": [self.source(100, 400, compatibility_fingerprint="old-scope")]}
        current = {"run_id": "new", "sources": [self.source(5, 20)]}
        report = compare_health_reports(baseline=baseline, current=current, run_id="new")
        codes = {value["code"] for value in report["anomalies"]}
        self.assertIn("baseline_incompatible", codes)
        self.assertNotIn("accepted_record_count_collapse", codes)
        self.assertNotIn("fetched_record_count_collapse", codes)
        self.assertEqual(report["critical_anomaly_count"], 0)
        self.assertEqual(report["warning_anomaly_count"], 0)
        self.assertEqual(report["incompatible_source_count"], 1)
        self.assertEqual(report["anomaly_status"], "baseline_incompatible")

    def test_missing_fingerprint_is_fail_closed(self):
        baseline = {"run_id": "old", "sources": [self.source(100, 400, compatibility_fingerprint=None)]}
        current = {"run_id": "new", "sources": [self.source(5, 20)]}
        report = compare_health_reports(baseline=baseline, current=current, run_id="new")
        codes = {value["code"] for value in report["anomalies"]}
        self.assertIn("baseline_incompatible", codes)
        self.assertNotIn("accepted_record_count_collapse", codes)
        self.assertEqual(report["critical_anomaly_count"], 0)

    def test_compatible_baseline_still_drives_existing_anomalies(self):
        baseline = {"run_id": "old", "sources": [self.source(40, 200)]}
        current = {"run_id": "new", "sources": [self.source(5, 30)]}
        report = compare_health_reports(baseline=baseline, current=current, run_id="new")
        self.assertEqual(report["compatible_source_count"], 1)
        self.assertEqual(report["incompatible_source_count"], 0)
        self.assertIn("accepted_record_count_collapse", {value["code"] for value in report["anomalies"]})

    def test_selecting_compatible_baseline_from_candidate_list(self):
        """When given multiple baselines, the first compatible one should be used."""
        current = {"run_id": "current_run", "sources": [self.source(5, 30)]}
        wrong_fp_baseline = {"run_id": "run_1", "overall_status": "success", "sources": [self.source(40, 200, compatibility_fingerprint="bad-fp")]}
        another_wrong = {"run_id": "run_2", "overall_status": "success", "sources": [self.source(40, 200, compatibility_fingerprint="also-bad")]}
        good_baseline = {"run_id": "run_3", "overall_status": "success", "sources": [self.source(40, 200)]}
        anomaly_report = compare_health_reports(baseline=None, current=current, run_id="current_run", baseline_candidates=[wrong_fp_baseline, another_wrong, good_baseline])
        self.assertEqual(anomaly_report["compatible_source_count"], 1)
        self.assertEqual(anomaly_report["incompatible_source_count"], 0)
        found_codes = {item["code"] for item in anomaly_report["anomalies"]}
        self.assertIn("accepted_record_count_collapse", found_codes)
        self.assertIn("fetched_record_count_collapse", found_codes)

    def test_no_compatible_candidates_yields_incompatible_status(self):
        """When history exists but no candidate is compatible, comparison fails closed with a diagnostic."""
        current = {"run_id": "current_run", "sources": [self.source(5, 30)]}
        bad_candidate_1 = {"run_id": "old_run_1", "overall_status": "success", "sources": [self.source(40, 200, compatibility_fingerprint="mismatch-A")]}
        bad_candidate_2 = {"run_id": "old_run_2", "overall_status": "success", "sources": [self.source(40, 200, compatibility_fingerprint="mismatch-B")]}
        anomaly_report = compare_health_reports(baseline=None, current=current, run_id="current_run", baseline_candidates=[bad_candidate_1, bad_candidate_2])
        self.assertEqual(anomaly_report["anomaly_status"], "baseline_incompatible")
        self.assertEqual(anomaly_report["critical_anomaly_count"], 0)
        self.assertIn("baseline_incompatible", {item["code"] for item in anomaly_report["anomalies"]})
        found_codes = {item["code"] for item in anomaly_report["anomalies"]}
        self.assertNotIn("accepted_record_count_collapse", found_codes)
        self.assertNotIn("fetched_record_count_collapse", found_codes)

    def test_empty_candidate_list_yields_no_baseline_status(self):
        """An empty candidate list should behave like having no baseline."""
        current = {"run_id": "current_run", "sources": [self.source(5, 30)]}
        anomaly_report = compare_health_reports(baseline=None, current=current, run_id="current_run", baseline_candidates=[])
        self.assertEqual(anomaly_report["anomaly_status"], "no_baseline")
        self.assertEqual(anomaly_report["critical_anomaly_count"], 0)

    def test_providing_both_baseline_and_candidates_raises_error(self):
        """Supplying both baseline and baseline_candidates should trigger an error."""
        current = {"run_id": "current_run", "sources": [self.source(5, 30)]}
        existing_baseline = {"run_id": "old_run", "sources": [self.source(40, 200)]}
        with self.assertRaisesRegex(ValueError, "baseline or baseline_candidates"):
            compare_health_reports(baseline=existing_baseline, current=current, run_id="current_run", baseline_candidates=[existing_baseline])


class PublicationManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = {
            "schema_version": 2, "vehicle_key": "test_vehicle", "make": "Test", "model": "Vehicle",
            "criteria": {"min_year": 2020, "max_year": 2026, "max_price_cad": 100000, "fuel": "Gas", "engine": ""},
            "origin": {"home_city": "Red Deer, AB", "home_coords": [52.2681, -113.8112], "max_distance_km": 800},
            "sources": {
                "autotrader": {"make": "test", "model": "vehicle", "search_locations": ["Red Deer, AB"]},
                "kijiji": {"make": "Test", "model": "Vehicle", "search_locations": ["Calgary, AB"]},
            },
        }
        (self.root / "config.json").write_text(json.dumps(self.config), encoding="utf-8")
        registry = {
            "schema_version": 2, "profile": "test",
            "vehicles": [{"vehicle_key": "test_vehicle", "config_path": "config.json", "enabled": True, "purpose": "primary_purchase", "priority": 1, "cadence": "weekly", "enabled_sources": ["autotrader", "kijiji"], "analysis_profile": "f350_purchase"}],
        }
        (self.root / "vehicle_registry.json").write_text(json.dumps(registry), encoding="utf-8")
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.root, check=True)

    def tearDown(self):
        self.temp.cleanup()

    def test_manifest_generation_and_verification(self):
        manifest = prepare_manifest(self.root, Path("vehicle_registry.json"))
        self.assertEqual(manifest["schema_version"], 1)
        self.assertIn("vehicle_registry.json", manifest["files"])
        staged = self.root / "staged"
        staged.mkdir()
        (staged / "vehicle_registry.json").write_text((self.root / "vehicle_registry.json").read_text(), encoding="utf-8")
        report = verify_staged_manifest(self.root, staged, manifest)
        self.assertTrue(report["valid"])

    def test_manifest_detects_modified_file(self):
        manifest = prepare_manifest(self.root, Path("vehicle_registry.json"))
        staged = self.root / "staged"
        staged.mkdir()
        (staged / "vehicle_registry.json").write_text("modified", encoding="utf-8")
        report = verify_staged_manifest(self.root, staged, manifest)
        self.assertFalse(report["valid"])
        self.assertTrue(report["errors"])


if __name__ == "__main__":
    unittest.main()
