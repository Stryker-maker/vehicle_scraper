# Current Limitations Register

## Purpose

This register preserves known weaknesses so they remain visible, prioritized, and assigned to approved packages. A successful workflow does not close a limitation unless its acceptance criteria are met.

Severity:

- **Critical** — can materially misrepresent scope, evidence, or decision data
- **High** — can materially reduce completeness, correctness, or maintainability
- **Medium** — creates drift, reproducibility, or operational risk
- **Low** — limited present impact but should be corrected deliberately

Status:

- **Open** — not fixed
- **Controlled, not fixed** — safeguards or one source reduce harm but the full defect remains
- **Implemented, validation pending** — code/tests exist but required live/owner evidence is incomplete
- **Resolved** — acceptance evidence exists for the stated boundary
- **Deferred by owner** — intentionally postponed

## Register

| ID | Severity | Status | Limitation | Current control | Planned package |
|---|---|---|---|---|---|
| LIM-001 | Critical | Implemented, validation pending | Legacy Kijiji parser stored search origin as location/address | Direct adapter accepts only listing-specific structured geography or unknown; query origin is provenance | Audit 05 |
| LIM-002 | Critical | Implemented, validation pending | Kijiji safety depended on exact runtime text replacement and `exec` | Patcher removed; direct adapter/runtime and compatibility shim implemented | Audit 05 |
| LIM-003 | Critical | Resolved | Source-boundary records were not traceable through canonical stages | Canonical schema v1 and enforced reconciliation | Audit 03 |
| LIM-004 | High | Resolved | AutoTrader had no verified pagination contract | Direct page-size/offset adapter, fixtures, and successful narrow validation | Audit 04 |
| LIM-005 | High | Implemented, validation pending | Broad collector exceptions could silently skip per-record parse failures | Both adapters preserve parse failures and raw payload evidence | Audit 05 |
| LIM-006 | High | Resolved | AutoTrader distance evidence did not distinguish routed from straight-line fallback | Explicit route/geodesic/unavailable methods validated live | Audit 04 |
| LIM-007 | High | Controlled, not fixed | `clean` means only that limited warning rules did not fire | Field/source evidence statuses and explicit documentation | Audits 04–05 |
| LIM-008 | High | Open | F-350 data lacks engine/idle hours, cab, box, SRW/DRW, and verified history enrichment | No values are invented | Audit 09 |
| LIM-009 | High | Controlled, not fixed | Source `listing_id` is not VIN or cross-source identity | Canonical ID is source-scoped and labelled `source_identifier_claim_not_vin`; merger disabled | Audit 06 |
| LIM-010 | High | Open | Price history lacks lifecycle states and older artifacts use week terminology | Supported review uses observation terms; underlying model remains compatibility history | Audit 06 |
| LIM-011 | High | Open | Timestamped CSV/history/evidence growth lacks retention boundaries | Optional high-volume vehicles paused; smoke artifacts expire after seven days | Audit 07 |
| LIM-012 | Medium | Open | Workflow installs unpinned dependencies | Tests run first | Audit 08 |
| LIM-013 | High | Resolved | Workflow scope was hard-coded and included unnecessary optional vehicles | Registry controls active vehicles; Audit 00 validation | Audit 00 |
| LIM-014 | High | Resolved | README contradicted actual operation | Current authorities and documentation tests | Audit 01 |
| LIM-015 | Medium | Resolved | Approved configs contained legacy `max_results` and `ranking_weights` | Schema v2 prohibits them | Audit 02 |
| LIM-016 | High | Resolved | Collectors could receive/mutate approved config paths | Both direct adapters read schema v2 and verify byte-identical config isolation | Audits 02, 04–05 |
| LIM-017 | Medium | Implemented, validation pending | Source output could contain rank/score fields | Both direct adapters omit rank/score; supported review excludes them | Audit 05 |
| LIM-018 | Medium | Implemented, validation pending | Source filters could reject unknown engine/fuel without evidence | Both adapters preserve explicit rejection reasons | Audit 05 |
| LIM-019 | Medium | Implemented, validation pending | Kijiji location-ID mappings/fallbacks were not formally validated | Six explicit Cars & Trucks hubs; unsupported labels fail and no `l0` fallback exists | Audit 05 |
| LIM-020 | Medium | Resolved | Source criteria and locations were ambiguous shared flat configuration | Schema v2 separates and validates source settings | Audit 02 |
| LIM-021 | High | Implemented, validation pending | Source parsing lacked representative fixtures | AutoTrader and Kijiji both have pagination and hostile fixtures | Audit 05 |
| LIM-022 | High | Open | Historical merger treats listing IDs like VINs and applies scoring | Workflow never calls it; explicitly disabled | Audit 06 |
| LIM-023 | Medium | Open | Generated data and implementation can share full-run branch/PR diffs | Single-pair smoke uploads an artifact without committing | Audits 07–08 |
| LIM-024 | Medium | Controlled, not fixed | Collection/tests share one workflow and generated-data approval adds friction | Single-pair smoke makes no commit; acknowledgement prevents duplicate full collection | Audit 08 |
| LIM-025 | High | Open | No transparent F-350 candidate/enrichment/override model | Accepted rows remain manual-review candidates | Audit 09 |
| LIM-026 | Medium | Open | Purpose-specific RAM/Forester and Odyssey/Carnival outputs do not exist | Collection continues | Audit 10 |
| LIM-027 | Medium | Deferred by owner | F-150 and Tundra are not polished during core audit | Both remain paused; dormant Kijiji hubs are normalized only | Audit 11 |
| LIM-028 | Medium | Resolved | Active collectors contained flat-config mutation and ranking internally | Both active source paths use direct schema-v2 adapters; legacy command names are governed shims | Audit 05 |
| LIM-029 | Low | Open | Cadence and analysis profile are validated metadata but not fully executed | Current scheduled profile remains weekly | Audits 08–10 |
| LIM-030 | Critical | Implemented, validation pending | End-to-end request/response and pre-output record counts were not preserved | Both source boundaries begin at returned listing objects and reconcile | Audit 05 |
| LIM-031 | Medium | Open | Evidence retention, archival policy, and repository-growth bounds are undefined | Canonical and adapter evidence use latest paths; timestamped source/review artifacts remain | Audit 07 |
| LIM-032 | High | Open | Canonical listing IDs identify source-scoped claims, not physical vehicles or cross-source duplicates | ID status explicit; no destructive merge | Audit 06 |
| LIM-033 | Medium | Open | Adapter completeness covers configured queries/locations, not the entire marketplace | Fetched scope and source completeness labels are explicit | Audits 08–10 |
| LIM-034 | Medium | Controlled, not fixed | AutoTrader distance depends on external geocoding and optional route service availability | Unavailable geography is rejected visibly; geodesic fallback is labelled as straight-line | Audit 08 |

## Interpretation notes

### Reconciliation boundaries

AutoTrader:

```text
autotrader_adapter_response_listing_objects
  = accepted_records + rejected_records + parse_failures
```

Kijiji after Audit 05 implementation:

```text
kijiji_adapter_json_ld_listing_objects
  = accepted_records + rejected_records + parse_failures
```

Neither equation by itself proves full marketplace coverage.

### Implemented does not mean validated

Kijiji direct execution, geography handling, hub validation, and reconciliation remain `Implemented, validation pending` until the narrow live run, owner review, and merge are complete.

### Closure requirements

A limitation becomes `Resolved` only when the relevant package implements/removes the defect, structured tests cover it, required live validation is complete, authorities are updated, and the owner approves/merges.

## Newly discovered limitations

Material weaknesses discovered later must be added here and assigned to an approved future package without opportunistically expanding current scope.
