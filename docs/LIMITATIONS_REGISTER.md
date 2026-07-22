# Current Limitations Register

## Purpose

This register preserves known repository weaknesses so they remain visible, prioritized, and assigned to approved packages. A successful workflow does not close a limitation unless its acceptance criteria are explicitly met.

Severity:

- **Critical** — can materially misrepresent scope, evidence, or decision data
- **High** — can materially reduce completeness, correctness, or maintainability
- **Medium** — creates drift, reproducibility, or operational risk
- **Low** — limited present impact but should be corrected deliberately

Status:

- **Open** — not fixed
- **Controlled, not fixed** — safeguards reduce harm but underlying defect remains
- **Resolved** — acceptance evidence exists for the stated boundary
- **Deferred by owner** — intentionally postponed

## Register

| ID | Severity | Status | Limitation | Current control | Planned package |
|---|---|---|---|---|---|
| LIM-001 | Critical | Controlled, not fixed | Kijiji parser stores search origin as location/address rather than verified listing geography | Canonical evidence preserves the raw value but normalizes location/distance to null and labels it quarantined | Audit 05 |
| LIM-002 | Critical | Controlled, not fixed | Kijiji safety depends on exact runtime text replacement and `exec` | Patch-anchor tests and runtime safety adapter | Audit 05 |
| LIM-003 | Critical | Resolved | Collector-emitted rows were not traceable through raw, normalized, accepted, rejected, and parse-failure stages | Canonical schema v1 artifacts and enforced reconciliation equation | Audit 03 |
| LIM-004 | High | Open | AutoTrader has no verified pagination contract | Post-parse result cap is disabled | Audit 04 |
| LIM-005 | High | Open | Broad collector exceptions can silently skip individual source parse failures before CSV output | Canonical layer begins at emitted CSV and explicitly labels source completeness unproven | Audits 04–05 |
| LIM-006 | High | Controlled, not fixed | AutoTrader distance evidence does not distinguish routed from straight-line fallback reliably | Canonical field status remains `legacy_method_not_yet_disambiguated` | Audit 04 |
| LIM-007 | High | Controlled, not fixed | `clean` means only that a small warning set did not fire | Manual review includes source-claim and field-evidence statuses; documentation limits interpretation | Audits 04–05 |
| LIM-008 | High | Open | F-350 data lacks engine/idle hours, cab, box, SRW/DRW, and verified history enrichment | No values are invented | Audit 09 |
| LIM-009 | High | Controlled, not fixed | Source `listing_id` is not VIN or cross-source identity | Canonical ID is source-scoped and status explicitly says `source_identifier_claim_not_vin`; merger remains disabled | Audit 06 |
| LIM-010 | High | Open | Price history mislabels observations as weeks and lacks lifecycle states | Supported review renames values to observation-based terms; underlying history model remains legacy | Audit 06 |
| LIM-011 | High | Open | Timestamped CSV/history/evidence growth lacks retention boundaries | Optional high-volume vehicles paused; evidence writes latest artifacts only | Audit 07 |
| LIM-012 | Medium | Open | Workflow installs unpinned dependencies | Tests run first | Audit 08 |
| LIM-013 | High | Resolved | Workflow scope was hard-coded and included unnecessary optional vehicles | Registry controls active vehicles; Audit 00 proved 10 runs and no paused changes | Audit 00 |
| LIM-014 | High | Resolved | README contradicted actual operation | Current authority documents and documentation-contract tests | Audit 01 |
| LIM-015 | Medium | Resolved | Approved configs contained legacy `max_results` and `ranking_weights` | Schema v2 prohibits them; compatibility values exist only in temporary runtime projection | Audit 02 |
| LIM-016 | High | Resolved | Legacy collectors could receive/mutate approved config paths | Disposable projection plus byte-for-byte config isolation evidence | Audit 02 |
| LIM-017 | Medium | Controlled, not fixed | Source CSVs and collector console output may contain rank/score fields | Supported manual review is built from canonical accepted records and contains neither field | Audits 04–05 |
| LIM-018 | Medium | Open | Legacy source filters can reject unknown engine/fuel before canonical evidence exists | Canonical post-CSV exclusions are visible, but pre-CSV filtering remains unproven | Audits 04–05 |
| LIM-019 | Medium | Open | Kijiji location-ID mappings/fallbacks are not formally validated | Geography disabled for decisions | Audit 05 |
| LIM-020 | Medium | Resolved | Source criteria and search locations were ambiguous shared flat configuration | Schema v2 separates and validates source settings | Audit 02 |
| LIM-021 | High | Open | Tests focus more on wrappers than real source fixtures | Canonical hostile tests cover boundary semantics | Audits 04–05 |
| LIM-022 | High | Open | Historical merger treats listing IDs like VINs and applies scoring | Workflow never calls it; explicitly disabled | Audit 06 |
| LIM-023 | Medium | Open | Generated data and implementation share branch/PR diffs | Data follow-up inspected separately | Audits 07–08 |
| LIM-024 | Medium | Open | Collection/tests share one workflow and generated-data approval adds friction | Acknowledgement path prevents duplicate collection | Audit 08 |
| LIM-025 | High | Open | No transparent F-350 candidate/enrichment/override model | All accepted rows remain manual-review candidates | Audit 09 |
| LIM-026 | Medium | Open | Purpose-specific RAM/Forester and Odyssey/Carnival outputs do not exist | Collection continues | Audit 10 |
| LIM-027 | Medium | Deferred by owner | F-150 and Tundra are not polished during core audit | Both remain paused with history retained | Audit 11 |
| LIM-028 | Medium | Controlled, not fixed | Legacy collectors still contain flat-config mutation and ranking code internally | They receive only disposable projected configs | Audits 04–05 |
| LIM-029 | Low | Open | Cadence and analysis profile are validated metadata but not yet used for separate scheduling/output execution | Current profile is uniformly weekly | Audits 08–10 |
| LIM-030 | Critical | Open | End-to-end marketplace fetch counts, response payloads, and pre-CSV parse failures are not preserved | Reconciliation scope is explicitly `legacy_collector_emitted_csv_rows` and never represented as marketplace completeness | Audits 04–05 |
| LIM-031 | Medium | Open | Evidence retention, archival policy, and repository-growth bounds are not defined | Current canonical artifacts use `latest` paths; timestamped source/review artifacts remain | Audit 07 |
| LIM-032 | High | Open | Canonical listing IDs identify a source-scoped listing claim, not a physical vehicle or cross-source duplicate | ID derivation and status are explicit; no destructive merge occurs | Audit 06 |

## Interpretation notes

### Canonical reconciliation boundary

Audit 03 guarantees that no row emitted by a legacy collector disappears after the canonical boundary:

```text
fetched_records = accepted_records + rejected_records + parse_failures
```

It does not guarantee that the collector fetched or emitted every marketplace record. That separate critical limitation remains open as LIM-030.

### Controlled does not mean corrected

Kijiji geography, runtime source rewriting, AutoTrader distance ambiguity, and internal legacy ranking remain controlled, not repaired.

### Successful run does not close source limitations

`SUCCESS` or `SUCCESS_WITH_WARNINGS` proves that enabled registry source pairs met the current runtime, config-isolation, freshness, and canonical-reconciliation health contract. It does not prove marketplace completeness, semantic accuracy, verified geography, vehicle identity, or purchase suitability.

### Closure requirements

A limitation becomes `Resolved` only when the relevant package implements or removes the affected capability, structured tests cover it, live validation is performed where external behaviour is involved, authorities are updated, and the owner approves/merges.

## Newly discovered limitations

Material weaknesses discovered later must be added here and assigned to an approved future package without opportunistically expanding current scope.
