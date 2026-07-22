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
| 04 | AutoTrader Collector Audit and Refactor | Implemented; narrow validation and owner merge pending |
| 05 | Kijiji Collector Replacement | Approved, not started |
| 06 | Identity, Deduplication and Listing Lifecycle | Approved, not started |
| 07 | Storage, Retention and Repository Hygiene | Approved, not started |
| 08 | CI and Workflow Hardening | Approved, not started |
| 09 | F-350 Buyer Intelligence | Approved, not started |
| 10 | Secondary Purpose Outputs | Approved, not started |
| 11 | Optional Search Reintroduction | Approved final stage |

## Global completion criteria

The audit is not complete until optional vehicles remain paused unless explicitly approved; one registry controls enabled vehicles and sources; approved configs are validated and source-specific; runtime source rewriting is removed; raw/accepted/rejected/parse-failure counts reconcile from both source adapters; parsing failures and exclusions are visible; Kijiji geography is verified or unknown; AutoTrader pagination is tested; distance methods are truthful; provenance is available; listing IDs are not confused with VINs; lifecycle/history semantics are correct; dependencies are locked; repository growth is bounded; documentation matches code; F-350 evidence supports real investigation; and three consecutive scheduled active-profile runs complete without manual repair.

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

Continuing boundary: Kijiji retains its compatibility projection and interim source patching until Audit 05. AutoTrader no longer uses that path after Audit 04.

---

## Audit 03 — Canonical Listing Schema and Evidence Model

**Status:** complete and merged through PR #5.

Delivered canonical evidence schema v1, stable source-scoped listing IDs, observation IDs, exact raw-value preservation, typed/null-safe normalized values, per-field evidence status, accepted/rejected/parse-failure artifacts, reason codes, source/health schema v5, count reconciliation, decision-safe manual review, and Kijiji geography quarantine.

The Audit 03 boundary was:

```text
legacy_collector_emitted_csv_rows
  = accepted_records + rejected_records + parse_failures
```

Audits 04 and 05 move that boundary into their source adapters.

---

## Audit 04 — AutoTrader Collector Audit and Refactor

**Status:** implemented on `ai/audit-04-autotrader-adapter`; pull-request checks and one narrow F-350 AutoTrader smoke run are required before owner merge.

### Purpose

Replace the legacy AutoTrader script with a directly testable source adapter and preserve every response listing object through request, parse, rejection, acceptance, and canonical evidence stages.

### Scope

- governed config schema v2 used directly
- explicit AutoTrader request contract
- pagination by page size and offset
- retry/backoff with request-attempt evidence
- per-page request provenance
- response listing-object fetched boundary
- duplicate records preserved as explicit rejections
- parse failures preserved with machine-readable reasons
- criteria exclusions preserved with reasons
- truthful route/geodesic/unavailable distance evidence
- unranked output with no score
- AutoTrader adapter evidence schema v1
- AutoTrader source status schema v6
- adapter-to-canonical reconciliation
- fixtures and hostile tests
- narrow single-pair validation mode with artifact upload and no generated-data commit

### Required reconciliation

```text
fetched_records = accepted_records + rejected_records + parse_failures
```

For AutoTrader, `fetched_records` means `autotrader_adapter_response_listing_objects`.

### Acceptance gate

- request and two-page fixture tests pass
- retries and pagination are visible and bounded
- no response listing object disappears
- every rejection and parse failure has reasons
- distance method is explicit and truthful
- no internal rank/score or config mutation remains
- adapter and canonical counts reconcile
- one narrow F-350 AutoTrader smoke run passes without a data commit
- F-150/Tundra and Kijiji implementation remain untouched

### Non-scope

No Kijiji replacement, VIN/dedup/lifecycle model, retention policy, F-350 enrichment, purpose-specific analysis, ranking, criteria change, or optional-vehicle reintroduction.

---

## Audit 05 — Kijiji Collector Replacement

**Status:** approved, not started.

Eliminate runtime text patching/`exec`; validate location identifiers; extract actual location or unknown; keep URL region as separate evidence; reduce overlapping searches; preserve query/page provenance; add fixtures; and reconcile raw/rejected/parse-failure records from the adapter.

Acceptance: no Toronto record is represented as Alberta because of search origin; no runtime patching remains; geography is verified or explicitly unknown.

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

Audit 04 introduces a limited single-pair validation input only to support time-sensitive source-adapter validation. Audit 08 owns the final workflow architecture.

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
