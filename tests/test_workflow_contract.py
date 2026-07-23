import re
import unittest
from pathlib import Path


class WorkflowContractTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        workflows = root / ".github" / "workflows"
        self.ci = (workflows / "ci.yml").read_text(encoding="utf-8")
        self.collection = (workflows / "scrape.yml").read_text(encoding="utf-8")
        self.generated = (workflows / "generated-data.yml").read_text(
            encoding="utf-8"
        )
        self.all_workflows = "\n".join((self.ci, self.collection, self.generated))

    def test_ci_is_reusable_and_pull_request_collection_is_impossible(self):
        self.assertIn("workflow_call:", self.ci)
        self.assertIn("pull_request:", self.ci)
        self.assertIn("paths-ignore:", self.ci)
        self.assertIn("- 'data/**'", self.ci)
        self.assertNotIn("pull_request:", self.collection)
        self.assertIn("uses: ./.github/workflows/ci.yml", self.collection)
        self.assertIn("needs: preflight", self.collection)

    def test_generated_data_has_a_separate_pull_request_validator(self):
        self.assertIn("name: Generated Data Validation", self.generated)
        self.assertIn("pull_request:", self.generated)
        self.assertIn("- 'data/**'", self.generated)
        self.assertIn("generated_data_validation.py", self.generated)
        self.assertIn("generated-data-paths.txt", self.generated)
        self.assertNotIn("acknowledge-generated-data", self.all_workflows)

    def test_actions_are_pinned_to_exact_commit_shas(self):
        action_lines = [
            line.strip()
            for line in self.all_workflows.splitlines()
            if "uses: actions/" in line
        ]
        self.assertGreaterEqual(len(action_lines), 8)
        for line in action_lines:
            self.assertRegex(line, r"uses: actions/[a-z-]+@[0-9a-f]{40}$")
            self.assertNotRegex(line, r"@v\d")

    def test_locked_python_environment_is_used_everywhere(self):
        for workflow in (self.ci, self.collection, self.generated):
            self.assertIn("python-version: '3.11.13'", workflow)
            self.assertIn("requirements.lock", workflow)
            self.assertIn("pip==25.1.1", workflow)
            self.assertIn("dependency_lock.py", workflow)
        self.assertIn("python -m pip check", self.all_workflows)

    def test_manual_inputs_and_schedule_are_explicit(self):
        self.assertIn("cron: '0 8 * * 1'", self.collection)
        for value in (
            "collection_scope:",
            "options: [full, single_pair]",
            "vehicle_key:",
            "options: [ford_f350, ram_3500, subaru_forester, honda_odyssey, kia_carnival]",
            "source:",
            "options: [autotrader, kijiji]",
            "publish_generated_data:",
            "anomaly_policy:",
            "options: [enforce, report_only]",
            "operator_note:",
        ):
            self.assertIn(value, self.collection)
        self.assertNotIn("config_f150.json", self.collection)
        self.assertNotIn("config_tundra.json", self.collection)

    def test_governed_plan_and_single_pair_remain_narrow(self):
        for value in (
            "workflow_control.py plan",
            "workflow_control.py validate-single-pair",
            "--fail-on-unhealthy",
            "smoke-artifact",
            "retention-days: 7",
            "autotrader_run.py",
            "kijiji_run.py",
        ):
            self.assertIn(value, self.collection)
        self.assertIn("if: env.COLLECTION_SCOPE == 'single_pair'", self.collection)
        self.assertIn("if: env.COLLECTION_SCOPE == 'full'", self.collection)

    def test_health_anomaly_retention_and_publish_gates_are_ordered(self):
        for value in (
            "phase1_pipeline.py check-health",
            "workflow_anomalies.py build",
            "workflow_anomalies.py check",
            "storage_retention.py apply",
            "storage_retention.py verify",
            "storage_retention.py validate-staged",
            "generated_data_publish.py prepare",
            "generated_data_publish.py verify-staged",
            "git diff --cached --check",
            "remote_sha=$(git rev-parse",
        ):
            self.assertIn(value, self.collection)
        health = self.collection.index("Fail visibly on unhealthy source evidence")
        anomaly = self.collection.index("Enforce critical anomaly policy")
        retention = self.collection.index("Apply and verify bounded storage retention")
        publish = self.collection.index("Commit and push governed generated data")
        self.assertLess(health, anomaly)
        self.assertLess(anomaly, retention)
        self.assertLess(retention, publish)

    def test_failure_artifacts_are_short_lived_and_pinned(self):
        self.assertIn("structured-test-failure-${{ github.run_id }}", self.ci)
        self.assertIn("generated-data-validation-failure-${{ github.run_id }}", self.generated)
        self.assertIn("full-run-diagnostics-${{ github.run_id }}", self.collection)
        self.assertIn("retention-days: 3", self.ci)
        self.assertIn("retention-days: 3", self.generated)
        self.assertIn("retention-days: 14", self.collection)

    def test_no_unpinned_action_reference_remains(self):
        self.assertEqual(re.findall(r"uses:\s+actions/[^@\s]+@v\d+", self.all_workflows), [])


if __name__ == "__main__":
    unittest.main()
