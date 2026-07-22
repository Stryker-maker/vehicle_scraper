# Audit 03 — Canonical Listing Schema and Evidence Model

## Status

Implemented on `ai/audit-03-canonical-evidence`. Structured PR validation and one live branch workflow are required before owner merge.

## Purpose

Audit 03 creates a traceable, decision-safe evidence layer between the current legacy collector CSVs and human-facing manual review.

It guarantees that every row emitted by a legacy collector is preserved and classified after the canonical boundary. It does not claim the legacy collectors fetched or emitted every marketplace record.

## Canonical boundary

Current boundary:

```text
legacy collector latest CSV
  → canonical evidence schema v1
```

The reconciliation scope is recorded as:

```text
legacy_collector_emitted_csv_rows
```

Required equality:

```text
fetched_records = accepted_records + rejected_records + parse_failures
```

Audits 04 and 05 must move the fetched/raw boundary into the AutoTrader and Kijiji source adapters.

## Delivered design

### Stable record identifiers

- `canonical_listing_id` is stable for one vehicle/source/source-listing identity basis.
- `observation_id` is specific to one run and source row position.
- Source listing identifiers are labelled `source_identifier_claim_not_vin`.
- No cross-source or physical-vehicle identity claim is made.

### Raw preservation

Every collector-emitted row is written to `raw_latest.jsonl` with:

- exact CSV string values
- source row number/index
- run ID
- vehicle/source context
- observation timestamp

### Normalization

`normalized_latest.jsonl` contains typed values and explicit JSON nulls.

Common unknown strings and legacy mileage sentinel `999999` normalize to null. Raw strings remain available for inspection.

### Provenance and evidence status

Each canonical field records:

- source field name
- raw value
- normalized value
- evidence status

Source claims remain unverified claims. Kijiji location/address/distance values remain raw evidence but normalize to null with quarantine/disabled statuses.

### Accepted, rejected, and parse-failure artifacts

- `accepted_latest.jsonl` contains records eligible for supported manual review.
- `rejected_latest.jsonl` contains normalized records with `rejection_reasons`.
- `parse_failures_latest.jsonl` contains malformed/failed rows with `parse_failure_reasons`.

Current structural rejection reasons:

- `missing_source_listing_id`
- `missing_listing_url`

Current parse-failure reasons include:

- `malformed_column_count`
- `csv_reader_error`
- `normalization_error:<type>`

### Reconciliation artifact

`reconciliation_latest.json` records:

- evidence schema
- vehicle/source/run
- fetched boundary scope
- source completeness caveat
- fetched/normalized/accepted/rejected/parse counts
- reconciliation result and equation
- all artifact paths

### Health integration

Per-source status schema advances to version 5 and records canonical counts, artifact paths, reconciliation, and evidence errors.

A source cannot be healthy unless:

- collector execution succeeded
- output is fresh and minimally schema-valid
- result cap is disabled
- approved config remained isolated
- canonical evidence schema is recognized
- reconciliation is successful
- at least one accepted record exists

Consolidated health schema advances to version 5 and totals all canonical counts.

### Decision-safe manual review

Manual review now loads only `accepted_latest.jsonl` for the current run.

It includes:

- canonical listing and observation IDs
- raw/normalized record references
- source-claim and per-field evidence statuses
- explicit Kijiji quarantine fields
- safer observation-based history names

It excludes:

- source `rank`
- source `score`
- misleading `weeks_tracked`
- misleading `price_last_week`

## Tests

Structured tests cover:

- accepted + rejected + parse-failure reconciliation
- exact raw sentinel preservation
- JSON-null normalization
- machine-readable rejection/failure reasons
- stable listing IDs and run-specific observation IDs
- source ID not-VIN status
- Kijiji location quarantine
- 200-row and 3,000-row uncapped reconciliation
- evidence-backed manual review
- evidence-run mismatch exclusion
- health totals and degradation behaviour
- documentation field coverage

## Preserved behaviour

- Active vehicles remain F-350, RAM 3500, Forester, Odyssey, and Carnival.
- F-150 and Tundra remain paused.
- Registry/config schema v2 remains authoritative.
- Ten source runs remain expected.
- Collector parsing/query behaviour is unchanged.
- Automated ranking remains disabled.
- Existing source CSV and price-history artifacts remain.

## Intentional non-scope

Audit 03 does not:

- repair AutoTrader pagination or parser logic
- capture marketplace HTTP/raw-response evidence
- replace Kijiji runtime source rewriting
- verify Kijiji geography
- create VIN/cross-source identity or deduplication
- create lifecycle states
- define retention policy
- create purpose-specific analytics
- enrich F-350 evidence
- re-enable optional vehicles

## PR acceptance

The pull-request head must pass:

- Python compilation
- registry/config validation
- complete structured test suite
- collection skipped on PR events

## Live acceptance

One manual branch workflow is required because generated artifacts and health semantics changed. It must prove:

- exactly 10 enabled source attempts
- all 10 sources healthy
- evidence schema version 1 for every source
- status schema version 5
- each source reconciliation equals fetched = accepted + rejected + parse failures
- all canonical artifact paths exist
- manual-review row totals equal accepted totals per vehicle
- Kijiji location remains quarantined
- consolidated health schema version 5 and totals reconcile
- no F-150 or Tundra path changes
- generated-data follow-up runs acknowledgement only

## Stop conditions

Stop and revise before merge if any collector-emitted row is unaccounted for, any evidence artifact is missing, a manual-review file consumes raw source CSV directly, a source with failed reconciliation is marked healthy, unknown values are replaced with invented facts, Kijiji location becomes trusted, or paused vehicle data changes.
