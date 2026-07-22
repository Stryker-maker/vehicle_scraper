# Phase 1: Data Collection and Manual Review

**Status:** active interim operating guidance during the repository audit.

For current architecture, field semantics, limitations and future package ownership, also read:

- `docs/REPOSITORY_BASELINE.md`
- `docs/ARCHITECTURE_AND_DATA_FLOW.md`
- `docs/DATA_DICTIONARY.md`
- `docs/LIMITATIONS_REGISTER.md`
- `docs/AUDIT_ROADMAP.md`

Phase 1 keeps both AutoTrader and Kijiji collection enabled for every registry-enabled vehicle while preventing the current unsafe cross-source ranking from being presented as a recommendation.

## What Phase 1 controls

- Both source scrapers run for every enabled vehicle.
- The authoritative active and paused vehicle list is `vehicle_registry.json`.
- The wrapper runs each collector against an isolated temporary configuration, so one source cannot change the approved search locations used by another source.
- The wrapper overrides the legacy `max_results` value with an effectively unbounded runtime value. Every listing that passes the current source filters is retained, including result sets larger than 50 or 200 vehicles.
- Each collector has a 75-minute timeout. A timeout is recorded and the remaining collectors continue.
- Every source run writes structured collection and data-quality evidence under `data/<vehicle>/run_status/`.
- Same-day reruns keep one price-history observation per listing and do not create an artificial extra observation for that date.
- The old `merge.py` process is not called by the automated workflow.
- Fresh source results are copied into `data/<vehicle>/manual_review/<vehicle>_manual_review_latest.csv`.
- Manual-review files contain no `rank` or `score` column.
- Phase 1 Kijiji collection bypasses geocoding, route calculation, geographic filtering, legacy source ranking and automatic location-list mutation because the current Kijiji location value is only the search origin.
- Kijiji distance fields are blank and marked `disabled_unverified_location`. The search origin remains available only as unverified evidence.
- Kijiji URL region segments are exposed as `url_region_hint` with status `unverified_url_evidence`; they are navigation hints, not verified listing locations.
- Suspicious values, including URL/year conflicts and implausibly low mileage, are retained but marked in `quality_warnings`.
- Existing files under `data/<vehicle>/merged/` remain historical records and are not refreshed. Each directory receives a `RANKING_DISABLED.md` warning.

## What Phase 1 does not prove

Phase 1 does not prove:

- that every marketplace record was fetched
- that every fetched record parsed successfully
- why every omitted record was rejected
- that Kijiji geography is correct
- that AutoTrader distance is always routed driving distance
- that a source claim is verified
- that source listing IDs identify the same physical vehicle across sources
- that observation count equals elapsed weeks
- that a listing is available, mechanically sound, fairly priced or suitable to purchase

A source or row labelled `clean` has only passed the current limited warning rules.

## Audit 00 active scope

During the repository audit, the scheduled and manual workflow collects only these enabled vehicles:

- Ford F-350 — primary purchase research
- RAM 3500 — owned-vehicle value monitoring
- Subaru Forester — owned-vehicle value monitoring
- Honda Odyssey — family-friend purchase search
- Kia Carnival — family-friend purchase search

Ford F-150 and Toyota Tundra collection is paused. Their existing data is retained unchanged, but no collector, manual-review generation, health expectation or generated-data update should run for them while disabled in `vehicle_registry.json`.

Use the registry commands to inspect or validate active scope:

```bash
python vehicle_registry.py validate
python vehicle_registry.py summary
python vehicle_registry.py active-configs
```

## Workflow behaviour

Collector failures and timeouts do not stop the remaining collector attempts. The workflow completes all attempts, builds manual-review files from current successful sources, writes a consolidated health report, commits collected evidence and then fails visibly when an expected enabled source is unhealthy.

Data-quality warnings do not discard records or fail collection. A fully collected run with warnings is reported as `SUCCESS_WITH_WARNINGS`, meaning the records are available but require manual verification.

Health reports distinguish `Current rows` from `Stale rows`. A stale file is preserved but never counted as current output and is labelled `not_evaluated_stale_output`.

A generated-data commit receives a lightweight successful acknowledgement check instead of rerunning collectors. Normal code and workflow changes run the full structured test suite.

## Files to use

Use:

- `data/<vehicle>/manual_review/<vehicle>_manual_review_latest.csv`
- `data/run_status/latest.md`
- `data/run_status/latest.json`
- `data/<vehicle>/run_status/<source>_latest.json` when source-level evidence is needed

Do not use:

- historical merged CSV files as current ranked recommendations
- source `rank` or `score` as purchase guidance
- Kijiji search-origin values as verified listing location

## Manual review guidance

Treat every listing as a candidate requiring direct verification. Confirm the live listing page, actual location, current price, mileage, vehicle identity, vehicle history, seller identity and availability before relying on it.

Review these evidence fields first:

- `quality_warnings`
- `review_status`
- `location_status`
- `distance_status`
- `url_region_hint`
- `url_region_status`
- `source_completed_at_utc`

Phase 1 remains in force until later audit packages replace its temporary safeguards with trustworthy source adapters and canonical evidence models.