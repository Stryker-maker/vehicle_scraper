# Legacy and Interim Components

## Purpose

This document prevents old files, fields and behaviours from being mistaken for supported capability. Retention does not imply approval.

## Status classes

- **Disabled legacy** — retained for history; excluded from supported workflow
- **Historical output** — preserved older evidence; not refreshed or authoritative
- **Active legacy** — still executes but is scheduled for replacement
- **Interim safety control** — actively reduces harm while a defect remains
- **Runtime compatibility field** — generated temporarily for a legacy process; never approved authority

## Disabled legacy

### `merge.py`

Status: **disabled legacy**

The workflow never calls it. It must not produce recommendations because it treats listing IDs like possible VINs, uses broad duplicate tolerances, fills fields without an evidence model, sorts by disabled scores and writes ranked merged CSVs. Audit 06 decides final removal/reuse.

### Historical merged CSVs

Path: `data/<vehicle>/merged/*.csv`

Do not refresh, recommend from, graph as current market, or infer availability from these files. Retain until storage policy is approved. `RANKING_DISABLED.md` redirects to current manual review.

## Active legacy

### `scraper.py`

Status: **active legacy AutoTrader collector**

It still contains internal ranking/display, distance ambiguity, location mutation attempts, broad exceptions and fixed-page assumptions. Audit 02 governs its input; Audit 04 replaces/refactors source behaviour.

### `kijiji_scraper.py`

Status: **legacy Kijiji collector still executed**

Do not run directly for supported collection. Direct execution would restore untrusted geography, filtering, ranking and mutation. The workflow uses `phase1_kijiji_runner.py` until Audit 05.

### `trim_tiers.json`

Status: **active legacy configuration**

Substring tiers may support future description normalization but are not recommendation weights and may misclassify packages. Final role belongs to canonical schema/F-350 work.

## Interim safety and compatibility controls

### `phase1_kijiji_runner.py`

Status: **active interim safety control**

It patches exact source anchors and executes modified Kijiji code. It prevents known unsafe geography/ranking from reaching supported output but remains fragile and difficult to analyze. Do not generalize this pattern.

### Phase 1 manual-review transformation

Status: **active interim safety control**

It removes rank/score and quarantines Kijiji geography. It is presentation/evidence protection, not source repair.

### Governed config projection

Status: **active compatibility boundary**

Approved schema-v2 configs are validated and never passed to collectors. For each source run, `vehicle_config.py` creates a disposable flat compatibility config containing:

- source-selected `search_locations`
- legacy source make/model aliases
- effectively unbounded `max_results`
- fixed compatibility `ranking_weights`

`phase1_runtime.py` substitutes the temporary path, deletes it after execution and verifies approved bytes remain unchanged.

This resolves approved-config ambiguity and mutation authority. It does not remove flat-config assumptions or ranking code from the collectors; Audits 04–05 own that removal.

## Runtime compatibility fields

### `max_results`

Current rule:

- prohibited in approved configs
- generated only in temporary runtime projection
- always injected as effectively unbounded
- never interpreted as owner-approved output scope

### `ranking_weights`

Current rule:

- prohibited in approved configs
- generated only for legacy process compatibility
- excluded from supported manual-review logic
- never represents purchase priorities

### Flat source aliases and `search_locations`

Current rule:

- prohibited at approved config top level
- generated from `sources.autotrader` or `sources.kijiji`
- selected source location list is explicit
- temporary values are not repository authority

### Source `rank` and `score`

They may exist in source CSVs but are excluded from supported manual review and must not guide recommendations, graphs or shortlists.

### `weeks_tracked`, `price_last_week`, `price_change_week`

These remain legacy names for observation sequence, not guaranteed elapsed weeks. Audit 06 replaces their semantics.

## Paused vehicle data

F-150 and Tundra are not legacy merely because they are paused. Their governed criteria and historical records remain for Audit 11; no current data should change while disabled.

## Removal rule

A legacy component is removed only after replacement/abandonment is approved, historical evidence needs are assessed, tests/docs no longer depend on it and the owner approves deletion.
