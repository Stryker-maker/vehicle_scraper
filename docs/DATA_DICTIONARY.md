# Data Dictionary

## Purpose

This document defines current repository fields and the evidence limits they represent. Raw strings, normalized values, source claims, inferred values, unknown values, and rejected records are distinct concepts.

## Registry and configuration

`vehicle_registry.json` uses schema version `2` and is the sole operational authority for `profile`, ordered `vehicles`, `vehicle_key`, `config_path`, `enabled`, `purpose`, `priority`, `cadence`, `enabled_sources`, `analysis_profile`, and conditional `pause_reason`.

Every `config_*.json` file uses schema version `2` and contains `vehicle_key`, human-facing `make` and `model`, shared `criteria`, `origin`, and separate `sources.autotrader` / `sources.kijiji` query settings. Approved configs prohibit legacy flat controls such as `max_results`, `ranking_weights`, one shared `search_locations`, and flat source aliases.

## Canonical evidence schema version 1

`canonical_evidence.py` starts at the fresh legacy collector CSV boundary. It does not claim that the legacy collector fetched or parsed every marketplace record. Until Audits 04 and 05 replace the source adapters, `fetched_records` means rows emitted by the legacy collector into its latest CSV.

Each source writes current evidence under:

```text
data/<vehicle>/evidence/<source>/
```

| Artifact | Meaning |
|---|---|
| `raw_latest.jsonl` | One envelope per collector-emitted row, preserving the exact CSV strings in `raw_values` |
| `normalized_latest.jsonl` | Successfully normalized rows, including rows later accepted or rejected |
| `accepted_latest.jsonl` | Normalized records eligible for supported manual review |
| `rejected_latest.jsonl` | Structurally normalized records excluded with machine-readable `rejection_reasons` |
| `parse_failures_latest.jsonl` | Malformed or unnormalizable rows with `parse_failure_reasons` and retained raw evidence where available |
| `reconciliation_latest.json` | Counts, artifact paths, scope caveat, and reconciliation result |

The enforced equation is:

```text
fetched_records = accepted_records + rejected_records + parse_failures
```

### Record envelope fields

| Field | Meaning |
|---|---|
| `evidence_schema_version` | Canonical evidence schema version; currently `1` |
| `record_stage` | `raw`, `normalized`, `accepted`, `rejected`, or `parse_failure` |
| `vehicle_key` | Governed repository vehicle key |
| `source` | Lowercase source key: `autotrader` or `kijiji` |
| `run_id` | Workflow run ID or explicit local run ID |
| `source_record_index` | Zero-based row position at the canonical boundary |
| `canonical_listing_id` | Stable hash of vehicle, source, and source listing identity basis; not a VIN and not cross-source identity |
| `observation_id` | Run-specific stable hash of canonical listing, run, and source row position |
| `source_listing_id` | Source-provided listing identifier after explicit null handling |
| `source_listing_id_status` | `source_identifier_claim_not_vin` or `unknown` |
| `source_claim_status` | `unverified_source_claims` |
| `raw_record_ref` | Artifact path plus raw record selector |
| `normalized_record_ref` | Artifact path plus normalized source-record selector |
| `normalized` | Typed/null-safe canonical values |
| `field_evidence` | Per-field raw value, normalized value, source field, and evidence status |
| `quality_warnings` | Non-destructive warning codes |
| `rejection_reasons` | Machine-readable reasons; empty for accepted records |
| `parse_failure_reasons` | Machine-readable parser/normalizer failure codes |

### Null and unknown policy

Empty strings and common sentinels such as `Unknown`, `N/A`, `None`, `null`, and `unavailable` normalize to JSON `null`. Legacy mileage sentinel `999999` also normalizes to `null`. The exact original string remains in `raw_values` and in the relevant `field_evidence.raw_value`.

Unknown values do not automatically reject a record. Current structural rejection reasons are `missing_source_listing_id` and `missing_listing_url`. Malformed column counts become `malformed_column_count` parse failures. Reader-level CSV failures use `csv_reader_error`; normalization exceptions use a `normalization_error:<type>` code.

### Evidence status vocabulary

Current evidence statuses include:

- `source_reported_unverified`
- `source_reported_or_configured_unverified`
- `source_reported_or_inferred_unverified`
- `source_text_claim_unverified`
- `source_identifier_claim_not_vin`
- `source_reported_not_independently_verified`
- `legacy_method_not_yet_disambiguated`
- `quarantined_unverified_search_origin`
- `disabled_due_to_unverified_location`
- `unverified_url_evidence`
- `unavailable`
- `unknown`

These labels describe evidence strength or handling. They do not verify a vehicle, seller, price, history, location, or availability.

## Canonical normalized values

Normalized records may contain:

| Field | Meaning |
|---|---|
| `year` | Parsed integer model year or null |
| `make` | Source-reported or configured make text or null |
| `model` | Source-reported or configured model text or null |
| `trim` | Source/title-derived trim text or null |
| `trim_tier` | Legacy numeric tier or null; not recommendation authority |
| `price_cad` | Parsed asking price integer in CAD or null |
| `mileage_km` | Parsed odometer integer in kilometres or null |
| `engine` | Source-derived engine text or null |
| `fuel` | Source-derived/inferred fuel text or null |
| `accident_claim` | Source-text claim or null; not a vehicle-history report |
| `dealer` | Source-reported seller/dealer name or null |
| `seller_type_claim` | Source-derived seller category claim or null |
| `dealer_address` | AutoTrader source evidence or null; Kijiji value is quarantined |
| `location` | AutoTrader reported location or null; Kijiji normalized location is null |
| `distance_km` | Legacy AutoTrader numeric distance or null; Kijiji is null |
| `distance_method` | Legacy method label or `disabled_unverified_location` |
| `source_listing_id` | Source-specific ID claim; not VIN |
| `url_region_hint` | Kijiji URL segment evidence or null |
| `url_region_status` | Source-provided URL evidence label or null |
| `listing_url` | Source listing URL or null |
| `source_name` | Source display text or lowercase fallback |
| `observation_count` | Legacy stored-observation count; not elapsed weeks |
| `first_observed_price_cad` | First stored price for current source listing ID |
| `previous_observation_price_cad` | Previous stored observation price; not necessarily one week earlier |
| `change_from_previous_observation_cad` | Current minus previous stored observation |
| `change_from_first_observation_cad` | Current minus first stored observation |
| `source_price_history_text` | Source or legacy price-history text |
| `legacy_trend_text` | Legacy trend wording; not authoritative elapsed-time evidence |
| `days_on_market_claim` | Source/legacy duration text claim or null |

## Decision-safe manual-review CSV

The supported manual-review CSV is generated only from `accepted_latest.jsonl`. It excludes source `rank`, source `score`, misleading `weeks_tracked`, and misleading `price_last_week` names. It preserves source claims with explicit status columns and retains Kijiji search-origin evidence only in `unverified_location_value`.

The complete field order is:

`evidence_schema_version`, `vehicle_key`, `source`, `canonical_listing_id`, `observation_id`, `source_listing_id`, `source_listing_id_status`, `source_claim_status`, `raw_record_ref`, `normalized_record_ref`, `ranking_status`, `review_status`, `collection_status`, `data_quality_status`, `quality_warnings`, `source_run_status`, `source_completed_at_utc`, `year`, `year_evidence_status`, `make`, `make_evidence_status`, `model`, `model_evidence_status`, `trim`, `trim_evidence_status`, `price_cad`, `price_evidence_status`, `mileage_km`, `mileage_evidence_status`, `engine`, `engine_evidence_status`, `fuel`, `fuel_evidence_status`, `accident_claim`, `accident_evidence_status`, `dealer`, `dealer_evidence_status`, `seller_type_claim`, `seller_type_evidence_status`, `dealer_address`, `dealer_address_evidence_status`, `location`, `location_evidence_status`, `unverified_location_value`, `distance_km`, `distance_evidence_status`, `distance_method`, `url_region_hint`, `url_region_evidence_status`, `listing_url`, `listing_url_evidence_status`, `observation_count`, `first_observed_price_cad`, `previous_observation_price_cad`, `change_from_previous_observation_cad`, `change_from_first_observation_cad`, `source_price_history_text`, `legacy_trend_text`, `days_on_market_claim`.

### Manual-review control fields

| Field | Meaning |
|---|---|
| `ranking_status` | Always `DISABLED_MANUAL_REVIEW_REQUIRED` |
| `review_status` | `manual_review_required`, `data_quality_review_required`, or `location_verification_required` |
| `collection_status` | Current source collection result |
| `data_quality_status` | `clean` or `warnings_present` under current limited rules |
| `quality_warnings` | Semicolon-separated warning codes |
| `source_run_status` | Current source execution status |
| `source_completed_at_utc` | Source completion timestamp |

A row labelled `clean` is not verified or purchase-safe. It only means the current warning rules did not fire.

## Per-source run-status JSON schema version 5

Each enabled pair writes `data/<vehicle>/run_status/<source>_latest.json`.

Audit 02 fields remain, including governed config/projection/isolation evidence, freshness, timeout, history protection, warnings, and stale rows. Audit 03 adds:

| Field | Meaning |
|---|---|
| `canonical_evidence_schema_version` | Currently `1` |
| `fetched_record_scope` | `legacy_collector_emitted_csv_rows` when evaluated |
| `source_fetch_completeness` | `not_proven_by_legacy_collector` until source adapters are replaced |
| `fetched_record_count` | Rows entering the canonical boundary |
| `normalized_record_count` | Rows successfully normalized |
| `accepted_record_count` | Records eligible for supported review |
| `rejected_record_count` | Normalized records with explicit rejection reasons |
| `parse_failure_count` | Rows preserved as parse failures |
| `evidence_reconciliation_status` | `reconciled` or `not_reconciled` |
| `evidence_reconciliation_equation` | Human-readable required equation |
| `canonical_evidence_artifacts` | Repository-relative artifact paths |
| `canonical_evidence_error` | Error text when evidence generation fails, otherwise null |

A source is healthy only if it is current, successful, fresh, minimally schema-valid, uncapped, config-isolated, reconciled, and has at least one accepted record.

## Consolidated health JSON schema version 5

`data/run_status/latest.json` contains the registry-derived expected source entries and totals:

- `expected_source_runs`
- `healthy_source_runs`
- `unhealthy_source_runs`
- `source_runs_with_quality_warnings`
- `fetched_record_count`
- `accepted_record_count`
- `rejected_record_count`
- `parse_failure_count`
- `sources`

The Markdown health report displays the same reconciliation counts for each enabled source pair.

## Remaining non-canonical areas

Audit 03 does not create marketplace HTTP/raw-response evidence inside the legacy collectors. It also does not create VIN identity, duplicate confidence, listing lifecycle, engine/idle-hour evidence, cab/box/drivetrain evidence, verified service/history/warranty evidence, owner notes, or candidate classifications. Those remain assigned to Audits 04–10 and must not be simulated from unrelated fields.
