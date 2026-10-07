from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from autotrader_history import write_csv_outputs as write_autotrader_csv_outputs
from kijiji_history import write_csv_outputs as write_kijiji_csv_outputs
from purpose_outputs import _write_csv as write_purpose_csv


class CsvLineTerminatorTests(unittest.TestCase):
    @staticmethod
    def _git_env(root: Path) -> dict[str, str]:
        env = os.environ.copy()
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["HOME"] = str(root / "home")
        env["XDG_CONFIG_HOME"] = str(root / "config")
        return env

    @staticmethod
    def _git_executable() -> str:
        executable = shutil.which("git")
        if executable is None:
            raise RuntimeError("git executable is required for CSV publication safety tests")
        return executable

    def _assert_staged_git_diff_clean(self, root: Path) -> None:
        env = self._git_env(root)
        git = self._git_executable()
        subprocess.run(
            [git, "-c", "core.autocrlf=false", "init"],
            cwd=root,
            check=True,
            capture_output=True,
            env=env,
        )
        subprocess.run(
            [git, "add", "data"],
            cwd=root,
            check=True,
            capture_output=True,
            env=env,
        )
        check = subprocess.run(
            [git, "diff", "--cached", "--check"],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def _assert_publication_safe(self, writer, source: str) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = {"vehicle_key": "test_vehicle"}
            rows = [
                {
                    "year": "2020",
                    "make": "Ford",
                    "model": "F-350",
                    "trim": "Lariat",
                    "price": "65000",
                    "mileage": "100000",
                    "location": "Calgary,\rAB",
                    "source": source,
                }
            ]

            archive, latest = writer(root, config, rows)
            outputs = (archive, latest)
            for output in outputs:
                raw = output.read_bytes()
                self.assertNotIn(b"\r\n", raw)
                self.assertIn(b"\r", raw)
                with output.open("r", encoding="utf-8", newline="") as handle:
                    parsed = list(csv.reader(handle))
                self.assertGreaterEqual(len(parsed), 2)
                header = parsed[0]
                values = parsed[1]
                self.assertEqual(values[header.index("location")], "Calgary,\rAB")
                self.assertEqual(values[header.index("price")], "65000")

            self._assert_staged_git_diff_clean(root)\n

    def _assert_direct_csv_writer_publication_safe(self, writer) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "data" / "test_vehicle" / "purpose_output" / "value_monitor" / "comparables_latest.csv"
            records = [
                {
                    "vehicle_key": "test_vehicle",
                    "source": "AutoTrader",
                    "price_cad": 65000,
                    "location": "Calgary,\rAB",
                    "subject_comparability_reasons": ["year_match", "model_match"],
                }
            ]
            writer(
                output,
                (
                    "vehicle_key",
                    "source",
                    "price_cad",
                    "location",
                    "subject_comparability_reasons",
                ),
                records,
            )

            raw = output.read_bytes()
            self.assertNotIn(b"\r\n", raw)
            self.assertIn(b"\r", raw)
            with output.open("r", encoding="utf-8", newline="") as handle:
                parsed = list(csv.DictReader(handle))
            self.assertEqual(parsed[0]["price_cad"], "65000")
            self.assertEqual(parsed[0]["location"], "Calgary,\rAB")
            self.assertEqual(
                json.loads(parsed[0]["subject_comparability_reasons"]),
                ["year_match", "model_match"],
            )

            env = self._git_env(root)
            subprocess.run(
                ["git", "-c", "core.autocrlf=false", "init"],
                cwd=root,
                check=True,
                capture_output=True,
                env=env,
            )
            subprocess.run(
                ["git", "add", "data"],
                cwd=root,
                check=True,
                capture_output=True,
                env=env,
            )
            check = subprocess.run(
                ["git", "diff", "--cached", "--check"],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
                env=env,
            )
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def test_purpose_output_csv_is_lf_and_git_diff_check_clean(self):
        self._assert_direct_csv_writer_publication_safe(write_purpose_csv)

    def test_autotrader_csv_is_lf_and_git_diff_check_clean(self):
        self._assert_publication_safe(write_autotrader_csv_outputs, "AutoTrader")

    def test_kijiji_csv_is_lf_and_git_diff_check_clean(self):
        self._assert_publication_safe(write_kijiji_csv_outputs, "Kijiji")

    def test_buyer_intelligence_csv_preserves_bare_cr(self):
        import f350_buyer_intelligence as buyer

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            overrides_path = root / "overrides.json"
            overrides_path.write_text(
                json.dumps({
                    "schema_version": 1,
                    "vehicle_key": "ford_f350",
                    "overrides": {},
                }),
                encoding="utf-8",
            )
            listing = {
                "vehicle_key": "ford_f350",
                "source": "autotrader",
                "canonical_listing_id": "listing-1",
                "trim_claim": "Lariat\rSpecial",
            }
            with mock.patch.object(
                buyer, "load_vehicle_config", return_value={"vehicle_key": "ford_f350"}
            ), mock.patch.object(
                buyer,
                "_collect_available_f350_source_bundles",
                return_value=([], ["autotrader"]),
            ), mock.patch.object(
                buyer,
                "_generate_f350_investigation_outputs",
                return_value=([listing], [{"canonical_listing_id": "listing-1", "questions": []}]),
            ), mock.patch.object(
                buyer, "market_summary", return_value={"listing_claim_count": 1}
            ), mock.patch.object(
                buyer, "write_summary_markdown"
            ), mock.patch.object(
                buyer, "csv_row", return_value={"trim_claim": "Lariat\rSpecial"}
            ):
                summary = buyer.build(
                    root, root / "config_f350.json", "run-1", ["autotrader"], overrides_path
                )

            output = buyer.artifact_paths(root, {"vehicle_key": "ford_f350"})["investigation_csv"]
            raw = output.read_bytes()
            self.assertNotIn(b"\r\n", raw)
            self.assertIn(b"\r", raw)
            with output.open("r", encoding="utf-8", newline="") as handle:
                parsed = list(csv.DictReader(handle))
            self.assertEqual(parsed[0]["trim_claim"], "Lariat\rSpecial")
            self.assertEqual(summary["listing_claim_count"], 1)

    def test_manual_review_csv_preserves_bare_cr(self):
        import phase1_reporting as reporting

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config_path = root / "config.json"
            config_path.write_text(json.dumps({"vehicle_key": "test_vehicle"}), encoding="utf-8")
            status_path = root / "status.json"
            status_path.write_text("{}", encoding="utf-8")
            config = {"vehicle_key": "test_vehicle"}
            status = {"run_id": "run-1", "execution_status": "success"}
            record = {"canonical_listing_id": "listing-1"}
            identity = {"canonical_listing_id": "listing-1"}
            duplicate = {
                "candidates": [],
                "candidate_count": 0,
                "high_confidence_count": 0,
                "medium_confidence_count": 0,
                "low_confidence_count": 0,
                "artifact": "data/test_vehicle/duplicates.json",
            }
            with mock.patch.object(reporting, "load_json", side_effect=[config, status]), \
                mock.patch.object(reporting, "source_status_path", return_value=status_path), \
                mock.patch.object(reporting, "status_is_current_success", return_value=True), \
                mock.patch.object(reporting, "_accepted_records", return_value=[record]), \
                mock.patch.object(reporting, "load_current_identity_records", return_value=[identity]), \
                mock.patch.object(reporting, "build_duplicate_candidates", return_value=duplicate), \
                mock.patch.object(reporting, "candidate_index", return_value={}), \
                mock.patch.object(
                    reporting,
                    "transform_manual_review_record",
                    return_value={"location": "Calgary,\rAB", "quality_warnings": []},
                ):
                reporting.build_manual_review(
                    root=root,
                    source_plan=[(config_path, ("autotrader",))],
                    run_id="run-1",
                )
            output = root / "data/test_vehicle/manual_review/test_vehicle_manual_review_latest.csv"
            raw = output.read_bytes()
            self.assertNotIn(b"\r\n", raw)
            self.assertIn(b"\r", raw)
            with output.open("r", encoding="utf-8", newline="") as handle:
                parsed = list(csv.DictReader(handle))
            self.assertEqual(parsed[0]["location"], "Calgary,\rAB")


if __name__ == "__main__":
    unittest.main()
