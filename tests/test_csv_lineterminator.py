from __future__ import annotations

import csv
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from autotrader_history import write_csv_outputs as write_autotrader_csv_outputs
from kijiji_history import write_csv_outputs as write_kijiji_csv_outputs


class CsvLineTerminatorTests(unittest.TestCase):
    def _git_env(self, root: Path) -> dict[str, str]:
        env = os.environ.copy()
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["HOME"] = str(root / "home")
        env["XDG_CONFIG_HOME"] = str(root / "config")
        return env

    def _assert_publication_safe(self, writer, source: str) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = {"vehicle_key": "test_vehicle"}
            rows = [
                {
                    "year": "2020",
                    "make": "Ford",
                    "model": "F-350",
                    "trim": "Lariat",
                    "price": "65000",
                    "mileage": "100000",
                    "location": "Calgary, AB",
                    "source": source,
                }
            ]

            archive, latest = writer(root, config, rows)
            outputs = (archive, latest)
            for output in outputs:
                raw = output.read_bytes()
                self.assertNotIn(b"\r\n", raw)
                self.assertNotIn(b"\r", raw)
                with output.open("r", encoding="utf-8", newline="") as handle:
                    parsed = list(csv.reader(handle))
                self.assertGreaterEqual(len(parsed), 2)
                header = parsed[0]
                values = parsed[1]
                self.assertEqual(values[header.index("location")], "Calgary, AB")
                self.assertEqual(values[header.index("price")], "65000")

            env = self._git_env(root)
            subprocess.run(
                ["git", "-c", "core.autocrlf=false", "init"],
                cwd=root,
                check=True,
                capture_output=True,
                env=env,
            )
            subprocess.run(
                ["git", "add", "data"],
                cwd=root,
                check=True,
                capture_output=True,
                env=env,
            )
            check = subprocess.run(
                ["git", "diff", "--cached", "--check"],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
                env=env,
            )
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def test_autotrader_csv_is_lf_and_git_diff_check_clean(self):
        self._assert_publication_safe(write_autotrader_csv_outputs, "AutoTrader")

    def test_kijiji_csv_is_lf_and_git_diff_check_clean(self):
        self._assert_publication_safe(write_kijiji_csv_outputs, "Kijiji")


if __name__ == "__main__":
    unittest.main()
