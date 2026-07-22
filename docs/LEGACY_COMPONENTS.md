# Legacy and Interim Components

## Purpose

This document prevents old files, fields and behaviours from being mistaken for current supported capability. Retention does not imply approval for operational use.

## Status classes

- **Disabled legacy** — retained for audit history; must not be used in the supported workflow
- **Historical output** — preserved evidence from an older process; not refreshed or authoritative
- **Active legacy** — still executes, but contains behaviour scheduled for replacement or correction
- **Interim safety control** — actively reduces harm while an underlying legacy defect remains
- **Legacy compatibility field** — retained because current collectors expect it; not part of the approved final model

## Disabled legacy

### `merge.py`

Status: **disabled legacy**

The automated workflow does not call `merge.py`.

Do not use it to produce current recommendations because it:

- treats source-specific listing IDs as possible VIN matches
- uses broad year/price/mileage tolerances for duplicate matching
- fills cross-source fields without an approved evidence model
- sorts output using the disabled legacy score
- writes ranked merged CSV files

The file is retained only until identity, deduplication and lifecycle work in Audit 06 determines what evidence is reusable and what should be removed.

### Historical merged CSV files

Status: **historical output**

Path:

```text
data/<vehicle>/merged/*.csv
```

Rules:

- do not refresh
- do not use as current recommendations
- do not graph as the current market dataset
- do not infer present availability
- retain until storage and historical-data policy is approved

Each merged directory contains `RANKING_DISABLED.md`, which redirects to the supported manual-review file.

## Active legacy

### `scraper.py`

Status: **active legacy AutoTrader collector**

It is still the current AutoTrader fetch/parser implementation. Phase 1 wraps it with runtime controls but does not remove its internal:

- legacy ranking and display flow
- distance fallback ambiguity
- automatic search-location mutation attempt
- broad per-record exception handling
- fixed-page collection assumptions

Audit 04 will replace or refactor this collector behind directly testable source contracts.

### `kijiji_scraper.py`

Status: **legacy Kijiji collector still executed**

It must not be run directly for supported collection. Direct execution would re-enable untrusted geography, location-based filtering, ranking and location mutation.

The current workflow executes it only through `phase1_kijiji_runner.py`.

Audit 05 will replace this arrangement with an ordinary testable Kijiji adapter.

### `trim_tiers.json`

Status: **active legacy configuration**

The collectors use substring keyword tiers. These tiers may support future descriptive normalization, but they are not approved recommendation weights and may misclassify packages such as `FX4` or `Tremor` as trim hierarchy.

Its future role must be decided through canonical-schema and F-350 intelligence work.

## Interim safety controls

### `phase1_kijiji_runner.py`

Status: **active interim safety control**

It patches exact strings in `kijiji_scraper.py` at runtime and executes the modified source. It currently prevents known unsafe behaviour from reaching supported review output.

It is intentionally temporary because:

- exact formatting changes can break patch anchors
- the stored source file is not identical to the program that runs
- debugging and static analysis are harder
- unsafe legacy functions remain present

Do not generalize this pattern to other collectors.

### Phase 1 manual-review transformation

Status: **active interim safety control**

It removes rank/score from supported output and quarantines Kijiji geography. This is a presentation and evidence safeguard, not a source repair.

### Runtime config isolation

Status: **active interim safety control**

Collectors run against a temporary config with an overridden result cap. This prevents approved config mutation but does not validate or redesign the collector configuration model.

## Legacy compatibility fields

### `max_results`

Current rule:

- retained in vehicle configs
- overridden to an effectively unbounded value during wrapped collection
- must not be interpreted as a current output limit

Audit 02 decides whether it is removed, renamed or made source-specific.

### `ranking_weights`

Current rule:

- retained in configs for collector compatibility
- not used by the supported manual-review output
- does not represent approved purchase priorities

### Source `rank` and `score`

Current rule:

- may exist in collector source CSVs
- are excluded from supported manual-review CSVs
- must not be used for purchase recommendation, graph ordering or shortlist decisions

### `weeks_tracked`, `price_last_week`, `price_change_week`

Current rule:

- retained legacy field names
- reflect observation sequence, not guaranteed weekly elapsed time
- must not be presented as precise lifecycle duration

Audit 06 replaces these semantics.

## Paused vehicle data

F-150 and Tundra data are not legacy merely because collection is paused. Their existing records are historical while disabled and must remain unchanged until Audit 11 or an owner-approved retention package addresses them.

## Removal rule

A legacy component must not be deleted solely because it is unsafe or obsolete. Removal requires:

1. replacement responsibility is implemented or the capability is formally abandoned
2. historical evidence needs are assessed
3. tests and documentation no longer depend on it
4. repository-owner approval

Until then, the component remains clearly marked and outside supported use.