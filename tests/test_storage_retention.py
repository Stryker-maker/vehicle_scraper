import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from canonical_evidence import write_jsonl
from identity_lifecycle import (
    IDENTITY_LIFECYCLE_SCHEMA_VERSION,
    MAX_RETAINED_PRICE_OBSERVATIONS,
    artifact_paths,
    update_source_identity_lifecycle,
)
from storage_retention import (
    MANUAL_REVIEW_ARCHIVES_TO_KEEP,
    MAX_RECENT_FILE_DELETIONS,
    SOURCE_ARCHIVES_TO_KEEP,
    apply_retention,
    validate_generated_data_paths,
    verify_retention,
)


def config_fixture(vehicle_key: str) -> dict:
    return {
        "schema_version": 2,
        "vehicle_key": vehicle_key,
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


def accepted_record(run_id: str, price: int = 60000) -> dict:
    return {
        "evidence_schema_version": 1,
        "record_stage": "accepted",
        "vehicle_key": "active_vehicle",
        "source": "autotrader",
        "run_id": run_id,
        "source_record_index": 0,
        "canonical_listing_id": "listing-a",
        "observation_id": f"obs-{run_id}",
        "source_listing_id": "source-a",
        "source_listing_id_status": "source_identifier_claim_not_vin",
        "normalized": {
            "year": 2021,
            "make": "Ford",
            "model": "F-350",
            "trim": "Lariat",
            "price_cad": price,
            "mileage_km": 80000,
            "dealer": "Dealer",
            "location": "Calgary, AB",
            "listing_url": "https://example.invalid/a",
        },
    }


class StorageRetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.active_config = config_fixture("active_vehicle")
        self.paused_config = config_fixture("paused_vehicle")
        (self.root / "config_active.json").write_text(
            json.dumps(self.active_config), encoding="utf-8"
        )
        (self.root / "config_paused.json").write_text(
            json.dumps(self.paused_config), encoding="utf-8"
        )
        registry = {
            "schema_version": 2,
            "profile": "test",
            "vehicles": [
                {
                    "vehicle_key": "active_vehicle",
                    "config_path": "config_active.json",
                    "enabled": True,
                    "purpose": "primary_purchase",
                    "priority": 1,
                    "cadence": "weekly",
                    "enabled_sources": ["autotrader", "kijiji"],
                    "analysis_profile": "f350_purchase",
                },
                {
                    "vehicle_key": "paused_vehicle",
                    "config_path": "config_paused.json",
                    "enabled": False,
                    "purpose": "optional_curiosity",
                    "priority": 2,
                    "cadence": "manual",
                    "enabled_sources": ["autotrader", "kijiji"],
                    "analysis_profile": "optional_curiosity",
                    "pause_reason": "test pause",
                },
            ],
        }
        self.registry = self.root / "vehicle_registry.json"
        self.registry.write_text(json.dumps(registry), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, path: Path, content: str = "x") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_apply_retention_bounds_archives_and_records_deletions(self):
        base = self.root / "data" / "active_vehicle"
        for source in ("autotrader", "kijiji"):
            for index in range(10):
                self._write(
                    base
                    / source
                    / f"active_vehicle_{source}_2026-01-{index + 1:02d}_00-00.csv",
                    f"{source}-{index}",
                )
        for index in range(6):
            self._write(
                base
                / "manual_review"
                / f"active_vehicle_manual_review_2026-01-{index + 1:02d}_00-00-00.csv",
                f"manual-{index}",
            )
        self._write(base / "price_history_autotrader.json", "{}")
        self._write(base / "price_history_kijiji.json", "{}")
        for index in range(3):
            self._write(base / "merged" / f"legacy-{index}.csv", "legacy")
        paused_legacy = (
            self.root / "data" / "paused_vehicle" / "price_history_autotrader.json"
        )
        self._write(paused_legacy, "{}")

        report = apply_retention(
            root=self.root,
            registry_path=self.registry,
            run_id="run-1",
            deleted_at_utc="2026-07-01T00:00:00+00:00",
        )
        self.assertEqual(report["verification_status"], "pass")
        self.assertEqual(report["deleted_file_count"], 11)
        for source in ("autotrader", "kijiji"):
            files = list((base / source).glob("*.csv"))
            self.assertEqual(len(files), SOURCE_ARCHIVES_TO_KEEP)
        self.assertEqual(
            len(list((base / "manual_review").glob("*.csv"))),
            MANUAL_REVIEW_ARCHIVES_TO_KEEP,
        )
        self.assertFalse((base / "price_history_autotrader.json").exists())
        self.assertFalse((base / "price_history_kijiji.json").exists())
        self.assertEqual(list((base / "merged").glob("*.csv")), [])
        self.assertTrue(paused_legacy.exists())

        ledger = json.loads(
            (base / "retention" / "deletion_ledger.json").read_text()
        )
        self.assertEqual(ledger["deleted_file_count_total"], 11)
        self.assertNotEqual(ledger["deletion_chain_sha256"], "0" * 64)
        self.assertTrue(all(value["sha256"] for value in ledger["recent_deletions"]))
        self.assertEqual(
            verify_retention(root=self.root, registry_path=self.registry)[
                "verification_status"
            ],
            "pass",
        )

    def test_file_deletion_ledger_is_bounded_but_cumulative(self):
        base = self.root / "data" / "active_vehicle" / "merged"
        for index in range(MAX_RECENT_FILE_DELETIONS + 5):
            self._write(base / f"legacy-{index:03d}.csv", str(index))
        apply_retention(
            root=self.root,
            registry_path=self.registry,
            run_id="run-1",
            deleted_at_utc="2026-07-01T00:00:00+00:00",
        )
        ledger = json.loads(
            (
                self.root
                / "data"
                / "active_vehicle"
                / "retention"
                / "deletion_ledger.json"
            ).read_text()
        )
        self.assertEqual(
            ledger["deleted_file_count_total"], MAX_RECENT_FILE_DELETIONS + 5
        )
        self.assertEqual(
            len(ledger["recent_deletions"]), MAX_RECENT_FILE_DELETIONS
        )

    def test_generated_data_path_gate_rejects_paused_and_ungoverned_paths(self):
        errors = validate_generated_data_paths(
            changed_paths=[
                "data/active_vehicle/latest/x.csv",
                "data/run_status/latest.json",
                "data/retention/latest.json",
                "data/paused_vehicle/latest/x.csv",
                "data/unknown/latest/x.csv",
                "README.md",
            ],
            active_vehicle_keys=["active_vehicle"],
            paused_vehicle_keys=["paused_vehicle"],
        )
        self.assertEqual(
            errors,
            [
                "paused_vehicle_changed:data/paused_vehicle/latest/x.csv",
                "ungoverned_vehicle_path:data/unknown/latest/x.csv",
                "outside_data:README.md",
            ],
        )

    def _identity_update(
        self,
        *,
        run_id: str,
        observed_at: str,
        records: list[dict],
    ) -> dict:
        accepted = self.root / "accepted.jsonl"
        adapter = self.root / "adapter.jsonl"
        write_jsonl(accepted, records)
        write_jsonl(
            adapter,
            [
                {
                    "source_record_index": record["source_record_index"],
                    "raw_payload": {},
                }
                for record in records
            ],
        )
        return update_source_identity_lifecycle(
            root=self.root,
            config=self.active_config,
            source="autotrader",
            run_id=run_id,
            observed_at_utc=observed_at,
            accepted_artifact=str(accepted.relative_to(self.root)),
            adapter_records_artifact=str(adapter.relative_to(self.root)),
        )

    def test_price_observations_are_compacted_with_digest_and_totals(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for index in range(15):
            run_id = f"run-{index + 1}"
            record = accepted_record(run_id, price=60000 - index * 100)
            self._identity_update(
                run_id=run_id,
                observed_at=(start + timedelta(days=index * 7)).isoformat(),
                records=[record],
            )
        state_path = artifact_paths(
            self.root, self.active_config, "autotrader"
        )["state"]
        listing = json.loads(state_path.read_text())["listings"]["listing-a"]
        self.assertEqual(listing["price_observation_count"], 15)
        self.assertEqual(
            listing["retained_price_observation_count"],
            MAX_RETAINED_PRICE_OBSERVATIONS,
        )
        self.assertEqual(listing["compacted_price_observation_count"], 2)
        self.assertEqual(
            len(listing["price_observations"]),
            MAX_RETAINED_PRICE_OBSERVATIONS,
        )
        self.assertNotEqual(
            listing["price_observation_compaction_digest_sha256"], "0" * 64
        )
        self.assertEqual(listing["first_observed_price_cad"], 60000)
        self.assertEqual(listing["current_price_cad"], 58600)
        self.assertEqual(listing["previous_observation_price_cad"], 58700)

        digest = listing["price_observation_compaction_digest_sha256"]
        self._identity_update(
            run_id="run-15",
            observed_at=(start + timedelta(days=14 * 7)).isoformat(),
            records=[accepted_record("run-15", price=58600)],
        )
        replay = json.loads(state_path.read_text())["listings"]["listing-a"]
        self.assertEqual(replay["price_observation_count"], 15)
        self.assertEqual(
            replay["price_observation_compaction_digest_sha256"], digest
        )

    def test_old_retired_tombstone_is_pruned_with_bounded_evidence(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self._identity_update(
            run_id="run-1",
            observed_at=start.isoformat(),
            records=[accepted_record("run-1")],
        )
        for index in range(2, 5):
            self._identity_update(
                run_id=f"run-{index}",
                observed_at=(start + timedelta(days=(index - 1) * 7)).isoformat(),
                records=[],
            )
        summary = self._identity_update(
            run_id="run-5",
            observed_at=(start + timedelta(days=400)).isoformat(),
            records=[],
        )
        state = json.loads(
            artifact_paths(self.root, self.active_config, "autotrader")[
                "state"
            ].read_text()
        )
        self.assertNotIn("listing-a", state["listings"])
        self.assertEqual(summary["retired_listings_pruned_this_run"], 1)
        ledger = state["state_retention_ledger"]
        self.assertEqual(ledger["deleted_retired_listing_count_total"], 1)
        self.assertEqual(len(ledger["recent_deletions"]), 1)
        self.assertTrue(ledger["recent_deletions"][0]["listing_sha256"])

    def test_schema_v1_state_migrates_without_losing_first_price(self):
        paths = artifact_paths(self.root, self.active_config, "autotrader")
        paths["state"].parent.mkdir(parents=True, exist_ok=True)
        paths["state"].write_text(
            json.dumps(
                {
                    "identity_lifecycle_schema_version": 1,
                    "vehicle_key": "active_vehicle",
                    "source": "autotrader",
                    "last_successful_run_id": "run-1",
                    "last_successful_run_at_utc": "2026-01-01T00:00:00+00:00",
                    "successful_source_run_count": 1,
                    "listings": {
                        "listing-a": {
                            "canonical_listing_id": "listing-a",
                            "source": "autotrader",
                            "source_listing_id": "source-a",
                            "lifecycle_state": "active",
                            "first_seen_at_utc": "2026-01-01T00:00:00+00:00",
                            "last_seen_at_utc": "2026-01-01T00:00:00+00:00",
                            "last_evaluated_at_utc": "2026-01-01T00:00:00+00:00",
                            "observation_count": 1,
                            "price_observation_count": 1,
                            "first_observed_price_cad": 60000,
                            "price_observations": [
                                {
                                    "run_id": "run-1",
                                    "observed_at_utc": "2026-01-01T00:00:00+00:00",
                                    "price_cad": 60000,
                                }
                            ],
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        summary = self._identity_update(
            run_id="run-2",
            observed_at="2026-01-08T00:00:00+00:00",
            records=[accepted_record("run-2", price=59000)],
        )
        state = json.loads(paths["state"].read_text())
        listing = state["listings"]["listing-a"]
        self.assertEqual(
            summary["migrated_from_identity_lifecycle_schema_version"], 1
        )
        self.assertEqual(state["identity_lifecycle_schema_version"], 2)
        self.assertEqual(listing["price_observation_count"], 2)
        self.assertEqual(listing["first_observed_price_cad"], 60000)


if __name__ == "__main__":
    unittest.main()
