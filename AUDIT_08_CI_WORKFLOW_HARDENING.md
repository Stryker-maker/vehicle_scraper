# Audit 08 — CI and Workflow Hardening

## Status

Implemented on `ai/audit-08-ci-workflow-hardening`; exact-head CI and owner merge remain pending.

## Purpose

Make repository validation, collection, anomaly review, and generated-data publication reproducible and independently testable without changing marketplace collection behavior or absorbing buyer-intelligence scope.

## Workflow separation

Audit 08 defines three workflows with independent triggers and permissions:

- `.github/workflows/ci.yml` — reusable deterministic code validation for non-data pull-request changes, manual CI, and collection preflight
- `.github/workflows/generated-data.yml` — pull-request validation for `data/**` changes
- `.github/workflows/scrape.yml` — schedule/manual collection only; it has no pull-request trigger and cannot begin until reusable CI preflight passes

Data-only changes no longer receive a synthetic success acknowledgement in place of validation.

## Dependency lock

Python execution is fixed to Python `3.11.13`. `requirements.lock` contains exact `==` pins for every direct collector library and its runtime dependencies. `dependency_lock.py` rejects empty locks, ranges, URLs, and duplicate package entries. CI and collection install the same lock and run `pip check`.

GitHub-owned actions are pinned to exact 40-character commit SHAs rather than moving major-version tags.

## Collection inputs and cadence

The scheduled full run remains Monday at `08:00 UTC`.

Manual collection inputs are explicit:

- `collection_scope`: `full` or `single_pair`
- `vehicle_key`: one of the five active governed vehicles
- `source`: `autotrader` or `kijiji`
- `publish_generated_data`: explicit manual publication authority
- `anomaly_policy`: `enforce` or `report_only`
- `operator_note`: optional context

`workflow_control.py` builds the plan from `vehicle_registry.json`. A paused or unknown vehicle, disabled source, unsupported scope, empty plan, or multi-row single-pair plan fails before collection.

## Anomaly diagnostics

A full run snapshots the previously committed health report before collection and writes:

```text
data/run_status/anomalies_latest.json
data/run_status/anomalies_latest.md
```

Anomaly schema version `1` reports:

- unhealthy source runs
- incomplete pagination and failed-page evidence when present in current health input
- severe accepted/fetched count collapses
- material accepted/fetched count shifts
- elevated parse-failure rates
- material quality-warning growth
- missing or same-run baseline status

Critical anomalies block scheduled publication and manual publication under `enforce`. `report_only` preserves the report and permits an explicitly chosen manual run to continue. It does not suppress or rewrite anomaly evidence.

## Generated-data publication discipline

A publishable full run must pass, in order:

1. reusable deterministic CI preflight
2. registry/config validation
3. governed collection plan
4. source execution and canonical/lifecycle evidence
5. manual-review and consolidated health generation
6. source-health gate
7. anomaly policy gate
8. retention apply and verify
9. staged-path validation
10. publication manifest preparation and staged-manifest verification
11. `git diff --cached --check`
12. remote-ref unchanged check

`generated_data_publish.py` writes schema version `1` at:

```text
data/run_status/publication_latest.json
```

The manifest records run ID, source SHA, target ref, workflow event, exact published paths, and change-type counts. Publication is skipped when no governed data change exists. A remote branch change during collection blocks the push.

## Generated-data pull-request validation

`.github/workflows/generated-data.yml` validates the complete `data/**` pull-request diff against:

- active/paused registry scope
- storage-retention bounds
- source-status schema and success state when source status changes
- consolidated health integrity when health changes
- anomaly schema and absence of critical anomalies when anomaly evidence changes
- publication-manifest schema and path membership when the manifest changes

Failure evidence is uploaded for three days. Full-run diagnostics are retained for fourteen days; single-pair smoke evidence remains seven days.

## Acceptance gate

Audit 08 is acceptable only when deterministic tests prove:

- code CI, generated-data validation, and collection are separate
- collection has no pull-request trigger
- collection cannot begin before reusable CI succeeds
- every GitHub-owned action uses an exact SHA
- every Python requirement is exactly pinned
- manual scope/vehicle/source inputs are registry-governed
- paused vehicles cannot enter a single-pair plan
- anomaly severity and baseline behavior are deterministic
- critical anomaly enforcement is visible
- publication manifests exactly match staged governed data
- non-data staged publication is rejected
- generated-data pull requests receive real integrity validation
- source queries, parsers, pagination, geography, distance, criteria, and ranking remain unchanged

## Stop conditions

Stop and revise before merge if:

- a pull-request event can execute a collector
- a collection run can bypass deterministic CI preflight
- a moving action tag or dependency range remains
- a paused vehicle can enter collection or publication
- critical anomalies can disappear without explicit policy evidence
- a publication manifest can diverge from staged paths
- generated data can push after the remote ref changes
- the package changes marketplace behavior or absorbs Audit 09, 10, or 11 scope

## Non-scope

Audit 08 does not change vehicle criteria, source locations, request construction, parsing, filtering, pagination, evidence equations, identity rules, lifecycle thresholds, retention limits, buyer ranking, F-350 enrichment, purpose-specific analytics, sold-state verification, or optional-vehicle state.
