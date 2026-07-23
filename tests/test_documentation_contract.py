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
            "acknowledgement only",
        ):
            self.assertNotIn(obsolete, readme)
        for current in (
            "vehicle_registry.json",
            "manual_review_latest.csv",
            "Automated cross-source ranking is disabled",
            "canonical_evidence.py",
            "identity_lifecycle.py",
            "storage_retention.py",
            "requirements.lock",
            "workflow_control.py",
            "workflow_anomalies.py",
            "generated_data_publish.py",
            "generated_data_validation.py",
            "fetched_records = accepted_records + rejected_records + parse_failures",
            "autotrader_adapter_response_listing_objects",
            "kijiji_adapter_json_ld_listing_objects",
            "source_identifier_claim_not_vin",
            "candidate_only_not_merged",
            "Python `3.11.13`",
            "eight timestamped source CSVs",
            "four timestamped manual-review CSVs",
            "50 MiB",
            "500 MiB",
        ):
            self.assertIn(current, readme)

    def test_data_dictionary_covers_supported_fields_and_new_schemas(self):
        dictionary = self.read("docs/DATA_DICTIONARY.md")
        missing = [field for field in MANUAL_REVIEW_FIELDS if field not in dictionary]
        self.assertEqual(missing, [])
        for value in (
            "autotrader_adapter_response_listing_objects",
            "kijiji_adapter_json_ld_listing_objects",
            "source_identifier_claim_not_vin",
            "query_origin_never_location",
            "source_reported_format_valid_unverified",
            "candidate_only_not_merged",
            "retained_price_observation_count",
            "price_observation_compaction_digest_sha256",
            "deletion_chain_sha256",
            "Workflow-control schema version 1",
            "Anomaly schema version 1",
            "Publication manifest schema version 1",
            "Generated-data validation schema version 1",
            "Dependency-lock schema version 1",
            "published_paths",
            "critical_anomaly_count",
        ):
            self.assertIn(value, dictionary)

    def test_approved_roadmap_preserves_every_audit_package(self):
        roadmap = self.read("docs/AUDIT_ROADMAP.md")
        for number in range(12):
            self.assertRegex(roadmap, rf"## Audit {number:02d} — ")
        for row in (
            "| 00 | Scope Freeze and Runtime Reduction | Complete and merged |",
            "| 05 | Kijiji Collector Replacement | Complete and merged |",
            "| 06 | Identity, Deduplication and Listing Lifecycle | Complete and merged |",
            "| 07 | Storage, Retention and Repository Hygiene | Complete and merged |",
            "| 08 | CI and Workflow Hardening | Implemented; deterministic validation and owner merge pending |",
            "| 11 | Optional Search Reintroduction | Approved final stage |",
        ):
            self.assertIn(row, roadmap)

    def test_limitations_have_unique_identifiers(self):
        register = self.read("docs/LIMITATIONS_REGISTER.md")
        identifiers = re.findall(r"LIM-\d{3}", register)
        self.assertGreaterEqual(len(set(identifiers)), 43)
        table_identifiers = re.findall(r"\| (LIM-\d{3}) \|", register)
        self.assertEqual(len(table_identifiers), len(set(table_identifiers)))
        for identifier in ("LIM-034", "LIM-039", "LIM-040", "LIM-043"):
            self.assertIn(identifier, register)

    def test_legacy_merger_history_and_acknowledgement_are_not_supported(self):
        merger = self.read("merge.py")
        collection = self.read(".github/workflows/scrape.yml")
        generated = self.read(".github/workflows/generated-data.yml")
        legacy = self.read("docs/LEGACY_COMPONENTS.md")
        self.assertIn("LEGACY / DISABLED", merger)
        self.assertIn("merge.py", legacy)
        self.assertNotIn("python merge.py", collection)
        self.assertIn("Acknowledgement-only generated-data workflow", legacy)
        self.assertIn("generated_data_validation.py", generated)
        self.assertNotIn("acknowledge-generated-data", collection + generated)

    def test_phase1_guidance_covers_current_workflows(self):
        guidance = self.read("PHASE1_MANUAL_REVIEW.md")
        for value in (
            "active interim operating guidance",
            "What Phase 1 does not prove",
            "identity_lifecycle",
            "single_pair",
            "seven-day evidence",
            ".github/workflows/ci.yml",
            ".github/workflows/generated-data.yml",
            ".github/workflows/scrape.yml",
            "publication_latest.json",
            "anomalies_latest.json",
            "Python `3.11.13`",
        ):
            self.assertIn(value, guidance)

    def test_audit_contracts_preserve_stop_conditions(self):
        for path in (
            "AUDIT_03_CANONICAL_EVIDENCE.md",
            "AUDIT_04_AUTOTRADER_ADAPTER.md",
            "AUDIT_06_IDENTITY_LIFECYCLE.md",
            "AUDIT_07_STORAGE_RETENTION.md",
            "AUDIT_08_CI_WORKFLOW_HARDENING.md",
        ):
            self.assertIn("Stop and revise before merge", self.read(path))
        audit05 = self.read("AUDIT_05_KIJIJI_ADAPTER.md")
        self.assertIn("query origin never becomes listing location", audit05)
        audit08 = self.read("AUDIT_08_CI_WORKFLOW_HARDENING.md")
        for value in (
            "requirements.lock",
            "Python `3.11.13`",
            "workflow_anomalies.py",
            "publication_latest.json",
            "remote ref changes",
            "generated-data pull requests",
        ):
            self.assertIn(value, audit08)


if __name__ == "__main__":
    unittest.main()
