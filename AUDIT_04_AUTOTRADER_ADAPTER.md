# Audit 04 — AutoTrader Collector Audit and Refactor

## Status

Implementation is on `ai/audit-04-autotrader-adapter`. Pull-request checks and one narrow F-350 AutoTrader smoke run are required before owner merge.

## Purpose

Replace the legacy AutoTrader script with a directly testable source adapter that makes request, pagination, parsing, filtering, distance, and reconciliation behaviour visible without changing the approved vehicle criteria.

## Source boundary

Audit 04 moves AutoTrader's fetched boundary earlier than Audit 03:

```text
AutoTrader response listing objects
  = accepted records + rejected records + parse failures
```

`fetched_records` now means `autotrader_adapter_response_listing_objects` for AutoTrader. This proves accounting for every listing object returned to the configured queries. It does not claim that the configured search locations represent the entire marketplace.

## Implemented components

- `autotrader_adapter.py` — request construction, retry/backoff, pagination, raw payload accounting, parsing, criteria rejection, and adapter reconciliation
- `autotrader_distance.py` — explicit routed, geodesic, or unavailable distance evidence
- `autotrader_history.py` — unranked CSV output and compatibility price observations
- `autotrader_canonical.py` — adapter-record reconciliation into canonical evidence schema v1
- `autotrader_run.py` — timeout, history rollback, source status schema v6, config-isolation verification, and health enforcement
- `scraper.py` — compatibility shim into the governed runtime

## Request and pagination contract

Each configured AutoTrader location is requested with explicit:

- source make and model slugs
- configured fuel category when supported
- page size (`rcp`)
- page offset (`rcs`)
- query location
- direct request URL provenance

Pagination continues until a reported total is reached or a short page is observed. A repeated-page fingerprint, failed page, or maximum-page boundary is visible and marks pagination incomplete.

Retry/backoff applies to network failures and HTTP 429, 500, 502, 503, and 504 responses. Request attempts and page outcomes are preserved in `requests_latest.jsonl`.

## Record accounting

Every response listing object receives a stable source-record index and one adapter stage:

- `accepted`
- `rejected`
- `parse_failure`

Examples of explicit rejection reasons include duplicate source identity, missing ID or URL, year/price criteria, fuel/engine criteria, and distance unavailable/out of range. Parse failures preserve the raw payload and a machine-readable reason such as invalid price, invalid year, missing vehicle object, or non-object payload.

The adapter writes:

```text
data/<vehicle>/adapter_evidence/autotrader/requests_latest.jsonl
data/<vehicle>/adapter_evidence/autotrader/records_latest.jsonl
data/<vehicle>/adapter_evidence/autotrader/reconciliation_latest.json
```

The canonical layer then writes the Audit 03 raw, normalized, accepted, rejected, parse-failure, and reconciliation artifacts from the adapter records rather than reconstructing evidence only from accepted CSV rows.

## Distance evidence

AutoTrader distance methods are explicit:

- `route_api_address`
- `route_api_city_center`
- `geodesic_address`
- `geodesic_city_center`
- `unavailable`

The associated evidence status states whether the value is a routed distance, a straight-line estimate from source-reported geography, or unavailable. A geodesic fallback is never labelled as driving distance.

## Ranking and configuration rules

- No AutoTrader rank or score is produced.
- The adapter reads approved config schema v2 directly.
- No temporary flat projection is used for AutoTrader.
- The approved config is not mutated.
- AutoTrader search locations are not self-added or self-removed.
- Kijiji remains on its Audit 02/03 compatibility path until Audit 05.

## Source status schema v6

AutoTrader source status adds:

- `source_adapter_schema_version`
- `runtime_config_projection: direct_schema_v2`
- pagination completeness and page/request counts
- source-adapter artifact paths
- `legacy_source_ranking_disabled: true`
- explicit distance-evidence contract

A healthy AutoTrader run requires a successful command, fresh non-empty accepted CSV, valid minimum schema, adapter and canonical reconciliation, complete pagination for every configured query, at least one accepted record, matching accepted/output counts, and unchanged approved config bytes.

## Narrow live validation

Audit 04 uses a single-pair workflow run rather than another ten-source run:

```text
validation_mode: single_pair
vehicle_key: ford_f350
source: autotrader
commit_generated_data: false
```

The smoke run:

- executes only the governed F-350 AutoTrader pair
- fails immediately if its source status is unhealthy
- uploads the pair's status, latest CSV, adapter evidence, canonical evidence, and source plan
- does not build registry-wide reports
- does not commit generated data
- does not trigger a generated-data acknowledgement run

## Acceptance gate

Before merge, all of the following must be true:

- request-contract and two-page fixture tests pass
- retry/backoff tests pass
- every response listing object is accepted, rejected, or a parse failure
- duplicates are visible rather than silently discarded
- parse and exclusion reasons are machine-readable
- pagination is complete for the narrow live query
- distance methods and evidence statuses are truthful
- supported AutoTrader output has no `rank` or `score`
- approved config remains byte-for-byte unchanged
- source status schema v6 and adapter schema v1 are present
- adapter and canonical equations reconcile
- no Kijiji implementation, vehicle criteria, F-150, Tundra, or unrelated data path is changed

## Stop conditions

Stop and revise before merge if pagination cannot be demonstrated, a response object disappears from reconciliation, an exception silently drops a record, geodesic distance is represented as routed distance, the approved config changes, ranking reappears, or narrow validation needs a full ten-source run without a demonstrated cross-source reason.

## Non-scope

Audit 04 does not replace Kijiji, create VIN/cross-source identity, implement lifecycle state, define retention, add F-350 enrichment, create analytics/ranking, change vehicle criteria, or re-enable optional vehicles.
