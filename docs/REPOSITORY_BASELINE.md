# Repository Baseline

## Status

**Baseline date:** July 22, 2026  
**Baseline source:** `main` through Audit 04, updated by Audit 05 implementation  
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
- run Kijiji directly from approved schema-v2 config and validated hub registry
- reject unsupported/duplicate Kijiji hubs rather than fall back to an undefined query
- bound source execution with a 75-minute timeout
- distinguish fresh from stale output
- preserve adapter and canonical raw, normalized, accepted, rejected, and parse-failure evidence
- enforce `fetched = accepted + rejected + parse failures`
- generate stable source-scoped listing IDs and run observations
- preserve per-field evidence status and source claims
- require reconciliation, configured-query pagination completion, and accepted records for source health
- build unranked manual-review CSVs from accepted evidence
- preserve Kijiji listing-specific geography or explicit unknown without substituting query origin
- keep Kijiji distance processing/filtering disabled
- protect price history from failed runs and same-day duplication
- perform one-pair validation without committing generated data

### AutoTrader supported boundary

AutoTrader uses `autotrader_run.py` and direct adapter modules. It preserves request attempts, page provenance, response listing objects, duplicates, parse failures, criteria rejections, explicit distance methods, and adapter-to-canonical reconciliation.

Fetched scope is `autotrader_adapter_response_listing_objects`. Source status uses schema version `6`; adapter evidence uses schema version `1`.

### Kijiji supported boundary

Kijiji uses `kijiji_run.py`, `kijiji_locations.py`, and direct adapter modules. It preserves validated query hubs, request/page provenance, JSON-LD listing objects, duplicates, parse failures, criteria rejections, URL-region evidence, and adapter-to-canonical reconciliation.

Fetched scope is `kijiji_adapter_json_ld_listing_objects`. Source status uses schema version `7`; adapter and location-registry versions are `1`.

Kijiji query origin is not listing geography. Listing-specific structured source geography is retained as unverified source evidence; otherwise location/address are null and unknown. Distance is null/disabled.

## Current unsupported capability

The repository still cannot reliably establish:

- which listing is the best purchase
- complete marketplace coverage
- independent truth of source claims or Kijiji geography
- routable Kijiji distance
- VIN or cross-source physical-vehicle identity
- duplicate confidence or merge authority
- sold/disappeared/relisted lifecycle state
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
| `config_*.json` / `vehicle_config.py` | approved criteria, source settings, hub validation |
| `.github/workflows/scrape.yml` | tests, full collection, single-pair validation, data commits |
| `autotrader_adapter.py` | AutoTrader request/pagination/record accounting |
| `autotrader_distance.py` | explicit route/geodesic/unavailable evidence |
| `autotrader_history.py` | unranked AutoTrader CSV and observations |
| `autotrader_canonical.py` | AutoTrader adapter-to-canonical reconciliation |
| `autotrader_run.py` | bounded AutoTrader runtime/status schema v6 |
| `kijiji_locations.py` | validated Cars & Trucks hub registry |
| `kijiji_adapter.py` | Kijiji requests/JSON-LD parsing/record accounting |
| `kijiji_history.py` | unranked Kijiji CSV and observations |
| `kijiji_canonical.py` | Kijiji adapter-to-canonical reconciliation |
| `kijiji_run.py` | bounded Kijiji runtime/status schema v7 |
| `canonical_evidence.py` | canonical IDs, normalization, stages, reconciliation |
| `phase1_reporting.py` | accepted-evidence manual review and full health |
| `phase1_common.py` | shared schemas, paths, warnings, health predicate |
| `tests/` | fixtures, hostile tests, governance/workflow contracts |

### Compatibility / remaining legacy

| Component | Present concern |
|---|---|
| `scraper.py` | compatibility alias into `autotrader_run.py` |
| `kijiji_scraper.py` | compatibility alias into `kijiji_run.py` |
| `phase1_runtime.py` | shared legacy wrapper/utilities still retained for historical tests/utilities |
| `legacy_runtime_config()` | historical compatibility projection; not used by active adapters |
| `trim_tiers.json` | descriptive keyword tiers, not recommendation authority |
| source price-history JSON | observation compatibility, not lifecycle authority |
| `merge.py` | disabled historical merger/ranker |

`phase1_kijiji_runner.py` is removed. Runtime source rewriting and `exec` are not part of the supported source paths.

## Supported data products

### Decision-safe manual review

`data/<vehicle>/manual_review/<vehicle>_manual_review_latest.csv`

Contains accepted current-run canonical records, evidence statuses, canonical IDs/references, observation-based names, and no rank/score.

### Adapter evidence

Under `data/<vehicle>/adapter_evidence/<source>/`:

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
2. invalid registry/config/hub state fails before collection
3. approved configs prohibit legacy controls
4. both active adapters read schema v2 directly and cannot mutate it
5. paused vehicles and disabled sources are omitted
6. runtime is bounded and stale files are not current
7. every adapter-returned listing object is accepted, rejected, or a parse failure
8. raw evidence and null-safe normalized values remain distinct
9. exclusions and failures have machine-readable reasons
10. source pagination failures are visible
11. AutoTrader distance method is explicit, not ambiguous
12. Kijiji query origin never becomes listing geography
13. missing Kijiji geography remains unknown
14. Kijiji distance remains null/disabled
15. supported output has no ranking authority
16. single-pair validation makes no generated-data commit

## Explicit non-guarantees

`SUCCESS` or `SUCCESS_WITH_WARNINGS` does not guarantee complete marketplace coverage, independently verified source claims/geography, physical vehicle identity, lifecycle, availability, mechanical condition, fair value, or purchase suitability.

## Last live operating results

Audit 03 full validation on July 22, 2026 produced 10/10 healthy source runs, 381 fetched and accepted collector-emitted rows, no stale rows, and no optional-vehicle data changes.

Audit 04 narrow F-350 AutoTrader run `29954526608` validated 174 response objects: 22 accepted, 150 rejected, and 2 parse failures, with complete configured-query pagination and no data commit.

Audit 05 requires one narrow F-350 Kijiji run to prove source status schema v7, adapter/location-registry schema v1, validated hubs, JSON-LD object reconciliation, listing-specific-or-unknown geography, disabled distance/ranking, unchanged config, and no generated-data commit.

## Repository change authority

Implementation work uses an approved `ai/*` branch and pull request. The owner reviews, merges, and deletes the branch. `docs/AUDIT_ROADMAP.md` governs sequence unless the owner approves revision.
