# Audit 07 — Storage, Retention and Repository Hygiene

## Status

Implemented on `ai/audit-07-storage-retention`; deterministic validation and owner merge remain pending.

## Purpose

Bound generated-data and identity-state growth without weakening current evidence, lifecycle continuity, source accounting, or the owner-approved active/paused vehicle boundary.

## Governed retention policy

### Current evidence

The following `*_latest` artifacts remain current-state evidence and are overwritten in place:

- source CSVs under `data/<vehicle>/latest/`
- adapter evidence under `data/<vehicle>/adapter_evidence/<source>/`
- canonical evidence under `data/<vehicle>/evidence/<source>/`
- source status under `data/<vehicle>/run_status/`
- identity/lifecycle current artifacts under `data/<vehicle>/identity_lifecycle/`
- supported manual review at `data/<vehicle>/manual_review/<vehicle>_manual_review_latest.csv`
- consolidated health and retention reports under `data/run_status/` and `data/retention/`

### Timestamped CSV archives

For each active vehicle:

- retain the eight newest timestamped AutoTrader source CSVs
- retain the eight newest timestamped Kijiji source CSVs
- retain the four newest timestamped manual-review CSVs

Older timestamped CSVs are deleted only during a governed full run.

### Identity and price history

Identity/lifecycle schema version `2` retains:

- total observation count
- first, previous, current, minimum, and maximum observed price
- first/last-seen and elapsed-time semantics
- the newest thirteen raw price observations per listing
- cumulative count and chained SHA-256 digest for compacted observations

The compaction digest proves ordered compacted content contributed to the retained state. It is not a raw-history reconstruction mechanism.

### Retired listing tombstones

Per source and vehicle:

- retain at most 500 retired listings
- remove retired listings more than 365 days past their last successful observation
- preserve cumulative deletion count/bytes, a chained SHA-256 deletion digest, and the latest 100 detailed deletion records

A retired lifecycle state remains an operational inference, not proof that a listing sold.

### Legacy generated files

For active vehicles, the governed retention pass removes:

- `price_history_autotrader.json`
- `price_history_kijiji.json`
- historical `merged/*.csv`

Before deletion, each file receives a record containing path, category, reason, size, SHA-256, run ID, and deletion time. Paused F-150 and Tundra data is not touched.

### Repository growth gates

The managed active-data boundary is:

- maximum individual managed file: 50 MiB
- maximum active managed data: 500 MiB

A full run fails before commit when these bounds or archive limits are violated.

## Generated-data commit discipline

A full scheduled or explicitly approved manual run must:

1. complete collection and evidence reporting
2. pass the source-health gate
3. apply retention
4. verify retention
5. stage only `data/`
6. run `storage_retention.py validate-staged` to reject paused-vehicle, ungoverned-vehicle, or non-data paths
7. print the staged diff summary
8. commit only when a governed data diff exists

Single-pair smoke validation remains non-committing and retains its workflow artifact for seven days.

## Deletion evidence limits

Detailed deletion ledgers are intentionally bounded. Cumulative counts, bytes, and chained digests survive after older detailed records roll out. The ledger therefore proves governed deletion accounting without becoming another unbounded archive.

## Acceptance gate

Audit 07 is acceptable only when deterministic tests prove:

- archive pruning keeps exact configured counts
- current/latest evidence survives
- paused vehicles remain untouched
- legacy active-vehicle files are removed with SHA-256 deletion evidence
- deletion ledgers remain bounded and cumulative
- price observations compact without changing total, first/current, or same-run semantics
- schema-v1 lifecycle state migrates to schema v2
- old/excess retired listings are pruned with bounded evidence
- staged generated-data paths reject paused, ungoverned, and non-data changes
- workflow health and retention gates run before any data commit
- no source query, parser, pagination, geography, distance, ranking, buyer-intelligence, or optional-vehicle scope changes occur

## Stop conditions

Stop and revise before merge if:

- a current `*_latest` evidence artifact is deleted
- a paused F-150 or Tundra data path changes
- lifecycle continuity or first/current price semantics are lost
- deletion occurs without path, size, reason, and SHA-256 evidence
- retention can delete files outside the explicit governed patterns
- staged generated data can include non-data, paused, or ungoverned paths
- the implementation absorbs Audit 08 workflow architecture, Audit 09 buyer intelligence, Audit 10 purpose outputs, or Audit 11 optional vehicles

## Non-scope

Audit 07 does not lock dependencies, redesign the workflow into separate workflows, change collection cadence, add anomaly diagnostics, alter source collection, rank vehicles, enrich F-350 listings, create purpose-specific analytics, verify sold state, or re-enable optional vehicles.
