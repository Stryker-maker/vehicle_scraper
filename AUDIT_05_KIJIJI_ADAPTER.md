# Audit 05 — Kijiji Collector Replacement

## Status

Implementation is on `ai/audit-05-kijiji-adapter`. Pull-request checks and one narrow F-350 Kijiji smoke run are required before owner merge.

## Purpose

Replace the runtime-patched legacy Kijiji collector with a directly testable source adapter that preserves request, pagination, parser, rejection, and geography evidence without treating query origin as listing location.

## Source boundary

Audit 05 moves Kijiji's fetched boundary to the returned JSON-LD listing objects:

```text
kijiji_adapter_json_ld_listing_objects
  = accepted records + rejected records + parse failures
```

This proves accounting for every JSON-LD listing object returned to the configured validated hub queries. It does not claim marketplace-wide completeness.

## Validated query hubs

`kijiji_locations.py` schema version 1 contains the explicit Cars & Trucks hub registry validated on July 22, 2026:

- Edmonton Area — `1700202`
- Calgary — `1700199`
- Saskatoon — `1700197`
- Regina Area — `1700194`
- Kelowna — `1700228`
- Kamloops — `1700227`

Unsupported labels fail validation. There is no fallback to `l0`, no duplicate location ID, and no runtime location mutation.

## Implemented components

- `kijiji_locations.py` — validated hub labels, slugs, IDs, and config validation
- `kijiji_adapter.py` — requests, retries, pagination, JSON-LD extraction, parsing, criteria handling, duplicate accounting, and adapter reconciliation
- `kijiji_history.py` — unranked accepted CSV output and compatibility observation history
- `kijiji_canonical.py` — adapter-to-canonical evidence verification and geography handling
- `kijiji_run.py` — bounded execution, history rollback, config isolation, canonical integration, and source status schema v7
- `kijiji_scraper.py` — compatibility alias into the governed runtime

`phase1_kijiji_runner.py` is removed. No text replacement or `exec` remains in the supported Kijiji path.

## Geography contract

The query hub is request provenance only. It never populates:

- `location`
- `dealer_address`
- `distance_km`

The adapter searches listing-specific structured source fields such as `address`, `contentLocation`, `location.address`, `offers.availableAtOrFrom`, and `seller.address`.

When listing-specific geography exists:

```text
location_evidence_status = source_reported_listing_specific_unverified
```

When it does not exist:

```text
location = null
dealer_address = null
location_evidence_status = unknown
```

URL region remains separate `unverified_url_evidence`. It is not treated as verified location.

## Distance contract

Kijiji distance processing and distance filtering remain disabled:

```text
distance_km = null
distance_method = disabled_listing_location_not_routed
distance_evidence_status = disabled_no_verified_route
```

Audit 05 does not invent a route from query origin, URL text, or an unverified listing location.

## Record accounting

Every response listing object receives a stable source-record index and one adapter stage:

- `accepted`
- `rejected`
- `parse_failure`

Duplicates remain visible as `duplicate_source_listing_identity`. Criteria exclusions and missing identity fields remain explicit rejections. Malformed objects and invalid year/price values remain parse failures with raw payload evidence.

The adapter writes:

```text
data/<vehicle>/adapter_evidence/kijiji/requests_latest.jsonl
data/<vehicle>/adapter_evidence/kijiji/records_latest.jsonl
data/<vehicle>/adapter_evidence/kijiji/reconciliation_latest.json
```

Canonical raw, normalized, accepted, rejected, parse-failure, and reconciliation artifacts remain under `data/<vehicle>/evidence/kijiji/`.

## Ranking and configuration rules

- No Kijiji rank or score is produced.
- Approved config schema v2 is read directly.
- No temporary flat projection is used for active Kijiji collection.
- Approved configs are not mutated.
- Search locations are not self-added or self-removed.
- F-150 and Tundra remain paused.

## Source status schema v7

Kijiji status records:

- adapter schema version
- location registry version
- direct schema-v2 execution
- pagination and request counts
- validated query-location count
- listing-specific and unknown geography counts
- adapter and canonical artifact paths
- disabled distance processing/filtering
- disabled legacy ranking
- config isolation
- reconciliation counts and result

## Narrow live validation

Audit 05 uses one source-pair smoke run:

```text
validation_mode: single_pair
vehicle_key: ford_f350
source: kijiji
commit_generated_data: false
```

The run must upload its status, accepted CSV, adapter evidence, canonical evidence, and exact source plan without building registry-wide reports or committing generated data.

## Acceptance gate

Before merge:

- fixture, retry, pagination, duplicate, parse-failure, canonical, and runtime tests pass
- all governed Kijiji location labels resolve to unique validated IDs
- no query uses `l0`
- no runtime patcher or `exec` path remains
- every returned listing object reconciles
- Toronto returned through Edmonton remains Toronto
- missing listing geography remains unknown
- query origin never becomes listing location/address/distance
- URL region remains separate evidence
- output contains no `rank` or `score`
- approved config remains unchanged
- source status schema v7 and adapter schema v1 are present
- the narrow F-350 Kijiji smoke run passes without a data commit

## Stop conditions

Stop and revise before merge if pagination cannot be demonstrated, a returned object disappears, an unsupported hub silently runs, Toronto or another out-of-region listing is represented as the query hub, query origin populates decision fields, parser exceptions silently drop records, ranking reappears, approved config changes, or narrow validation requires a full ten-source run without a demonstrated cross-source reason.

## Non-scope

Audit 05 does not create VIN/cross-source identity, lifecycle states, retention, F-350 enrichment, secondary analytics, recommendation ranking, AutoTrader changes, vehicle-criteria changes, or optional-vehicle reintroduction.
