import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from baseline_history import discover_compatible_baseline, write_selected_baseline


class BaselineHistoryTests(unittest.TestCase):
    def source(self, fingerprint="fp", **extra):
        value = {
            "vehicle_key": "ford_f350",
            "source": "autotrader",
            "healthy": True,
            "compatibility_fingerprint": fingerprint,
        }
        value.update(extra)
        return value

    def current(self):
        return {"run_id": "current", "sources": [self.source()]}

    def test_newest_compatible_candidate_is_selected(self):
        candidates = [
            {"run_id": "newest", "overall_status": "success", "sources": [self.source()]},
            {"run_id": "older", "overall_status": "success", "sources": [self.source()]},
        ]
        with patch("baseline_history._git_history_paths", return_value=["r1", "r2"]), patch(
            "baseline_history._read_git_json", side_effect=candidates
        ):
            selected = discover_compatible_baseline(root=Path("."), current=self.current())
        self.assertEqual(selected["run_id"], "newest")

    def test_newest_incompatible_candidate_falls_back_to_older_compatible(self):
        candidates = [
            {"run_id": "newest", "overall_status": "success", "sources": [self.source("bad")]},
            {"run_id": "older", "overall_status": "success", "sources": [self.source()]},
        ]
        with patch("baseline_history._git_history_paths", return_value=["r1", "r2"]), patch(
            "baseline_history._read_git_json", side_effect=candidates
        ):
            selected = discover_compatible_baseline(root=Path("."), current=self.current())
        self.assertEqual(selected["run_id"], "older")

    def test_invalid_candidates_are_skipped(self):
        candidates = [
            {"run_id": "current", "overall_status": "success", "sources": [self.source()]},
            {"run_id": "failed", "overall_status": "failure", "sources": [self.source()]},
            {"run_id": "missing-fingerprint", "overall_status": "success", "sources": [self.source(None)]},
            {"run_id": "missing-source", "overall_status": "success", "sources": []},
            {"run_id": "good", "overall_status": "success_with_warnings", "sources": [self.source()]},
        ]
        with patch("baseline_history._git_history_paths", return_value=["1", "2", "3", "4", "5"]), patch(
            "baseline_history._read_git_json", side_effect=candidates
        ):
            selected = discover_compatible_baseline(root=Path("."), current=self.current())
        self.assertEqual(selected["run_id"], "good")

    def test_no_usable_candidate_returns_none(self):
        candidates = [
            {"run_id": "bad", "overall_status": "success", "sources": [self.source("bad")]},
        ]
        with patch("baseline_history._git_history_paths", return_value=["r1"]), patch(
            "baseline_history._read_git_json", side_effect=candidates
        ):
            self.assertIsNone(discover_compatible_baseline(root=Path("."), current=self.current()))

    def test_selected_baseline_is_written_with_selection_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current_path = root / "current.json"
            output_path = root / "baseline.json"
            current_path.write_text(json.dumps(self.current()), encoding="utf-8")
            selected = {"run_id": "older", "overall_status": "success", "sources": [self.source()]}
            metadata = {"schema_version": 1, "status": "selected", "historical_candidate_count": 1}
            with patch("baseline_history._discover_selection", return_value=(selected, metadata)):
                result = write_selected_baseline(root=root, current_path=current_path, output_path=output_path)
            artifact = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(result["run_id"], "older")
            self.assertEqual(artifact["run_id"], "older")
            self.assertEqual(artifact["_baseline_selection"]["status"], "selected")

    def test_no_compatible_history_writes_incompatibility_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current_path = root / "current.json"
            output_path = root / "baseline.json"
            current_path.write_text(json.dumps(self.current()), encoding="utf-8")
            metadata = {
                "schema_version": 1,
                "status": "incompatible",
                "reason": "no_compatible_historical_baseline",
                "historical_candidate_count": 2,
                "rejection_reasons": {"incompatible": 2},
            }
            with patch("baseline_history._discover_selection", return_value=(None, metadata)):
                result = write_selected_baseline(root=root, current_path=current_path, output_path=output_path)
            artifact = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(result["_baseline_selection"]["status"], "incompatible")
            self.assertEqual(artifact["_baseline_selection"]["historical_candidate_count"], 2)
            self.assertEqual(artifact["sources"], [])


class WorkflowBaselineWiringTests(unittest.TestCase):
    def test_scrape_workflow_discovers_history_instead_of_copying_latest(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "scrape.yml").read_text(encoding="utf-8")
        self.assertIn("Discover compatible historical health baseline", workflow)
        self.assertIn("python baseline_history.py", workflow)
        self.assertNotIn("cp data/run_status/latest.json", workflow)
        self.assertIn("--baseline", workflow)
        self.assertIn("--history-limit 50", workflow)


if __name__ == "__main__":
    unittest.main()
