import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from workflow_anomalies import compare_health_reports


class DirectBaselineEligibilityTests(unittest.TestCase):
    """Verify direct baseline inputs fail closed under the shared eligibility contract."""

    @staticmethod
    def source(accepted=40, fetched=200, **extra):
        """Build a minimal compatible source fixture."""
        value = {
            "vehicle_key": "ford_f350",
            "source": "autotrader",
            "healthy": True,
            "execution_status": "success",
            "accepted_record_count": accepted,
            "fetched_record_count": fetched,
            "parse_failure_count": 0,
            "quality_warning_rows": 0,
            "compatibility_fingerprint": "fingerprint-v1",
        }
        value.update(extra)
        return value

    def current(self):
        """Build the current report used by direct-baseline tests."""
        return {"run_id": "current", "sources": [self.source(5, 30)]}

    def assert_no_count_anomalies(self, baseline):
        """Assert that an invalid direct baseline cannot drive numerical anomalies."""
        report = compare_health_reports(baseline=baseline, current=self.current(), run_id="current")
        codes = {item["code"] for item in report["anomalies"]}
        self.assertNotIn("accepted_record_count_collapse", codes)
        self.assertNotIn("fetched_record_count_collapse", codes)
        self.assertEqual(report["critical_anomaly_count"], 0)

    def test_unsuccessful_direct_baseline_is_rejected(self):
        """Reject a baseline whose overall collection status is unsuccessful."""
        self.assert_no_count_anomalies({
            "run_id": "old", "overall_status": "failure",
            "sources": [self.source()],
        })

    def test_incomplete_direct_baseline_is_rejected(self):
        """Reject a baseline that has no usable source evidence."""
        current = self.current()
        baseline = {"run_id": "old", "sources": []}
        report = compare_health_reports(baseline=baseline, current=current, run_id="current")
        self.assertEqual(report["baseline_status"], "incompatible")
        self.assert_no_count_anomalies(baseline)

    def test_duplicate_direct_baseline_sources_are_rejected(self):
        """Reject duplicate vehicle/source entries in a direct baseline."""
        self.assert_no_count_anomalies({
            "run_id": "old", "overall_status": "success",
            "sources": [self.source(), self.source()],
        })

    def test_malformed_direct_baseline_source_is_rejected(self):
        """Reject a direct baseline containing a non-object source entry."""
        self.assert_no_count_anomalies({
            "run_id": "old", "overall_status": "success",
            "sources": [self.source(), "not-a-source-object"],
        })

    def test_missing_vehicle_key_in_direct_baseline_is_rejected(self):
        """Reject a baseline source whose vehicle identity is missing or blank."""
        for vehicle_key in (None, "", "   "):
            with self.subTest(vehicle_key=repr(vehicle_key)):
                self.assert_no_count_anomalies({
                    "run_id": "old", "overall_status": "success",
                    "sources": [self.source(vehicle_key=vehicle_key)],
                })

    def test_missing_source_in_direct_baseline_is_rejected(self):
        """Reject a baseline source whose source identity is missing or blank."""
        for source in (None, "", "   "):
            with self.subTest(source=repr(source)):
                self.assert_no_count_anomalies({
                    "run_id": "old", "overall_status": "success",
                    "sources": [self.source(source=source)],
                })

    def test_missing_identity_in_current_source_fails_closed(self):
        """Reject comparison when current source identity is missing or blank."""
        baseline = {"run_id": "old", "overall_status": "success", "sources": [self.source()]}
        for field in ("vehicle_key", "source"):
            for value in (None, "", "   "):
                with self.subTest(field=field, value=repr(value)):
                    current_source = self.source(5, 30, **{field: value})
                    current = {"run_id": "current", "sources": [current_source]}
                    report = compare_health_reports(
                        baseline=baseline,
                        current=current,
                        run_id="current",
                    )
                    codes = {item["code"] for item in report["anomalies"]}
                    self.assertNotIn("accepted_record_count_collapse", codes)
                    self.assertNotIn("fetched_record_count_collapse", codes)
                    self.assertEqual(report["critical_anomaly_count"], 0)
                    self.assertEqual(report["baseline_status"], "incompatible")

    def test_malformed_current_source_fails_closed(self):
        """Reject comparison when the current report itself contains malformed evidence."""
        current = {"run_id": "current", "sources": [self.source(5, 30), "not-a-source-object"]}
        baseline = {"run_id": "old", "overall_status": "success", "sources": [self.source()]}
        report = compare_health_reports(baseline=baseline, current=current, run_id="current")
        codes = {item["code"] for item in report["anomalies"]}
        self.assertNotIn("accepted_record_count_collapse", codes)
        self.assertNotIn("fetched_record_count_collapse", codes)
        self.assertEqual(report["baseline_status"], "incompatible")

    def test_same_run_direct_baseline_is_not_compared(self):
        """Reject a direct baseline that refers to the current run."""
        self.assert_no_count_anomalies({
            "run_id": "current", "overall_status": "success",
            "sources": [self.source()],
        })


if __name__ == "__main__":
    unittest.main()
