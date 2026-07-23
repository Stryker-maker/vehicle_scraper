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
| LIM-008 | High | Implemented, validation pending | F-350 evidence did not expose engine/idle hours, cab, box, SRW/DRW, drivetrain, service-history, or prior-use claims | Audit 09 extracts source-text claims, preserves unknowns, and generates seller questions | Audit 09 |
| LIM-009 | High | Resolved | Source `listing_id` could be confused with VIN | `source_identifier_claim_not_vin` and explicit VIN evidence | Audit 06 |
| LIM-010 | High | Resolved | Price history used artificial week semantics and lacked lifecycle states | Actual timestamps, observations, lifecycle, and compact history | Audits 06–07 |
| LIM-011 | High | Resolved | Timestamped CSVs and state could grow without bound | Archive, observation, tombstone, ledger, and size limits | Audit 07 |
| LIM-012 | Medium | Resolved | Workflow dependencies were unpinned | Exact Python lock, Python 3.11.13, exact action SHAs, CI and smoke validation | Audit 08 |
| LIM-013 | High | Resolved | Workflow scope was hard-coded and included optional vehicles | Registry controls active vehicles | Audit 00 |
| LIM-014 | High | Resolved | README contradicted actual operation | Current authorities and documentation tests | Audit 01 |
| LIM-015 | Medium | Resolved | Approved configs contained legacy caps/weights | Config schema v2 prohibits them | Audit 02 |
| LIM-016 | High | Resolved | Collectors could mutate approved config paths | Direct adapters and byte-identical isolation checks | Audits 02, 04–05 |
| LIM-017 | Medium | Resolved | Source output could contain rank/score fields | Direct adapters and supported review exclude both | Audit 05 |
| LIM-018 | Medium | Controlled, not fixed | Unknown engine/fuel can cause source-specific criteria rejection | Explicit machine-readable reasons | Audit 05 |
| LIM-019 | Medium | Resolved | Kijiji location IDs/fallbacks were not validated | Six explicit hubs; unsupported labels fail | Audit 05 |
| LIM-020 | Medium | Resolved | Source criteria/locations were ambiguous flat config | Schema v2 separates source settings | Audit 02 |
| LIM-021 | High | Resolved | Source parsing lacked representative fixtures | Pagination and hostile fixtures for both adapters | Audit 05 |
| LIM-022 | High | Resolved | Historical merger treats listing IDs like VINs and ranks output | Disabled; active legacy output removed by retention | Audit 07 |
| LIM-023 | Medium | Resolved | Generated data and implementation could share unvalidated diffs | Separate data PR validation plus publication manifest | Audit 08 |
| LIM-024 | Medium | Resolved | Collection/tests shared one workflow | Reusable CI, separate data validator, collection-only workflow | Audit 08 |
| LIM-025 | High | Implemented, validation pending | No transparent F-350 investigation, seller-question, market-context, and owner-override model | Buyer schema v1 with explainable classifications and preserved computed/owner results | Audit 09 |
| LIM-026 | Medium | Open | Purpose-specific RAM/Forester and Odyssey/Carnival outputs do not exist | Collection continues | Audit 10 |
| LIM-027 | Medium | Deferred by owner | F-150 and Tundra are not polished during core audit | Both remain paused | Audit 11 |
| LIM-028 | Medium | Resolved | Active collectors contained flat-config mutation and ranking | Direct schema-v2 adapters; compatibility aliases only | Audit 05 |
| LIM-029 | Low | Controlled, not fixed | Registry cadence/analysis profile metadata is only partly operationalized | Weekly core schedule, explicit manual inputs, F-350 profile output | Audits 08–10 |
| LIM-030 | Critical | Resolved | Request/response and pre-output record counts were not preserved | Adapter boundaries reconcile returned objects | Audit 05 |
| LIM-031 | Medium | Resolved | Evidence retention, archival policy, and repository-growth bounds were undefined | Storage-retention schema v1 and hostile tests | Audit 07 |
| LIM-032 | High | Resolved | No cross-source duplicate confidence/lifecycle model | Explainable candidates and schema-v2 lifecycle | Audit 06 |
| LIM-033 | Medium | Open | Adapter and market context cover configured queries, not entire marketplaces | Explicit fetched scopes, comparable counts, and `configured_query_accepted_listing_claims_not_complete_market` | Audits 09–10 |
| LIM-034 | Medium | Controlled, not fixed | AutoTrader distance depends on external geocoding/route availability | Unavailable rejected visibly; geodesic labelled | Current control |
| LIM-035 | High | Resolved | Legacy active-vehicle history/merged files remained until retention | Governed full-run deletion with SHA-256 evidence | Audit 07 |
| LIM-036 | Medium | Resolved | Detailed deletion evidence could itself grow indefinitely | Latest 100 records plus cumulative count/bytes/digest | Audit 07 |
| LIM-037 | Medium | Resolved | Per-listing price observations could grow indefinitely | Latest 13 raw observations plus aggregate/digest evidence | Audit 07 |
| LIM-038 | Medium | Resolved | Retired listing tombstones could accumulate indefinitely | 500/source and 365-day limits with deletion evidence | Audit 07 |
| LIM-039 | Medium | Resolved | Generated-data commits could include paused/ungoverned/non-data paths | Staged-path validator rejects them | Audit 07 |
| LIM-040 | High | Resolved | Pull requests could trigger or ambiguously acknowledge collection/data behavior | Collectors have no PR trigger; data PRs receive real validation | Audit 08 |
| LIM-041 | Medium | Resolved | Collection anomalies lacked baseline-aware evidence and policy | Anomaly schema v1 with enforce/report-only policy | Audit 08 |
| LIM-042 | High | Resolved | Generated-data publication lacked run/path manifest and ref-race protection | Publication manifest, staged verification, whitespace and remote-ref gates | Audit 08 |
| LIM-043 | Medium | Open | Three consecutive scheduled active-profile runs have not yet proven unattended operation | Exact workflows and diagnostics are available; evidence must accumulate | Final audit completion |
| LIM-044 | High | Controlled, not fixed | Listing text cannot independently verify F-350 configuration, hours, history, prior use, or condition | Every extracted value remains unverified; missing evidence stays unknown; seller documents/inspection required | Audit 09/current control |
| LIM-045 | High | Controlled, not fixed | Asking-price quartiles and mileage regression are not sale-price or appraisal evidence | Cohort/sample/method/limits are visible; outputs explicitly deny appraisal and future-value authority | Audit 09/current control |
| LIM-046 | Medium | Implemented, validation pending | Owner notes or overrides could be mistaken for source evidence or erase computed results | Governed override schema preserves source, computed, override, reason, and effective classification separately | Audit 09 |
| LIM-047 | Medium | Controlled, not fixed | Seller questions identify evidence gaps but cannot obtain or verify answers | Questions remain prompts; manual contact, documents, history report, and inspection remain required | Audit 09/current control |

## Reconciliation boundaries

```text
autotrader_adapter_response_listing_objects
  = accepted_records + rejected_records + parse_failures

kijiji_adapter_json_ld_listing_objects
  = accepted_records + rejected_records + parse_failures
```

Neither equation proves full marketplace coverage.

## Workflow interpretation

Workflow success proves that configured deterministic, health, buyer-intelligence, anomaly, retention, and publication gates applicable to that run passed. It does not establish marketplace completeness, listing truth, purchase suitability, or absence of anomalies outside configured thresholds.

`report_only` is an explicit manual anomaly policy. It does not erase or downgrade the recorded anomaly evidence. Scheduled runs enforce critical anomalies.

## F-350 buyer-intelligence interpretation

Buyer-intelligence output is investigation support, not a verified vehicle dossier or recommendation. `source_text_reported_unverified`, evidence completeness, kilometres per engine hour, idle-hour percentage, observed price position, regression context, computed classification, seller question, and owner override each have different authority.

- Source-text claims remain unverified.
- Missing fields remain unknown.
- Evidence completeness measures presence only.
- Hour calculations provide usage context, not condition proof.
- Quartiles summarize current asking claims, not transactions.
- Regression summarizes a sample relationship, not future value.
- Computed classifications are explainable review labels, not ranks.
- Seller questions are prompts, not findings.
- Owner overrides alter review disposition only and do not rewrite evidence.

## Retention interpretation

Deletion and compaction digests prove governed accounting order. They do not reconstruct deleted raw files or compacted raw observations. Paused F-150/Tundra data remains outside the deletion boundary. A retired listing remains an operational inference and does not establish sold state.

## Closure requirements

A limitation becomes **Resolved** only when the relevant package implements or removes the defect, structured tests cover it, required live validation is complete, authorities are updated, and the owner approves and merges.

## Newly discovered limitations

Material weaknesses discovered later must be added here and assigned to an approved future package without opportunistically expanding current scope.
