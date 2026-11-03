import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import phase1_source_runner_common as common


class SourceRunnerCommonTests(unittest.TestCase):
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
            self.assertTrue(common.restore_config_if_mutated(config, original))
            config.write_bytes(b'{"value":2}')
            self.assertFalse(common.restore_config_if_mutated(config, original))
            self.assertEqual(config.read_bytes(), original)

    def test_restore_identity_only_for_unhealthy_status(self):
        restore = Mock()
        common.restore_identity_if_unhealthy("success", {"snapshot": 1}, restore)
        restore.assert_not_called()
        common.restore_identity_if_unhealthy("degraded", {"snapshot": 1}, restore)
        restore.assert_called_once_with({"snapshot": 1})

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
