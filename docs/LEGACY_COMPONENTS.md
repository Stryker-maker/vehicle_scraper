# Legacy and Interim Components

## Purpose

This document prevents old files, fields, and behaviours from being mistaken for supported capability. Retention does not imply approval.

## Status classes

- **Disabled legacy** — retained for history; excluded from supported workflow
- **Historical output** — preserved older evidence; not current authority
- **Compatibility alias** — old entry point redirected into the supported path
- **Active legacy** — still executes and awaits replacement
- **Interim safety control** — reduces harm while an upstream defect remains
- **Runtime compatibility field** — temporary input for a legacy process; never approved authority

## Disabled legacy

### `merge.py`

Status: **disabled legacy**

The workflow never calls it. It treats source listing IDs like possible VINs, uses broad duplicate tolerances, fills fields without an approved identity model, and ranks output. Audit 06 decides final removal or limited historical reuse.

### Historical merged CSVs

Path: `data/<vehicle>/merged/*.csv`

Do not refresh, recommend from, graph as current market, or infer current availability from these files. `RANKING_DISABLED.md` redirects users to accepted-record manual review.

## AutoTrader replacement state

### `scraper.py`

Status: **compatibility alias**

The legacy AutoTrader implementation has been removed from this file. Older commands are redirected into `autotrader_run.py`, preserving timeout, source status, canonical evidence, and config isolation.

### `autotrader_adapter.py`

Status: **active supported source adapter**

It directly reads schema-v2 config, preserves request/page and response-object evidence, paginates, retries, records duplicates/rejections/parse failures, emits no rank or score, and does not mutate config or locations.

### AutoTrader flat projection and ranking code

Status: **retired for AutoTrader**

AutoTrader no longer receives `max_results`, `ranking_weights`, flat source aliases, or a mutable shared location list. `runtime_config_projection` is `direct_schema_v2`.

## Kijiji active legacy

### `kijiji_scraper.py`

Status: **legacy Kijiji collector still executed**

Do not run it directly for supported collection. Direct execution would restore untrusted geography, distance filtering, ranking, and mutation behaviour.

### `phase1_kijiji_runner.py`

Status: **active interim safety control**

It patches exact source anchors and executes modified Kijiji code. It disables known unsafe geography, distance, ranking, and location mutation but remains fragile. Audit 05 replaces it.

### Governed Kijiji config projection

Status: **active compatibility boundary**

`vehicle_config.py` creates a disposable flat Kijiji projection containing source-selected locations, legacy aliases, effectively unbounded `max_results`, and compatibility `ranking_weights`. It is never approved authority. AutoTrader no longer uses this projection.

## Shared supported controls

### Canonical evidence

Status: **active supported evidence control**

`canonical_evidence.py` preserves raw, normalized, accepted, rejected, parse-failure, and reconciliation artifacts. AutoTrader now supplies response-object adapter evidence to this layer. Kijiji still supplies emitted CSV rows until Audit 05.

### Evidence-backed manual review

Status: **active supported presentation control**

`phase1_reporting.py` consumes accepted canonical evidence, excludes rank/score, uses observation-based history names, exposes evidence statuses, and quarantines Kijiji geography. Accepted does not mean verified or recommended.

## Remaining legacy fields

### `max_results` and `ranking_weights`

- prohibited in approved configs
- no longer used by AutoTrader
- generated only for the Kijiji legacy compatibility path
- never represent owner-approved ranking or result scope

### Source `rank` and `score`

AutoTrader no longer emits these. Kijiji legacy source artifacts may still contain them. Canonical accepted evidence and supported manual review exclude both.

### `weeks_tracked`, `price_last_week`, `price_change_week`

These remain compatibility source/history names. Supported output exposes `observation_count`, `previous_observation_price_cad`, and `change_from_previous_observation_cad`. Audit 06 replaces underlying lifecycle semantics.

### Unknown sentinels

Raw artifacts may retain `Unknown`, `N/A`, or `999999`. Canonical normalization converts these to JSON null while preserving raw evidence.

### `trim_tiers.json`

Status: **active legacy descriptive configuration**

Keyword tiers may support descriptive normalization but are not recommendation weights and can misclassify packages. Audit 09 decides their F-350 role.

## Paused vehicle data

F-150 and Tundra are paused, not legacy. Their criteria and historical data remain for Audit 11; no current source, evidence, review, or status data should change while disabled.

## Removal rule

Remove a legacy component only after replacement/abandonment is approved, historical evidence needs are assessed, tests/docs no longer depend on it, and the owner approves deletion.
