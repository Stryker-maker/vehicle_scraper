# Legacy and Interim Components

## Purpose

This document prevents old files, fields, and behaviours from being mistaken for supported capability. Retention does not imply approval.

## Status classes

- **Disabled legacy** — retained for history; excluded from supported workflow
- **Historical output** — preserved older evidence; not refreshed or authoritative
- **Active legacy** — still executes but is scheduled for replacement
- **Interim safety control** — actively reduces harm while a defect remains
- **Runtime compatibility field** — generated temporarily for a legacy process; never approved authority

## Disabled legacy

### `merge.py`

Status: **disabled legacy**

The workflow never calls it. It must not produce recommendations because it treats listing IDs like possible VINs, uses broad duplicate tolerances, fills fields without an approved identity/evidence model, sorts by disabled scores, and writes ranked merged CSVs. Audit 06 decides final removal/reuse.

### Historical merged CSVs

Path: `data/<vehicle>/merged/*.csv`

Do not refresh, recommend from, graph as current market, or infer availability from these files. Retain until storage policy is approved. `RANKING_DISABLED.md` redirects to current accepted-record manual review.

## Active legacy

### `scraper.py`

Status: **active legacy AutoTrader collector**

It still contains internal ranking/display, distance ambiguity, location mutation attempts, broad exceptions, and fixed-page assumptions. Audit 02 governs its input. Audit 03 reconciles only rows it emits. Audit 04 replaces/refactors source behaviour and moves the raw/fetch boundary into the adapter.

### `kijiji_scraper.py`

Status: **legacy Kijiji collector still executed**

Do not run directly for supported collection. Direct execution would restore untrusted geography, filtering, ranking, and mutation. The workflow uses `phase1_kijiji_runner.py` until Audit 05. Audit 03 preserves emitted rows but does not validate source geography or pre-CSV completeness.

### `trim_tiers.json`

Status: **active legacy configuration**

Substring tiers may support future descriptive normalization but are not recommendation weights and may misclassify packages. Final role belongs to source/F-350 work.

## Interim safety and compatibility controls

### `phase1_kijiji_runner.py`

Status: **active interim safety control**

It patches exact source anchors and executes modified Kijiji code. It prevents known unsafe geography/ranking from reaching supported output but remains fragile and difficult to analyze. Do not generalize this pattern.

### Canonical evidence boundary

Status: **active supported evidence control with a legacy upstream boundary**

`canonical_evidence.py` preserves and reconciles every row emitted by current collectors into raw, normalized, accepted, rejected, and parse-failure artifacts. This is a genuine supported evidence layer, but its `fetched_records` count is scoped to `legacy_collector_emitted_csv_rows`.

It does not prove what happened before CSV emission. Audits 04–05 must provide request/response/parser evidence inside the source adapters.

### Evidence-backed manual-review transformation

Status: **active supported presentation control**

`phase1_reporting.py` now consumes accepted canonical evidence rather than raw collector CSVs. It excludes rank/score, replaces misleading legacy history names with observation-based names, exposes evidence statuses, and quarantines Kijiji geography.

Accepted means structurally eligible for human review, not verified or recommended.

### Governed config projection

Status: **active compatibility boundary**

Approved schema-v2 configs are validated and never passed to collectors. For each source run, `vehicle_config.py` creates a disposable flat compatibility config containing source-selected locations, legacy aliases, effectively unbounded `max_results`, and fixed compatibility ranking weights.

This resolves approved-config ambiguity/mutation authority. It does not remove flat-config assumptions or ranking code from collectors; Audits 04–05 own that removal.

## Runtime compatibility and legacy fields

### `max_results`

- prohibited in approved configs
- generated only in temporary runtime projection
- injected as effectively unbounded
- never interpreted as owner-approved output scope

### `ranking_weights`

- prohibited in approved configs
- generated only for legacy process compatibility
- excluded from supported evidence/manual-review logic
- never represents purchase priorities

### Flat source aliases and `search_locations`

- prohibited at approved config top level
- generated from source-specific schema-v2 settings
- temporary values are not repository authority

### Source `rank` and `score`

They may exist in source CSVs and collector console output. They are absent from canonical normalized decision fields and supported manual review. They must not guide recommendations, graphs, or shortlists.

### `weeks_tracked`, `price_last_week`, `price_change_week`

These remain legacy source/history names. Canonical normalized/manual-review output exposes `observation_count`, `previous_observation_price_cad`, and `change_from_previous_observation_cad` instead. Audit 06 replaces the underlying lifecycle/history semantics.

### Legacy unknown sentinels

Strings such as `Unknown`/`N/A` and mileage sentinel `999999` may remain in raw source artifacts. Canonical normalization converts them to JSON null while preserving the exact raw value and evidence status.

## Paused vehicle data

F-150 and Tundra are not legacy merely because they are paused. Their governed criteria and historical records remain for Audit 11; no current source, evidence, review, or status data should change while disabled.

## Removal rule

A legacy component is removed only after replacement/abandonment is approved, historical evidence needs are assessed, tests/docs no longer depend on it, and the owner approves deletion.
