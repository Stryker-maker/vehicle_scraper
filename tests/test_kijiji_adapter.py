import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kijiji_adapter import (
    build_search_url,
    collect_kijiji,
    extract_page_payload,
    parse_listing,
)
from kijiji_locations import query_location, validate_query_locations

FIXTURES = Path(__file__).parent / "fixtures"


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


def listing(
    identifier,
    *,
    city="Toronto",
    region="ON",
    price="55000",
    year="2022",
    with_location=True,
):
    offers = {"price": price}
    if with_location:
        offers["availableAtOrFrom"] = {
            "address": {
                "addressLocality": city,
                "addressRegion": region,
            }
        }
    return {
        "@type": "Vehicle",
        "sku": str(identifier),
        "name": f"{year} Ford F-350 XLT 6.7L diesel",
        "description": "No accidents reported",
        "url": (
            f"https://www.kijiji.ca/v-cars-trucks/"
            f"{city.lower().replace(' ', '-')}/vehicle/{identifier}"
        ),
        "vehicleModelDate": year,
        "mileageFromOdometer": {"value": "123000"},
        "offers": offers,
        "seller": {"name": "Dealer"},
    }


def page_html(items):
    payload = {
        "@type": "ItemList",
        "itemListElement": [{"item": item} for item in items],
    }
    return (
        '<html><script type="application/ld+json">'
        + json.dumps(payload)
        + "</script></html>"
    )


class KijijiAdapterTests(unittest.TestCase):
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
                    "search_locations": ["Edmonton, AB"],
                },
            },
        }
        self.config_path = self.root / "config.json"
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")
        (self.root / "trim_tiers.json").write_text(
            json.dumps(
                {
                    "ford_f350": {
                        "tier3": ["Lariat"],
                        "tier2": ["XLT"],
                        "tier1": [],
                    }
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_validated_location_registry_and_search_url(self):
        descriptor = query_location("Edmonton, AB")
        self.assertEqual(descriptor["location_id"], "1700202")
        url = build_search_url(
            make="Ford",
            model="F-350",
            query_location=descriptor,
            page=2,
        )
        self.assertIn(
            "/edmonton-area/ford-f-350/page-2/k0c174l1700202",
            url,
        )
        with self.assertRaises(ValueError):
            validate_query_locations(["Camrose, AB"])

    def test_two_page_fixture_retry_and_reconciliation(self):
        first = (FIXTURES / "kijiji_page_1.html").read_text(encoding="utf-8")
        second = (FIXTURES / "kijiji_page_2.html").read_text(encoding="utf-8")
        rows, errors = extract_page_payload(first)
        self.assertEqual(len(rows), 2)
        self.assertEqual(errors, [])
        original = self.config_path.read_bytes()
        session = Session(
            [Response(500, "retry"), Response(200, first), Response(200, second)]
        )
        report = collect_kijiji(
            root=self.root,
            config_path=self.config_path,
            run_id="run-1",
            session=session,
            sleep=lambda _seconds: None,
            page_size=2,
            max_pages=5,
        )
        self.assertTrue(report["pagination_complete"])
        self.assertTrue(report["reconciled"])
        self.assertEqual(report["request_attempt_count"], 3)
        self.assertEqual(report["page_request_count"], 2)
        self.assertEqual(report["fetched_records"], 3)
        self.assertEqual(report["accepted_records"], 3)
        self.assertEqual(report["listing_specific_location_records"], 2)
        self.assertEqual(report["unknown_location_records"], 1)
        self.assertEqual(self.config_path.read_bytes(), original)
        with (self.root / report["latest_output"]).open(
            encoding="utf-8", newline=""
        ) as handle:
            header = next(csv.reader(handle))
        self.assertNotIn("rank", header)
        self.assertNotIn("score", header)
        self.assertIn("query_location_id", header)
        self.assertIn("page-2", session.urls[-1])

    def test_query_origin_never_replaces_listing_location(self):
        row, rejections, failures = parse_listing(
            listing("1", city="Toronto", region="ON"),
            config=self.config,
            tiers={"tier1": [], "tier2": [], "tier3": []},
            provenance={"query_location": "Edmonton, AB"},
        )
        self.assertEqual(rejections, [])
        self.assertEqual(failures, [])
        self.assertEqual(row["location"], "Toronto, ON")
        self.assertNotEqual(row["location"], "Edmonton, AB")
        self.assertEqual(
            row["location_evidence_status"],
            "source_reported_listing_specific_unverified",
        )

    def test_missing_listing_location_remains_unknown(self):
        row, rejections, failures = parse_listing(
            listing("2", with_location=False),
            config=self.config,
            tiers={"tier1": [], "tier2": [], "tier3": []},
            provenance={"query_location": "Edmonton, AB"},
        )
        self.assertEqual(rejections, [])
        self.assertEqual(failures, [])
        self.assertEqual(row["location"], "")
        self.assertEqual(row["dealer_address"], "")
        self.assertEqual(row["location_evidence_status"], "unknown")
        self.assertEqual(row["distance_km"], "")

    def test_duplicate_and_parse_failures_are_preserved(self):
        broken = listing("3", price="not-price")
        session = Session(
            [Response(200, page_html([listing("1"), listing("1"), broken, "bad"]))]
        )
        report = collect_kijiji(
            root=self.root,
            config_path=self.config_path,
            run_id="run-1",
            session=session,
            sleep=lambda _seconds: None,
        )
        self.assertEqual(report["fetched_records"], 4)
        self.assertEqual(report["accepted_records"], 1)
        self.assertEqual(report["rejected_records"], 1)
        self.assertEqual(report["parse_failures"], 2)
        records = [
            json.loads(line)
            for line in (
                self.root / report["artifacts"]["records"]
            ).read_text(encoding="utf-8").splitlines()
        ]
        self.assertIn(
            "duplicate_source_listing_identity",
            records[1]["rejection_reasons"],
        )
        self.assertIn("invalid_price", records[2]["parse_failure_reasons"])
        self.assertIn(
            "listing_payload_not_object",
            records[3]["parse_failure_reasons"],
        )

    def test_legitimate_empty_terminal_page_succeeds(self):
        empty_page = page_html([])
        session = Session([Response(200, empty_page)])
        report = collect_kijiji(
            root=self.root,
            config_path=self.config_path,
            run_id="run-empty",
            session=session,
            sleep=lambda _seconds: None,
        )
        self.assertTrue(report["pagination_complete"])
        self.assertEqual(report["successful_page_count"], 1)
        self.assertEqual(report["failed_page_count"], 0)
        requests = [
            json.loads(line)
            for line in (
                self.root / report["artifacts"]["requests"]
            ).read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(requests[0]["page_status"], "success")
        self.assertEqual(requests[0]["stop_reason"], "empty_page")

    def test_explicit_block_marker_fails_with_suspected_block(self):
        block_page = (
            "<html><head><title>Access Denied</title></head>"
            "<body>Please complete the CAPTCHA to verify you are human.</body></html>"
        )
        session = Session([Response(200, block_page)])
        report = collect_kijiji(
            root=self.root,
            config_path=self.config_path,
            run_id="run-block",
            session=session,
            sleep=lambda _seconds: None,
        )
        self.assertFalse(report["pagination_complete"])
        self.assertEqual(report["successful_page_count"], 0)
        self.assertEqual(report["failed_page_count"], 1)
        requests = [
            json.loads(line)
            for line in (
                self.root / report["artifacts"]["requests"]
            ).read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(requests[0]["page_status"], "failed")
        self.assertEqual(requests[0]["stop_reason"], "suspected_block")

    def test_structurally_suspicious_empty_page_fails_with_suspected_block(self):
        suspicious_page = "<html><head><title>Blank</title></head><body>Nothing here</body></html>"
        session = Session([Response(200, suspicious_page)])
        report = collect_kijiji(
            root=self.root,
            config_path=self.config_path,
            run_id="run-suspicious",
            session=session,
            sleep=lambda _seconds: None,
        )
        self.assertFalse(report["pagination_complete"])
        self.assertEqual(report["successful_page_count"], 0)
        self.assertEqual(report["failed_page_count"], 1)
        requests = [
            json.loads(line)
            for line in (
                self.root / report["artifacts"]["requests"]
            ).read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(requests[0]["page_status"], "failed")
        self.assertEqual(requests[0]["stop_reason"], "suspected_block")

    def test_populated_page_followed_by_empty_terminal_page(self):
        populated_page = page_html([listing("1"), listing("2")])
        empty_page = page_html([])
        session = Session([Response(200, populated_page), Response(200, empty_page)])
        report = collect_kijiji(
            root=self.root,
            config_path=self.config_path,
            run_id="run-populated",
            session=session,
            sleep=lambda _seconds: None,
            page_size=2,
        )
        self.assertTrue(report["pagination_complete"])
        self.assertEqual(report["successful_page_count"], 2)
        self.assertEqual(report["failed_page_count"], 0)
        requests = [
            json.loads(line)
            for line in (
                self.root / report["artifacts"]["requests"]
            ).read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(requests[0]["page_status"], "success")
        self.assertEqual(requests[1]["page_status"], "success")
        self.assertEqual(requests[1]["stop_reason"], "empty_page")


if __name__ == "__main__":
    unittest.main()
