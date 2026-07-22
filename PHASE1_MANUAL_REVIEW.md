# Phase 1: Canonical Evidence and Manual Review

**Status:** active interim operating guidance during the repository audit.

For current architecture, field semantics, limitations, and future package ownership, also read:

- `docs/REPOSITORY_BASELINE.md`
- `docs/ARCHITECTURE_AND_DATA_FLOW.md`
- `docs/DATA_DICTIONARY.md`
- `docs/LIMITATIONS_REGISTER.md`
- `docs/AUDIT_ROADMAP.md`
- `AUDIT_03_CANONICAL_EVIDENCE.md`

## What Phase 1 controls

- The authoritative vehicle/source plan is `vehicle_registry.json` schema v2.
- Approved `config_*.json` files use schema v2 and are never passed to collectors for mutation.
- Each source receives a disposable source-specific legacy projection with an effectively unbounded result cap.
- Each collector has a 75-minute timeout; remaining source attempts continue after one failure.
- Fresh collector output is validated at a minimum source-schema boundary.
- Every collector-emitted row is preserved in canonical evidence schema v1.
- Raw values, normalized values, accepted records, rejected records, and parse failures are separate artifacts.
- Rejections and parse failures carry machine-readable reasons.
- A source is healthy only when evidence reconciles and at least one accepted record exists.
- Supported manual review is built only from accepted evidence for the current run.
- Manual review contains no source rank or score.
- Misleading legacy names such as `weeks_tracked` and `price_last_week` are not used in supported review.
- Kijiji location/address/distance values remain raw evidence but are quarantined from normalized decision fields.
- Existing files under `data/<vehicle>/merged/` remain historical and are not refreshed.

## Canonical evidence files

For each enabled vehicle/source pair:

```text
data/<vehicle>/evidence/<source>/raw_latest.jsonl
data/<vehicle>/evidence/<source>/normalized_latest.jsonl
data/<vehicle>/evidence/<source>/accepted_latest.jsonl
data/<vehicle>/evidence/<source>/rejected_latest.jsonl
data/<vehicle>/evidence/<source>/parse_failures_latest.jsonl
data/<vehicle>/evidence/<source>/reconciliation_latest.json
```

The required equation is:

```text
fetched_records = accepted_records + rejected_records + parse_failures
```

During the legacy collector phase, `fetched_records` means rows emitted into the collector CSV. It does not prove how many marketplace records were requested, returned, or lost inside the collector.

## What Phase 1 does not prove

Phase 1 does not prove:

- that every marketplace record was requested or fetched
- that every source response was preserved
- that every record skipped inside a legacy collector has evidence
- that AutoTrader pagination is complete
- that Kijiji geography is correct
- that AutoTrader distance is routed driving distance
- that a source claim is independently verified
- that source listing IDs are VINs or identify one physical vehicle across sources
- that observation count equals elapsed weeks
- that a listing is available, mechanically sound, fairly priced, or suitable to purchase

A source or row labelled `clean` has only passed the current limited warning rules.

## Active scope

The scheduled/manual workflow currently includes:

- Ford F-350 — primary purchase research
- RAM 3500 — owned-vehicle value monitoring
- Subaru Forester — owned-vehicle value monitoring
- Honda Odyssey — family-friend purchase search
- Kia Carnival — family-friend purchase search

Ford F-150 and Toyota Tundra remain paused. Their existing data must remain unchanged until Audit 11 or an owner-approved revision.

Use:

```bash
python vehicle_registry.py validate
python vehicle_registry.py summary
python vehicle_registry.py active-runs
```

## Workflow behaviour

Collector failures and timeouts do not stop remaining attempts. After each successful fresh source CSV, canonical evidence is generated and reconciled. The workflow then builds manual-review files from accepted evidence, writes consolidated health, commits generated data/evidence, and fails visibly if any expected source is unhealthy.

Quality warnings do not discard accepted records or fail collection. A fully reconciled run with warnings is `SUCCESS_WITH_WARNINGS`.

A generated-data commit receives a lightweight acknowledgement check instead of rerunning collectors. Normal implementation changes run the complete structured test suite.

## Files to use

Use:

- `data/<vehicle>/manual_review/<vehicle>_manual_review_latest.csv`
- `data/<vehicle>/evidence/<source>/reconciliation_latest.json`
- `data/<vehicle>/evidence/<source>/accepted_latest.jsonl`
- `data/<vehicle>/evidence/<source>/rejected_latest.jsonl`
- `data/<vehicle>/evidence/<source>/parse_failures_latest.jsonl`
- `data/run_status/latest.md`
- `data/run_status/latest.json`
- `data/<vehicle>/run_status/<source>_latest.json`

Do not use:

- historical merged CSV files as current recommendations
- source rank or score as purchase guidance
- raw Kijiji search-origin values as verified listing location
- `canonical_listing_id` as a VIN or cross-source physical-vehicle identity
- `accepted` as meaning verified or recommended

## Manual review guidance

Treat every accepted record as a candidate requiring direct verification. Confirm the live listing page, actual location, current price, mileage, vehicle identity, history, seller identity, condition, and availability.

Review these fields first:

- `quality_warnings`
- `review_status`
- `source_claim_status`
- `source_listing_id_status`
- `location_evidence_status`
- `distance_evidence_status`
- `year_evidence_status`
- `price_evidence_status`
- `mileage_evidence_status`
- `raw_record_ref`
- `normalized_record_ref`
- `source_completed_at_utc`

Phase 1 remains an interim system until source adapters, identity/lifecycle, retention, workflow hardening, and purpose-specific outputs are completed and proven.
