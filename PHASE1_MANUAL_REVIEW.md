# Phase 1: Evidence, Investigation, Value Monitoring and Candidate Review

**Status:** active interim operating guidance during the repository audit.

Read with the repository baseline, architecture, data dictionary, limitations register, roadmap, and Audit 03–10 authority documents.

## Core controls

- Registry/config schema v2 controls operational collection scope and criteria.
- Canonical schema v1 reconciles every returned object.
- Identity/lifecycle schema v2 updates only after healthy source execution.
- Source listing IDs are not VINs; duplicate candidates never merge records.
- General, F-350, and secondary-purpose outputs contain no purchase `rank` or `score`.
- Missing owner/friend inputs and missing listing evidence remain unknown.
- Python `3.11.13`, exact dependencies/actions, separated workflows, retention, anomalies, and publication manifests remain required.

## Current evidence paths

Common evidence:

```text
data/<vehicle>/adapter_evidence/<source>/...
data/<vehicle>/evidence/<source>/...
data/<vehicle>/identity_lifecycle/<source>/...
data/<vehicle>/manual_review/<vehicle>_manual_review_latest.csv
data/<vehicle>/run_status/<source>_latest.json
data/<vehicle>/retention/...
data/run_status/...
data/retention/latest.json
```

F-350:

```text
data/ford_f350/buyer_intelligence/...
```

Owned-value profiles:

```text
data/<ram_3500|subaru_forester>/purpose_output/value_monitor/...
```

Family-candidate profiles:

```text
data/<honda_odyssey|kia_carnival>/purpose_output/family_candidate/...
```

The canonical equation remains:

```text
fetched_records = accepted_records + rejected_records + parse_failures
```

## Identity/lifecycle interpretation

- `active`: observed in the current successful source run
- `missing`: absent from a successful source run
- `reappeared`: observed after missing/retired
- `retired`: three successful misses plus fourteen days

These are operational inferences, not sold claims. Price-change fields represent listing asking-price observations, not transaction prices.

## F-350 investigation guidance

Treat F-350 source-text claims, `km_per_engine_hour`, `idle_hour_percent`, asking-price quartiles, regression, classifications, questions, and owner overrides according to Audit 09. They are investigation context, not verified configuration/history, condition, appraisal, or recommendation.

Before advancing a truck, confirm live availability, VIN, exact configuration, engine/idle hours, records/history, prior use, modifications, cold start, diagnostic scan, and independent inspection.

## RAM 3500 value-monitor guidance

Open:

```text
data/ram_3500/purpose_output/value_monitor/market_snapshot_latest.md
data/ram_3500/purpose_output/value_monitor/comparables_latest.csv
```

Review:

- `subject_comparability` and visible reasons
- asking-price/mileage distributions and cohort basis
- current `subject_profile_missing_fields`
- real `change_from_previous_observation_cad` evidence
- multi-run direction status

The known 2013/Laramie/6.7 Cummins/4WD profile and historic “just over 400,000 km” statement are owner-reported historical context. Record the current odometer before treating output as current subject context.

`competitive_asking_context` is a Q1-to-median observed asking band. It is not a verified faster-sale range, transaction value, sale probability, or appraisal.

## Subaru Forester value-monitor guidance

Until the owner records current year, trim, fuel/engine, drivetrain, odometer, and relevant context, use Forester output only as broad configured-query market context.

`subject_profile_incomplete` is expected while those fields are absent. Do not select a listing as a close comparable by guessing the owner's vehicle details.

## Odyssey/Carnival candidate guidance

Open:

```text
data/<vehicle>/purpose_output/family_candidate/requirements_summary_latest.md
data/<vehicle>/purpose_output/family_candidate/candidate_review_latest.csv
data/<vehicle>/purpose_output/family_candidate/seller_questions_latest.jsonl
```

First resolve `questions_for_friend` for:

- budget
- year range
- maximum mileage
- seating and cargo requirements
- travel radius
- history/service requirements
- acceptable seller types
- timing, deposit, inspection, and availability constraints

While those inputs are missing, `candidate_pending_requirements` means only that the listing passed broad collection criteria. It is not a shortlist or recommendation.

After preferences are recorded:

- `candidate_outside_stated_preferences` exposes visible mismatches
- `candidate_with_evidence_gaps` requires seller/document confirmation
- `candidate_for_manual_review` still requires live-listing confirmation, history review, and independent inspection

Never apply F-350 truck assumptions to minivans.

## Seller-question interpretation

Seller questions identify missing evidence or verification needs. They do not prove a defect, obtain an answer, or verify a claim. Keep seller responses/documents separate from collected source evidence.

## Workflow behaviour

### Deterministic CI

`.github/workflows/ci.yml` validates exact dependencies, compiles all source and analysis modules, validates registry/config state, and runs hostile tests. It never collects marketplace data.

### Generated-data pull requests

`.github/workflows/generated-data.yml` validates governed paths, retention, statuses, health/anomalies, manifests, and any changed F-350 or secondary-purpose artifacts against current underlying evidence.

### Collection

A `single_pair` run executes one active vehicle/source, builds only that vehicle's applicable analysis output, uploads seven-day evidence, and never publishes generated data.

A full run builds general review and health, then F-350 and all four secondary-purpose outputs after health passes. Anomaly, retention, staging, manifest, whitespace, and remote-ref gates remain before publication.

## What Phase 1 does not prove

Phase 1 does not prove complete marketplace coverage, independently verified identity/configuration/history, sold state, availability, mechanical condition, transaction price, appraisal, future value, sale speed/probability, seller answers, personalized secondary analysis without required inputs, or raw reconstruction of deleted/compacted evidence.

## Active scope

- Ford F-350
- RAM 3500
- Subaru Forester
- Honda Odyssey
- Kia Carnival

Ford F-150 and Toyota Tundra remain paused.

Phase 1 remains interim until Audit 10 validation/merge, Audit 11 decisions, and three consecutive unattended scheduled runs are complete.
