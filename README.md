# Vehicle Market Information Collector

This repository collects used-vehicle listings from AutoTrader and Kijiji, preserves source/run evidence, tracks source-scoped listing lifecycle, and produces decision-safe unranked CSV files for manual review.

Its primary purpose is an informed early-2020s diesel Ford F-350 purchase. It also supports lightweight owned-vehicle value monitoring and a family-vehicle search for a family friend.

## Current status

**Functional collection prototype under structured audit.**

The repository validates governed scope, runs enabled sources independently, preserves adapter and canonical evidence, reconciles every fetched listing object, tracks explainable listing lifecycle, and produces accepted-record review datasets. It is not a finished appraisal, recommendation, or automatic vehicle-selection system.

Important boundaries:

- Automated cross-source ranking is disabled.
- Every listing requires manual verification.
- Source listing IDs are source-scoped claims and are never VINs.
- VIN values are recorded only when explicitly source-reported; they remain unverified claims.
- Duplicate matches are explainable candidates only and never merge canonical records.
- `missing` and `retired` are operational lifecycle inferences from successful source runs, not source claims that a vehicle sold.
- Historical merged/ranked CSV files are not current recommendations.
- Historical `price_history_*.json` files are not used by supported output.

See `docs/LIMITATIONS_REGISTER.md` for tracked limitations.

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

Paused vehicles retain historical data and governed criteria but do not run or receive current evidence.

## Supported outputs

After a successful full run, use:

```text
data/<vehicle>/manual_review/<vehicle>_manual_review_latest.csv
data/<vehicle>/run_status/<source>_latest.json
data/<vehicle>/adapter_evidence/<source>/requests_latest.jsonl
data/<vehicle>/adapter_evidence/<source>/records_latest.jsonl
data/<vehicle>/adapter_evidence/<source>/reconciliation_latest.json
data/<vehicle>/evidence/<source>/accepted_latest.jsonl
data/<vehicle>/evidence/<source>/rejected_latest.jsonl
data/<vehicle>/evidence/<source>/parse_failures_latest.jsonl
data/<vehicle>/evidence/<source>/reconciliation_latest.json
data/<vehicle>/identity_lifecycle/<source>/state_latest.json
data/<vehicle>/identity_lifecycle/<source>/current_latest.jsonl
data/<vehicle>/identity_lifecycle/<source>/events_latest.jsonl
data/<vehicle>/identity_lifecycle/<source>/summary_latest.json
data/<vehicle>/identity_lifecycle/duplicate_candidates_latest.jsonl
data/run_status/latest.json
data/run_status/latest.md
```

The supported manual-review CSV is built from accepted canonical records joined one-to-one with current identity/lifecycle evidence. It contains no `rank` or `score`.

Do not use `data/<vehicle>/merged/*.csv` as current recommendations. Historical merged files remain disabled legacy output.

## Evidence boundaries

The canonical equation is:

```text
fetched_records = accepted_records + rejected_records + parse_failures
```

AutoTrader fetched scope:

```text
autotrader_adapter_response_listing_objects
```

Kijiji fetched scope:

```text
kijiji_adapter_json_ld_listing_objects
```

Every returned adapter listing object is preserved as accepted, rejected, or parse failure. This proves accounting for configured queries, not complete marketplace coverage.

Kijiji query origin never becomes listing geography. Listing location is listing-specific unverified source evidence when present and otherwise unknown. Kijiji distance remains disabled.

## Identity and lifecycle model

`identity_lifecycle.py` provides schema version `1`.

- `canonical_listing_id` remains a stable source-scoped listing claim.
- `source_listing_id_status` remains `source_identifier_claim_not_vin`.
- Explicit VIN claims are labelled `source_reported_format_valid_unverified`, invalid, conflicting, or not reported.
- Strict and loose fingerprints support explainable comparison; they are not physical-vehicle identity authority.
- Cross-source duplicate candidates are labelled high, medium, or low confidence with visible reasons and `candidate_only_not_merged`.
- Lifecycle states are `active`, `missing`, `reappeared`, and `retired`.
- A listing retires only after at least three consecutive successful source-run misses and at least fourteen actual elapsed days.
- Actual timestamps and elapsed seconds/days replace fake week semantics.
- Price observations are keyed by run ID and expose first, previous, current, and change values.

Both source status files use schema version `8`; adapter schema remains `1`.

## Current execution flow

1. Validate registry schema v2 and all config schema-v2 files.
2. Validate Kijiji hubs and build the governed full or single-pair plan.
3. Run structured and hostile tests.
4. Run the direct AutoTrader or Kijiji adapter.
5. Preserve request, page, raw object, rejection, parse-failure, and canonical evidence.
6. Update identity/lifecycle only after a successful, reconciled source run.
7. Roll back lifecycle artifacts if the source run is unhealthy.
8. Build cross-source duplicate candidates without merging records.
9. Build manual review from accepted canonical plus current identity evidence.
10. For full runs, write consolidated health and optionally commit active-scope data.

## Workflow modes

The workflow is `.github/workflows/scrape.yml`.

- Scheduled full run: Mondays at 08:00 UTC and commits active-scope generated data.
- Manual full run: `validation_mode=full`; commits only with `commit_generated_data=true`.
- Narrow validation: `validation_mode=single_pair`; one governed source pair, temporary artifact, no data commit.
- Pull requests: compile, validate, and run deterministic tests only.
- Generated-data follow-up: acknowledgement only; collectors do not rerun.

## Local validation

```bash
python -m pip install requests beautifulsoup4 geopy
python vehicle_registry.py validate
python vehicle_registry.py summary
python vehicle_registry.py active-runs
python -m unittest discover -s tests -v
```

Run governed sources:

```bash
python autotrader_run.py --config config_f350.json --timeout-seconds 4500 --fail-on-unhealthy
python kijiji_run.py --config config_f350.json --timeout-seconds 4500 --fail-on-unhealthy
```

Legacy command names remain aliases into the governed runtimes. Never run `merge.py` to create a recommendation set.

## Repository map

```text
.github/workflows/scrape.yml  tests, full collection, narrow validation
autotrader_*.py               direct AutoTrader adapter/runtime/evidence
kijiji_*.py                   direct Kijiji adapter/runtime/evidence
canonical_evidence.py         canonical stages and reconciliation
identity_lifecycle.py         identity claims, lifecycle, price observations, duplicate candidates
phase1_reporting.py           accepted plus identity evidence manual review and health
vehicle_registry.json/.py     operational scope and source plan
vehicle_config.py/config_*.json governed criteria
merge.py                      LEGACY / DISABLED merger and ranker
data/                         generated evidence, lifecycle, status, and review data
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
- `AUDIT_06_IDENTITY_LIFECYCLE.md`

## Change authority

All implementation changes use an `ai/*` branch and pull request. The repository owner reviews, merges, and deletes the branch. The approved roadmap controls package sequence.
