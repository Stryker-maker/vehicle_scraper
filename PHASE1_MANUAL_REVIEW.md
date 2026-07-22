# Phase 1: Data Collection and Manual Review

**Status:** active interim operating guidance during the repository audit.

For current architecture, field semantics, limitations and future package ownership, also read:

- `docs/REPOSITORY_BASELINE.md`
- `docs/ARCHITECTURE_AND_DATA_FLOW.md`
- `docs/DATA_DICTIONARY.md`
- `docs/LIMITATIONS_REGISTER.md`
- `docs/AUDIT_ROADMAP.md`
- `AUDIT_02_CONFIG_GOVERNANCE.md`

Phase 1 prevents unsafe cross-source ranking from being presented as a recommendation while preserving current collection and review evidence.

## What Phase 1 and Audit 02 control

- `vehicle_registry.json` is the authority for enabled vehicles, enabled sources, purpose, priority, cadence and analysis profile.
- Every referenced schema-v2 config is validated before collection.
- AutoTrader and Kijiji criteria are separately governed in each config.
- The workflow executes only the vehicle/source pairs emitted by `vehicle_registry.py active-runs`.
- Manual-review generation and health reporting use the same source plan.
- The runtime creates a temporary flat compatibility config for each legacy collector.
- The approved config is never passed to a collector and must remain byte-for-byte unchanged.
- The temporary projection injects an effectively unbounded result cap; approved configs contain no `max_results` or `ranking_weights`.
- Each collector has a 75-minute timeout; remaining attempts continue after a failure.
- Every source run writes structured collection and limited quality evidence under `data/<vehicle>/run_status/`.
- Same-day reruns retain one price-history observation per listing/date.
- `merge.py` is not called.
- Current successful source rows feed `data/<vehicle>/manual_review/<vehicle>_manual_review_latest.csv`.
- Manual-review files contain no `rank` or `score`.
- Kijiji collection bypasses geocoding, route calculation, geographic filtering, legacy source ranking and location-list mutation.
- Kijiji distance is blank/disabled; search origin remains only as unverified evidence.
- URL-region hints are navigation evidence, not verified location.
- Suspicious rows are retained with `quality_warnings`.
- Historical merged files are not refreshed and contain warning markers.

## What Phase 1 does not prove

Phase 1 does not prove marketplace completeness, parse completeness, rejection reasons, Kijiji geography, routed AutoTrader distance, verified source claims, cross-source vehicle identity, elapsed lifecycle, availability, mechanical condition, fair value or purchase suitability.

A source or row labelled `clean` has only passed the current limited warning rules.

## Active audit scope

Enabled vehicles:

- Ford F-350 — primary purchase research
- RAM 3500 — owned-vehicle value monitoring
- Subaru Forester — owned-vehicle value monitoring
- Honda Odyssey — family-friend purchase search
- Kia Carnival — family-friend purchase search

Ford F-150 and Toyota Tundra remain paused. Their history and governed criteria are retained, but no source run, current manual review, health expectation or generated-data update should occur while disabled.

Inspect governance with:

```bash
python vehicle_registry.py validate
python vehicle_registry.py summary
python vehicle_registry.py active-configs
python vehicle_registry.py active-runs
```

## Workflow behaviour

Collector failures and timeouts do not stop remaining attempts. The workflow completes the registry plan, builds review files from current successful enabled sources, writes health evidence, commits generated data and fails visibly when an expected source is unhealthy.

Data-quality warnings do not discard records or fail collection. `SUCCESS_WITH_WARNINGS` means all expected source runs were healthy under current execution rules but row evidence still requires manual review.

Health distinguishes current from stale rows. Generated-data follow-up receives acknowledgement only rather than rerunning collectors.

## Files to use

Use:

- `data/<vehicle>/manual_review/<vehicle>_manual_review_latest.csv`
- `data/run_status/latest.md`
- `data/run_status/latest.json`
- `data/<vehicle>/run_status/<source>_latest.json`

Do not use:

- historical merged CSVs as recommendations
- source `rank` or `score` as purchase guidance
- Kijiji search-origin values as verified listing location
- temporary runtime-config fields as approved project criteria

## Manual review guidance

Confirm the live listing, actual location, current price, mileage, identity, history, seller and availability. Review `quality_warnings`, `review_status`, `location_status`, `distance_status`, `url_region_hint`, `url_region_status`, `source_completed_at_utc`, `configuration_schema_version`, `runtime_config_projection` and `config_isolated`.

Phase 1 remains in force until source adapters and canonical evidence models replace these interim safeguards.
