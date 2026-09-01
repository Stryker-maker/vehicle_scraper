# Baseline Compatibility Contract

## Purpose

The anomaly engine must compare a current collection only with a historical collection that represents the same collection contract. Vehicle/source identity alone is insufficient because query scope, configuration, governed location data, and schema can change independently of the vehicle and source names.

This contract defines the semantic inputs that determine whether two collection health reports are comparable.

## Compatibility identity

A source collection is comparable when all required compatibility dimensions match:

- `vehicle_key`
- `source`
- `collection_scope`
- effective source query locations
- source-specific search parameters that affect the population being collected
- `configuration_schema_version`
- governed location-registry version, when the source uses a governed location registry
- source adapter schema version
- canonical evidence schema version

The compatibility identity must be deterministic. Equivalent semantic inputs must produce the same identity regardless of JSON key ordering or query-location ordering.

## Query locations

Query locations are part of the collection population definition. The identity must use the effective validated locations, not merely the number of locations.

Location order is not significant. Adding, removing, or replacing a location is significant.

For governed Kijiji collection, the effective location identity includes the validated query-location labels and the governed location-registry version. This prevents a historical run using a different query population from being treated as a valid numerical baseline.

## Configuration

Configuration compatibility is semantic rather than a raw file-byte comparison. Formatting-only changes must not invalidate an otherwise equivalent baseline.

Fields that affect the collected population or acceptance behavior are compatibility inputs. Incidental representation details are not.

## Schema and implementation versions

Schema versions are compatibility boundaries. A change to an adapter/evidence schema that can alter the meaning of collection metrics must invalidate numerical comparison with an older incompatible baseline.

The compatibility contract does not use the source adapter's Python file hash as a blanket compatibility key. Versioned semantic contracts are preferred so harmless implementation changes do not unnecessarily discard useful baselines.

## Baseline outcomes

The baseline-selection and anomaly system must distinguish these states:

### Comparable baseline

The historical report satisfies the compatibility contract. Numerical anomaly checks are permitted.

### Incompatible baseline

A historical report exists, but one or more compatibility dimensions differ. Numerical count comparisons must not be performed against that report. The report should identify the incompatible dimensions and continue searching for the most recent compatible successful baseline when historical reports are available.

### No comparable baseline

No usable compatible historical baseline exists. Count-based anomaly checks are skipped because there is no scientifically valid comparison. This is distinct from a source failure.

### Current collection failure

Collection-health failures such as an unhealthy source, incomplete pagination, failed pages, or other critical integrity failures remain critical regardless of baseline compatibility. Baseline compatibility must never suppress current-run safety checks.

## Safety invariants

1. A count-collapse or count-surge anomaly may only be emitted when the compared baseline is compatible.
2. Baseline incompatibility must never be converted into a collection failure.
3. Baseline incompatibility must never suppress current-run critical health failures.
4. A compatible baseline must preserve the existing anomaly thresholds and fail-closed enforcement behavior.
5. A change in query scope must be visible and explainable in run-status/anomaly evidence.
6. Missing or malformed historical evidence must not be treated as a valid baseline.
7. Compatibility evaluation must be deterministic and covered by regression tests.

## Run #116 regression target

The implementation must prevent the false-positive pattern observed in governed collection run #116:

- Forester Kijiji: historical broad scope versus current four-hub scope
- Odyssey Kijiji: historical broad scope versus current six-hub scope
- Carnival Kijiji: historical broad scope versus current six-hub scope

Those cases must be classified as baseline incompatibility rather than accepted-record-count collapse.

## Planned status vocabulary

The implementation should use explicit machine-readable baseline states rather than overloading anomaly severity:

- `available` — a compatible baseline is available and numerical comparison is permitted.
- `incompatible` — a candidate baseline exists but fails the compatibility contract.
- `unavailable` — no usable baseline exists.
- `same_run_not_compared` — the candidate refers to the current run and must not be compared.

The exact final field names may follow existing repository conventions during implementation, but the semantic distinctions above are mandatory.
