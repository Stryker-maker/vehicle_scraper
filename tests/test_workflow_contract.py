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

    def test_all_workflow_stages_use_authoritative_registry_source_plan(self):
        self.assertIn("vehicle_registry.py validate", self.workflow)
        self.assertIn("vehicle_registry.py active-runs", self.workflow)
        self.assertGreaterEqual(self.workflow.count("--registry vehicle_registry.json"), 6)
        self.assertIn("build-manual-review", self.workflow)
        self.assertIn("report-health", self.workflow)
        self.assertNotIn("vehicle_registry.py active-configs", self.workflow)
        self.assertNotIn("config_f150.json", self.workflow)
        self.assertNotIn("config_tundra.json", self.workflow)
        self.assertNotIn("config_f350.json", self.workflow)

    def test_pull_requests_do_not_run_collectors(self):
        self.assertIn("if: github.event_name != 'pull_request'", self.workflow)
        self.assertIn("vehicle_config.py", self.workflow)
        self.assertIn("Validate governed vehicle registry and configurations", self.workflow)


if __name__ == "__main__":
    unittest.main()
