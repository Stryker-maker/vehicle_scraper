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
            """Fail the second move while allowing the rollback move to succeed."""
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

    def test_existing_quarantine_destination_is_not_overwritten(self):
        """A same-run retry must preserve existing quarantine evidence and fail preflight."""
        run_id = "run_collision_123"
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
        quarantine_dir = (
            root / "data" / vehicle_key / "quarantine" / source / run_id
        )
        existing_quarantine = (
            quarantine_dir / f"{vehicle_key}_{source}_latest_quarantined.csv"
        )
        for path in (latest, archive, status_path, existing_quarantine):
            path.parent.mkdir(parents=True, exist_ok=True)

        latest.write_text("new_latest_content", encoding="utf-8")
        archive.write_text("archive_content", encoding="utf-8")
        existing_quarantine.write_text(
            "prior_quarantine_evidence", encoding="utf-8"
        )
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
            "isolated_collections": [{"vehicle_key": vehicle_key, "source": source}],
        }

        with self.assertRaisesRegex(ValueError, "Quarantine destination already exists"):
            isolate_anomalous_collections(root=root, report=report)

        self.assertEqual(latest.read_text(encoding="utf-8"), "new_latest_content")
        self.assertEqual(archive.read_text(encoding="utf-8"), "archive_content")
        self.assertEqual(
            existing_quarantine.read_text(encoding="utf-8"),
            "prior_quarantine_evidence",
        )
        self.assertEqual(report["isolated_collections"], [])
        failures = [
            anomaly for anomaly in report.get("anomalies", [])
            if anomaly.get("code") == "collection_isolation_failed"
        ]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["severity"], "critical")
        self.assertIn("Quarantine destination already exists", failures[0]["message"])

    def test_rollback_failure_reports_unrestored_paths_and_does_not_claim_isolation(self):
        """If both a move and its rollback fail, report the evidence's actual locations."""
        run_id = "run_rollback_failure_123"
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
            "isolated_collections": [{"vehicle_key": vehicle_key, "source": source}],
        }

        original_replace = Path.replace
        replace_calls = 0
        def fail_second_move_and_rollback(
            path: Path, target: Path
        ) -> Path:
            nonlocal replace_calls
            replace_calls += 1
            if replace_calls in (2, 3):
                raise OSError(
                    "Simulated second move failure" if replace_calls == 2
                    else "Simulated rollback failure"
                )
            return original_replace(path, target)

        with (
            patch.object(Path, "replace", new=fail_second_move_and_rollback),
            self.assertRaisesRegex(
                RuntimeError, "Rollback failed to restore paths"
            ) as error,
        ):
            isolate_anomalous_collections(root=root, report=report)

        quarantine_dir = root / "data" / vehicle_key / "quarantine" / source / run_id
        quarantined_latest = (
            quarantine_dir / f"{vehicle_key}_{source}_latest_quarantined.csv"
        )
        self.assertIn(f"{quarantined_latest} -> {latest}", str(error.exception))
        self.assertEqual(replace_calls, 3)
        # Rollback failed: latest evidence remains in quarantine; archive move never completed.
        self.assertFalse(latest.exists())
        self.assertEqual(
            quarantined_latest.read_text(encoding="utf-8"), "latest_content"
        )
        self.assertEqual(archive.read_text(encoding="utf-8"), "archive_content")
        self.assertEqual(report["isolated_collections"], [])
        failures = [
            anomaly for anomaly in report.get("anomalies", [])
            if anomaly.get("code") == "collection_isolation_failed"
        ]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["severity"], "critical")
        self.assertIn("Rollback failed to restore paths", failures[0]["message"])


if __name__ == "__main__":
    unittest.main()
