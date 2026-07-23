# Phase 1: Canonical, Identity, Retention, Workflow and Buyer-Investigation Evidence

**Status:** active interim operating guidance during the repository audit.

Read with the repository baseline, architecture, data dictionary, limitations register, roadmap, and Audit 03–09 authority documents.

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
- Retired state and generated-data growth are bounded.
- General manual review and F-350 buyer intelligence contain no purchase `rank` or `score`.
- Kijiji query origin is provenance only; listing geography is listing-specific or unknown.
- Python `3.11.13`, exact `requirements.lock` pins, and exact GitHub Action SHAs govern workflows.
- Code CI, generated-data PR validation, and collection are separate workflows.
- F-350 buyer intelligence requires current source status, canonical, raw adapter, and identity evidence from the same run.
- Missing F-350 configuration/history/usage evidence stays unknown and becomes an investigation gap rather than an inferred fact.
- Owner overrides preserve computed classifications and source evidence.

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

F-350 buyer-investigation evidence adds:

```text
data/ford_f350/buyer_intelligence/investigation_latest.jsonl
data/ford_f350/buyer_intelligence/investigation_latest.csv
data/ford_f350/buyer_intelligence/seller_questions_latest.jsonl
data/ford_f350/buyer_intelligence/market_summary_latest.json
data/ford_f350/buyer_intelligence/market_summary_latest.md
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

## F-350 buyer-intelligence interpretation

Buyer intelligence is an investigation aid, not a verified dossier, appraisal, or automatic recommendation.

### Source-text claims

Review evidence status and matched source text for:

- trim and package claims
- cab and box claims
- SRW/DRW and drivetrain claims
- total engine and idle hours
- service-record availability
- accident/title language
- prior-use language

`source_text_reported_unverified` means the source text supported the claim; it does not mean the claim was independently confirmed. `unknown` means the repository found no supported value and did not infer one.

`trim_tiers.json` and compatibility `trim_tier` values are not purchase authority. Audit 09 extracts trim and package claims separately.

### Usage context

`km_per_engine_hour` and `idle_hour_percent` are calculated only when the required source claims exist. They provide usage context, not condition proof. Confirm instrument-cluster values and inspect for inconsistent or impossible claims.

### Asking-price context

Review:

- `price_band_basis`
- `price_band_comparable_count`
- `price_band_q1_cad`
- `price_band_median_cad`
- `price_band_q3_cad`
- `price_position`
- `price_difference_from_median_cad`

These summarize current accepted asking-price claims from configured queries. They are not sale prices or appraised value.

When available, the mileage-adjusted projection also exposes sample count, slope per 10,000 km, intercept, and `r_squared`. Treat it as descriptive sample context only. A weak or small sample must not be used as value authority.

### Owner-use scenario

`projected_mileage_5y_min_km` and `projected_mileage_5y_max_km` add 25,000–40,000 km to the current mileage claim. They use the owner's expected 5,000–8,000 km annual use and do not predict resale value.

### Classifications

Review both:

- `computed_classification` and `computed_classification_reasons`
- owner classification override, reason, and `effective_classification`

Computed labels are explainable review categories, not ranks. An owner override changes review disposition only; it does not change the source evidence, market calculations, or computed result.

### Seller questions

Use `seller_questions_latest.jsonl` as a conversation and document-request checklist. Questions identify missing evidence or visible concerns; they do not prove that a defect exists. Record answers and supporting documents through an approved owner-note workflow rather than rewriting source evidence.

## Retention interpretation

Full-run retention keeps eight timestamped source CSVs/source and four timestamped manual-review CSVs for active vehicles while preserving current `*_latest` evidence, including buyer-intelligence outputs. File deletion evidence records path, category, reason, size, SHA-256, run ID, and time. Paused F-150/Tundra data remains outside collection, retention deletion, buyer intelligence, and publication scope.

A passing retention report proves configured storage limits and deletion accounting passed; it does not verify listing truth.

## Workflow behaviour

### Deterministic CI

`.github/workflows/ci.yml` runs for non-data pull-request changes, manual CI, and collection preflight. It validates the exact dependency lock, installs the locked environment, compiles sources including `f350_buyer_intelligence.py`, validates registry/config state, and runs structured/hostile tests. It never collects marketplace data.

### Generated-data pull requests

`.github/workflows/generated-data.yml` runs when a pull request changes `data/**`. It validates governed paths, retention, changed source statuses, health/anomaly evidence, and publication-manifest membership. Data-only changes do not receive acknowledgement-only success.

### Collection

`.github/workflows/scrape.yml` runs only on the Monday 08:00 UTC schedule or manual dispatch. It cannot begin until reusable CI passes.

A `single_pair` run validates one active governed vehicle/source pair, uploads seven-day evidence, and never publishes data. When the selected vehicle is F-350, source-specific buyer intelligence is included. Other vehicles do not receive F-350 buyer output.

A full run builds health and baseline-aware anomaly evidence, fails on unhealthy source evidence, builds combined AutoTrader/Kijiji F-350 buyer intelligence, applies anomaly/retention gates, and publishes only when explicitly authorized. Scheduled runs enforce critical anomalies. Manual `report_only` preserves anomaly evidence while allowing an explicitly selected diagnostic publication policy.

Before publishing, the workflow validates staged paths, writes and verifies `publication_latest.json`, runs whitespace checks, and confirms the remote ref has not changed since collection began.

## What Phase 1 does not prove

Phase 1 does not prove complete marketplace coverage, independent truth of source or extracted configuration/history claims, verified VIN, physical-vehicle identity, sold status, verified Kijiji geography, routable Kijiji distance, current availability, mechanical condition, actual sale price, appraised/fair/future value, seller answers, repair cost, purchase suitability, or raw reconstruction of compacted/deleted evidence.

A clean anomaly report means only the configured diagnostics did not identify a critical/warning condition. A publication manifest proves staged-path accounting, not marketplace truth. A complete F-350 evidence profile means fields were present, not independently verified.

## Active scope

- Ford F-350
- RAM 3500
- Subaru Forester
- Honda Odyssey
- Kia Carnival

Ford F-150 and Toyota Tundra remain paused.

## General manual-review guidance

Confirm the live listing, actual location, price, mileage, VIN, identity, history, seller, condition, and availability. Review VIN evidence, lifecycle state/reason, elapsed time, missing/reappearance counters, duplicate-candidate evidence, quality warnings, source claims, location/distance evidence, canonical/raw references, and source completion time.

## F-350 investigation guidance

Before advancing a truck beyond investigation:

1. Open the live listing and confirm it still exists.
2. Confirm VIN from independent images/documents.
3. Confirm exact trim, packages, cab, box, SRW/DRW, drivetrain, and major modifications.
4. Obtain current total engine and idle hours from a cluster image.
5. Obtain maintenance/repair records and a current history report.
6. Clarify prior fleet, commercial, rental, oilfield, towing, plowing, worksite, and idle use.
7. Compare asking price only within the visible cohort and sample limits.
8. Arrange a true cold start, diagnostic scan, and independent pre-purchase inspection.
9. Record owner disposition, notes, tags, and any override reason without altering source evidence.

Phase 1 remains interim until Audit 09 validation/merge, purpose-specific outputs, optional-vehicle decisions, and three consecutive unattended scheduled runs are complete.
