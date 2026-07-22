import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autotrader_adapter import collect_autotrader
from autotrader_canonical import build_autotrader_canonical_evidence
from autotrader_distance import DistanceResult
from canonical_evidence import read_jsonl


def page_html(listings):
    payload = {
        "props": {
            "pageProps": {
                "totalResults": len(listings),
                "listings": listings,
            }
        }
    }
    return (
        '<html><script type="application/json">'
        + json.dumps(payload)
        + "</script></html>"
    )


def listing(identifier, *, price="$40,000"):
    return {
        "id": str(identifier),
        "url": f"https://example/{identifier}",
        "price": {"priceFormatted": price},
        "vehicle": {
            "modelYear": 2021,
            "make": "Ford",
            "model": "F-350",
            "modelVersionInput": "XLT",
            "mileageInKm": "100,000 km",
            "fuel": "Diesel",
            "engineDisplacementInCCM": "6700",
        },
        "location": {
            "city": "Calgary",
            "provinceCode": "AB",
            "street": "1 Main St",
            "zip": "T1T1T1",
        },
        "seller": {"companyName": "Dealer"},
    }


class Response:
    status_code = 200

    def __init__(self, text):
        self.text = text


class Session:
    def __init__(self, response):
        self.response = response

    def get(self, url, headers, timeout):
        return self.response


class CanonicalBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = {
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
                "home_coords": [52.2, -113.8],
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
        self.config_path = self.root / "config.json"
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")
        (self.root / "trim_tiers.json").write_text("{}", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def distance(_row):
        return DistanceResult(
            150,
            "geodesic_city_center",
            "straight_line_estimate_from_source_reported_location",
        )

    def test_adapter_boundary_reconciles_into_canonical_stages(self):
        malformed = listing("bad", price="not a price")
        adapter = collect_autotrader(
            root=self.root,
            config_path=self.config_path,
            run_id="run-1",
            session=Session(
                Response(page_html([listing("1"), listing("1"), malformed]))
            ),
            distance_resolver=self.distance,
            sleep=lambda _seconds: None,
        )
        self.assertEqual(adapter["fetched_records"], 3)

        evidence = build_autotrader_canonical_evidence(
            root=self.root,
            config=self.config,
            run_id="run-1",
        )
        self.assertTrue(evidence["reconciled"])
        self.assertEqual(
            evidence["fetched_record_scope"],
            "autotrader_adapter_response_listing_objects",
        )
        self.assertEqual(evidence["fetched_records"], 3)
        self.assertEqual(evidence["accepted_records"], 1)
        self.assertEqual(evidence["rejected_records"], 1)
        self.assertEqual(evidence["parse_failures"], 1)

        accepted = read_jsonl(self.root / evidence["artifacts"]["accepted"])
        rejected = read_jsonl(self.root / evidence["artifacts"]["rejected"])
        failures = read_jsonl(self.root / evidence["artifacts"]["parse_failures"])
        raw = read_jsonl(self.root / evidence["artifacts"]["raw"])
        self.assertEqual(
            (len(raw), len(accepted), len(rejected), len(failures)),
            (3, 1, 1, 1),
        )
        self.assertEqual(
            accepted[0]["field_evidence"]["distance_km"]["evidence_status"],
            "straight_line_estimate_from_source_reported_location",
        )
        self.assertEqual(
            accepted[0]["query_provenance"]["query_location"],
            "Calgary, AB",
        )
        self.assertIn(
            "duplicate_source_listing_identity",
            rejected[0]["rejection_reasons"],
        )
        self.assertIn("invalid_price", failures[0]["parse_failure_reasons"])


if __name__ == "__main__":
    unittest.main()
