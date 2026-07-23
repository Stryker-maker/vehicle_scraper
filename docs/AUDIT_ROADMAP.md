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
| 07 | Storage, Retention and Repository Hygiene | Complete and merged |
| 08 | CI and Workflow Hardening | Implemented; deterministic validation and owner merge pending |
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

**Status:** complete and merged through PR #9.

Delivered eight source snapshots per active source, four manual-review snapshots per active vehicle, compacted price observations with cumulative digests, bounded retired tombstones and deletion ledgers, active-data size gates, governed legacy-file deletion, and staged-path validation while leaving paused data untouched.

---

## Audit 08 — CI and Workflow Hardening

**Status:** implemented on `ai/audit-08-ci-workflow-hardening`; exact-head deterministic validation and owner merge remain pending.

### Scope

- exact Python dependency lock and Python runtime version
- exact GitHub Action commit SHAs
- reusable code CI separated from collection
- separate generated-data pull-request validation
- schedule/manual-only collection with reusable CI preflight
- explicit full/single-pair, active-vehicle, source, publication, anomaly-policy, and operator-note inputs
- baseline-aware anomaly schema v1
- generated-data publication manifest schema v1
- health, anomaly, retention, staged-path, manifest, whitespace, and remote-ref gates before push
- short-lived failure evidence and bounded full-run diagnostics

### Acceptance

Pull requests must never execute collectors; collection must not start before reusable CI passes; moving dependency/action references must be absent; paused vehicles must fail plan/publication validation; critical anomalies must remain visible and enforceable; publication manifests must match staged governed paths; and generated-data pull requests must receive actual integrity validation rather than acknowledgement-only success.

### Non-scope

No source-query/parser, vehicle-criteria, evidence-equation, identity/lifecycle, retention-limit, buyer-ranking, F-350 enrichment, purpose-output, sold-state, or optional-vehicle change.

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
