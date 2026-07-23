# Data Dictionary

## Purpose

This document defines current supported fields and their evidence limits. Source claims, normalized values, identity fingerprints, VIN claims, lifecycle inferences, F-350 buyer-intelligence claims/calculations, owner annotations, compacted history, duplicate candidates, deletion evidence, anomaly evidence, publication evidence, rejections, and parse failures are distinct.

## Registry and configuration

`vehicle_registry.json` schema version `2` controls enabled/paused vehicles and sources. Every `config_*.json` uses schema version `2` with shared criteria, origin, and separate AutoTrader/Kijiji query settings.

`f350_owner_overrides.json` uses owner-override schema version `1` and applies only to `ford_f350` canonical listing IDs.

## Source fetched boundaries

```text
fetched_records = accepted_records + rejected_records + parse_failures
```

| Source | `fetched_record_scope` | Meaning |
|---|---|---|
| AutoTrader | `autotrader_adapter_response_listing_objects` | Every listing object returned to configured direct-adapter queries |
| Kijiji | `kijiji_adapter_json_ld_listing_objects` | Every JSON-LD listing object returned to configured validated hub queries |

Neither boundary proves full marketplace coverage.

## Adapter and canonical evidence

Both adapters use schema version `1` and write request, record, and reconciliation evidence. Canonical evidence schema version `1` writes raw, normalized, accepted, rejected, parse-failure, and reconciliation artifacts.

Key canonical fields include `canonical_listing_id`, `observation_id`, `source_listing_id`, `source_listing_id_status`, `source_adapter_record_ref`, `query_provenance`, `field_evidence`, `rejection_reasons`, and `parse_failure_reasons`.

`source_listing_id_status` is `source_identifier_claim_not_vin`. Evidence statuses include `straight_line_estimate_from_source_reported_location`, `source_reported_listing_specific_unverified`, `query_origin_never_location`, `unverified_url_evidence`, `unknown`, and `unavailable`.

## Identity and lifecycle schema version 2

Per-source identity artifacts are under `data/<vehicle>/identity_lifecycle/<source>/`.

Identity fields include `source_listing_id_status`, `vin_claim`, `vin_evidence_status`, `vin_raw_claims`, `identity_fingerprint_strict`, `identity_fingerprint_loose`, and `identity_fingerprint_components`. Fingerprints are comparison evidence, not merge authority.

Lifecycle fields include `lifecycle_state`, `lifecycle_state_reason`, first/last/evaluation timestamps, elapsed seconds/days, `missing_run_count`, `reappearance_count`, and `observation_count`. States are `active`, `missing`, `reappeared`, and `retired`. Retirement requires three consecutive successful-run misses and fourteen elapsed days; it is not a sold claim.

Price fields include `price_observation_count`, `retained_price_observation_count`, `compacted_price_observation_count`, `price_observation_retention_limit`, `price_observation_compaction_digest_sha256`, `price_observations_compacted_through_at_utc`, `first_observed_price_cad`, `first_price_observed_at_utc`, `previous_observation_price_cad`, `current_price_cad`, `minimum_observed_price_cad`, `maximum_observed_price_cad`, `change_from_previous_observation_cad`, and `change_from_first_observation_cad`.

The newest thirteen raw observations are retained. Compacted counts and a chained digest preserve accounting evidence but cannot reconstruct removed raw observations.

Retired-state retention fields include `storage_retention_policy`, `state_retention_ledger`, `deleted_retired_listing_count_total`, `deleted_retired_listing_bytes_total`, `deletion_chain_sha256`, `recent_deletions`, `retired_listings_pruned_this_run`, `retired_listing_deletion_count_total`, and `retired_listing_deletion_chain_sha256`. At most 500 retired listings are retained per source and no retained tombstone may exceed 365 days since last successful observation.

## Duplicate candidates

`duplicate_candidates_latest.jsonl` contains `candidate_id`, `confidence`, `confidence_score`, `reasons`, `decision_status`, `left`, and `right`. `decision_status` is always `candidate_only_not_merged`; canonical records remain separate.

## F-350 buyer-intelligence schema version 1

Buyer artifacts are:

```text
data/ford_f350/buyer_intelligence/investigation_latest.jsonl
data/ford_f350/buyer_intelligence/investigation_latest.csv
data/ford_f350/buyer_intelligence/seller_questions_latest.jsonl
data/ford_f350/buyer_intelligence/market_summary_latest.json
data/ford_f350/buyer_intelligence/market_summary_latest.md
```

The builder requires current source status schema `8`, canonical accepted schema `1`, adapter raw evidence schema `1`, identity current schema `2`, and owner overrides schema `1`. It rejects stale, unhealthy, wrong-run, wrong-schema, count-mismatched, discontinuous, or disconnected evidence.

### Investigation identity and scope

- `buyer_intelligence_schema_version` — currently `1`
- `run_id` — current source run ID
- `scope` — `single_source` or `full_sources`
- `vehicle_key` — always `ford_f350`
- `source` — `autotrader` or `kijiji`
- `canonical_listing_id` — source-scoped canonical listing claim
- `source_listing_id` — source identifier claim, not VIN
- `listing_url`
- `lifecycle_state`
- `vin_claim`
- `vin_evidence_status`
- `raw_record_ref`
- `source_adapter_record_ref`

### Configuration and history evidence

Each extracted claim has a `value`, `evidence_status`, and optional `matched_text`. Known extracted text uses `source_text_reported_unverified`; absent evidence uses `unknown`.

- `configuration_evidence.trim` — XL, XLT, Lariat, King Ranch, Platinum, or Limited claim
- `configuration_evidence.packages` — STX, FX4, or Tremor claims; separate from trim
- `configuration_evidence.cab_configuration` — `regular_cab`, `supercab`, or `crew_cab`
- `configuration_evidence.box_configuration` — `long_box_or_8ft_claim` or `short_box_or_6_75ft_claim`
- `configuration_evidence.rear_wheel_configuration` — `srw` or `drw`
- `configuration_evidence.drivetrain` — `4wd` or `2wd`
- `configuration_evidence.engine_hours`
- `configuration_evidence.idle_hours`
- `configuration_evidence.service_history` — `records_available_claim` or `records_not_available_claim`
- `configuration_evidence.accident_title` — canonical source/text-derived unverified claim
- `configuration_evidence.prior_use_claims` — possible one-owner, highway, towing, fleet, commercial, rental, oilfield, work-truck, or explicit no-fleet/commercial/rental-use claims
- `configuration_evidence.source_text_digest_sha256` — digest of the examined source-text projection; not source authenticity proof

`trim_tiers.json` and its tier numbers are not buyer-intelligence or purchase authority.

### Derived hour context

- `derived_hour_context.km_per_engine_hour` — mileage divided by total engine hours when both are present and engine hours are positive
- `derived_hour_context.idle_hour_percent` — idle hours divided by total engine hours ×100 when internally possible
- `derived_hour_context.warnings` — includes `idle_hours_exceed_engine_hours` when applicable
- `derived_hour_context.meaning` — `usage_context_only_not_condition_proof`

### Evidence completeness

- `evidence_completeness` — `complete`, `partial`, or `insufficient`
- `missing_investigation_fields` — missing evidence among `vin`, `cab_configuration`, `box_configuration`, `rear_wheel_configuration`, `drivetrain`, `engine_hours`, `idle_hours`, `service_history`, `accident_title`, and `prior_use`

Completeness measures evidence presence, not independent truth or vehicle condition.

### Model-year fit

- `year_fit` — `ideal_2023`, `early_2020s_target`, `broad_market_context`, or `unknown`

### Asking-price market context

- `market_context.cohort_basis` — exact year, year ±1, 2020–2023, or all current accepted F-350 claims
- `market_context.comparable_count`
- `market_context.price_q1_cad`
- `market_context.price_median_cad`
- `market_context.price_q3_cad`
- `market_context.price_position` — below, within, or above observed interquartile range; otherwise `insufficient_comparables`
- `market_context.price_difference_from_median_cad`
- `market_context.market_scope` — `configured_query_accepted_listing_claims_not_complete_market`

Quartiles describe current asking-price claims, not sale prices, appraisal, or complete-market truth.

### Mileage-adjusted asking-price projection

`market_context.mileage_adjusted_asking_price_projection` contains:

- `status` — `available`, `insufficient_comparables`, or `insufficient_mileage_variation`
- `sample_count`
- `projected_asking_price_cad`
- `slope_cad_per_10000_km`
- `intercept_cad`
- `r_squared`
- `meaning` — `asking_price_context_not_appraisal_or_future_value`

The calculation requires at least five valid price/mileage pairs and adequate mileage variation. It is descriptive ordinary least squares, not causal depreciation, appraisal, or future resale value.

### Owner-use mileage projection

`ownership_mileage_projection` contains:

- `annual_km_min` — `5000`
- `annual_km_max` — `8000`
- `projection_years` — `5`
- `projected_mileage_min_km`
- `projected_mileage_max_km`
- `meaning` — `owner_usage_scenario_not_odometer_or_value_guarantee`

### Computed classification

- `computed_classification` — `investigate_priority`, `investigate_with_evidence_gaps`, `investigate_price_concern`, `concern_review`, `market_context_only`, or `insufficient_evidence`
- `computed_classification_reasons` — visible reason codes
- `decision_contract` — `explainable_classification_not_rank_not_score_manual_override_preserves_source_evidence`

No buyer output contains purchase `rank` or `score`.

### Seller questions

`seller_questions_latest.jsonl` contains `canonical_listing_id`, `listing_url`, and a `questions` array. Each question has:

- `category`
- `priority`
- `question`
- `reason`

Questions are prompts driven by missing evidence or visible concerns. They are not defect findings or seller answers.

### Owner override schema version 1

`f350_owner_overrides.json` contains `schema_version`, `vehicle_key`, and `overrides` keyed by `canonical_listing_id`.

Supported override fields:

- `owner_disposition` — `unreviewed`, `contacted`, `inspection_planned`, `hold`, `pass`, or `purchased`
- `owner_note`
- `owner_tags`
- `classification_override` — `priority_investigate`, `investigate`, `hold`, `pass`, or `market_context_only`
- `override_reason` — required when `classification_override` is set

Generated output preserves `computed_classification`, `classification_override`, `override_reason`, `override_applied`, and `effective_classification`. Owner input cannot change canonical or raw evidence, market calculations, or computed reasons.

### Investigation CSV fields

The supported CSV field order is:

`buyer_intelligence_schema_version`, `run_id`, `scope`, `vehicle_key`, `source`, `canonical_listing_id`, `source_listing_id`, `listing_url`, `lifecycle_state`, `vin_claim`, `vin_evidence_status`, `year`, `year_fit`, `price_cad`, `mileage_km`, `distance_km`, `trim_claim`, `trim_evidence_status`, `package_claims`, `cab_configuration_claim`, `cab_configuration_evidence_status`, `box_configuration_claim`, `box_configuration_evidence_status`, `rear_wheel_configuration_claim`, `rear_wheel_configuration_evidence_status`, `drivetrain_claim`, `drivetrain_evidence_status`, `engine_hours_claim`, `engine_hours_evidence_status`, `idle_hours_claim`, `idle_hours_evidence_status`, `km_per_engine_hour`, `idle_hour_percent`, `service_history_claim`, `service_history_evidence_status`, `accident_title_claim`, `accident_title_evidence_status`, `prior_use_claims`, `evidence_completeness`, `missing_investigation_fields`, `price_band_basis`, `price_band_comparable_count`, `price_band_q1_cad`, `price_band_median_cad`, `price_band_q3_cad`, `price_position`, `price_difference_from_median_cad`, `mileage_adjusted_projection_cad`, `projection_slope_cad_per_10000_km`, `projection_r_squared`, `projected_mileage_5y_min_km`, `projected_mileage_5y_max_km`, `computed_classification`, `computed_classification_reasons`, `owner_disposition`, `owner_note`, `owner_tags`, `owner_classification_override`, `owner_override_reason`, `override_applied`, `effective_classification`, `seller_question_count`, `seller_questions_ref`, `raw_record_ref`, `source_adapter_record_ref`.

### Market summary fields

`market_summary_latest.json` includes `listing_claim_count`, `source_listing_claim_counts`, `year_groups`, `field_coverage`, `effective_classification_counts`, `owner_override_digest_sha256`, `owner_usage_projection`, `market_scope`, `price_band_contract`, `projection_contract`, `classification_contract`, `limitations`, and artifact paths.

## Storage-retention schema version 1

`storage_retention.py` writes per-vehicle retention reports/ledgers and `data/retention/latest.json`.

File deletion records include `path`, `category`, `reason`, `size_bytes`, `sha256`, `run_id`, and `deleted_at_utc`. Ledgers expose `deleted_file_count_total`, `deleted_bytes_total`, `deletion_chain_sha256`, `recent_deletions`, and `recent_deletion_limit`.

Repository metrics include `managed_file_count`, `managed_bytes`, `largest_file_bytes`, `oversized_files`, `max_managed_file_bytes`, `max_active_data_bytes`, `verification_status`, and `verification_errors`.

Archive limits are eight timestamped source CSVs per active vehicle/source and four timestamped manual-review CSVs per active vehicle. Current `*_latest` artifacts, including F-350 buyer-intelligence outputs, are never archive candidates. Paused vehicle data is outside the deletion boundary.

## Workflow-control schema version 1

`workflow_control.py` governs collection plans and single-pair validation.

A plan row is:

```text
<config_path>\t<source>
```

Supported scopes are `full` and `single_pair`. Single-pair validation requires exactly one active registry vehicle and one enabled source. Unknown, paused, disabled, empty, duplicate, or malformed plans fail before collection.

## Anomaly schema version 1

`data/run_status/anomalies_latest.json` contains `anomaly_schema_version`, `run_id`, `generated_at_utc`, `baseline_status`, `baseline_run_id`, `current_health_run_id`, `anomaly_status`, `critical_anomaly_count`, `warning_anomaly_count`, `informational_anomaly_count`, and `anomalies`.

Each anomaly contains `severity`, `code`, `vehicle_key`, `source`, `message`, `baseline`, `current`, and `threshold`. Severities are `critical`, `warning`, and `info`. `baseline_status` may be `available`, `unavailable`, or `same_run_not_compared`.

Anomaly evidence is a workflow diagnostic. It does not establish vehicle quality, fair value, or purchase suitability.

## Publication manifest schema version 1

`data/run_status/publication_latest.json` contains `publication_schema_version`, `publication_status`, `run_id`, `generated_at_utc`, `source_commit_sha`, `workflow_event`, `target_ref`, `manifest_path`, `published_path_count`, `published_paths`, `change_type_counts`, `active_vehicle_keys`, and `paused_vehicle_keys`.

The manifest must exactly match staged governed data paths other than the manifest itself. It proves publication-path accounting, not source truth.

## Generated-data validation schema version 1

Generated-data pull-request validation reports `generated_data_validation_schema_version`, `validation_status`, `changed_path_count`, `changed_paths`, `validation_errors`, and `retention_verification_status`.

Validation checks active/paused scope, retention, changed source statuses, changed health/anomaly evidence, and publication-manifest membership.

## Dependency-lock schema version 1

`requirements.lock` uses exact `package==version` entries. `dependency_lock.py` reports `dependency_lock_schema_version`, `validation_status`, `package_count`, `packages`, and `validation_errors`. Ranges, URLs, duplicates, and empty locks fail.

## Supported normalized listing fields

Normalized canonical records may contain `year`, `make`, `model`, `trim`, `trim_tier`, `price_cad`, `mileage_km`, `engine`, `fuel`, `accident_claim`, `dealer`, `seller_type_claim`, `dealer_address`, `location`, `distance_km`, `distance_method`, `source_listing_id`, `url_region_hint`, `url_region_status`, `listing_url`, `source_name`, and `days_on_market_claim`.

Kijiji query origin never becomes listing geography. Kijiji distance remains disabled.

## Decision-safe general manual-review CSV

The complete supported field order is:

`evidence_schema_version`, `identity_lifecycle_schema_version`, `vehicle_key`, `source`, `canonical_listing_id`, `observation_id`, `source_listing_id`, `source_listing_id_status`, `vin_claim`, `vin_evidence_status`, `source_claim_status`, `raw_record_ref`, `normalized_record_ref`, `identity_fingerprint_strict`, `identity_fingerprint_loose`, `lifecycle_state`, `lifecycle_state_reason`, `first_seen_at_utc`, `last_seen_at_utc`, `elapsed_since_first_seen_days`, `elapsed_since_last_seen_days`, `missing_run_count`, `reappearance_count`, `duplicate_candidate_count`, `highest_duplicate_confidence`, `duplicate_candidate_ids`, `duplicate_candidate_reasons`, `ranking_status`, `review_status`, `collection_status`, `data_quality_status`, `quality_warnings`, `source_run_status`, `source_completed_at_utc`, `year`, `year_evidence_status`, `make`, `make_evidence_status`, `model`, `model_evidence_status`, `trim`, `trim_evidence_status`, `price_cad`, `price_evidence_status`, `mileage_km`, `mileage_evidence_status`, `engine`, `engine_evidence_status`, `fuel`, `fuel_evidence_status`, `accident_claim`, `accident_evidence_status`, `dealer`, `dealer_evidence_status`, `seller_type_claim`, `seller_type_evidence_status`, `dealer_address`, `dealer_address_evidence_status`, `location`, `location_evidence_status`, `unverified_location_value`, `distance_km`, `distance_evidence_status`, `distance_method`, `url_region_hint`, `url_region_evidence_status`, `listing_url`, `listing_url_evidence_status`, `observation_count`, `price_observation_count`, `first_observed_price_cad`, `previous_observation_price_cad`, `change_from_previous_observation_cad`, `change_from_first_observation_cad`, `days_on_market_claim`.

`ranking_status` remains disabled. `duplicate_candidate_review_required` means human comparison is needed; it does not mean the records are the same physical vehicle.

## Runtime status schemas

Source status remains schema version `8` and requires canonical schema `1`, adapter schema `1`, identity schema `2`, current accepted/identity count agreement, freshness, reconciliation, pagination, uncapped execution, and config isolation.

Consolidated health remains schema version `6` and aggregates source reconciliation plus identity tracked/new/reappeared/missing/retired counts.

## Remaining limits

The repository does not establish independent VIN truth, physical-vehicle identity, verified configuration/history/prior use, sold status, marketplace completeness, mechanical condition, actual sale price, fair/appraised/future value, seller answers, purpose-specific non-F-350 analytics, or successful completion of three consecutive scheduled active-profile runs.
