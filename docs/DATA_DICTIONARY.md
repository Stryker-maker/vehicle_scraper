# Data Dictionary

## Purpose

This document defines the current meaning of repository fields and the limits of the evidence they represent. It describes present implementation semantics, including known defects that later audits must correct.

Blank, `Unknown`, `N/A`, sentinel values and source claims must not be treated as equivalent. Where current code does not preserve that distinction reliably, the limitation is stated explicitly.

## Registry fields

`vehicle_registry.json` is schema version 1.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | integer | Registry schema version accepted by `vehicle_registry.py` |
| `profile` | string | Human-readable operational profile name; currently `audit_active` |
| `vehicles` | array | Ordered vehicle entries |
| `vehicle_key` | string | Canonical repository key; must equal the referenced config's `vehicle_key` |
| `config_path` | string | Repository-relative config file path |
| `enabled` | boolean | Governs inclusion in collection, manual-review generation and health reporting |
| `purpose` | string | Machine-readable search purpose |
| `priority` | integer | Owner-approved relative priority; lower number is higher priority |
| `pause_reason` | string, optional | Reason a disabled vehicle is retained but not run |

Current registry validation guarantees unique vehicle keys, unique config paths, repository-contained paths, existing config files, matching config keys and at least one enabled vehicle.

## Vehicle configuration fields

The current `config_*.json` files are legacy collector configurations. Not every field is part of the desired final configuration model.

| Field | Meaning | Current caveat |
|---|---|---|
| `vehicle_key` | Canonical data-directory and registry key | Must match registry entry |
| `make` | Display make | Collector-specific make fields may differ |
| `model` | Display model | Parsing may normalize model text inconsistently |
| `autotrader_make` | AutoTrader query make slug/value | Source-specific legacy field |
| `autotrader_model` | AutoTrader query model slug/value | Source-specific legacy field |
| `kijiji_make` | Kijiji query/display make | Source-specific legacy field |
| `kijiji_model` | Kijiji query/display model | Source-specific legacy field |
| `min_year` | Minimum accepted parsed model year | Records with unknown year are rejected by current collectors |
| `max_year` | Maximum accepted parsed model year | F-350 currently includes broad market context, not only the preferred target |
| `max_price` | Maximum accepted parsed asking price in CAD | Does not represent total purchase cost |
| `fuel` | Required fuel substring | Depends on source parsing accuracy |
| `engine` | Required engine substring | Exact/substring behaviour can reject valid records when engine parsing is unknown |
| `home_city` | Human-readable origin | Used by legacy distance logic |
| `home_coords` | Latitude/longitude origin | Used by legacy distance logic |
| `max_distance_km` | Intended travel-distance boundary | Disabled for Kijiji; AutoTrader method remains ambiguous |
| `max_results` | Legacy display/output cap | Overridden to an effectively unbounded runtime value by Phase 1 |
| `ranking_weights` | Legacy rank weights | Not used by the supported manual-review output |
| `search_locations` | Source search origins | Shared legacy list; Kijiji search origin is not actual listing location |

Operational enablement must not be added to or inferred from vehicle configs; it belongs in the registry.

## Source CSV fields

The current source collectors may write the following fields. Source CSVs are internal collection artifacts and may include legacy fields not present in supported manual review.

| Field | Current meaning | Evidence and limitation |
|---|---|---|
| `rank` | Legacy source-order position | Not a supported recommendation; removed from manual review |
| `year` | Parsed model year | Source-derived; warning rules detect only some conflicts |
| `make` | Parsed or configured make | Not independently verified |
| `model` | Parsed or configured model | Formatting varies by source |
| `trim` | Parsed trim keyword or title-derived text | Keyword matching can be incomplete or misleading |
| `trim_tier` | Legacy numeric trim tier | Based on `trim_tiers.json`; not approved purchase ranking |
| `price` | Parsed asking price in CAD | Excludes taxes, fees, financing and negotiation |
| `price_history` | Source-page price-change wording or legacy label | May not represent complete listing history |
| `trend` | Legacy summary derived from stored observations | Observation count is currently described as weeks; this is not reliable elapsed time |
| `weeks_tracked` | Number of prior/current stored observations | Misnamed; not guaranteed to equal calendar weeks |
| `price_first_seen` | First stored price for current source listing ID | History can reset if listing ID changes |
| `price_last_week` | Previous stored observation price | Misnamed when runs are not weekly |
| `price_change_week` | Current price minus previous stored price | Previous observation may not be one week earlier |
| `price_change_total` | Current price minus first stored price | Applies only to the current source listing ID history |
| `mileage` | Parsed odometer in kilometres | `999999` may be used as a legacy unknown sentinel |
| `engine` | Parsed engine displacement/text | Can be `Unknown`; engine filtering may discard unknowns |
| `fuel` | Parsed/inferred fuel category | Keyword-derived and not independently verified |
| `accident_flag` | Keyword classification of listing text | Source-reported claim only; not a vehicle-history report |
| `days_on_market` | Source date/time text or `N/A` | Not normalized into a reliable lifecycle duration |
| `dealer` | Parsed seller/dealer name | May be `Unknown` |
| `seller_type` | Parsed/inferred `Dealer`, `Private` or `Unknown` | Kijiji inference may use page badges or wording |
| `dealer_address` | Parsed dealer address or legacy Kijiji search origin | Kijiji value is not actual seller address and is quarantined in manual review |
| `location` | Parsed AutoTrader location or legacy Kijiji search origin | Kijiji value is not actual listing location and is quarantined |
| `distance_km` | Legacy computed distance | Kijiji blank/disabled; AutoTrader route-versus-geodesic fallback is not fully exposed |
| `distance_method` | Legacy location source or disabled marker | `address`/`city_center` does not always identify route versus straight-line calculation |
| `listing_id` | Source-specific listing identifier | Not a VIN and not cross-source identity |
| `url_region_hint` | Region segment extracted from Kijiji URL | Unverified navigation evidence only |
| `url_region_status` | Status of URL-region hint | Currently `unverified_url_evidence` or `unavailable` |
| `url` | Direct source listing URL | Listing may later be unavailable or changed |
| `score` | Legacy numeric ranking score or blank | Not a supported recommendation; removed from manual review |
| `source` | Source display name | Normally `AutoTrader` or `Kijiji` |

## Supported manual-review fields

The supported manual-review CSV contains Phase 1 evidence fields followed by the non-rank source fields.

### Review and evidence fields

| Field | Current value or meaning |
|---|---|
| `ranking_status` | `DISABLED_MANUAL_REVIEW_REQUIRED`; confirms no supported automated ranking |
| `review_status` | `manual_review_required`, `location_verification_required`, or `data_quality_review_required` |
| `collection_status` | Source collection/execution status copied from current run evidence |
| `data_quality_status` | `clean` or `warnings_present` under the limited current warning rules |
| `quality_warnings` | Semicolon-separated current row-warning codes |
| `source_run_status` | Current source execution status |
| `source_completed_at_utc` | Source completion timestamp in UTC |
| `location_status` | Evidence label for location trust |
| `distance_status` | Evidence label for distance trust |
| `unverified_location_value` | Quarantined Kijiji search-origin location value |
| `unverified_distance_value` | Quarantined legacy distance value, when present |

### Current row-warning codes

| Warning | Meaning |
|---|---|
| `unverified_kijiji_location` | Every Kijiji row requires location verification |
| `url_year_conflicts_with_parsed_year` | One year found in URL conflicts with parsed year |
| `suspiciously_low_mileage` | Non-current vehicle has parsed mileage at or below 100 km |
| `year_unknown` | Parsed year is missing or non-positive |
| `mileage_unknown` | Mileage is missing or uses the legacy unknown sentinel |

A row marked `clean` means only that none of these limited rules fired. It does not mean the listing is verified, complete, correctly located, mechanically sound or suitable.

### Kijiji transformation

For Kijiji rows, manual-review generation currently:

- sets `review_status` to `location_verification_required`
- sets `location_status` to `unverified_search_origin_not_listing_location`
- sets `distance_status` to `disabled_due_to_unverified_location`
- copies source `location` into `unverified_location_value`
- clears `dealer_address`, `location` and `distance_km`
- sets `distance_method` to `disabled_unverified_location`

The URL-region hint remains visible but is not promoted to verified location.

## Per-source run-status JSON

Each enabled vehicle/source pair writes `data/<vehicle>/run_status/<source>_latest.json`.

### Identity and timing

| Field | Meaning |
|---|---|
| `schema_version` | Current source-status schema version, presently 3 |
| `run_id` | GitHub run ID or `local` |
| `vehicle_key` | Vehicle key from config |
| `source` | Lowercase source key |
| `config_path` | Approved repository config path |
| `command` | Original collector command before runtime config substitution |
| `started_at_utc` | Wrapper start time |
| `completed_at_utc` | Wrapper completion time |
| `timeout_seconds` | Applied timeout |

### Execution and failure

| Field | Meaning |
|---|---|
| `execution_status` | `success`, `degraded`, `failed`, or `timed_out` |
| `collection_status` | Currently mirrors execution status |
| `exit_code` | Collector process exit code or null after timeout |
| `timed_out` | Whether timeout occurred |
| `failure_reasons` | Machine-readable reasons such as `collector_timed_out`, `collector_command_failed`, `no_fresh_output`, `invalid_output_schema`, `empty_output`, or `approved_config_mutated` |
| `stdout_tail` | Final captured standard-output characters |
| `stderr_tail` | Final captured standard-error characters |

### Freshness and schema

| Field | Meaning |
|---|---|
| `expected_output` | Expected source latest-CSV path |
| `output_exists` | Whether a file exists after execution |
| `output_updated_this_run` | Whether file signature/timing indicates fresh output |
| `schema_valid` | Whether minimum required columns exist |
| `missing_columns` | Missing minimum columns |
| `validation_error` | File/schema read error, if any |
| `observed_file_row_count` | Rows physically observed in the file |
| `current_row_count` | Rows counted as fresh current output |
| `stale_row_count` | Preserved rows counted as stale, not current |
| `stale_output_available` | Whether stale output exists |

The minimum required columns are currently only `listing_id`, `url`, `source`, `price`, `mileage`, `location`, and `distance_km`. Minimum schema validity does not establish completeness or semantic correctness.

### Safety controls

| Field | Meaning |
|---|---|
| `configured_max_results` | Legacy config value before runtime override |
| `effective_max_results` | `unbounded` under Phase 1 |
| `row_cap_disabled` | Confirms Phase 1 cap override |
| `config_isolated` | Confirms approved config remained byte-for-byte unchanged |
| `distance_processing_disabled` | True for current Kijiji path |
| `distance_filter_disabled` | True for current Kijiji path |
| `legacy_source_ranking_disabled` | True for current Kijiji path; AutoTrader source ranking may still occur internally but is not used in manual review |
| `same_day_history_removed_before_run` | Same-date history observations removed before execution |
| `same_day_history_duplicates_removed_after_run` | Duplicate same-date observations removed after success |

### Quality summary

| Field | Meaning |
|---|---|
| `data_quality_status` | `clean`, `warnings_present`, `not_evaluated`, or `not_evaluated_stale_output` |
| `quality_warning_rows` | Number of rows with at least one current warning |
| `quality_warning_count` | Total warning occurrences |
| `quality_warning_summary` | Warning code to occurrence count |

## Consolidated run-health JSON

`data/run_status/latest.json` contains:

| Field | Meaning |
|---|---|
| `schema_version` | Consolidated health schema version, presently 3 |
| `run_id` | Active run ID |
| `generated_at_utc` | Report generation time |
| `overall_status` | `success`, `success_with_warnings`, or `degraded` |
| `expected_source_runs` | Two sources multiplied by enabled vehicle count |
| `healthy_source_runs` | Expected source entries meeting current-success contract |
| `unhealthy_source_runs` | Expected source entries failing that contract |
| `source_runs_with_quality_warnings` | Healthy or unhealthy source entries whose row analysis found warnings |
| `sources` | Per-vehicle/source summary entries |

## Not-yet-existent canonical fields

The current repository does not yet have approved canonical fields for:

- VIN and VIN evidence status
- total engine hours
- idle hours
- kilometres per engine hour
- idle-hour percentage
- cab configuration
- box length
- SRW/DRW
- four-wheel-drive evidence
- fleet/commercial evidence
- service-history evidence
- accident/title evidence source
- warranty status
- first-seen and last-seen timestamps
- consecutive missed runs
- reappeared/relisted status
- raw record payload
- normalized record ID
- rejection reasons
- parse-failure evidence
- manual owner notes
- manual candidate classification and override

These belong to later approved audit packages and must not be simulated using unrelated existing fields.