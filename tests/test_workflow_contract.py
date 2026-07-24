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
            "options: [ford_f350, ram_3500, subaru_forester, honda_odyssey, kia_carnival, ford_f150]",
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
        self.assertGreaterEqual(self.collection.count("--cadence weekly"), 3)

    def test_f350_buyer_intelligence_is_ci_compiled_validated_and_scope_gated(self):
        self.assertIn("f350_buyer_intelligence.py", self.ci)
        self.assertIn("f350_buyer_validation.py", self.ci)
        for value in (
            "Build and validate F-350 buyer intelligence for narrow validation",
            "if: env.COLLECTION_SCOPE == 'single_pair' && env.VEHICLE_KEY == 'ford_f350'",
            "--source \"$SELECTED_SOURCE\"",
            "--overrides f350_owner_overrides.json",
            "f350_buyer_validation.py",
            "data/$VEHICLE_KEY/buyer_intelligence",
            "Build and validate transparent F-350 buyer intelligence",
            "--source autotrader",
            "--source kijiji",
            "data/ford_f350/buyer_intelligence/market_summary_latest.md",
        ):
            self.assertIn(value, self.collection)
        self.assertNotIn("ram_3500/buyer_intelligence", self.collection)
        self.assertNotIn("subaru_forester/buyer_intelligence", self.collection)
        self.assertNotIn("honda_odyssey/buyer_intelligence", self.collection)
        self.assertNotIn("kia_carnival/buyer_intelligence", self.collection)

    def test_secondary_purpose_outputs_are_profile_gated_and_artifact_backed(self):
        self.assertIn("purpose_outputs.py", self.ci)
        self.assertIn("purpose_output_validation.py", self.ci)
        for value in (
            "Build and validate secondary-purpose output for narrow validation",
            "env.VEHICLE_KEY == 'ram_3500' ||",
            "--inputs purpose_inputs.json",
            "data/$VEHICLE_KEY/purpose_output",
            "Build and validate secondary-purpose outputs",
            "config_ram3500.json",
            "config_forester.json",
            "config_odyssey.json",
            "config_carnival.json",
            "data/ram_3500/purpose_output/",
            "data/subaru_forester/purpose_output/",
            "data/honda_odyssey/purpose_output/",
            "data/kia_carnival/purpose_output/",
        ):
            self.assertIn(value, self.collection)
        self.assertNotIn("data/ford_f350/purpose_output", self.collection)
        self.assertNotIn("data/ford_f150/purpose_output", self.collection)
        self.assertNotIn("config_f150.json", self.collection)
        self.assertNotIn("config_tundra.json", self.collection)

    def test_f150_is_manual_nonpublishing_and_profile_isolated(self):
        for value in (
            "ford_f150",
            "Write optional-curiosity manual summary",
            "optional-curiosity-summary.md",
            "No purchase need, rank, score, appraisal, or recommendation is implied.",
            "env.VEHICLE_KEY == 'ford_f150'",
        ):
            self.assertIn(value, self.collection)
        self.assertIn(
            "env.COLLECTION_SCOPE == 'full' && env.PUBLISH_GENERATED_DATA == 'true'",
            self.collection,
        )
        self.assertNotIn("config_tundra.json", self.collection)

    def test_health_purpose_anomaly_retention_and_publish_gates_are_ordered(self):
        for value in (
            "phase1_pipeline.py check-health",
            "workflow_anomalies.py build",
            "workflow_anomalies.py check",
            "storage_retention.py apply",
            "storage_retention.py verify",
            "--cadence weekly",
            "storage_retention.py validate-staged",
            "generated_data_publish.py prepare",
            "generated_data_publish.py verify-staged",
            "git diff --cached --check",
            "remote_sha=$(git rev-parse",
        ):
            self.assertIn(value, self.collection)
        health = self.collection.index("Fail visibly on unhealthy source evidence")
        buyer = self.collection.index(
            "Build and validate transparent F-350 buyer intelligence"
        )
        purpose = self.collection.index("Build and validate secondary-purpose outputs")
        anomaly = self.collection.index("Enforce critical anomaly policy")
        retention = self.collection.index("Apply and verify bounded storage retention")
        publish = self.collection.index("Commit and push governed generated data")
        self.assertLess(health, buyer)
        self.assertLess(buyer, purpose)
        self.assertLess(purpose, anomaly)
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
