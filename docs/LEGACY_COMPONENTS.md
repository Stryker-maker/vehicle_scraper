# Legacy and Interim Components

## Purpose

This document prevents old files, fields, and behaviours from being mistaken for supported capability. Retention does not imply approval.

## Disabled legacy

### `merge.py`

Status: **disabled legacy**. The workflow never calls it. Its listing-ID/VIN assumptions, destructive duplicate logic, field filling, and ranking cannot influence supported output.

### Historical merged CSVs

`data/<vehicle>/merged/*.csv` are historical only. Do not refresh, recommend from, or infer current availability from them.

### Former Kijiji patcher

`phase1_kijiji_runner.py` has been removed. Runtime text replacement and `exec` are not supported.

## Compatibility aliases

- `scraper.py` redirects old AutoTrader commands into `autotrader_run.py`.
- `kijiji_scraper.py` redirects old Kijiji commands into `kijiji_run.py`.

Aliases receive the same source status, adapter/canonical evidence, identity/lifecycle, timeout, and config-isolation controls as the workflow.

## Active supported components

### Source adapters

AutoTrader: `autotrader_adapter.py`, `autotrader_distance.py`, `autotrader_history.py`, `autotrader_canonical.py`, `autotrader_run.py`.

Kijiji: `kijiji_locations.py`, `kijiji_adapter.py`, `kijiji_history.py`, `kijiji_canonical.py`, `kijiji_run.py`.

Both read schema-v2 config directly, preserve raw object/rejection/parse evidence, emit no rank/score, and cannot mutate approved config.

### Canonical evidence

`canonical_evidence.py` preserves raw, normalized, accepted, rejected, parse-failure, and reconciliation artifacts.

### Identity and lifecycle

`identity_lifecycle.py` is the supported identity/history state model. It keeps source IDs distinct from VIN, records explicit VIN evidence, tracks actual elapsed time and lifecycle, and creates non-destructive duplicate candidates.

### Manual review

`phase1_reporting.py` joins accepted canonical evidence one-to-one with current identity/lifecycle evidence. It fails closed on missing/mismatched identity artifacts.

## Historical price history

### `data/<vehicle>/price_history_autotrader.json`
### `data/<vehicle>/price_history_kijiji.json`

Status: **historical output**.

Active adapters do not read, migrate, deduplicate, or rewrite these files. Supported manual review does not use them. Their listing-ID-based observations and week-named semantics are not trusted lifecycle/history authority.

The source CSV compatibility fields `weeks_tracked`, `price_last_week`, `price_change_week`, `price_change_total`, `price_history`, and `trend` may remain in raw/source schemas for compatibility, but active writers leave history values blank and identify the retirement. Supported output exposes actual observation and elapsed-time fields from identity/lifecycle artifacts.

## Other compatibility fields

- `max_results` and `ranking_weights` are prohibited in approved configs and unused by active adapters.
- Source `rank` and `score` are not emitted by active adapters and are excluded from supported review.
- Unknown sentinels can remain in raw evidence but normalize to null.
- `trim_tiers.json` remains descriptive legacy configuration, not recommendation authority; Audit 09 decides its future role.

## Paused vehicle data

F-150 and Tundra are paused, not legacy. Their criteria and historical data remain for Audit 11, but no current source/evidence/lifecycle/review/status data is produced while disabled.

## Removal rule

Remove a legacy component only after replacement or abandonment is approved, historical evidence needs are assessed, tests/documents no longer depend on it, and the owner approves deletion.
