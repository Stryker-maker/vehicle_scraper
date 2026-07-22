# Repository Baseline

## Status

**Baseline date:** July 22, 2026  
**Baseline source:** `main` after Audit 00 merge commit `c3dd100b84aa453010b6283188a8ab57a230c284`  
**Project state:** functional collection prototype under structured audit

This document records what the repository currently is. It does not describe the desired final architecture unless explicitly labelled as future work.

## Higher purpose

The repository is intended to become a continuously usable market-information tool that:

- gathers vehicle listings from multiple public marketplaces
- preserves enough evidence to determine whether a run and its records can be trusted
- supports repeatable market comparisons over time
- helps a human investigate, compare and monitor real purchase candidates
- supports approximate current-value monitoring for owned vehicles
- remains understandable and maintainable without relying on opaque recommendation logic

The primary decision use case is an informed purchase of an early-2020s diesel Ford F-350, ideally a 2023 model at a reasonable price with acceptable kilometres and evidence about engine hours, idle hours, service history and prior use.

## Current supported capability

The repository currently supports supervised collection and manual review.

It can:

- validate an authoritative enabled/paused vehicle registry
- attempt AutoTrader and Kijiji independently for every enabled vehicle
- isolate collector configuration changes from approved repository configuration
- enforce a 75-minute timeout per source
- continue attempting remaining collectors after a source failure or timeout
- distinguish fresh current output from preserved stale output
- validate a minimum source CSV schema
- preserve all rows that pass the current source filters rather than applying the legacy 50-row output cap
- record structured per-source run status
- identify a limited set of row-quality warnings
- protect price-history files from failed runs and duplicate same-day observations
- build unranked manual-review files from current successful source output
- write a consolidated health report for all expected enabled source runs

## Current unsupported capability

The repository does not yet provide a trustworthy automated answer to any of these questions:

- Which listing is the best purchase?
- Is the collected market dataset complete?
- Is a Kijiji listing actually located within the intended search area?
- Did every source record parse correctly?
- Why was every omitted record rejected?
- Are two records from different sources definitely the same vehicle?
- Has a disappeared listing been sold?
- Is an AutoTrader distance routed driving distance or straight-line fallback?
- Is a source-reported accident or title claim independently verified?
- Is a high-mileage truck likely highway-driven based on engine and idle hours?

Those capabilities require later approved audit packages.

## Governing vehicle scope

`vehicle_registry.json` is the single authority for operational enablement.

| Vehicle | Current state | Purpose | Priority |
|---|---|---|---:|
| Ford F-350 | Enabled | Primary purchase research | 1 |
| RAM 3500 | Enabled | Owned-vehicle value monitoring | 2 |
| Subaru Forester | Enabled | Owned-vehicle value monitoring | 2 |
| Honda Odyssey | Enabled | Family-friend purchase search | 3 |
| Kia Carnival | Enabled | Family-friend purchase search | 3 |
| Ford F-150 | Paused | Optional curiosity | 4 |
| Toyota Tundra | Paused | Optional curiosity | 4 |

The detailed intent is governed by [Vehicle Purposes and Priorities](VEHICLE_PURPOSES.md).

## Component inventory

### Authoritative and active

| Component | Status | Present responsibility |
|---|---|---|
| `vehicle_registry.json` | Authoritative | Defines enabled and paused vehicles, purpose and priority |
| `vehicle_registry.py` | Active | Validates registry integrity and emits enabled config paths |
| `.github/workflows/scrape.yml` | Active | Runs tests, scheduled/manual collection, reporting and generated-data commits |
| `phase1_pipeline.py` | Active | Command-line entry point for source execution, manual review and health reporting |
| `phase1_runtime.py` | Active safety layer | Runs collectors with timeout, config isolation, history protection and status evidence |
| `phase1_common.py` | Active | Shared paths, minimum schemas, field lists and warning rules |
| `phase1_reporting.py` | Active | Builds supported manual-review CSVs and consolidated health reports |
| `tests/` | Active | Protects current Phase 1 and registry contracts |
| `config_*.json` | Active or paused by registry | Holds per-vehicle legacy source criteria |
| `trim_tiers.json` | Active legacy configuration | Supplies trim keyword tiers to collectors |

### Active legacy or interim

| Component | Status | Present responsibility and concern |
|---|---|---|
| `scraper.py` | Active legacy collector | Collects AutoTrader records; still contains legacy ranking, distance and location-mutation behaviour beneath the safety wrapper |
| `kijiji_scraper.py` | Legacy collector still executed | Supplies Kijiji parsing and fetching but cannot be trusted directly for geography or ranking |
| `phase1_kijiji_runner.py` | Active interim workaround | Rewrites exact portions of `kijiji_scraper.py` at runtime to bypass unsafe geography, ranking and location mutation |
| Source CSV `rank` and `score` fields | Legacy source output | May exist internally but are excluded from the supported manual-review output |
| `max_results` and `ranking_weights` config fields | Legacy configuration | Retained for compatibility; result cap is overridden and ranking is not used for supported review output |

### Disabled or historical

| Component | Status | Rule |
|---|---|---|
| `merge.py` | Disabled legacy | Not called by the workflow; must not be used to create recommendations |
| `data/<vehicle>/merged/*.csv` | Historical | Do not use as current recommendations |
| `data/<vehicle>/merged/RANKING_DISABLED.md` | Active warning marker | Directs users to the supported manual-review file |
| Paused F-150 and Tundra data | Historical while paused | Retained but not refreshed during the audit |

See [Legacy Components](LEGACY_COMPONENTS.md) for detailed handling rules.

## Supported data products

### Human-facing current listing set

`data/<vehicle>/manual_review/<vehicle>_manual_review_latest.csv`

This is the supported listing-review artifact. It:

- includes only current successful source runs for the active run ID
- removes `rank` and `score`
- makes review status explicit
- blanks Kijiji location and distance fields that would otherwise misrepresent search-origin data
- preserves unverified Kijiji search-origin values separately
- retains warning-bearing records rather than silently discarding them

### Run health

- `data/run_status/latest.md`
- `data/run_status/latest.json`

These show expected source runs, current and stale row counts, failures and warning summaries.

### Source evidence

- `data/<vehicle>/run_status/autotrader_latest.json`
- `data/<vehicle>/run_status/kijiji_latest.json`
- `data/<vehicle>/latest/<vehicle>_<source>_latest.csv`
- timestamped source archives
- source-specific price-history JSON

Source CSVs are implementation artifacts, not final purchase recommendations.

## Present operational guarantees

The current code and tests are intended to guarantee only the following:

1. Enabled scope comes from one registry.
2. Paused vehicles are omitted from all registry-driven workflow stages.
3. Collector runtime is bounded.
4. Approved configuration is restored if a collector mutates it.
5. A stale file is not counted as fresh current output.
6. An expected enabled source must produce a fresh, non-empty, minimum-schema-valid file for the run to be healthy.
7. A failed source does not prevent remaining source attempts.
8. Same-day price-history duplication is controlled.
9. Supported manual-review output contains no automated rank or score.
10. Known Kijiji location uncertainty remains visible.

## Explicit non-guarantees

A successful or `SUCCESS_WITH_WARNINGS` run does not guarantee:

- marketplace completeness
- correct parsing of every record
- accurate actual Kijiji location
- verified driving distance
- accurate seller, accident, title or service claims
- correct duplicate matching
- correct elapsed days or weeks on market
- vehicle availability at review time
- mechanical condition
- fair value
- purchase suitability

## Last validated Audit 00 operating result

The Audit 00 live validation run on July 22, 2026 produced:

- 10/10 healthy enabled source runs
- 362 current records
- no stale rows
- `SUCCESS_WITH_WARNINGS`
- approximately 31 minutes from first source start to final source completion
- no F-150 or Tundra data changes

This proves the registry-driven reduced scope operated as designed. It does not resolve any open data-quality limitation.

## Repository change authority

- No implementation work is committed directly to `main`.
- Work uses an approved `ai/*` branch and pull request.
- The repository owner reviews and merges.
- The owner deletes the merged branch.
- Audit packages must preserve approved scope and non-scope.
- The audit sequence in [Approved Audit Roadmap](AUDIT_ROADMAP.md) is governing unless the owner approves a revision.

## Baseline interpretation rule

Where code, generated data or older documentation conflicts with this baseline, do not guess which is authoritative. Record the conflict in the limitations register and resolve it through the appropriate approved audit package.