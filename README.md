# Vehicle Market Information Collector

This repository collects used-vehicle listings from AutoTrader and Kijiji, preserves source/run evidence, and produces decision-safe unranked CSV files for manual review.

Its primary purpose is an informed early-2020s diesel Ford F-350 purchase. It also supports lightweight owned-vehicle value monitoring and a family-vehicle search for a family friend.

## Current status

**Functional collection prototype under structured audit.**

The repository validates governed scope, runs enabled sources independently, preserves failures and stale-output evidence, reconciles records through canonical stages, and creates accepted-record review datasets. It is not a finished appraisal, recommendation, or automatic vehicle-selection system.

Important boundaries:

- Automated cross-source ranking is disabled.
- Every listing requires manual verification.
- AutoTrader now uses a direct schema-v2 source adapter with tested pagination, visible rejects/parse failures, and truthful route/geodesic distance labels.
- Kijiji geography remains untrusted and quarantined until Audit 05.
- Source listing IDs are not VINs or cross-source vehicle identity.
- Historical merged/ranked CSV files are not current recommendations.

See `docs/LIMITATIONS_REGISTER.md` for the tracked limitations.

## Governed vehicle scope

`vehicle_registry.json` is the sole operational authority.

### Active

| Vehicle | Purpose | Priority |
|---|---|---:|
| Ford F-350 | Primary purchase research | 1 |
| RAM 3500 | Owned-vehicle value monitoring | 2 |
| Subaru Forester | Owned-vehicle value monitoring | 2 |
| Honda Odyssey | Family-friend purchase search | 3 |
| Kia Carnival | Family-friend purchase search | 3 |

### Paused until Audit 11

- Ford F-150
- Toyota Tundra

Paused vehicles retain historical data and governed criteria but do not run, produce current evidence/review files, or contribute health expectations.

## Supported outputs

After a successful full run, use:

- `data/<vehicle>/manual_review/<vehicle>_manual_review_latest.csv`
- `data/<vehicle>/evidence/<source>/reconciliation_latest.json`
- `data/<vehicle>/evidence/<source>/accepted_latest.jsonl`
- `data/<vehicle>/evidence/<source>/rejected_latest.jsonl`
- `data/<vehicle>/evidence/<source>/parse_failures_latest.jsonl`
- `data/<vehicle>/run_status/<source>_latest.json`
- `data/run_status/latest.json`
- `data/run_status/latest.md`

AutoTrader additionally writes source-adapter evidence:

- `data/<vehicle>/adapter_evidence/autotrader/requests_latest.jsonl`
- `data/<vehicle>/adapter_evidence/autotrader/records_latest.jsonl`
- `data/<vehicle>/adapter_evidence/autotrader/reconciliation_latest.json`

The supported manual-review CSV is built only from accepted canonical records and contains no `rank` or `score`.

Do not use `data/<vehicle>/merged/*.csv` as current recommendations. Historical merged files remain only as disabled legacy output.

## Evidence boundaries

The canonical equation is:

```text
fetched_records = accepted_records + rejected_records + parse_failures
```

For AutoTrader after Audit 04, `fetched_records` means:

```text
autotrader_adapter_response_listing_objects
```

Every returned listing object is therefore preserved as accepted, rejected, or parse failure, including duplicate source identities. This proves accounting for configured AutoTrader queries, not complete national marketplace coverage.

For Kijiji until Audit 05, `fetched_records` still means:

```text
legacy_collector_emitted_csv_rows
```

Raw values remain distinct from normalized values. Unknowns normalize to JSON `null` while raw source text is retained.

## Current execution flow

1. Validate registry schema v2 and every referenced config schema v2.
2. Build the governed full or single-pair source plan.
3. Run structured tests before collection.
4. AutoTrader reads the approved schema-v2 config directly through `autotrader_run.py` and `autotrader_adapter.py`.
5. Kijiji still receives a disposable legacy projection through the interim safety runner.
6. Record freshness, status, current/stale rows, config isolation, and reconciliation evidence.
7. Preserve source-adapter and canonical raw/normalized/accepted/rejected/parse-failure stages.
8. Build unranked manual review from current accepted evidence.
9. For a full run, create registry-wide health reports and optionally commit generated data.

## AutoTrader guarantees and limits

The direct adapter provides:

- explicit page size and offset requests
- retry/backoff evidence
- per-page query provenance
- reported-total or short-page pagination termination
- repeated-page and maximum-page fail-visible protection
- visible duplicate, parse-failure, and criteria-rejection reasons
- explicit distance methods: route API, geodesic estimate, or unavailable
- no internal ranking or score
- no config mutation or self-managing search locations

AutoTrader source status uses schema version `6` and adapter schema version `1`.

## Kijiji interim boundary

Kijiji still runs through `phase1_kijiji_runner.py`, which disables location-based filtering, distance processing, source ranking, and automatic search-location mutation. Canonical evidence preserves the raw search origin but normalizes Kijiji location/address/distance to null or disabled. Audit 05 replaces this path.

## Workflow modes

The workflow is `.github/workflows/scrape.yml`.

- Scheduled full run: Mondays at 08:00 UTC and commits active-scope generated data.
- Manual full run: `validation_mode=full`; commits only when `commit_generated_data=true`.
- Narrow validation: `validation_mode=single_pair`, one governed vehicle/source pair, uploaded artifact, no generated-data commit.
- Pull requests: compilation, registry/config validation, and structured tests only.
- Generated-data follow-up: acknowledgement only; collectors do not rerun.

Audit 04 validation uses:

```text
validation_mode: single_pair
vehicle_key: ford_f350
source: autotrader
commit_generated_data: false
```

## Local validation

Python 3.11 is the current target.

```bash
python -m pip install requests beautifulsoup4 geopy
python vehicle_registry.py validate
python vehicle_registry.py summary
python vehicle_registry.py active-runs
python -m unittest discover -s tests -v
```

Run governed AutoTrader collection:

```bash
python autotrader_run.py \
  --config config_f350.json \
  --timeout-seconds 4500 \
  --fail-on-unhealthy
```

The legacy command remains a compatibility alias into the same governed runtime:

```bash
python scraper.py --config config_f350.json --fail-on-unhealthy
```

Kijiji remains:

```bash
python phase1_pipeline.py run-source \
  --source kijiji \
  --config config_f350.json \
  --timeout-seconds 4500 \
  -- python phase1_kijiji_runner.py --config config_f350.json
```

Never run `merge.py` to create a recommendation set.

## Repository map

```text
.github/workflows/scrape.yml  tests, full collection, and narrow validation
autotrader_adapter.py         direct request/pagination/parse/filter adapter
autotrader_distance.py        truthful route/geodesic/unavailable evidence
autotrader_history.py         unranked CSV and compatibility observations
autotrader_canonical.py       adapter-to-canonical reconciliation
autotrader_run.py             bounded runtime and source status schema v6
scraper.py                    compatibility alias into autotrader_run.py
canonical_evidence.py         canonical IDs, normalization, stages, reconciliation
phase1_runtime.py             Kijiji-era compatibility runtime and shared protections
phase1_reporting.py           accepted-evidence manual review and health
phase1_kijiji_runner.py       interim Kijiji safety adapter
vehicle_registry.json/.py     operational scope and source plan
vehicle_config.py/config_*.json governed source criteria
merge.py                      disabled legacy merger/ranker
data/                         generated source, adapter, canonical, status, review data
tests/                        fixtures, hostile tests, contracts
docs/                         repository authorities
```

## Documentation authority

- `docs/REPOSITORY_BASELINE.md`
- `docs/ARCHITECTURE_AND_DATA_FLOW.md`
- `docs/VEHICLE_PURPOSES.md`
- `docs/DATA_DICTIONARY.md`
- `docs/LIMITATIONS_REGISTER.md`
- `docs/LEGACY_COMPONENTS.md`
- `docs/AUDIT_ROADMAP.md`
- `PHASE1_MANUAL_REVIEW.md`
- `AUDIT_03_CANONICAL_EVIDENCE.md`
- `AUDIT_04_AUTOTRADER_ADAPTER.md`

## Change authority

All implementation changes use an `ai/*` branch and pull request. The repository owner reviews, merges, and deletes the branch. The approved roadmap controls package sequence.
