# Current Limitations Register

## Purpose

This register keeps known weaknesses visible and assigned to approved packages. Passing tests does not independently verify source claims or close a limitation beyond its stated boundary.

Status values: **Open**, **Controlled, not fixed**, **Implemented, validation pending**, **Resolved**, and **Deferred by owner**.

## Register

| ID | Severity | Status | Limitation | Current control | Planned package |
|---|---|---|---|---|---|
| LIM-001 | Critical | Resolved | Legacy Kijiji parser stored search origin as location/address | Direct adapter uses listing-specific geography or unknown; Audit 05 live validation | Audit 05 |
| LIM-002 | Critical | Resolved | Kijiji safety depended on runtime text replacement and `exec` | Patcher removed; direct runtime merged | Audit 05 |
| LIM-003 | Critical | Resolved | Source-boundary records were not traceable through canonical stages | Canonical schema v1 and reconciliation | Audit 03 |
| LIM-004 | High | Resolved | AutoTrader lacked a verified pagination contract | Direct pagination, fixtures, and narrow validation | Audit 04 |
| LIM-005 | High | Resolved | Broad collector exceptions could silently skip record failures | Both adapters preserve raw parse failures and reasons | Audits 04–05 |
| LIM-006 | High | Resolved | AutoTrader distance conflated routed and straight-line values | Explicit route/geodesic/unavailable evidence | Audit 04 |
| LIM-007 | High | Controlled, not fixed | `clean` means only limited warning rules did not fire | Evidence statuses and manual verification | Ongoing |
| LIM-008 | High | Open | F-350 lacks engine/idle hours, cab, box, SRW/DRW, and verified history enrichment | No values invented | Audit 09 |
| LIM-009 | High | Implemented, validation pending | Source listing IDs could be mistaken for VIN/physical identity | Explicit source-ID/VIN separation and VIN evidence status | Audit 06 |
| LIM-010 | High | Implemented, validation pending | Price history lacked lifecycle and used artificial week terminology | Run-ID observations, actual elapsed time, lifecycle state; legacy history inactive | Audit 06 |
| LIM-011 | High | Open | Timestamped evidence/history growth lacks retention bounds | Optional vehicles paused; latest artifacts used | Audit 07 |
| LIM-012 | Medium | Open | Workflow dependencies remain unpinned | Tests run before collection | Audit 08 |
| LIM-013 | High | Resolved | Workflow scope included unnecessary optional vehicles | Registry controls active scope | Audit 00 |
| LIM-014 | High | Resolved | README contradicted operation | Current authorities and documentation tests | Audit 01 |
| LIM-015 | Medium | Resolved | Approved configs contained legacy result/ranking controls | Schema v2 prohibits them | Audit 02 |
| LIM-016 | High | Resolved | Collectors could mutate approved config | Direct schema-v2 adapters and byte-isolation checks | Audits 02, 04–05 |
| LIM-017 | Medium | Resolved | Source output could contain rank/score | Both adapters and supported review omit ranking | Audit 05 |
| LIM-018 | Medium | Resolved | Unknown engine/fuel exclusions could disappear | Both adapters preserve rejection reasons | Audit 05 |
| LIM-019 | Medium | Resolved | Kijiji location IDs/fallbacks were unvalidated | Explicit hub registry; unsupported labels fail; no `l0` fallback | Audit 05 |
| LIM-020 | Medium | Resolved | Source criteria/locations were ambiguous shared config | Schema v2 separates settings | Audit 02 |
| LIM-021 | High | Resolved | Source parsing lacked representative fixtures | Both adapters have pagination and hostile fixtures | Audits 04–05 |
| LIM-022 | High | Implemented, validation pending | Historical merger treated listing IDs like VINs and scored output | Merger disabled; supported duplicate candidates never merge records | Audit 06 |
| LIM-023 | Medium | Open | Generated data and implementation can share full-run diffs | Narrow smoke can upload without commit | Audits 07–08 |
| LIM-024 | Medium | Controlled, not fixed | Collection/tests share one workflow and approvals add friction | Narrow validation and acknowledgement-only follow-up | Audit 08 |
| LIM-025 | High | Open | No transparent F-350 enrichment/override model | Accepted rows remain manual-review candidates | Audit 09 |
| LIM-026 | Medium | Open | Purpose-specific RAM/Forester/Odyssey/Carnival outputs do not exist | Collection continues | Audit 10 |
| LIM-027 | Medium | Deferred by owner | F-150 and Tundra are not polished during core audit | Both remain paused | Audit 11 |
| LIM-028 | Medium | Resolved | Active collectors contained mutation/ranking internally | Direct governed adapters; legacy names are aliases | Audit 05 |
| LIM-029 | Low | Open | Cadence/analysis profile metadata are not fully executed | Weekly profile remains | Audits 08–10 |
| LIM-030 | Critical | Resolved | Pre-output request/response counts were not preserved | Both boundaries start at returned listing objects | Audit 05 |
| LIM-031 | Medium | Open | Evidence retention and repository-growth bounds are undefined | Latest artifacts plus unbounded state remain visible | Audit 07 |
| LIM-032 | High | Implemented, validation pending | Canonical IDs are source claims, not physical-vehicle identity | Fingerprints and explainable non-destructive duplicate candidates | Audit 06 |
| LIM-033 | Medium | Open | Adapter completeness covers configured queries, not whole marketplaces | Scope labels remain explicit | Audits 08–10 |
| LIM-034 | Medium | Controlled, not fixed | AutoTrader distance depends on external geocoding/routing availability | Unavailable rejected visibly; geodesic labelled straight-line | Audit 08 |
| LIM-035 | High | Implemented, validation pending | Missing/retired state could be misread as sold or source-confirmed removal | Operational inference labels, successful-run-only transitions, thresholds and reasons | Audit 06 |
| LIM-036 | Medium | Open | Identity/lifecycle state and observation history will grow without policy | No deletion added in Audit 06 | Audit 07 |

## Interpretation notes

### Reconciliation boundaries

```text
autotrader_adapter_response_listing_objects
  = accepted_records + rejected_records + parse_failures

kijiji_adapter_json_ld_listing_objects
  = accepted_records + rejected_records + parse_failures
```

Neither proves complete marketplace coverage.

### Identity boundaries

A format-valid VIN remains an unverified source claim. A duplicate candidate remains `candidate_only_not_merged`. `missing` and `retired` are operational inferences, not sold claims.

### Implemented does not mean merged

Audit 06 limitations remain `Implemented, validation pending` until exact-head CI, authority review, owner merge, and branch deletion are complete.

### Closure requirements

A limitation becomes `Resolved` only when implementation, relevant tests/evidence, authorities, and owner approval support the stated boundary.
