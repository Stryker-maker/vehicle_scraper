import re
import unittest
from pathlib import Path

from phase1_common import MANUAL_REVIEW_FIELDS


class DocumentationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]

    def read(self, path: str) -> str:
        return (self.root / path).read_text(encoding="utf-8")

    def test_required_authority_documents_exist_and_are_linked(self):
        required = [
            "docs/REPOSITORY_BASELINE.md",
            "docs/ARCHITECTURE_AND_DATA_FLOW.md",
            "docs/VEHICLE_PURPOSES.md",
            "docs/DATA_DICTIONARY.md",
            "docs/LIMITATIONS_REGISTER.md",
            "docs/LEGACY_COMPONENTS.md",
            "docs/AUDIT_ROADMAP.md",
            "AUDIT_03_CANONICAL_EVIDENCE.md",
            "AUDIT_04_AUTOTRADER_ADAPTER.md",
            "AUDIT_05_KIJIJI_ADAPTER.md",
            "AUDIT_06_IDENTITY_LIFECYCLE.md",
            "AUDIT_07_STORAGE_RETENTION.md",
            "AUDIT_08_CI_WORKFLOW_HARDENING.md",
            "AUDIT_09_F350_BUYER_INTELLIGENCE.md",
            "AUDIT_10_SECONDARY_PURPOSE_OUTPUTS.md",
            "AUDIT_11A_F150_MANUAL_REINTRODUCTION.md",
        ]
        readme = self.read("README.md")
        for path in required:
            self.assertTrue((self.root / path).is_file(), path)
            self.assertIn(path, readme)

    def test_readme_preserves_current_boundaries(self):
        readme = self.read("README.md")
        for obsolete in (
            "Price 60% | Mileage 25% | Distance 15%",
            "Edit `config.json`",
            "score | Ranking score (lower = better)",
            "phase1_kijiji_runner.py",
            "acknowledgement only",
        ):
            self.assertNotIn(obsolete, readme)
        for current in (
            "Automated cross-source ranking is disabled",
            "purpose_inputs.json",
            "purpose_outputs.py",
            "purpose_output_validation.py",
            "comparables_latest.jsonl",
            "owner_input_gaps_latest.json",
            "candidate_review_latest.jsonl",
            "requirements_summary_latest.json",
            "candidate_pending_requirements",
            "insufficient_multi_run_history",
            "not a verified faster-sale range",
            "fetched_records = accepted_records + rejected_records + parse_failures",
            "source_identifier_claim_not_vin",
            "candidate_only_not_merged",
            "Python is fixed to `3.11.13`",
        ):
            self.assertIn(current, readme)

    def test_data_dictionary_covers_general_and_purpose_fields(self):
        dictionary = self.read("docs/DATA_DICTIONARY.md")
        self.assertEqual(
            [field for field in MANUAL_REVIEW_FIELDS if field not in dictionary],
            [],
        )
        for value in (
            "owner_reported_historical_unverified",
            "owner_input_required",
            "friend_input_required",
            "friend_reported_unverified",
            "close_subject_comparable",
            "subject_profile_incomplete",
            "lower_observed_asking_band_not_verified_faster_sale_range_or_sale_probability",
            "listing_asking_price_changes_only_not_market_value_trend_or_sale_evidence",
            "candidate_pending_requirements",
            "candidate_outside_stated_preferences",
            "purpose_specific_candidate_classification_not_rank_not_score",
            "candidate_review_not_rank_not_recommendation_not_condition_verification",
            "price_observation_compaction_digest_sha256",
            "source_text_reported_unverified",
        ):
            self.assertIn(value, dictionary)

    def test_roadmap_status_and_limitations_are_current(self):
        roadmap = self.read("docs/AUDIT_ROADMAP.md")
        for number in range(12):
            self.assertRegex(roadmap, rf"## Audit {number:02d} — ")
        for row in (
            "| 09 | F-350 Buyer Intelligence | Complete and merged |",
            "| 10 | Secondary Purpose Outputs | Complete and merged |",
            "| 11A | Ford F-150 Manual Reintroduction | Implemented; live validation pending |",
            "| 11B | Toyota Tundra Reconsideration | Pending owner decision |",
        ):
            self.assertIn(row, roadmap)
        register = self.read("docs/LIMITATIONS_REGISTER.md")
        identifiers = re.findall(r"\| (LIM-\d{3}) \|", register)
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertGreaterEqual(len(identifiers), 54)
        for identifier in (
            "LIM-048",
            "LIM-049",
            "LIM-050",
            "LIM-051",
            "LIM-052",
            "LIM-053",
            "LIM-054",
            "LIM-055",
            "LIM-056",
        ):
            self.assertIn(identifier, register)

    def test_legacy_and_operating_guidance_prevent_inference(self):
        legacy = self.read("docs/LEGACY_COMPONENTS.md")
        guidance = self.read("PHASE1_MANUAL_REVIEW.md")
        for value in (
            "not current odometer",
            "subject_profile_incomplete",
            "candidate_pending_requirements",
            "verified faster-sale range",
        ):
            self.assertIn(value, legacy)
        for value in (
            "active interim operating guidance",
            "What Phase 1 does not prove",
            "seven-day evidence",
            "market_snapshot_latest.md",
            "current odometer",
            "requirements_summary_latest.md",
            "questions_for_friend",
            "Never apply F-350 truck assumptions",
        ):
            self.assertIn(value, guidance)

    def test_audit_contracts_preserve_stop_conditions(self):
        for path in (
            "AUDIT_03_CANONICAL_EVIDENCE.md",
            "AUDIT_04_AUTOTRADER_ADAPTER.md",
            "AUDIT_06_IDENTITY_LIFECYCLE.md",
            "AUDIT_07_STORAGE_RETENTION.md",
            "AUDIT_08_CI_WORKFLOW_HARDENING.md",
            "AUDIT_09_F350_BUYER_INTELLIGENCE.md",
            "AUDIT_10_SECONDARY_PURPOSE_OUTPUTS.md",
            "AUDIT_11A_F150_MANUAL_REINTRODUCTION.md",
        ):
            self.assertIn("Stop and revise before merge", self.read(path))
        audit10 = self.read("AUDIT_10_SECONDARY_PURPOSE_OUTPUTS.md")
        for value in (
            "historical owner-reported, unverified claims",
            "friend_input_required",
            "lower_observed_asking_band_not_verified_faster_sale_range_or_sale_probability",
            "insufficient_multi_run_history",
            "candidate_pending_requirements",
            "purpose_output_validation.py",
            "no rank or score",
            "Audit 10 does not change source requests",
        ):
            self.assertIn(value, audit10)


if __name__ == "__main__":
    unittest.main()
