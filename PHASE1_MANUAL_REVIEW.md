# Phase 1: Canonical, Identity, Retention, Workflow and Manual Review Evidence

**Status:** active interim operating guidance during the repository audit.

Read with the repository baseline, architecture, data dictionary, limitations register, roadmap, and Audit 03–08 authority documents.

## Current controls

- Registry/config schema v2 controls operational scope and criteria.
- Both sources run through direct adapters with bounded execution.
- Canonical evidence schema v1 preserves raw, normalized, accepted, rejected, and parse-failure stages.
- Identity/lifecycle schema v2 updates only after a successful reconciled source run.
- Source status schema v8 requires identity current count to equal accepted count.
- Failed or unhealthy source runs cannot advance lifecycle state.
- Source listing IDs remain `source_identifier_claim_not_vin`; VIN is explicit unverified source evidence only.
- Duplicate matches are candidates only; canonical records are never merged.
- Price history keeps truthful aggregate values, the newest thirteen raw observations, and digest-backed compaction evidence.
- Retired state and generated-data growth are bounded by Audit 07 controls.
- Manual review contains no `rank` or `score`.
- Kijiji query origin is provenance only; listing geography is listing-specific or unknown.
- Python `3.11.13`, exact `requirements.lock` pins, and exact GitHub Action SHAs govern workflows.
- Code CI, generated-data PR validation, and collection are separate workflows.

## Current evidence files

Source, canonical, identity, review, retention, health, anomaly, and publication evidence includes:

```text
data/<vehicle>/adapter_evidence/<source>/...
data/<vehicle>/evidence/<source>/...
data/<vehicle>/identity_lifecycle/<source>/...
data/<vehicle>/identity_lifecycle/duplicate_candidates_latest.jsonl
data/<vehicle>/manual_review/<vehicle>_manual_review_latest.csv
data/<vehicle>/retention/latest.json
data/<vehicle>/retention/deletion_ledger.json
data/<vehicle>/run_status/<source>_latest.json
data/retention/latest.json
data/run_status/latest.json
data/run_status/latest.md
data/run_status/anomalies_latest.json
data/run_status/anomalies_latest.md
data/run_status/publication_latest.json
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
- `retired` requires three successful-run misses and fourteen elapsed days.
- These are operational inferences, not sold/removed claims.
- Observation counts include compacted evidence; compacted raw observations are not reconstructable.
- `duplicate_candidate_review_required` means human comparison, not merge authority.

## Retention interpretation

Full-run retention keeps eight timestamped source CSVs/source and four timestamped manual-review CSVs for active vehicles while preserving current `*_latest` evidence. File deletion evidence records path, category, reason, size, SHA-256, run ID, and time. Paused F-150/Tundra data remains outside collection, retention deletion, and publication scope.

A passing retention report proves configured storage limits and deletion accounting passed; it does not verify listing truth.

## Workflow behaviour

### Deterministic CI

`.github/workflows/ci.yml` runs for non-data pull-request changes, manual CI, and collection preflight. It validates the exact dependency lock, installs the locked environment, compiles sources, validates registry/config state, and runs structured/hostile tests. It never collects marketplace data.

### Generated-data pull requests

`.github/workflows/generated-data.yml` runs when a pull request changes `data/**`. It validates governed paths, retention, changed source statuses, health/anomaly evidence, and publication-manifest membership. Data-only changes do not receive acknowledgement-only success.

### Collection

`.github/workflows/scrape.yml` runs only on the Monday 08:00 UTC schedule or manual dispatch. It cannot begin until reusable CI passes.

A `single_pair` run validates one active governed vehicle/source pair, uploads seven-day evidence, and never publishes data.

A full run builds health and baseline-aware anomaly evidence, applies the health/anomaly/retention gates, and publishes only when explicitly authorized. Scheduled runs enforce critical anomalies. Manual `report_only` preserves anomaly evidence while allowing an explicitly selected diagnostic publication policy.

Before publishing, the workflow validates staged paths, writes and verifies `publication_latest.json`, runs whitespace checks, and confirms the remote ref has not changed since collection began.

## What Phase 1 does not prove

Phase 1 does not prove complete marketplace coverage, independent truth of source claims, verified VIN, physical-vehicle identity, sold status, verified Kijiji geography, routable Kijiji distance, current availability, mechanical condition, fair value, purchase suitability, or raw reconstruction of compacted/deleted evidence.

A clean anomaly report means only the configured diagnostics did not identify a critical/warning condition. A publication manifest proves staged-path accounting, not marketplace truth.

## Active scope

- Ford F-350
- RAM 3500
- Subaru Forester
- Honda Odyssey
- Kia Carnival

Ford F-150 and Toyota Tundra remain paused.

## Manual review guidance

Confirm the live listing, actual location, price, mileage, VIN, identity, history, seller, condition, and availability. Review VIN evidence, lifecycle state/reason, elapsed time, missing/reappearance counters, duplicate-candidate evidence, quality warnings, source claims, location/distance evidence, canonical/raw references, and source completion time.

Phase 1 remains interim until buyer intelligence, purpose-specific outputs, optional-vehicle decisions, and three consecutive unattended scheduled runs are complete.
