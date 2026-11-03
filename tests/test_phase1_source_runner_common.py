import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

import phase1_source_runner_common as common


class SourceRunnerCommonTests(unittest.TestCase):

    def test_build_source_evidence_and_identity_success_and_failure_paths(self):
        evidence = {
            "reconciled": True,
            "pagination_complete": True,
            "accepted_records": 2,
            "artifacts": {"accepted": "accepted.csv"},
            "source_adapter_artifacts": {"records": "records.jsonl"},
        }
        identity = {"observed_current_count": 2, "artifacts": {"current": "current.jsonl"}}
        builder = Mock(return_value=evidence)
        failures = []
        with patch.object(
            common, "update_source_identity_lifecycle", return_value=identity
        ) as update_identity:
            result = common.build_source_evidence_and_identity(
                root=Path("."),
                config={"vehicle_key": "vehicle"},
                source="autotrader",
                active_run="run-1",
                completed_at="2026-11-03T00:00:00Z",
                fresh=True,
                validation={"schema_valid": True},
                current_rows=2,
                failures=failures,
                adapter_schema_version=3,
                evidence_schema_version=2,
                build_canonical_evidence=builder,
            )
        self.assertEqual(result, (evidence, None, identity, None))
        self.assertEqual(failures, [])
        update_identity.assert_called_once()
        self.assertEqual(update_identity.call_args.kwargs["source"], "autotrader")

        failed_build = Mock(side_effect=RuntimeError("canonical failure"))
        failures = []
        result = common.build_source_evidence_and_identity(
            root=Path("."),
            config={"vehicle_key": "vehicle"},
            source="kijiji",
            active_run="run-2",
            completed_at="2026-11-03T00:00:00Z",
            fresh=True,
            validation={"schema_valid": True},
            current_rows=2,
            failures=failures,
            adapter_schema_version=4,
            evidence_schema_version=2,
            build_canonical_evidence=failed_build,
            additional_evidence_defaults={"query_location_count": 0},
        )
        self.assertIn("canonical failure", result[1])
        self.assertEqual(failures, ["canonical_evidence_failed"])
        self.assertEqual(result[0]["query_location_count"], 0)

        stale_builder = Mock()
        result = common.build_source_evidence_and_identity(
            root=Path("."),
            config={"vehicle_key": "vehicle"},
            source="kijiji",
            active_run="run-3",
            completed_at="2026-11-03T00:00:00Z",
            fresh=False,
            validation={"schema_valid": True},
            current_rows=0,
            failures=[],
            adapter_schema_version=4,
            evidence_schema_version=2,
            build_canonical_evidence=stale_builder,
        )
        stale_builder.assert_not_called()
        self.assertIsNone(result[1])
        self.assertEqual(result[0]["accepted_records"], 0)

    def test_build_source_evidence_blocks_identity_on_reconciliation_failure(self):
        evidence = {
            "reconciled": False,
            "pagination_complete": True,
            "accepted_records": 1,
            "artifacts": {"accepted": "accepted.csv"},
            "source_adapter_artifacts": {},
        }
        failures = []
        with patch.object(common, "update_source_identity_lifecycle") as update_identity:
            result = common.build_source_evidence_and_identity(
                root=Path("."),
                config={"vehicle_key": "vehicle"},
                source="kijiji",
                active_run="run-1",
                completed_at="2026-11-03T00:00:00Z",
                fresh=True,
                validation={"schema_valid": True},
                current_rows=1,
                failures=failures,
                adapter_schema_version=4,
                evidence_schema_version=2,
                build_canonical_evidence=Mock(return_value=evidence),
            )
        self.assertIn("evidence_reconciliation_failed", failures)
        update_identity.assert_not_called()
        self.assertEqual(result[2]["observed_current_count"], 0)


    def test_finalize_source_status_from_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "latest.csv"
            context = {
                "root": root,
                "config": {"vehicle_key": "vehicle"},
                "active_run": "run-1",
                "started_ns": 100,
                "rec_before_sig": None,
                "archive_before_sigs": {},
                "fresh": True,
                "output_path": output,
                "status_name": "success",
                "identity_error": None,
                "evidence": {"reconciled": True},
            }
            status = {}
            with patch.object(
                common,
                "validate_invocation_archive_output",
                return_value="data/vehicle/autotrader/archive.csv",
            ):
                common.finalize_source_status_from_context(
                    status, context, source="autotrader"
                )
        self.assertEqual(status["latest_output"], "latest.csv")
        self.assertEqual(
            status["archive_output"], "data/vehicle/autotrader/archive.csv"
        )
        self.assertEqual(status["evidence_reconciliation_status"], "reconciled")
        self.assertEqual(status["identity_lifecycle_status"], "updated")

    def test_print_source_summary(self):
        status = {
            "fetched_record_count": 10,
            "accepted_record_count": 4,
            "rejected_record_count": 6,
            "parse_failure_count": 1,
            "identity_lifecycle_status": "updated",
            "identity_new_listing_count": 2,
            "identity_reappeared_listing_count": 1,
        }
        output = StringIO()
        with redirect_stdout(output):
            common.print_source_summary("vehicle", "kijiji", "success", status)
        self.assertIn("[vehicle:kijiji] success", output.getvalue())
        self.assertIn("fetched=10", output.getvalue())
        self.assertIn("reappeared=1", output.getvalue())


    def test_source_runtime_contract_fields(self):
        fields = common.source_runtime_contract_fields({"config_isolated": True})
        self.assertEqual(fields["runtime_config_projection"], "direct_schema_v2")
        self.assertFalse(fields["approved_config_contains_legacy_controls"])
        self.assertIsNone(fields["configured_max_results"])
        self.assertEqual(fields["effective_max_results"], "unbounded")
        self.assertTrue(fields["row_cap_disabled"])
        self.assertTrue(fields["config_isolated"])
        self.assertTrue(fields["legacy_source_ranking_disabled"])
        self.assertFalse(fields["legacy_price_history_active"])
        self.assertEqual(
            fields["legacy_price_history_status"],
            "retired_not_used_by_supported_output",
        )


    def test_source_execution_outcome_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "latest.csv"
            output.write_text("data", encoding="utf-8")
            fields = common.source_execution_outcome_fields(
                {
                    "command": ["python", "adapter.py"],
                    "collection_scope": "full",
                    "started_at": "start",
                    "returncode": 0,
                    "timed_out": False,
                    "timeout_seconds": 90,
                    "output_path": output,
                    "root": root,
                    "fresh": True,
                    "stdout": "out",
                    "stderr": "err",
                }
            )
        self.assertEqual(fields["command"], ["python", "adapter.py"])
        self.assertEqual(fields["collection_scope"], "full")
        self.assertEqual(fields["started_at_utc"], "start")
        self.assertEqual(fields["exit_code"], 0)
        self.assertFalse(fields["timed_out"])
        self.assertEqual(fields["timeout_seconds"], 90)
        self.assertEqual(fields["expected_output"], "latest.csv")
        self.assertTrue(fields["output_exists"])
        self.assertTrue(fields["output_updated_this_run"])
        self.assertEqual(fields["stdout_tail"], "out")
        self.assertEqual(fields["stderr_tail"], "err")


    def test_source_evidence_status_fields(self):
        fields = common.source_evidence_status_fields(
            {
                "stale_rows": 2,
                "observed_rows": 5,
                "evidence": {
                    "fetched_record_scope": "complete",
                    "source_fetch_completeness": "complete",
                    "pagination_complete": True,
                    "page_request_count": 3,
                    "request_attempt_count": 4,
                    "successful_page_count": 3,
                    "failed_page_count": 1,
                    "normalized_records": 5,
                    "source_adapter_artifacts": {"records": "records.jsonl"},
                },
                "identity": {
                    "artifacts": {"current": "current.jsonl"},
                    "observed_current_count": 5,
                    "transition_event_count": 2,
                },
                "evidence_error": None,
                "identity_error": None,
            }
        )
        self.assertTrue(fields["stale_output_available"])
        self.assertEqual(fields["observed_file_row_count"], 5)
        self.assertEqual(fields["fetched_record_scope"], "complete")
        self.assertEqual(fields["source_fetch_completeness"], "complete")
        self.assertTrue(fields["pagination_complete"])
        self.assertEqual(fields["page_request_count"], 3)
        self.assertEqual(fields["request_attempt_count"], 4)
        self.assertEqual(fields["successful_page_count"], 3)
        self.assertEqual(fields["failed_page_count"], 1)
        self.assertEqual(fields["normalized_record_count"], 5)
        self.assertIn("fetched_records =", fields["evidence_reconciliation_equation"])
        self.assertEqual(fields["source_adapter_artifacts"], {"records": "records.jsonl"})
        self.assertEqual(fields["identity_lifecycle_artifacts"], {"current": "current.jsonl"})
        self.assertEqual(fields["identity_observed_current_count"], 5)
        self.assertEqual(fields["identity_transition_event_count"], 2)


    def test_source_status_metrics_shared_contract(self):
        metrics = common.source_status_metrics(
            current_rows=3,
            stale_rows=2,
            fetched_record_count=5,
            accepted_record_count=3,
            rejected_record_count=2,
            parse_failure_count=0,
            identity_tracked_listing_count=4,
            identity_new_listing_count=1,
            identity_reappeared_listing_count=1,
            identity_missing_listing_count=2,
            identity_retired_listing_count=1,
            failure_reasons=["warning"],
        )
        self.assertEqual(metrics["row_count"], 3)
        self.assertEqual(metrics["current_row_count"], 3)
        self.assertEqual(metrics["stale_row_count"], 2)
        self.assertEqual(metrics["fetched_record_count"], 5)
        self.assertEqual(metrics["accepted_record_count"], 3)
        self.assertEqual(metrics["rejected_record_count"], 2)
        self.assertEqual(metrics["parse_failure_count"], 0)
        self.assertEqual(metrics["identity_tracked_listing_count"], 4)
        self.assertEqual(metrics["identity_new_listing_count"], 1)
        self.assertEqual(metrics["identity_reappeared_listing_count"], 1)
        self.assertEqual(metrics["identity_missing_listing_count"], 2)
        self.assertEqual(metrics["identity_retired_listing_count"], 1)
        self.assertEqual(metrics["failure_reasons"], ["warning"])

    def test_source_status_metrics_from_context(self):
        metrics = common.source_status_metrics_from_context(
            {
                "current_rows": 3,
                "stale_rows": 2,
                "evidence": {
                    "fetched_records": 5,
                    "accepted_records": 3,
                    "rejected_records": 2,
                    "parse_failures": 0,
                },
                "identity": {
                    "tracked_listing_count": 4,
                    "new_listing_count": 1,
                    "reappeared_listing_count": 1,
                    "missing_listing_count": 2,
                    "retired_listing_count": 1,
                },
                "failures": ["warning"],
            }
        )
        self.assertEqual(metrics["accepted_record_count"], 3)
        self.assertEqual(metrics["identity_retired_listing_count"], 1)
        self.assertEqual(metrics["failure_reasons"], ["warning"])


    def test_source_schema_version_fields(self):
        fields = common.source_schema_version_fields(
            status_schema_version=8,
            config_schema_version=2,
            evidence_schema_version=3,
            adapter_schema_version=4,
            identity_schema_version=5,
        )
        self.assertEqual(fields["schema_version"], 8)
        self.assertEqual(fields["configuration_schema_version"], 2)
        self.assertEqual(fields["canonical_evidence_schema_version"], 3)
        self.assertEqual(fields["source_adapter_schema_version"], 4)
        self.assertEqual(fields["identity_lifecycle_schema_version"], 5)


    def test_source_status_identity_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "config.json"
            fields = common.source_status_identity_fields(
                {
                    "active_run": "run-1",
                    "config": {"vehicle_key": "vehicle"},
                    "compatibility_identity": {"vehicle": "vehicle"},
                    "compatibility_fingerprint": "fingerprint",
                    "config_path": config_path,
                    "root": root,
                    "completed_at": "completed",
                    "status_name": "success",
                },
                source="autotrader",
            )
        self.assertEqual(fields["run_id"], "run-1")
        self.assertEqual(fields["vehicle_key"], "vehicle")
        self.assertEqual(fields["source"], "autotrader")
        self.assertEqual(fields["compatibility_identity"], {"vehicle": "vehicle"})
        self.assertEqual(fields["compatibility_fingerprint"], "fingerprint")
        self.assertEqual(fields["config_path"], "config.json")
        self.assertEqual(fields["completed_at_utc"], "completed")
        self.assertEqual(fields["execution_status"], "success")
        self.assertEqual(fields["collection_status"], "success")


    def test_source_validation_quality_fields(self):
        fields = common.source_validation_quality_fields(
            {"schema_valid": True, "row_count": 99},
            {"quality_status": "acceptable"},
            3,
        )
        self.assertTrue(fields["schema_valid"])
        self.assertEqual(fields["row_count"], 3)
        self.assertEqual(fields["quality_status"], "acceptable")

    def test_collection_scope_validation(self):
        common.validate_collection_scope("full", ("full", "single_pair"))
        with self.assertRaisesRegex(ValueError, "Unsupported collection scope"):
            common.validate_collection_scope("invalid", ("full", "single_pair"))

    def test_snapshot_archive_signatures(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_dir = Path(directory)
            self.assertEqual(common.snapshot_archive_signatures(archive_dir), {})
            archive = archive_dir / "run.csv"
            archive.write_text("a,b\\n1,2\\n", encoding="utf-8")
            signatures = common.snapshot_archive_signatures(archive_dir)
            self.assertEqual(set(signatures), {archive.resolve()})
            self.assertIsNotNone(signatures[archive.resolve()])

    def test_restore_config_if_mutated(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            original = b'{"value":1}'
            config.write_bytes(original)
            self.assertTrue(common.restore_config_if_mutated(config, original, []))
            config.write_bytes(b'{"value":2}')
            failures = []
            self.assertFalse(
                common.restore_config_if_mutated(config, original, failures)
            )
            self.assertEqual(failures, ["approved_config_mutated"])
            self.assertEqual(config.read_bytes(), original)


    def test_snapshot_reconciliation_signature(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.json"
            self.assertIsNone(common.snapshot_reconciliation_signature(missing))
            existing = Path(directory) / "reconciliation.json"
            existing.write_text("{}", encoding="utf-8")
            stat = existing.stat()
            self.assertEqual(
                common.snapshot_reconciliation_signature(existing),
                (stat.st_mtime_ns, stat.st_size),
            )

    def test_resolve_collector_command_preserves_defaulting_behavior(self):
        self.assertEqual(
            common.resolve_collector_command(None, ["python", "adapter.py"]),
            ["python", "adapter.py"],
        )
        self.assertEqual(
            common.resolve_collector_command([], ["python", "adapter.py"]),
            ["python", "adapter.py"],
        )
        self.assertEqual(
            common.resolve_collector_command(["python", "custom.py"], ["unused"]),
            ["python", "custom.py"],
        )

    def test_restore_identity_only_for_unhealthy_status(self):
        restore = Mock()
        common.restore_identity_if_unhealthy("success", {"snapshot": 1}, restore)
        restore.assert_not_called()
        common.restore_identity_if_unhealthy("degraded", {"snapshot": 1}, restore)
        self.assertEqual(restore.call_count, 1)
        self.assertEqual(restore.call_args.args[0], {"snapshot": 1})

    def test_execute_source_collector_success_and_timeout(self):
        completed = subprocess.CompletedProcess(["collector"], 0, "ok\\n", "")
        with patch.object(common.subprocess, "run", return_value=completed):
            result = common.execute_source_collector(
                ["collector"], root=Path("."), timeout_seconds=10
            )
        self.assertEqual(result, (0, False, "ok\\n", ""))

        timeout = subprocess.TimeoutExpired(
            ["collector"], 10, output=b"partial", stderr=b"timeout"
        )
        with patch.object(common.subprocess, "run", side_effect=timeout):
            result = common.execute_source_collector(
                ["collector"], root=Path("."), timeout_seconds=10
            )
        self.assertEqual(result, (None, True, "partial", "timeout"))

    def test_source_status_decision_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "latest.csv"
            with patch.object(
                common,
                "validate_invocation_archive_output",
                return_value="data/vehicle/kijiji/archive.csv",
            ) as validate_archive:
                fields = common.source_status_decision_fields(
                    root=root,
                    config={"vehicle_key": "vehicle"},
                    source="kijiji",
                    active_run="run-1",
                    started_ns=100,
                    rec_before_sig=None,
                    archive_before_sigs={},
                    fresh=True,
                    output_path=output,
                    status_name="success",
                    identity_error=None,
                    evidence={"reconciled": True},
                )
                validate_archive.assert_called_once()
            self.assertEqual(fields["latest_output"], "latest.csv")
            self.assertEqual(
                fields["archive_output"], "data/vehicle/kijiji/archive.csv"
            )
            self.assertEqual(fields["evidence_reconciliation_status"], "reconciled")
            self.assertEqual(fields["identity_lifecycle_status"], "updated")

            stale = common.source_status_decision_fields(
                root=root,
                config={"vehicle_key": "vehicle"},
                source="kijiji",
                active_run="run-1",
                started_ns=100,
                rec_before_sig=None,
                archive_before_sigs={},
                fresh=False,
                output_path=output,
                status_name="degraded",
                identity_error="failed",
                evidence={"reconciled": False},
            )
            self.assertIsNone(stale["latest_output"])
            self.assertIsNone(stale["archive_output"])
            self.assertEqual(stale["evidence_reconciliation_status"], "not_reconciled")
            self.assertEqual(stale["identity_lifecycle_status"], "not_updated")

    def test_collector_status_name(self):
        self.assertEqual(common.collector_status_name(True, 0, []), "timed_out")
        self.assertEqual(common.collector_status_name(False, 2, []), "failed")
        self.assertEqual(
            common.collector_status_name(False, 0, ["warning"]), "degraded"
        )
        self.assertEqual(common.collector_status_name(False, 0, []), "success")

    def test_quality_report(self):
        with patch.object(
            common, "analyze_csv_quality", return_value={"quality": "ok"}
        ) as analyze:
            self.assertEqual(
                common.collector_quality_report(
                    Path("latest.csv"), "kijiji", True, True, 0
                ),
                {"quality": "ok"},
            )
            analyze.assert_called_once_with(Path("latest.csv"), "kijiji")
        self.assertEqual(
            common.collector_quality_report(
                Path("latest.csv"), "kijiji", False, True, 2
            ),
            {
                "data_quality_status": "not_evaluated_stale_output",
                "quality_warning_rows": 0,
                "quality_warning_count": 0,
                "quality_warning_summary": {},
            },
        )
        self.assertEqual(
            common.collector_quality_report(
                Path("latest.csv"), "kijiji", False, False, 0
            )[
                "data_quality_status"
            ],
            "not_evaluated",
        )

    def test_assess_source_output_fresh_and_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.csv"
            path.write_text("data", encoding="utf-8")
            valid = {"row_count": 3, "schema_valid": True}
            with (
                patch.object(
                    common,
                    "file_signature",
                    side_effect=[(200, 30), (200, 30)],
                ),
                patch.object(common, "validate_csv", return_value=valid),
            ):
                fresh = common.assess_source_output(
                    path,
                    before_signature=(100, 30),
                    started_ns=150,
                    returncode=0,
                    timed_out=False,
                )
                stale = common.assess_source_output(
                    path,
                    before_signature=(200, 30),
                    started_ns=300,
                    returncode=0,
                    timed_out=False,
                )
        self.assertEqual(fresh[:5], (True, valid, 3, 3, 0))
        self.assertEqual(stale[:5], (False, valid, 3, 0, 3))
        self.assertIn("no_fresh_output", stale[5])

    def test_assess_source_output_reports_timeout_and_invalid_empty_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.csv"
            path.write_text("", encoding="utf-8")
            invalid = {"row_count": 0, "schema_valid": False}
            with (
                patch.object(common, "file_signature", return_value=(200, 30)),
                patch.object(common, "validate_csv", return_value=invalid),
            ):
                result = common.assess_source_output(
                    path,
                    before_signature=None,
                    started_ns=150,
                    returncode=None,
                    timed_out=True,
                )
        self.assertTrue(result[0])
        self.assertIn("collector_timed_out", result[5])
        self.assertIn("invalid_output_schema", result[5])
        self.assertIn("empty_output", result[5])


if __name__ == "__main__":
    unittest.main()
