# Current Limitations Register

## Purpose

This register preserves known weaknesses so they remain visible, prioritized, and assigned. Status values are **Open**, **Controlled, not fixed**, **Implemented, validation pending**, **Resolved**, and **Deferred by owner**.

## Register

| ID | Severity | Status | Limitation | Current control | Planned package |
|---|---|---|---|---|---|
| LIM-001 | Critical | Resolved | Legacy Kijiji parser stored search origin as location/address | Direct adapter accepts listing-specific geography or unknown | Audit 05 |
| LIM-002 | Critical | Resolved | Kijiji safety depended on runtime text replacement and `exec` | Direct governed adapter/runtime | Audit 05 |
| LIM-003 | Critical | Resolved | Source records lacked canonical traceability | Canonical schema v1 and reconciliation | Audit 03 |
| LIM-004 | High | Resolved | AutoTrader lacked verified pagination | Direct page-size/offset adapter and live validation | Audit 04 |
| LIM-005 | High | Resolved | Parse failures could disappear | Both adapters preserve parse-failure evidence | Audit 05 |
| LIM-006 | High | Resolved | AutoTrader distance evidence was ambiguous | Route/geodesic/unavailable contracts | Audit 04 |
| LIM-007 | High | Controlled, not fixed | `clean` reflects only configured warning rules | Field/source evidence and manual review | Current control |
| LIM-008 | High | Resolved | F-350 configuration/history/use evidence was absent from investigation output | Audit 09 unverified extraction, unknown preservation, questions | Audit 09 |
| LIM-009 | High | Resolved | Source listing IDs could be confused with VIN | Explicit source-ID/VIN separation | Audit 06 |
| LIM-010 | High | Resolved | Price history used artificial week semantics | Actual observations and lifecycle | Audits 06–07 |
| LIM-011 | High | Resolved | Generated data/state could grow without bound | Archive, observation, tombstone, ledger, and size limits | Audit 07 |
| LIM-012 | Medium | Resolved | Dependencies were unpinned | Exact Python/dependency/action pins | Audit 08 |
| LIM-013 | High | Resolved | Workflow scope included optional vehicles | Registry controls active scope | Audit 00 |
| LIM-014 | High | Resolved | README contradicted operation | Current authorities and tests | Audit 01 |
| LIM-015 | Medium | Resolved | Approved configs contained legacy caps/weights | Schema v2 prohibits them | Audit 02 |
| LIM-016 | High | Resolved | Collectors could mutate configs | Direct adapters and isolation checks | Audits 02, 04–05 |
| LIM-017 | Medium | Resolved | Source output could contain rank/score | Direct adapters and supported output exclude both | Audit 05 |
| LIM-018 | Medium | Controlled, not fixed | Unknown engine/fuel can cause criteria rejection | Explicit reasons | Current control |
| LIM-019 | Medium | Resolved | Kijiji hub IDs/fallbacks were unvalidated | Explicit supported hubs | Audit 05 |
| LIM-020 | Medium | Resolved | Source settings were ambiguous | Schema v2 separates settings | Audit 02 |
| LIM-021 | High | Resolved | Parsing lacked hostile fixtures | Direct-adapter fixtures | Audit 05 |
| LIM-022 | High | Resolved | Legacy merger ranked and conflated identity | Disabled and removed from active output | Audit 07 |
| LIM-023 | Medium | Resolved | Generated data and implementation shared unvalidated diffs | Separate data validation and manifest | Audit 08 |
| LIM-024 | Medium | Resolved | Collection and tests shared one workflow | Separated workflows | Audit 08 |
| LIM-025 | High | Resolved | F-350 lacked transparent investigation/override output | Buyer schema v1, tests, live validation, owner merge | Audit 09 |
| LIM-026 | Medium | Implemented, validation pending | Purpose-specific secondary outputs did not exist | Audit 10 purpose-input/output/validation schemas | Audit 10 |
| LIM-027 | Medium | Deferred by owner | F-150 and Tundra are not polished | Both remain paused | Audit 11 |
| LIM-028 | Medium | Resolved | Active collectors retained mutation/ranking behavior | Direct schema-v2 adapters | Audit 05 |
| LIM-029 | Low | Implemented, validation pending | Registry analysis profiles were not operationalized | F-350 and Audit 10 profile-specific outputs | Audit 10 |
| LIM-030 | Critical | Resolved | Request/response counts were not preserved | Adapter reconciliation | Audit 05 |
| LIM-031 | Medium | Resolved | Retention policy was undefined | Storage-retention schema v1 | Audit 07 |
| LIM-032 | High | Resolved | No duplicate/lifecycle model | Explainable candidates and lifecycle | Audit 06 |
| LIM-033 | Medium | Open | Configured-query evidence is not complete marketplace coverage | Explicit scopes, counts, and market-scope labels | Current control |
| LIM-034 | Medium | Controlled, not fixed | AutoTrader distance depends on external services | Unavailable/geodesic evidence remains visible | Current control |
| LIM-035 | High | Resolved | Active legacy history/merged files remained | Governed deletion evidence | Audit 07 |
| LIM-036 | Medium | Resolved | Deletion evidence could grow indefinitely | Bounded detail plus cumulative digest | Audit 07 |
| LIM-037 | Medium | Resolved | Price observations could grow indefinitely | Thirteen raw observations plus aggregates/digest | Audit 07 |
| LIM-038 | Medium | Resolved | Retired tombstones could grow indefinitely | Count/age limits | Audit 07 |
| LIM-039 | Medium | Resolved | Publication could include paused/ungoverned paths | Staged-path validation | Audit 07 |
| LIM-040 | High | Resolved | Pull requests could trigger/ambiguously acknowledge collection | No collector PR trigger; real data validation | Audit 08 |
| LIM-041 | Medium | Resolved | Anomalies lacked baseline evidence/policy | Anomaly schema v1 | Audit 08 |
| LIM-042 | High | Resolved | Publication lacked manifest/ref-race protection | Manifest and remote-ref gate | Audit 08 |
| LIM-043 | Medium | Open | Three consecutive unattended scheduled runs are unproven | Exact workflows and diagnostics available | Final completion |
| LIM-044 | High | Controlled, not fixed | Listing text cannot independently verify F-350 facts | Explicit unverified status and manual verification | Current control |
| LIM-045 | High | Controlled, not fixed | F-350 asking-price math is not sale/appraisal evidence | Method/sample/limits visible | Current control |
| LIM-046 | Medium | Resolved | F-350 owner input could erase computed/source evidence | Separate governed override contract | Audit 09 |
| LIM-047 | Medium | Controlled, not fixed | Seller questions cannot obtain or verify answers | Questions remain prompts | Current control |
| LIM-048 | High | Implemented, validation pending | RAM historical odometer context could be mistaken for current odometer | Separate historical field; current odometer remains required | Audit 10 |
| LIM-049 | Medium | Implemented, validation pending | Forester lacks subject year/trim/powertrain/drivetrain/current odometer input | `subject_profile_incomplete` and owner-input gaps | Audit 10 |
| LIM-050 | High | Implemented, validation pending | Odyssey/Carnival friend requirements are not yet supplied | `candidate_pending_requirements` and explicit friend questions | Audit 10 |
| LIM-051 | High | Controlled, not fixed | Observed lower asking prices do not prove faster sale or sale probability | Explicit lower-band non-authority contract | Audit 10/current control |
| LIM-052 | Medium | Controlled, not fixed | Listing asking-price changes do not prove market-value direction | Actual previous observations plus non-trend contract | Audit 10/current control |
| LIM-053 | Medium | Controlled, not fixed | Family listing text cannot verify seating, features, history, condition, or availability | Unverified/unknown evidence and seller/inspection questions | Audit 10/current control |
| LIM-054 | High | Implemented, validation pending | Secondary artifacts could diverge from current evidence | Fail-closed underlying-evidence validator and data-PR integration | Audit 10 |
| LIM-055 | High | Implemented, validation pending | Kijiji structured `vehicleEngine.fuelType` was ignored, falsely rejecting valid gas and diesel listings as unknown fuel | Structured engine/fuel parsing, hostile tests, sanitized response signatures, failed-run evidence artifacts, and five-profile live validation | Audit 10 corrective work |

## Reconciliation boundaries

```text
autotrader_adapter_response_listing_objects
  = accepted_records + rejected_records + parse_failures

kijiji_adapter_json_ld_listing_objects
  = accepted_records + rejected_records + parse_failures
```

Neither equation proves full marketplace coverage.

## Interpretation

Workflow success proves only that applicable configured gates passed.

F-350 and secondary outputs remain investigation support:

- source-text claims are unverified
- missing values remain unknown
- comparability/classification labels are explainable review categories, not ranks
- asking-price distributions are not transaction prices or appraisal
- a lower asking band is not a verified faster-sale range
- price-change direction is not market-value trend
- seller questions are prompts, not findings or verified answers
- owner/friend inputs affect interpretation only, not collected evidence

## Retention interpretation

Deletion and compaction digests prove governed accounting order, not raw reconstruction. Paused F-150/Tundra data remains outside deletion scope. Retired state does not establish sold state.

## Closure requirements

A limitation becomes **Resolved** only when implementation, structured tests, required live validation, authorities, owner approval, and merge are complete.

## Newly discovered limitations

Material weaknesses discovered later must be recorded and assigned without opportunistically expanding current scope.
