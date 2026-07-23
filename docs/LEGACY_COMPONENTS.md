# Legacy and Interim Components

## Purpose

This document prevents old files, fields, workflows, and behaviours from being mistaken for supported capability. Retention does not imply approval.

## Status classes

- **Disabled legacy** — excluded from supported workflow
- **Historical output** — older evidence; not current authority
- **Compatibility alias** — old entry point redirected into a supported path
- **Active supported adapter** — current governed source execution
- **Active shared control** — current evidence, workflow, retention, anomaly, or publication control

## Disabled legacy

### `merge.py`

Status: **LEGACY / DISABLED**.

No workflow calls it. It treated source listing IDs like possible VINs, applied broad duplicate tolerances, filled fields without current evidence authority, and ranked output. Audit 06 replaced identity/dedup semantics; Audit 07 removes active-vehicle historical merged CSVs through governed SHA-256 deletion evidence.

### Historical merged CSVs

`data/<vehicle>/merged/*.csv` files are not current recommendations, graph inputs, or availability evidence. Active-vehicle files are deleted during governed retention. Paused F-150/Tundra files remain untouched until later owner-approved scope.

### Legacy source price history

`price_history_autotrader.json` and `price_history_kijiji.json` are not read, migrated, or rewritten by supported runtimes. Active-vehicle copies are deleted with path, reason, size, SHA-256, run, and time evidence. Identity/lifecycle schema v2 is the supported history authority.

### Former Kijiji patcher

`phase1_kijiji_runner.py` has been removed. Its text replacement and `exec` strategy is not part of the repository or workflow.

### Acknowledgement-only generated-data workflow

The former pull-request branch that merely acknowledged bot-generated data is removed. `data/**` pull requests now run `.github/workflows/generated-data.yml` and receive actual path, retention, status, health, anomaly, and publication-manifest validation.

### Moving dependency and action references

Direct unpinned installation commands such as `pip install requests beautifulsoup4 geopy`, moving Python versions, and action references such as `actions/checkout@v4` are not supported workflow patterns after Audit 08. Supported workflows use Python `3.11.13`, `requirements.lock`, and exact action commit SHAs.

## Compatibility aliases

### `scraper.py`

The former AutoTrader command is an alias into `autotrader_run.py`.

### `kijiji_scraper.py`

The former Kijiji command is an alias into `kijiji_run.py`.

Legacy command names therefore receive the same timeout, source-status, adapter/canonical evidence, identity/lifecycle, config-isolation, and rollback controls as the supported runtimes.

## Active supported source adapters

### AutoTrader

`autotrader_adapter.py`, `autotrader_distance.py`, `autotrader_history.py`, `autotrader_canonical.py`, and `autotrader_run.py` read schema-v2 config directly, preserve request/page and response-object evidence, paginate, retry, record duplicates/rejections/parse failures, emit no rank or score, and do not mutate config.

### Kijiji

`kijiji_locations.py`, `kijiji_adapter.py`, `kijiji_history.py`, `kijiji_canonical.py`, and `kijiji_run.py` read schema-v2 config directly, validate explicit Cars & Trucks hubs, preserve JSON-LD objects and query/page provenance, record duplicates/rejections/parse failures, emit no rank or score, and never substitute query origin for listing geography.

## Active shared controls

- `canonical_evidence.py` — raw, normalized, accepted, rejected, parse-failure, and reconciliation evidence
- `identity_lifecycle.py` schema v2 — source-ID/VIN separation, fingerprints, duplicate candidates, lifecycle, compact history, and bounded retired-state evidence
- `phase1_reporting.py` — accepted canonical evidence joined with current identity/lifecycle evidence
- `storage_retention.py` schema v1 — archive limits, deletion evidence, managed-size and staged-path gates
- `requirements.lock` / `dependency_lock.py` — exact Python environment
- `.github/workflows/ci.yml` — reusable deterministic code validation
- `.github/workflows/generated-data.yml` — generated-data pull-request validation
- `.github/workflows/scrape.yml` — schedule/manual collection only
- `workflow_control.py` — registry-governed plan and smoke validation
- `workflow_anomalies.py` schema v1 — baseline-aware anomaly evidence and policy
- `generated_data_publish.py` schema v1 — run/path publication manifest and staged verification
- `generated_data_validation.py` schema v1 — generated-data pull-request integrity checks

## Remaining compatibility fields

`max_results` and `ranking_weights` are prohibited in approved configs and unused by active adapters. Source `rank` and `score` are absent from supported adapters and review. `weeks_tracked`, `price_last_week`, and `price_change_week` remain blank source-CSV compatibility columns; supported history uses actual observations. Raw unknown sentinels may remain in raw evidence while canonical normalization preserves null-safe values.

`trim_tiers.json` remains active legacy descriptive configuration, not recommendation authority. Audit 09 decides its F-350 role.

## Paused vehicle data

F-150 and Tundra are paused, not legacy. Their historical data is not modified by retention, generated-data validation, collection, or publication until Audit 11 or another explicit owner-approved package.

## Removal rule

Remove a legacy component only after replacement or abandonment is approved, historical evidence needs are assessed, deletion evidence is defined where needed, tests and documents no longer depend on it, and the owner approves the change.
