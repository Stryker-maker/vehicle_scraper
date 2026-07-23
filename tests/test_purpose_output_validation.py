from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import purpose_output_validation as validation
import purpose_outputs as purpose


class PurposeOutputValidationTests(unittest.TestCase):
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

    def bundle(self, vehicle_key: str, index: int):
        canonical_id = f"autotrader:{vehicle_key}:{index}"
        return {
            "record": {
                "run_id": "run-1",
                "vehicle_key": vehicle_key,
                "source": "autotrader",
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
                    "mileage_km": 180000 - index * 5000,
                    "distance_km": 100,
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

    def copy_inputs(self, root: Path):
        repository_root = Path(__file__).resolve().parents[1]
        (root / "purpose_inputs.json").write_text(
            (repository_root / "purpose_inputs.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    def build_artifacts(self, root: Path, vehicle_key: str):
        self.copy_inputs(root)
        config = self.config(vehicle_key)
        bundles = [self.bundle(vehicle_key, index) for index in range(3)]
        with mock.patch.object(purpose, "load_vehicle_config", return_value=config), mock.patch.object(
            purpose,
            "load_source_bundles",
            return_value=bundles,
        ):
            purpose.build(
                root=root,
                config_path=Path("config.json"),
                run_id="run-1",
                sources=["autotrader"],
                inputs_path=Path("purpose_inputs.json"),
            )
        return config, bundles

    def validate(self, root: Path, config: dict, bundles: list[dict]):
        with mock.patch.object(validation, "load_vehicle_config", return_value=config), mock.patch.object(
            validation,
            "load_source_bundles",
            return_value=bundles,
        ):
            return validation.validate_purpose_output(
                root=root,
                config_path=Path("config.json"),
                inputs_path=Path("purpose_inputs.json"),
                run_id="run-1",
                expected_sources=["autotrader"],
            )

    def test_owned_output_set_passes_and_matches_underlying_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, bundles = self.build_artifacts(root, "ram_3500")
            report = self.validate(root, config, bundles)
            self.assertEqual(report["validation_status"], "pass")
            self.assertEqual(report["record_count"], 3)
            self.assertEqual(report["csv_row_count"], 3)

    def test_family_output_set_passes_and_questions_match_candidates(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, bundles = self.build_artifacts(root, "honda_odyssey")
            report = self.validate(root, config, bundles)
            self.assertEqual(report["validation_status"], "pass")
            self.assertEqual(report["analysis_profile"], "family_friend_purchase")

    def test_forbidden_rank_key_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, bundles = self.build_artifacts(root, "ram_3500")
            paths = purpose.artifact_paths(root, config, "owned_vehicle_value")
            records = [
                json.loads(line)
                for line in paths["records_jsonl"].read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            records[0]["rank"] = 1
            paths["records_jsonl"].write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )
            report = self.validate(root, config, bundles)
            self.assertEqual(report["validation_status"], "fail")
            self.assertTrue(
                any(
                    error.startswith("record_forbidden_key")
                    for error in report["validation_errors"]
                )
            )

    def test_disconnected_complete_looking_output_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, bundles = self.build_artifacts(root, "honda_odyssey")
            disconnected = [self.bundle("honda_odyssey", 99)]
            report = self.validate(root, config, disconnected)
            self.assertIn(
                "record_underlying_canonical_id_set_mismatch",
                report["validation_errors"],
            )


if __name__ == "__main__":
    unittest.main()
