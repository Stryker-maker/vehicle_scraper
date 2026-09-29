import json
import tempfile
import unittest
from pathlib import Path

from phase1_pipeline import _validate_isolation_for_health_gate


class Phase1HealthIsolationGateTests(unittest.TestCase):
    def test_degraded_health_passes_when_every_unhealthy_source_is_isolated(self):
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
