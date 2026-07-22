import unittest
from pathlib import Path


class WorkflowContractTests(unittest.TestCase):
    def setUp(self):
        self.workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "scrape.yml"
        ).read_text(encoding="utf-8")

    def test_generated_data_commits_receive_success_acknowledgement(self):
        self.assertNotIn("paths-ignore", self.workflow)
        self.assertIn("acknowledge-generated-data", self.workflow)
        self.assertIn("github.actor == 'github-actions[bot]'", self.workflow)
        self.assertNotIn("phase1_kijiji_runner.py", self.workflow)
        self.assertIn("--timeout-seconds 4500", self.workflow)

    def test_full_workflow_keeps_authoritative_registry_plan(self):
        self.assertIn("vehicle_registry.py validate", self.workflow)
        self.assertIn("vehicle_registry.py active-runs", self.workflow)
        self.assertGreaterEqual(
            self.workflow.count("--registry vehicle_registry.json"),
            5,
        )
        self.assertIn("build-manual-review", self.workflow)
        self.assertIn("report-health", self.workflow)
        self.assertNotIn("vehicle_registry.py active-configs", self.workflow)
        self.assertNotIn("config_f150.json", self.workflow)
        self.assertNotIn("config_tundra.json", self.workflow)
        self.assertNotIn("config_f350.json", self.workflow)

    def test_single_pair_validation_is_narrow_and_non_committing(self):
        self.assertIn("validation_mode", self.workflow)
        self.assertIn("single_pair", self.workflow)
        self.assertIn("vehicle_key", self.workflow)
        self.assertIn("commit_generated_data", self.workflow)
        self.assertIn("--fail-on-unhealthy", self.workflow)
        self.assertIn("actions/upload-artifact@v4", self.workflow)
        self.assertIn("smoke-artifact", self.workflow)
        self.assertIn("Single-pair validation passed", self.workflow)
        self.assertIn(
            "github.event_name == 'schedule' || "
            "(inputs.validation_mode == 'full' && inputs.commit_generated_data)",
            self.workflow,
        )

    def test_autotrader_uses_direct_adapter_runtime(self):
        self.assertIn("autotrader_run.py", self.workflow)
        self.assertIn("autotrader_adapter.py", self.workflow)
        self.assertIn("autotrader_canonical.py", self.workflow)
        self.assertIn("autotrader_distance.py", self.workflow)
        self.assertIn("autotrader_history.py", self.workflow)
        self.assertNotIn("python scraper.py --config", self.workflow)
        self.assertIn("direct_schema_v2", self.workflow)
        self.assertIn("pagination_complete", self.workflow)

    def test_kijiji_uses_direct_adapter_runtime(self):
        self.assertIn("kijiji_run.py", self.workflow)
        self.assertIn("kijiji_adapter.py", self.workflow)
        self.assertIn("kijiji_canonical.py", self.workflow)
        self.assertIn("kijiji_locations.py", self.workflow)
        self.assertIn("kijiji_history.py", self.workflow)
        self.assertNotIn("phase1_kijiji_runner.py", self.workflow)
        self.assertNotIn("python kijiji_scraper.py --config", self.workflow)
        self.assertIn("location_registry_version", self.workflow)
        self.assertIn("query_origin_never_location", self.workflow)

    def test_pull_requests_do_not_run_collectors(self):
        self.assertIn("if: github.event_name != 'pull_request'", self.workflow)
        self.assertIn("vehicle_config.py", self.workflow)
        self.assertIn("canonical_evidence.py", self.workflow)
        self.assertIn(
            "Validate governed vehicle registry and configurations",
            self.workflow,
        )

    def test_full_collection_commits_canonical_evidence(self):
        self.assertIn("canonical status evidence", self.workflow)
        self.assertIn("evidence-backed manual-review files", self.workflow)
        self.assertIn("consolidated reconciliation", self.workflow)
        self.assertIn("git add data/", self.workflow)


if __name__ == "__main__":
    unittest.main()
