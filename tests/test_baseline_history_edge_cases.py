import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from baseline_history import discover_compatible_baseline, write_selected_baseline
from workflow_anomalies import compare_health_reports


class BaselineHistoryEdgeCaseTests(unittest.TestCase):
    """Exercise hostile and boundary conditions in historical baseline selection."""

    @staticmethod
    def source(*, vehicle_key="ford_f350", source="autotrader", fingerprint="fp", **extra):
        """Build a minimal source fixture with a controllable compatibility fingerprint."""
        value = {"vehicle_key": vehicle_key, "source": source, "healthy": True, "compatibility_fingerprint": fingerprint}
        value.update(extra)
        return value

    def current(self, sources=None):
        """Build the current report for an edge-case scenario."""
        return {"run_id": "current-run", "sources": sources or [self.source()]}

    def test_history_is_evaluated_newest_to_oldest(self):
        """Verify incompatible newer history is skipped in favor of the older compatible report."""
        current = self.current()
        reports = {
            "new": {"run_id": "new", "overall_status": "success", "sources": [self.source(fingerprint="fp-bad")]},
            "middle": {"run_id": "middle", "overall_status": "success", "sources": [self.source(fingerprint="fp-bad-2")]},
            "old": {"run_id": "old", "overall_status": "success", "sources": [self.source()]},
        }
        with patch("baseline_history._git_history_paths", return_value=["new", "middle", "old"]) as history, patch("baseline_history._read_git_json", side_effect=lambda root, revision, path: reports[revision]) as reader:
            selected = discover_compatible_baseline(root=Path("."), current=current, history_limit=3)
        self.assertEqual(selected["run_id"], "old")
        history.assert_called_once_with(Path("."), "data/run_status/latest.json", 3)
        self.assertEqual([call.args[1] for call in reader.call_args_list], ["new", "middle", "old"])

    def test_malformed_and_missing_historical_reports_are_skipped(self):
        """Skip reports that are missing or malformed until a valid baseline is found."""
        current = self.current()
        reports = {"malformed": None, "missing": None, "good": {"run_id": "good", "overall_status": "success", "sources": [self.source()]}}
        with patch("baseline_history._git_history_paths", return_value=["malformed", "missing", "good"]), patch("baseline_history._read_git_json", side_effect=lambda root, revision, path: reports[revision]):
            selected = discover_compatible_baseline(root=Path("."), current=current)
        self.assertEqual(selected["run_id"], "good")

    def test_git_history_failure_fails_closed(self):
        """Treat inability to inspect Git history as absence of a usable baseline."""
        current = self.current()
        failure = subprocess.CalledProcessError(128, ["git", "log"])
        with patch("baseline_history._git_history_paths", side_effect=failure):
            self.assertIsNone(discover_compatible_baseline(root=Path("."), current=current))

    def test_history_limit_is_passed_to_git_history_discovery(self):
        """Ensure the configured history search limit reaches Git discovery."""
        current = self.current()
        with patch("baseline_history._git_history_paths", return_value=["new"]) as history, patch("baseline_history._read_git_json", return_value={"run_id": "new", "overall_status": "success", "sources": [self.source(fingerprint="bad")]}) as reader:
            selected = discover_compatible_baseline(root=Path("."), current=current, history_limit=1)
        self.assertIsNone(selected)
        history.assert_called_once_with(Path("."), "data/run_status/latest.json", 1)
        self.assertEqual(reader.call_count, 1)

    def test_same_run_candidate_is_skipped_before_compatible_history(self):
        """Exclude the current run before considering older compatible history."""
        current = self.current()
        reports = [
            {"run_id": "current-run", "overall_status": "success", "sources": [self.source()]},
            {"run_id": "historical", "overall_status": "success", "sources": [self.source()]},
        ]
        with patch("baseline_history._git_history_paths", return_value=["r1", "r2"]), patch("baseline_history._read_git_json", side_effect=reports):
            selected = discover_compatible_baseline(root=Path("."), current=current)
        self.assertEqual(selected["run_id"], "historical")

    def test_same_run_only_history_is_unavailable_not_incompatible(self):
        """Classify history containing only the current run as unavailable, not incompatible."""
        current = self.current()
        current_report = {"run_id": "current-run", "overall_status": "success", "sources": [self.source()]}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current_path = root / "current.json"
            baseline_path = root / "baseline.json"
            current_path.write_text(json.dumps(current), encoding="utf-8")
            with patch("baseline_history._git_history_paths", return_value=["current-revision"]), patch("baseline_history._read_git_json", return_value=current_report):
                artifact = write_selected_baseline(root=root, current_path=current_path, output_path=baseline_path)
            metadata = artifact["_baseline_selection"]
            report = compare_health_reports(baseline=artifact, current=current, run_id="current-run")
        self.assertEqual(metadata["status"], "unavailable")
        self.assertEqual(metadata["reason"], "no_historical_reports")
        self.assertEqual(metadata["historical_candidate_count"], 0)
        self.assertNotIn("baseline_incompatible", {item["code"] for item in report["anomalies"]})
        self.assertEqual(report["anomaly_status"], "no_baseline")

    def test_mixed_source_candidate_must_be_complete(self):
        """Require a historical candidate to cover every current source."""
        current = self.current([self.source(source="autotrader"), self.source(source="kijiji")])
        incomplete = {"run_id": "incomplete", "overall_status": "success", "sources": [self.source(source="autotrader")]}
        complete = {"run_id": "complete", "overall_status": "success", "sources": [self.source(source="autotrader"), self.source(source="kijiji")]}
        with patch("baseline_history._git_history_paths", return_value=["r1", "r2"]), patch("baseline_history._read_git_json", side_effect=[incomplete, complete]):
            selected = discover_compatible_baseline(root=Path("."), current=current)
        self.assertEqual(selected["run_id"], "complete")

    def test_historical_candidate_with_malformed_source_is_rejected(self):
        """Reject a candidate containing a non-object source entry and continue searching."""
        current = self.current()
        malformed = {"run_id": "malformed", "overall_status": "success", "sources": [self.source(), "malformed-entry"]}
        compatible = {"run_id": "compatible", "overall_status": "success", "sources": [self.source()]}
        with patch("baseline_history._git_history_paths", return_value=["r1", "r2"]), patch("baseline_history._read_git_json", side_effect=[malformed, compatible]):
            selected = discover_compatible_baseline(root=Path("."), current=current)
        self.assertEqual(selected["run_id"], "compatible")

    def test_selected_artifact_drives_anomaly_comparison(self):
        """Verify a selected artifact can drive normal compatible baseline anomaly detection."""
        current = {"run_id": "current-run", "sources": [self.source(accepted_record_count=5, fetched_record_count=20)]}
        selected = {"run_id": "historical", "overall_status": "success", "sources": [self.source(accepted_record_count=40, fetched_record_count=100)]}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); current_path = root / "current.json"; baseline_path = root / "baseline.json"
            current_path.write_text(json.dumps(current), encoding="utf-8")
            metadata = {"schema_version": 1, "status": "selected", "historical_candidate_count": 1}
            with patch("baseline_history._discover_selection", return_value=(selected, metadata)):
                result = write_selected_baseline(root=root, current_path=current_path, output_path=baseline_path)
            artifact = json.loads(baseline_path.read_text(encoding="utf-8"))
            report = compare_health_reports(baseline=artifact, current=current, run_id="current-run")
        self.assertEqual(result["run_id"], "historical")
        self.assertEqual(report["baseline_run_id"], "historical")
        self.assertIn("accepted_record_count_collapse", {item["code"] for item in report["anomalies"]})

    def test_incompatible_selection_artifact_reports_incompatibility_without_count_anomalies(self):
        """Verify an incompatible selection artifact emits diagnostics without count anomalies."""
        current = {"run_id": "current-run", "sources": [self.source(accepted_record_count=5, fetched_record_count=20)]}
        metadata = {"schema_version": 1, "status": "incompatible", "reason": "no_compatible_historical_baseline", "historical_candidate_count": 2}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); current_path = root / "current.json"; baseline_path = root / "baseline.json"
            current_path.write_text(json.dumps(current), encoding="utf-8")
            with patch("baseline_history._discover_selection", return_value=(None, metadata)):
                write_selected_baseline(root=root, current_path=current_path, output_path=baseline_path)
            artifact = json.loads(baseline_path.read_text(encoding="utf-8"))
            report = compare_health_reports(baseline=artifact, current=current, run_id="current-run")
        codes = {item["code"] for item in report["anomalies"]}
        self.assertEqual(report["anomaly_status"], "baseline_incompatible")
        self.assertEqual(report["baseline_status"], "incompatible")
        self.assertIn("baseline_incompatible", codes)
        self.assertFalse(any(code.endswith(("_collapse", "_drop", "_surge")) for code in codes))

    def test_direct_selector_rejects_invalid_candidates_and_chooses_next_complete_one(self):
        """Verify direct candidate selection skips invalid candidates and selects the next valid one."""
        current = self.current([self.source(source="autotrader"), self.source(source="kijiji")])
        candidates = [
            {"run_id": "current-run", "overall_status": "success", "sources": [self.source(source="autotrader"), self.source(source="kijiji")]},
            {"run_id": "failed", "overall_status": "failure", "sources": [self.source(source="autotrader"), self.source(source="kijiji")]},
            {"run_id": "incomplete", "overall_status": "success", "sources": [self.source(source="autotrader")]},
            {"run_id": "bad-fp", "overall_status": "success", "sources": [self.source(source="autotrader", fingerprint="bad"), self.source(source="kijiji")]},
            {"run_id": "good", "overall_status": "success", "sources": [self.source(source="autotrader"), self.source(source="kijiji")]},
        ]
        report = compare_health_reports(baseline=None, current=current, run_id="current-run", baseline_candidates=candidates)
        self.assertEqual(report["baseline_run_id"], "good")
        self.assertEqual(report["baseline_status"], "available")

    def test_direct_selector_rejects_duplicate_candidate_source_entries(self):
        """Reject direct candidates with duplicate vehicle/source keys."""
        current = self.current()
        duplicate = {"run_id": "duplicate", "overall_status": "success", "sources": [self.source(), self.source()]}
        report = compare_health_reports(baseline=None, current=current, run_id="current-run", baseline_candidates=[duplicate])
        self.assertEqual(report["baseline_status"], "incompatible")
        self.assertEqual(report["anomaly_status"], "baseline_incompatible")

    def test_real_git_history_selects_oldest_compatible_after_current_and_incompatible_revisions(self):
        """Verify real Git history skips the current and incompatible revisions before selecting a valid baseline."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True, text=True)
            subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Vehicle Scraper Tests"], cwd=root, check=True)
            report_path = root / "data" / "run_status" / "latest.json"
            report_path.parent.mkdir(parents=True)

            def commit(report, message):
                """Write a historical report and commit it to the temporary Git repository."""
                report_path.write_text(json.dumps(report), encoding="utf-8")
                subprocess.run(["git", "add", str(report_path.relative_to(root))], cwd=root, check=True)
                subprocess.run(["git", "commit", "-m", message], cwd=root, check=True, capture_output=True, text=True)

            commit({"run_id": "good", "overall_status": "success", "sources": [self.source()]}, "good")
            commit({"run_id": "bad", "overall_status": "success", "sources": [self.source(fingerprint="bad")]}, "incompatible")
            commit({"run_id": "current-run", "overall_status": "success", "sources": [self.source()]}, "current")
            selected = discover_compatible_baseline(root=root, current=self.current(), history_limit=3)
        self.assertEqual(selected["run_id"], "good")


if __name__ == "__main__":
    unittest.main()
