import unittest
from pathlib import Path


class WorkflowContractTests(unittest.TestCase):
    def setUp(self):
        self.workflow = (
            Path(__file__).resolve().parents[1]
            / ".github" / "workflows" / "scrape.yml"
        ).read_text(encoding="utf-8")

    def test_generated_data_commits_receive_success_acknowledgement(self):
        self.assertNotIn("paths-ignore", self.workflow)
        self.assertIn("acknowledge-generated-data", self.workflow)
        self.assertIn("github.actor == 'github-actions[bot]'", self.workflow)
        self.assertIn("--timeout-seconds 4500", self.workflow)

    def test_full_workflow_keeps_authoritative_registry_plan(self):
        self.assertIn("vehicle_registry.py validate", self.workflow)
        self.assertIn("vehicle_registry.py active-runs", self.workflow)
        self.assertGreaterEqual(
            self.workflow.count("--registry vehicle_registry.json"), 7
        )
        self.assertIn("build-manual-review", self.workflow)
        self.assertIn("report-health", self.workflow)
        self.assertNotIn("vehicle_registry.py active-configs", self.workflow)
        self.assertNotIn("config_f150.json", self.workflow)
        self.assertNotIn("config_tundra.json", self.workflow)
        self.assertNotIn("config_f350.json", self.workflow)

    def test_single_pair_validation_is_narrow_non_committing_and_identity_aware(self):
        for value in (
            "validation_mode", "single_pair", "vehicle_key",
            "commit_generated_data", "--fail-on-unhealthy",
            "actions/upload-artifact@v4", "smoke-artifact",
            "Single-pair validation passed", "identity_lifecycle_status",
            "identity_observed_current_count", "identity_lifecycle",
            '"identity_lifecycle_schema_version": 2',
        ):
            self.assertIn(value, self.workflow)
        self.assertIn(
            "github.event_name == 'schedule' || "
            "(inputs.validation_mode == 'full' && inputs.commit_generated_data)",
            self.workflow,
        )

    def test_both_sources_use_direct_adapter_runtime(self):
        for value in (
            "autotrader_run.py", "autotrader_adapter.py",
            "autotrader_canonical.py", "autotrader_distance.py",
            "autotrader_history.py", "kijiji_run.py", "kijiji_adapter.py",
            "kijiji_canonical.py", "kijiji_locations.py", "kijiji_history.py",
            "identity_lifecycle.py", "direct_schema_v2", "pagination_complete",
            "location_registry_version", "query_origin_never_location",
        ):
            self.assertIn(value, self.workflow)
        self.assertNotIn("phase1_kijiji_runner.py", self.workflow)
        self.assertNotIn("python scraper.py --config", self.workflow)
        self.assertNotIn("python kijiji_scraper.py --config", self.workflow)

    def test_pull_requests_do_not_run_collectors(self):
        self.assertIn("if: github.event_name != 'pull_request'", self.workflow)
        for value in (
            "vehicle_config.py",
            "canonical_evidence.py",
            "identity_lifecycle.py",
            "storage_retention.py",
        ):
            self.assertIn(value, self.workflow)
        self.assertIn(
            "Validate governed vehicle registry and configurations", self.workflow
        )

    def test_full_run_retention_and_health_gate_precede_commit(self):
        for value in (
            "Fail visibly before any generated-data commit",
            "storage_retention.py apply",
            "storage_retention.py verify",
            "storage_retention.py validate-staged",
            "git diff --cached --stat",
            "git add data/",
        ):
            self.assertIn(value, self.workflow)
        health_index = self.workflow.index(
            "Fail visibly before any generated-data commit"
        )
        retention_index = self.workflow.index(
            "Apply and verify bounded storage retention"
        )
        commit_index = self.workflow.index(
            "Commit and push governed generated data"
        )
        self.assertLess(health_index, retention_index)
        self.assertLess(retention_index, commit_index)

    def test_single_pair_never_reaches_retention_or_commit_steps(self):
        self.assertIn(
            "if: github.event_name == 'schedule' || inputs.validation_mode == 'full'",
            self.workflow,
        )
        self.assertIn("retention-days: 7", self.workflow)


if __name__ == "__main__":
    unittest.main()
