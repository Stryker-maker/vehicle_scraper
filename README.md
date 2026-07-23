# Vehicle Market Information Collector

This repository collects used-vehicle listings from AutoTrader and Kijiji, preserves source/run evidence, tracks source-scoped listing lifecycle, bounds generated-data growth, and produces decision-safe unranked outputs for manual review and F-350 purchase investigation.

Its primary purpose is an informed early-2020s diesel Ford F-350 purchase. It also supports lightweight owned-vehicle value monitoring and a family-vehicle search for a family friend.

## Current status

**Functional collection and F-350 investigation prototype under structured audit.**

The repository validates governed scope, runs enabled sources independently, preserves adapter and canonical evidence, reconciles every fetched listing object, tracks explainable listing lifecycle, applies bounded retention, uses reproducible CI/collection workflows, and builds transparent F-350 investigation context. It is not an appraisal, automatic recommendation, independent vehicle-history service, or replacement for inspection.

Important boundaries:

- Automated cross-source ranking is disabled.
- Every listing and source claim requires manual verification.
- Source listing IDs are source-scoped claims and are never VINs.
- VIN values are recorded only when explicitly source-reported; they remain unverified claims.
- Duplicate matches are explainable candidates only and never merge canonical records.
- `missing` and `retired` are operational lifecycle inferences, not source claims that a vehicle sold.
- Asking-price bands are observed listing context, not sale prices or appraisal.
- Mileage-adjusted projections are descriptive asking-price context, not future value.
- Owner overrides never rewrite source or computed evidence.
- Historical merged/ranked CSV files and legacy `price_history_*.json` are not supported outputs.

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

Paused vehicles retain historical data and governed criteria but do not run or receive current evidence. Retention and publication validation do not modify their data.

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
data/<vehicle>/retention/latest.json
data/<vehicle>/retention/deletion_ledger.json
data/run_status/latest.json
data/run_status/latest.md
data/run_status/anomalies_latest.json
data/run_status/anomalies_latest.md
data/run_status/publication_latest.json
data/retention/latest.json
```

F-350-specific buyer investigation adds:

```text
data/ford_f350/buyer_intelligence/investigation_latest.jsonl
data/ford_f350/buyer_intelligence/investigation_latest.csv
data/ford_f350/buyer_intelligence/seller_questions_latest.jsonl
data/ford_f350/buyer_intelligence/market_summary_latest.json
data/ford_f350/buyer_intelligence/market_summary_latest.md
```

The general manual-review CSV is built from accepted canonical records joined one-to-one with current identity/lifecycle evidence. The F-350 investigation output additionally joins current raw adapter payloads to expose configuration, usage, history, price-band, projection, seller-question, and owner-override context. Neither output contains `rank` or `score`.

Do not use `data/<vehicle>/merged/*.csv` as current recommendations. Historical merged CSVs are disabled legacy output and are deleted for active vehicles by governed retention with SHA-256 deletion evidence.

## Evidence boundaries

```text
fetched_records = accepted_records + rejected_records + parse_failures
```

AutoTrader fetched scope is `autotrader_adapter_response_listing_objects`.

Kijiji fetched scope is `kijiji_adapter_json_ld_listing_objects`.

Every returned adapter listing object is preserved as accepted, rejected, or parse failure. This proves accounting for configured queries, not complete marketplace coverage.

Kijiji query origin never becomes listing geography. Listing location is listing-specific unverified source evidence when present and otherwise unknown. Kijiji distance remains disabled.

## Identity and lifecycle model

`identity_lifecycle.py` provides schema version `2`.

- `canonical_listing_id` remains a stable source-scoped listing claim.
- `source_listing_id_status` remains `source_identifier_claim_not_vin`.
- Explicit VIN claims are labelled format-valid unverified, invalid, conflicting, or not reported.
- Strict and loose fingerprints support explainable comparison; they are not physical-vehicle identity authority.
- Cross-source duplicate candidates are high, medium, or low confidence with visible reasons and `candidate_only_not_merged`.
- Lifecycle states are `active`, `missing`, `reappeared`, and `retired`.
- Retirement requires at least three consecutive successful source-run misses and at least fourteen elapsed days.
- Price history retains total counts and first/previous/current/minimum/maximum values while keeping the newest thirteen raw observations plus a chained SHA-256 compaction digest.
- Retired tombstones are limited to 500 per source and 365 days since last successful observation.

Both source status files use schema version `8`; adapter schema remains `1`.

## F-350 buyer intelligence

`f350_buyer_intelligence.py` provides buyer-intelligence schema version `1`. It builds only from current successful source status, accepted canonical evidence, matching raw adapter payloads, and matching identity/lifecycle evidence. Stale Audit 03 review CSVs and legacy rank/history fields are not inputs.

It can expose source-text claims for trim, STX/FX4/Tremor packages, cab, box, SRW/DRW, drivetrain, engine hours, idle hours, service-record availability, accident/title language, and prior-use language. Missing evidence remains unknown and becomes a visible investigation gap and seller question.

When supported, it calculates kilometres per engine hour and idle-hour percentage as usage context only. It also provides:

- observed asking-price quartiles with cohort basis and comparable count
- transparent mileage-adjusted asking-price regression with sample count, slope, intercept, and `r_squared`
- a five-year mileage scenario using the owner's expected 5,000–8,000 km per year
- explainable non-ranked classifications and reasons
- seller questions driven by missing evidence or visible concerns
- owner dispositions, notes, tags, and reasoned classification overrides

The computed classification remains visible when an owner override is applied. `f350_owner_overrides.json` is governed input; it never rewrites collected or computed evidence. `trim_tiers.json` remains legacy descriptive configuration and is not buyer-intelligence or purchase authority.

## Storage and retention

`storage_retention.py` provides storage-retention schema version `1`.

For each active vehicle, a governed full run retains eight timestamped source CSVs per source, four timestamped manual-review CSVs, and all current `*_latest` evidence. File deletions record path, reason, size, SHA-256, run ID, and time. Detailed ledgers retain the latest 100 records while cumulative counts, bytes, and chained digests continue.

Repository-growth gates are 50 MiB per managed file and 500 MiB total active managed data.

## Reproducible workflows

The repository separates three workflows:

- `.github/workflows/ci.yml` — reusable deterministic CI for non-data pull-request changes, manual CI, and collection preflight
- `.github/workflows/generated-data.yml` — integrity and retention validation for `data/**` pull-request changes
- `.github/workflows/scrape.yml` — schedule/manual collection only; it has no pull-request trigger

Python is fixed to `3.11.13`. `requirements.lock` contains exact dependency pins, and GitHub-owned actions use exact commit SHAs.

Scheduled full collection runs Mondays at 08:00 UTC. Manual inputs are `collection_scope`, active `vehicle_key`, `source`, `publish_generated_data`, `anomaly_policy`, and optional `operator_note`.

A full run snapshots prior health, writes baseline-aware anomaly schema v1, applies source health, builds combined F-350 buyer intelligence, then applies anomaly/retention/publication gates. A remote branch change during collection blocks publication.

A `single_pair` run validates one active governed source pair, uploads seven-day temporary evidence, and never publishes generated data. F-350 single-pair runs also include source-specific buyer intelligence; other vehicles do not receive F-350 outputs.

## Current execution flow

1. Reusable deterministic CI validates exact dependencies, compilation, registry/config state, and hostile tests.
2. Collection validates inputs and builds a registry-governed full or single-pair plan.
3. Direct adapters preserve request, page, raw object, rejection, parse-failure, and canonical evidence.
4. Identity/lifecycle updates only after healthy reconciled source execution and rolls back on failure.
5. Full runs build manual review, consolidated health, and baseline-aware anomaly evidence.
6. Source health passes before combined F-350 buyer intelligence is built.
7. Critical-anomaly policy and retention gates run.
8. Publication validates staged paths, writes/verifies the manifest, checks whitespace, confirms the remote ref is unchanged, and then pushes a governed data commit.

## Local validation

```bash
python dependency_lock.py --lock requirements.lock
python -m pip install --requirement requirements.lock
python -m pip check
python vehicle_registry.py validate
python vehicle_registry.py summary
python vehicle_registry.py active-runs
python -m unittest discover -s tests -v
python storage_retention.py verify --registry vehicle_registry.json
```

Run governed sources and then build current-run F-350 intelligence:

```bash
python autotrader_run.py --config config_f350.json --timeout-seconds 4500 --fail-on-unhealthy
python kijiji_run.py --config config_f350.json --timeout-seconds 4500 --fail-on-unhealthy
python f350_buyer_intelligence.py build --config config_f350.json --run-id <same-run-id> --overrides f350_owner_overrides.json
```

Legacy command names remain aliases into the governed runtimes. Never run `merge.py` to create a recommendation set.

## Repository map

```text
.github/workflows/ci.yml             reusable deterministic code CI
.github/workflows/generated-data.yml generated-data pull-request validation
.github/workflows/scrape.yml         schedule/manual governed collection
requirements.lock                    exact Python dependency lock
dependency_lock.py                   dependency-lock validation
workflow_control.py                  governed collection plan and smoke validation
workflow_anomalies.py                baseline-aware anomaly evidence
generated_data_publish.py            staged publication manifest and verification
generated_data_validation.py         generated-data pull-request integrity checks
autotrader_*.py                      direct AutoTrader adapter/runtime/evidence
kijiji_*.py                          direct Kijiji adapter/runtime/evidence
canonical_evidence.py                canonical stages and reconciliation
identity_lifecycle.py                identity, lifecycle, compact history, duplicate candidates
f350_buyer_intelligence.py           transparent F-350 investigation outputs
f350_owner_overrides.json            governed owner annotations and overrides
storage_retention.py                 archive bounds, deletion evidence, size and staged-path gates
phase1_reporting.py                  accepted plus identity evidence manual review and health
vehicle_registry.json/.py            operational scope and source plan
vehicle_config.py/config_*.json      governed criteria
trim_tiers.json                      legacy descriptive labels, not buyer authority
merge.py                             LEGACY / DISABLED merger and ranker
data/                                generated evidence, lifecycle, retention, status, review data
tests/                               fixtures, hostile tests, contracts
docs/                                repository authorities
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
- `AUDIT_07_STORAGE_RETENTION.md`
- `AUDIT_08_CI_WORKFLOW_HARDENING.md`
- `AUDIT_09_F350_BUYER_INTELLIGENCE.md`

## Change authority

All implementation changes use an `ai/*` branch and pull request. The repository owner reviews, merges, and deletes the branch. The approved roadmap controls package sequence.
