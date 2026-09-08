import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autotrader_adapter import ADAPTER_SCHEMA_VERSION as AUTOTRADER_ADAPTER_SCHEMA_VERSION
from autotrader_run import run_autotrader
from baseline_compatibility import build_compatibility_fingerprint
from canonical_evidence import EVIDENCE_SCHEMA_VERSION
from kijiji_adapter import ADAPTER_SCHEMA_VERSION as KIJIJI_ADAPTER_SCHEMA_VERSION
from kijiji_locations import LOCATION_REGISTRY_VERSION
from kijiji_run import run_kijiji
from vehicle_config import CONFIG_SCHEMA_VERSION
from workflow_anomalies import compare_health_reports


class RunStatusCompatibilityMetadataTests(unittest.TestCase):
    """Verify compatibility metadata survives source execution and health consolidation."""

    def setUp(self):
        """Create an isolated configuration and filesystem for runner tests."""
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = {
            "schema_version": 2,
            "vehicle_key": "test_vehicle",
            "make": "Test",
            "model": "Vehicle",
            "criteria": {"min_year": 2000, "max_year": 2030, "max_price_cad": 100000, "fuel": "Gas", "engine": ""},
            "origin": {"home_city": "Red Deer, AB", "home_coords": [52.2681, -113.8112], "max_distance_km": 800},
            "sources": {
                "autotrader": {"make": "test", "model": "vehicle", "search_locations": ["Calgary, AB"]},
                "kijiji": {"make": "Test", "model": "Vehicle", "search_locations": ["Edmonton, AB"]},
            },
        }
        self.config_path = self.root / "config.json"
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")

    def tearDown(self):
        """Remove the isolated test filesystem."""
        self.temp.cleanup()

    @staticmethod
    def _evidence():
        """Build minimal successful collection evidence for runner tests."""
        return {
            "fetched_record_scope": "test", "source_fetch_completeness": "complete", "pagination_complete": True,
            "query_location_count": 1, "page_request_count": 1, "request_attempt_count": 1,
            "successful_page_count": 1, "failed_page_count": 0, "listing_specific_location_records": 0,
            "unknown_location_records": 1, "fetched_records": 1, "normalized_records": 1,
            "accepted_records": 1, "rejected_records": 0, "parse_failures": 0, "reconciled": True,
            "reconciliation_equation": "fetched_records = accepted_records + rejected_records + parse_failures",
            "artifacts": {"accepted": "accepted.jsonl"}, "source_adapter_artifacts": {},
        }

    @staticmethod
    def _identity():
        """Build minimal identity lifecycle evidence for runner tests."""
        return {
            "observed_current_count": 1, "tracked_listing_count": 1, "new_listing_count": 1,
            "reappeared_listing_count": 0, "missing_listing_count": 0, "retired_listing_count": 0,
            "transition_event_count": 1, "artifacts": {},
        }

    def _run_with_patches(self, runner, module_name, evidence):
        """Execute a runner with deterministic I/O and adapter dependencies patched."""
        status_path = self.root / "status.json"
        output_path = self.root / "output.csv"
        captured = {}
        validation = {"row_count": 1, "schema_valid": True}
        quality = {"data_quality_status": "ok", "quality_warning_rows": 0, "quality_warning_count": 0, "quality_warning_summary": {}}

        def persist_status(path, value):
            """Capture and persist the runner status emitted by the test double."""
            captured["status"] = value
            Path(path).write_text(json.dumps(value), encoding="utf-8")

        with patch.dict(os.environ, {"COLLECTION_SCOPE": "full"}, clear=False), \
             patch(f"{module_name}.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")), \
             patch(f"{module_name}.file_signature", side_effect=[(1, 1), (2, 2)]), \
             patch(f"{module_name}.validate_csv", return_value=validation), \
             patch(f"{module_name}.expected_output_path", return_value=output_path), \
             patch(f"{module_name}.source_status_path", return_value=status_path), \
             patch(f"{module_name}.snapshot_artifacts", return_value={}), \
             patch(f"{module_name}.build_{'kijiji' if module_name == 'kijiji_run' else 'autotrader'}_canonical_evidence", return_value=evidence), \
             patch(f"{module_name}.update_source_identity_lifecycle", return_value=self._identity()), \
             patch(f"{module_name}.analyze_csv_quality", return_value=quality), \
             patch(f"{module_name}.write_json", side_effect=persist_status):
            status = runner(root=self.root, config_path=self.config_path, command=["fake"], run_id="run-1")
        return status, captured["status"]

    def test_kijiji_runtime_status_contains_compatibility_metadata(self):
        """Verify Kijiji runtime status contains its compatibility contract and fingerprint."""
        status, written = self._run_with_patches(run_kijiji, "kijiji_run", self._evidence())
        self.assertEqual(status["execution_status"], "success")
        self.assertEqual(status["collection_scope"], "full")
        self.assertEqual(status["compatibility_fingerprint"], written["compatibility_fingerprint"])
        self.assertEqual(status["compatibility_identity"]["query_locations"], ["Edmonton, AB"])
        self.assertEqual(status["compatibility_identity"]["location_registry_version"], LOCATION_REGISTRY_VERSION)
        self.assertEqual(status["compatibility_identity"]["adapter_schema_version"], KIJIJI_ADAPTER_SCHEMA_VERSION)

    def test_autotrader_runtime_status_contains_compatibility_metadata(self):
        """Verify AutoTrader runtime status contains its compatibility contract and fingerprint."""
        status, written = self._run_with_patches(run_autotrader, "autotrader_run", self._evidence())
        self.assertEqual(status["execution_status"], "success")
        self.assertEqual(status["collection_scope"], "full")
        self.assertEqual(status["compatibility_fingerprint"], written["compatibility_fingerprint"])
        self.assertIsNone(status["compatibility_identity"]["location_registry_version"])
        self.assertEqual(status["compatibility_identity"]["adapter_schema_version"], AUTOTRADER_ADAPTER_SCHEMA_VERSION)

    def test_fingerprint_metadata_matches_contract_dimensions(self):
        """Verify the generated fingerprint is tied to the declared compatibility dimensions."""
        identity, fingerprint = build_compatibility_fingerprint(config=self.config, source="kijiji", collection_scope="full", adapter_schema_version=KIJIJI_ADAPTER_SCHEMA_VERSION)
        self.assertEqual(identity["compatibility_schema_version"], 1)
        self.assertEqual(identity["configuration_schema_version"], CONFIG_SCHEMA_VERSION)
        self.assertEqual(identity["canonical_evidence_schema_version"], EVIDENCE_SCHEMA_VERSION)
        self.assertEqual(identity["adapter_schema_version"], KIJIJI_ADAPTER_SCHEMA_VERSION)
        self.assertEqual(identity["location_registry_version"], LOCATION_REGISTRY_VERSION)
        self.assertEqual(identity["query_location_count"], 1)
        self.assertEqual(len(fingerprint), 64)

    def test_compatibility_metadata_propagates_to_health_report(self):
        """Verify source status compatibility metadata is copied into consolidated health."""
        from phase1_reporting import collect_health
        for source_runner, source_name, module_name in [(run_kijiji, "kijiji", "kijiji_run"), (run_autotrader, "autotrader", "autotrader_run")]:
            with self.subTest(source=source_name):
                status, persisted_status = self._run_with_patches(source_runner, module_name, self._evidence())
                self.assertIn("compatibility_fingerprint", persisted_status)
                self.assertIn("compatibility_identity", persisted_status)
                self.assertIsNotNone(persisted_status["compatibility_fingerprint"])
                self.assertIsNotNone(persisted_status["compatibility_identity"])
                with patch("phase1_reporting.source_status_path", return_value=self.root / "status.json"):
                    health = collect_health(root=self.root, source_plan=[(self.config_path, [source_name])], run_id=status["run_id"])
                self.assertEqual(len(health["sources"]), 1)
                health_entry = health["sources"][0]
                self.assertEqual(health_entry.get("compatibility_fingerprint"), persisted_status["compatibility_fingerprint"], f"Fingerprint must propagate from {source_name} status to health report")
                self.assertEqual(health_entry.get("compatibility_identity"), persisted_status["compatibility_identity"], f"Identity must propagate from {source_name} status to health report")

    def test_persisted_status_to_health_to_anomaly_comparison_is_end_to_end(self):
        """Verify status metadata survives consolidation and enables a compatible baseline comparison."""
        from phase1_reporting import collect_health
        status, persisted_status = self._run_with_patches(run_kijiji, "kijiji_run", self._evidence())
        with patch("phase1_reporting.source_status_path", return_value=self.root / "status.json"):
            health = collect_health(root=self.root, source_plan=[(self.config_path, ["kijiji"])], run_id=status["run_id"])
        current_entry = health["sources"][0]
        baseline_entry = dict(current_entry)
        baseline_entry.update({"accepted_record_count": 40, "fetched_record_count": 200, "healthy": True, "execution_status": "success"})
        baseline = {"run_id": "historical-run", "overall_status": "success", "sources": [baseline_entry]}
        report = compare_health_reports(baseline=baseline, current=health, run_id=status["run_id"])
        self.assertEqual(current_entry["compatibility_fingerprint"], persisted_status["compatibility_fingerprint"])
        self.assertEqual(report["baseline_status"], "available")
        self.assertEqual(report["compatible_source_count"], 1)
        self.assertIn("accepted_record_count_collapse", {item["code"] for item in report["anomalies"]})
        self.assertIn("fetched_record_count_collapse", {item["code"] for item in report["anomalies"]})

    def test_collection_scope_isolated_from_outer_environment(self):
        """Verify runner tests force full scope even when the outer process requests single-pair scope."""
        with patch.dict(os.environ, {"COLLECTION_SCOPE": "single_pair"}, clear=False):
            _, persisted_status = self._run_with_patches(run_kijiji, "kijiji_run", self._evidence())
        self.assertEqual(persisted_status["collection_scope"], "full")


if __name__ == "__main__":
    unittest.main()
