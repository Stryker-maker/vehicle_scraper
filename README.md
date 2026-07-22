# Vehicle Market Information Collector

This repository collects used-vehicle listings from AutoTrader and Kijiji, preserves source and run evidence, and produces unranked CSV files for manual review.

Its primary purpose is to support an informed purchase of an early-2020s diesel Ford F-350. It also supports lightweight value monitoring for currently owned vehicles and a family-vehicle search for a family friend.

## Current status

**Functional collection prototype under structured audit.**

The repository can run both sources, isolate failures, preserve fresh results, identify stale output, and generate reviewable datasets. It is not yet a finished appraisal, recommendation, or automatic vehicle-selection system.

Important boundaries:

- Automated cross-source ranking is disabled.
- Every listing requires manual verification.
- Kijiji listing geography is not currently trusted.
- AutoTrader distance values use a legacy method that has not yet been fully disambiguated.
- Source coverage and parsing completeness are not yet proven.
- Historical merged/ranked CSV files are not current recommendations.

See [Current Limitations](docs/LIMITATIONS_REGISTER.md) for the complete tracked register.

## Vehicle purposes and audit scope

The authoritative active and paused vehicle list is [`vehicle_registry.json`](vehicle_registry.json).

### Active during the audit

| Vehicle | Purpose | Priority |
|---|---|---:|
| Ford F-350 | Primary purchase research | 1 |
| RAM 3500 | Owned-vehicle value monitoring | 2 |
| Subaru Forester | Owned-vehicle value monitoring | 2 |
| Honda Odyssey | Family-friend purchase search | 3 |
| Kia Carnival | Family-friend purchase search | 3 |

### Paused until the final audit stage

| Vehicle | Purpose |
|---|---|
| Ford F-150 | Optional curiosity search |
| Toyota Tundra | Optional curiosity search |

Paused vehicles retain their existing historical data but do not run collectors, generate new manual-review files, or contribute expected health entries.

See [Vehicle Purposes and Priorities](docs/VEHICLE_PURPOSES.md) for the governing intent behind each search.

## Supported outputs

Use these files after a successful run:

- `data/<vehicle>/manual_review/<vehicle>_manual_review_latest.csv`
- `data/run_status/latest.md`
- `data/run_status/latest.json`
- `data/<vehicle>/run_status/autotrader_latest.json`
- `data/<vehicle>/run_status/kijiji_latest.json`

The manual-review CSV is the supported human-facing listing set. It intentionally contains no `rank` or `score` column.

Do not use files under `data/<vehicle>/merged/` as current recommendations. They are historical output from a disabled legacy process.

## How the system currently works

1. GitHub Actions validates registry schema v2 and every referenced configuration schema v2.
2. The registry supplies one authoritative plan of enabled vehicle/source runs.
3. Tests run before collection.
4. Each enabled source is attempted independently according to that plan.
5. The governed source-specific config is projected into a temporary flat compatibility file for the legacy collector.
6. Each collector runs with a 75-minute timeout; the approved registry and configs are never passed for mutation.
7. Freshness, minimum schema, row count, warnings, failures, and stale output are recorded per source.
8. Current successful source rows are transformed into an unranked manual-review CSV.
9. A consolidated health report verifies exactly the source runs enabled in the registry.
10. Generated data and evidence are committed by GitHub Actions.

Kijiji currently runs through an interim safety adapter that disables location-based filtering, distance processing, source ranking, and automatic search-location mutation. This prevents known unsafe geography from influencing the review dataset, but it does not repair the underlying Kijiji collector.

See [Architecture and Data Flow](docs/ARCHITECTURE_AND_DATA_FLOW.md) for the complete component and artifact flow.

## Schedule and manual runs

The workflow is defined in `.github/workflows/scrape.yml`.

- Scheduled: Mondays at 08:00 UTC
- Manual: **Actions → Weekly Vehicle Scrape → Run workflow**
- Pull requests: compilation, governed registry/config validation, and structured tests only
- Generated-data follow-up commits: acknowledgement check only; collectors are not rerun

## Local validation

The repository currently targets Python 3.11.

Install collector dependencies:

```bash
python -m pip install requests beautifulsoup4 geopy
```

Validate scope, operational metadata and source-specific criteria:

```bash
python vehicle_registry.py validate
python vehicle_registry.py summary
python vehicle_registry.py active-configs
python vehicle_registry.py active-runs
```

Run the structured tests:

```bash
python -m unittest discover -s tests -v
```

Run one source through the Phase 1 safety wrapper:

```bash
python phase1_pipeline.py run-source \
  --source autotrader \
  --config config_f350.json \
  --timeout-seconds 4500 \
  -- python scraper.py --config config_f350.json
```

Kijiji must use the Phase 1 runner while the current workaround remains in place:

```bash
python phase1_pipeline.py run-source \
  --source kijiji \
  --config config_f350.json \
  --timeout-seconds 4500 \
  -- python phase1_kijiji_runner.py --config config_f350.json
```

Do not run `merge.py` to create a recommendation set. It is disabled legacy code retained for audit history.

## Configuration governance

Operational state belongs only in `vehicle_registry.json`:

- `enabled`
- `purpose`
- `priority`
- `cadence`
- `enabled_sources`
- `analysis_profile`
- `pause_reason` when disabled

Each `config_*.json` file uses schema version 2 and contains only approved vehicle criteria, origin settings and separate AutoTrader/Kijiji query settings.

Legacy flat fields such as `max_results`, `ranking_weights`, shared `search_locations`, `autotrader_make` and `kijiji_make` are not allowed in approved configs. `vehicle_config.py` creates those compatibility values only inside the temporary runtime file required by the current collectors. The result cap is injected as effectively unbounded; legacy ranking weights exist only to keep the collector process compatible and do not govern supported output.

Toggling a vehicle between active and paused remains a single `enabled` change. Source enablement is controlled by `enabled_sources`, and collection, manual-review generation and health reporting all use the same registry source plan.

`ORS_API_KEY` may be configured as a GitHub Actions repository secret. When unavailable or when routing fails, the legacy AutoTrader collector may fall back to straight-line distance; current evidence does not yet distinguish that fallback reliably in every row.

See [Audit 02 Configuration Governance](AUDIT_02_CONFIG_GOVERNANCE.md) for the package contract and validation evidence.

## Repository map

```text
.github/workflows/scrape.yml   GitHub Actions tests and registry-driven collection
vehicle_registry.json          Authoritative operational scope and source plan
vehicle_registry.py            Registry/config validation and run-plan selection
vehicle_config.py              Config schema validation and temporary legacy projection
config_*.json                  Governed per-vehicle and per-source search criteria
phase1_pipeline.py             Command-line orchestration entry point
phase1_runtime.py              Projection, timeout, isolation, freshness, status and history protection
phase1_reporting.py            Registry-source-aware manual-review and health outputs
phase1_common.py               Shared output schemas, paths and warning rules
scraper.py                     Active legacy AutoTrader collector
kijiji_scraper.py              Legacy Kijiji collector executed through the safety adapter
phase1_kijiji_runner.py         Interim Kijiji runtime safety adapter
merge.py                       Disabled legacy merger/ranker
data/                          Generated source data, history, status and manual-review files
tests/                         Structured contract and behaviour tests
docs/                          Repository baseline, architecture, dictionary, limitations and roadmap
```

## Documentation authority

- [Repository Baseline](docs/REPOSITORY_BASELINE.md) — present-state purpose, guarantees, non-guarantees and component status
- [Architecture and Data Flow](docs/ARCHITECTURE_AND_DATA_FLOW.md) — execution path and generated artifacts
- [Vehicle Purposes and Priorities](docs/VEHICLE_PURPOSES.md) — why each vehicle exists in the registry
- [Data Dictionary](docs/DATA_DICTIONARY.md) — current field meanings and evidence limits
- [Current Limitations](docs/LIMITATIONS_REGISTER.md) — known weaknesses and planned correction packages
- [Legacy Components](docs/LEGACY_COMPONENTS.md) — disabled, historical and interim components
- [Approved Audit Roadmap](docs/AUDIT_ROADMAP.md) — Audit 00 through Audit 11 sequence
- [Phase 1 Manual Review](PHASE1_MANUAL_REVIEW.md) — current operating safeguards and files to use
- [Audit 00 Scope Freeze](AUDIT_00_SCOPE_FREEZE.md) — completed runtime-reduction package
- [Audit 02 Configuration Governance](AUDIT_02_CONFIG_GOVERNANCE.md) — governed registry/config contract

## Change workflow

Implementation changes must not be committed directly to `main`.

1. Create an `ai/*` branch.
2. Keep the package within its approved scope.
3. Add or update structured tests where applicable.
4. Open a pull request.
5. Verify the exact PR head and GitHub Actions results.
6. The repository owner reviews and merges.
7. Delete the merged branch.

The approved audit roadmap controls the sequence of corrective work. Roadmap scope changes require repository-owner approval.
