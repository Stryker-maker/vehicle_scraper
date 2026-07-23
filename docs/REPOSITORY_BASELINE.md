# Repository Baseline

## Status

**Baseline date:** July 23, 2026  
**Baseline source:** `main` through Audit 06, updated by Audit 07 implementation  
**Project state:** functional collection prototype under structured audit

This document records current supported behaviour. Future-package behaviour is labelled separately.

## Higher purpose

The repository is intended to become a continuously usable vehicle-market information tool that gathers listings, preserves trust evidence, supports repeatable comparison, assists human purchase investigation, and provides lightweight owned-vehicle monitoring without opaque recommendation logic.

The primary use case remains an informed early-2020s diesel Ford F-350 purchase.

## Current supported capability

The repository can:

- validate registry/config schema v2 and Kijiji hub registry v1
- derive governed full or single-pair source plans
- run both sources directly from approved config without mutation
- preserve request/page, raw object, rejection, parse-failure, and canonical evidence
- enforce `fetched = accepted + rejected + parse failures`
- preserve truthful AutoTrader distance methods
- keep Kijiji query origin separate from listing-specific-or-unknown geography
- update source-scoped identity/lifecycle only after a healthy source run
- restore prior lifecycle artifacts when a source run is unhealthy
- keep source IDs distinct from explicit unverified VIN claims
- produce explainable, non-destructive cross-source duplicate candidates
- track actual first/last-seen time, elapsed days, missing/reappeared/retired state, and price observations
- compact price observations while preserving truthful total and price summaries
- prune old/excess retired tombstones with bounded deletion evidence
- build unranked manual review from accepted canonical plus current identity evidence
- fail closed when canonical or identity evidence is missing, corrupt, wrong-run, or count-mismatched
- retain bounded timestamped source/manual-review archives
- remove active-vehicle legacy history/merged CSVs with SHA-256 deletion evidence
- enforce managed file/data-size limits and staged generated-data path governance
- perform narrow validation without committing generated data

## Supported source boundaries

AutoTrader fetched scope:

```text
autotrader_adapter_response_listing_objects
```

Kijiji fetched scope:

```text
kijiji_adapter_json_ld_listing_objects
```

Both adapter schemas are version `1`. Canonical evidence schema is version `1`. Both source statuses use schema version `8`.

## Identity and lifecycle boundary

Identity/lifecycle schema version `2` provides:

- `source_identifier_claim_not_vin`
- explicit VIN evidence statuses
- strict and loose comparison fingerprints
- lifecycle states `active`, `missing`, `reappeared`, and `retired`
- actual UTC timestamps and elapsed seconds/days
- unique-run observation and price semantics
- latest thirteen raw price observations plus compacted count/digest and aggregate values
- at most 500 retired listings/source and a 365-day retired tombstone age limit
- bounded cumulative state-deletion evidence
- high/medium/low duplicate candidates with visible reasons
- `candidate_only_not_merged`

Retirement requires at least three consecutive successful-run misses and fourteen elapsed days. Missing/retired are operational inferences, not sold claims. Failed runs do not advance lifecycle.

## Storage-retention boundary

Storage-retention schema version `1` provides:

- eight timestamped source CSVs per active vehicle/source
- four timestamped manual-review CSVs per active vehicle
- preservation of all current `*_latest` evidence
- active-vehicle removal of `price_history_*.json` and historical merged CSVs
- deletion records with path, reason, category, size, SHA-256, run, and time
- cumulative bounded deletion ledgers retaining the latest 100 detailed records
- 50 MiB maximum individual managed file
- 500 MiB maximum active managed data
- staged-path rejection for non-data, paused-vehicle, and ungoverned-vehicle changes

Audit 07 does not modify paused F-150/Tundra data. Compaction/deletion digests prove accounting order but do not reconstruct removed raw content.

## Current unsupported capability

The repository still cannot reliably establish:

- which listing is the best purchase
- complete marketplace coverage
- independently verified VIN or physical-vehicle identity
- verified sold/removal state
- independent truth of source claims or Kijiji geography
- routable Kijiji distance
- F-350 engine/idle hours, cab/box/SRW/DRW, and verified history enrichment
- fully locked/reproducible dependency and workflow architecture
- purpose-specific decision outputs

## Governing vehicle scope

| Vehicle | State | Purpose | Priority | Enabled sources |
|---|---|---|---:|---|
| Ford F-350 | Enabled | Primary purchase research | 1 | AutoTrader, Kijiji |
| RAM 3500 | Enabled | Owned-vehicle value monitoring | 2 | AutoTrader, Kijiji |
| Subaru Forester | Enabled | Owned-vehicle value monitoring | 2 | AutoTrader, Kijiji |
| Honda Odyssey | Enabled | Family-friend purchase search | 3 | AutoTrader, Kijiji |
| Kia Carnival | Enabled | Family-friend purchase search | 3 | AutoTrader, Kijiji |
| Ford F-150 | Paused | Optional curiosity | 4 | AutoTrader, Kijiji when enabled |
| Toyota Tundra | Paused | Optional curiosity | 4 | AutoTrader, Kijiji when enabled |

F-150 and Tundra must not receive current data, evidence, lifecycle, review, status, or retention deletion updates until their owner-approved package.

## Component inventory

### Authoritative and active

| Component | Present responsibility |
|---|---|
| `vehicle_registry.json` / `vehicle_registry.py` | operational scope and source plan |
| `config_*.json` / `vehicle_config.py` | criteria, source settings, hub validation |
| `.github/workflows/scrape.yml` | tests, collection, health/retention gates, governed data commits |
| `autotrader_*.py` | direct AutoTrader adapter/runtime/evidence |
| `kijiji_*.py` | direct Kijiji adapter/runtime/evidence |
| `canonical_evidence.py` | canonical IDs, stages, reasons, reconciliation |
| `identity_lifecycle.py` | VIN evidence, fingerprints, lifecycle, compact history, duplicate candidates |
| `storage_retention.py` | archive bounds, deletion evidence, size and staged-path gates |
| `phase1_reporting.py` | identity-backed manual review and health schema v6 |
| `phase1_common.py` | supported fields, paths, warnings, health predicate |
| `tests/` | fixtures, hostile tests, governance/workflow contracts |

### Compatibility / historical

| Component | Rule |
|---|---|
| `scraper.py` / `kijiji_scraper.py` | compatibility aliases into governed runtimes |
| `phase1_runtime.py` | retained legacy utilities/tests; not active direct-source path |
| `legacy_runtime_config()` | historical compatibility projection; unused by active adapters |
| `price_history_*.json` | historical only; removed for active vehicles by retention |
| `merge.py` | disabled historical merger/ranker |
| `data/<vehicle>/merged/*.csv` | historical only; removed for active vehicles by retention |
| `trim_tiers.json` | descriptive legacy configuration, not recommendation authority |

## Supported data products

Manual review:

```text
data/<vehicle>/manual_review/<vehicle>_manual_review_latest.csv
```

Adapter and canonical evidence:

```text
data/<vehicle>/adapter_evidence/<source>/...
data/<vehicle>/evidence/<source>/...
```

Identity/lifecycle evidence:

```text
data/<vehicle>/identity_lifecycle/<source>/state_latest.json
data/<vehicle>/identity_lifecycle/<source>/current_latest.jsonl
data/<vehicle>/identity_lifecycle/<source>/events_latest.jsonl
data/<vehicle>/identity_lifecycle/<source>/summary_latest.json
data/<vehicle>/identity_lifecycle/duplicate_candidates_latest.jsonl
```

Retention evidence:

```text
data/<vehicle>/retention/latest.json
data/<vehicle>/retention/deletion_ledger.json
data/retention/latest.json
```

Run health:

```text
data/<vehicle>/run_status/<source>_latest.json
data/run_status/latest.json
data/run_status/latest.md
```

## Present operational guarantees

Current code/tests are intended to guarantee:

1. one registry controls enabled vehicles and sources
2. invalid registry/config/hub state fails before collection
3. direct adapters cannot mutate approved config
4. paused vehicles and disabled sources are omitted
5. runtime is bounded and stale output is not current
6. every returned listing object is accepted, rejected, or a parse failure
7. canonical counts reconcile with machine-readable reasons
8. AutoTrader distance evidence is explicit
9. Kijiji query origin never becomes listing geography
10. identity updates only after healthy source execution
11. unhealthy source runs restore prior identity state
12. source listing IDs are never VINs
13. explicit VIN claims remain unverified evidence
14. duplicate candidates never merge or remove records
15. lifecycle time is actual elapsed time, not fake weeks
16. supported review requires current matching identity evidence
17. price-observation and retired-state growth is bounded
18. timestamped archives and active managed data are bounded
19. every retention deletion has digest-backed evidence
20. generated-data commits reject paused, ungoverned, and non-data paths
21. supported output has no ranking authority
22. narrow validation makes no generated-data commit

## Explicit non-guarantees

`SUCCESS`, `active`, `retired`, format-valid VIN, high-confidence duplicate candidate, or retention verification does not guarantee marketplace completeness, independently verified identity, sold status, availability, condition, fair value, purchase suitability, or raw reconstruction of compacted/deleted evidence.

## Last operating evidence

- Audit 03 full validation: 10/10 source pairs healthy, 381 accepted collector-emitted rows, no stale rows.
- Audit 04 narrow AutoTrader run `29954526608`: 174 objects = 22 accepted + 150 rejected + 2 parse failures.
- Audit 05 narrow Kijiji run `29968206030`: 441 objects = 11 accepted + 430 rejected + 0 parse failures; query geography stayed separate.
- Audit 06 exact-head deterministic/hostile validation passed 66 tests; no external scrape was required because source-fetch behaviour did not change.
- Audit 07 similarly changes deterministic storage/state and commit-gate behaviour rather than source requests; external collection is not required unless integration evidence contradicts tests.

## Repository change authority

Implementation uses an `ai/*` branch and pull request. The owner reviews, merges, and deletes the branch. `docs/AUDIT_ROADMAP.md` governs package sequence unless the owner approves revision.
