# Repository Baseline

## Status

**Baseline date:** July 22, 2026  
**Baseline source:** `main` after Audit 03, updated by Audit 04 implementation  
**Project state:** functional collection prototype under structured audit

This document records current supported behaviour. Future behaviour is labelled separately.

## Higher purpose

The repository is intended to become a continuously usable market-information tool that gathers listings, preserves trust evidence, supports repeatable comparisons, assists human purchase investigation, and provides lightweight owned-vehicle monitoring without opaque recommendation logic.

The primary decision use case remains an informed early-2020s diesel Ford F-350 purchase.

## Current supported capability

The repository can:

- validate registry schema v2 and referenced config schema v2
- derive a governed full or single-pair source plan
- keep operational state separate from source criteria
- run AutoTrader directly from approved schema-v2 config
- run Kijiji through an isolated disposable compatibility config
- bound source execution with a 75-minute timeout
- distinguish fresh from stale output
- preserve canonical raw, normalized, accepted, rejected, and parse-failure evidence
- enforce `fetched = accepted + rejected + parse failures`
- generate stable source-scoped listing IDs and run observations
- preserve per-field evidence status and source claims
- require reconciliation and accepted records for source health
- build unranked manual-review CSVs from accepted evidence
- quarantine Kijiji location/distance evidence
- protect price history from failed runs and same-day duplication
- perform one-pair validation without committing generated data

### AutoTrader supported boundary

AutoTrader uses `autotrader_run.py` and the direct adapter modules. It preserves request attempts, page provenance, response listing objects, duplicates, parse failures, criteria rejections, explicit distance methods, and adapter-to-canonical reconciliation.

AutoTrader fetched scope is `autotrader_adapter_response_listing_objects`. Source status uses schema version `6`; adapter evidence uses schema version `1`.

### Kijiji interim boundary

Kijiji remains on the runtime-patched legacy collector. Its canonical fetched scope remains `legacy_collector_emitted_csv_rows`, and source status remains schema version `5`. Geography is quarantined until Audit 05.

## Current unsupported capability

The repository still cannot reliably establish:

- which listing is the best purchase
- complete national marketplace coverage
- Kijiji request/response and pre-CSV parse completeness
- actual Kijiji listing geography
- VIN or cross-source physical-vehicle identity
- duplicate confidence or merge authority
- sold/disappeared/relisted lifecycle state
- independent verification of source claims
- F-350 engine/idle-hour and configuration evidence
- bounded retention/repository growth
- purpose-specific decision outputs

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
| `vehicle_registry.json` / `vehicle_registry.py` | operational scope and validated source plan |
| `config_*.json` / `vehicle_config.py` | approved criteria and config validation |
| `.github/workflows/scrape.yml` | tests, full collection, single-pair validation, data commits |
| `autotrader_adapter.py` | AutoTrader request/pagination/record accounting |
| `autotrader_distance.py` | explicit route/geodesic/unavailable evidence |
| `autotrader_history.py` | unranked accepted CSV and compatibility observations |
| `autotrader_canonical.py` | adapter-to-canonical reconciliation |
| `autotrader_run.py` | bounded AutoTrader runtime and status schema v6 |
| `canonical_evidence.py` | canonical IDs, normalization, stages, reconciliation |
| `phase1_reporting.py` | accepted-evidence manual review and full health |
| `phase1_common.py` | shared schemas, paths, warnings, health predicate |
| `tests/` | fixtures, hostile tests, governance and workflow contracts |

### Active legacy/interim

| Component | Present concern |
|---|---|
| `kijiji_scraper.py` | source geography, parser, ranking, and mutation remain legacy |
| `phase1_kijiji_runner.py` | runtime text replacement and `exec` remain temporary |
| `phase1_runtime.py` | still owns the Kijiji legacy compatibility path |
| temporary flat config | Kijiji compatibility only; never approved authority |
| `trim_tiers.json` | descriptive keyword tiers, not recommendation authority |
| source price-history JSON | observation compatibility, not lifecycle authority |

### Compatibility/disabled/historical

| Component | Rule |
|---|---|
| `scraper.py` | compatibility alias into `autotrader_run.py` |
| `merge.py` | disabled; must not create recommendations |
| `data/<vehicle>/merged/*.csv` | historical only |
| paused F-150/Tundra data | retained but not refreshed |

## Supported data products

### Decision-safe manual review

`data/<vehicle>/manual_review/<vehicle>_manual_review_latest.csv`

Contains accepted current-run canonical records, evidence statuses, canonical IDs/references, observation-based names, and no rank/score.

### AutoTrader adapter evidence

Under `data/<vehicle>/adapter_evidence/autotrader/`:

- `requests_latest.jsonl`
- `records_latest.jsonl`
- `reconciliation_latest.json`

### Canonical source evidence

Under `data/<vehicle>/evidence/<source>/`:

- `raw_latest.jsonl`
- `normalized_latest.jsonl`
- `accepted_latest.jsonl`
- `rejected_latest.jsonl`
- `parse_failures_latest.jsonl`
- `reconciliation_latest.json`

### Run health

- `data/<vehicle>/run_status/<source>_latest.json`
- `data/run_status/latest.json`
- `data/run_status/latest.md`

## Present operational guarantees

Current code/tests are intended to guarantee:

1. one registry controls enabled vehicles and sources
2. invalid registry/config state fails before collection
3. approved configs prohibit legacy controls
4. AutoTrader reads schema v2 directly and cannot mutate it
5. Kijiji receives only a disposable compatibility projection
6. paused vehicles and disabled sources are omitted
7. runtime is bounded
8. stale files are not current
9. AutoTrader response listing objects are all accepted, rejected, or parse failures
10. Kijiji emitted CSV rows are all canonically accounted for
11. raw evidence and null-safe normalized values remain distinct
12. exclusions and failures have machine-readable reasons
13. AutoTrader pagination failures are visible
14. AutoTrader distance method is route, geodesic, or unavailable—not ambiguous
15. supported output has no ranking authority
16. Kijiji geography uncertainty remains visible
17. single-pair validation makes no generated-data commit

## Explicit non-guarantees

`SUCCESS` or `SUCCESS_WITH_WARNINGS` does not guarantee complete marketplace coverage, independently verified source claims, actual Kijiji geography, physical vehicle identity, lifecycle, availability, mechanical condition, fair value, or purchase suitability.

## Last live operating result

Audit 03 live validation on July 22, 2026 produced 10/10 healthy source runs, 381 fetched and accepted collector-emitted rows, zero rejected records, zero parse failures, no stale rows, and no F-150/Tundra changes.

Audit 04 requires only one narrow F-350 AutoTrader smoke run because the changed external behaviour is source-specific. The run must prove source status schema v6, adapter schema v1, complete configured-query pagination, response-object reconciliation, truthful distance evidence, unchanged config, and no generated-data commit.

## Repository change authority

Implementation work uses an approved `ai/*` branch and pull request. The owner reviews, merges, and deletes the branch. `docs/AUDIT_ROADMAP.md` governs sequence unless the owner approves revision.
