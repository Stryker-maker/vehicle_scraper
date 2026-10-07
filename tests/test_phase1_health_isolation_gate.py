import unittest
from pathlib import Path
from unittest.mock import patch

from phase1_pipeline import _validate_isolation_for_health_gate, main


class Phase1HealthIsolationGateTests(unittest.TestCase):
    def test_report_health_prints_json_and_summary_paths(self):
        root = Path.cwd()
        with patch("phase1_pipeline.collect_health", return_value={}), patch(
            "phase1_pipeline.write_health_report",
            return_value=(root / "health.json", root / "health.md"),
        ), patch("builtins.print") as output:
            self.assertEqual(main(["report-health", "--configs", "config_f350.json"]), 0)
        self.assertEqual(output.call_args_list, [
            unittest.mock.call("Health JSON: health.json"),
            unittest.mock.call("Health summary: health.md"),
        ])

    @staticmethod
    def test_degraded_health_passes_when_every_unhealthy_source_is_isolated():
        health = {
            "run_id": "run-123",
            "overall_status": "degraded",
            "unhealthy_source_runs": 1,
            "sources": [
                {"vehicle_key": "ford_f350", "source": "autotrader", "healthy": True},
                {"vehicle_key": "ford_f150", "source": "kijiji", "healthy": False},
            ],
        }
        anomaly = {
            "run_id": "run-123",
            "isolated_collections": [
                {"vehicle_key": "ford_f150", "source": "kijiji"}
            ],
            "anomalies": [],
        }

        _validate_isolation_for_health_gate(health=health, anomaly=anomaly)

    def test_malformed_isolated_collections_fail_closed_before_mutation(self):
        with patch("phase1_pipeline.load_json") as load_json, patch(
            "phase1_pipeline.isolate_anomalous_collections"
        ) as isolate:
            load_json.side_effect = [
                {
                    "run_id": "run-current",
                    "overall_status": "degraded",
                    "unhealthy_source_runs": 1,
                    "sources": [
                        {"vehicle_key": "ford_f150", "source": "kijiji", "healthy": False}
                    ],
                },
                {
                    "run_id": "run-current",
                    "isolated_collections": None,
                    "anomalies": [],
                },
            ]
            self.assertEqual(
                main(["check-health", "--report", "health.json", "--anomaly-report", "anomalies.json"]),
                1,
            )
            isolate.assert_not_called()

    def test_gate_rejects_unhealthy_source_that_is_not_isolated(self):
        health = {
            "run_id": "run-123",
            "overall_status": "degraded",
            "unhealthy_source_runs": 1,
            "sources": [
                {"vehicle_key": "ford_f350", "source": "autotrader", "healthy": True},
                {"vehicle_key": "ford_f150", "source": "kijiji", "healthy": False},
            ],
        }
        anomaly = {
            "run_id": "run-123",
            "isolated_collections": [],
            "anomalies": [],
        }

        with self.assertRaisesRegex(RuntimeError, "isolation is incomplete"):
            _validate_isolation_for_health_gate(health=health, anomaly=anomaly)

    def test_gate_rejects_isolation_failure_even_if_collection_is_listed(self):
        health = {
            "run_id": "run-123",
            "overall_status": "degraded",
            "unhealthy_source_runs": 1,
            "sources": [
                {"vehicle_key": "ford_f150", "source": "kijiji", "healthy": False},
            ],
        }
        anomaly = {
            "run_id": "run-123",
            "isolated_collections": [
                {"vehicle_key": "ford_f150", "source": "kijiji"}
            ],
            "anomalies": [
                {
                    "code": "collection_isolation_failed",
                    "vehicle_key": "ford_f150",
                    "source": "kijiji",
                }
            ],
        }

        with self.assertRaisesRegex(RuntimeError, "isolation reported"):
            _validate_isolation_for_health_gate(health=health, anomaly=anomaly)

    def test_gate_rejects_stale_anomaly_report(self):
        health = {
            "run_id": "run-current",
            "overall_status": "degraded",
            "unhealthy_source_runs": 1,
            "sources": [
                {"vehicle_key": "ford_f150", "source": "kijiji", "healthy": False},
            ],
        }
        anomaly = {
            "run_id": "run-old",
            "isolated_collections": [
                {"vehicle_key": "ford_f150", "source": "kijiji"}
            ],
            "anomalies": [],
        }

        with self.assertRaisesRegex(RuntimeError, "run_id"):
            _validate_isolation_for_health_gate(health=health, anomaly=anomaly)

    def test_stale_anomaly_report_cannot_trigger_isolation_mutation(self):
        with patch("phase1_pipeline.load_json") as load_json, patch(
            "phase1_pipeline.isolate_anomalous_collections"
        ) as isolate:
            load_json.side_effect = [
                {
                    "run_id": "run-current",
                    "overall_status": "degraded",
                    "unhealthy_source_runs": 1,
                    "sources": [
                        {
                            "vehicle_key": "ford_f150",
                            "source": "kijiji",
                            "healthy": False,
                        }
                    ],
                },
                {
                    "run_id": "run-old",
                    "isolated_collections": [
                        {"vehicle_key": "ford_f150", "source": "kijiji"}
                    ],
                    "anomalies": [],
                },
            ]
            with patch("phase1_pipeline.Path.exists", return_value=True), patch(
                "sys.argv",
                [
                    "phase1_pipeline.py",
                    "check-health",
                    "--report",
                    "health.json",
                    "--anomaly-report",
                    "anomalies.json",
                ],
            ):
                self.assertEqual(main(), 1)
            isolate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
