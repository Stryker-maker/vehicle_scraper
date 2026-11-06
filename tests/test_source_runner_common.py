import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from identity_lifecycle import IDENTITY_LIFECYCLE_SCHEMA_VERSION
from source_runner_common import (
    assess_source_output,
    collector_quality_report,
    collector_status_name,
    empty_identity,
    restore_config_if_mutated,
)


class SourceRunnerCommonTests(unittest.TestCase):
    def test_empty_identity_preserves_schema_and_zeroed_fields(self):
        identity = empty_identity(IDENTITY_LIFECYCLE_SCHEMA_VERSION)

        self.assertEqual(
            identity["identity_lifecycle_schema_version"],
            IDENTITY_LIFECYCLE_SCHEMA_VERSION,
        )
        self.assertEqual(identity["observed_current_count"], 0)
        self.assertEqual(identity["artifacts"], {})

    def test_assess_source_output_classifies_fresh_valid_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "latest.csv"
            output.write_text(
                "listing_id,url,source,price,mileage,location,distance_km\n"
                "one,https://example.test/one,autotrader,100,10,Red Deer,1\n",
                encoding="utf-8",
            )
            result = assess_source_output(
                output,
                before_signature=None,
                started_ns=0,
                returncode=0,
                timed_out=False,
            )

        fresh, validation, observed, current, stale, failures = result
        self.assertTrue(fresh)
        self.assertTrue(validation["schema_valid"])
        self.assertEqual((observed, current, stale), (1, 1, 0))
        self.assertEqual(failures, [])

    def test_assess_source_output_preserves_stale_and_timeout_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "latest.csv"
            output.write_text(
                "listing_id,url,source,price,mileage,location,distance_km\n"
                "one,https://example.test/one,kijiji,100,10,Red Deer,1\n",
                encoding="utf-8",
            )
            signature = (output.stat().st_mtime_ns, output.stat().st_size)
            result = assess_source_output(
                output,
                before_signature=signature,
                started_ns=output.stat().st_mtime_ns + 1,
                returncode=None,
                timed_out=True,
            )

        fresh, _, observed, current, stale, failures = result
        self.assertFalse(fresh)
        self.assertEqual((observed, current, stale), (1, 0, 1))
        self.assertEqual(failures, ["collector_timed_out", "no_fresh_output"])

    def test_collector_status_precedence(self):
        self.assertEqual(collector_status_name(True, 1, []), "timed_out")
        self.assertEqual(collector_status_name(False, 1, []), "failed")
        self.assertEqual(
            collector_status_name(False, 0, ["warning"]), "degraded"
        )
        self.assertEqual(collector_status_name(False, 0, []), "success")

    def test_restore_config_if_mutated_restores_original_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            original = b'{"approved": true}\n'
            config.write_bytes(b'{"approved": false}\n')
            failures = []

            isolated = restore_config_if_mutated(config, original, failures)

            self.assertFalse(isolated)
            self.assertEqual(config.read_bytes(), original)
            self.assertEqual(failures, ["approved_config_mutated"])

    def test_quality_report_skips_stale_and_unavailable_data(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "latest.csv"
            output.write_text("placeholder", encoding="utf-8")
            stale = collector_quality_report(output, "kijiji", False, False, 1)
            not_evaluated = collector_quality_report(
                output, "autotrader", False, False, 0
            )

        self.assertEqual(
            stale["data_quality_status"], "not_evaluated_stale_output"
        )
        self.assertEqual(not_evaluated["data_quality_status"], "not_evaluated")
        self.assertEqual(stale["quality_warning_count"], 0)

    def test_quality_report_passes_source_to_quality_analyzer(self):
        with patch(
            "source_runner_common.analyze_csv_quality",
            return_value={"source": "kijiji"},
        ) as analyze:
            result = collector_quality_report(
                Path("latest.csv"), "kijiji", True, True, 0
            )

        analyze.assert_called_once_with(Path("latest.csv"), "kijiji")
        self.assertEqual(result, {"source": "kijiji"})


if __name__ == "__main__":
    unittest.main()
