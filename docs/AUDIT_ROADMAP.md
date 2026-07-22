# Approved Repository Audit Roadmap

## Purpose

This document preserves the owner-approved sequence for turning the repository into a continuously usable, evidence-aware vehicle-market information tool. Packages must stay within scope unless the owner approves a roadmap revision.

## Package status

| Package | Name | Status |
|---|---|---|
| 00 | Scope Freeze and Runtime Reduction | Complete and merged |
| 01 | Repository Baseline and Project Truth | Complete and merged |
| 02 | Vehicle Registry and Configuration Governance | Complete and merged |
| 03 | Canonical Listing Schema and Evidence Model | Implemented; validation and owner merge pending |
| 04 | AutoTrader Collector Audit and Refactor | Approved, not started |
| 05 | Kijiji Collector Replacement | Approved, not started |
| 06 | Identity, Deduplication and Listing Lifecycle | Approved, not started |
| 07 | Storage, Retention and Repository Hygiene | Approved, not started |
| 08 | CI and Workflow Hardening | Approved, not started |
| 09 | F-350 Buyer Intelligence | Approved, not started |
| 10 | Secondary Purpose Outputs | Approved, not started |
| 11 | Optional Search Reintroduction | Approved final stage |

## Global completion criteria

The audit is not complete until optional vehicles remain paused unless explicitly approved; one registry controls enabled vehicles and sources; approved configs are validated and source-specific; runtime source rewriting is removed; raw/accepted/rejected/parse-failure counts reconcile from the source adapters; parsing failures and exclusion reasons are visible; Kijiji location is verified or unknown; AutoTrader pagination is tested; distance methods are truthful; provenance is available; listing IDs are not confused with VINs; lifecycle/history semantics are correct; dependencies are locked; repository growth is bounded; documentation matches code; F-350 evidence supports real investigation; and three consecutive scheduled active-profile runs complete without manual repair.

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

Delivered registry schema v2, config schema v2, validated purpose/priority/cadence/source/profile metadata, source-specific criteria, canonical location naming, disposable legacy projection, registry-driven source planning, config-isolation evidence, structured tests, and a successful ten-source live validation.

Continuing boundary: source collectors remain legacy and retain their own parsing/ranking/geography defects for Audits 04 and 05.

---

## Audit 03 — Canonical Listing Schema and Evidence Model

**Status:** implemented on `ai/audit-03-canonical-evidence`; PR and live branch validation required before owner merge.

### Purpose

Make every record emitted by the current collectors traceable through raw, normalized, accepted, rejected, parse-failure, and manual-review stages without pretending the legacy collectors prove marketplace completeness.

### Scope

- canonical evidence schema version 1
- stable source-scoped canonical listing IDs
- run-specific observation IDs
- exact raw CSV value preservation
- typed/null-safe normalized values
- per-field provenance/evidence status
- explicit unknown handling instead of misleading sentinels
- accepted/rejected/parse-failure JSONL artifacts
- machine-readable rejection/failure reasons
- source-status and health schema version 5
- enforced count reconciliation
- decision-safe manual-review schema built only from accepted evidence
- Kijiji raw geography preservation plus normalized quarantine
- hostile tests for malformed rows, missing identifiers, unknowns, ID stability, and run mismatch

### Required reconciliation

```text
fetched_records = accepted_records + rejected_records + parse_failures
```

For Audit 03, `fetched_records` is explicitly scoped to `legacy_collector_emitted_csv_rows`. Audits 04 and 05 must move this boundary into the source adapters.

### Acceptance gate

- no collector-emitted row disappears after the canonical boundary
- raw and normalized values are distinguishable
- unknowns normalize to JSON null while raw strings remain preserved
- every rejection and parse failure has machine-readable reasons
- source listing IDs are explicitly not VINs
- supported manual review contains only accepted current-run evidence
- source health requires reconciliation and at least one accepted record
- structured tests pass
- one live ten-source branch run proves all source pairs reconcile
- F-150/Tundra remain untouched

### Non-scope

No AutoTrader pagination/refactor, Kijiji source replacement, marketplace HTTP/raw-response capture, VIN/duplicate/lifecycle model, storage policy, purpose-specific analysis, ranking, F-350 enrichment, or optional-vehicle reintroduction.

---

## Audit 04 — AutoTrader Collector Audit and Refactor

**Status:** approved, not started.

Replace the legacy AutoTrader script with a directly testable source adapter covering request contract, pagination, retry/backoff, request/fetch/parse/accept/reject counts, parse-failure preservation, fixtures, truthful distance evidence, no internal ranking, no config mutation, and reconciliation into Audit 03 stages.

Acceptance: pagination and fixtures pass; no silent per-record loss; distance method is truthful; source-adapter counts reconcile.

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

Lock dependencies; separate tests from collection; add profile/vehicle/source inputs; implement cadence; add anomaly detection and diagnostics; avoid multi-hour PR collection; and improve generated-data discipline.

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
