# Audit 00 — Scope Freeze and Runtime Reduction

## Purpose

Audit 00 reduces collection time and generated-data volume while the repository is being audited. It does not change source parsing, filtering, ranking safety, market analysis, or historical data.

## Authoritative scope

`vehicle_registry.json` is the single authoritative list used by collection, manual-review generation, and health reporting.

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

Paused vehicles retain all existing repository data. They do not run collectors, generate new manual-review files, contribute expected health entries, or receive data updates.

## Workflow contract

The workflow must:

1. Validate `vehicle_registry.json` before collection.
2. Derive its config paths from the registry for both source loops.
3. Use the same registry-derived config paths for manual-review generation.
4. Use the same registry-derived config paths for health reporting.
5. Expect ten source runs: two sources for each of five active vehicles.
6. Leave paused-vehicle data untouched.

## Non-scope

Audit 00 does not:

- refactor either collector
- repair Kijiji location extraction
- add AutoTrader pagination
- change filters or purchase criteria
- introduce F-350 analysis or graphs
- delete historical F-150 or Tundra data
- re-enable automated ranking

## Validation

Audit 00 is complete when:

- registry validation passes
- structured tests pass
- the workflow contains no hard-coded vehicle config list
- F-150 and Tundra are disabled only through the registry
- a manual workflow run attempts ten source runs
- no F-150 or Tundra data file changes during that run
- the consolidated health report expects ten source runs
