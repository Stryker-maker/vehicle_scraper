import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from baseline_history import discover_compatible_baseline, write_selected_baseline
from workflow_anomalies import compare_health_reports


class BaselineHistoryEdgeCaseTests(unittest.TestCase):
    @staticmethod
    def source(*, vehicle_key="ford_f350", source="autotrader", fingerprint="fp", **extra):
        value = {
            "vehicle_key": vehicle_key,
            "source": source,
            "healthy": True,
            "compatibility_fingerprint": fingerprint,
        }
        value.update(extra)
        return value

    def current(self, sources=None):
        return {
            "run_id": "current-run",
            "sources": sources or [self.source()],
        }

    def test_history_is_evaluated_newest_to_oldest(self):
        current = self.current()
        reports = {
            "new": {"run_id": "new", "overall_status": "success", "sources": [self.source(fingerprint="fp-bad")]},
            "middle": {"run_id": "middle", "overall_status": "success", "sources": [self.source(fingerprint="fp-bad-2")]},
            "old": {"run_id": "old", "overall_status": "success", "sources": [self.source()]},
        }
        with patch("baseline_history._git_history_paths", return_value=["new", "middle", "old"]) as history, patch(
            "baseline_history._read_git_json", side_effect=lambda root, revision, path: reports[revision]
        ) as reader:
            selected = discover_compatible_baseline(root=Path("."), current=current, history_limit=3)
        self.assertEqual(selected["run_id"], "old")
        history.assert_called_once_with(Path("."), "data/run_status/latest.json", 3)
        self.assertEqual([call.args[1] for call in reader.call_args_list], ["new", "middle", "old"])

    def test_malformed_and_missing_historical_reports_are_skipped(self):
        current = self.current()
        reports = {
            "malformed": None,
            "missing": None,
            "good": {"run_id": "good", "overall_status": "success", "sources": [self.source()]},
        }
        with patch("baseline_history._git_history_paths", return_value=["malformed", "missing", "good"]), patch(
            "baseline_history._read_git_json", side_effect=lambda root, revision, path: reports[revision]
        ):
            selected = discover_compatible_baseline(root=Path("."), current=current)
        self.assertEqual(selected["run_id"], "good")

    def test_git_history_failure_fails_closed(self):
        current = self.current()
        failure = subprocess.CalledProcessError(128, ["git", "log"])
        with patch("baseline_history._git_history_paths", side_effect=failure):
            self.assertIsNone(discover_compatible_baseline(root=Path("."), current=current))

    def test_history_limit_is_passed_to_git_history_discovery(self):
        current = self.current()
        with patch("baseline_history._git_history_paths", return_value=["new"]) as history, patch(
            "baseline_history._read_git_json", return_value={
                "run_id": "new", "overall_status": "success", "sources": [self.source(fingerprint="bad")]
            }
        ) as reader:
            selected = discover_compatible_baseline(root=Path("."), current=current, history_limit=1)
        self.assertIsNone(selected)
        history.assert_called_once_with(Path("."), "data/run_status/latest.json", 1)
        self.assertEqual(reader.call_count, 1)

    def test_same_run_candidate_is_skipped_before_compatible_history(self):
        current = self.current()
        reports = [
            {"run_id": "current-run", "overall_status": "success", "sources": [self.source()]},
            {"run_id": "historical", "overall_status": "success", "sources": [self.source()]},
        ]
        with patch("baseline_history._git_history_paths", return_value=["r1", "r2"]), patch(
            "baseline_history._read_git_json", side_effect=reports
        ):
            selected = discover_compatible_baseline(root=Path("."), current=current)
        self.assertEqual(selected["run_id"], "historical")

    def test_mixed_source_candidate_must_be_complete(self):
        current = self.current(
            sources=[
                self.source(vehicle_key="ford_f350", source="autotrader"),
                self.source(vehicle_key="ford_f350", source="kijiji"),
            ]
        )
        incomplete = {
            "run_id": "incomplete",
            "overall_status": "success",
            "sources": [self.source(vehicle_key="ford_f350", source="autotrader")],
        }
        complete = {
            "run_id": "complete",
            "overall_status": "success",
            "sources": [
                self.source(vehicle_key="ford_f350", source="autotrader"),
                self.source(vehicle_key="ford_f350", source="kijiji"),
            ],
        }
        with patch("baseline_history._git_history_paths", return_value=["r1", "r2"]), patch(
            "baseline_history._read_git_json", side_effect=[incomplete, complete]
        ):
            selected = discover_compatible_baseline(root=Path("."), current=current)
        self.assertEqual(selected["run_id"], "complete")

    def test_selected_artifact_drives_anomaly_comparison(self):
        current = {
            "run_id": "current-run",
            "sources": [self.source(accepted_record_count=5, fetched_record_count=20)],
        }
        selected = {
            "run_id": "historical",
            "overall_status": "success",
            "sources": [self.source(accepted_record_count=40, fetched_record_count=100)],
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current_path = root / "current.json"
            baseline_path = root / "baseline.json"
            current_path.write_text(json.dumps(current), encoding="utf-8")
            with patch("baseline_history.discover_compatible_baseline", return_value=selected):
                result = write_selected_baseline(
                    root=root, current_path=current_path, output_path=baseline_path
                )
            self.assertEqual(result["run_id"], "historical")
            artifact = json.loads(baseline_path.read_text(encoding="utf-8"))
            report = compare_health_reports(
                baseline=artifact, current=current, run_id="current-run"
            )
        self.assertEqual(report["baseline_run_id"], "historical")
        self.assertIn(
            "accepted_record_count_collapse",
            {item["code"] for item in report["anomalies"]},
        )


if __name__ == "__main__":
    unittest.main()
