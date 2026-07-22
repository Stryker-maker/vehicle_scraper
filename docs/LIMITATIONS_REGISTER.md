# Current Limitations Register

## Purpose

This register preserves known repository weaknesses so they remain visible, prioritized and assigned to approved audit packages. A successful workflow does not close a limitation unless its acceptance criteria are explicitly met.

Severity describes potential effect on trustworthy continuous use:

- **Critical** — can materially misrepresent scope, evidence or decision data
- **High** — can materially reduce completeness, correctness or maintainability
- **Medium** — creates drift, reproducibility or operational risk
- **Low** — limited present impact but should be corrected deliberately

Status values:

- **Open** — not fixed
- **Controlled, not fixed** — current safeguards reduce harm but underlying defect remains
- **Resolved** — acceptance evidence exists
- **Deferred by owner** — intentionally postponed

## Register

| ID | Severity | Status | Limitation | Current control | Planned package |
|---|---|---|---|---|---|
| LIM-001 | Critical | Controlled, not fixed | Kijiji parser stores search origin as location/address rather than verified listing geography | Manual-review transformation blanks Kijiji location/distance and preserves search origin only as unverified evidence | Audit 05 |
| LIM-002 | Critical | Controlled, not fixed | Kijiji safety depends on exact runtime text replacement and `exec` of patched legacy source | Patch-anchor count must equal one; tests compile patched current source | Audit 05 |
| LIM-003 | Critical | Open | Repository does not preserve raw, accepted, rejected and parse-failure records as reconcilable stages | Final CSV freshness and minimum schema are recorded | Audit 03, then Audits 04–05 |
| LIM-004 | High | Open | AutoTrader collector requests a fixed result page and has no verified pagination contract | Result cap after parsing is disabled | Audit 04 |
| LIM-005 | High | Open | Collector-level broad exception handling can silently skip individual parse failures | Wrapper captures process output and validates final CSV only | Audits 04–05 |
| LIM-006 | High | Controlled, not fixed | AutoTrader distance evidence does not reliably distinguish routed driving distance from straight-line fallback | Manual review labels method `legacy_method_not_yet_disambiguated` | Audit 04 |
| LIM-007 | High | Open | `clean` data-quality status means only that a small warning rule set did not fire | README and dictionary explicitly limit interpretation | Audit 03 and source audits |
| LIM-008 | High | Open | Current F-350 data lacks engine hours, idle hours, cab, box, SRW/DRW, verified history and owner enrichment | No values are inferred or invented | Audit 09 |
| LIM-009 | High | Controlled, not fixed | Source `listing_id` is not VIN and cannot establish cross-source vehicle identity | Automated legacy merge is disabled | Audit 06 |
| LIM-010 | High | Open | Price history labels observation count as weeks and does not model active, missing, reappeared or relisted states | Same-day duplicates are controlled | Audit 06 |
| LIM-011 | High | Open | Timestamped CSVs and price-history files grow without an approved retention boundary | F-150 and Tundra are paused to reduce current growth | Audit 07 |
| LIM-012 | Medium | Open | Workflow installs unpinned latest dependencies | Tests run before collection | Audit 08 |
| LIM-013 | High | Resolved | Workflow scope was repeated in hard-coded lists and included unnecessary F-150/Tundra runs | Registry is now authoritative; Audit 00 live run proved 10 enabled source runs and no paused-vehicle changes | Audit 00 |
| LIM-014 | High | Resolved | README described a single F-350 AutoTrader ranker and contradicted current operating behaviour | Replaced with current baseline and linked authority documents | Audit 01 |
| LIM-015 | Medium | Controlled, not fixed | Config files retain legacy `max_results` and `ranking_weights` fields | Runtime overrides cap; supported manual review removes rank/score | Audit 02 |
| LIM-016 | High | Controlled, not fixed | Legacy collectors can attempt to mutate search-location configuration | Wrapper uses temporary config and restores approved file if mutated | Audit 02 and source audits |
| LIM-017 | Medium | Controlled, not fixed | Source CSVs may still contain rank and score fields that could be mistaken for recommendations | Supported manual-review schema excludes both fields; merged directories contain warning markers | Audit 03 and source audits |
| LIM-018 | Medium | Open | Current source filters can reject records with unknown parsed engine/fuel without preserving rejection reasons | No completeness claim is made | Audit 03 and source audits |
| LIM-019 | Medium | Open | Kijiji location-ID mappings and fallback ID behaviour are not formally validated | Geography is disabled for review decisions | Audit 05 |
| LIM-020 | Medium | Open | Search-location lists contain historical expansion and inconsistent naming that have not been governed by schema | Registry controls vehicle scope only, not source locations | Audit 02 |
| LIM-021 | High | Open | Structured tests focus on wrappers and synthetic records more than real source fixtures and parser contracts | Current Phase 1 safety contracts are covered | Audits 04–05 |
| LIM-022 | High | Open | Historical `merge.py` duplicate logic compares source listing IDs as though they could be VIN and applies legacy scoring | Workflow does not call `merge.py`; file is explicitly marked disabled | Audit 06 |
| LIM-023 | Medium | Open | Generated data and implementation code share the same branch and PR diff, making code review noisy | Audit packages inspect generated-data follow-up separately | Audit 07–08 |
| LIM-024 | Medium | Open | Workflow collection and test responsibilities remain in one workflow file and generated-data approval adds operational friction | Dedicated acknowledgement path prevents duplicate collection | Audit 08 |
| LIM-025 | High | Open | No transparent F-350 candidate state, manual enrichment record or owner override model exists | All current records remain manual-review candidates | Audit 09 |
| LIM-026 | Medium | Open | RAM/Forester valuation and Odyssey/Carnival shortlisting outputs do not yet exist | Collection continues for those purposes | Audit 10 |
| LIM-027 | Medium | Deferred by owner | F-150 and Tundra collectors and output behaviour are not being polished during the core audit | Both vehicles remain paused and historical data is retained | Audit 11 |

## Interpretation notes

### Controlled does not mean corrected

Examples:

- Kijiji location is prevented from influencing supported review output, but actual listing geography is still not extracted reliably.
- Legacy ranking is hidden from the supported output, but source collectors still contain ranking code and fields.
- Config mutation is isolated, but the legacy self-mutating design remains.

### Successful run does not close data limitations

`SUCCESS` or `SUCCESS_WITH_WARNINGS` currently proves the enabled source attempts met the Phase 1 health contract. It does not prove marketplace completeness, semantic field accuracy, verified geography or purchase suitability.

### Closure requirements

A limitation may be changed to `Resolved` only when:

1. the relevant approved package implements a correction or formally removes the affected capability
2. structured tests cover the corrected contract
3. live validation is performed where external source behaviour is involved
4. documentation and the data dictionary are updated
5. the repository owner approves and merges the package

## Newly discovered limitations

Any material weakness discovered during a later package must be added here even when it is outside that package's implementation scope. The discovering package should identify the appropriate future owner and must not opportunistically expand its own scope without approval.