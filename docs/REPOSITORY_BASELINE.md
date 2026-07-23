# Repository Baseline

## Status

**Baseline date:** July 23, 2026  
**Baseline source:** `main` through Audit 09, updated by Audit 10 implementation  
**Project state:** functional collection and purpose-specific analysis prototype under structured audit

This document records current supported behaviour. Validation-pending Audit 10 behaviour is labelled accordingly.

## Higher purpose

The repository gathers vehicle listings, preserves evidence, supports repeatable comparison, assists human investigation, and provides lightweight monitoring without opaque recommendation logic. The primary use case remains an informed early-2020s diesel Ford F-350 purchase.

## Current supported capability

The repository can:

- validate registry/config schema v2 and Kijiji hub registry v1
- run both sources directly from approved config without mutation
- reconcile every returned source object as accepted, rejected, or parse failure
- preserve request/page, raw, canonical, identity, lifecycle, and quality evidence
- preserve source-ID/VIN, geography, distance, duplicate, and lifecycle boundaries
- build fail-closed unranked general manual review
- bound generated data, observations, retired tombstones, ledgers, and managed size
- run exact, separated CI/data-validation/collection workflows
- produce baseline-aware anomalies and run-tied publication manifests
- build current-run F-350 buyer intelligence with visible evidence gaps and reasons
- build validation-pending profile-specific outputs for RAM 3500, Subaru Forester, Honda Odyssey, and Kia Carnival

## Supported schema boundaries

- Registry/config: v2
- Kijiji location registry: v1
- Source adapters: v1
- Canonical evidence: v1
- Identity/lifecycle: v2
- Source status: v8
- Consolidated health: v6
- Storage retention: v1
- Workflow control: v1
- Anomaly evidence: v1
- Publication manifest: v1
- Generated-data validation: v1
- F-350 buyer intelligence: v1
- F-350 owner overrides: v1
- Secondary-purpose inputs: v1
- Secondary-purpose outputs: v1
- Secondary-purpose validation: v1

AutoTrader fetched scope is `autotrader_adapter_response_listing_objects`. Kijiji fetched scope is `kijiji_adapter_json_ld_listing_objects`. Neither proves complete marketplace coverage.

## F-350 boundary

F-350 buyer intelligence accepts only current successful source status, accepted canonical evidence, matching raw adapter records, matching identity records, and governed owner overrides. It fails closed on stale, unhealthy, wrong-run, wrong-schema, count-mismatched, discontinuous, or disconnected evidence.

Its asking-price bands and regression are descriptive listing context, not appraisal, transaction price, fair value, or future value.

## Secondary-purpose boundary

`purpose_inputs.json` is non-generated interpretation input, not collection authority.

### Owned-vehicle value monitoring

RAM 3500 and Subaru Forester outputs provide current accepted comparables, subject-profile comparability, observed asking-price/mileage distributions, actual previous asking-price changes, and explicit owner-input gaps.

- RAM historical year/trim/engine/drivetrain/odometer context remains owner-reported and unverified.
- RAM current odometer remains required.
- Forester subject details remain required before personalized subject context is available.
- Q1-to-median is an observed lower asking band, not a verified faster-sale range.
- Multi-run direction requires at least three real previous-price observations and remains asking-price change evidence only.

### Family-friend purchase review

Odyssey and Carnival outputs provide current candidates, explicit preference gaps, visible preference mismatches, unverified seating/cargo/history/service/seller claims, and seller questions.

Until the friend supplies budget, year, mileage, seating, cargo, distance, history, seller, and availability preferences, accepted listings remain `candidate_pending_requirements`. Config acceptance is not a personalized recommendation.

No F-350 truck-specific assumptions apply to family vehicles.

## Workflow boundary

| Workflow | Trigger | Responsibility |
|---|---|---|
| `.github/workflows/ci.yml` | non-data PR, manual, reusable call | exact dependencies, compilation, governance, deterministic/hostile tests |
| `.github/workflows/generated-data.yml` | `data/**` PR | path, retention, status, health, anomaly, manifest, buyer, and purpose-output integrity |
| `.github/workflows/scrape.yml` | Monday schedule or manual | collection, reporting, purpose outputs, anomalies, retention, optional publication |

Collection has no pull-request trigger and cannot start before reusable CI succeeds.

A narrow run builds only the selected vehicle's applicable F-350 or secondary-purpose output, uploads seven-day evidence, and never publishes generated data.

A full run builds all current purpose outputs only after source health passes. Publication remains behind anomaly, retention, staged-path, artifact, manifest, whitespace, and remote-ref gates.

## Current unsupported capability

The repository still cannot reliably establish:

- complete marketplace coverage
- independently verified identity, VIN, configuration, history, use, or condition
- verified sold/removal state
- actual transaction prices or time to sale
- appraisal, fair value, future value, sale probability, or verified faster-sale range
- current RAM subject value without current odometer and adequate close comparables
- personalized Forester value context without owner inputs
- personalized Odyssey/Carnival shortlist without friend preferences
- seller answers, inspection findings, repair costs, or external history-report contents
- three consecutive unattended scheduled active-profile runs

## Governing vehicle scope

| Vehicle | State | Purpose | Analysis profile |
|---|---|---|---|
| Ford F-350 | Enabled | Primary purchase research | `f350_purchase` |
| RAM 3500 | Enabled | Owned-vehicle value monitoring | `owned_vehicle_value` |
| Subaru Forester | Enabled | Owned-vehicle value monitoring | `owned_vehicle_value` |
| Honda Odyssey | Enabled | Family-friend purchase search | `family_friend_purchase` |
| Kia Carnival | Enabled | Family-friend purchase search | `family_friend_purchase` |
| Ford F-150 | Paused | Optional curiosity | `optional_curiosity` |
| Toyota Tundra | Paused | Optional curiosity | `optional_curiosity` |

F-150 and Tundra receive no current collection, evidence, lifecycle, review, purpose output, retention deletion, or publication update until Audit 11.

## Active component inventory

| Component | Present responsibility |
|---|---|
| `vehicle_registry.json/.py` | operational scope and source plan |
| `config_*.json` / `vehicle_config.py` | criteria and source settings |
| direct `autotrader_*.py` / `kijiji_*.py` | collection and evidence |
| `canonical_evidence.py` | canonical stages and reconciliation |
| `identity_lifecycle.py` | identity, lifecycle, compact history, duplicate candidates |
| `phase1_reporting.py` | general review and health |
| `f350_buyer_intelligence.py` / validator | F-350 investigation |
| `f350_owner_overrides.json` | F-350 owner review input |
| `purpose_inputs.json` | secondary owner/friend input |
| `purpose_outputs.py` / validator | owned-value and family-candidate outputs |
| `storage_retention.py` | bounded storage and staged paths |
| workflow-control/anomaly/publication modules | workflow and publication integrity |

## Present operational guarantees

Current code/tests are intended to guarantee:

1. registry/config and paused scope remain authoritative
2. pull requests cannot collect marketplace data
3. collection cannot bypass exact CI preflight
4. source objects and current identity evidence reconcile
5. generated growth remains bounded
6. generated publication remains run/path/ref governed
7. F-350 and secondary outputs require current matching evidence
8. missing owner/friend inputs remain explicit
9. purpose profiles do not import one another's assumptions
10. asking-price context is not represented as appraisal or transaction evidence
11. lower asking bands are not represented as verified faster-sale ranges
12. all classifications and comparability labels have visible reasons
13. no supported output contains purchase `rank` or `score`

## Explicit non-guarantees

A successful run, active lifecycle state, complete artifact set, close comparable, candidate classification, observed quartile, price-change direction, clean anomaly report, retention pass, or publication manifest does not guarantee marketplace completeness, verified truth, availability, condition, appraised value, sale price, sale speed, or purchase suitability.

## Last operating evidence

- Audit 08 narrow run `30002827204` proved separated CI/collection and no publication.
- Audit 09 narrow run `30017275049` proved current F-350 raw/canonical/identity joins and buyer outputs on exact head.
- Audit 10 requires exact-head deterministic/hostile validation plus narrow live proof for both an owned-value profile and a family-candidate profile.

## Repository change authority

Implementation uses an `ai/*` branch and pull request. The owner reviews, merges, and deletes the branch. `docs/AUDIT_ROADMAP.md` governs package sequence unless the owner approves revision.
