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
            self.assertIsNone(
                discover_compatible_baseline(root=Path("."), current=self.current())
            )

    def test_selected_baseline_is_written(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current_path = root / "current.json"
            output_path = root / "baseline.json"
            current = self.current()
            current_path.write_text(json.dumps(current), encoding="utf-8")
            selected = {"run_id": "older", "overall_status": "success", "sources": [self.source()]}
            with patch("baseline_history.discover_compatible_baseline", return_value=selected):
                result = write_selected_baseline(
                    root=root, current_path=current_path, output_path=output_path
                )
            self.assertEqual(result["run_id"], "older")
            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8"))["run_id"], "older")


class WorkflowBaselineWiringTests(unittest.TestCase):
    def test_scrape_workflow_discovers_history_instead_of_copying_latest(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "scrape.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("Discover compatible historical health baseline", workflow)
        self.assertIn("python baseline_history.py", workflow)
        self.assertNotIn("cp data/run_status/latest.json", workflow)
        self.assertIn("--baseline", workflow)
        self.assertIn("--history-limit 50", workflow)


if __name__ == "__main__":
    unittest.main()
