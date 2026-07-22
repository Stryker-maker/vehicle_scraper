# Vehicle Market Information Collector

This repository collects used-vehicle listings from AutoTrader and Kijiji, preserves source and run evidence, and produces decision-safe unranked CSV files for manual review.

Its primary purpose is to support an informed purchase of an early-2020s diesel Ford F-350. It also supports lightweight value monitoring for currently owned vehicles and a family-vehicle search for a family friend.

## Current status

**Functional collection prototype under structured audit.**

The repository can validate operational scope, run both sources independently, isolate failures, preserve fresh results, reconcile every collector-emitted row through canonical evidence stages, and generate reviewable accepted-record datasets. It is not yet a finished appraisal, recommendation, or automatic vehicle-selection system.

Important boundaries:

- Automated cross-source ranking is disabled.
- Every listing requires manual verification.
- Kijiji listing geography is not currently trusted.
- AutoTrader distance values use a legacy method that has not yet been fully disambiguated.
- Canonical reconciliation begins at the legacy collector CSV boundary; marketplace fetch and parser completeness are not yet proven.
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

Paused vehicles retain their existing historical data but do not run collectors, generate new evidence/manual-review files, or contribute expected health entries.

See [Vehicle Purposes and Priorities](docs/VEHICLE_PURPOSES.md) for the governing intent behind each search.

## Supported outputs

Use these files after a successful run:

- `data/<vehicle>/manual_review/<vehicle>_manual_review_latest.csv`
- `data/<vehicle>/evidence/<source>/reconciliation_latest.json`
- `data/<vehicle>/evidence/<source>/accepted_latest.jsonl`
- `data/<vehicle>/evidence/<source>/rejected_latest.jsonl`
- `data/<vehicle>/evidence/<source>/parse_failures_latest.jsonl`
- `data/run_status/latest.md`
- `data/run_status/latest.json`
- `data/<vehicle>/run_status/<source>_latest.json`

The manual-review CSV is the supported human-facing listing set. It is built only from accepted canonical records and intentionally contains no `rank` or `score` column. It uses explicit evidence-status fields and safer names such as `observation_count` instead of the misleading legacy `weeks_tracked` field.

Do not use files under `data/<vehicle>/merged/` as current recommendations. They are historical output from a disabled legacy process.

## Canonical evidence stages

For each fresh source CSV, `canonical_evidence.py` writes:

```text
raw_latest.jsonl
  → normalized_latest.jsonl
    → accepted_latest.jsonl
    → rejected_latest.jsonl
    → parse_failures_latest.jsonl
  → reconciliation_latest.json
```

The enforced equation is:

```text
fetched_records = accepted_records + rejected_records + parse_failures
```

During the current legacy-collector phase, `fetched_records` means **records emitted into the collector CSV at the canonical boundary**. It does not prove how many marketplace records were requested, returned, skipped, or lost inside the collector. Audits 04 and 05 will extend this evidence chain into the source adapters.

Raw values are preserved exactly as strings. Normalized values use real JSON `null` for unknown/unavailable data rather than misleading sentinels. Source listing IDs remain source claims and are explicitly not VINs or cross-source identity.

## How the system currently works

1. GitHub Actions validates registry schema v2 and every referenced configuration schema v2.
2. The registry supplies one authoritative plan of enabled vehicle/source runs.
3. Tests run before collection.
4. Each enabled source is attempted independently according to that plan.
5. The governed source-specific config is projected into a temporary flat compatibility file for the legacy collector.
6. Each collector runs with a 75-minute timeout; approved registry/config files are never passed for mutation.
7. Freshness, minimum source schema, current/stale rows, warnings, failures, and config isolation are recorded.
8. Every collector-emitted row is preserved and classified as accepted, rejected, or parse failure.
9. A source is healthy only when canonical evidence reconciles and at least one accepted record exists.
10. Current accepted records are transformed into the decision-safe manual-review CSV.
11. A consolidated health report verifies exactly the source runs enabled in the registry and totals fetched/accepted/rejected/parse-failure records.
12. Generated data and evidence are committed by GitHub Actions.

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

Run one source through the Phase 1 wrapper:

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

Operational state belongs only in `vehicle_registry.json`: `enabled`, `purpose`, `priority`, `cadence`, `enabled_sources`, `analysis_profile`, and `pause_reason` when disabled.

Each `config_*.json` file uses schema version 2 and contains only approved vehicle criteria, origin settings, and separate AutoTrader/Kijiji query settings.

Legacy flat fields such as `max_results`, `ranking_weights`, shared `search_locations`, `autotrader_make`, and `kijiji_make` are not allowed in approved configs. `vehicle_config.py` creates those compatibility values only inside the temporary runtime file required by current collectors.

`ORS_API_KEY` may be configured as a GitHub Actions repository secret. When unavailable or when routing fails, the legacy AutoTrader collector may fall back to straight-line distance; current evidence does not yet distinguish that fallback reliably in every row.

## Repository map

```text
.github/workflows/scrape.yml   GitHub Actions tests and registry-driven collection
vehicle_registry.json          Authoritative operational scope and source plan
vehicle_registry.py            Registry/config validation and run-plan selection
vehicle_config.py              Config schema validation and temporary legacy projection
config_*.json                  Governed per-vehicle and per-source search criteria
phase1_pipeline.py             Command-line orchestration entry point
phase1_runtime.py              Runtime, isolation, freshness, evidence and status control
canonical_evidence.py          Canonical IDs, normalization, stage artifacts and reconciliation
phase1_reporting.py            Evidence-backed manual-review and health outputs
phase1_common.py               Shared output schemas, paths and warning rules
scraper.py                     Active legacy AutoTrader collector
kijiji_scraper.py              Legacy Kijiji collector executed through the safety adapter
phase1_kijiji_runner.py         Interim Kijiji runtime safety adapter
merge.py                       Disabled legacy merger/ranker
data/                          Generated source data, canonical evidence, status and review files
tests/                         Structured contract, hostile and behaviour tests
docs/                          Repository baseline, architecture, dictionary, limitations and roadmap
```

## Documentation authority

- [Repository Baseline](docs/REPOSITORY_BASELINE.md)
- [Architecture and Data Flow](docs/ARCHITECTURE_AND_DATA_FLOW.md)
- [Vehicle Purposes and Priorities](docs/VEHICLE_PURPOSES.md)
- [Data Dictionary](docs/DATA_DICTIONARY.md)
- [Current Limitations](docs/LIMITATIONS_REGISTER.md)
- [Legacy Components](docs/LEGACY_COMPONENTS.md)
- [Approved Audit Roadmap](docs/AUDIT_ROADMAP.md)
- [Phase 1 Manual Review](PHASE1_MANUAL_REVIEW.md)
- [Audit 00 Scope Freeze](AUDIT_00_SCOPE_FREEZE.md)
- [Audit 02 Configuration Governance](AUDIT_02_CONFIG_GOVERNANCE.md)
- [Audit 03 Canonical Evidence](AUDIT_03_CANONICAL_EVIDENCE.md)

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
