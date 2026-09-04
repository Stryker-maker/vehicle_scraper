import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from workflow_anomalies import compare_health_reports


class DirectBaselineEligibilityTests(unittest.TestCase):
    def source(self, accepted=40, fetched=200, **extra):
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
        return {"run_id": "current", "sources": [self.source(5, 30)]}

    def assert_no_count_anomalies(self, baseline):
        report = compare_health_reports(
            baseline=baseline, current=self.current(), run_id="current"
        )
        codes = {item["code"] for item in report["anomalies"]}
        self.assertNotIn("accepted_record_count_collapse", codes)
        self.assertNotIn("fetched_record_count_collapse", codes)
        self.assertEqual(report["critical_anomaly_count"], 0)

    def test_unsuccessful_direct_baseline_is_rejected(self):
        self.assert_no_count_anomalies({
            "run_id": "old", "overall_status": "failure",
            "sources": [self.source()],
        })

    def test_incomplete_direct_baseline_is_rejected(self):
        current = self.current()
        baseline = {"run_id": "old", "sources": []}
        report = compare_health_reports(baseline=baseline, current=current, run_id="current")
        self.assertEqual(report["baseline_status"], "incompatible")
        self.assert_no_count_anomalies(baseline)

    def test_duplicate_direct_baseline_sources_are_rejected(self):
        self.assert_no_count_anomalies({
            "run_id": "old", "overall_status": "success",
            "sources": [self.source(), self.source()],
        })

    def test_malformed_direct_baseline_source_is_rejected(self):
        self.assert_no_count_anomalies({
            "run_id": "old", "overall_status": "success",
            "sources": [self.source(), "not-a-source-object"],
        })

    def test_malformed_current_source_fails_closed(self):
        current = {"run_id": "current", "sources": [self.source(5, 30), "not-a-source-object"]}
        baseline = {"run_id": "old", "overall_status": "success", "sources": [self.source()]}
        report = compare_health_reports(baseline=baseline, current=current, run_id="current")
        codes = {item["code"] for item in report["anomalies"]}
        self.assertNotIn("accepted_record_count_collapse", codes)
        self.assertNotIn("fetched_record_count_collapse", codes)
        self.assertEqual(report["baseline_status"], "incompatible")

    def test_same_run_direct_baseline_is_not_compared(self):
        self.assert_no_count_anomalies({
            "run_id": "current", "overall_status": "success",
            "sources": [self.source()],
        })


if __name__ == "__main__":
    unittest.main()
