# Repository Baseline

## Status

**Baseline date:** July 22, 2026  
**Baseline source:** `main` after Audit 02, updated by Audit 03 implementation  
**Project state:** functional collection prototype under structured audit

This document records current supported behaviour. Desired future behaviour is labelled separately.

## Higher purpose

The repository is intended to become a continuously usable market-information tool that gathers listings, preserves trust evidence, supports repeatable comparisons, assists human purchase investigation, and provides lightweight owned-vehicle value monitoring without opaque recommendation logic.

The primary decision use case remains an informed purchase of an early-2020s diesel Ford F-350, ideally a 2023 model at a reasonable price with acceptable kilometres and evidence about engine hours, idle hours, service history, and prior use.

## Current supported capability

The repository can:

- validate registry schema v2 and all referenced config schema-v2 files
- derive one explicit enabled vehicle/source run plan
- keep operational state separate from source criteria
- project approved criteria into disposable legacy collector input
- verify approved configs remain unchanged
- attempt enabled sources independently with a 75-minute timeout
- continue after individual failures/timeouts
- distinguish fresh from stale output
- preserve every fresh collector-emitted row as canonical raw evidence
- normalize typed values with explicit JSON nulls
- generate stable source-scoped listing IDs and run-specific observation IDs
- preserve per-field evidence status and source claims
- classify rows as accepted, rejected, or parse failure with reasons
- enforce collector-boundary count reconciliation
- require reconciliation and accepted records for source health
- build decision-safe manual-review CSVs only from accepted current-run evidence
- quarantine Kijiji location/distance evidence
- write per-source and consolidated health schema-v5 evidence
- protect price history from failed runs and same-day duplication

## Current unsupported capability

The repository still cannot reliably establish:

- which listing is the best purchase
- marketplace-wide source completeness
- HTTP/raw-response preservation inside current collectors
- every pre-CSV parser failure or filter exclusion
- verified AutoTrader pagination
- actual Kijiji listing geography
- routed versus straight-line AutoTrader distance on every row
- VIN or cross-source physical-vehicle identity
- duplicate confidence or destructive merge authority
- sold/disappeared/relisted lifecycle state
- independent verification of source claims
- highway-use likelihood from engine and idle hours
- bounded retention/repository growth

Those remain assigned to later approved packages.

## Governing vehicle scope

`vehicle_registry.json` is the sole operational authority.

| Vehicle | State | Purpose | Priority | Cadence | Enabled sources |
|---|---|---|---:|---|---|
| Ford F-350 | Enabled | Primary purchase research | 1 | Weekly | AutoTrader, Kijiji |
| RAM 3500 | Enabled | Owned-vehicle value monitoring | 2 | Weekly | AutoTrader, Kijiji |
| Subaru Forester | Enabled | Owned-vehicle value monitoring | 2 | Weekly | AutoTrader, Kijiji |
| Honda Odyssey | Enabled | Family-friend purchase search | 3 | Weekly | AutoTrader, Kijiji |
| Kia Carnival | Enabled | Family-friend purchase search | 3 | Weekly | AutoTrader, Kijiji |
| Ford F-150 | Paused | Optional curiosity | 4 | Weekly when enabled | AutoTrader, Kijiji |
| Toyota Tundra | Paused | Optional curiosity | 4 | Weekly when enabled | AutoTrader, Kijiji |

## Component inventory

### Authoritative and active

| Component | Present responsibility |
|---|---|
| `vehicle_registry.json` | operational scope, purpose, cadence, source plan |
| `vehicle_registry.py` | registry/config consistency and run-plan validation |
| `vehicle_config.py` | config schema v2 and disposable legacy projection |
| `config_*.json` | approved shared/source criteria |
| `.github/workflows/scrape.yml` | tests, registry-driven collection, reporting, generated-data commits |
| `phase1_pipeline.py` | CLI orchestration and final health gate |
| `phase1_runtime.py` | execution, timeout, freshness, isolation, canonical integration, status |
| `canonical_evidence.py` | raw/normalized/accepted/rejected/parse evidence and reconciliation |
| `phase1_reporting.py` | accepted-evidence manual review and consolidated health |
| `phase1_common.py` | shared schemas, paths, warnings, health contract |
| `tests/` | governance, hostile evidence, runtime, reporting, workflow, and documentation contracts |

### Active legacy or interim

| Component | Present concern |
|---|---|
| `scraper.py` | pagination, internal ranking, distance, and pre-CSV parse visibility remain legacy |
| `kijiji_scraper.py` | geography/ranking cannot be trusted directly |
| `phase1_kijiji_runner.py` | runtime text replacement and `exec` remain temporary |
| temporary flat config | compatibility only; never approved authority |
| source CSV rank/score | retained only in implementation artifacts, not supported review |
| source price-history JSON | observation history, not lifecycle authority |

### Disabled or historical

| Component | Rule |
|---|---|
| `merge.py` | disabled; must not create current recommendations |
| `data/<vehicle>/merged/*.csv` | historical only |
| paused F-150/Tundra data | retained but not refreshed |

## Supported data products

### Decision-safe manual review

`data/<vehicle>/manual_review/<vehicle>_manual_review_latest.csv`

This file contains only accepted current-run canonical records. It includes canonical IDs, raw/normalized references, evidence statuses, warning/review fields, safer observation names, and no rank/score.

### Canonical source evidence

For each source:

- `raw_latest.jsonl`
- `normalized_latest.jsonl`
- `accepted_latest.jsonl`
- `rejected_latest.jsonl`
- `parse_failures_latest.jsonl`
- `reconciliation_latest.json`

These live under `data/<vehicle>/evidence/<source>/`.

### Run health

- `data/<vehicle>/run_status/<source>_latest.json`
- `data/run_status/latest.json`
- `data/run_status/latest.md`

Health now requires current/fresh/minimum-schema-valid output, uncapped execution, config isolation, recognized canonical evidence, successful reconciliation, and at least one accepted record.

## Present operational guarantees

Current code/tests are intended to guarantee:

1. one registry controls enabled vehicles and sources
2. invalid/conflicting registry/config state fails before collection
3. approved configs contain no legacy controls
4. collectors receive only temporary compatibility projections
5. approved configuration remains byte-for-byte unchanged
6. paused vehicles/disabled sources are omitted from collection, evidence, review, and health expectations
7. runtime is bounded and remaining attempts continue after failure
8. stale files are not counted as current
9. every collector-emitted row is represented as accepted, rejected, or parse failure
10. raw source strings remain preserved after canonicalization
11. normalized unknowns use null rather than invented values
12. every canonical rejection/failure has machine-readable reasons
13. source listing IDs are explicitly not VINs
14. supported manual review consumes accepted evidence only
15. Kijiji location uncertainty remains visible and quarantined

## Explicit non-guarantees

`SUCCESS` or `SUCCESS_WITH_WARNINGS` does not guarantee marketplace completeness, correct legacy collector parsing before CSV output, actual Kijiji location, routed distance, verified source claims, physical vehicle identity, lifecycle, current availability, mechanical condition, fair value, or purchase suitability.

## Last live operating result

Audit 02 live validation on July 22, 2026 produced 10/10 healthy enabled source runs, 374 current collector rows, no stale rows, `SUCCESS_WITH_WARNINGS`, and no F-150/Tundra changes.

Audit 03 requires a new live branch validation because canonical artifacts, manual-review schema, source health, and consolidated reconciliation totals change.

## Repository change authority

Implementation work uses an approved `ai/*` branch and pull request. The owner reviews, merges, and deletes the branch. The [Approved Audit Roadmap](AUDIT_ROADMAP.md) governs sequence unless the owner approves revision.
