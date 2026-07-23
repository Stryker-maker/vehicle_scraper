# Legacy and Interim Components

## Purpose

This document prevents old files, fields, and behaviours from being mistaken for supported capability. Retention does not imply approval.

## Status classes

- **Disabled legacy** — retained only when historical value justifies it; excluded from supported workflow
- **Historical output** — older evidence; not current authority
- **Compatibility alias** — old entry point redirected into a supported path
- **Active supported adapter** — current governed source execution
- **Active retention control** — bounded generated-data and deletion-evidence management

## Disabled legacy

### `merge.py`

Status: **LEGACY / DISABLED**.

The workflow never calls it. It treated source listing IDs like possible VINs, applied broad duplicate tolerances, filled fields without current evidence authority, and ranked output. Audit 06 replaced identity/dedup semantics; Audit 07 removes active-vehicle historical merged CSVs through governed SHA-256 deletion evidence. The script remains only until owner-approved code removal is separately justified.

### Historical merged CSVs

Path: `data/<vehicle>/merged/*.csv`

They are not current recommendations, graph inputs, or availability evidence. For active vehicles, Audit 07 deletes them during a governed full retention pass. Paused F-150/Tundra files remain untouched until their later owner-approved package.

### Legacy source price history

Paths:

- `data/<vehicle>/price_history_autotrader.json`
- `data/<vehicle>/price_history_kijiji.json`

Supported runtimes do not read, migrate, or rewrite these files. Audit 07 deletes them for active vehicles with path, reason, size, SHA-256, run, and time evidence. Identity/lifecycle schema v2 is the supported history authority.

### Former Kijiji patcher

`phase1_kijiji_runner.py` has been removed. Its exact text replacement and `exec` strategy is not part of the repository or workflow.

## Compatibility aliases

### `scraper.py`

The former AutoTrader implementation is a compatibility alias into `autotrader_run.py`.

### `kijiji_scraper.py`

The former Kijiji implementation is a compatibility alias into `kijiji_run.py`.

Legacy command names therefore receive the same timeout, source-status, adapter-evidence, canonical-evidence, identity/lifecycle, config-isolation, and rollback controls as the workflow.

## Active supported source adapters

### AutoTrader

- `autotrader_adapter.py`
- `autotrader_distance.py`
- `autotrader_history.py`
- `autotrader_canonical.py`
- `autotrader_run.py`

AutoTrader reads schema-v2 config directly, preserves request/page and response-object evidence, paginates, retries, records duplicates/rejections/parse failures, emits no rank or score, and does not mutate config.

### Kijiji

- `kijiji_locations.py`
- `kijiji_adapter.py`
- `kijiji_history.py`
- `kijiji_canonical.py`
- `kijiji_run.py`

Kijiji reads schema-v2 config directly, validates explicit Cars & Trucks hubs, preserves JSON-LD objects and query/page provenance, records duplicates/rejections/parse failures, emits no rank or score, and never substitutes query origin for listing geography.

## Shared supported controls

### Canonical evidence

`canonical_evidence.py` preserves raw, normalized, accepted, rejected, parse-failure, and reconciliation artifacts.

### Identity and lifecycle

`identity_lifecycle.py` schema v2 owns source-ID/VIN separation, fingerprints, non-destructive duplicate candidates, lifecycle, actual elapsed time, compact price history, retired-state bounds, and state-deletion evidence.

### Evidence-backed manual review

`phase1_reporting.py` consumes accepted canonical evidence joined with current identity/lifecycle evidence. Accepted does not mean verified or recommended.

### Storage retention

`storage_retention.py` schema v1 owns timestamped archive limits, active-vehicle legacy-file deletion, file deletion ledgers, managed-size gates, and staged generated-data path validation.

## Remaining compatibility fields

### `max_results` and `ranking_weights`

They are prohibited in approved configs, unused by active adapters, and may appear only in historical compatibility utilities/tests.

### Source `rank` and `score`

Neither active adapter emits these. Canonical accepted evidence and supported manual review exclude both.

### `weeks_tracked`, `price_last_week`, `price_change_week`

These source CSV columns remain blank compatibility fields. Supported history uses actual observations and elapsed time in identity/lifecycle schema v2.

### Unknown sentinels

Raw artifacts may retain `Unknown`, `N/A`, or `999999`. Canonical normalization converts them to JSON null while preserving raw evidence.

### `trim_tiers.json`

Status: **active legacy descriptive configuration**. It is not recommendation authority. Audit 09 decides its F-350 role.

## Paused vehicle data

F-150 and Tundra are paused, not legacy. Their historical data is not modified by Audit 07 retention. Audit 11 controls any reintroduction or later cleanup.

## Removal rule

Remove a legacy component only after replacement or abandonment is approved, historical evidence needs are assessed, deletion evidence is defined where needed, tests and documents no longer depend on it, and the owner approves the change.
