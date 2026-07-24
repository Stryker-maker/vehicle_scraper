# Audit 11A — Ford F-150 Manual Reintroduction

## Status

Started from Audit 10 merge commit `10f0467e1b21d2609a3f7a2bc3045a3dfd577582` on branch `ai/audit-11a-f150-manual-reintroduction`.

## Purpose

Reintroduce the optional Ford F-150 search as an explicitly manual, non-publishing workflow without expanding the unattended weekly collection set, changing the primary F-350 use case, or activating Toyota Tundra.

The roadmap requires F-150 first and Tundra separately. This package is Audit 11A only. Toyota Tundra remains paused for a later Audit 11B package and may remain paused permanently if the owner does not approve it.

## Approved operating state

Ford F-150 becomes:

- registry-enabled for explicit single-pair manual dispatch
- cadence `manual`
- purpose `optional_curiosity`
- analysis profile `optional_curiosity`
- sources AutoTrader and Kijiji
- excluded from scheduled/full weekly collection, health expectations, manual-review generation, anomaly comparison, retention mutation, and publication
- non-publishing in Audit 11A

The existing F-150 vehicle criteria, origin, distance boundary, source queries, and source locations remain unchanged unless live validation proves a specific defect. Reintroduction alone does not authorize criteria expansion or inference.

## Cadence authority

Registry cadence must become operational rather than descriptive.

- `weekly` entries form the unattended/full collection plan.
- `manual` entries may be selected only through explicit `single_pair` dispatch.
- A manual entry must not enter a scheduled/full plan merely because `enabled` is true.
- Reporting, health, anomalies, retention, diagnostics, and publication for a full run must use the same weekly plan that collection used.
- A paused entry cannot be manually collected.

The weekly core remains five vehicles and ten source runs. Audit 11A adds two governed manual source pairs for F-150 without changing that weekly count.

## Manual F-150 result boundary

A successful F-150 single-pair run must:

1. pass reusable deterministic CI
2. select exactly one F-150 source
3. collect through the existing governed source adapter
4. reconcile fetched, accepted, rejected, and parse-failure evidence
5. update identity/lifecycle only after a successful source run
6. validate source status and current identity counts
7. skip F-350 buyer intelligence and Audit 10 secondary-purpose output
8. upload source, canonical, adapter, lifecycle, and current CSV evidence for seven days
9. include an explicit optional-curiosity summary stating that no purchase need, rank, score, appraisal, or recommendation is implied
10. skip retention and repository publication

Audit 11A does not create a specialized F-150 recommendation model. The accepted source CSV and governed evidence artifact are the usable manual search result.

## Required validation

Deterministic and hostile tests must prove:

- F-150 is enabled with cadence `manual`
- Tundra remains paused
- weekly plans remain exactly ten source runs and exclude F-150/Tundra
- manual plans expose exactly the two F-150 source pairs
- full collection uses weekly cadence only
- single-pair accepts enabled manual F-150
- single-pair rejects paused Tundra
- F-150 does not enter F-350 or secondary-purpose analysis paths
- F-150 single-pair publication remains impossible
- available failed-run evidence is still uploaded
- registry/config/source isolation remains intact

Required live validation is one non-publishing AutoTrader F-150 single pair followed by one non-publishing Kijiji F-150 single pair. Both must pass pagination, reconciliation, lifecycle, and evidence-artifact checks before owner review.

## Stop conditions

Stop and revise before merge if:

- F-150 enters an unattended weekly/full plan
- weekly expected source runs exceed ten
- Tundra becomes enabled or its data changes
- F-150 receives F-350 buyer assumptions or Audit 10 secondary-purpose semantics
- a manual F-150 run can publish generated data
- source criteria, hubs, distance, canonical equations, lifecycle thresholds, or retention limits change without defect evidence
- ranking or scoring is reintroduced
- a failed run loses available status or adapter evidence

## Non-scope

Audit 11A does not activate Tundra, add monthly scheduling, change F-150 criteria, add transaction-price or appraisal evidence, create purchase recommendations, add ranking, change active weekly vehicle outputs, alter source adapters, change identity/lifecycle thresholds, change retention limits, or claim repository completion.

Three consecutive unattended weekly full runs without manual repair remain a separate final completion requirement.