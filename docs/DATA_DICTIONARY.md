# Data Dictionary

## Purpose

This document defines supported fields and evidence limits. Source claims, normalized values, identity/lifecycle state, F-350 buyer intelligence, secondary-purpose inputs/outputs, owner/friend annotations, calculations, deletion evidence, anomalies, publication evidence, rejections, and parse failures remain distinct.

## Registry and configuration

- `vehicle_registry.json`: schema v2; operational enabled/paused state, sources, purpose, priority, cadence, and analysis profile.
- `config_*.json`: schema v2; criteria, origin, and source query settings.
- `f350_owner_overrides.json`: schema v1; F-350 owner review input only.
- `purpose_inputs.json`: schema v1; secondary-purpose interpretation input only.

## Source and canonical boundary

```text
fetched_records = accepted_records + rejected_records + parse_failures
```

| Source | `fetched_record_scope` |
|---|---|
| AutoTrader | `autotrader_adapter_response_listing_objects` |
| Kijiji | `kijiji_adapter_json_ld_listing_objects` |

Adapters and canonical evidence use schema v1. Key fields include `canonical_listing_id`, `observation_id`, `source_listing_id`, `source_listing_id_status`, `source_adapter_record_ref`, `query_provenance`, `field_evidence`, `rejection_reasons`, and `parse_failure_reasons`.

`source_listing_id_status` is `source_identifier_claim_not_vin`. Kijiji query origin never becomes listing geography.

## Identity/lifecycle schema v2

Identity fields include `vin_claim`, `vin_evidence_status`, fingerprints, fingerprint components, and source-ID status. Fingerprints are comparison evidence, not merge authority.

Lifecycle fields include `lifecycle_state`, reasons, timestamps, elapsed time, `missing_run_count`, `reappearance_count`, and observation counts. States are `active`, `missing`, `reappeared`, and `retired`; retirement is not a sold claim.

Price fields include `price_observation_count`, `retained_price_observation_count`, `compacted_price_observation_count`, `price_observation_compaction_digest_sha256`, `first_observed_price_cad`, `previous_observation_price_cad`, `current_price_cad`, `minimum_observed_price_cad`, `maximum_observed_price_cad`, `change_from_previous_observation_cad`, and `change_from_first_observation_cad`.

## Duplicate candidates

`duplicate_candidates_latest.jsonl` contains `candidate_id`, `confidence`, `confidence_score`, `reasons`, `decision_status`, `left`, and `right`. `decision_status` remains `candidate_only_not_merged`.

## F-350 buyer-intelligence schema v1

Artifacts:

```text
data/ford_f350/buyer_intelligence/investigation_latest.jsonl
data/ford_f350/buyer_intelligence/investigation_latest.csv
data/ford_f350/buyer_intelligence/seller_questions_latest.jsonl
data/ford_f350/buyer_intelligence/market_summary_latest.json
data/ford_f350/buyer_intelligence/market_summary_latest.md
```

Important fields/contracts include:

- `source_text_reported_unverified`
- `km_per_engine_hour`
- `idle_hour_percent`
- `price_band_comparable_count`
- `projection_slope_cad_per_10000_km`
- `projection_r_squared`
- `computed_classification`
- `owner_classification_override`
- `seller_question_count`
- `owner_usage_scenario_not_odometer_or_value_guarantee`
- `asking_price_context_not_appraisal_or_future_value`

No buyer artifact contains purchase `rank` or `score`.

## Secondary-purpose input schema v1

`purpose_inputs.json` has top-level `schema_version` and exactly four vehicle entries.

### Owned-vehicle subject profile

RAM 3500 and Subaru Forester use `analysis_profile: owned_vehicle_value` and `subject_profile` fields:

- `year`
- `trim`
- `fuel`
- `engine`
- `drivetrain`
- `current_odometer_km`
- `odometer_context`

Each field contains exactly `value` and `evidence_status`. Allowed statuses:

- `owner_reported_historical_unverified`
- `owner_input_required`

`odometer_context` does not become current odometer.

### Family-friend preference profile

Honda Odyssey and Kia Carnival use `analysis_profile: family_friend_purchase` and preference fields:

- `budget_max_cad`
- `min_year`
- `max_year`
- `max_mileage_km`
- `minimum_seating`
- `cargo_requirements`
- `max_distance_km`
- `accident_title_requirement`
- `service_history_requirement`
- `acceptable_seller_types`
- `availability_constraints`

Allowed statuses:

- `friend_input_required`
- `friend_reported_unverified`

Null or empty values remain missing preferences.

## Secondary-purpose output schema v1

`purpose_outputs.py` requires current source status v8, canonical v1, raw adapter v1, identity v2, and purpose-input v1. `purpose_output_validation.py` provides validation schema v1.

### Owned-vehicle artifacts

```text
data/<vehicle>/purpose_output/value_monitor/comparables_latest.jsonl
data/<vehicle>/purpose_output/value_monitor/comparables_latest.csv
data/<vehicle>/purpose_output/value_monitor/owner_input_gaps_latest.json
data/<vehicle>/purpose_output/value_monitor/market_snapshot_latest.json
data/<vehicle>/purpose_output/value_monitor/market_snapshot_latest.md
```

Owned comparable fields include:

- `purpose_output_schema_version`
- `run_id`, `scope`, `vehicle_key`, `analysis_profile`, `source`
- `canonical_listing_id`, `source_listing_id`, `listing_url`, `lifecycle_state`
- `year`, `trim_claim`, `fuel_claim`, `engine_claim`, `drivetrain_claim`
- `price_cad`, `mileage_km`, `distance_km`
- `price_observation_count`
- `previous_observation_price_cad`
- `change_from_previous_observation_cad`
- `change_from_first_observation_cad`
- `subject_comparability`
- `subject_comparability_reasons`
- `subject_profile_missing_fields`
- `market_role`
- `raw_record_ref`, `source_adapter_record_ref`

Comparability values:

- `close_subject_comparable`
- `partial_subject_comparable`
- `broad_market_context`
- `subject_profile_incomplete`
- `insufficient_configuration_evidence`

Record contract:

```text
observed_asking_price_context_not_appraisal_not_sale_probability
```

Summary fields include `source_record_counts`, `year_counts`, `subject_comparability_counts`, `cohort_basis`, `cohort_count`, `asking_price_distribution_cad`, `mileage_distribution_km`, `competitive_asking_context`, `multi_run_direction`, `subject_profile_missing_fields`, and artifact paths.

Distribution objects contain `count`, `minimum`, `q1`, `median`, `q3`, and `maximum`.

Lower asking-band meaning:

```text
lower_observed_asking_band_not_verified_faster_sale_range_or_sale_probability
```

Multi-run statuses:

- `insufficient_multi_run_history`
- `observed_asking_price_change_context_available`

Multi-run meaning:

```text
listing_asking_price_changes_only_not_market_value_trend_or_sale_evidence
```

### Family-candidate artifacts

```text
data/<vehicle>/purpose_output/family_candidate/candidate_review_latest.jsonl
data/<vehicle>/purpose_output/family_candidate/candidate_review_latest.csv
data/<vehicle>/purpose_output/family_candidate/seller_questions_latest.jsonl
data/<vehicle>/purpose_output/family_candidate/requirements_summary_latest.json
data/<vehicle>/purpose_output/family_candidate/requirements_summary_latest.md
```

Family candidate fields include:

- common run/source/canonical/lifecycle references
- `seller_type_claim`
- `seating_claim`, `seating_evidence_status`
- `cargo_feature_claims`, `cargo_feature_evidence_status`
- `service_history_claim`, `service_history_evidence_status`
- `accident_title_claim`, `accident_title_evidence_status`
- `missing_preference_fields`
- `preference_match_status`, `preference_match_reasons`
- `candidate_classification`, `candidate_classification_reasons`
- `seller_question_count`, `seller_questions_ref`
- raw and adapter references

Candidate classifications:

- `candidate_pending_requirements`
- `candidate_outside_stated_preferences`
- `candidate_with_evidence_gaps`
- `candidate_for_manual_review`

Preference-match statuses:

- `preferences_incomplete`
- `outside_stated_preferences`
- `preference_match_unresolved_by_missing_listing_evidence`
- `within_stated_preferences_based_on_unverified_listing_claims`

Decision contract:

```text
purpose_specific_candidate_classification_not_rank_not_score
```

Summary contract:

```text
candidate_review_not_rank_not_recommendation_not_condition_verification
```

`requirements_status` is `friend_input_required` while any preference is missing; otherwise it is `requirements_recorded_unverified`.

Seller-question entries contain `category`, `priority`, `question`, and `reason`. Questions do not verify answers.

## Storage-retention schema v1

File deletion records include path, category, reason, bytes, SHA-256, run, and time. Current `*_latest` F-350 and secondary-purpose artifacts are preserved; Audit 10 adds no timestamped purpose archives.

## Workflow and publication schemas

- Workflow-control schema v1 governs `full` and `single_pair` plans.
- Anomaly schema v1 is diagnostic, not vehicle-quality authority.
- Publication manifest schema v1 must match staged governed paths.
- Generated-data validation schema v1 validates active/paused scope, retention, source status, health, anomalies, manifests, F-350 artifacts, and secondary-purpose artifacts.
- Dependency-lock schema v1 requires exact `package==version` entries.

## Supported normalized listing fields

Normalized records may contain `year`, `make`, `model`, `trim`, `trim_tier`, `price_cad`, `mileage_km`, `engine`, `fuel`, `accident_claim`, `dealer`, `seller_type_claim`, `dealer_address`, `location`, `distance_km`, `distance_method`, `source_listing_id`, `url_region_hint`, `url_region_status`, `listing_url`, `source_name`, and `days_on_market_claim`.

## Decision-safe general manual-review CSV

The supported field order remains:

`evidence_schema_version`, `identity_lifecycle_schema_version`, `vehicle_key`, `source`, `canonical_listing_id`, `observation_id`, `source_listing_id`, `source_listing_id_status`, `vin_claim`, `vin_evidence_status`, `source_claim_status`, `raw_record_ref`, `normalized_record_ref`, `identity_fingerprint_strict`, `identity_fingerprint_loose`, `lifecycle_state`, `lifecycle_state_reason`, `first_seen_at_utc`, `last_seen_at_utc`, `elapsed_since_first_seen_days`, `elapsed_since_last_seen_days`, `missing_run_count`, `reappearance_count`, `duplicate_candidate_count`, `highest_duplicate_confidence`, `duplicate_candidate_ids`, `duplicate_candidate_reasons`, `ranking_status`, `review_status`, `collection_status`, `data_quality_status`, `quality_warnings`, `source_run_status`, `source_completed_at_utc`, `year`, `year_evidence_status`, `make`, `make_evidence_status`, `model`, `model_evidence_status`, `trim`, `trim_evidence_status`, `price_cad`, `price_evidence_status`, `mileage_km`, `mileage_evidence_status`, `engine`, `engine_evidence_status`, `fuel`, `fuel_evidence_status`, `accident_claim`, `accident_evidence_status`, `dealer`, `dealer_evidence_status`, `seller_type_claim`, `seller_type_evidence_status`, `dealer_address`, `dealer_address_evidence_status`, `location`, `location_evidence_status`, `unverified_location_value`, `distance_km`, `distance_evidence_status`, `distance_method`, `url_region_hint`, `url_region_evidence_status`, `listing_url`, `listing_url_evidence_status`, `observation_count`, `price_observation_count`, `first_observed_price_cad`, `previous_observation_price_cad`, `change_from_previous_observation_cad`, `change_from_first_observation_cad`, `days_on_market_claim`.

`ranking_status` remains disabled.

## Runtime status schemas

Source status remains v8; consolidated health remains v6.

## Remaining limits

The repository does not establish independent identity/configuration/history truth, sold state, marketplace completeness, mechanical condition, actual sale price, appraisal, future value, sale probability, verified faster-sale range, seller answers, personalized secondary outputs without required inputs, or three consecutive unattended scheduled runs.
