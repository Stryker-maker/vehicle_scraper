# Vehicle Market Information Collector

This repository collects used-vehicle listings from AutoTrader and Kijiji, preserves source/run evidence, and produces decision-safe unranked CSV files for manual review.

Its primary purpose is an informed early-2020s diesel Ford F-350 purchase. It also supports lightweight owned-vehicle value monitoring and a family-vehicle search for a family friend.

## Current status

**Functional collection prototype under structured audit.**

The repository validates governed scope, runs enabled sources independently, preserves failures and stale-output evidence, reconciles records through source-adapter and canonical stages, and creates accepted-record review datasets. It is not a finished appraisal, recommendation, or automatic vehicle-selection system.

Important boundaries:

- Automated cross-source ranking is disabled.
- Every listing requires manual verification.
- AutoTrader uses a direct schema-v2 adapter with tested pagination and truthful route/geodesic distance labels.
- Kijiji uses a direct schema-v2 JSON-LD adapter; query origin never becomes listing geography.
- Kijiji location is listing-specific unverified source evidence when present, otherwise unknown; distance remains disabled.
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

Both sources additionally write adapter evidence:

```text
data/<vehicle>/adapter_evidence/<source>/requests_latest.jsonl
data/<vehicle>/adapter_evidence/<source>/records_latest.jsonl
data/<vehicle>/adapter_evidence/<source>/reconciliation_latest.json
```

The supported manual-review CSV is built only from accepted canonical records and contains no `rank` or `score`.

Do not use `data/<vehicle>/merged/*.csv` as current recommendations. Historical merged files remain only as disabled legacy output.

## Evidence boundaries

The required equation is:

```text
fetched_records = accepted_records + rejected_records + parse_failures
```

For AutoTrader:

```text
autotrader_adapter_response_listing_objects
```

For Kijiji after Audit 05:

```text
kijiji_adapter_json_ld_listing_objects
```

Every returned adapter listing object is preserved as accepted, rejected, or parse failure, including duplicate source identities. This proves accounting for configured queries, not complete marketplace coverage.

Raw values remain distinct from normalized values. Unknowns normalize to JSON `null` while raw source payloads and query provenance are retained.

## Current execution flow

1. Validate registry schema v2 and every referenced config schema v2.
2. Validate every Kijiji query label against the explicit hub registry.
3. Build the governed full or single-pair source plan.
4. Run structured tests before collection.
5. AutoTrader runs through `autotrader_run.py` and `autotrader_adapter.py`.
6. Kijiji runs through `kijiji_run.py` and `kijiji_adapter.py` with no runtime patching or `exec`.
7. Record requests, pagination, failures, current/stale rows, config isolation, and reconciliation evidence.
8. Preserve adapter and canonical raw/normalized/accepted/rejected/parse-failure stages.
9. Build unranked manual review from current accepted evidence.
10. For a full run, create registry-wide health reports and optionally commit generated data.

## AutoTrader guarantees and limits

The direct adapter provides explicit page-size/offset requests, retry/backoff evidence, per-page provenance, bounded pagination protection, visible duplicate/parse/exclusion reasons, truthful route/geodesic/unavailable distance methods, no ranking, and no config mutation.

AutoTrader source status uses schema version `6` and adapter schema version `1`.

## Kijiji guarantees and limits

The direct Kijiji adapter provides:

- six validated Cars & Trucks query hubs with no `l0` fallback
- explicit retry and page evidence
- JSON-LD `ItemList`, `Vehicle`, `Car`, and `Product` extraction
- visible duplicate, parse-failure, and criteria-rejection reasons
- query hub, page, request URL, and response-item provenance
- listing-specific geography only from structured source fields
- explicit unknown geography when listing evidence is absent
- URL region evidence kept separate from location
- disabled distance processing/filtering
- no rank/score, runtime patching, or config mutation

Kijiji source status uses schema version `7`, adapter schema version `1`, and location-registry version `1`.

## Workflow modes

The workflow is `.github/workflows/scrape.yml`.

- Scheduled full run: Mondays at 08:00 UTC and commits active-scope generated data.
- Manual full run: `validation_mode=full`; commits only when `commit_generated_data=true`.
- Narrow validation: `validation_mode=single_pair`, one governed vehicle/source pair, uploaded artifact, no generated-data commit.
- Pull requests: compilation, registry/config validation, and structured tests only.
- Generated-data follow-up: acknowledgement only; collectors do not rerun.

Audit 05 validation uses:

```text
validation_mode: single_pair
vehicle_key: ford_f350
source: kijiji
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

Run governed Kijiji collection:

```bash
python kijiji_run.py \
  --config config_f350.json \
  --timeout-seconds 4500 \
  --fail-on-unhealthy
```

Legacy command names remain compatibility aliases into the same governed runtimes:

```bash
python scraper.py --config config_f350.json --fail-on-unhealthy
python kijiji_scraper.py --config config_f350.json --fail-on-unhealthy
```

Never run `merge.py` to create a recommendation set.

## Repository map

```text
.github/workflows/scrape.yml  tests, full collection, narrow validation
autotrader_*.py              direct AutoTrader adapter/runtime/evidence
kijiji_locations.py           validated Kijiji hub registry
kijiji_adapter.py             direct JSON-LD request/parser adapter
kijiji_history.py             unranked Kijiji CSV/observation output
kijiji_canonical.py           adapter-to-canonical reconciliation
kijiji_run.py                 bounded runtime and source status schema v7
kijiji_scraper.py             compatibility alias into kijiji_run.py
canonical_evidence.py         canonical IDs, normalization, stages, reconciliation
phase1_runtime.py             shared legacy protections and utilities
phase1_reporting.py           accepted-evidence manual review and health
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
- `AUDIT_05_KIJIJI_ADAPTER.md`

## Change authority

All implementation changes use an `ai/*` branch and pull request. The repository owner reviews, merges, and deletes the branch. The approved roadmap controls package sequence.
