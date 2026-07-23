# Current Limitations Register

## Purpose

This register preserves known weaknesses so they remain visible, prioritized, and assigned to approved packages. A successful workflow does not close a limitation unless its acceptance criteria are met.

Status values are **Open**, **Controlled, not fixed**, **Implemented, validation pending**, **Resolved**, and **Deferred by owner**.

## Register

| ID | Severity | Status | Limitation | Current control | Planned package |
|---|---|---|---|---|---|
| LIM-001 | Critical | Resolved | Legacy Kijiji parser stored search origin as location/address | Direct adapter accepts listing-specific geography or unknown | Audit 05 |
| LIM-002 | Critical | Resolved | Kijiji safety depended on runtime text replacement and `exec` | Patcher removed; direct governed adapter/runtime | Audit 05 |
| LIM-003 | Critical | Resolved | Source-boundary records were not traceable through canonical stages | Canonical schema v1 and reconciliation | Audit 03 |
| LIM-004 | High | Resolved | AutoTrader had no verified pagination contract | Direct page-size/offset adapter and live validation | Audit 04 |
| LIM-005 | High | Resolved | Per-record parse failures could disappear | Both adapters preserve raw parse-failure evidence | Audit 05 |
| LIM-006 | High | Resolved | AutoTrader distance evidence was ambiguous | Route/geodesic/unavailable evidence contracts | Audit 04 |
| LIM-007 | High | Controlled, not fixed | `clean` means only limited warning rules did not fire | Field/source evidence statuses and manual review | Audits 04–05 |
| LIM-008 | High | Open | F-350 lacks engine/idle hours, cab, box, SRW/DRW, and verified history enrichment | No values invented | Audit 09 |
| LIM-009 | High | Resolved | Source `listing_id` could be confused with VIN | `source_identifier_claim_not_vin` and explicit VIN evidence | Audit 06 |
| LIM-010 | High | Resolved | Price history used artificial week semantics and lacked lifecycle states | Actual timestamps, observations, and lifecycle model | Audit 06 |
| LIM-011 | High | Implemented, validation pending | Timestamped CSVs and state could grow without bound | Audit 07 archive/state limits and verification | Audit 07 |
| LIM-012 | Medium | Open | Workflow dependencies remain unpinned | Tests run before collection | Audit 08 |
| LIM-013 | High | Resolved | Workflow scope was hard-coded and included optional vehicles | Registry controls active vehicles | Audit 00 |
| LIM-014 | High | Resolved | README contradicted actual operation | Current authorities and documentation tests | Audit 01 |
| LIM-015 | Medium | Resolved | Approved configs contained legacy caps/weights | Config schema v2 prohibits them | Audit 02 |
| LIM-016 | High | Resolved | Collectors could mutate approved config paths | Direct adapters and byte-identical isolation checks | Audits 02, 04–05 |
| LIM-017 | Medium | Resolved | Source output could contain rank/score fields | Direct adapters and supported review exclude both | Audit 05 |
| LIM-018 | Medium | Controlled, not fixed | Unknown engine/fuel can cause source-specific criteria rejection | Explicit machine-readable reasons | Audit 05 |
| LIM-019 | Medium | Resolved | Kijiji location IDs/fallbacks were not validated | Six explicit hubs; unsupported labels fail | Audit 05 |
| LIM-020 | Medium | Resolved | Source criteria/locations were ambiguous flat config | Schema v2 separates source settings | Audit 02 |
| LIM-021 | High | Resolved | Source parsing lacked representative fixtures | Pagination and hostile fixtures for both adapters | Audit 05 |
| LIM-022 | High | Implemented, validation pending | Historical merger treats listing IDs like VINs and ranks output | Disabled and removed from supported generated data by retention | Audit 07 |
| LIM-023 | Medium | Controlled, not fixed | Generated data and implementation can share full-run branch/PR diffs | Non-committing smoke; staged data-path gate | Audits 07–08 |
| LIM-024 | Medium | Controlled, not fixed | Collection/tests share one workflow | Health/retention pre-commit gates; final split deferred | Audit 08 |
| LIM-025 | High | Open | No transparent F-350 investigation/override model | Accepted rows remain manual-review candidates | Audit 09 |
| LIM-026 | Medium | Open | Purpose-specific RAM/Forester and Odyssey/Carnival outputs do not exist | Collection continues | Audit 10 |
| LIM-027 | Medium | Deferred by owner | F-150 and Tundra are not polished during core audit | Both remain paused | Audit 11 |
| LIM-028 | Medium | Resolved | Active collectors contained flat-config mutation and ranking | Direct schema-v2 adapters; compatibility aliases only | Audit 05 |
| LIM-029 | Low | Open | Cadence/analysis profile metadata is not fully executed | Weekly core profile only | Audits 08–10 |
| LIM-030 | Critical | Resolved | Request/response and pre-output record counts were not preserved | Adapter boundaries reconcile returned objects | Audit 05 |
| LIM-031 | Medium | Implemented, validation pending | Evidence retention, archival policy, and repository-growth bounds were undefined | Storage-retention schema v1 and deterministic tests | Audit 07 |
| LIM-032 | High | Resolved | No cross-source duplicate confidence/lifecycle model | Explainable candidates and schema-v2 lifecycle | Audit 06 |
| LIM-033 | Medium | Open | Adapter completeness covers configured queries, not entire marketplaces | Explicit fetched scopes and completeness labels | Audits 08–10 |
| LIM-034 | Medium | Controlled, not fixed | AutoTrader distance depends on external geocoding/route availability | Unavailable rejected visibly; geodesic labelled | Audit 08 |
| LIM-035 | High | Implemented, validation pending | Legacy active-vehicle history/merged files remain in repository until a retention pass | Full run removes them with SHA-256 deletion evidence | Audit 07 |
| LIM-036 | Medium | Implemented, validation pending | Detailed deletion evidence could itself grow indefinitely | Latest 100 records plus cumulative count/bytes/digest | Audit 07 |
| LIM-037 | Medium | Implemented, validation pending | Per-listing price observations could grow indefinitely | Latest 13 raw observations plus aggregate/digest evidence | Audit 07 |
| LIM-038 | Medium | Implemented, validation pending | Retired listing tombstones could accumulate indefinitely | 500/source and 365-day limits with deletion evidence | Audit 07 |
| LIM-039 | Medium | Implemented, validation pending | Generated-data commits could include paused/ungoverned/non-data paths | Staged-path validator rejects them before commit | Audit 07 |

## Reconciliation boundaries

AutoTrader:

```text
autotrader_adapter_response_listing_objects
  = accepted_records + rejected_records + parse_failures
```

Kijiji:

```text
kijiji_adapter_json_ld_listing_objects
  = accepted_records + rejected_records + parse_failures
```

Neither equation proves full marketplace coverage.

## Retention interpretation

Audit 07 deletion and compaction digests prove governed accounting order. They do not reconstruct deleted raw files or compacted raw observations. Paused F-150/Tundra data remains outside the deletion boundary. A retired listing remains an operational inference and does not establish sold state.

## Closure requirements

A limitation becomes **Resolved** only when the relevant package implements or removes the defect, structured tests cover it, required live validation is complete, authorities are updated, and the owner approves and merges.

## Newly discovered limitations

Material weaknesses discovered later must be added here and assigned to an approved future package without opportunistically expanding current scope.
