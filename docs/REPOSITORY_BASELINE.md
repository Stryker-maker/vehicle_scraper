# Repository Baseline

## Status

**Baseline date:** July 23, 2026  
**Baseline source:** `main` through Audit 07, updated by Audit 08 implementation  
**Project state:** functional collection prototype under structured audit

This document records current supported behaviour. Future-package behaviour is labelled separately.

## Higher purpose

The repository is intended to become a continuously usable vehicle-market information tool that gathers listings, preserves trust evidence, supports repeatable comparison, assists human purchase investigation, and provides lightweight owned-vehicle monitoring without opaque recommendation logic. The primary use case remains an informed early-2020s diesel Ford F-350 purchase.

## Current supported capability

The repository can:

- validate registry/config schema v2 and Kijiji hub registry v1
- derive governed full or single-pair source plans and reject paused/invalid selections
- run both sources directly from approved config without mutation
- preserve request/page, raw object, rejection, parse-failure, canonical, identity, and lifecycle evidence
- enforce `fetched = accepted + rejected + parse failures`
- preserve truthful AutoTrader distance methods and listing-specific-or-unknown Kijiji geography
- keep source IDs distinct from explicit unverified VIN claims
- produce explainable non-destructive duplicate candidates
- track actual elapsed lifecycle and compact price observations without losing aggregate semantics
- bound timestamped archives, retired tombstones, deletion ledgers, managed file size, and total active data
- build fail-closed unranked manual review
- run reusable deterministic CI with exact Python and action dependencies
- separate code CI, generated-data validation, and collection triggers
- produce baseline-aware anomaly evidence
- publish generated data only after health, anomaly, retention, staged-path, manifest, whitespace, and remote-ref gates
- perform narrow validation without committing generated data

## Supported schema boundaries

- Registry/config: schema v2
- Kijiji location registry: v1
- Source adapters: schema v1
- Canonical evidence: schema v1
- Identity/lifecycle: schema v2
- Source status: schema v8
- Consolidated health: schema v6
- Storage retention: schema v1
- Workflow control: schema v1
- Anomaly evidence: schema v1
- Publication manifest: schema v1
- Generated-data validation: schema v1

AutoTrader fetched scope is `autotrader_adapter_response_listing_objects`. Kijiji fetched scope is `kijiji_adapter_json_ld_listing_objects`. Neither proves complete marketplace coverage.

## Reproducible workflow boundary

The active workflow set is:

| Workflow | Trigger | Responsibility |
|---|---|---|
| `.github/workflows/ci.yml` | non-data PR, manual, reusable call | exact dependency validation, compilation, governance checks, deterministic/hostile tests |
| `.github/workflows/generated-data.yml` | `data/**` PR | generated-data path, retention, status, health, anomaly, and manifest validation |
| `.github/workflows/scrape.yml` | Monday schedule or manual dispatch | governed collection, reporting, anomalies, retention, and optional publication |

Collection has no pull-request trigger and cannot start before reusable CI succeeds. Python is fixed to `3.11.13`; `requirements.lock` uses exact pins; GitHub-owned actions use exact commit SHAs.

Scheduled full collection runs Monday at 08:00 UTC. Manual inputs explicitly control scope, active vehicle, source, publication, anomaly policy, and operator note.

## Generated-data publication boundary

A full run snapshots the prior health report, produces current health and anomaly evidence, and cannot publish until source health, anomaly policy, retention, governed staged paths, publication-manifest agreement, whitespace, and remote-ref stability pass.

`data/run_status/publication_latest.json` records the run ID, source SHA, workflow event, target ref, exact published paths, and change-type counts. A changed remote branch blocks the push. Data-only pull requests receive actual validation rather than acknowledgement-only success.

## Current unsupported capability

The repository still cannot reliably establish:

- which listing is the best purchase
- complete marketplace coverage
- independently verified VIN or physical-vehicle identity
- verified sold/removal state
- independent truth of source claims or Kijiji geography
- routable Kijiji distance
- F-350 engine/idle hours, cab, box, SRW/DRW, or verified history enrichment
- purpose-specific decision outputs
- three consecutive scheduled active-profile runs without manual repair

## Governing vehicle scope

| Vehicle | State | Purpose | Priority | Enabled sources |
|---|---|---|---:|---|
| Ford F-350 | Enabled | Primary purchase research | 1 | AutoTrader, Kijiji |
| RAM 3500 | Enabled | Owned-vehicle value monitoring | 2 | AutoTrader, Kijiji |
| Subaru Forester | Enabled | Owned-vehicle value monitoring | 2 | AutoTrader, Kijiji |
| Honda Odyssey | Enabled | Family-friend purchase search | 3 | AutoTrader, Kijiji |
| Kia Carnival | Enabled | Family-friend purchase search | 3 | AutoTrader, Kijiji |
| Ford F-150 | Paused | Optional curiosity | 4 | AutoTrader, Kijiji when enabled |
| Toyota Tundra | Paused | Optional curiosity | 4 | AutoTrader, Kijiji when enabled |

F-150 and Tundra must not receive current collection, evidence, lifecycle, review, retention deletion, or publication updates until Audit 11.

## Active component inventory

| Component | Present responsibility |
|---|---|
| `vehicle_registry.json` / `vehicle_registry.py` | operational scope and source plan |
| `config_*.json` / `vehicle_config.py` | criteria, source settings, hub validation |
| `.github/workflows/ci.yml` | reusable deterministic code CI |
| `.github/workflows/generated-data.yml` | generated-data PR validation |
| `.github/workflows/scrape.yml` | schedule/manual collection and publication |
| `requirements.lock` / `dependency_lock.py` | exact Python environment |
| `workflow_control.py` | registry-governed inputs, plan, smoke validation |
| `workflow_anomalies.py` | baseline-aware anomaly evidence and policy |
| `generated_data_publish.py` | publication manifest and staged verification |
| `generated_data_validation.py` | data-PR integrity validation |
| `autotrader_*.py` / `kijiji_*.py` | direct source adapters/runtimes/evidence |
| `canonical_evidence.py` | canonical stages and reconciliation |
| `identity_lifecycle.py` | VIN evidence, fingerprints, lifecycle, compact history, duplicate candidates |
| `storage_retention.py` | archive bounds, deletion evidence, size and staged-path gates |
| `phase1_reporting.py` | identity-backed manual review and health schema v6 |
| `tests/` | fixtures, hostile tests, governance and workflow contracts |

## Compatibility and historical components

`scraper.py` and `kijiji_scraper.py` are compatibility aliases. `phase1_runtime.py` and `legacy_runtime_config()` are historical utilities. `price_history_*.json`, historical merged CSVs, and `merge.py` are not supported output or recommendation authority. `trim_tiers.json` remains descriptive legacy configuration pending Audit 09.

## Present operational guarantees

Current code/tests are intended to guarantee:

1. registry/config authority and paused scope are preserved
2. pull requests cannot execute collectors
3. collection cannot bypass deterministic CI preflight
4. Python and GitHub Action dependencies are exact
5. source objects reconcile with explicit evidence
6. source-ID/VIN, geography, distance, duplicate, and lifecycle boundaries remain truthful
7. current manual review fails closed on evidence mismatch
8. state and repository growth are bounded with deletion evidence
9. anomaly evidence remains visible and critical policy is enforceable
10. generated publication paths match a run-tied manifest
11. non-data, paused, ungoverned, malformed, whitespace-invalid, or stale-ref publication fails
12. supported output has no purchase-ranking authority

## Explicit non-guarantees

`SUCCESS`, `active`, `retired`, format-valid VIN, high-confidence duplicate candidate, clean anomaly report, retention pass, or publication manifest does not guarantee marketplace completeness, independently verified identity, sold status, availability, condition, fair value, or purchase suitability.

## Last operating evidence

- Audit 03 full validation: 10/10 source pairs healthy, 381 accepted collector-emitted rows, no stale rows.
- Audit 04 narrow AutoTrader run `29954526608`: 174 objects = 22 accepted + 150 rejected + 2 parse failures.
- Audit 05 narrow Kijiji run `29968206030`: 441 objects = 11 accepted + 430 rejected + 0 parse failures; query geography stayed separate.
- Audits 06 and 07 passed exact-head deterministic/hostile validation because they changed state/storage semantics rather than source requests.
- Audit 08 changes workflow orchestration and publication controls; its final acceptance requires exact-head CI and a narrow manual collection validation of the new collection workflow.

## Repository change authority

Implementation uses an `ai/*` branch and pull request. The owner reviews, merges, and deletes the branch. `docs/AUDIT_ROADMAP.md` governs package sequence unless the owner approves revision.
