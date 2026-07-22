# Audit 02 — Vehicle Registry and Configuration Governance

**Status:** implemented on `ai/audit-02-config-governance`; pending validation and owner merge.

## Purpose

Audit 02 replaces ambiguous flat legacy configuration with validated operational governance and source-specific criteria while keeping the current collectors operational through disposable compatibility projections.

## Authoritative models

### Registry schema v2

`vehicle_registry.json` controls:

- `enabled`
- `purpose`
- `priority`
- `cadence`
- `enabled_sources`
- `analysis_profile`
- `pause_reason` for disabled entries

The registry remains the only operational authority. Toggling `enabled` is the one-change pause/re-enable mechanism.

### Config schema v2

Each `config_*.json` contains only:

- vehicle identity
- shared year/price/fuel/engine criteria
- origin and distance boundary
- independent AutoTrader make/model/location settings
- independent Kijiji make/model/location settings

Approved configs reject unknown fields, legacy flat aliases, legacy result caps and ranking weights.

## Runtime compatibility boundary

The current collectors still require their old flat schema. `vehicle_config.py` therefore creates one temporary source-specific compatibility config for each run.

The temporary projection:

- copies governed shared criteria
- selects only the active source's location list
- provides both source make/model aliases required by legacy code
- injects effectively unbounded `max_results`
- injects fixed legacy ranking weights solely to keep the collector process compatible
- is deleted when the source process finishes

The approved config is never passed to a collector. `phase1_runtime.py` verifies its bytes remained unchanged and records the projection contract in source status JSON.

## Registry source-plan contract

`python vehicle_registry.py active-runs` emits ordered tab-separated `config_path` and `source` pairs.

The workflow uses that plan for:

1. collector execution
2. manual-review source inclusion
3. health-report expected source pairs

This means a disabled source is not executed, copied to current manual review or expected by health reporting.

## Preserved search criteria

Audit 02 migrates existing approved year, price, fuel, engine, origin, distance and search-location values into schema v2. It does not revise vehicle-market intent or collector filtering behaviour.

F-150 and Tundra remain paused. Their governed criteria and enabled-source selections remain stored for later Audit 11 reintroduction.

## Validation contracts

Structured tests cover:

- exact active/paused vehicle set
- ten current enabled source runs
- source-level enablement
- required pause reasons
- allowed purpose/cadence/profile values
- purpose/profile consistency
- registry/config key matching
- config schema/range/coordinate/location validation
- duplicate location rejection
- obsolete approved-config field rejection
- source-specific location projection
- injected uncapped compatibility values
- approved config isolation
- registry-source-aware workflow, reporting and health expectations

## Required live validation

Because collector input construction changed, Audit 02 requires one manual workflow run on the branch before merge.

Acceptance requires:

- governed registry/config validation passes before collection
- exactly 10 source runs are attempted
- five active vehicles run both enabled sources
- F-150 and Tundra do not run or change
- every source status records config schema version `2`
- every source status records `runtime_config_projection: legacy_collector_v1`
- every source status records `approved_config_contains_legacy_controls: false`
- every healthy source records `config_isolated: true`
- consolidated health expects 10 source runs
- final status is `SUCCESS` or `SUCCESS_WITH_WARNINGS`
- generated-data follow-up runs acknowledgement only

## Intentional non-scope

Audit 02 does not:

- repair AutoTrader pagination or parsing
- repair Kijiji geography or remove runtime source rewriting
- create raw/rejected/parse-failure evidence
- create canonical listing identity or lifecycle
- change F-350 purchase criteria
- create candidate rankings or graphs
- change storage retention
- re-enable F-150 or Tundra

## Completion rule

Audit 02 is complete only after tests pass, live validation passes, PR evidence is recorded, the owner merges the PR and deletes the branch.
