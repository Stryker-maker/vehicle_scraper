from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import purpose_outputs as purpose


class PurposeInputTests(unittest.TestCase):
    def test_repository_inputs_preserve_known_and_missing_boundaries(self):
        root = Path(__file__).resolve().parents[1]
        inputs = purpose.load_purpose_inputs(root / "purpose_inputs.json")
        ram = inputs["vehicles"]["ram_3500"]["subject_profile"]
        self.assertEqual(ram["year"]["value"], 2013)
        self.assertEqual(
            ram["year"]["evidence_status"],
            "owner_reported_historical_unverified",
        )
        self.assertIsNone(ram["current_odometer_km"]["value"])
        forester = inputs["vehicles"]["subaru_forester"]["subject_profile"]
        self.assertTrue(all(value["value"] is None for value in forester.values()))
        for vehicle_key in purpose.FAMILY_VEHICLES:
            preferences = inputs["vehicles"][vehicle_key]["preferences"]
            self.assertEqual(
                purpose._missing_input_fields(preferences),
                sorted(purpose.FAMILY_PREFERENCE_FIELDS),
            )

    def test_unknown_input_field_fails_closed(self):
        root = Path(__file__).resolve().parents[1]
        value = json.loads((root / "purpose_inputs.json").read_text(encoding="utf-8"))
        value["vehicles"]["ram_3500"]["subject_profile"]["invented"] = {
            "value": "x",
            "evidence_status": "owner_input_required",
        }
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "inputs.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "field set mismatch"):
                purpose.load_purpose_inputs(path)


class PurposeBehaviorTests(unittest.TestCase):
    def owned_subject(self):
        return {
            "year": {"value": 2013, "evidence_status": "owner_reported_historical_unverified"},
            "trim": {"value": "Laramie", "evidence_status": "owner_reported_historical_unverified"},
            "fuel": {"value": "Diesel", "evidence_status": "owner_reported_historical_unverified"},
            "engine": {"value": "6.7 Cummins diesel", "evidence_status": "owner_reported_historical_unverified"},
            "drivetrain": {"value": "4wd", "evidence_status": "owner_reported_historical_unverified"},
            "current_odometer_km": {"value": None, "evidence_status": "owner_input_required"},
            "odometer_context": {"value": "historical", "evidence_status": "owner_reported_historical_unverified"},
        }

    def bundle(self, vehicle_key: str, index: int = 0, source: str = "autotrader"):
        canonical_id = f"{source}:{vehicle_key}:{index}"
        return {
            "record": {
                "run_id": "run-1",
                "vehicle_key": vehicle_key,
                "source": source,
                "canonical_listing_id": canonical_id,
                "source_listing_id": f"source-{index}",
                "raw_record_ref": f"raw#{index}",
                "source_adapter_record_ref": f"adapter#{index}",
                "normalized": {
                    "year": 2013 if vehicle_key == "ram_3500" else 2022,
                    "trim": "Laramie" if vehicle_key == "ram_3500" else "EX-L",
                    "fuel": "Diesel" if vehicle_key == "ram_3500" else "Gas",
                    "engine": "6.7L Cummins" if vehicle_key == "ram_3500" else "3.5L",
                    "price_cad": 30000 + index * 1000,
                    "mileage_km": 200000 - index * 5000,
                    "distance_km": 150,
                    "seller_type_claim": "dealer",
                    "listing_url": f"https://example.invalid/{index}",
                },
            },
            "identity": {
                "lifecycle_state": "active",
                "price_observation_count": 2,
                "previous_observation_price_cad": 31000 + index * 1000,
                "change_from_previous_observation_cad": -1000,
                "change_from_first_observation_cad": -2000,
            },
            "raw_payload": {
                "description": (
                    "Laramie 6.7 Cummins 4x4 full service history"
                    if vehicle_key == "ram_3500"
                    else "8 passenger power sliding doors full service history"
                )
            },
        }

    def incomplete_preferences(self):
        list_fields = {
            "cargo_requirements",
            "acceptable_seller_types",
            "availability_constraints",
        }
        return {
            name: {
                "value": [] if name in list_fields else None,
                "evidence_status": "friend_input_required",
            }
            for name in purpose.FAMILY_PREFERENCE_FIELDS
        }

    def test_ram_comparability_is_explainable_not_ranked(self):
        record = purpose._owned_record(
            self.bundle("ram_3500"),
            self.owned_subject(),
            "single_source",
        )
        self.assertEqual(record["subject_comparability"], "close_subject_comparable")
        self.assertIn("subject_match:year", record["subject_comparability_reasons"])
        self.assertEqual(
            record["interpretation_contract"],
            "observed_asking_price_context_not_appraisal_not_sale_probability",
        )
        self.assertNotIn("rank", record)
        self.assertNotIn("score", record)

    def test_forester_missing_profile_stays_broad_context(self):
        subject = {
            name: {"value": None, "evidence_status": "owner_input_required"}
            for name in purpose.OWNED_SUBJECT_FIELDS
        }
        record = purpose._owned_record(
            self.bundle("subaru_forester"),
            subject,
            "single_source",
        )
        self.assertEqual(record["subject_comparability"], "subject_profile_incomplete")
        self.assertEqual(
            record["subject_profile_missing_fields"],
            sorted(purpose.OWNED_SUBJECT_FIELDS),
        )

    def test_multi_run_direction_requires_real_previous_observations(self):
        records = [
            {"change_from_previous_observation_cad": -1000},
            {"change_from_previous_observation_cad": None},
        ]
        self.assertEqual(
            purpose._direction(records)["status"],
            "insufficient_multi_run_history",
        )
        records.extend(
            [
                {"change_from_previous_observation_cad": 0},
                {"change_from_previous_observation_cad": 500},
            ]
        )
        result = purpose._direction(records)
        self.assertEqual(
            result["status"],
            "observed_asking_price_change_context_available",
        )
        self.assertEqual(
            result["meaning"],
            "listing_asking_price_changes_only_not_market_value_trend_or_sale_evidence",
        )

    def test_family_candidates_wait_for_friend_requirements(self):
        preferences = self.incomplete_preferences()
        record, questions = purpose._family_record(
            self.bundle("honda_odyssey"),
            preferences,
            "single_source",
            Path("data/honda_odyssey/purpose_output/family_candidate/seller_questions_latest.jsonl"),
        )
        self.assertEqual(record["candidate_classification"], "candidate_pending_requirements")
        self.assertEqual(record["preference_match_status"], "preferences_incomplete")
        self.assertEqual(record["seating_claim"], 8)
        self.assertGreater(len(questions["questions"]), 0)
        self.assertNotIn("engine_hours", record)
        self.assertNotIn("rank", record)
        self.assertNotIn("score", record)

    def test_recorded_preferences_produce_visible_mismatch_not_silent_exclusion(self):
        preferences = self.incomplete_preferences()
        values = {
            "budget_max_cad": 25000,
            "min_year": 2020,
            "max_year": 2023,
            "max_mileage_km": 150000,
            "minimum_seating": 7,
            "cargo_requirements": ["power_sliding_doors_claim"],
            "max_distance_km": 500,
            "accident_title_requirement": "clean_title_required",
            "service_history_requirement": "records_required",
            "acceptable_seller_types": ["dealer"],
            "availability_constraints": ["inspection_required"],
        }
        for name, value in values.items():
            preferences[name] = {
                "value": value,
                "evidence_status": "friend_reported_unverified",
            }
        bundle = self.bundle("kia_carnival")
        base = purpose._base_record(bundle, "family_friend_purchase", "single_source")
        evidence = purpose._family_evidence(bundle, base)
        status, reasons, missing = purpose.evaluate_preferences(base, evidence, preferences)
        self.assertEqual(missing, [])
        self.assertEqual(status, "outside_stated_preferences")
        self.assertIn("preference_mismatch:budget_max_cad", reasons)


class PurposeBuildTests(PurposeBehaviorTests):
    def config(self, vehicle_key: str):
        make_model = {
            "ram_3500": ("RAM", "3500"),
            "honda_odyssey": ("Honda", "Odyssey"),
        }
        make, model = make_model[vehicle_key]
        return {
            "schema_version": 2,
            "vehicle_key": vehicle_key,
            "make": make,
            "model": model,
            "criteria": {
                "min_year": 2012,
                "max_year": 2023,
                "max_price_cad": 60000,
                "fuel": "Diesel" if vehicle_key == "ram_3500" else "Gas",
                "engine": "",
            },
            "origin": {
                "home_city": "Red Deer, AB",
                "home_coords": [52.2681, -113.8112],
                "max_distance_km": 800,
            },
            "sources": {
                "autotrader": {
                    "make": make.casefold(),
                    "model": model.casefold(),
                    "search_locations": ["Calgary, AB"],
                },
                "kijiji": {
                    "make": make,
                    "model": model,
                    "search_locations": ["Calgary, AB"],
                },
            },
        }

    def copy_inputs(self, root: Path):
        repository_root = Path(__file__).resolve().parents[1]
        (root / "purpose_inputs.json").write_text(
            (repository_root / "purpose_inputs.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    def test_owned_build_writes_five_non_ranked_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.copy_inputs(root)
            config = self.config("ram_3500")
            with mock.patch.object(purpose, "load_vehicle_config", return_value=config), mock.patch.object(
                purpose,
                "load_source_bundles",
                return_value=[self.bundle("ram_3500", index) for index in range(4)],
            ):
                summary = purpose.build(
                    root=root,
                    config_path=Path("config.json"),
                    run_id="run-1",
                    sources=["autotrader"],
                    inputs_path=Path("purpose_inputs.json"),
                )
            paths = purpose.artifact_paths(root, config, "owned_vehicle_value")
            self.assertTrue(all(path.is_file() for path in paths.values()))
            self.assertEqual(summary["record_count"], 4)
            self.assertEqual(
                summary["competitive_asking_context"]["meaning"],
                "lower_observed_asking_band_not_verified_faster_sale_range_or_sale_probability",
            )
            combined = "".join(path.read_text(encoding="utf-8") for path in paths.values())
            self.assertNotIn('"rank"', combined.casefold())
            self.assertNotIn('"score"', combined.casefold())

    def test_family_build_writes_candidates_and_questions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.copy_inputs(root)
            config = self.config("honda_odyssey")
            with mock.patch.object(purpose, "load_vehicle_config", return_value=config), mock.patch.object(
                purpose,
                "load_source_bundles",
                return_value=[self.bundle("honda_odyssey", index) for index in range(3)],
            ):
                summary = purpose.build(
                    root=root,
                    config_path=Path("config.json"),
                    run_id="run-1",
                    sources=["autotrader"],
                    inputs_path=Path("purpose_inputs.json"),
                )
            paths = purpose.artifact_paths(root, config, "family_friend_purchase")
            self.assertTrue(all(path.is_file() for path in paths.values()))
            self.assertEqual(summary["record_count"], 3)
            self.assertEqual(summary["requirements_status"], "friend_input_required")
            questions = [
                json.loads(line)
                for line in paths["questions_jsonl"].read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(questions), 3)
            self.assertTrue(all(record["questions"] for record in questions))


if __name__ == "__main__":
    unittest.main()
