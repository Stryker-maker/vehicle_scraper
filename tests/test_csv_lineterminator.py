from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autotrader_history import write_csv_outputs as at_write_csv
from f350_buyer_intelligence import CSV_FIELDS, csv_row
import f350_buyer_intelligence as f350_bi
from kijiji_history import write_csv_outputs as kj_write_csv
from phase1_reporting import MANUAL_REVIEW_FIELDS
import phase1_reporting as pr
from purpose_outputs import OWNED_CSV_FIELDS, _write_csv


class TestCsvLineterminator(unittest.TestCase):
    def test_autotrader_csv_lineterminator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = {"vehicle_key": "ford_f150"}
            rows = [{"listing_id": "1", "price": "10000"}]
            archive, latest = at_write_csv(root, config, rows)
            for p in (archive, latest):
                content = p.read_bytes()
                self.assertNotIn(b"\r", content)
                self.assertIn(b"\n", content)

    def test_kijiji_csv_lineterminator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = {"vehicle_key": "ford_f150"}
            rows = [{"listing_id": "1", "price": "10000"}]
            archive, latest = kj_write_csv(root, config, rows)
            for p in (archive, latest):
                content = p.read_bytes()
                self.assertNotIn(b"\r", content)
                self.assertIn(b"\n", content)

    def test_purpose_outputs_csv_lineterminator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "test.csv"
            records = [{"run_id": "1", "scope": "full"}]
            _write_csv(csv_path, OWNED_CSV_FIELDS, records)
            content = csv_path.read_bytes()
            self.assertNotIn(b"\r", content)
            self.assertIn(b"\n", content)


if __name__ == "__main__":
    unittest.main()
