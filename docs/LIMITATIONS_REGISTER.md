# Current Limitations Register

## Purpose

This register preserves known repository weaknesses so they remain visible, prioritized and assigned to approved packages. A successful workflow does not close a limitation unless its acceptance criteria are explicitly met.

Severity:

- **Critical** — can materially misrepresent scope, evidence or decision data
- **High** — can materially reduce completeness, correctness or maintainability
- **Medium** — creates drift, reproducibility or operational risk
- **Low** — limited present impact but should be corrected deliberately

Status:

- **Open** — not fixed
- **Controlled, not fixed** — safeguards reduce harm but underlying defect remains
- **Resolved** — acceptance evidence exists
- **Deferred by owner** — intentionally postponed

## Register

| ID | Severity | Status | Limitation | Current control | Planned package |
|---|---|---|---|---|---|
| LIM-001 | Critical | Controlled, not fixed | Kijiji parser stores search origin as location/address rather than verified listing geography | Manual review blanks Kijiji location/distance and preserves search origin only as unverified evidence | Audit 05 |
| LIM-002 | Critical | Controlled, not fixed | Kijiji safety depends on exact runtime text replacement and `exec` | Patch-anchor count must equal one; tests compile patched current source | Audit 05 |
| LIM-003 | Critical | Open | Raw, accepted, rejected and parse-failure records are not reconcilable stages | Final CSV freshness and minimum schema are recorded | Audit 03, then Audits 04–05 |
| LIM-004 | High | Open | AutoTrader has no verified pagination contract | Post-parse result cap is disabled | Audit 04 |
| LIM-005 | High | Open | Broad collector exceptions can silently skip individual parse failures | Process output and final CSV are recorded | Audits 04–05 |
| LIM-006 | High | Controlled, not fixed | AutoTrader distance evidence does not distinguish routed from straight-line fallback reliably | Manual review labels method as legacy/ambiguous | Audit 04 |
| LIM-007 | High | Open | `clean` means only that a small warning set did not fire | README/dictionary limit interpretation | Audit 03 and source audits |
| LIM-008 | High | Open | F-350 data lacks engine/idle hours, cab, box, SRW/DRW and verified history enrichment | No values are invented | Audit 09 |
| LIM-009 | High | Controlled, not fixed | Source `listing_id` is not VIN or cross-source identity | Automated merger disabled | Audit 06 |
| LIM-010 | High | Open | Price history mislabels observations as weeks and lacks lifecycle states | Same-day duplication controlled | Audit 06 |
| LIM-011 | High | Open | Timestamped CSV/history growth lacks retention boundaries | Optional high-volume vehicles paused | Audit 07 |
| LIM-012 | Medium | Open | Workflow installs unpinned dependencies | Tests run first | Audit 08 |
| LIM-013 | High | Resolved | Workflow scope was hard-coded and included unnecessary optional vehicles | Registry controls active vehicles; Audit 00 proved 10 runs and no paused changes | Audit 00 |
| LIM-014 | High | Resolved | README contradicted actual operation | Replaced with current authority documents | Audit 01 |
| LIM-015 | Medium | Resolved | Approved configs contained legacy `max_results` and `ranking_weights` | Schema v2 prohibits them; compatibility values exist only in temporary runtime projection | Audit 02 |
| LIM-016 | High | Resolved | Legacy collectors could receive/mutate approved config paths | Runtime validates approved config, creates disposable projection and verifies approved bytes unchanged | Audit 02 |
| LIM-017 | Medium | Controlled, not fixed | Source CSVs may contain rank/score fields | Supported manual review excludes them | Audit 03 and source audits |
| LIM-018 | Medium | Open | Filters can reject unknown engine/fuel without rejection evidence | No completeness claim | Audit 03 and source audits |
| LIM-019 | Medium | Open | Kijiji location-ID mappings/fallbacks are not formally validated | Geography disabled for decisions | Audit 05 |
| LIM-020 | Medium | Resolved | Source criteria and search locations were ambiguous shared flat configuration | Schema v2 separates source make/model/location lists and validates non-empty, formatted, duplicate-free values | Audit 02 |
| LIM-021 | High | Open | Tests focus more on wrappers than real source fixtures | Phase 1/governance contracts covered | Audits 04–05 |
| LIM-022 | High | Open | Historical merger treats listing IDs like VINs and applies scoring | Workflow never calls it; explicitly disabled | Audit 06 |
| LIM-023 | Medium | Open | Generated data and implementation share branch/PR diffs | Data follow-up inspected separately | Audit 07–08 |
| LIM-024 | Medium | Open | Collection/tests share one workflow and generated-data approval adds friction | Acknowledgement path prevents duplicate collection | Audit 08 |
| LIM-025 | High | Open | No transparent F-350 candidate/enrichment/override model | All rows remain manual-review candidates | Audit 09 |
| LIM-026 | Medium | Open | Purpose-specific RAM/Forester and Odyssey/Carnival outputs do not exist | Collection continues | Audit 10 |
| LIM-027 | Medium | Deferred by owner | F-150 and Tundra are not polished during core audit | Both remain paused with history retained | Audit 11 |
| LIM-028 | Medium | Controlled, not fixed | Legacy collectors still contain flat-config mutation and ranking code internally | They receive only disposable projected configs; source audits must remove legacy behaviour | Audits 04–05 |
| LIM-029 | Low | Open | Cadence and analysis profile are validated metadata but not yet used for separate scheduling/output execution | Current profile is uniformly weekly; purpose outputs remain future work | Audits 08–10 |

## Interpretation notes

### Controlled does not mean corrected

Kijiji geography and runtime source rewriting remain controlled, not repaired. Legacy source ranking remains internal even though it cannot govern supported manual review.

### Successful run does not close data limitations

`SUCCESS` or `SUCCESS_WITH_WARNINGS` proves only that enabled registry source pairs met the Phase 1 health contract. It does not prove completeness, semantic accuracy, verified geography or purchase suitability.

### Closure requirements

A limitation becomes `Resolved` only when the relevant package implements/removes the affected capability, structured tests cover it, live validation is performed where external behaviour is involved, authorities are updated, and the owner approves/merges.

## Newly discovered limitations

Material weaknesses discovered later must be added here and assigned to an approved future package without opportunistically expanding current scope.
