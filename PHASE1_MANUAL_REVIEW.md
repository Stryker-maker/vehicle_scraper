# Phase 1: Canonical, Identity, Retention and Manual Review Evidence

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
- `AUDIT_06_IDENTITY_LIFECYCLE.md`
- `AUDIT_07_STORAGE_RETENTION.md`

## Current controls

- Registry/config schema v2 controls operational scope and criteria.
- Both sources run through direct adapters with bounded execution.
- Canonical evidence schema v1 preserves raw, normalized, accepted, rejected, and parse-failure stages.
- Identity/lifecycle schema v2 updates only after a successful reconciled source run.
- Source status schema v8 requires identity current count to equal accepted count.
- A failed or unhealthy source run cannot advance lifecycle state.
- Source listing IDs remain `source_identifier_claim_not_vin`.
- VIN is explicit source evidence only and remains unverified.
- Duplicate matches are candidates only; canonical records are never merged.
- Price history retains total/first/previous/current/minimum/maximum values, the newest thirteen raw observations, and digest-backed compaction evidence.
- Retired state is limited to 500 listings/source and 365 days since last successful observation.
- Storage-retention schema v1 bounds timestamped archives and managed active data.
- Manual review contains no `rank` or `score`.
- Historical `price_history_*.json` and merged CSV files are not used by supported output and are removed for active vehicles by governed retention.
- Kijiji query origin is provenance only; listing geography is listing-specific or unknown.

## Evidence files

For every enabled source pair:

```text
data/<vehicle>/adapter_evidence/<source>/requests_latest.jsonl
data/<vehicle>/adapter_evidence/<source>/records_latest.jsonl
data/<vehicle>/adapter_evidence/<source>/reconciliation_latest.json
data/<vehicle>/evidence/<source>/raw_latest.jsonl
data/<vehicle>/evidence/<source>/normalized_latest.jsonl
data/<vehicle>/evidence/<source>/accepted_latest.jsonl
data/<vehicle>/evidence/<source>/rejected_latest.jsonl
data/<vehicle>/evidence/<source>/parse_failures_latest.jsonl
data/<vehicle>/evidence/<source>/reconciliation_latest.json
data/<vehicle>/identity_lifecycle/<source>/state_latest.json
data/<vehicle>/identity_lifecycle/<source>/current_latest.jsonl
data/<vehicle>/identity_lifecycle/<source>/events_latest.jsonl
data/<vehicle>/identity_lifecycle/<source>/summary_latest.json
```

Per vehicle:

```text
data/<vehicle>/identity_lifecycle/duplicate_candidates_latest.jsonl
data/<vehicle>/manual_review/<vehicle>_manual_review_latest.csv
data/<vehicle>/retention/latest.json
data/<vehicle>/retention/deletion_ledger.json
```

Global:

```text
data/run_status/latest.json
data/run_status/latest.md
data/retention/latest.json
```

The canonical equation remains:

```text
fetched_records = accepted_records + rejected_records + parse_failures
```

AutoTrader scope is `autotrader_adapter_response_listing_objects`. Kijiji scope is `kijiji_adapter_json_ld_listing_objects`.

## Identity and lifecycle interpretation

- `active` means observed in the current successful source run.
- `missing` means not observed in a successful source run.
- `reappeared` means observed after missing or retired state.
- `retired` requires three consecutive successful-run misses and fourteen elapsed days.
- These states are operational inferences, not sold/removed claims.
- `first_seen_at_utc`, `last_seen_at_utc`, and elapsed days are actual time values.
- `observation_count` and `price_observation_count` count unique source-run observations, not weeks.
- Compacted observations remain included in total counts and price summaries but are no longer raw-reconstructable.
- `duplicate_candidate_review_required` means human comparison is required; it does not authorize merging.

## Retention interpretation

For active vehicles, full-run retention keeps eight timestamped source CSVs/source and four timestamped manual-review CSVs. Current `*_latest` evidence is preserved.

When a managed file is deleted, retention records path, category, reason, size, SHA-256, run ID, and time. Detailed ledgers retain the latest 100 records while cumulative counts, bytes, and chained digest survive.

A passing retention report means configured bounds and governed deletion accounting passed. It does not independently verify listing truth or reconstruct deleted evidence.

Ford F-150 and Toyota Tundra data is outside the Audit 07 deletion boundary.

## What Phase 1 does not prove

Phase 1 does not prove complete marketplace coverage, independent truth of source claims, verified VIN, physical-vehicle identity, sold status, verified Kijiji geography, routable Kijiji distance, current availability, mechanical condition, fair value, purchase suitability, or raw reconstruction of compacted/deleted evidence.

A format-valid VIN remains `source_reported_format_valid_unverified`. A high-confidence duplicate remains `candidate_only_not_merged`. A row labelled `clean` has only passed limited warning rules.

## Active scope

- Ford F-350
- RAM 3500
- Subaru Forester
- Honda Odyssey
- Kia Carnival

Ford F-150 and Toyota Tundra remain paused and must not receive current data or retention deletion updates.

## Workflow behaviour

A full run executes the registry plan, updates source/canonical/identity evidence, builds manual review and consolidated health, fails if source health is bad, applies/verifies retention, stages only `data/`, rejects paused/ungoverned/non-data paths, and commits only a governed data diff.

A `single_pair` run validates one governed vehicle/source pair, including identity/lifecycle artifacts, uploads a seven-day temporary artifact, and makes no repository commit.

Generated-data commits receive acknowledgement only and do not rerun collection.

## Manual review guidance

Confirm the live listing, actual location, price, mileage, VIN, identity, history, seller, condition, and availability. Review:

- `vin_evidence_status`
- `lifecycle_state` and `lifecycle_state_reason`
- `elapsed_since_first_seen_days`
- `missing_run_count` and `reappearance_count`
- `duplicate_candidate_count`, confidence, IDs, and reasons
- `quality_warnings`
- `source_claim_status`
- location/distance evidence status
- canonical and raw evidence references
- source completion timestamp

Phase 1 remains interim until workflow hardening, buyer intelligence, and purpose-specific outputs are complete.
