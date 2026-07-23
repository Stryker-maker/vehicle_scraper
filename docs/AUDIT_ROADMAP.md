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
| 08 | CI and Workflow Hardening | Complete and merged |
| 09 | F-350 Buyer Intelligence | Complete and merged |
| 10 | Secondary Purpose Outputs | Implemented; deterministic and narrow validation pending |
| 11 | Optional Search Reintroduction | Approved final stage |

## Global completion criteria

The audit is not complete until optional vehicles remain paused unless approved; registry/config authority is preserved; both adapters reconcile returned objects; parsing and exclusions are visible; Kijiji geography is listing-specific or unknown; source listing IDs remain distinct from VIN; identity/lifecycle semantics are explainable; generated-data and state growth are bounded; dependencies and workflows are reproducible; documentation matches code; F-350 evidence supports investigation; secondary purposes have profile-specific outputs; and three consecutive scheduled active-profile runs complete without manual repair.

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

**Status:** complete and merged through PR #10.

Delivered exact dependency/action pins, reusable code CI, generated-data validation, schedule/manual-only collection, explicit inputs, baseline-aware anomalies, publication manifests, and pre-push health/anomaly/retention/path/manifest/whitespace/ref gates.

---

## Audit 09 — F-350 Buyer Intelligence

**Status:** complete and merged through PR #11.

Delivered current-run canonical/raw/identity joins, unverified F-350 configuration/history/use claims, explicit missing evidence, guarded engine-hour context, asking-price bands and regression context, five-year mileage scenarios, explainable non-ranked classifications, seller questions, owner notes/overrides, rich buyer artifacts, generated-data validation integration, and narrow live validation.

Asking-price math remains non-appraisal context. Owner overrides preserve computed and source evidence.

---

## Audit 10 — Secondary Purpose Outputs

**Status:** implemented on `ai/audit-10-purpose-outputs`; exact-head deterministic validation, narrow live validation, owner review, and merge remain pending.

### Scope

- governed non-generated `purpose_inputs.json` schema v1
- RAM 3500 and Subaru Forester `owned_vehicle_value` outputs
- Honda Odyssey and Kia Carnival `family_friend_purchase` outputs
- current source-status/canonical/raw/identity joins
- observed asking-price and mileage distributions
- explainable subject comparability
- actual previous-observation price-change context
- explicit owner input gaps
- explicit family-friend requirement gaps
- practical candidate classifications with visible reasons
- seller questions for identity, history, service, seating, family-use features, availability, and inspection
- profile-specific JSONL, CSV, JSON, and Markdown artifacts
- fail-closed artifact validation and generated-data integration
- narrow and full workflow integration

### Acceptance

RAM historical claims must remain unverified and historical mileage must not become current odometer; incomplete Forester inputs must prevent personalized subject context; incomplete family-friend preferences must prevent personalized shortlisting; observed lower asking bands must not be represented as verified faster-sale ranges; multi-run direction must use actual previous observations; candidates and comparables must have visible reasons; artifacts must match current source evidence; outputs must contain no rank or score; and F-350/optional-vehicle behavior must remain unchanged.

### Non-scope

No source-query/parser, vehicle-criteria, registry enablement, canonical-equation, identity/lifecycle-threshold, retention-limit, F-350 buyer logic, independent appraisal, transaction-price collection, time-to-sale model, repair-cost prediction, sold-state, external history-report purchase, or F-150/Tundra change.

---

## Audit 11 — Optional Search Reintroduction

**Status:** approved final stage.

Reintroduce F-150 first under limited validation and owner approval, then Tundra separately. Either may remain manual/monthly.

## Roadmap authority

The owner may approve revisions. Without explicit revision, packages execute in order, Audit 11 remains last, and no package absorbs later scope opportunistically.
