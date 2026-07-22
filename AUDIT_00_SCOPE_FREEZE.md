# Audit 00 — Scope Freeze and Runtime Reduction

**Status:** complete and merged through PR #2 on July 22, 2026.

## Purpose

Audit 00 reduced collection time and generated-data volume while the repository is being audited. It did not change source parsing, filtering, ranking safety, market analysis or historical data.

## Authoritative scope

`vehicle_registry.json` is the single authoritative list used by collection, manual-review generation and health reporting.

### Active

| Vehicle | Purpose |
|---|---|
| Ford F-350 | Primary used-truck purchase research |
| RAM 3500 | Owned-vehicle value monitoring |
| Subaru Forester | Owned-vehicle value monitoring |
| Honda Odyssey | Family-friend family-vehicle search |
| Kia Carnival | Family-friend family-vehicle search |

### Paused

| Vehicle | Reason |
|---|---|
| Ford F-150 | Optional curiosity search; high runtime and generated-data volume |
| Toyota Tundra | Optional curiosity search; deferred until the final audit stage |

Paused vehicles retain all existing repository data. They do not run collectors, generate new manual-review files, contribute expected health entries or receive data updates.

## Workflow contract

The workflow must:

1. validate `vehicle_registry.json` before collection
2. derive config paths from the registry for both source loops
3. use the same registry-derived config paths for manual-review generation
4. use the same registry-derived config paths for health reporting
5. expect ten source runs: two sources for each of five active vehicles
6. leave paused-vehicle data untouched

## Intentional non-scope

Audit 00 did not:

- refactor either collector
- repair Kijiji location extraction
- add AutoTrader pagination
- change filters or purchase criteria
- introduce F-350 analysis or graphs
- delete historical F-150 or Tundra data
- re-enable automated ranking

## Acceptance evidence

Manual workflow run `29926745165` on branch `ai/audit-00-scope-freeze` established:

- registry validation passed
- structured tests passed
- collection completed
- 10/10 expected enabled source runs were healthy
- overall health was `SUCCESS_WITH_WARNINGS`
- no stale rows were reported
- 362 current records were collected
- only the five enabled vehicle data directories and consolidated health files changed
- Ford F-150 data did not change
- Toyota Tundra data did not change
- the collection window was approximately 31 minutes

The generated-data commit was `3023687062e304cf881ade89aa5df6184eeb5530`.

PR #2 was merged to `main`, and branch `ai/audit-00-scope-freeze` was deleted.

## Continuing rule

F-150 and Tundra remain paused until Audit 11 unless the repository owner explicitly approves a roadmap revision. Audit 00 proves scope control and runtime reduction only; it does not resolve source-data limitations.