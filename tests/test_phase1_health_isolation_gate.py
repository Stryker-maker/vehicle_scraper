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
            with patch("phase1_pipeline.Path.exists", return_value=True), patch(
                "sys.stderr"
            ) as stderr:
                self.assertEqual(
                    main(["check-health", "--report", "health.json", "--anomaly-report", "anomalies.json"]),
                    1,
                )
            self.assertIn(
                "must be a list of objects",
                "".join(call.args[0] for call in stderr.write.call_args_list),
            )
            self.assertEqual(load_json.call_count, 2)
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


    def test_degraded_health_passes_when_unhealthy_source_has_no_current_run_output(self):
        health = {
            "run_id": "run-123",
            "overall_status": "degraded",
            "unhealthy_source_runs": 1,
            "sources": [
                {"vehicle_key": "ford_f150", "source": "kijiji", "healthy": False},
            ],
        }
        pair = {"vehicle_key": "ford_f150", "source": "kijiji"}
        anomaly = {
            "run_id": "run-123",
            "isolated_collections": [],
            "no_output_collections": [pair],
            "isolation_requested_collections": [pair],
            "anomalies": [],
        }
        _validate_isolation_for_health_gate(health=health, anomaly=anomaly)

    def test_gate_rejects_collection_classified_as_isolated_and_no_output(self):
        pair = {"vehicle_key": "ford_f150", "source": "kijiji"}
        health = {
            "run_id": "run-123",
            "overall_status": "degraded",
            "unhealthy_source_runs": 1,
            "sources": [{"vehicle_key": "ford_f150", "source": "kijiji", "healthy": False}],
        }
        anomaly = {
            "run_id": "run-123",
            "isolated_collections": [pair],
            "no_output_collections": [pair],
            "isolation_requested_collections": [pair],
            "anomalies": [],
        }
        with self.assertRaisesRegex(RuntimeError, "both isolated and no-output"):
            _validate_isolation_for_health_gate(health=health, anomaly=anomaly)

    def test_gate_rejects_malformed_no_output_collection_list(self):
        pair = {"vehicle_key": "ford_f150", "source": "kijiji"}
        health = {
            "run_id": "run-123",
            "overall_status": "degraded",
            "unhealthy_source_runs": 1,
            "sources": [{"vehicle_key": "ford_f150", "source": "kijiji", "healthy": False}],
        }
        anomaly = {
            "run_id": "run-123",
            "isolated_collections": [],
            "no_output_collections": None,
            "isolation_requested_collections": [pair],
            "anomalies": [],
        }
        with self.assertRaisesRegex(RuntimeError, "no_output_collections must be a list of objects"):
            _validate_isolation_for_health_gate(health=health, anomaly=anomaly)

    def test_requested_set_mismatch_fails_before_isolation_mutation(self):
        with patch("phase1_pipeline.load_json") as load_json, patch(
            "phase1_pipeline.isolate_anomalous_collections"
        ) as isolate:
            load_json.side_effect = [
                {
                    "run_id": "run-current",
                    "overall_status": "degraded",
                    "unhealthy_source_runs": 1,
                    "sources": [{"vehicle_key": "ford_f150", "source": "kijiji", "healthy": False}],
                },
                {
                    "run_id": "run-current",
                    "isolated_collections": [],
                    "no_output_collections": [
                        {"vehicle_key": "ford_f150", "source": "kijiji"}
                    ],
                    "isolation_requested_collections": [],
                    "anomalies": [],
                },
            ]
            with patch("phase1_pipeline.Path.exists", return_value=True), patch("sys.stderr") as stderr:
                self.assertEqual(
                    main(["check-health", "--report", "health.json", "--anomaly-report", "anomalies.json"]),
                    1,
                )
            self.assertIn(
                "isolation_requested_collections does not match",
                "".join(call.args[0] for call in stderr.write.call_args_list),
            )
            isolate.assert_not_called()

    def test_check_health_handler_returns_zero_for_valid_degraded_isolation(self):
        health = {
            "run_id": "run-current",
            "overall_status": "degraded",
            "unhealthy_source_runs": 1,
            "sources": [
                {"vehicle_key": "ford_f150", "source": "kijiji", "healthy": False},
            ],
        }
        isolated = [{"vehicle_key": "ford_f150", "source": "kijiji"}]
        anomaly = {
            "run_id": "run-current",
            "isolated_collections": isolated,
            "no_output_collections": [],
            "isolation_requested_collections": isolated,
            "anomalies": [],
        }
        with patch("phase1_pipeline.load_json", side_effect=[health, anomaly]), patch(
            "phase1_pipeline.Path.exists", return_value=True
        ), patch(
            "phase1_pipeline.isolate_anomalous_collections", return_value=isolated
        ), patch("builtins.print"):
            self.assertEqual(
                main(["check-health", "--report", "health.json", "--anomaly-report", "anomalies.json"]),
                0,
            )

    def test_check_health_handler_accepts_valid_no_output_reclassification(self):
        health = {
            "run_id": "run-current",
            "overall_status": "degraded",
            "unhealthy_source_runs": 1,
            "sources": [
                {"vehicle_key": "ford_f150", "source": "kijiji", "healthy": False},
            ],
        }
        pair = {"vehicle_key": "ford_f150", "source": "kijiji"}
        anomaly = {
            "run_id": "run-current",
            "isolated_collections": [pair],
            "no_output_collections": [],
            "isolation_requested_collections": [pair],
            "anomalies": [],
        }

        def classify_as_no_output(*, root, report):
            report["isolated_collections"] = []
            report["no_output_collections"] = [dict(pair)]
            return []

        with patch("phase1_pipeline.load_json", side_effect=[health, anomaly]), patch(
            "phase1_pipeline.Path.exists", return_value=True
        ), patch(
            "phase1_pipeline.isolate_anomalous_collections",
            side_effect=classify_as_no_output,
        ), patch("builtins.print"):
            self.assertEqual(
                main([
                    "check-health",
                    "--report",
                    "health.json",
                    "--anomaly-report",
                    "anomalies.json",
                ]),
                0,
            )

    def test_check_health_handler_returns_one_when_isolation_result_mismatches(self):
        health = {
            "run_id": "run-current",
            "overall_status": "degraded",
            "unhealthy_source_runs": 1,
            "sources": [
                {"vehicle_key": "ford_f150", "source": "kijiji", "healthy": False},
            ],
        }
        isolated = [{"vehicle_key": "ford_f150", "source": "kijiji"}]
        anomaly = {
            "run_id": "run-current",
            "isolated_collections": isolated,
            "no_output_collections": [],
            "isolation_requested_collections": isolated,
            "anomalies": [],
        }
        with patch("phase1_pipeline.load_json", side_effect=[health, anomaly]), patch(
            "phase1_pipeline.Path.exists", return_value=True
        ), patch(
            "phase1_pipeline.isolate_anomalous_collections", return_value=[]
        ), patch("sys.stderr") as stderr:
            self.assertEqual(
                main(["check-health", "--report", "health.json", "--anomaly-report", "anomalies.json"]),
                1,
            )
        self.assertIn(
            "did not produce the requested isolation set",
            "".join(call.args[0] for call in stderr.write.call_args_list),
        )


if __name__ == "__main__":
    unittest.main()
