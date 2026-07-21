# Phase 1: Data Collection and Manual Review

Phase 1 keeps both AutoTrader and Kijiji collection enabled while preventing the current unsafe cross-source ranking from being presented as a recommendation.

## What changed

- Both source scrapers still run for every configured vehicle.
- The Phase 1 wrapper runs each collector against an isolated temporary configuration, so one source cannot change the approved search locations used by another source.
- The wrapper overrides the legacy `max_results` value with an effectively unbounded runtime value. Every listing that passes the source scraper's existing filters is retained, including result sets larger than 50 or 200 vehicles.
- Each collector has a 75-minute timeout. A timeout is recorded and the remaining collectors continue.
- Every source run writes structured collection and data-quality evidence under `data/<vehicle>/run_status/`.
- Same-day reruns keep one price-history observation per listing and do not create an artificial extra week.
- The old `merge.py` process is not called by the automated workflow.
- Fresh source results are copied into `data/<vehicle>/manual_review/<vehicle>_manual_review_latest.csv`.
- Manual-review files contain no `rank` or `score` column.
- Kijiji's current location and distance values are moved into clearly labelled `unverified_*` fields. The normal location and distance fields are blank until the real listing location can be extracted.
- Suspicious values, including URL/year conflicts and implausibly low mileage, are retained but marked in `quality_warnings`.
- Existing files under `data/<vehicle>/merged/` remain as historical records but are not refreshed. Each directory receives a `RANKING_DISABLED.md` warning.

## Workflow behaviour

Collector failures and timeouts do not stop the other collectors. The workflow completes all collection attempts, builds manual-review files from current successful sources, writes a consolidated health report, and commits collected evidence. The final health gate then marks the workflow failed only when an expected source run is unhealthy.

Data-quality warnings do not discard records or fail collection. A fully collected run with warnings is reported as `SUCCESS_WITH_WARNINGS`, which means the records are available but require manual verification.

## Files to use

Use:

- `data/<vehicle>/manual_review/<vehicle>_manual_review_latest.csv`
- `data/run_status/latest.md`
- `data/run_status/latest.json`

Do not use the historical merged CSV files as current ranked recommendations.

## Manual review guidance

Treat every listing as a candidate requiring direct verification. Confirm the listing page, actual location, current price, mileage, vehicle history, seller identity, and availability before making a purchasing decision. Review `quality_warnings`, `location_status`, and `distance_status` before relying on any inferred field.
