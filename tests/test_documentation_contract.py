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
        ]
        readme = self.read("README.md")
        for path in required:
            self.assertTrue((self.root / path).is_file(), path)
            self.assertIn(path, readme)

    def test_readme_does_not_preserve_obsolete_project_claims(self):
        readme = self.read("README.md")
        obsolete = [
            "Automated AutoTrader.ca scraper for Ford F-350 diesel trucks",
            "Price 60% | Mileage 25% | Distance 15%",
            "Edit `config.json`",
            "Weekly AutoTrader Scrape",
            "score | Ranking score (lower = better)",
        ]
        for claim in obsolete:
            self.assertNotIn(claim, readme)
        self.assertIn("vehicle_registry.json", readme)
        self.assertIn("manual_review_latest.csv", readme)
        self.assertIn("Automated cross-source ranking is disabled", readme)

    def test_data_dictionary_covers_supported_manual_review_fields(self):
        dictionary = self.read("docs/DATA_DICTIONARY.md")
        missing = [field for field in MANUAL_REVIEW_FIELDS if f"`{field}`" not in dictionary]
        self.assertEqual(missing, [])

    def test_approved_roadmap_preserves_every_audit_package(self):
        roadmap = self.read("docs/AUDIT_ROADMAP.md")
        for number in range(12):
            self.assertRegex(roadmap, rf"## Audit {number:02d} — ")
        self.assertIn("| 00 | Scope Freeze and Runtime Reduction | Complete and merged |", roadmap)
        self.assertIn("| 11 | Optional Search Reintroduction | Approved final stage |", roadmap)

    def test_limitations_have_unique_identifiers(self):
        register = self.read("docs/LIMITATIONS_REGISTER.md")
        identifiers = re.findall(r"LIM-\d{3}", register)
        self.assertGreaterEqual(len(set(identifiers)), 20)
        table_identifiers = re.findall(r"\| (LIM-\d{3}) \|", register)
        self.assertEqual(len(table_identifiers), len(set(table_identifiers)))

    def test_legacy_merger_is_marked_and_not_automated(self):
        merger = self.read("merge.py")
        workflow = self.read(".github/workflows/scrape.yml")
        legacy = self.read("docs/LEGACY_COMPONENTS.md")
        self.assertIn("LEGACY / DISABLED", merger)
        self.assertIn("merge.py", legacy)
        self.assertNotIn("python merge.py", workflow)
        self.assertIn("historical merged CSV", self.read("README.md"))

    def test_phase1_guidance_points_to_current_authorities(self):
        guidance = self.read("PHASE1_MANUAL_REVIEW.md")
        self.assertIn("active interim operating guidance", guidance)
        self.assertIn("docs/REPOSITORY_BASELINE.md", guidance)
        self.assertIn("docs/LIMITATIONS_REGISTER.md", guidance)
        self.assertIn("What Phase 1 does not prove", guidance)


if __name__ == "__main__":
    unittest.main()
