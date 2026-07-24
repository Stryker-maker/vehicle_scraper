# Legacy and Interim Components

## Purpose

This document prevents old files, fields, workflows, and behaviours from being mistaken for supported capability. Retention does not imply approval.

## Status classes

- **Disabled legacy** — excluded from supported workflow
- **Historical output** — older evidence; not current authority
- **Compatibility alias** — old entry point redirected into a supported path
- **Active supported adapter** — current governed source execution
- **Active shared control** — current evidence, workflow, analysis, retention, or publication control

## Disabled legacy

### `merge.py`

Status: **LEGACY / DISABLED**.

No workflow calls it. It conflated listing IDs with possible VINs, applied broad duplicate tolerances, filled fields without current evidence authority, and ranked output. No F-350 or secondary-purpose output reuses its merge, ranking, weighting, or recommendation logic.

### Historical merged CSVs

`data/<vehicle>/merged/*.csv` files are not current recommendations, value-monitor inputs, family-candidate inputs, graph authority, or availability evidence.

### Legacy source price history

`price_history_autotrader.json` and `price_history_kijiji.json` are not read by supported runtimes or purpose outputs. Identity/lifecycle schema v2 is the supported observation authority.

### Historical review and analysis files

Older manual-review, buyer, or purpose-output files may describe their own historical runs but are not current analysis inputs. Current purpose output requires matching source status, canonical, raw adapter, identity, and governed input evidence from one run.

### Former Kijiji patcher

`phase1_kijiji_runner.py` has been removed. Runtime text replacement and `exec` are unsupported.

### Acknowledgement-only generated-data workflow

The former acknowledgement-only path is removed. `data/**` pull requests receive actual integrity validation, including F-350 and secondary-purpose artifact validation when those paths change.

### Moving dependencies and actions

Unpinned package installs, moving Python versions, and moving action tags are unsupported. Workflows use Python `3.11.13`, `requirements.lock`, and exact action SHAs.

## Compatibility aliases

- `scraper.py` redirects to `autotrader_run.py`.
- `kijiji_scraper.py` redirects to `kijiji_run.py`.

These aliases receive the same governed runtime controls.

## Active supported adapters

Direct AutoTrader and Kijiji modules read schema-v2 config, preserve request/page/object evidence, record duplicates/rejections/parse failures, emit no rank/score, and do not mutate approved config. Kijiji never substitutes query origin for listing geography.

## Active shared controls

- `canonical_evidence.py` — canonical stages and reconciliation
- `identity_lifecycle.py` v2 — identity, lifecycle, compact history, duplicate candidates
- `phase1_reporting.py` — current general review and health
- `f350_buyer_intelligence.py` / validator — F-350 investigation
- `f350_owner_overrides.json` v1 — F-350 owner review input
- `purpose_inputs.json` v1 — secondary owner/friend interpretation input
- `purpose_outputs.py` / validator v1 — owned-value and family-candidate outputs
- `storage_retention.py` v1 — archive, deletion, size, and staged-path controls
- exact CI, generated-data validation, collection, anomaly, manifest, and publication controls

## Non-authoritative historical context

### RAM historical odometer statement

“Just over 400,000 km” is preserved only as `owner_reported_historical_unverified` context. It is not current odometer, current valuation input, or a replacement for an owner update.

### Missing Forester profile

Absence of Forester subject details is not permission to infer them from listings, config ranges, or another vehicle. Output remains `subject_profile_incomplete` until owner input exists.

### Missing family-friend requirements

Operational Odyssey/Carnival config criteria are broad collection boundaries, not personalized friend preferences. Until explicit friend input exists, listings remain `candidate_pending_requirements` rather than recommendations.

### Historical “faster sale” language

No current repository evidence contains transaction prices, sale dates, or sale probability. An observed lower asking band must not be called a verified faster-sale range.

## Remaining compatibility fields and descriptive configuration

`max_results` and `ranking_weights` are prohibited in approved configs. Source `rank` and `score` are absent from supported outputs. Legacy week columns remain blank compatibility fields; supported history uses actual observations.

`trim_tiers.json` remains active legacy descriptive configuration. Its tiers mix trims and packages and are not purchase, comparability, or candidate authority. F-350 and secondary-purpose outputs do not use it for classifications.

## Paused vehicle data

F-150 and Tundra are paused, not legacy. Their historical data is not modified by collection, analysis, retention deletion, generated-data validation, or publication until Audit 11 or explicit owner approval.

## Removal rule

Remove legacy material only after replacement/abandonment approval, historical-evidence review, deletion controls where needed, test/document updates, and owner approval.
