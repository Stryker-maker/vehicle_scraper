from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from canonical_evidence import write_jsonl
from f350_buyer_intelligence import CSV_FIELDS, artifact_paths
from f350_buyer_validation import validate_buyer_artifacts


class BuyerArtifactValidationTests(unittest.TestCase):
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

    def create_artifacts(self, root: Path) -> dict[str, Path]:
        config = self.config()
        config_path = root / "config_f350.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        paths = artifact_paths(root, config)
        relative = {name: str(path.relative_to(root)) for name, path in paths.items()}
        listing = {
            "buyer_intelligence_schema_version": 1,
            "run_id": "run-1",
            "scope": "single_source",
            "vehicle_key": "ford_f350",
            "source": "autotrader",
            "canonical_listing_id": "listing-1",
            "decision_contract": (
                "explainable_classification_not_rank_not_score_"
                "manual_override_preserves_source_evidence"
            ),
            "owner_annotation": {
                "override_applied": False,
                "override_reason": "",
                "override_contract": (
                    "owner_classification_only_source_evidence_unchanged"
                ),
            },
            "market_context": {
                "market_scope": (
                    "configured_query_accepted_listing_claims_not_complete_market"
                ),
                "mileage_adjusted_asking_price_projection": {
                    "meaning": (
                        "asking_price_context_not_appraisal_or_future_value"
                    )
                },
            },
        }
        question = {
            "buyer_intelligence_schema_version": 1,
            "run_id": "run-1",
            "vehicle_key": "ford_f350",
            "source": "autotrader",
            "canonical_listing_id": "listing-1",
            "listing_url": "https://example.invalid/1",
            "questions": [
                {
                    "category": "identity",
                    "priority": "high",
                    "question": "What is the VIN?",
                    "reason": "vin_not_source_reported",
                }
            ],
        }
        write_jsonl(paths["investigation_jsonl"], [listing])
        write_jsonl(paths["seller_questions"], [question])
        paths["investigation_csv"].parent.mkdir(parents=True, exist_ok=True)
        row = {field: "" for field in CSV_FIELDS}
        row.update(
            buyer_intelligence_schema_version="1",
            run_id="run-1",
            vehicle_key="ford_f350",
            source="autotrader",
            canonical_listing_id="listing-1",
        )
        with paths["investigation_csv"].open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerow(row)
        summary = {
            "buyer_intelligence_schema_version": 1,
            "run_id": "run-1",
            "vehicle_key": "ford_f350",
            "scope": "single_source",
            "sources": ["autotrader"],
            "listing_claim_count": 1,
            "source_listing_claim_counts": {"autotrader": 1},
            "artifacts": relative,
        }
        paths["market_summary_json"].write_text(
            json.dumps(summary), encoding="utf-8"
        )
        paths["market_summary_markdown"].write_text(
            "# F-350 Buyer Intelligence\n\n- Run ID: `run-1`\n",
            encoding="utf-8",
        )
        return paths

    def validate_fixture(self, root: Path):
        return validate_buyer_artifacts(
            root=root,
            config_path=Path("config_f350.json"),
            run_id="run-1",
            expected_sources=["autotrader"],
            validate_source_evidence=False,
        )

    def test_complete_artifact_set_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.create_artifacts(root)
            report = self.validate_fixture(root)
            self.assertEqual(report["validation_status"], "pass")
            self.assertEqual(
                report["source_evidence_validation_status"],
                "skipped_by_test_contract",
            )
            self.assertEqual(report["listing_count"], 1)
            self.assertEqual(report["question_record_count"], 1)
            self.assertEqual(report["csv_row_count"], 1)

    def test_forbidden_rank_key_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.create_artifacts(root)
            listing = json.loads(
                paths["investigation_jsonl"].read_text(encoding="utf-8")
            )
            listing["rank"] = 1
            paths["investigation_jsonl"].write_text(
                json.dumps(listing) + "\n", encoding="utf-8"
            )
            report = self.validate_fixture(root)
            self.assertEqual(report["validation_status"], "fail")
            self.assertTrue(
                any(
                    error.startswith("listing_forbidden_key")
                    for error in report["validation_errors"]
                )
            )

    def test_cross_file_count_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.create_artifacts(root)
            summary = json.loads(
                paths["market_summary_json"].read_text(encoding="utf-8")
            )
            summary["listing_claim_count"] = 2
            paths["market_summary_json"].write_text(
                json.dumps(summary), encoding="utf-8"
            )
            report = self.validate_fixture(root)
            self.assertIn(
                "summary_listing_count_mismatch", report["validation_errors"]
            )

    def test_current_source_evidence_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.create_artifacts(root)
            with mock.patch(
                "f350_buyer_validation.load_source_bundles",
                return_value=[],
            ):
                report = validate_buyer_artifacts(
                    root=root,
                    config_path=Path("config_f350.json"),
                    run_id="run-1",
                    expected_sources=["autotrader"],
                )
            self.assertEqual(report["validation_status"], "fail")
            self.assertEqual(
                report["source_evidence_validation_status"], "fail"
            )
            self.assertTrue(
                any(
                    error.startswith(
                        "buyer_listings_not_in_current_source_evidence"
                    )
                    for error in report["validation_errors"]
                )
            )


if __name__ == "__main__":
    unittest.main()
