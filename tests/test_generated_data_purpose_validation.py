from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import generated_data_validation as generated


class GeneratedDataPurposeValidationTests(unittest.TestCase):
    def entries(self):
        return [
            {
                "vehicle_key": "ram_3500",
                "config_path": "config_ram3500.json",
                "enabled": True,
                "analysis_profile": "owned_vehicle_value",
            },
            {
                "vehicle_key": "ford_f150",
                "config_path": "config_f150.json",
                "enabled": False,
                "analysis_profile": "optional_curiosity",
            },
        ]

    def test_changed_purpose_output_invokes_vehicle_validator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths_file = root / "paths.txt"
            paths_file.write_text(
                "data/ram_3500/purpose_output/value_monitor/market_snapshot_latest.json\n",
                encoding="utf-8",
            )
            purpose_report = {
                "validation_status": "pass",
                "validation_errors": [],
                "vehicle_key": "ram_3500",
            }
            with mock.patch.object(generated, "registry_entries", return_value=self.entries()), mock.patch.object(
                generated,
                "validate_generated_data_paths",
                return_value=[],
            ), mock.patch.object(
                generated,
                "verify_retention",
                return_value={"verification_status": "pass", "verification_errors": []},
            ), mock.patch.object(
                generated,
                "validate_purpose_output",
                return_value=purpose_report,
            ) as purpose_validator:
                report = generated.validate_generated_data_change(
                    root=root,
                    paths_file=paths_file,
                )
            self.assertEqual(report["validation_status"], "pass")
            self.assertEqual(report["purpose_output_validation_status"], "pass")
            self.assertEqual(
                report["purpose_output_validations"]["ram_3500"],
                purpose_report,
            )
            purpose_validator.assert_called_once()

    def test_failed_purpose_output_validation_fails_data_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths_file = root / "paths.txt"
            paths_file.write_text(
                "data/ram_3500/purpose_output/value_monitor/comparables_latest.jsonl\n",
                encoding="utf-8",
            )
            with mock.patch.object(generated, "registry_entries", return_value=self.entries()), mock.patch.object(
                generated,
                "validate_generated_data_paths",
                return_value=[],
            ), mock.patch.object(
                generated,
                "verify_retention",
                return_value={"verification_status": "pass", "verification_errors": []},
            ), mock.patch.object(
                generated,
                "validate_purpose_output",
                return_value={
                    "validation_status": "fail",
                    "validation_errors": ["record_underlying_canonical_id_set_mismatch"],
                },
            ):
                report = generated.validate_generated_data_change(
                    root=root,
                    paths_file=paths_file,
                )
            self.assertEqual(report["validation_status"], "fail")
            self.assertIn(
                "purpose_output:ram_3500:record_underlying_canonical_id_set_mismatch",
                report["validation_errors"],
            )


if __name__ == "__main__":
    unittest.main()
