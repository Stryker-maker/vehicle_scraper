import unittest
from pathlib import Path


class WorkflowContractTests(unittest.TestCase):
    def test_generated_data_commits_receive_success_acknowledgement(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "scrape.yml").read_text()
        self.assertNotIn("paths-ignore", workflow)
        self.assertIn("acknowledge-generated-data", workflow)
        self.assertIn("github.actor == 'github-actions[bot]'", workflow)
        self.assertIn("phase1_kijiji_runner.py --config", workflow)
        self.assertIn("--timeout-seconds 4500", workflow)


if __name__ == "__main__":
    unittest.main()
