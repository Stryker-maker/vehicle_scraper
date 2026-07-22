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

## Current controls

- `vehicle_registry.json` schema v2 controls enabled vehicles and sources.
- Approved `config_*.json` files use schema v2 and must remain unchanged.
- AutoTrader reads schema v2 directly through `autotrader_run.py`.
- Kijiji still receives a disposable compatibility projection until Audit 05.
- Source execution is bounded by a 75-minute timeout.
- Fresh output must meet the minimum source schema.
- Canonical schema v1 separates raw, normalized, accepted, rejected, and parse-failure artifacts.
- Rejections and parse failures carry machine-readable reasons.
- A healthy source requires reconciliation and at least one accepted record.
- Supported manual review is built only from accepted current-run evidence.
- Manual review contains no `rank` or `score`.
- Kijiji geography remains quarantined.
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

AutoTrader also writes:

```text
data/<vehicle>/adapter_evidence/autotrader/requests_latest.jsonl
data/<vehicle>/adapter_evidence/autotrader/records_latest.jsonl
data/<vehicle>/adapter_evidence/autotrader/reconciliation_latest.json
```

The required equation is:

```text
fetched_records = accepted_records + rejected_records + parse_failures
```

AutoTrader `fetched_records` now means `autotrader_adapter_response_listing_objects`. Kijiji remains `legacy_collector_emitted_csv_rows` until Audit 05.

## AutoTrader evidence

AutoTrader preserves:

- query location, page, offset, and request URL
- request attempts and failed pages
- duplicate source identities as explicit rejections
- parse failures before accepted CSV output
- criteria rejection reasons
- complete/incomplete pagination state
- routed, geodesic, or unavailable distance evidence

A geodesic estimate is never labelled as routed driving distance. AutoTrader source status uses schema version `6`, adapter schema version `1`, and `runtime_config_projection: direct_schema_v2`.

## What Phase 1 does not prove

Phase 1 does not prove complete national marketplace coverage, independent truth of source claims, correct Kijiji geography, VIN/cross-source vehicle identity, lifecycle state, current availability, mechanical condition, fair value, or purchase suitability.

For AutoTrader, complete pagination applies only to the configured queries and locations. For Kijiji, request/response completeness remains unproven.

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

A single-pair validation run executes one governed vehicle/source pair, validates that source status, uploads only its current status/evidence as an artifact, and makes no repository commit. Audit 04 uses:

```text
validation_mode: single_pair
vehicle_key: ford_f350
source: autotrader
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

Do not treat historical merged files, source IDs, accepted status, or Kijiji search origins as verified recommendations, VINs, or listing geography.

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

Phase 1 remains interim until both source adapters, identity/lifecycle, retention, workflow hardening, and purpose-specific outputs are completed.
