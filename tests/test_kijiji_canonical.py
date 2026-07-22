import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from canonical_evidence import read_jsonl
from kijiji_adapter import collect_kijiji
from kijiji_canonical import build_kijiji_canonical_evidence


def listing(identifier, *, price="45000", with_location=True):
    offers = {"price": price}
    if with_location:
        offers["availableAtOrFrom"] = {
            "address": {
                "addressLocality": "Toronto",
                "addressRegion": "ON",
            }
        }
    return {
        "@type": "Vehicle",
        "sku": str(identifier),
        "name": "2021 Ford F-350 XLT 6.7L diesel",
        "url": f"https://www.kijiji.ca/v-cars-trucks/toronto-gta/x/{identifier}",
        "vehicleModelDate": "2021",
        "mileageFromOdometer": {"value": "100000"},
        "offers": offers,
        "seller": {"name": "Dealer"},
    }


def page_html(items):
    return (
        '<script type="application/ld+json">'
        + json.dumps(
            {
                "@type": "ItemList",
                "itemListElement": [{"item": item} for item in items],
            }
        )
        + "</script>"
    )


class Response:
    status_code = 200

    def __init__(self, text):
        self.text = text


class Session:
    def __init__(self, response):
        self.response = response

    def get(self, url, headers, timeout):
        return self.response


class KijijiCanonicalTests(unittest.TestCase):
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
        (self.root / "trim_tiers.json").write_text("{}", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_adapter_boundary_reconciles_and_restores_only_listing_geography(self):
        malformed = listing("bad", price="not-price")
        adapter = collect_kijiji(
            root=self.root,
            config_path=self.config_path,
            run_id="run-1",
            session=Session(
                Response(
                    page_html(
                        [listing("1"), listing("1"), listing("2", with_location=False), malformed]
                    )
                )
            ),
            sleep=lambda _seconds: None,
        )
        self.assertEqual(adapter["fetched_records"], 4)
        evidence = build_kijiji_canonical_evidence(
            root=self.root,
            config=self.config,
            run_id="run-1",
        )
        self.assertTrue(evidence["reconciled"])
        self.assertEqual(
            evidence["fetched_record_scope"],
            "kijiji_adapter_json_ld_listing_objects",
        )
        self.assertEqual(evidence["accepted_records"], 2)
        self.assertEqual(evidence["rejected_records"], 1)
        self.assertEqual(evidence["parse_failures"], 1)

        accepted = read_jsonl(self.root / evidence["artifacts"]["accepted"])
        rejected = read_jsonl(self.root / evidence["artifacts"]["rejected"])
        failures = read_jsonl(
            self.root / evidence["artifacts"]["parse_failures"]
        )
        locations = {record["source_listing_id"]: record for record in accepted}
        self.assertEqual(locations["1"]["normalized"]["location"], "Toronto, ON")
        self.assertEqual(
            locations["1"]["field_evidence"]["location"]["evidence_status"],
            "source_reported_listing_specific_unverified",
        )
        self.assertIsNone(locations["2"]["normalized"]["location"])
        self.assertEqual(
            locations["2"]["field_evidence"]["location"]["evidence_status"],
            "unknown",
        )
        self.assertEqual(
            locations["1"]["query_provenance"]["query_location"],
            "Edmonton, AB",
        )
        self.assertNotEqual(
            locations["1"]["normalized"]["location"],
            locations["1"]["query_provenance"]["query_location"],
        )
        self.assertIsNone(locations["1"]["normalized"]["distance_km"])
        self.assertIn(
            "duplicate_source_listing_identity",
            rejected[0]["rejection_reasons"],
        )
        self.assertIn("invalid_price", failures[0]["parse_failure_reasons"])

    def test_wrong_adapter_run_is_rejected(self):
        collect_kijiji(
            root=self.root,
            config_path=self.config_path,
            run_id="other-run",
            session=Session(Response(page_html([listing("1")]))),
            sleep=lambda _seconds: None,
        )
        with self.assertRaisesRegex(ValueError, "run_id mismatch"):
            build_kijiji_canonical_evidence(
                root=self.root,
                config=self.config,
                run_id="run-1",
            )


if __name__ == "__main__":
    unittest.main()
