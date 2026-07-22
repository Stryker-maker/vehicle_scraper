# Approved Repository Audit Roadmap

## Authority and purpose

This roadmap preserves the repository-owner-approved sequence for turning the current prototype into a dependable, continuously usable information-gathering tool.

The sequence is deliberate:

1. reduce unnecessary runtime
2. establish project truth
3. govern configuration and data contracts
4. repair source collection
5. add identity, lifecycle and retention
6. harden operations
7. build decision outputs only after collection evidence is trustworthy
8. reintroduce optional searches last

Scope changes require repository-owner approval. A later package may add a newly discovered limitation to the register without expanding its own implementation scope.

## Status summary

| Audit | Package | Status |
|---:|---|---|
| 00 | Scope Freeze and Runtime Reduction | Complete and merged |
| 01 | Repository Baseline and Project Truth | Current package |
| 02 | Vehicle Registry and Configuration Governance | Approved, not started |
| 03 | Canonical Listing Schema and Evidence Model | Approved, not started |
| 04 | AutoTrader Collector Audit and Refactor | Approved, not started |
| 05 | Kijiji Collector Replacement | Approved, not started |
| 06 | Identity, Deduplication and Listing Lifecycle | Approved, not started |
| 07 | Storage, Retention and Repository Hygiene | Approved, not started |
| 08 | CI and Operational Workflow Hardening | Approved, not started |
| 09 | F-350 Buyer Intelligence Foundation | Approved, not started |
| 10 | Secondary Use-Case Outputs | Approved, not started |
| 11 | Optional Search Reintroduction | Approved final stage |

---

## Audit 00 — Scope Freeze and Runtime Reduction

**Status:** complete and merged through PR #2.

### Purpose

Stop unnecessary F-150 and Tundra collection while preserving useful active data gathering during the audit.

### Delivered

- one authoritative vehicle registry
- five enabled vehicles
- F-150 and Tundra paused
- collection, manual review and health reporting derived from the same registry
- exact active/paused scope tests
- live validation of 10/10 healthy source runs
- no paused-vehicle data changes
- active-scope runtime reduced to approximately 31 minutes in the validation run

### Continuing contract

- two sources for each of five enabled vehicles
- paused data retained unchanged
- optional vehicles remain off until Audit 11 unless the owner revises scope

---

## Audit 01 — Repository Baseline and Project Truth

**Status:** current package.

### Purpose

Replace obsolete documentation and create a trustworthy map of what the repository currently does, does not do and plans to correct.

### Scope

- replace obsolete README
- document project purpose and vehicle priorities
- inventory authoritative, active, interim, legacy and historical components
- document present architecture and data flow
- create a current data dictionary
- create a tracked limitations register
- clearly mark `merge.py` and historical merged output as disabled legacy
- preserve Audit 00–11 package sequence and acceptance intent
- add documentation-contract tests

### Non-scope

- no collector refactor
- no source filter change
- no schema redesign
- no Kijiji geography repair
- no AutoTrader pagination
- no ranking or candidate model
- no storage deletion

### Acceptance gate

- README matches actual operating behaviour
- a new user can identify supported outputs and unsafe/historical files
- every current component has a documented status
- current field semantics and evidence limitations are documented
- known weaknesses are assigned IDs and future packages
- all approved packages are preserved in repository documentation
- documentation-contract and existing structured tests pass

---

## Audit 02 — Vehicle Registry and Configuration Governance

**Status:** approved, not started.

### Purpose

Replace ambiguous and scattered legacy configuration with validated, source-aware governance.

### Planned scope

- formal registry/config schema validation
- source-specific configuration structure where required
- validate purpose, priority, cadence and enabled sources
- validate search locations and naming consistency
- remove all collector authority to mutate approved config
- decide disposition of `max_results` and `ranking_weights`
- distinguish operational state from source search criteria
- preserve one-change enable/pause behaviour

### Acceptance gate

- one validated registry governs workflow scope
- invalid or conflicting config fails before collection
- collector execution cannot alter approved configuration
- obsolete compatibility fields are removed or explicitly governed
- source-specific criteria are no longer ambiguous

---

## Audit 03 — Canonical Listing Schema and Evidence Model

**Status:** approved, not started.

### Purpose

Make every record traceable through raw, normalized, accepted, rejected and manual-review stages.

### Planned scope

- canonical listing and observation identifiers
- schema versioning
- raw source-value preservation
- field provenance and evidence status
- explicit null/unknown handling
- accepted and rejected artifacts
- machine-readable rejection reasons
- parse-failure evidence
- count reconciliation
- decision-safe manual-review schema

### Required reconciliation

```text
fetched records = accepted records + rejected records + parse failures
```

### Acceptance gate

- no record disappears without evidence
- raw and normalized values are distinguishable
- every exclusion has one or more reasons
- source claims are not presented as verified truth
- unknown values are not replaced by misleading sentinels

---

## Audit 04 — AutoTrader Collector Audit and Refactor

**Status:** approved, not started.

### Purpose

Make AutoTrader collection directly testable, paginated, measurable and honest about parsing and distance evidence.

### Planned scope

- separate source adapter from CLI orchestration
- remove module-level mutable execution where practical
- implement and test pagination
- validate HTTP status behaviour
- bounded retry/backoff
- preserve request, fetched, parsed and failed counts
- make individual parse failures visible
- replace broad silent record skipping
- distinguish route distance from geodesic fallback
- verify seller and accident-claim parsing semantics
- add stored source fixtures and parser-contract tests

### Acceptance gate

- more-than-one-page fixture proves pagination
- malformed records produce explicit evidence
- source counts reconcile under the canonical schema
- every distance records its actual method
- F-350 output is reproducible from fixtures

---

## Audit 05 — Kijiji Collector Replacement

**Status:** approved, not started.

### Purpose

Remove runtime source rewriting and create a directly testable Kijiji adapter with verified or explicitly unknown geography.

### Planned scope

- replace `phase1_kijiji_runner.py` patch/exec path
- validate Kijiji query location IDs and URLs
- remove unvalidated location-ID fallback
- extract actual listing location where available
- preserve query origin separately from listing location
- preserve URL-region evidence separately
- prevent unverified geography from filtering or ranking
- reduce redundant overlapping query origins
- add source query/page provenance
- add local, out-of-region and unknown-location fixtures

### Acceptance gate

- no runtime text patching or `exec`
- query origin can never become listing location
- out-of-region records cannot appear as local records
- unknown location remains explicit
- every query location has a validated mechanism
- geographic exclusions have recorded reasons

---

## Audit 06 — Identity, Deduplication and Listing Lifecycle

**Status:** approved, not started.

### Purpose

Track listings and likely duplicate vehicles over time without inventing identity or sale certainty.

### Planned scope

- source-specific canonical listing IDs
- VIN and VIN evidence status when available
- normalized seller/dealer identity
- duplicate-candidate fingerprints
- visible match evidence and confidence
- no destructive automatic merge of ambiguous candidates
- first-seen and last-seen timestamps
- active, missing, reappeared and retired states
- consecutive missed-run counts
- relisting evidence
- price-change events based on actual observation dates
- replace misleading weekly field semantics

### Acceptance gate

- source listing ID is never called VIN
- duplicate candidates remain reviewable
- observation count is not labelled elapsed weeks
- disappeared listing is not automatically declared sold
- lifecycle state is reproducible from observations

---

## Audit 07 — Storage, Retention and Repository Hygiene

**Status:** approved, not started.

### Purpose

Bound repository growth while preserving useful history and evidence.

### Planned scope

- quantify current and projected growth
- retention periods for source archives, manual-review archives, logs and inactive listings
- price-history compaction
- decide whether raw data belongs in workflow artifacts or a data branch
- keep code-review diffs readable
- preserve latest normalized output and required trend history
- decide historical F-150/Tundra retention handling without re-enabling them

### Acceptance gate

- repository growth has an approved upper-bound model
- code PRs are not dominated by generated data
- historical trends remain recoverable
- deletion/compaction is tested and documented

---

## Audit 08 — CI and Operational Workflow Hardening

**Status:** approved, not started.

### Purpose

Make testing and collection reproducible, diagnosable and operationally efficient.

### Planned scope

- dependency manifest and tested version locking
- separate code-test and collection responsibilities
- manual inputs for profile, vehicle and source
- scheduled active profile
- per-source runtime telemetry
- abnormal count-drop and count-spike detection
- parser-regression signals
- diagnostic artifacts
- concurrency and source-limit policy
- reduce generated-data approval friction without rerunning collectors

### Acceptance gate

- normal code PRs never run multi-hour collection
- scheduled collection uses only enabled scope
- dependencies are reproducible
- abnormal source behaviour is visible
- workflow failures provide actionable evidence

---

## Audit 09 — F-350 Buyer Intelligence Foundation

**Status:** approved, not started.

### Purpose

Build the repository's primary decision-support output after collection and evidence foundations are trustworthy.

### Planned fields

- target-year status
- total engine hours
- idle hours
- kilometres per engine hour
- idle-hour percentage
- cab configuration
- box length
- SRW/DRW
- four-wheel-drive evidence
- trim and package evidence
- fleet/commercial evidence
- service-history evidence
- accident/title evidence
- emissions-system history
- warranty status
- owner notes
- investigation status
- manual classification and override

### Planned outputs

- early-2020s market context
- price versus mileage
- year-specific price bands
- 2023 candidate comparison
- mileage-discount context
- projected five-year mileage
- engine-hour and idle-hour context when verified
- price-change and listing-lifecycle view
- immediate-investigation watchlist
- seller questions and missing-evidence checklist

### Acceptance gate

- no opaque best-truck score
- every classification has visible reasons
- unknown evidence is not treated as positive or negative
- owner override is preserved
- 2023 target is highlighted without discarding useful comparison years

---

## Audit 10 — Secondary Use-Case Outputs

**Status:** approved, not started.

### Purpose

Create purpose-specific outputs for owned vehicles and the family-friend minivan search without delaying F-350 work.

### RAM 3500 and Forester

Planned lightweight monitoring:

- comparable count
- asking-price and mileage ranges
- median asking price
- trend across observations
- approximate owner-vehicle market position
- likely normal asking range and faster-sale context

### Odyssey and Carnival

Planned practical review:

- friend-specific requirements
- relevant candidate set
- location and availability verification
- accident/title and service evidence
- missing-information checklist
- practical shortlist

### Acceptance gate

- output logic matches each actual purpose
- F-350 assumptions are not applied to minivans
- lightweight valuation does not become an unsupported appraisal claim

---

## Audit 11 — Optional Search Reintroduction

**Status:** approved final stage.

### Purpose

Reintroduce Ford F-150 and Toyota Tundra only after the core system is polished and validated.

### Required order

1. select one optional vehicle
2. perform a limited manual source run
3. validate parser, geography and canonical output
4. measure runtime and generated-data growth
5. correct newly exposed bugs
6. obtain owner approval for cadence
7. enable only after acceptance
8. repeat for the second optional vehicle

### Acceptance gate

- optional search cannot degrade primary F-350 operation
- runtime and storage remain within approved limits
- source behaviour passes the same evidence contracts as active vehicles
- cadence may be manual or less frequent rather than weekly

---

## Full audit exit criteria

The repository is not fully audited until:

- F-150 and Tundra remain paused unless explicitly reapproved
- one validated registry governs scope
- no collector relies on runtime source rewriting
- raw, accepted, rejected and parse-failure counts reconcile
- source parsing failures are visible
- Kijiji geography is verified or explicitly unknown
- AutoTrader pagination is tested
- distance methods are truthful
- field provenance is available
- source listing IDs are not confused with VIN
- lifecycle uses accurate time semantics
- dependency versions are locked
- storage growth is bounded
- documentation matches implementation
- F-350 buyer criteria and enrichment exist
- three consecutive scheduled active-profile runs complete without manual repair
- the resulting F-350 candidate set supports real purchase investigation

## Package completion rule

Each audit package is complete only after:

1. approved scope is implemented on an `ai/*` branch
2. tests pass on the exact final head SHA
3. live validation is performed when external collection behaviour changed
4. documentation and limitations register are updated
5. the owner reviews and merges the PR
6. the branch is deleted
7. completion is recorded before the next package begins