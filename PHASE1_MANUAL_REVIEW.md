# Phase 1: Data Collection and Manual Review

Phase 1 keeps both AutoTrader and Kijiji collection enabled while preventing the current unsafe cross-source ranking from being presented as a recommendation.

## What changed

- Both source scrapers still run for every configured vehicle.
- Every source run writes a structured status file under `data/<vehicle>/run_status/`.
- A source is considered healthy only when it exits successfully and produces a fresh, non-empty CSV with the required columns.
- The old `merge.py` process is not called by the automated workflow.
- Fresh, healthy source results are copied into `data/<vehicle>/manual_review/<vehicle>_manual_review_latest.csv`.
- Manual-review files contain no `rank` or `score` column.
- Kijiji's current location and distance values are moved into clearly labelled `unverified_*` fields. The normal location and distance fields are blank until the real listing location can be extracted.
- Existing files under `data/<vehicle>/merged/` remain as historical records but are not refreshed. Each directory receives a `RANKING_DISABLED.md` warning.

## Workflow behaviour

Collector failures do not stop the other collectors. The workflow completes all collection attempts, builds manual-review files from healthy sources, writes a consolidated health report, and commits the collected evidence. The final health gate then marks the workflow failed when any expected source run was unhealthy.

This creates a visible red workflow result without discarding successful data from the same run.

## Files to use

Use:

- `data/<vehicle>/manual_review/<vehicle>_manual_review_latest.csv`
- `data/run_status/latest.md`
- `data/run_status/latest.json`

Do not use the historical merged CSV files as current ranked recommendations.

## Manual review guidance

Treat every listing as a candidate requiring direct verification. Confirm the listing page, actual location, current price, mileage, vehicle history, seller identity, and availability before making a purchasing decision.
