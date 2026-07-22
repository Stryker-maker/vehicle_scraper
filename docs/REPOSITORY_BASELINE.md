# Repository Baseline

## Status

**Baseline date:** July 22, 2026  
**Baseline source:** `main` after Audit 01, updated by Audit 02  
**Project state:** functional collection prototype under structured audit

This document records what the repository currently is. Desired future behaviour is labelled separately.

## Higher purpose

The repository is intended to become a continuously usable market-information tool that gathers listings, preserves trust evidence, supports repeatable comparisons, assists human purchase investigation and provides lightweight owned-vehicle value monitoring without opaque recommendation logic.

The primary decision use case is an informed purchase of an early-2020s diesel Ford F-350, ideally a 2023 model at a reasonable price with acceptable kilometres and evidence about engine hours, idle hours, service history and prior use.

## Current supported capability

The repository currently supports supervised collection and manual review. It can:

- validate registry schema v2 and every referenced config schema v2 before collection
- derive an explicit enabled vehicle/source run plan from one registry
- keep operational state separate from source search criteria
- maintain separate AutoTrader and Kijiji make/model/location settings
- project governed configs into temporary flat compatibility files for legacy collectors
- prevent collectors from receiving or mutating approved config files
- attempt enabled sources independently with a 75-minute timeout
- continue after individual source failures or timeouts
- distinguish fresh output from preserved stale output
- validate a minimum source CSV schema
- disable the legacy row cap for runtime collection
- record structured per-source run evidence
- identify a limited set of row-quality warnings
- protect price history from failed runs and same-day duplication
- build unranked manual-review files from current successful enabled sources
- write health evidence for exactly the source pairs enabled in the registry

## Current unsupported capability

The repository does not yet answer reliably:

- which listing is the best purchase
- whether the market dataset is complete
- actual Kijiji listing geography
- whether every fetched record parsed correctly
- why every omitted record was rejected
- cross-source physical vehicle identity
- sold/disappeared/relisted lifecycle state
- route distance versus straight-line fallback on every AutoTrader row
- independent verification of source claims
- highway-use likelihood from engine and idle hours

Those require later approved packages.

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

The detailed intent is governed by [Vehicle Purposes and Priorities](VEHICLE_PURPOSES.md).

## Component inventory

### Authoritative and active

| Component | Status | Present responsibility |
|---|---|---|
| `vehicle_registry.json` | Authoritative | Operational state, purpose, priority, cadence, enabled sources and analysis profile |
| `vehicle_registry.py` | Active governance | Validates registry/config consistency and emits active configs/source runs |
| `vehicle_config.py` | Active governance | Validates config schema v2 and creates temporary legacy projections |
| `config_*.json` | Governed criteria | Shared criteria, origin and separate source query settings |
| `.github/workflows/scrape.yml` | Active | Tests, registry-driven collection, reporting and data commits |
| `phase1_pipeline.py` | Active | Source execution, registry-aware review and health commands |
| `phase1_runtime.py` | Active safety layer | Projection, timeout, isolation, history protection and status evidence |
| `phase1_common.py` | Active | Shared paths, minimum schemas, fields and warning rules |
| `phase1_reporting.py` | Active | Registry-source-aware review and health outputs |
| `tests/` | Active | Governance, Phase 1 and documentation contracts |
| `trim_tiers.json` | Active legacy configuration | Supplies trim keywords to collectors |

### Active legacy or interim

| Component | Status | Present concern |
|---|---|---|
| `scraper.py` | Active legacy collector | Legacy ranking, pagination and distance behaviour remain |
| `kijiji_scraper.py` | Legacy collector still executed | Geography and ranking cannot be trusted directly |
| `phase1_kijiji_runner.py` | Active interim workaround | Runtime text replacement and `exec` remain temporary |
| Temporary flat runtime config | Compatibility only | Contains injected `max_results`, ranking weights and selected source locations; never approved authority |
| Source CSV `rank` and `score` | Legacy source output | Excluded from supported manual review |

### Disabled or historical

| Component | Status | Rule |
|---|---|---|
| `merge.py` | Disabled legacy | Must not create recommendations |
| `data/<vehicle>/merged/*.csv` | Historical | Not current recommendations |
| `data/<vehicle>/merged/RANKING_DISABLED.md` | Active warning | Directs users to manual review |
| Paused F-150 and Tundra data | Historical while paused | Retained but not refreshed |

See [Legacy Components](LEGACY_COMPONENTS.md).

## Supported data products

### Human-facing listing set

`data/<vehicle>/manual_review/<vehicle>_manual_review_latest.csv`

It includes current successful enabled sources, removes `rank` and `score`, exposes review status, quarantines Kijiji location/distance and retains warning-bearing records.

### Run health

- `data/run_status/latest.md`
- `data/run_status/latest.json`

These reflect the registry's enabled source pairs rather than assuming every vehicle always has two sources.

### Source evidence

- `data/<vehicle>/run_status/<source>_latest.json`
- `data/<vehicle>/latest/<vehicle>_<source>_latest.csv`
- timestamped source archives
- source-specific price-history JSON

Source CSVs are implementation artifacts, not purchase recommendations.

## Present operational guarantees

Current code and tests are intended to guarantee:

1. one registry controls enabled vehicles and sources
2. invalid or conflicting registry/config state fails before collection
3. approved configs contain no legacy `max_results`, ranking weights or shared source-location authority
4. collectors receive only temporary compatibility projections
5. approved configuration remains byte-for-byte unchanged
6. paused vehicles and disabled sources are omitted from collection, review and health expectations
7. runtime is bounded and remaining attempts continue after failure
8. stale files are not counted as fresh output
9. expected enabled sources need fresh, non-empty, minimum-schema-valid output to be healthy
10. same-day price-history duplication is controlled
11. supported manual review contains no automated rank or score
12. known Kijiji location uncertainty remains visible

## Explicit non-guarantees

`SUCCESS` or `SUCCESS_WITH_WARNINGS` does not guarantee marketplace completeness, correct parsing, actual Kijiji location, routed distance, verified source claims, duplicate identity, elapsed lifecycle, current availability, mechanical condition, fair value or purchase suitability.

## Last live operating result

Audit 00 live validation on July 22, 2026 produced 10/10 healthy enabled source runs, 362 current records, no stale rows, `SUCCESS_WITH_WARNINGS`, approximately 31 minutes of collection and no F-150/Tundra changes.

Audit 02 requires a new live validation because the collector input is now generated from governed schema-v2 configs. That validation must prove ten source runs, unchanged active criteria, no paused-vehicle changes and successful config-isolation evidence.

## Repository change authority

Implementation work uses an approved `ai/*` branch and pull request. The owner reviews, merges and deletes the branch. The [Approved Audit Roadmap](AUDIT_ROADMAP.md) governs sequence unless the owner approves revision.

## Baseline interpretation rule

Where code, generated data or older documentation conflicts with this baseline, record the conflict and resolve it through the appropriate approved package rather than guessing.
