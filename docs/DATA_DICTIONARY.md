# Data Dictionary

## Purpose

This document defines current repository fields and their evidence limits. Raw values, normalized values, source claims, inferred values, unknowns, rejected records, and parse failures are distinct.

## Registry and configuration

`vehicle_registry.json` schema version `2` is the operational authority for `profile`, ordered `vehicles`, `vehicle_key`, `config_path`, `enabled`, `purpose`, `priority`, `cadence`, `enabled_sources`, `analysis_profile`, and conditional `pause_reason`.

Every `config_*.json` uses schema version `2` and contains `vehicle_key`, human-facing `make` and `model`, shared `criteria`, `origin`, and separate `sources.autotrader` / `sources.kijiji` query settings. Approved configs prohibit legacy flat controls such as `max_results`, `ranking_weights`, one shared `search_locations`, and flat source aliases.

## Source fetched boundaries

The required equation is:

```text
fetched_records = accepted_records + rejected_records + parse_failures
```

| Source | `fetched_record_scope` | Meaning |
|---|---|---|
| AutoTrader | `autotrader_adapter_response_listing_objects` | Every listing object returned to the configured direct adapter queries |
| Kijiji | `legacy_collector_emitted_csv_rows` | Rows emitted by the legacy collector after its internal fetch/parse/filter path |

AutoTrader pagination completeness describes configured queries and locations, not complete national marketplace coverage. Kijiji source fetch completeness remains `not_proven_by_legacy_collector` until Audit 05.

## AutoTrader adapter evidence schema version 1

AutoTrader writes under `data/<vehicle>/adapter_evidence/autotrader/`:

| Artifact | Meaning |
|---|---|
| `requests_latest.jsonl` | One record per requested page, including `query_location`, `query_page`, `query_offset`, `request_url`, `attempts`, HTTP/error outcome, listing count, and `pagination_stop_reason` |
| `records_latest.jsonl` | One record per response listing object with `raw_payload`, `provenance`, `record_stage`, `parsed_row`, `rejection_reasons`, and `parse_failure_reasons` |
| `reconciliation_latest.json` | Page/request counts, pagination completeness, fetched/accepted/rejected/failure counts, and adapter equality result |

Adapter record stages are `accepted`, `rejected`, and `parse_failure`. Rejection examples include `duplicate_source_listing_identity`, `missing_source_listing_id`, `missing_listing_url`, `year_out_of_range`, `price_out_of_range`, `fuel_unknown`, `fuel_mismatch`, `engine_unknown`, `engine_mismatch`, `distance_unavailable`, and `distance_out_of_range`. Parse failures include `listing_payload_not_object`, `missing_vehicle_object`, `invalid_price`, and `invalid_year`.

## Canonical evidence schema version 1

Each source writes under `data/<vehicle>/evidence/<source>/`:

| Artifact | Meaning |
|---|---|
| `raw_latest.jsonl` | Exact source-boundary evidence and provenance |
| `normalized_latest.jsonl` | Successfully normalized records |
| `accepted_latest.jsonl` | Records eligible for supported manual review |
| `rejected_latest.jsonl` | Excluded records with `rejection_reasons` |
| `parse_failures_latest.jsonl` | Failed records with `parse_failure_reasons` |
| `reconciliation_latest.json` | Counts, fetched scope, completeness state, paths, and equality result |

### Record envelope fields

| Field | Meaning |
|---|---|
| `evidence_schema_version` | Canonical evidence schema; currently `1` |
| `record_stage` | `raw`, `normalized`, `accepted`, `rejected`, or `parse_failure` |
| `vehicle_key` | Governed vehicle key |
| `source` | `autotrader` or `kijiji` |
| `run_id` | Workflow or explicit local run ID |
| `source_record_index` | Zero-based position at the source boundary |
| `canonical_listing_id` | Stable source-scoped listing hash; not VIN or cross-source identity |
| `observation_id` | Run-specific observation hash |
| `source_listing_id` | Source-provided listing identifier claim |
| `source_listing_id_status` | `source_identifier_claim_not_vin` or `unknown` |
| `source_claim_status` | `unverified_source_claims` |
| `raw_record_ref` | Raw artifact selector |
| `normalized_record_ref` | Normalized artifact selector |
| `source_adapter_record_ref` | AutoTrader adapter record selector when available |
| `query_provenance` | AutoTrader location/page/offset/request URL evidence when available |
| `normalized` | Typed/null-safe values |
| `field_evidence` | Raw value, normalized value, source field, and evidence status |
| `quality_warnings` | Non-destructive warning codes |
| `rejection_reasons` | Machine-readable exclusion reasons |
| `parse_failure_reasons` | Machine-readable failure reasons |

### Null and unknown policy

Empty strings and common sentinels such as `Unknown`, `N/A`, `None`, `null`, and `unavailable` normalize to JSON `null`. Legacy mileage `999999` also normalizes to null. Raw evidence remains preserved.

### Evidence status vocabulary

Statuses include:

- `source_reported_unverified`
- `source_reported_or_configured_unverified`
- `source_reported_or_inferred_unverified`
- `source_text_claim_unverified`
- `source_identifier_claim_not_vin`
- `source_reported_not_independently_verified`
- `route_distance_from_source_reported_location`
- `straight_line_estimate_from_source_reported_location`
- `location_or_geocode_unavailable`
- `legacy_method_not_yet_disambiguated` for pre-Audit-04 AutoTrader evidence only
- `quarantined_unverified_search_origin`
- `disabled_due_to_unverified_location`
- `unverified_url_evidence`
- `unavailable`
- `unknown`

These labels describe evidence handling, not independent verification.

## Canonical normalized values

Normalized records may contain:

| Field | Meaning |
|---|---|
| `year` | Model year integer or null |
| `make` | Source/configured make or null |
| `model` | Source/configured model or null |
| `trim` | Source trim/title text or null |
| `trim_tier` | Legacy keyword tier or null; not ranking authority |
| `price_cad` | Asking price integer or null |
| `mileage_km` | Odometer integer or null |
| `engine` | Source-derived engine text or null |
| `fuel` | Source-derived/inferred fuel or null |
| `accident_claim` | Source-text claim or null |
| `dealer` | Source seller/dealer name or null |
| `seller_type_claim` | Source-derived seller category or null |
| `dealer_address` | AutoTrader source evidence or null; Kijiji quarantined |
| `location` | AutoTrader source location or null; Kijiji null |
| `distance_km` | Explicit AutoTrader distance value or null; Kijiji null |
| `distance_method` | Explicit route/geodesic/unavailable method or Kijiji disabled marker |
| `distance_evidence_status` | AutoTrader routed/geodesic/unavailable evidence status |
| `source_listing_id` | Source ID claim; not VIN |
| `url_region_hint` | Kijiji URL segment evidence or null |
| `url_region_status` | URL evidence label or null |
| `listing_url` | Listing URL or null |
| `source_name` | Source display text or fallback |
| `observation_count` | Stored prior observation count; not elapsed weeks |
| `first_observed_price_cad` | First stored price for current source ID |
| `previous_observation_price_cad` | Previous stored observation price |
| `change_from_previous_observation_cad` | Current minus previous observation |
| `change_from_first_observation_cad` | Current minus first observation |
| `source_price_history_text` | Source/compatibility history text |
| `legacy_trend_text` | Compatibility trend wording |
| `days_on_market_claim` | Source duration claim or null |

## Decision-safe manual-review CSV

The supported CSV is generated only from `accepted_latest.jsonl`. It excludes source `rank`, `score`, `weeks_tracked`, and `price_last_week`. Kijiji search origin appears only in `unverified_location_value`.

The complete field order is:

`evidence_schema_version`, `vehicle_key`, `source`, `canonical_listing_id`, `observation_id`, `source_listing_id`, `source_listing_id_status`, `source_claim_status`, `raw_record_ref`, `normalized_record_ref`, `ranking_status`, `review_status`, `collection_status`, `data_quality_status`, `quality_warnings`, `source_run_status`, `source_completed_at_utc`, `year`, `year_evidence_status`, `make`, `make_evidence_status`, `model`, `model_evidence_status`, `trim`, `trim_evidence_status`, `price_cad`, `price_evidence_status`, `mileage_km`, `mileage_evidence_status`, `engine`, `engine_evidence_status`, `fuel`, `fuel_evidence_status`, `accident_claim`, `accident_evidence_status`, `dealer`, `dealer_evidence_status`, `seller_type_claim`, `seller_type_evidence_status`, `dealer_address`, `dealer_address_evidence_status`, `location`, `location_evidence_status`, `unverified_location_value`, `distance_km`, `distance_evidence_status`, `distance_method`, `url_region_hint`, `url_region_evidence_status`, `listing_url`, `listing_url_evidence_status`, `observation_count`, `first_observed_price_cad`, `previous_observation_price_cad`, `change_from_previous_observation_cad`, `change_from_first_observation_cad`, `source_price_history_text`, `legacy_trend_text`, `days_on_market_claim`.

Control fields include `ranking_status`, `review_status`, `collection_status`, `data_quality_status`, `quality_warnings`, `source_run_status`, and `source_completed_at_utc`. `clean` does not mean verified or purchase-safe.

## Source status

Each enabled pair writes `data/<vehicle>/run_status/<source>_latest.json`.

### Shared canonical fields

- `canonical_evidence_schema_version`
- `fetched_record_scope`
- `source_fetch_completeness`
- `fetched_record_count`
- `normalized_record_count`
- `accepted_record_count`
- `rejected_record_count`
- `parse_failure_count`
- `evidence_reconciliation_status`
- `evidence_reconciliation_equation`
- `canonical_evidence_artifacts`
- `canonical_evidence_error`

### AutoTrader source status schema version 6

AutoTrader additionally records:

- `source_adapter_schema_version` = `1`
- `runtime_config_projection` = `direct_schema_v2`
- `pagination_complete`
- `page_request_count`
- `request_attempt_count`
- `successful_page_count`
- `failed_page_count`
- `source_adapter_artifacts`
- `legacy_source_ranking_disabled` = `true`
- `distance_evidence_contract` = `explicit_route_api_or_geodesic_or_unavailable`

### Kijiji source status schema version 5

Kijiji retains `runtime_config_projection: legacy_collector_v1`, config-isolation evidence, and disabled geography/ranking markers until Audit 05.

A source is healthy only when current, successful, fresh, minimally schema-valid, uncapped, config-isolated, reconciled, and non-empty. AutoTrader can report success only when pagination is complete and accepted/output counts match.

## Consolidated health schema version 5

Full runs write registry-derived totals for `expected_source_runs`, `healthy_source_runs`, `unhealthy_source_runs`, `source_runs_with_quality_warnings`, `fetched_record_count`, `accepted_record_count`, `rejected_record_count`, `parse_failure_count`, and `sources`.

## Remaining non-canonical areas

The repository still lacks VIN/cross-source physical identity, duplicate confidence, lifecycle, bounded retention, F-350 engine/idle-hour and configuration evidence, verified service/history/warranty, owner notes, and purpose-specific candidate classifications. These remain assigned to later audits and must not be inferred from unrelated fields.
