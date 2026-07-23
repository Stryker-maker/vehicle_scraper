# Audit 10 — Secondary Purpose Outputs

## Status

Implemented on `ai/audit-10-purpose-outputs`; exact-head deterministic validation, narrow live validation, owner review, and merge remain pending.

## Purpose

Create trustworthy purpose-specific outputs for the four active secondary vehicles without inheriting Ford F-350 assumptions, adding opaque ranking, treating asking prices as transaction prices, or inventing owner/family-friend requirements.

Audit 10 supports two separate analysis profiles:

- `owned_vehicle_value` — RAM 3500 and Subaru Forester
- `family_friend_purchase` — Honda Odyssey and Kia Carnival

The profiles share current evidence controls but not decision semantics.

## Governed input boundary

`purpose_inputs.json` schema version `1` records non-generated owner or family-friend inputs.

### RAM 3500

The current governed subject profile preserves historical owner-reported, unverified claims:

- model year 2013
- Laramie trim
- diesel fuel
- 6.7 Cummins diesel engine
- four-wheel drive
- just over 400,000 km when the purpose was originally recorded

The current odometer is intentionally null and labelled `owner_input_required`. Historical odometer context is not treated as current mileage.

### Subaru Forester

The subject year, trim, fuel, engine, drivetrain, current odometer, and historical odometer context remain null and labelled `owner_input_required` until the owner records them.

### Honda Odyssey and Kia Carnival

Budget, year range, mileage limit, seating, cargo requirements, travel radius, accident/title requirements, service-history requirements, seller-type preferences, and availability constraints remain null or empty and labelled `friend_input_required` until supplied.

Unknown inputs must stay unknown. The output may state that personalized context or practical shortlisting is unavailable; it must never fill a missing requirement from the operational config, another vehicle profile, or a listing claim.

## Current-run evidence boundary

Purpose output joins only matching current evidence:

```text
source status schema v8
  + accepted canonical evidence schema v1
  + preserved adapter raw payload schema v1
  + current identity/lifecycle schema v2
  + governed purpose-input schema v1
  → secondary-purpose output schema v1
```

Wrong-run, unhealthy, wrong-schema, count-mismatched, discontinuous, disconnected, or missing evidence fails closed.

## Owned-vehicle value monitoring

For RAM 3500 and Subaru Forester, Audit 10 writes:

```text
data/<vehicle>/purpose_output/value_monitor/comparables_latest.jsonl
data/<vehicle>/purpose_output/value_monitor/comparables_latest.csv
data/<vehicle>/purpose_output/value_monitor/owner_input_gaps_latest.json
data/<vehicle>/purpose_output/value_monitor/market_snapshot_latest.json
data/<vehicle>/purpose_output/value_monitor/market_snapshot_latest.md
```

Each comparable preserves source and canonical identity, listing URL, lifecycle state, year, trim/fuel/engine/drivetrain claims, asking price, mileage, distance, price-observation context, source references, and explainable subject comparability.

Subject-comparability labels are:

- `close_subject_comparable`
- `partial_subject_comparable`
- `broad_market_context`
- `subject_profile_incomplete`
- `insufficient_configuration_evidence`

They are not ranks, scores, appraisals, or physical-vehicle identity claims.

The market snapshot reports:

- source and model-year counts
- subject-comparability counts
- asking-price and mileage distributions
- cohort basis and count
- current owner-input gaps
- multi-run listing asking-price change counts when previous observations exist
- an observed lower asking band from Q1 to median

The lower observed asking band is explicitly:

```text
lower_observed_asking_band_not_verified_faster_sale_range_or_sale_probability
```

No repository evidence currently proves transaction prices, time-to-sale, sale probability, or a true faster-sale range.

Multi-run direction is based only on current listings with previous asking-price observations. Fewer than three such observations produces `insufficient_multi_run_history`. Even when available, the result means listing asking-price changes only—not market-value trend or sale evidence.

## Family-friend candidate review

For Honda Odyssey and Kia Carnival, Audit 10 writes:

```text
data/<vehicle>/purpose_output/family_candidate/candidate_review_latest.jsonl
data/<vehicle>/purpose_output/family_candidate/candidate_review_latest.csv
data/<vehicle>/purpose_output/family_candidate/seller_questions_latest.jsonl
data/<vehicle>/purpose_output/family_candidate/requirements_summary_latest.json
data/<vehicle>/purpose_output/family_candidate/requirements_summary_latest.md
```

Each candidate preserves current source/canonical/identity references and may expose unverified source-text claims for:

- seating capacity
- cargo or seat-folding features
- power sliding doors
- rear entertainment
- service-record availability
- accident/title language
- seller type
- location/distance when already supported by the source evidence model

Candidate classifications are:

- `candidate_pending_requirements`
- `candidate_outside_stated_preferences`
- `candidate_with_evidence_gaps`
- `candidate_for_manual_review`

Every classification must include visible reasons. No cross-model or within-model rank or score is allowed.

When family-friend preferences are incomplete, accepted listings remain `candidate_pending_requirements`. The summary lists the exact missing preference fields and questions for the friend. Operational config acceptance is not silently promoted into a personalized recommendation.

Seller questions remain separate from friend-preference questions. Seller questions address identity, accident/title documents, service records, seating, family-use features, availability, and independent inspection. Asking a question does not verify an answer.

## Validation boundary

`purpose_output_validation.py` schema version `1` validates:

- all five profile-specific artifacts exist
- output schema, run ID, vehicle, analysis profile, and source scope
- one-to-one canonical IDs across current accepted evidence, current identity evidence, JSONL, CSV, and family seller-question records
- non-empty raw-record and adapter-record references
- summary counts and artifact map
- exact CSV field order
- profile interpretation contracts
- no `rank` or `score` key or CSV column

A complete-looking artifact set that is disconnected from current source evidence fails.

`generated_data_validation.py` invokes the purpose-output validator whenever a `data/<vehicle>/purpose_output/**` path changes.

## Workflow integration

### Narrow validation

A secondary-vehicle `single_pair` run:

1. completes reusable deterministic CI
2. runs only the selected governed vehicle/source pair
3. validates source/canonical/lifecycle evidence
4. builds and validates only that vehicle's purpose output
5. includes `purpose_output/` in the seven-day smoke artifact
6. skips full reporting, anomalies, retention, and publication

The F-350 narrow path continues to use F-350 buyer intelligence and does not create a secondary-purpose output.

### Full run

After all source runs and the consolidated health gate pass, a full run builds and validates:

- RAM 3500 value monitoring
- Subaru Forester value monitoring
- Honda Odyssey candidate review
- Kia Carnival candidate review

These outputs are built before anomaly enforcement, retention, staging, and publication. Full diagnostics include all four purpose-output directories.

## Acceptance gate

Audit 10 is acceptable only when deterministic and required narrow live validation prove:

- current evidence joins fail closed
- the RAM historical profile remains labelled unverified and current odometer remains required
- incomplete Forester inputs prevent personalized subject context
- incomplete friend preferences prevent personalized shortlisting
- comparability and candidate labels have visible reasons
- asking-price distributions are not represented as appraisals or transaction prices
- lower asking bands are not represented as verified faster-sale ranges
- multi-run direction uses actual previous observations and exposes insufficient history
- family seller questions are non-empty and trace to evidence gaps or manual verification needs
- output contains no rank or score
- F-350 behavior and optional vehicle state remain unchanged

## Stop conditions

Stop and revise before merge if:

- a missing owner or friend input is inferred
- RAM historical mileage is treated as current odometer
- a lower asking band is called a verified faster-sale range
- asking prices are treated as transaction values or appraisal authority
- a candidate is ranked or recommended by an opaque score
- Odyssey or Carnival receives truck-specific engine-hour, idle-hour, cab, box, SRW/DRW, towing, or diesel-modification assumptions
- Forester receives RAM-specific subject assumptions
- a purpose artifact can diverge from current canonical/raw/identity evidence
- a secondary narrow run builds another vehicle's output
- a pull request can execute marketplace collection
- source queries, parsers, criteria, identity/lifecycle thresholds, retention limits, or optional-vehicle state change

## Non-scope

Audit 10 does not change source requests, parsing, filtering, pagination, locations, distance, vehicle criteria, registry enablement, canonical equations, identity/lifecycle thresholds, retention limits, F-350 buyer logic, independent appraisal, transaction-price collection, time-to-sale modelling, repair-cost prediction, sold-state verification, external history-report purchase, or F-150/Tundra reintroduction.
