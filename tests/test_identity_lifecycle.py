import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from canonical_evidence import write_jsonl
from identity_lifecycle import (
    IDENTITY_LIFECYCLE_SCHEMA_VERSION,
    artifact_paths,
    build_duplicate_candidates,
    load_current_identity_records,
    update_source_identity_lifecycle,
    vin_claim_evidence,
)


def config_fixture() -> dict:
    return {
        "schema_version": 2,
        "vehicle_key": "test_vehicle",
        "make": "Ford",
        "model": "F-350",
        "criteria": {
            "min_year": 2020,
            "max_year": 2025,
            "max_price_cad": 100000,
            "fuel": "Diesel",
            "engine": "6.7L",
        },
        "origin": {
            "home_city": "Red Deer, AB",
            "home_coords": [52.2681, -113.8112],
            "max_distance_km": 800,
        },
        "sources": {
            "autotrader": {
                "make": "ford",
                "model": "f-350",
                "search_locations": ["Red Deer, AB"],
            },
            "kijiji": {
                "make": "Ford",
                "model": "F-350",
                "search_locations": ["Calgary, AB"],
            },
        },
    }


def accepted_record(
    *,
    source: str,
    run_id: str,
    canonical_id: str,
    source_id: str,
    index: int,
    price: int = 60000,
    mileage: int = 80000,
    dealer: str = "Dealer One",
) -> dict:
    return {
        "evidence_schema_version": 1,
        "record_stage": "accepted",
        "vehicle_key": "test_vehicle",
        "source": source,
        "run_id": run_id,
        "source_record_index": index,
        "canonical_listing_id": canonical_id,
        "observation_id": f"obs-{run_id}-{index}",
        "source_listing_id": source_id,
        "source_listing_id_status": "source_identifier_claim_not_vin",
        "normalized": {
            "year": 2021,
            "make": "Ford",
            "model": "F-350",
            "trim": "Lariat",
            "price_cad": price,
            "mileage_km": mileage,
            "dealer": dealer,
            "location": "Calgary, AB",
            "listing_url": f"https://example.invalid/{source_id}",
        },
    }


class IdentityLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = config_fixture()

    def tearDown(self):
        self.temp.cleanup()

    def write_inputs(
        self,
        *,
        source: str,
        run_id: str,
        records: list[dict],
        raw_payloads: list[dict] | None = None,
    ) -> tuple[str, str]:
        accepted_path = self.root / f"accepted-{source}.jsonl"
        adapter_path = self.root / f"adapter-{source}.jsonl"
        write_jsonl(accepted_path, records)
        payloads = raw_payloads or [{} for _ in records]
        write_jsonl(
            adapter_path,
            [
                {
                    "source_record_index": record["source_record_index"],
                    "raw_payload": payload,
                }
                for record, payload in zip(records, payloads)
            ],
        )
        return str(accepted_path.relative_to(self.root)), str(
            adapter_path.relative_to(self.root)
        )

    def update(
        self,
        *,
        source: str,
        run_id: str,
        observed_at: str,
        records: list[dict],
        raw_payloads: list[dict] | None = None,
    ) -> dict:
        accepted, adapter = self.write_inputs(
            source=source,
            run_id=run_id,
            records=records,
            raw_payloads=raw_payloads,
        )
        return update_source_identity_lifecycle(
            root=self.root,
            config=self.config,
            source=source,
            run_id=run_id,
            observed_at_utc=observed_at,
            accepted_artifact=accepted,
            adapter_records_artifact=adapter,
        )

    def test_source_id_is_not_vin_and_vin_claim_is_explicit_only(self):
        record = accepted_record(
            source="autotrader",
            run_id="run-1",
            canonical_id="listing-a",
            source_id="1FT8W3BT1MED12345",
            index=0,
        )
        summary = self.update(
            source="autotrader",
            run_id="run-1",
            observed_at="2026-07-01T00:00:00+00:00",
            records=[record],
            raw_payloads=[{"vehicle": {"vin": "1FT8W3BT1MED12345"}}],
        )
        self.assertEqual(summary["identity_lifecycle_schema_version"], 1)
        current = load_current_identity_records(
            root=self.root,
            config=self.config,
            source="autotrader",
            run_id="run-1",
        )[0]
        self.assertEqual(current["source_listing_id_status"], "source_identifier_claim_not_vin")
        self.assertEqual(current["vin_claim"], "1FT8W3BT1MED12345")
        self.assertEqual(
            current["vin_evidence_status"],
            "source_reported_format_valid_unverified",
        )
        self.assertEqual(current["lifecycle_state"], "active")
        self.assertNotEqual(current["source_listing_id"], current["canonical_listing_id"])

    def test_listing_id_that_looks_like_vin_is_not_inferred_as_vin(self):
        record = accepted_record(
            source="kijiji",
            run_id="run-1",
            canonical_id="listing-k",
            source_id="1FT8W3BT1MED12345",
            index=0,
        )
        self.update(
            source="kijiji",
            run_id="run-1",
            observed_at="2026-07-01T00:00:00+00:00",
            records=[record],
            raw_payloads=[{"sku": "1FT8W3BT1MED12345"}],
        )
        current = load_current_identity_records(
            root=self.root,
            config=self.config,
            source="kijiji",
            run_id="run-1",
        )[0]
        self.assertIsNone(current["vin_claim"])
        self.assertEqual(current["vin_evidence_status"], "not_reported")

    def test_actual_elapsed_time_and_price_observation_semantics_are_idempotent(self):
        first = accepted_record(
            source="autotrader",
            run_id="run-1",
            canonical_id="listing-a",
            source_id="a",
            index=0,
            price=60000,
        )
        self.update(
            source="autotrader",
            run_id="run-1",
            observed_at="2026-07-01T00:00:00+00:00",
            records=[first],
        )
        second = accepted_record(
            source="autotrader",
            run_id="run-2",
            canonical_id="listing-a",
            source_id="a",
            index=0,
            price=57500,
        )
        self.update(
            source="autotrader",
            run_id="run-2",
            observed_at="2026-07-10T12:00:00+00:00",
            records=[second],
        )
        self.update(
            source="autotrader",
            run_id="run-2",
            observed_at="2026-07-10T12:00:00+00:00",
            records=[second],
        )
        current = load_current_identity_records(
            root=self.root,
            config=self.config,
            source="autotrader",
            run_id="run-2",
        )[0]
        self.assertEqual(current["observation_count"], 2)
        self.assertEqual(current["price_observation_count"], 2)
        self.assertEqual(current["first_observed_price_cad"], 60000)
        self.assertEqual(current["previous_observation_price_cad"], 60000)
        self.assertEqual(current["change_from_previous_observation_cad"], -2500)
        self.assertEqual(current["change_from_first_observation_cad"], -2500)
        self.assertEqual(current["elapsed_since_first_seen_seconds"], 820800)
        self.assertEqual(current["elapsed_since_first_seen_days"], 9.5)

    def test_missing_retired_and_reappeared_states_advance_only_on_successful_updates(self):
        record = accepted_record(
            source="autotrader",
            run_id="run-1",
            canonical_id="listing-a",
            source_id="a",
            index=0,
        )
        self.update(
            source="autotrader",
            run_id="run-1",
            observed_at="2026-07-01T00:00:00+00:00",
            records=[record],
        )
        for run_id, observed_at in (
            ("run-2", "2026-07-08T00:00:00+00:00"),
            ("run-3", "2026-07-15T00:00:00+00:00"),
            ("run-4", "2026-07-22T00:00:00+00:00"),
        ):
            self.update(
                source="autotrader",
                run_id=run_id,
                observed_at=observed_at,
                records=[],
            )
        state = json.loads(
            artifact_paths(self.root, self.config, "autotrader")["state"].read_text()
        )
        retired = state["listings"]["listing-a"]
        self.assertEqual(retired["lifecycle_state"], "retired")
        self.assertEqual(retired["missing_run_count"], 3)
        self.assertEqual(retired["elapsed_since_last_seen_days"], 21.0)

        reappeared_record = accepted_record(
            source="autotrader",
            run_id="run-5",
            canonical_id="listing-a",
            source_id="a",
            index=0,
            price=55000,
        )
        self.update(
            source="autotrader",
            run_id="run-5",
            observed_at="2026-07-29T00:00:00+00:00",
            records=[reappeared_record],
        )
        current = load_current_identity_records(
            root=self.root,
            config=self.config,
            source="autotrader",
            run_id="run-5",
        )[0]
        self.assertEqual(current["lifecycle_state"], "reappeared")
        self.assertEqual(current["missing_run_count"], 0)
        self.assertEqual(current["reappearance_count"], 1)

    def test_duplicate_candidates_are_explainable_and_non_destructive(self):
        auto = accepted_record(
            source="autotrader",
            run_id="run-1",
            canonical_id="auto-a",
            source_id="auto-source",
            index=0,
            price=60000,
            mileage=80000,
        )
        kijiji = accepted_record(
            source="kijiji",
            run_id="run-1",
            canonical_id="kijiji-a",
            source_id="kijiji-source",
            index=0,
            price=60500,
            mileage=80500,
        )
        self.update(
            source="autotrader",
            run_id="run-1",
            observed_at="2026-07-01T00:00:00+00:00",
            records=[auto],
            raw_payloads=[{"vin": "1FT8W3BT1MED12345"}],
        )
        self.update(
            source="kijiji",
            run_id="run-1",
            observed_at="2026-07-01T00:00:00+00:00",
            records=[kijiji],
            raw_payloads=[{"vehicleIdentificationNumber": "1FT8W3BT1MED12345"}],
        )
        identities = [
            *load_current_identity_records(
                root=self.root,
                config=self.config,
                source="autotrader",
                run_id="run-1",
            ),
            *load_current_identity_records(
                root=self.root,
                config=self.config,
                source="kijiji",
                run_id="run-1",
            ),
        ]
        result = build_duplicate_candidates(
            root=self.root,
            config=self.config,
            run_id="run-1",
            identity_records=identities,
        )
        self.assertEqual(result["candidate_count"], 1)
        candidate = result["candidates"][0]
        self.assertEqual(candidate["confidence"], "high")
        self.assertEqual(candidate["decision_status"], "candidate_only_not_merged")
        self.assertEqual(
            candidate["reasons"], ["exact_source_reported_vin_claim_match"]
        )
        self.assertNotEqual(
            candidate["left"]["canonical_listing_id"],
            candidate["right"]["canonical_listing_id"],
        )

    def test_invalid_and_conflicting_vin_claims_remain_visible(self):
        invalid = vin_claim_evidence({"vin": "not-a-vin"})
        self.assertEqual(
            invalid["vin_evidence_status"],
            "source_reported_invalid_format_unverified",
        )
        conflict = vin_claim_evidence(
            {
                "vin": "1FT8W3BT1MED12345",
                "vehicleIdentificationNumber": "2FT8W3BT1MED12345",
            }
        )
        self.assertEqual(
            conflict["vin_evidence_status"], "conflicting_source_reported_claims"
        )
        self.assertIsNone(conflict["vin_claim"])


if __name__ == "__main__":
    unittest.main()
