# Legacy and Interim Components

## Purpose

This document prevents old files, fields, and behaviours from being mistaken for supported capability. Retention does not imply approval.

## Status classes

- **Disabled legacy** — retained for history; excluded from supported workflow
- **Historical output** — preserved older evidence; not current authority
- **Compatibility alias** — old entry point redirected into a supported path
- **Active supported adapter** — current governed source execution
- **Runtime compatibility field** — temporary support for historical utilities; never approved authority

## Disabled legacy

### `merge.py`

Status: **disabled legacy**

The workflow never calls it. It treats source listing IDs like possible VINs, uses broad duplicate tolerances, fills fields without an approved identity model, and ranks output. Audit 06 decides final removal or limited historical reuse.

### Historical merged CSVs

Path: `data/<vehicle>/merged/*.csv`

Do not refresh, recommend from, graph as current market, or infer current availability from these files. `RANKING_DISABLED.md` redirects users to accepted-record manual review.

### Former Kijiji patcher

`phase1_kijiji_runner.py` has been removed. Its exact text replacement and `exec` strategy is no longer part of the repository or workflow.

The former multi-function Kijiji implementation has also been removed from `kijiji_scraper.py`; its unsafe search-origin geography, distance filtering, ranking, broad exception swallowing, location mutation, and silent duplicate loss no longer execute.

## Compatibility aliases

### `scraper.py`

The former AutoTrader implementation is replaced by a compatibility alias into `autotrader_run.py`.

### `kijiji_scraper.py`

The former Kijiji implementation is replaced by a compatibility alias into `kijiji_run.py`. Older manual commands therefore receive the same timeout, source-status, adapter-evidence, canonical-evidence, and config-isolation controls as the workflow.

## Active supported source adapters

### AutoTrader

- `autotrader_adapter.py`
- `autotrader_distance.py`
- `autotrader_history.py`
- `autotrader_canonical.py`
- `autotrader_run.py`

AutoTrader reads schema-v2 config directly, preserves request/page and response-object evidence, paginates, retries, records duplicates/rejections/parse failures, emits no rank or score, and does not mutate config or locations.

### Kijiji

- `kijiji_locations.py`
- `kijiji_adapter.py`
- `kijiji_history.py`
- `kijiji_canonical.py`
- `kijiji_run.py`

Kijiji reads schema-v2 config directly, validates explicit Cars & Trucks hubs, preserves JSON-LD listing objects and query/page provenance, records duplicates/rejections/parse failures, emits no rank or score, and does not mutate config or locations. Query origin never becomes listing geography.

## Shared supported controls

### Canonical evidence

`canonical_evidence.py` preserves raw, normalized, accepted, rejected, parse-failure, and reconciliation artifacts. Both direct adapters now supply source-boundary records and adapter evidence to this layer.

### Evidence-backed manual review

`phase1_reporting.py` consumes accepted canonical evidence, excludes rank/score, uses observation-based history names, and exposes evidence statuses. Accepted does not mean verified or recommended.

## Remaining compatibility fields

### `max_results` and `ranking_weights`

- prohibited in approved configs
- not used by either active source adapter
- may still be produced by `legacy_runtime_config()` for historical utilities/tests
- never represent owner-approved ranking or result scope

### Source `rank` and `score`

Neither active source adapter emits these. Canonical accepted evidence and supported manual review exclude both.

### `weeks_tracked`, `price_last_week`, `price_change_week`

These remain compatibility source/history names. Supported output exposes `observation_count`, `previous_observation_price_cad`, and `change_from_previous_observation_cad`. Audit 06 replaces underlying lifecycle semantics.

### Unknown sentinels

Raw artifacts may retain `Unknown`, `N/A`, or `999999`. Canonical normalization converts these to JSON null while preserving raw evidence.

### `trim_tiers.json`

Status: **active legacy descriptive configuration**

Keyword tiers may support descriptive normalization but are not recommendation weights and can misclassify packages. Audit 09 decides their F-350 role.

## Paused vehicle data

F-150 and Tundra are paused, not legacy. Their criteria and historical data remain for Audit 11. Audit 05 normalizes their dormant Kijiji hub labels only; no current source, evidence, review, or status data is produced while disabled.

## Removal rule

Remove a legacy component only after replacement or abandonment is approved, historical evidence needs are assessed, tests and documents no longer depend on it, and the owner approves deletion.
