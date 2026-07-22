# Data Dictionary

## Purpose

This document defines current repository fields and the limits of the evidence they represent. Blank, `Unknown`, `N/A`, sentinel values and source claims must not be treated as equivalent.

## Registry schema version 2

`vehicle_registry.json` is the sole operational authority for vehicle and source execution.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | integer | Must equal `2` |
| `profile` | string | Operational profile name; currently `audit_active` |
| `vehicles` | array | Ordered vehicle entries |
| `vehicle_key` | string | Canonical repository key; must match the referenced config |
| `config_path` | string | Repository-relative governed config path |
| `enabled` | boolean | Includes or excludes the vehicle from collection, review generation and health reporting |
| `purpose` | enum string | `primary_purchase`, `owned_vehicle_value_monitoring`, `family_friend_purchase_search`, or `optional_curiosity` |
| `priority` | positive integer | Owner-approved relative priority; lower is higher |
| `cadence` | enum string | Approved cadence metadata: `weekly` or `manual` |
| `enabled_sources` | array | Ordered subset of `autotrader` and `kijiji`; drives collection and expected health entries |
| `analysis_profile` | enum string | Purpose-linked future output profile; validated but not yet used for ranking |
| `pause_reason` | string, conditional | Required when `enabled` is false; prohibited when enabled |

Validation rejects missing or unknown fields, duplicate vehicle keys, duplicate config paths, unsupported purposes/cadences/sources, inconsistent purpose/profile pairs, unsafe paths, missing configs, config key mismatches, paused entries without reasons and registries with no enabled vehicle.

Changing only `enabled` remains sufficient to pause or re-enable a vehicle because cadence and source selections remain stored with the entry.

## Vehicle configuration schema version 2

Every `config_*.json` file is an approved source-criteria document. Operational state does not belong here.

### Top-level fields

| Field | Meaning |
|---|---|
| `schema_version` | Must equal `2` |
| `vehicle_key` | Canonical registry/data key in lowercase snake case |
| `make` | Human-facing make |
| `model` | Human-facing model |
| `criteria` | Shared vehicle acceptance criteria |
| `origin` | Search origin and intended distance boundary |
| `sources` | Separate AutoTrader and Kijiji query settings |

### `criteria`

| Field | Meaning | Current caveat |
|---|---|---|
| `min_year` | Minimum accepted parsed model year | Unknown years may still be rejected by legacy collectors without rejection evidence |
| `max_year` | Maximum accepted parsed model year | F-350 remains broad market context, not only the preferred target year |
| `max_price_cad` | Maximum parsed asking price in CAD | Excludes taxes, fees and negotiation |
| `fuel` | Required fuel substring/category | Depends on source parsing accuracy |
| `engine` | Required engine substring; blank disables the engine criterion | Unknown parsing can still exclude otherwise relevant rows |

### `origin`

| Field | Meaning | Current caveat |
|---|---|---|
| `home_city` | Origin in `City, PROVINCE` form | Used by legacy distance logic |
| `home_coords` | `[latitude, longitude]` | Validated for numeric bounds |
| `max_distance_km` | Intended travel-distance boundary | Kijiji distance filtering remains disabled; AutoTrader method remains ambiguous |

### `sources.autotrader` and `sources.kijiji`

| Field | Meaning |
|---|---|
| `make` | Source-specific query make/slug |
| `model` | Source-specific query model/slug |
| `search_locations` | Ordered, non-empty, duplicate-free locations in `City, PROVINCE` form |

The two source location lists are independently governed even when currently identical. Changing one source no longer implicitly changes the other.

### Prohibited approved-config fields

Approved schema-v2 configs reject legacy flat fields including:

- `autotrader_make`
- `autotrader_model`
- `kijiji_make`
- `kijiji_model`
- shared `search_locations`
- `min_year`, `max_year`, `max_price`, `fuel`, `engine` at top level
- `home_city`, `home_coords`, `max_distance_km` at top level
- `max_results`
- `ranking_weights`

`vehicle_config.py` creates those values only in a temporary compatibility projection for the active legacy collector. The projection uses the selected source's location list, injects an effectively unbounded `max_results`, and supplies fixed compatibility ranking weights. Those weights do not govern supported manual-review output.

## Source CSV fields

Source CSVs are internal collection artifacts and may include legacy fields absent from supported manual review.

| Field | Current meaning | Evidence and limitation |
|---|---|---|
| `rank` | Legacy source-order position | Not a supported recommendation; removed from manual review |
| `year` | Parsed model year | Source-derived; warning rules detect only some conflicts |
| `make` | Parsed or configured make | Not independently verified |
| `model` | Parsed or configured model | Formatting varies by source |
| `trim` | Parsed trim keyword or title-derived text | Can be incomplete or misleading |
| `trim_tier` | Legacy numeric trim tier | Not approved purchase ranking |
| `price` | Parsed asking price in CAD | Excludes taxes, fees, financing and negotiation |
| `price_history` | Source wording or legacy price label | Not a complete listing lifecycle |
| `trend` | Legacy observation summary | Observation count is not reliable elapsed time |
| `weeks_tracked` | Stored observation count | Misnamed; not guaranteed calendar weeks |
| `price_first_seen` | First stored price for current source listing ID | Can reset when source ID changes |
| `price_last_week` | Previous stored observation price | Previous observation may not be one week earlier |
| `price_change_week` | Current minus previous stored price | Timing is not guaranteed weekly |
| `price_change_total` | Current minus first stored price | Applies only to current source ID history |
| `mileage` | Parsed odometer in kilometres | `999999` may be a legacy unknown sentinel |
| `engine` | Parsed engine text | Can be `Unknown` |
| `fuel` | Parsed/inferred fuel category | Not independently verified |
| `accident_flag` | Keyword classification | Not a vehicle-history report |
| `days_on_market` | Source date/time text or `N/A` | Not a normalized lifecycle duration |
| `dealer` | Parsed seller/dealer name | May be `Unknown` |
| `seller_type` | Parsed/inferred seller category | Not independently verified |
| `dealer_address` | Parsed dealer address or legacy Kijiji search origin | Kijiji value is quarantined |
| `location` | Parsed AutoTrader location or legacy Kijiji search origin | Kijiji value is not verified listing location |
| `distance_km` | Legacy computed distance | Kijiji blank/disabled; AutoTrader fallback not fully exposed |
| `distance_method` | Legacy location source or disabled marker | Does not always distinguish route from straight line |
| `listing_id` | Source-specific listing identifier | Not a VIN and not cross-source identity |
| `url_region_hint` | Kijiji URL region segment | Unverified navigation evidence only |
| `url_region_status` | Hint status | `unverified_url_evidence` or `unavailable` |
| `url` | Direct listing URL | May later change or disappear |
| `score` | Legacy numeric score or blank | Not supported guidance; removed from manual review |
| `source` | Source display name | Normally `AutoTrader` or `Kijiji` |

## Supported manual-review fields

The supported CSV contains Phase 1 evidence fields followed by non-rank source fields.

| Field | Current value or meaning |
|---|---|
| `ranking_status` | `DISABLED_MANUAL_REVIEW_REQUIRED` |
| `review_status` | `manual_review_required`, `location_verification_required`, or `data_quality_review_required` |
| `collection_status` | Current source collection status |
| `data_quality_status` | `clean` or `warnings_present` under limited current rules |
| `quality_warnings` | Semicolon-separated warning codes |
| `source_run_status` | Current source execution status |
| `source_completed_at_utc` | Source completion time |
| `location_status` | Location evidence label |
| `distance_status` | Distance evidence label |
| `unverified_location_value` | Quarantined Kijiji search origin |
| `unverified_distance_value` | Quarantined legacy distance value |
| `year` | Source year |
| `make` | Source/configured make |
| `model` | Source/configured model |
| `trim` | Source trim/title text |
| `trim_tier` | Legacy trim tier, not recommendation |
| `price` | Asking price |
| `price_history` | Legacy/source history wording |
| `trend` | Legacy observation summary |
| `weeks_tracked` | Observation count, not elapsed weeks |
| `price_first_seen` | First stored price |
| `price_last_week` | Previous stored price |
| `price_change_week` | Change from previous observation |
| `price_change_total` | Change from first observation |
| `mileage` | Parsed kilometres |
| `engine` | Parsed engine text |
| `fuel` | Parsed/inferred fuel |
| `accident_flag` | Source-text keyword claim |
| `days_on_market` | Source/legacy duration text |
| `dealer` | Seller/dealer name |
| `seller_type` | Seller category |
| `dealer_address` | AutoTrader address; blanked for Kijiji review rows |
| `location` | AutoTrader reported location; blanked for Kijiji review rows |
| `distance_km` | Legacy AutoTrader distance; blanked for Kijiji |
| `distance_method` | Legacy method label or Kijiji disabled marker |
| `listing_id` | Source listing ID |
| `url_region_hint` | Kijiji URL region hint |
| `url_region_status` | Hint evidence status |
| `url` | Direct listing URL |
| `source` | Source display name |

Current warning codes are `unverified_kijiji_location`, `url_year_conflicts_with_parsed_year`, `suspiciously_low_mileage`, `year_unknown`, and `mileage_unknown`. A row marked `clean` is not verified or purchase-safe.

For Kijiji rows, manual-review generation preserves the search origin only in `unverified_location_value`, clears location/address/distance fields and uses `disabled_unverified_location`.

## Per-source run-status JSON

Each enabled vehicle/source pair writes `data/<vehicle>/run_status/<source>_latest.json`.

| Field | Meaning |
|---|---|
| `schema_version` | Source-status schema version, presently `4` |
| `configuration_schema_version` | Approved config schema used, presently `2` |
| `runtime_config_projection` | `legacy_collector_v1` |
| `approved_config_contains_legacy_controls` | False for governed configs |
| `run_id` | GitHub run ID or `local` |
| `vehicle_key` | Governed vehicle key |
| `source` | Lowercase source key |
| `config_path` | Approved config path |
| `command` | Original collector command before substitution |
| `started_at_utc` | Wrapper start time |
| `completed_at_utc` | Wrapper completion time |
| `timeout_seconds` | Applied timeout |
| `execution_status` | `success`, `degraded`, `failed`, or `timed_out` |
| `collection_status` | Currently mirrors execution status |
| `exit_code` | Collector exit code or null after timeout |
| `timed_out` | Whether timeout occurred |
| `failure_reasons` | Machine-readable failure reasons |
| `stdout_tail` | Captured standard-output tail |
| `stderr_tail` | Captured standard-error tail |
| `expected_output` | Expected latest CSV path |
| `output_exists` | Whether output exists |
| `output_updated_this_run` | Freshness result |
| `schema_valid` | Minimum columns present |
| `missing_columns` | Missing minimum columns |
| `validation_error` | CSV read/schema error |
| `observed_file_row_count` | Physical rows observed |
| `current_row_count` | Fresh current rows |
| `stale_row_count` | Preserved stale rows |
| `stale_output_available` | Whether stale output exists |
| `configured_max_results` | Null; approved configs no longer contain this field |
| `effective_max_results` | `unbounded` |
| `row_cap_disabled` | Confirms runtime compatibility projection is uncapped |
| `config_isolated` | Approved config remained byte-for-byte unchanged |
| `distance_processing_disabled` | True for current Kijiji path |
| `distance_filter_disabled` | True for current Kijiji path |
| `legacy_source_ranking_disabled` | True for current Kijiji path |
| `same_day_history_removed_before_run` | Same-date observations removed before execution |
| `same_day_history_duplicates_removed_after_run` | Same-date duplicates removed after success |
| `data_quality_status` | `clean`, `warnings_present`, `not_evaluated`, or stale equivalent |
| `quality_warning_rows` | Rows with warnings |
| `quality_warning_count` | Warning occurrences |
| `quality_warning_summary` | Warning-code counts |

Minimum schema validity still does not establish completeness or semantic correctness.

## Consolidated run-health JSON

`data/run_status/latest.json` currently uses schema version `4`.

| Field | Meaning |
|---|---|
| `run_id` | Active run ID |
| `generated_at_utc` | Report generation time |
| `overall_status` | `success`, `success_with_warnings`, or `degraded` |
| `expected_source_runs` | Count of enabled registry source pairs, not a fixed two-per-vehicle assumption |
| `healthy_source_runs` | Expected pairs meeting current-success contract |
| `unhealthy_source_runs` | Expected pairs failing that contract |
| `source_runs_with_quality_warnings` | Source entries containing row warnings |
| `sources` | Per-vehicle/source summaries |

## Not-yet-existent canonical fields

The repository still lacks canonical VIN/evidence, engine and idle hours, cab/box/SRW/DRW, four-wheel-drive evidence, fleet/service/history/warranty evidence, listing lifecycle, raw payloads, normalized IDs, rejection reasons, parse-failure evidence, owner notes and candidate classification. These belong to later approved packages and must not be simulated from unrelated fields.
