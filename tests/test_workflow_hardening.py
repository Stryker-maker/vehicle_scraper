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
            path.write_text("requests>=2\nrequests==2.34.2\n", encoding="utf-8")
            report = validate_lock(path)
            self.assertEqual(report["validation_status"], "fail")
            self.assertTrue(
                any(value.startswith("non_exact_pin:") for value in report["validation_errors"])
            )
            self.assertIn("duplicate_package:requests", report["validation_errors"])


class WorkflowControlTests(unittest.TestCase):
    def test_full_and_single_pair_plans_are_registry_governed(self):
        root = Path(__file__).resolve().parents[1]
        full = build_collection_plan(
            root=root,
            scope="full",
            registry_path=Path("vehicle_registry.json"),
        )
        self.assertEqual(len(full), 10)
        single = build_collection_plan(
            root=root,
            scope="single_pair",
            registry_path=Path("vehicle_registry.json"),
            vehicle_key="ford_f350",
            source="kijiji",
        )
        self.assertEqual(single, [(Path("config_f350.json"), "kijiji")])
        with self.assertRaisesRegex(ValueError, "paused"):
            build_collection_plan(
                root=root,
                scope="single_pair",
                registry_path=Path("vehicle_registry.json"),
                vehicle_key="ford_f150",
                source="autotrader",
            )


class AnomalyTests(unittest.TestCase):
    def source(self, accepted: int, fetched: int, **extra):
        value = {
            "vehicle_key": "ford_f350",
            "source": "autotrader",
            "healthy": True,
            "execution_status": "success",
            "accepted_record_count": accepted,
            "fetched_record_count": fetched,
            "parse_failure_count": 0,
            "quality_warning_rows": 0,
        }
        value.update(extra)
        return value

    def test_material_count_collapse_is_critical(self):
        baseline = {"run_id": "old", "sources": [self.source(40, 200)]}
        current = {"run_id": "new", "sources": [self.source(5, 30)]}
        report = compare_health_reports(
            baseline=baseline, current=current, run_id="new"
        )
        self.assertEqual(report["anomaly_status"], "critical")
        codes = {value["code"] for value in report["anomalies"]}
        self.assertIn("accepted_record_count_collapse", codes)
        self.assertIn("fetched_record_count_collapse", codes)

    def test_parse_rate_and_quality_growth_are_visible(self):
        baseline = {"run_id": "old", "sources": [self.source(20, 100)]}
        current = {
            "run_id": "new",
            "sources": [
                self.source(
                    18,
                    100,
                    parse_failure_count=6,
                    quality_warning_rows=7,
                )
            ],
        }
        report = compare_health_reports(
            baseline=baseline, current=current, run_id="new"
        )
        codes = {value["code"] for value in report["anomalies"]}
        self.assertIn("parse_failure_rate_elevated", codes)
        self.assertIn("quality_warning_growth", codes)
        self.assertEqual(report["warning_anomaly_count"], 2)

    def test_missing_baseline_is_visible_but_not_critical(self):
        current = {"run_id": "new", "sources": [self.source(20, 100)]}
        report = compare_health_reports(
            baseline=None, current=current, run_id="new"
        )
        self.assertEqual(report["anomaly_status"], "no_baseline")
        self.assertEqual(report["critical_anomaly_count"], 0)


class PublicationManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = {
            "schema_version": 2,
            "vehicle_key": "test_vehicle",
            "make": "Test",
            "model": "Vehicle",
            "criteria": {
                "min_year": 2020,
                "max_year": 2026,
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
                    "search_locations": ["Red Deer, AB"],
                },
                "kijiji": {
                    "make": "Test",
                    "model": "Vehicle",
                    "search_locations": ["Calgary, AB"],
                },
            },
        }
        (self.root / "config.json").write_text(
            json.dumps(self.config), encoding="utf-8"
        )
        registry = {
            "schema_version": 2,
            "profile": "test",
            "vehicles": [
                {
                    "vehicle_key": "test_vehicle",
                    "config_path": "config.json",
                    "enabled": True,
                    "purpose": "primary_purchase",
                    "priority": 1,
                    "cadence": "weekly",
                    "enabled_sources": ["autotrader", "kijiji"],
                    "analysis_profile": "f350_purchase",
                }
            ],
        }
        (self.root / "vehicle_registry.json").write_text(
            json.dumps(registry), encoding="utf-8"
        )
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.invalid"],
            cwd=self.root,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"], cwd=self.root, check=True
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_manifest_matches_staged_governed_data(self):
        data = self.root / "data/test_vehicle/latest/example.csv"
        data.parent.mkdir(parents=True)
        data.write_text("a,b\n1,2\n", encoding="utf-8")
        subprocess.run(["git", "add", "data/"], cwd=self.root, check=True)
        manifest = prepare_manifest(
            root=self.root,
            registry_path=Path("vehicle_registry.json"),
            run_id="123",
            source_sha="a" * 40,
            event_name="workflow_dispatch",
            ref_name="ai/test",
        )
        self.assertEqual(manifest["published_paths"], ["data/test_vehicle/latest/example.csv"])
        subprocess.run(
            ["git", "add", MANIFEST_PATH.as_posix()], cwd=self.root, check=True
        )
        verified = verify_staged_manifest(
            root=self.root, registry_path=Path("vehicle_registry.json")
        )
        self.assertEqual(verified["verification_status"], "pass")

    def test_non_data_staged_path_is_rejected(self):
        (self.root / "README.md").write_text("unsafe", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, check=True)
        with self.assertRaisesRegex(ValueError, "outside_data"):
            prepare_manifest(
                root=self.root,
                registry_path=Path("vehicle_registry.json"),
                run_id="123",
                source_sha="a" * 40,
                event_name="workflow_dispatch",
                ref_name="ai/test",
            )


if __name__ == "__main__":
    unittest.main()
