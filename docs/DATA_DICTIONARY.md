# Data Dictionary

## Purpose

This document defines current supported fields and their evidence limits. Source claims, normalized values, identity fingerprints, VIN claims, lifecycle inferences, duplicate candidates, rejections, and parse failures are distinct.

## Registry and configuration

`vehicle_registry.json` schema version `2` controls enabled/paused vehicles and sources. Every `config_*.json` uses schema version `2` with shared criteria, origin, and separate AutoTrader/Kijiji query settings.

## Source fetched boundaries

```text
fetched_records = accepted_records + rejected_records + parse_failures
```

| Source | `fetched_record_scope` | Meaning |
|---|---|---|
| AutoTrader | `autotrader_adapter_response_listing_objects` | Every listing object returned to configured direct-adapter queries |
| Kijiji | `kijiji_adapter_json_ld_listing_objects` | Every JSON-LD listing object returned to configured validated hub queries |

Neither boundary proves full marketplace coverage.

## Adapter evidence schema version 1

Both sources write `requests_latest.jsonl`, `records_latest.jsonl`, and `reconciliation_latest.json` under `data/<vehicle>/adapter_evidence/<source>/`. Record stages are `accepted`, `rejected`, and `parse_failure`.

## Canonical evidence schema version 1

Each source writes raw, normalized, accepted, rejected, parse-failure, and reconciliation artifacts under `data/<vehicle>/evidence/<source>/`.

Key canonical fields include `canonical_listing_id`, `observation_id`, `source_listing_id`, `source_listing_id_status`, `source_adapter_record_ref`, `query_provenance`, `field_evidence`, `rejection_reasons`, and `parse_failure_reasons`.

`source_listing_id_status` is `source_identifier_claim_not_vin`. Evidence statuses include `straight_line_estimate_from_source_reported_location`, `source_reported_listing_specific_unverified`, `query_origin_never_location`, `unverified_url_evidence`, `unknown`, and `unavailable`.

## Identity and lifecycle schema version 1

Per-source identity artifacts are under `data/<vehicle>/identity_lifecycle/<source>/`.

### Identity fields

- `source_listing_id_status` — source ID remains distinct from VIN
- `vin_claim` — explicit source-reported format-valid VIN claim or null
- `vin_evidence_status` — `source_reported_format_valid_unverified`, `source_reported_invalid_format_unverified`, `conflicting_source_reported_claims`, or `not_reported`
- `vin_raw_claims` — explicit raw VIN claims
- `identity_fingerprint_strict` — deterministic strict comparison fingerprint
- `identity_fingerprint_loose` — deterministic broader comparison fingerprint
- `identity_fingerprint_components` — visible components used by fingerprints

Fingerprints are comparison evidence, not merge authority.

### Lifecycle fields

- `lifecycle_state` — `active`, `missing`, `reappeared`, or `retired`
- `lifecycle_state_reason` — visible transition reason
- `first_seen_at_utc` / `last_seen_at_utc` — exact successful-observation timestamps
- `last_evaluated_at_utc` — latest successful lifecycle evaluation
- `elapsed_since_first_seen_seconds` / `elapsed_since_first_seen_days`
- `elapsed_since_last_seen_seconds` / `elapsed_since_last_seen_days`
- `missing_run_count` — consecutive successful source runs without observation
- `reappearance_count` — returns after missing/retired
- `observation_count` — unique successful-run observations

`retired` requires at least three consecutive successful-run misses and at least fourteen actual elapsed days. It is not a sold claim.

### Price observation fields

- `price_observation_count`
- `first_observed_price_cad`
- `previous_observation_price_cad`
- `current_price_cad`
- `change_from_previous_observation_cad`
- `change_from_first_observation_cad`

Legacy `weeks_tracked`, `price_last_week`, `price_change_week`, and `price_history_*.json` are not supported history semantics.

## Duplicate candidates

`duplicate_candidates_latest.jsonl` contains cross-source comparison candidates.

- `candidate_id` — stable candidate-pair identifier
- `confidence` — `high`, `medium`, or `low`
- `confidence_score` — bounded comparison confidence, not purchase ranking
- `reasons` — visible supporting evidence
- `decision_status` — always `candidate_only_not_merged`
- `left` / `right` — preserved source and canonical references

Canonical records remain separate.

## Supported normalized listing fields

Normalized canonical records may contain `year`, `make`, `model`, `trim`, `trim_tier`, `price_cad`, `mileage_km`, `engine`, `fuel`, `accident_claim`, `dealer`, `seller_type_claim`, `dealer_address`, `location`, `distance_km`, `distance_method`, `source_listing_id`, `url_region_hint`, `url_region_status`, `listing_url`, `source_name`, and `days_on_market_claim`.

Kijiji query origin never becomes listing geography. Kijiji distance remains disabled.

## Decision-safe manual-review CSV

The complete supported field order is:

`evidence_schema_version`, `identity_lifecycle_schema_version`, `vehicle_key`, `source`, `canonical_listing_id`, `observation_id`, `source_listing_id`, `source_listing_id_status`, `vin_claim`, `vin_evidence_status`, `source_claim_status`, `raw_record_ref`, `normalized_record_ref`, `identity_fingerprint_strict`, `identity_fingerprint_loose`, `lifecycle_state`, `lifecycle_state_reason`, `first_seen_at_utc`, `last_seen_at_utc`, `elapsed_since_first_seen_days`, `elapsed_since_last_seen_days`, `missing_run_count`, `reappearance_count`, `duplicate_candidate_count`, `highest_duplicate_confidence`, `duplicate_candidate_ids`, `duplicate_candidate_reasons`, `ranking_status`, `review_status`, `collection_status`, `data_quality_status`, `quality_warnings`, `source_run_status`, `source_completed_at_utc`, `year`, `year_evidence_status`, `make`, `make_evidence_status`, `model`, `model_evidence_status`, `trim`, `trim_evidence_status`, `price_cad`, `price_evidence_status`, `mileage_km`, `mileage_evidence_status`, `engine`, `engine_evidence_status`, `fuel`, `fuel_evidence_status`, `accident_claim`, `accident_evidence_status`, `dealer`, `dealer_evidence_status`, `seller_type_claim`, `seller_type_evidence_status`, `dealer_address`, `dealer_address_evidence_status`, `location`, `location_evidence_status`, `unverified_location_value`, `distance_km`, `distance_evidence_status`, `distance_method`, `url_region_hint`, `url_region_evidence_status`, `listing_url`, `listing_url_evidence_status`, `observation_count`, `price_observation_count`, `first_observed_price_cad`, `previous_observation_price_cad`, `change_from_previous_observation_cad`, `change_from_first_observation_cad`, `days_on_market_claim`.

`ranking_status` remains disabled. `duplicate_candidate_review_required` means human comparison is needed; it does not mean the records are the same physical vehicle.

## Source status schema version 8

Both source statuses require canonical evidence schema `1`, adapter schema `1`, identity/lifecycle schema `1`, `identity_lifecycle_status: updated`, identity current count equal to accepted canonical count, fresh schema-valid output, reconciliation, pagination, uncapped execution, and config isolation.

Identity status also records tracked, new, reappeared, missing, retired, and transition-event counts. Legacy price history is explicitly inactive.

## Consolidated health schema version 6

Full-run health aggregates source reconciliation plus identity tracked/new/reappeared/missing/retired counts.

## Remaining limits

The repository does not establish independent VIN truth, physical-vehicle identity, sold status, marketplace completeness, mechanical condition, fair value, buyer ranking, retention policy, or purpose-specific analytics.
