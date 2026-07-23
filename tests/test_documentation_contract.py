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
        ]
        readme = self.read("README.md")
        for path in required:
            self.assertTrue((self.root / path).is_file(), path)
            self.assertIn(path, readme)

    def test_readme_preserves_current_boundaries(self):
        readme = self.read("README.md")
        for obsolete in (
            "Automated AutoTrader.ca scraper for Ford F-350 diesel trucks",
            "Price 60% | Mileage 25% | Distance 15%",
            "Edit `config.json`",
            "Weekly AutoTrader Scrape",
            "score | Ranking score (lower = better)",
            "phase1_kijiji_runner.py",
        ):
            self.assertNotIn(obsolete, readme)
        for current in (
            "vehicle_registry.json",
            "manual_review_latest.csv",
            "Automated cross-source ranking is disabled",
            "canonical_evidence.py",
            "identity_lifecycle.py",
            "autotrader_*.py",
            "kijiji_*.py",
            "fetched_records = accepted_records + rejected_records + parse_failures",
            "autotrader_adapter_response_listing_objects",
            "kijiji_adapter_json_ld_listing_objects",
            "source_identifier_claim_not_vin",
            "candidate_only_not_merged",
            "price_history_*.json",
        ):
            self.assertIn(current, readme)

    def test_data_dictionary_covers_supported_manual_review_fields(self):
        dictionary = self.read("docs/DATA_DICTIONARY.md")
        missing = [
            field for field in MANUAL_REVIEW_FIELDS
            if f"`{field}`" not in dictionary
        ]
        self.assertEqual(missing, [])
        for value in (
            "autotrader_adapter_response_listing_objects",
            "kijiji_adapter_json_ld_listing_objects",
            "source_identifier_claim_not_vin",
            "straight_line_estimate_from_source_reported_location",
            "source_reported_listing_specific_unverified",
            "query_origin_never_location",
            "source_reported_format_valid_unverified",
            "candidate_only_not_merged",
            "active", "missing", "reappeared", "retired",
        ):
            self.assertIn(value, dictionary)

    def test_approved_roadmap_preserves_every_audit_package(self):
        roadmap = self.read("docs/AUDIT_ROADMAP.md")
        for number in range(12):
            self.assertRegex(roadmap, rf"## Audit {number:02d} — ")
        self.assertIn(
            "| 00 | Scope Freeze and Runtime Reduction | Complete and merged |",
            roadmap,
        )
        self.assertIn(
            "| 05 | Kijiji Collector Replacement | Complete and merged |",
            roadmap,
        )
        self.assertIn(
            "| 06 | Identity, Deduplication and Listing Lifecycle | "
            "Implemented; deterministic validation and owner merge pending |",
            roadmap,
        )
        self.assertIn(
            "| 11 | Optional Search Reintroduction | Approved final stage |",
            roadmap,
        )

    def test_limitations_have_unique_identifiers(self):
        register = self.read("docs/LIMITATIONS_REGISTER.md")
        identifiers = re.findall(r"LIM-\d{3}", register)
        self.assertGreaterEqual(len(set(identifiers)), 34)
        table_identifiers = re.findall(r"\| (LIM-\d{3}) \|", register)
        self.assertEqual(len(table_identifiers), len(set(table_identifiers)))
        self.assertIn("LIM-034", register)

    def test_legacy_merger_and_history_are_not_supported(self):
        merger = self.read("merge.py")
        workflow = self.read(".github/workflows/scrape.yml")
        legacy = self.read("docs/LEGACY_COMPONENTS.md")
        readme = self.read("README.md")
        self.assertIn("LEGACY / DISABLED", merger)
        self.assertIn("merge.py", legacy)
        self.assertNotIn("python merge.py", workflow)
        self.assertIn("Historical merged", readme)
        self.assertIn("price_history_*.json", readme)

    def test_phase1_guidance_points_to_current_authorities(self):
        guidance = self.read("PHASE1_MANUAL_REVIEW.md")
        for value in (
            "active interim operating guidance",
            "docs/REPOSITORY_BASELINE.md",
            "docs/LIMITATIONS_REGISTER.md",
            "AUDIT_03_CANONICAL_EVIDENCE.md",
            "AUDIT_04_AUTOTRADER_ADAPTER.md",
            "AUDIT_05_KIJIJI_ADAPTER.md",
            "AUDIT_06_IDENTITY_LIFECYCLE.md",
            "What Phase 1 does not prove",
            "accepted_latest.jsonl",
            "identity_lifecycle",
            "single_pair",
        ):
            self.assertIn(value, guidance)

    def test_audit_contracts_preserve_stop_conditions(self):
        audit03 = self.read("AUDIT_03_CANONICAL_EVIDENCE.md")
        self.assertIn("legacy_collector_emitted_csv_rows", audit03)
        self.assertIn("Stop and revise before merge", audit03)
        audit04 = self.read("AUDIT_04_AUTOTRADER_ADAPTER.md")
        self.assertIn("autotrader_adapter_response_listing_objects", audit04)
        self.assertIn("Stop and revise before merge", audit04)
        audit05 = self.read("AUDIT_05_KIJIJI_ADAPTER.md")
        self.assertIn("kijiji_adapter_json_ld_listing_objects", audit05)
        self.assertIn("query origin never becomes listing location", audit05)
        audit06 = self.read("AUDIT_06_IDENTITY_LIFECYCLE.md")
        for value in (
            "source_identifier_claim_not_vin",
            "candidate_only_not_merged",
            "active", "missing", "reappeared", "retired",
            "Stop and revise before merge",
            "price_history_*.json",
        ):
            self.assertIn(value, audit06)


if __name__ == "__main__":
    unittest.main()
