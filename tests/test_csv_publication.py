import unittest
import csv
import subprocess
import tempfile
from pathlib import Path

from autotrader_history import write_csv_outputs as at_write_csv
from kijiji_history import write_csv_outputs as kj_write_csv
from purpose_outputs import _write_csv as purpose_write_csv
from f350_buyer_intelligence import build as build_f350_buyer_intelligence


class TestCSVPublicationWhitespace(unittest.TestCase):
    def test_autotrader_csv_line_endings_and_git_check(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config = {"vehicle_key": "ford_f350"}
            rows = [{"year": 2023, "price": 50000, "make": "Ford", "model": "F-350"}]
            archive, latest = at_write_csv(root, config, rows)

            for path in (archive, latest):
                content_bytes = path.read_bytes()
                self.assertNotIn(b"\r\n", content_bytes)
                self.assertIn(b"\n", content_bytes)

            # Test git diff --cached --check compatibility
            repo_dir = root / "repo"
            repo_dir.mkdir()
            subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
            test_csv = repo_dir / "test.csv"
            test_csv.write_bytes(latest.read_bytes())
            subprocess.run(["git", "add", "test.csv"], cwd=repo_dir, check=True, capture_output=True)
            res = subprocess.run(
                ["git", "diff", "--cached", "--check"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"git diff --check output: {res.stdout}")

    def test_kijiji_csv_line_endings_and_git_check(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config = {"vehicle_key": "ford_f350"}
            rows = [{"year": 2023, "price": 50000, "make": "Ford", "model": "F-350"}]
            archive, latest = kj_write_csv(root, config, rows)

            for path in (archive, latest):
                content_bytes = path.read_bytes()
                self.assertNotIn(b"\r\n", content_bytes)
                self.assertIn(b"\n", content_bytes)

    def test_purpose_outputs_csv_line_endings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test_purpose.csv"
            fieldnames = ["a", "b"]
            records = [{"a": "val1", "b": "val2"}]
            purpose_write_csv(csv_path, fieldnames, records)

            content_bytes = csv_path.read_bytes()
            self.assertNotIn(b"\r\n", content_bytes)
            self.assertIn(b"\n", content_bytes)


if __name__ == "__main__":
    unittest.main()
