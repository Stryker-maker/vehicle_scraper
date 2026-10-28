"""Regression tests for successful rollback after a partial collection-isolation move."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from phase1_common import utc_now
from workflow_anomalies import isolate_anomalous_collections


class SuccessfulIsolationRollbackTests(unittest.TestCase):
    def test_later_move_failure_restores_prior_moves_without_partial_quarantine(self):
        """A failed batch must restore moved files when rollback itself succeeds."""
        run_id = "run_rollback_success_123"
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)

        vehicle_key = "ford_f150"
        source = "autotrader"
        latest = (
            root / "data" / vehicle_key / "latest"
            / f"{vehicle_key}_{source}_latest.csv"
        )
        archive = (
            root / "data" / vehicle_key / source
            / f"{vehicle_key}_{source}_2026-08-01_00-00-00.csv"
        )
        status_path = (
            root / "data" / vehicle_key / "run_status" / f"{source}_latest.json"
        )
        for path in (latest, archive, status_path):
            path.parent.mkdir(parents=True, exist_ok=True)

        latest.write_text("latest_content", encoding="utf-8")
        archive.write_text("archive_content", encoding="utf-8")
        status_path.write_text(
            json.dumps({
                "run_id": run_id,
                "started_at_utc": utc_now(),
                "latest_output": str(latest.relative_to(root)),
                "archive_output": str(archive.relative_to(root)),
            }),
            encoding="utf-8",
        )

        report = {
            "run_id": run_id,
            "isolated_collections": [
                {"vehicle_key": vehicle_key, "source": source}
            ],
        }
        original_replace = Path.replace
        replace_calls = 0

        def fail_second_move_then_allow_rollback(
            path: Path, target: Path
        ) -> Path:
            nonlocal replace_calls
            replace_calls += 1
            if replace_calls == 2:
                raise OSError("Simulated second move failure")
            return original_replace(path, target)

        with (
            patch.object(
                Path, "replace", new=fail_second_move_then_allow_rollback
            ),
            self.assertRaisesRegex(
                RuntimeError, "Atomic anomaly isolation failed during file movement"
            ) as error,
        ):
            isolate_anomalous_collections(root=root, report=report)

        self.assertNotIn("Rollback failed to restore paths", str(error.exception))
        self.assertEqual(
            replace_calls, 3,
            "expected first move, failed second move, successful rollback",
        )

        # Both original files must be restored byte-for-byte at their original paths.
        self.assertTrue(latest.is_file())
        self.assertEqual(latest.read_text(encoding="utf-8"), "latest_content")
        self.assertTrue(archive.is_file())
        self.assertEqual(archive.read_text(encoding="utf-8"), "archive_content")

        # The quarantine directory may exist, but no partial quarantine file may remain.
        quarantine_dir = (
            root / "data" / vehicle_key / "quarantine" / source / run_id
        )
        quarantined_files = (
            [path for path in quarantine_dir.rglob("*") if path.is_file()]
            if quarantine_dir.exists()
            else []
        )
        self.assertEqual(quarantined_files, [])
        self.assertEqual(report["isolated_collections"], [])
        failures = [
            anomaly for anomaly in report.get("anomalies", [])
            if anomaly.get("code") == "collection_isolation_failed"
        ]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["severity"], "critical")


if __name__ == "__main__":
    unittest.main()
