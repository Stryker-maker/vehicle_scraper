from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import f350_buyer_intelligence as buyer


class EvidenceExtractionTests(unittest.TestCase):
    def test_configuration_and_usage_claims_are_explicit(self):
        normalized = {
            "trim": "2023 Lariat Tremor Crew Cab 6.75 ft box SRW 4x4",
            "engine": "6.7L",
            "fuel": "Diesel",
            "accident_claim": "No accidents reported",
        }
        raw_payload = {
            "description": (
                "One owner highway use. Full service history. "
                "Total engine hours: 2,400. Idle hours: 350."
            )
        }
        result = buyer.extract_configuration_evidence(normalized, raw_payload)
        self.assertEqual(result["trim"]["value"], "Lariat")
        self.assertEqual(result["packages"]["value"], ["Tremor"])
        self.assertEqual(result["cab_configuration"]["value"], "crew_cab")
        self.assertEqual(result["box_configuration"]["value"], "short_box_or_6_75ft_claim")
        self.assertEqual(result["rear_wheel_configuration"]["value"], "srw")
        self.assertEqual(result["drivetrain"]["value"], "4wd")
        self.assertEqual(result["engine_hours"]["value"], 2400)
        self.assertEqual(result["idle_hours"]["value"], 350)
        self.assertEqual(result["service_history"]["value"], "records_available_claim")
        self.assertIn("one_owner_claim", result["prior_use_claims"]["value"])
        self.assertIn("highway_use_claim", result["prior_use_claims"]["value"])
        for field in (
            "trim",
            "cab_configuration",
            "box_configuration",
            "rear_wheel_configuration",
            "drivetrain",
            "engine_hours",
            "idle_hours",
            "service_history",
        ):
            self.assertEqual(
                result[field]["evidence_status"],
                "source_text_reported_unverified",
            )

    def test_missing_evidence_remains_unknown_and_generates_questions(self):
        normalized = {
            "trim": "",
            "mileage_km": 230000,
            "accident_claim": "Unknown",
        }
        result = buyer.extract_configuration_evidence(normalized, {})
        identity = {"vin_evidence_status": "not_reported"}
        completeness, missing = buyer.evidence_completeness(result, identity)
        self.assertEqual(completeness, "insufficient")
        self.assertIn("engine_hours", missing)
        self.assertIn("idle_hours", missing)
        self.assertIn("service_history", missing)
        self.assertIn("cab_configuration", missing)
        self.assertIsNone(result["engine_hours"]["value"])
        questions = buyer.seller_questions(normalized, result, missing)
        categories = {value["category"] for value in questions}
        self.assertIn("identity", categories)
        self.assertIn("usage", categories)
        self.assertIn("configuration", categories)
        self.assertIn("history", categories)
        self.assertIn("high_mileage", categories)
        self.assertIn("inspection", categories)

    def test_hour_context_does_not_treat_calculation_as_condition_proof(self):
        result = buyer.hour_context(240000, 4000, 800)
        self.assertEqual(result["km_per_engine_hour"], 60.0)
        self.assertEqual(result["idle_hour_percent"], 20.0)
        self.assertEqual(result["meaning"], "usage_context_only_not_condition_proof")
        invalid = buyer.hour_context(100000, 1000, 1200)
        self.assertIsNone(invalid["idle_hour_percent"])
        self.assertIn("idle_hours_exceed_engine_hours", invalid["warnings"])


class MarketAndOverrideTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"year": 2023, "price_cad": 50000, "mileage_km": 80000},
            {"year": 2023, "price_cad": 52000, "mileage_km": 70000},
            {"year": 2023, "price_cad": 54000, "mileage_km": 60000},
            {"year": 2023, "price_cad": 56000, "mileage_km": 50000},
            {"year": 2023, "price_cad": 58000, "mileage_km": 40000},
            {"year": 2022, "price_cad": 47000, "mileage_km": 100000},
        ]

    def test_price_bands_and_projection_are_descriptive(self):
        target = {"year": 2023, "price_cad": 51000, "mileage_km": 75000}
        result = buyer.market_context(self.rows, target)
        self.assertEqual(result["cohort_basis"], "exact_model_year_2023")
        self.assertEqual(result["comparable_count"], 5)
        self.assertEqual(result["price_q1_cad"], 52000)
        self.assertEqual(result["price_median_cad"], 54000)
        self.assertEqual(result["price_q3_cad"], 56000)
        self.assertEqual(result["price_position"], "below_observed_interquartile_range")
        projection = result["mileage_adjusted_asking_price_projection"]
        self.assertEqual(projection["status"], "available")
        self.assertIsNotNone(projection["projected_asking_price_cad"])
        self.assertEqual(
            projection["meaning"],
            "asking_price_context_not_appraisal_or_future_value",
        )
        self.assertEqual(
            result["market_scope"],
            "configured_query_accepted_listing_claims_not_complete_market",
        )

    def test_small_cohort_does_not_create_regression_authority(self):
        rows = [
            {"year": 2023, "price_cad": 50000, "mileage_km": 80000},
            {"year": 2023, "price_cad": 52000, "mileage_km": 70000},
        ]
        result = buyer.market_context(rows, rows[0])
        self.assertEqual(result["price_position"], "insufficient_comparables")
        self.assertEqual(
            result["mileage_adjusted_asking_price_projection"]["status"],
            "insufficient_comparables",
        )

    def test_override_requires_reason_and_preserves_computed_result(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "overrides.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "vehicle_key": "ford_f350",
                        "overrides": {
                            "listing_1": {
                                "classification_override": "pass"
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "requires override_reason"):
                buyer.load_owner_overrides(path)

            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "vehicle_key": "ford_f350",
                        "overrides": {
                            "listing_1": {
                                "owner_disposition": "hold",
                                "owner_note": "Known local truck",
                                "owner_tags": ["local", "follow-up"],
                                "classification_override": "pass",
                                "override_reason": "Owner observed corrosion in person",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            loaded = buyer.load_owner_overrides(path)
            result = buyer.owner_annotation(
                "listing_1", loaded, "investigate_priority"
            )
            self.assertTrue(result["override_applied"])
            self.assertEqual(result["effective_classification"], "pass")
            self.assertEqual(result["classification_override"], "pass")
            self.assertEqual(
                result["override_contract"],
                "owner_classification_only_source_evidence_unchanged",
            )


class SourceLoadingTests(unittest.TestCase):
    def test_wrong_status_schema_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = {
                "schema_version": 2,
                "vehicle_key": "ford_f350",
                "make": "Ford",
                "model": "F-350",
                "criteria": {
                    "min_year": 2015,
                    "max_year": 2023,
                    "max_price_cad": 60000,
                    "fuel": "Diesel",
                    "engine": "6.7L",
                },
                "origin": {
                    "home_city": "Red Deer, AB",
                    "home_coords": [52.2681, -113.8112],
                    "max_distance_km": 800,
                },
                "sources": {
                    "autotrader": {
                        "make": "ford",
                        "model": "f-350",
                        "search_locations": ["Calgary, AB"],
                    },
                    "kijiji": {
                        "make": "Ford",
                        "model": "F-350",
                        "search_locations": ["Calgary, AB"],
                    },
                },
            }
            status = root / "data/ford_f350/run_status/autotrader_latest.json"
            status.parent.mkdir(parents=True)
            status.write_text(
                json.dumps(
                    {
                        "schema_version": 7,
                        "run_id": "run-1",
                        "vehicle_key": "ford_f350",
                        "source": "autotrader",
                        "execution_status": "success",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "schema-v8 success"):
                buyer.load_source_bundles(root, config, "autotrader", "run-1")


class BuildTests(unittest.TestCase):
    def config(self):
        return {
            "schema_version": 2,
            "vehicle_key": "ford_f350",
            "make": "Ford",
            "model": "F-350",
            "criteria": {
                "min_year": 2015,
                "max_year": 2023,
                "max_price_cad": 60000,
                "fuel": "Diesel",
                "engine": "6.7L",
            },
            "origin": {
                "home_city": "Red Deer, AB",
                "home_coords": [52.2681, -113.8112],
                "max_distance_km": 800,
            },
            "sources": {
                "autotrader": {
                    "make": "ford",
                    "model": "f-350",
                    "search_locations": ["Calgary, AB"],
                },
                "kijiji": {
                    "make": "Ford",
                    "model": "F-350",
                    "search_locations": ["Calgary, AB"],
                },
            },
        }

    def bundle(self, index: int, price: int, mileage: int):
        canonical_id = f"listing_{index}"
        return {
            "record": {
                "evidence_schema_version": 1,
                "record_stage": "accepted",
                "run_id": "run-1",
                "vehicle_key": "ford_f350",
                "source": "autotrader",
                "source_record_index": index,
                "canonical_listing_id": canonical_id,
                "source_listing_id": f"source-{index}",
                "raw_record_ref": f"raw#{index}",
                "source_adapter_record_ref": f"adapter#{index}",
                "normalized": {
                    "year": 2023,
                    "price_cad": price,
                    "mileage_km": mileage,
                    "distance_km": 150,
                    "trim": "Lariat Crew Cab SRW 4x4",
                    "engine": "6.7L",
                    "fuel": "Diesel",
                    "accident_claim": "No accidents reported",
                    "listing_url": f"https://example.invalid/{index}",
                },
            },
            "identity": {
                "identity_lifecycle_schema_version": 2,
                "run_id": "run-1",
                "source": "autotrader",
                "canonical_listing_id": canonical_id,
                "lifecycle_state": "active",
                "vin_claim": None,
                "vin_evidence_status": "not_reported",
            },
            "raw_payload": {
                "description": (
                    "Crew Cab SRW 4x4. Full service history. "
                    "Engine hours 2400. Idle hours 300. One owner highway use."
                )
            },
        }

    def test_build_writes_transparent_outputs_without_rank_or_score(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config_path = root / "config_f350.json"
            config_path.write_text(json.dumps(self.config()), encoding="utf-8")
            overrides_path = root / "f350_owner_overrides.json"
            overrides_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "vehicle_key": "ford_f350",
                        "overrides": {
                            "listing_0": {
                                "classification_override": "hold",
                                "override_reason": "Awaiting inspection",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            bundles = [
                self.bundle(index, 50000 + index * 1000, 90000 - index * 5000)
                for index in range(6)
            ]
            with mock.patch.object(
                buyer, "load_source_bundles", return_value=bundles
            ):
                summary = buyer.build(
                    root,
                    config_path,
                    "run-1",
                    ["autotrader"],
                    overrides_path,
                )

            paths = buyer.artifact_paths(root, self.config())
            for path in paths.values():
                self.assertTrue(path.is_file(), path)
            self.assertEqual(summary["listing_claim_count"], 6)
            self.assertEqual(summary["scope"], "single_source")
            self.assertEqual(
                summary["market_scope"],
                "configured_query_accepted_listing_claims_not_complete_market",
            )
            jsonl_text = paths["investigation_jsonl"].read_text(encoding="utf-8")
            csv_text = paths["investigation_csv"].read_text(encoding="utf-8")
            lowered = (jsonl_text + csv_text).casefold()
            self.assertNotIn('"rank"', lowered)
            self.assertNotIn('"score"', lowered)
            rows = list(
                csv.DictReader(
                    paths["investigation_csv"].open(encoding="utf-8")
                )
            )
            self.assertEqual(rows[0]["computed_classification"], "investigate_priority")
            self.assertEqual(rows[0]["owner_classification_override"], "hold")
            self.assertEqual(rows[0]["effective_classification"], "hold")
            self.assertGreater(int(rows[0]["seller_question_count"]), 0)
            questions = [
                json.loads(line)
                for line in paths["seller_questions"].read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            ]
            self.assertEqual(len(questions), 6)
            self.assertTrue(questions[0]["questions"])


if __name__ == "__main__":
    unittest.main()
