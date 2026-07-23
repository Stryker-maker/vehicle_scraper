# Phase 1: Canonical Evidence and Manual Review

**Status:** active interim operating guidance during the repository audit.

Read with:

- `docs/REPOSITORY_BASELINE.md`
- `docs/ARCHITECTURE_AND_DATA_FLOW.md`
- `docs/DATA_DICTIONARY.md`
- `docs/LIMITATIONS_REGISTER.md`
- `docs/AUDIT_ROADMAP.md`
- `AUDIT_03_CANONICAL_EVIDENCE.md`
- `AUDIT_04_AUTOTRADER_ADAPTER.md`
- `AUDIT_05_KIJIJI_ADAPTER.md`

## Current controls

- `vehicle_registry.json` schema v2 controls enabled vehicles and sources.
- Approved `config_*.json` files use schema v2 and must remain unchanged during execution.
- AutoTrader reads schema v2 directly through `autotrader_run.py`.
- Kijiji reads schema v2 directly through `kijiji_run.py`; no text patching or `exec` remains.
- Kijiji query labels must resolve through location-registry version 1.
- Source execution is bounded by a 75-minute timeout.
- Fresh output must meet the minimum source schema.
- Canonical schema v1 separates raw, normalized, accepted, rejected, and parse-failure artifacts.
- Rejections and parse failures carry machine-readable reasons.
- A healthy source requires reconciliation, complete configured pagination, and at least one accepted record.
- Supported manual review is built only from accepted current-run evidence.
- Manual review contains no `rank` or `score`.
- Kijiji query origin is provenance only; listing geography is listing-specific source evidence or unknown.
- Kijiji distance remains disabled.
- Historical merged files remain disabled.

## Evidence files

For every enabled source pair:

```text
data/<vehicle>/evidence/<source>/raw_latest.jsonl
data/<vehicle>/evidence/<source>/normalized_latest.jsonl
data/<vehicle>/evidence/<source>/accepted_latest.jsonl
data/<vehicle>/evidence/<source>/rejected_latest.jsonl
data/<vehicle>/evidence/<source>/parse_failures_latest.jsonl
data/<vehicle>/evidence/<source>/reconciliation_latest.json
```

Both direct adapters also write:

```text
data/<vehicle>/adapter_evidence/<source>/requests_latest.jsonl
data/<vehicle>/adapter_evidence/<source>/records_latest.jsonl
data/<vehicle>/adapter_evidence/<source>/reconciliation_latest.json
```

The required equation is:

```text
fetched_records = accepted_records + rejected_records + parse_failures
```

AutoTrader `fetched_records` means `autotrader_adapter_response_listing_objects`.

Kijiji `fetched_records` means `kijiji_adapter_json_ld_listing_objects`.

## Source evidence

AutoTrader preserves query location/page/offset/request URL, attempts, failed pages, duplicates, parse failures, criteria rejections, pagination state, and routed/geodesic/unavailable distance evidence. AutoTrader status uses schema version `6`.

Kijiji preserves validated query hub/page/request URL/item index, attempts, failed pages, duplicates, parse failures, criteria rejections, pagination state, URL region evidence, and listing-specific/unknown geography counts. Kijiji status uses schema version `7`.

A geodesic estimate is never labelled as routed driving distance. A Kijiji query hub or URL region is never treated as listing location.

## What Phase 1 does not prove

Phase 1 does not prove complete marketplace coverage, independent truth of source claims, verified Kijiji geography, routable Kijiji distance, VIN/cross-source vehicle identity, lifecycle state, current availability, mechanical condition, fair value, or purchase suitability.

Complete pagination applies only to the configured queries and validated hubs. `source_reported_listing_specific_unverified` means the source supplied listing-specific geography; it does not independently verify that geography.

A source or row labelled `clean` has only passed the current limited warning rules.

## Active scope

- Ford F-350
- RAM 3500
- Subaru Forester
- Honda Odyssey
- Kia Carnival

Ford F-150 and Toyota Tundra remain paused and must not receive current data updates.

## Workflow behaviour

A full run executes the complete registry plan, builds manual review and consolidated health, and may commit generated data. Scheduled runs commit automatically; manual full runs require `commit_generated_data=true`.

A single-pair validation run executes one governed vehicle/source pair, validates that source status, uploads only its current status/evidence as an artifact, and makes no repository commit. Audit 05 uses:

```text
validation_mode: single_pair
vehicle_key: ford_f350
source: kijiji
commit_generated_data: false
```

Generated-data commits receive acknowledgement only and do not rerun collection.

## Files to use

Use:

- `data/<vehicle>/manual_review/<vehicle>_manual_review_latest.csv`
- `data/<vehicle>/evidence/<source>/reconciliation_latest.json`
- `data/<vehicle>/evidence/<source>/accepted_latest.jsonl`
- `data/<vehicle>/evidence/<source>/rejected_latest.jsonl`
- `data/<vehicle>/evidence/<source>/parse_failures_latest.jsonl`
- `data/<vehicle>/run_status/<source>_latest.json`
- `data/run_status/latest.json`
- `data/run_status/latest.md`

Do not treat historical merged files, source IDs, accepted status, Kijiji query hubs, URL regions, or unverified listing geography as recommendations, VINs, or independently verified location.

## Manual review guidance

Confirm the live listing, actual location, price, mileage, identity, history, seller, condition, and availability. Review:

- `quality_warnings`
- `review_status`
- `source_claim_status`
- `source_listing_id_status`
- `location_evidence_status`
- `distance_evidence_status`
- `year_evidence_status`
- `price_evidence_status`
- `mileage_evidence_status`
- `raw_record_ref`
- `normalized_record_ref`
- `source_completed_at_utc`

Phase 1 remains interim until identity/lifecycle, retention, workflow hardening, and purpose-specific outputs are completed.
