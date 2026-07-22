import unittest
from pathlib import Path


class WorkflowContractTests(unittest.TestCase):
    def setUp(self):
        self.workflow = (
            Path(__file__).resolve().parents[1] / ".github" / "workflows" / "scrape.yml"
        ).read_text(encoding="utf-8")

    def test_generated_data_commits_receive_success_acknowledgement(self):
        self.assertNotIn("paths-ignore", self.workflow)
        self.assertIn("acknowledge-generated-data", self.workflow)
        self.assertIn("github.actor == 'github-actions[bot]'", self.workflow)
        self.assertIn("phase1_kijiji_runner.py --config", self.workflow)
        self.assertIn("--timeout-seconds 4500", self.workflow)

    def test_all_workflow_stages_use_authoritative_registry(self):
        self.assertIn("vehicle_registry.py validate", self.workflow)
        self.assertGreaterEqual(
            self.workflow.count("vehicle_registry.py active-configs"), 3
        )
        self.assertNotIn("config_f150.json", self.workflow)
        self.assertNotIn("config_tundra.json", self.workflow)
        self.assertNotIn("config_f350.json", self.workflow)
        self.assertIn("vehicle_registry.py", self.workflow)


if __name__ == "__main__":
    unittest.main()
