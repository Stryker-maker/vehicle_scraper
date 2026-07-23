# Audit 06 — Identity, Deduplication and Listing Lifecycle

## Status

Implementation is on `ai/audit-06-identity-lifecycle`. Pull-request checks and deterministic lifecycle validation remain required before owner merge.

## Purpose

Add explainable source-scoped identity, explicit VIN evidence, non-destructive duplicate candidates, correct observation semantics, and successful-run-driven listing lifecycle without importing assumptions from the disabled historical merger.

## Identity authority

A source listing identifier is not a VIN and is not cross-source physical-vehicle identity.

```text
source_listing_id
  → source-scoped source claim
  → source_identifier_claim_not_vin
```

`canonical_listing_id` remains stable only within vehicle/source identity scope. Canonical records are never merged by Audit 06.

## VIN evidence

VIN is recorded only from explicit source fields in raw adapter payloads. A listing ID that happens to contain 17 VIN-like characters is not treated as VIN.

Statuses are:

- `source_reported_format_valid_unverified`
- `source_reported_invalid_format_unverified`
- `conflicting_source_reported_claims`
- `not_reported`

A format-valid VIN remains an unverified source claim.

## Fingerprints and duplicate candidates

Audit 06 creates strict and loose deterministic fingerprints from available normalized claims such as year, make, model, trim tokens, mileage buckets, dealer, and location.

Cross-source comparisons can produce high-, medium-, or low-confidence duplicate candidates. Every candidate includes visible reasons and:

```text
decision_status: candidate_only_not_merged
```

High confidence may result from an exact format-valid source-reported VIN claim on both records. Lower confidence uses bounded, visible field similarity. No candidate deletes, suppresses, rewrites, or merges a canonical record.

## Lifecycle states

The supported operational states are:

- `active` — observed in the current successful source run
- `missing` — not observed in a successful source run
- `reappeared` — observed after missing or retired state
- `retired` — at least three consecutive successful-run misses and at least fourteen actual elapsed days since last observation

These are operational inferences, not marketplace claims that a vehicle sold or was removed for a particular reason. Failed, timed-out, stale, unreconciled, or otherwise unhealthy runs do not advance lifecycle state.

## Time and price semantics

Lifecycle state stores exact UTC timestamps and actual elapsed seconds/days.

Price observations are keyed by source run ID. Reprocessing the same run ID is idempotent. Supported output exposes:

- `observation_count`
- `price_observation_count`
- `first_observed_price_cad`
- `previous_observation_price_cad`
- `current_price_cad`
- `change_from_previous_observation_cad`
- `change_from_first_observation_cad`

Legacy week-named fields and `price_history_*.json` files are not used by supported output.

## Artifacts

Per source:

```text
data/<vehicle>/identity_lifecycle/<source>/state_latest.json
data/<vehicle>/identity_lifecycle/<source>/current_latest.jsonl
data/<vehicle>/identity_lifecycle/<source>/events_latest.jsonl
data/<vehicle>/identity_lifecycle/<source>/summary_latest.json
```

Per vehicle:

```text
data/<vehicle>/identity_lifecycle/duplicate_candidates_latest.jsonl
```

Source status schema version `8` requires identity/lifecycle schema version `1`, successful update status, and current identity count equal to accepted canonical count.

## Reporting contract

Supported manual review joins accepted canonical records one-to-one with current identity/lifecycle records. It exposes VIN status, fingerprints, lifecycle state/reason, elapsed time, corrected price observations, and duplicate-candidate references.

Duplicate candidates change review status to `duplicate_candidate_review_required`; they do not create ranking authority.

Consolidated health schema version `6` includes tracked, new, reappeared, missing, and retired listing counts.

## Rollback contract

Before source execution, current identity/lifecycle artifacts are snapshotted. If collection, freshness, schema, canonical reconciliation, pagination, accepted/output agreement, config isolation, or identity update fails, the prior identity/lifecycle artifacts are restored.

## Deterministic acceptance gate

Before merge, tests must prove:

- source listing IDs remain distinct from VIN
- VIN is explicit-only and evidence-labelled
- VIN-like listing IDs do not become VIN
- invalid and conflicting VIN claims remain visible
- same-run replay is idempotent
- actual elapsed time is correct
- price observation semantics are correct
- missing advances only on successful source runs
- retirement requires both miss count and elapsed-time thresholds
- reappearance is visible
- duplicate candidates are explainable and non-destructive
- source runners roll back identity state on unhealthy runs
- supported manual review fails closed on missing or mismatched identity artifacts
- legacy price-history files do not influence supported output
- F-150 and Tundra remain paused and receive no data changes

## Stop and revise before merge

Stop if a source listing ID is labelled as VIN, a duplicate candidate merges or removes records, a failed source run advances lifecycle, retirement lacks both threshold proofs, elapsed time is represented as artificial weeks, legacy history influences supported output, or Audit 07/09 scope is absorbed.

## Non-scope

Audit 06 does not define retention/deletion policy, repository-growth bounds, buyer ranking, F-350 enrichment, purpose-specific analytics, marketplace-wide identity truth, sold-state verification, or optional-vehicle reintroduction.

## Completion rule

Audit 06 completes only after exact-head PR validation passes, the owner reviews and merges the PR, and `ai/audit-06-identity-lifecycle` is deleted.
