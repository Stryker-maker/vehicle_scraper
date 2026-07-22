import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autotrader_adapter import build_search_url, collect_autotrader, extract_page_payload
from autotrader_distance import DistanceResult

FIXTURES = Path(__file__).parent / "fixtures"


def html(listings, total=None):
    page_props = {"listings": listings}
    if total is not None:
        page_props["totalResults"] = total
    return (
        '<html><script type="application/json">'
        + json.dumps({"props": {"pageProps": page_props}})
        + "</script></html>"
    )


def listing(
    index, *, year=2021, price="$40,000", fuel="Diesel",
    engine="6700", mileage="100,000 km",
):
    return {
        "id": str(index),
        "url": f"https://example/{index}",
        "price": {"priceFormatted": price},
        "vehicle": {
            "modelYear": year,
            "make": "Ford",
            "model": "F-350",
            "modelVersionInput": "XLT",
            "mileageInKm": mileage,
            "fuel": fuel,
            "engineDisplacementInCCM": engine,
        },
        "location": {
            "city": "Calgary", "provinceCode": "AB",
            "street": "1 Main St", "zip": "T1T1T1",
        },
        "seller": {"companyName": "Dealer"},
    }


class Response:
    def __init__(self, status, text):
        self.status_code = status
        self.text = text


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def get(self, url, headers, timeout):
        self.urls.append(url)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = {
            "schema_version": 2,
            "vehicle_key": "ford_f350",
            "make": "Ford",
            "model": "F-350",
            "criteria": {
                "min_year": 2015, "max_year": 2023,
                "max_price_cad": 60000, "fuel": "Diesel", "engine": "6.7L",
            },
            "origin": {
                "home_city": "Red Deer, AB", "home_coords": [52.2, -113.8],
                "max_distance_km": 800,
            },
            "sources": {
                "autotrader": {
                    "make": "ford", "model": "f-350",
                    "search_locations": ["Calgary, AB"],
                },
                "kijiji": {
                    "make": "Ford", "model": "F-350",
                    "search_locations": ["Calgary, AB"],
                },
            },
        }
        self.config_path = self.root / "config.json"
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")
        (self.root / "trim_tiers.json").write_text(
            json.dumps({"ford_f350": {"tier3": ["lariat"], "tier2": ["xlt"], "tier1": []}}),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def distance(_row):
        return DistanceResult(
            150, "geodesic_city_center",
            "straight_line_estimate_from_source_reported_location",
        )

    def test_search_url_contract(self):
        url = build_search_url(
            make_slug="ford", model_slug="f-350", location="Calgary, AB",
            fuel="Diesel", offset=100, page_size=100,
        )
        query = parse_qs(urlparse(url).query)
        self.assertEqual(query["rcp"], ["100"])
        self.assertEqual(query["rcs"], ["100"])
        self.assertEqual(query["loc"], ["Calgary, AB"])
        self.assertEqual(query["fuel"], ["Diesel"])

    def test_fixture_payload_extraction(self):
        rows, total = extract_page_payload(
            (FIXTURES / "autotrader_page_1.html").read_text(encoding="utf-8")
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(total, 3)

    def test_pagination_retry_reconciliation_and_no_ranking(self):
        session = Session([
            Response(500, "retry"),
            Response(200, (FIXTURES / "autotrader_page_1.html").read_text()),
            Response(200, (FIXTURES / "autotrader_page_2.html").read_text()),
        ])
        original = self.config_path.read_bytes()
        report = collect_autotrader(
            root=self.root, config_path=self.config_path, run_id="run-1",
            session=session, distance_resolver=self.distance, sleep=lambda _seconds: None,
            page_size=2, max_pages=5,
        )
        self.assertTrue(report["pagination_complete"])
        self.assertTrue(report["reconciled"])
        self.assertEqual(report["request_attempt_count"], 3)
        self.assertEqual(report["page_request_count"], 2)
        self.assertEqual(report["fetched_records"], 3)
        self.assertEqual(report["accepted_records"], 3)
        self.assertEqual(self.config_path.read_bytes(), original)
        header = (self.root / report["latest_output"]).read_text().splitlines()[0].split(",")
        self.assertNotIn("rank", header)
        self.assertNotIn("score", header)
        self.assertIn("distance_evidence_status", header)
        self.assertIn("rcs=2", session.urls[-1])

    def test_duplicate_and_parse_failure_are_preserved(self):
        broken = listing(2)
        broken["price"] = {"priceFormatted": "not a price"}
        session = Session([Response(200, html([listing(1), listing(1), broken, "bad"], total=4))])
        report = collect_autotrader(
            root=self.root, config_path=self.config_path, run_id="run-1",
            session=session, distance_resolver=self.distance, sleep=lambda _seconds: None,
        )
        self.assertEqual(report["fetched_records"], 4)
        self.assertEqual(report["accepted_records"], 1)
        self.assertEqual(report["rejected_records"], 1)
        self.assertEqual(report["parse_failures"], 2)
        records = [
            json.loads(line)
            for line in (self.root / report["artifacts"]["records"]).read_text().splitlines()
        ]
        self.assertIn("duplicate_source_listing_identity", records[1]["rejection_reasons"])
        self.assertIn("invalid_price", records[2]["parse_failure_reasons"])
        self.assertIn("listing_payload_not_object", records[3]["parse_failure_reasons"])

    def test_filter_reasons_and_truthful_distance(self):
        far = lambda _row: DistanceResult(
            900, "geodesic_city_center",
            "straight_line_estimate_from_source_reported_location",
        )
        session = Session([Response(200, html([
            listing(1, year=2010), listing(2, fuel="Gas"), listing(3),
        ], total=3))])
        report = collect_autotrader(
            root=self.root, config_path=self.config_path, run_id="run-1",
            session=session, distance_resolver=far, sleep=lambda _seconds: None,
        )
        self.assertEqual(report["accepted_records"], 0)
        self.assertEqual(report["rejected_records"], 3)
        records = [
            json.loads(line)
            for line in (self.root / report["artifacts"]["records"]).read_text().splitlines()
        ]
        self.assertIn("year_out_of_range", records[0]["rejection_reasons"])
        self.assertIn("fuel_mismatch", records[1]["rejection_reasons"])
        self.assertTrue(all("distance_out_of_range" in row["rejection_reasons"] for row in records))
        self.assertEqual(records[2]["parsed_row"]["distance_method"], "geodesic_city_center")
        self.assertEqual(
            records[2]["parsed_row"]["distance_evidence_status"],
            "straight_line_estimate_from_source_reported_location",
        )


if __name__ == "__main__":
    unittest.main()
