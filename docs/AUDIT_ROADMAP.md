# Approved Repository Audit Roadmap

## Purpose

This document preserves the owner-approved sequence for turning the repository into a continuously usable, evidence-aware vehicle-market information tool. Packages must stay within scope unless the owner approves a roadmap revision.

## Package status

| Package | Name | Status |
|---|---|---|
| Audit 00 | Scope Freeze and Runtime Reduction | Complete and merged |
| Audit 01 | Repository Baseline and Project Truth | Complete and merged |
| Audit 02 | Vehicle Registry and Configuration Governance | Implemented; validation and owner merge pending |
| Audit 03 | Canonical Listing Schema and Evidence Model | Approved, not started |
| Audit 04 | AutoTrader Collector Audit and Refactor | Approved, not started |
| Audit 05 | Kijiji Collector Replacement | Approved, not started |
| Audit 06 | Identity, Deduplication and Listing Lifecycle | Approved, not started |
| Audit 07 | Storage, Retention and Repository Hygiene | Approved, not started |
| Audit 08 | CI and Workflow Hardening | Approved, not started |
| Audit 09 | F-350 Buyer Intelligence | Approved, not started |
| Audit 10 | Secondary Purpose Outputs | Approved, not started |
| Audit 11 | Optional Search Reintroduction | Approved final stage |

## Global completion criteria

The audit is not complete until:

- optional vehicles remain paused unless explicitly approved
- one registry controls enabled vehicles and sources
- approved configs are validated and source-specific
- runtime source rewriting is removed
- raw/accepted/rejected/parse-failure counts reconcile
- parsing failures and exclusion reasons are visible
- Kijiji location is verified or explicitly unknown
- AutoTrader pagination is tested
- distance methods are truthful
- provenance is available
- listing IDs are not confused with VINs
- lifecycle/history semantics are correct
- dependencies are locked
- repository growth is bounded
- documentation matches code
- F-350 criteria/enrichment support real investigation
- three consecutive scheduled active-profile runs complete without manual repair

---

## Audit 00 — Scope Freeze and Runtime Reduction

**Status:** complete and merged through PR #2.

### Purpose

Reduce runtime and generated-data growth during the core audit.

### Delivered

- authoritative active/paused vehicle registry
- five active vehicles and two paused optional vehicles
- collection, review generation and health derived from the same registry
- ten expected source runs instead of fourteen
- live proof that F-150/Tundra data remained unchanged

### Continuing rule

F-150 and Tundra remain paused until Audit 11 unless the owner approves revision.

---

## Audit 01 — Repository Baseline and Project Truth

**Status:** complete and merged through PR #3.

### Purpose

Replace obsolete documentation and establish trustworthy project authorities.

### Delivered

- current README
- repository baseline
- architecture/data flow
- vehicle purposes
- data dictionary
- limitations register
- legacy-component classification
- complete package roadmap
- documentation-contract tests

---

## Audit 02 — Vehicle Registry and Configuration Governance

**Status:** implemented on `ai/audit-02-config-governance`; tests and live branch validation required before owner merge.

### Purpose

Replace ambiguous/scattered legacy configuration with validated operational governance and source-specific criteria.

### Scope

- registry schema v2
- validated purpose, priority, cadence, enabled sources and analysis profile
- config schema v2
- separate shared criteria, origin and source query settings
- formatted, duplicate-free search locations
- removal of `max_results`, `ranking_weights` and flat source aliases from approved configs
- temporary source-specific legacy projection for current collectors
- registry source plan used by collection, manual review and health
- byte-for-byte approved-config isolation evidence
- one-change vehicle pause/re-enable behaviour

### Acceptance gate

- one validated registry governs operational scope and source pairs
- invalid/conflicting registry or config fails before collection
- approved configs cannot be altered by collector execution
- obsolete controls exist only in disposable compatibility projection
- source-specific criteria are unambiguous
- exactly ten current active source runs remain planned
- F-150/Tundra remain untouched
- structured tests pass
- one live branch run passes with schema/projection/isolation evidence

### Non-scope

No collector parsing repair, Kijiji geography repair, AutoTrader pagination, canonical evidence stages, ranking, storage policy, F-350 enrichment or optional-vehicle reintroduction.

---

## Audit 03 — Canonical Listing Schema and Evidence Model

**Status:** approved, not started.

### Purpose

Make every record traceable through raw, normalized, accepted, rejected and manual-review stages.

### Scope

- canonical listing/observation IDs
- schema versioning
- raw value preservation
- field provenance/evidence status
- explicit null/unknown handling
- accepted/rejected artifacts
- machine-readable rejection reasons
- parse-failure evidence
- count reconciliation
- decision-safe manual-review schema

### Required reconciliation

```text
fetched records = accepted records + rejected records + parse failures
```

### Acceptance gate

No record disappears without evidence; raw and normalized values are distinguishable; every exclusion has reasons; source claims remain claims; unknowns are not replaced by misleading sentinels.

---

## Audit 04 — AutoTrader Collector Audit and Refactor

**Status:** approved, not started.

### Purpose

Replace the legacy AutoTrader script with a directly testable source adapter.

### Scope

- explicit request contract and pagination
- status/retry/backoff handling
- request/fetch/parse/accept/reject counts
- parse failures preserved
- source fixtures and parser tests
- truthful route/geodesic/unavailable distance evidence
- no internal recommendation ranking
- no config mutation

### Acceptance gate

Pagination and fixture tests pass; no silent per-record loss; distance method is truthful; output reconciles to Audit 03 stages.

---

## Audit 05 — Kijiji Collector Replacement

**Status:** approved, not started.

### Purpose

Remove runtime source rewriting and create an ordinary testable Kijiji adapter.

### Scope

- eliminate text patching and `exec`
- validate location identifiers and remove unsafe fallback ID
- extract actual location or record unknown
- keep URL region separate as evidence
- reduce overlapping searches
- query/page provenance
- fixtures and parser tests
- raw/rejected/parse-failure reconciliation

### Acceptance gate

No Toronto record is represented as Alberta because of search origin; no runtime patching remains; geography is verified or explicitly unknown.

---

## Audit 06 — Identity, Deduplication and Listing Lifecycle

**Status:** approved, not started.

### Purpose

Create transparent source identity, duplicate-candidate and lifecycle evidence.

### Scope

- source IDs distinct from VIN
- VIN plus evidence status
- duplicate fingerprints/confidence
- no destructive automatic merge
- first/last seen
- active/missing/reappeared/retired states
- actual elapsed durations
- corrected price-history semantics

### Acceptance gate

Identity evidence is explainable; lifecycle states are run-based and dated; historical merger assumptions cannot influence supported output.

---

## Audit 07 — Storage, Retention and Repository Hygiene

**Status:** approved, not started.

### Purpose

Bound data growth and separate code review from bulky generated evidence.

### Scope

- archive retention policy
- raw artifacts or dedicated data branch
- compact history
- bounded repository growth
- deletion/retention evidence
- generated-data diff strategy

### Acceptance gate

Main remains reviewable; retention is explicit; required evidence survives; growth is measurable and bounded.

---

## Audit 08 — CI and Workflow Hardening

**Status:** approved, not started.

### Purpose

Make tests, collection and operational diagnostics reproducible and maintainable.

### Scope

- dependency lock
- separate test/collection workflows
- workflow inputs by profile/vehicle/source
- scheduled active profile
- cadence handling
- row-count anomaly detection
- diagnostics artifacts
- no multi-hour collection on normal PRs
- generated-data branch/PR discipline

### Acceptance gate

PR checks are fast and deterministic; scheduled collection is explicit; dependency versions are reproducible; failures provide actionable diagnostics.

---

## Audit 09 — F-350 Buyer Intelligence

**Status:** approved, not started.

### Purpose

Create transparent purchase-investigation support for the primary F-350 goal after source evidence is trustworthy.

### Scope

- target-year status
- engine/idle hours and derived context
- cab/box/SRW/DRW/4x4 evidence
- trim/options
- fleet/commercial, service, accident/title, emissions and warranty evidence
- owner notes and investigation state
- price/mileage/year bands
- five-year mileage projection
- price-change and seller-question outputs
- manual override

### Acceptance gate

No opaque score; every candidate state has visible reasons and evidence; output supports real owner investigation.

---

## Audit 10 — Secondary Purpose Outputs

**Status:** approved, not started.

### Purpose

Create lightweight outputs appropriate to the non-primary vehicle purposes.

### Scope

RAM/Forester:

- comparable count
- price/mileage ranges
- median ask
- trend
- owner vehicle's market position

Odyssey/Carnival:

- friend criteria
- candidate set
- availability/location/history/condition evidence
- shortlist with questions

### Acceptance gate

Outputs remain purpose-specific and do not inherit F-350 assumptions or opaque ranking.

---

## Audit 11 — Optional Search Reintroduction

**Status:** approved final stage.

### Purpose

Evaluate F-150 and Tundra only after the core system is trustworthy and efficient.

### Sequence

1. F-150 alone
2. limited manual validation
3. parser/geography/performance/growth assessment
4. owner approval
5. Tundra alone under the same process

### Acceptance gate

Each optional vehicle is introduced one at a time, does not destabilize the core profile, and may remain manual/monthly rather than weekly.

## Roadmap authority

The owner may approve revisions. Without explicit revision, packages execute in order, Audit 11 remains last, and no package absorbs later scope opportunistically.
