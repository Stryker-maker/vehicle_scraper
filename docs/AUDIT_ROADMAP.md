# Approved Repository Audit Roadmap

## Purpose

This document preserves the owner-approved sequence for turning the repository into a continuously usable, evidence-aware vehicle-market information tool. Packages stay within scope unless the owner approves revision.

## Package status

| Package | Name | Status |
|---|---|---|
| 00 | Scope Freeze and Runtime Reduction | Complete and merged |
| 01 | Repository Baseline and Project Truth | Complete and merged |
| 02 | Vehicle Registry and Configuration Governance | Complete and merged |
| 03 | Canonical Listing Schema and Evidence Model | Complete and merged |
| 04 | AutoTrader Collector Audit and Refactor | Complete and merged |
| 05 | Kijiji Collector Replacement | Complete and merged |
| 06 | Identity, Deduplication and Listing Lifecycle | Complete and merged |
| 07 | Storage, Retention and Repository Hygiene | Implemented; deterministic validation and owner merge pending |
| 08 | CI and Workflow Hardening | Approved, not started |
| 09 | F-350 Buyer Intelligence | Approved, not started |
| 10 | Secondary Purpose Outputs | Approved, not started |
| 11 | Optional Search Reintroduction | Approved final stage |

## Global completion criteria

The audit is not complete until optional vehicles remain paused unless approved; registry/config authority is preserved; both adapters reconcile returned objects; parsing and exclusions are visible; Kijiji geography is listing-specific or unknown; source listing IDs remain distinct from VIN; identity/lifecycle semantics are explainable; generated-data and state growth are bounded; dependencies and workflows are reproducible; documentation matches code; F-350 evidence supports investigation; and three consecutive scheduled active-profile runs complete without manual repair.

---

## Audit 00 — Scope Freeze and Runtime Reduction

**Status:** complete and merged through PR #2.

Delivered five active vehicles, two paused optional vehicles, ten expected source runs, and proof that F-150/Tundra remained unchanged.

---

## Audit 01 — Repository Baseline and Project Truth

**Status:** complete and merged through PR #3.

Delivered current repository authorities, limitations, legacy classification, roadmap, and documentation tests.

---

## Audit 02 — Vehicle Registry and Configuration Governance

**Status:** complete and merged through PR #4.

Delivered registry/config schema v2, registry-driven source planning, source-specific settings, config isolation, and structured tests.

---

## Audit 03 — Canonical Listing Schema and Evidence Model

**Status:** complete and merged through PR #5.

Delivered canonical evidence schema v1, source-scoped canonical IDs, raw/normalized/accepted/rejected/parse-failure artifacts, reason codes, reconciliation, and decision-safe manual review.

```text
fetched_records = accepted_records + rejected_records + parse_failures
```

---

## Audit 04 — AutoTrader Collector Audit and Refactor

**Status:** complete and merged through PR #6.

Delivered direct schema-v2 AutoTrader execution, explicit requests/pagination, response-object reconciliation, truthful route/geodesic distance evidence, no ranking, and narrow validation.

AutoTrader fetched scope is `autotrader_adapter_response_listing_objects`.

---

## Audit 05 — Kijiji Collector Replacement

**Status:** complete and merged through PR #7.

Delivered direct schema-v2 Kijiji JSON-LD collection, validated hubs, request/page provenance, listing-specific-or-unknown geography, no query-origin substitution, no ranking, and adapter/canonical reconciliation.

Kijiji fetched scope is `kijiji_adapter_json_ld_listing_objects`.

---

## Audit 06 — Identity, Deduplication and Listing Lifecycle

**Status:** complete and merged through PR #8.

Delivered source-ID/VIN separation, explicit VIN evidence, deterministic fingerprints, non-destructive duplicate candidates, active/missing/reappeared/retired lifecycle states, successful-run-only advancement, actual elapsed time, corrected price observations, fail-closed reporting, source status schema v8, and consolidated health schema v6.

Duplicate candidates remain `candidate_only_not_merged`. Retired state is an operational inference, not a sold claim.

---

## Audit 07 — Storage, Retention and Repository Hygiene

**Status:** implemented on `ai/audit-07-storage-retention`; deterministic exact-head validation and owner merge remain pending.

### Scope

- retain eight timestamped source CSVs per active vehicle/source
- retain four timestamped manual-review CSVs per active vehicle
- preserve all current `*_latest` evidence in place
- compact listing price history to the newest thirteen raw observations plus cumulative totals, extrema, first/current values, and a chained SHA-256 digest
- retain at most 500 retired listings per source and no retired tombstone older than 365 days
- preserve bounded, cumulative SHA-256 deletion ledgers
- remove active-vehicle legacy `price_history_*.json` and historical merged CSVs through governed deletion evidence
- cap individual managed files at 50 MiB and active managed data at 500 MiB
- require source health, retention verification, and staged-path validation before generated-data commits
- leave paused F-150/Tundra data untouched

### Acceptance

Repository growth must be measurable and bounded; current evidence and lifecycle continuity must survive; deletion evidence must identify path, reason, size, and SHA-256; compacted history must retain truthful aggregate semantics; and staged generated-data diffs must reject paused, ungoverned, or non-data paths.

### Non-scope

No dependency locking, final workflow decomposition, cadence redesign, anomaly diagnostics, source-query/parser changes, buyer ranking, F-350 enrichment, purpose-specific analytics, sold-state verification, or optional-vehicle reintroduction.

---

## Audit 08 — CI and Workflow Hardening

**Status:** approved, not started.

Lock dependencies; separate tests from collection; complete inputs/cadence; add anomaly diagnostics; and finalize generated-data discipline. Earlier single-pair and Audit 07 pre-commit controls remain interim inputs to this package.

---

## Audit 09 — F-350 Buyer Intelligence

**Status:** approved, not started.

Add transparent F-350 configuration/history/condition investigation, price bands, projections, seller questions, and manual override without opaque ranking.

---

## Audit 10 — Secondary Purpose Outputs

**Status:** approved, not started.

Create purpose-specific RAM/Forester market monitoring and Odyssey/Carnival candidate outputs without inheriting F-350 assumptions.

---

## Audit 11 — Optional Search Reintroduction

**Status:** approved final stage.

Reintroduce F-150 first under limited validation and owner approval, then Tundra separately. Either may remain manual/monthly.

## Roadmap authority

The owner may approve revisions. Without explicit revision, packages execute in order, Audit 11 remains last, and no package absorbs later scope opportunistically.
