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
| LIM-001 | Critical | Controlled, not fixed | Kijiji parser stores search origin as location/address rather than verified listing geography | Canonical evidence preserves raw value but normalizes location/distance to null and labels it quarantined | Audit 05 |
| LIM-002 | Critical | Controlled, not fixed | Kijiji safety depends on exact runtime text replacement and `exec` | Patch-anchor tests and runtime safety adapter | Audit 05 |
| LIM-003 | Critical | Resolved | Source-boundary records were not traceable through raw, normalized, accepted, rejected, and parse-failure stages | Canonical schema v1 and enforced reconciliation | Audit 03 |
| LIM-004 | High | Implemented, validation pending | AutoTrader had no verified pagination contract | Direct page-size/offset adapter, total/short-page termination, repeated-page/max-page failure evidence, fixtures | Audit 04 |
| LIM-005 | High | Controlled, not fixed | Broad collector exceptions could silently skip per-record parse failures | AutoTrader response objects now preserve failures; Kijiji remains legacy | Audit 05 |
| LIM-006 | High | Implemented, validation pending | AutoTrader distance evidence did not distinguish routed from straight-line fallback | Explicit route/geodesic/unavailable methods and evidence statuses | Audit 04 |
| LIM-007 | High | Controlled, not fixed | `clean` means only that limited warning rules did not fire | Field/source evidence statuses and explicit documentation | Audits 04–05 |
| LIM-008 | High | Open | F-350 data lacks engine/idle hours, cab, box, SRW/DRW, and verified history enrichment | No values are invented | Audit 09 |
| LIM-009 | High | Controlled, not fixed | Source `listing_id` is not VIN or cross-source identity | Canonical ID is source-scoped and labelled `source_identifier_claim_not_vin`; merger disabled | Audit 06 |
| LIM-010 | High | Open | Price history lacks lifecycle states and older artifacts use week terminology | Supported review uses observation terms; underlying model remains compatibility history | Audit 06 |
| LIM-011 | High | Open | Timestamped CSV/history/evidence growth lacks retention boundaries | Optional high-volume vehicles paused; smoke artifacts expire after seven days | Audit 07 |
| LIM-012 | Medium | Open | Workflow installs unpinned dependencies | Tests run first | Audit 08 |
| LIM-013 | High | Resolved | Workflow scope was hard-coded and included unnecessary optional vehicles | Registry controls active vehicles; Audit 00 validation | Audit 00 |
| LIM-014 | High | Resolved | README contradicted actual operation | Current authorities and documentation tests | Audit 01 |
| LIM-015 | Medium | Resolved | Approved configs contained legacy `max_results` and `ranking_weights` | Schema v2 prohibits them | Audit 02 |
| LIM-016 | High | Resolved | Legacy collectors could receive/mutate approved config paths | Audit 02 isolated configs; AutoTrader now reads schema v2 directly and remains byte-identical | Audits 02, 04 |
| LIM-017 | Medium | Controlled, not fixed | Source output could contain rank/score fields | AutoTrader no longer emits either; supported review excludes them; Kijiji remains legacy | Audit 05 |
| LIM-018 | Medium | Controlled, not fixed | Source filters could reject unknown engine/fuel without evidence | AutoTrader adapter records explicit reasons; Kijiji remains legacy | Audit 05 |
| LIM-019 | Medium | Open | Kijiji location-ID mappings/fallbacks are not formally validated | Geography disabled for decisions | Audit 05 |
| LIM-020 | Medium | Resolved | Source criteria and locations were ambiguous shared flat configuration | Schema v2 separates and validates source settings | Audit 02 |
| LIM-021 | High | Controlled, not fixed | Source parsing lacked representative fixtures | AutoTrader has two-page and hostile fixtures; Kijiji fixtures remain pending | Audit 05 |
| LIM-022 | High | Open | Historical merger treats listing IDs like VINs and applies scoring | Workflow never calls it; explicitly disabled | Audit 06 |
| LIM-023 | Medium | Open | Generated data and implementation can share full-run branch/PR diffs | Audit 04 single-pair smoke uploads an artifact without committing | Audits 07–08 |
| LIM-024 | Medium | Controlled, not fixed | Collection/tests share one workflow and generated-data approval adds friction | Single-pair smoke makes no commit; acknowledgement prevents duplicate full collection | Audit 08 |
| LIM-025 | High | Open | No transparent F-350 candidate/enrichment/override model | Accepted rows remain manual-review candidates | Audit 09 |
| LIM-026 | Medium | Open | Purpose-specific RAM/Forester and Odyssey/Carnival outputs do not exist | Collection continues | Audit 10 |
| LIM-027 | Medium | Deferred by owner | F-150 and Tundra are not polished during core audit | Both remain paused with history retained | Audit 11 |
| LIM-028 | Medium | Controlled, not fixed | Legacy collectors contained flat-config mutation and ranking internally | AutoTrader behavior removed; Kijiji retains disposable projection and patched legacy code | Audit 05 |
| LIM-029 | Low | Open | Cadence and analysis profile are validated metadata but not fully executed | Current scheduled profile remains weekly | Audits 08–10 |
| LIM-030 | Critical | Controlled, not fixed | End-to-end request/response and pre-output record counts were not preserved | AutoTrader begins at response listing objects; Kijiji remains emitted-CSV scope | Audit 05 |
| LIM-031 | Medium | Open | Evidence retention, archival policy, and repository-growth bounds are undefined | Canonical and adapter evidence use latest paths; timestamped source/review artifacts remain | Audit 07 |
| LIM-032 | High | Open | Canonical listing IDs identify source-scoped claims, not physical vehicles or cross-source duplicates | ID status explicit; no destructive merge | Audit 06 |
| LIM-033 | Medium | Open | AutoTrader pagination completeness covers only configured queries/locations, not the entire national marketplace | Fetched scope and source completeness labels are explicit | Audits 08–10 |
| LIM-034 | Medium | Controlled, not fixed | AutoTrader distance depends on external geocoding and optional route service availability | Unavailable geography is rejected visibly; geodesic fallback is labelled as straight-line | Audit 08 |

## Interpretation notes

### Reconciliation boundaries

AutoTrader:

```text
autotrader_adapter_response_listing_objects
  = accepted_records + rejected_records + parse_failures
```

Kijiji until Audit 05:

```text
legacy_collector_emitted_csv_rows
  = accepted_records + rejected_records + parse_failures
```

Neither equation by itself proves full marketplace coverage.

### Controlled does not mean corrected

Kijiji geography/runtime patching, mixed-source completeness, identity, retention, and purpose-specific analysis remain incomplete even when an AutoTrader smoke run succeeds.

### Closure requirements

A limitation becomes `Resolved` only when the relevant package implements/removes the defect, structured tests cover it, required live validation is complete, authorities are updated, and the owner approves/merges.

## Newly discovered limitations

Material weaknesses discovered later must be added here and assigned to an approved future package without opportunistically expanding current scope.
