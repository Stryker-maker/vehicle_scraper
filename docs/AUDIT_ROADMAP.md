# Approved Repository Audit Roadmap

## Purpose

This document preserves the owner-approved sequence for turning the repository into a continuously usable, evidence-aware vehicle-market information tool. Packages must stay within scope unless the owner approves a roadmap revision.

## Package status

| Package | Name | Status |
|---|---|---|
| 00 | Scope Freeze and Runtime Reduction | Complete and merged |
| 01 | Repository Baseline and Project Truth | Complete and merged |
| 02 | Vehicle Registry and Configuration Governance | Complete and merged |
| 03 | Canonical Listing Schema and Evidence Model | Complete and merged |
| 04 | AutoTrader Collector Audit and Refactor | Complete and merged |
| 05 | Kijiji Collector Replacement | Implemented; narrow validation and owner merge pending |
| 06 | Identity, Deduplication and Listing Lifecycle | Approved, not started |
| 07 | Storage, Retention and Repository Hygiene | Approved, not started |
| 08 | CI and Workflow Hardening | Approved, not started |
| 09 | F-350 Buyer Intelligence | Approved, not started |
| 10 | Secondary Purpose Outputs | Approved, not started |
| 11 | Optional Search Reintroduction | Approved final stage |

## Global completion criteria

The audit is not complete until optional vehicles remain paused unless explicitly approved; one registry controls enabled vehicles and sources; approved configs are validated and source-specific; runtime source rewriting is removed; raw/accepted/rejected/parse-failure counts reconcile from both source adapters; parsing failures and exclusions are visible; Kijiji geography is listing-specific source evidence or unknown; AutoTrader pagination is tested; distance methods are truthful; provenance is available; listing IDs are not confused with VINs; lifecycle/history semantics are correct; dependencies are locked; repository growth is bounded; documentation matches code; F-350 evidence supports real investigation; and three consecutive scheduled active-profile runs complete without manual repair.

---

## Audit 00 — Scope Freeze and Runtime Reduction

**Status:** complete and merged through PR #2.

Delivered the authoritative active/paused registry, five active vehicles, two paused optional vehicles, ten expected source runs, and live proof that F-150/Tundra data remained unchanged.

Continuing rule: F-150 and Tundra remain paused until Audit 11 unless the owner approves revision.

---

## Audit 01 — Repository Baseline and Project Truth

**Status:** complete and merged through PR #3.

Delivered the current README, repository baseline, architecture/data flow, vehicle purposes, data dictionary, limitations register, legacy-component classification, complete roadmap, and documentation-contract tests.

---

## Audit 02 — Vehicle Registry and Configuration Governance

**Status:** complete and merged through PR #4.

Delivered registry schema v2, config schema v2, validated operational metadata, source-specific criteria, canonical location naming, disposable legacy projection, registry-driven source planning, config-isolation evidence, structured tests, and successful ten-source validation.

The disposable compatibility projection now remains only for historical/legacy utilities; both active source adapters read governed schema v2 directly after Audits 04–05.

---

## Audit 03 — Canonical Listing Schema and Evidence Model

**Status:** complete and merged through PR #5.

Delivered canonical evidence schema v1, stable source-scoped listing IDs, observation IDs, exact raw-value preservation, typed/null-safe normalized values, per-field evidence status, accepted/rejected/parse-failure artifacts, reason codes, source/health schema v5, count reconciliation, decision-safe manual review, and the initial Kijiji search-origin quarantine.

The Audit 03 boundary was:

```text
legacy_collector_emitted_csv_rows
  = accepted_records + rejected_records + parse_failures
```

Audits 04 and 05 move that boundary into their source adapters.

---

## Audit 04 — AutoTrader Collector Audit and Refactor

**Status:** complete and merged through PR #6.

Delivered direct schema-v2 execution, explicit requests and pagination, bounded retry evidence, response-object reconciliation, duplicate and parse-failure preservation, truthful route/geodesic/unavailable distance evidence, unranked output, adapter evidence schema v1, source status schema v6, fixtures/hostile tests, and narrow single-pair validation without generated-data commits.

For AutoTrader, `fetched_records` means `autotrader_adapter_response_listing_objects`.

```text
fetched_records = accepted_records + rejected_records + parse_failures
```

---

## Audit 05 — Kijiji Collector Replacement

**Status:** implemented on `ai/audit-05-kijiji-adapter`; pull-request checks and one narrow F-350 Kijiji smoke run are required before owner merge.

### Purpose

Replace the runtime-patched Kijiji script with a directly testable adapter that preserves every JSON-LD listing object, validates query hubs, and never represents query origin as listing geography.

### Scope

- remove runtime text replacement and `exec`
- use governed config schema v2 directly
- validate Kijiji Cars & Trucks hub labels, slugs, and location IDs
- reduce overlapping city queries to six validated regional hubs
- preserve request attempts, page outcomes, query hub, URL, and item index
- parse JSON-LD `ItemList`, `Vehicle`, `Car`, and `Product` records
- preserve duplicates as explicit rejections
- preserve malformed listing objects and parser failures with reasons
- retain actual listing-specific source geography when present
- set location/address to unknown when listing-specific evidence is absent
- keep URL region and query origin as separate provenance
- keep distance processing/filtering disabled pending trustworthy routable geography
- remove rank/score and config mutation
- write Kijiji adapter evidence schema v1
- write Kijiji source status schema v7
- reconcile adapter objects into canonical evidence schema v1
- add fixtures and hostile geography tests
- validate with one non-committing single-pair smoke run

### Required reconciliation

```text
fetched_records = accepted_records + rejected_records + parse_failures
```

For Kijiji, `fetched_records` means `kijiji_adapter_json_ld_listing_objects` returned to the configured validated hub queries. This does not prove marketplace-wide completeness.

### Acceptance gate

- no runtime patcher or `exec` path remains
- unsupported hub labels fail rather than falling back to `l0`
- request and pagination evidence is visible and bounded
- every returned listing object is accepted, rejected, or a parse failure
- duplicate and parser reasons are machine-readable
- a Toronto listing returned through an Edmonton query remains Toronto
- missing listing geography remains unknown
- query origin never populates location, address, or distance
- URL region remains separate unverified evidence
- no Kijiji rank/score or config mutation remains
- adapter and canonical counts reconcile
- one narrow F-350 Kijiji smoke run passes without a data commit
- F-150 and Tundra remain paused

### Non-scope

No VIN/dedup/lifecycle model, retention policy, F-350 enrichment, purpose-specific analysis, recommendation ranking, vehicle-criteria change, AutoTrader refactor, or optional-vehicle reintroduction.

---

## Audit 06 — Identity, Deduplication and Listing Lifecycle

**Status:** approved, not started.

Create source IDs distinct from VIN, VIN evidence status, duplicate fingerprints/confidence, non-destructive duplicate candidates, first/last seen, active/missing/reappeared/retired states, actual elapsed durations, and corrected price-history semantics.

Acceptance: identity and lifecycle evidence are explainable; historical merger assumptions cannot influence supported output.

---

## Audit 07 — Storage, Retention and Repository Hygiene

**Status:** approved, not started.

Define archive/evidence retention, compact history, bounded repository growth, deletion evidence, and generated-data diff strategy.

Acceptance: `main` remains reviewable; retention is explicit; required evidence survives; growth is measurable and bounded.

---

## Audit 08 — CI and Workflow Hardening

**Status:** approved, not started.

Lock dependencies; separate tests from collection; complete profile/vehicle/source inputs; implement cadence; add anomaly detection and diagnostics; avoid multi-hour PR collection; and improve generated-data discipline.

Audits 04–05 introduce a limited single-pair validation input only to support time-sensitive source-adapter validation. Audit 08 owns the final workflow architecture.

Acceptance: PR checks are fast/deterministic; scheduling is explicit; dependencies are reproducible; failures are actionable.

---

## Audit 09 — F-350 Buyer Intelligence

**Status:** approved, not started.

Add transparent F-350 investigation evidence: target year, engine/idle hours, cab/box/SRW/DRW/4x4, trim/options, fleet/service/accident/title/emissions/warranty, owner notes, price/mileage/year bands, five-year projection, price changes, seller questions, and manual override.

Acceptance: no opaque score; every candidate state has visible reasons and evidence.

---

## Audit 10 — Secondary Purpose Outputs

**Status:** approved, not started.

RAM/Forester: comparable count, price/mileage ranges, median ask, trend, and owner-vehicle position.

Odyssey/Carnival: friend criteria, candidate set, availability/location/history/condition evidence, and shortlist questions.

Acceptance: outputs remain purpose-specific and do not inherit F-350 assumptions or opaque ranking.

---

## Audit 11 — Optional Search Reintroduction

**Status:** approved final stage.

Sequence: F-150 alone; limited validation; parser/geography/performance/growth assessment; owner approval; then Tundra alone under the same process.

Acceptance: each optional vehicle is introduced one at a time, does not destabilize the core profile, and may remain manual/monthly rather than weekly.

## Roadmap authority

The owner may approve revisions. Without explicit revision, packages execute in order, Audit 11 remains last, and no package absorbs later scope opportunistically.
