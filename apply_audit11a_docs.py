from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"Expected exactly one match in {path}: found {count}; "
            f"anchor={old.splitlines()[0]!r}"
        )
    path.write_text(text.replace(old, new), encoding="utf-8")


readme = ROOT / "README.md"
replace_once(
    readme,
    "Its primary purpose is an informed early-2020s diesel Ford F-350 purchase. It also supports lightweight RAM 3500 and Subaru Forester value monitoring plus Honda Odyssey and Kia Carnival searches for a family friend.\n",
    "Its primary purpose is an informed early-2020s diesel Ford F-350 purchase. It also supports lightweight RAM 3500 and Subaru Forester value monitoring, Honda Odyssey and Kia Carnival searches for a family friend, and an explicitly manual-only Ford F-150 optional-curiosity search.\n",
)
replace_once(
    readme,
    '''### Active

| Vehicle | Purpose | Priority |
|---|---|---:|
| Ford F-350 | Primary purchase research | 1 |
| RAM 3500 | Owned-vehicle value monitoring | 2 |
| Subaru Forester | Owned-vehicle value monitoring | 2 |
| Honda Odyssey | Family-friend purchase search | 3 |
| Kia Carnival | Family-friend purchase search | 3 |

### Paused until Audit 11

- Ford F-150
- Toyota Tundra

Paused vehicles retain historical data and governed criteria but do not run or receive current evidence. Retention and publication validation do not modify their data.
''',
    '''### Enabled

| Vehicle | Purpose | Priority | Cadence |
|---|---|---:|---|
| Ford F-350 | Primary purchase research | 1 | Weekly |
| RAM 3500 | Owned-vehicle value monitoring | 2 | Weekly |
| Subaru Forester | Owned-vehicle value monitoring | 2 | Weekly |
| Honda Odyssey | Family-friend purchase search | 3 | Weekly |
| Kia Carnival | Family-friend purchase search | 3 | Weekly |
| Ford F-150 | Optional curiosity | 4 | Manual only |

### Paused

- Toyota Tundra — pending separate Audit 11B owner decision

The weekly plan remains five vehicles and ten source runs. F-150 can run only through explicit non-publishing `single_pair` dispatch. Tundra retains historical data and governed criteria but cannot run or receive current evidence.
''',
)
replace_once(
    readme,
    '''All supported review and purpose outputs are built from current accepted canonical records joined to current identity/lifecycle evidence. F-350 and Audit 10 outputs also join matching raw adapter payloads. No supported output contains `rank` or `score`.

Do not use `data/<vehicle>/merged/*.csv` as current recommendations.
''',
    '''All supported review and purpose outputs are built from current accepted canonical records joined to current identity/lifecycle evidence. F-350 and Audit 10 outputs also join matching raw adapter payloads. No supported output contains `rank` or `score`.

A manual F-150 single-pair run does not create buyer intelligence or a secondary-purpose output. Its seven-day artifact contains the selected source CSV, status, adapter/canonical/lifecycle evidence, and an `optional-curiosity-summary.md` that explicitly disclaims purchase need, rank, score, appraisal, and recommendation.

Do not use `data/<vehicle>/merged/*.csv` as current recommendations.
''',
)
replace_once(
    readme,
    "For each active vehicle, a governed full run retains eight timestamped source CSVs per source, four timestamped manual-review CSVs, and all current `*_latest` evidence. File deletions record path, reason, size, SHA-256, run ID, and time. Detailed ledgers retain the latest 100 records while cumulative counts, bytes, and chained digests continue.\n",
    "For each weekly-cadence vehicle, a governed full run retains eight timestamped source CSVs per source, four timestamped manual-review CSVs, and all current `*_latest` evidence. Manual-only F-150 runs do not invoke retention or publication. File deletions record path, reason, size, SHA-256, run ID, and time. Detailed ledgers retain the latest 100 records while cumulative counts, bytes, and chained digests continue.\n",
)
replace_once(
    readme,
    "Scheduled full collection runs Mondays at 08:00 UTC. Manual inputs are `collection_scope`, active `vehicle_key`, `source`, `publish_generated_data`, `anomaly_policy`, and optional `operator_note`.\n",
    "Scheduled full collection runs Mondays at 08:00 UTC and use only registry entries with cadence `weekly`. Manual inputs are `collection_scope`, enabled `vehicle_key`, `source`, `publish_generated_data`, `anomaly_policy`, and optional `operator_note`. F-150 is selectable only as a manual `single_pair`; Tundra is not selectable.\n",
)
replace_once(
    readme,
    "A `single_pair` run validates one active governed source pair, builds only the selected vehicle's applicable F-350 or secondary-purpose output, uploads seven-day temporary evidence, and never publishes generated data.\n",
    "A `single_pair` run validates one enabled governed source pair, builds only the selected vehicle's applicable F-350 or secondary-purpose output, or writes the F-150 optional-curiosity summary, uploads seven-day temporary evidence, and never publishes generated data.\n",
)
replace_once(
    readme,
    '''python vehicle_registry.py active-runs
python -m unittest discover -s tests -v
python storage_retention.py verify --registry vehicle_registry.json
''',
    '''python vehicle_registry.py weekly-runs
python vehicle_registry.py manual-runs
python -m unittest discover -s tests -v
python storage_retention.py verify --registry vehicle_registry.json --cadence weekly
''',
)
replace_once(
    readme,
    "- `AUDIT_10_SECONDARY_PURPOSE_OUTPUTS.md`\n",
    "- `AUDIT_10_SECONDARY_PURPOSE_OUTPUTS.md`\n- `AUDIT_11A_F150_MANUAL_REINTRODUCTION.md`\n",
)

roadmap = ROOT / "docs" / "AUDIT_ROADMAP.md"
replace_once(
    roadmap,
    '''| 10 | Secondary Purpose Outputs | Implemented; deterministic and narrow validation pending |
| 11 | Optional Search Reintroduction | Approved final stage |
''',
    '''| 10 | Secondary Purpose Outputs | Complete and merged |
| 11A | Ford F-150 Manual Reintroduction | Implemented; live validation pending |
| 11B | Toyota Tundra Reconsideration | Pending owner decision |
''',
)
replace_once(
    roadmap,
    "The audit is not complete until optional vehicles remain paused unless approved; registry/config authority is preserved;",
    "The audit is not complete until optional vehicles remain paused or explicitly cadence-governed by owner approval; registry/config authority is preserved;",
)
replace_once(
    roadmap,
    "**Status:** implemented on `ai/audit-10-purpose-outputs`; exact-head deterministic validation, narrow live validation, owner review, and merge remain pending.\n",
    "**Status:** complete and merged through PR #12, including Kijiji structured fuel/engine correction and all-profile live validation.\n",
)
replace_once(
    roadmap,
    '''## Audit 11 — Optional Search Reintroduction

**Status:** approved final stage.

Reintroduce F-150 first under limited validation and owner approval, then Tundra separately. Either may remain manual/monthly.
''',
    '''## Audit 11 — Optional Search Reintroduction

**Status:** Audit 11A implemented on `ai/audit-11a-f150-manual-reintroduction`; deterministic CI and two-source live validation remain pending. Audit 11B is not started.

### Audit 11A — Ford F-150 manual reintroduction

F-150 is enabled with cadence `manual` for explicit non-publishing single-pair collection only. Registry cadence is operational: scheduled/full collection, reporting, health, anomalies, retention, diagnostics, and publication remain limited to the five weekly vehicles and ten weekly source pairs. F-150 receives source/canonical/lifecycle evidence and an explicit optional-curiosity summary, but no F-350 buyer intelligence, Audit 10 purpose output, rank, score, appraisal, or recommendation.

### Audit 11B — Toyota Tundra reconsideration

Tundra remains paused and requires a separate package and owner decision after Audit 11A. It may remain paused permanently.
''',
)

purposes = ROOT / "docs" / "VEHICLE_PURPOSES.md"
replace_once(
    purposes,
    '''## Priority 4 — Optional curiosity searches

### Ford F-150

### Toyota Tundra

There is no current purchase or ownership need. They remain paused throughout the core audit, preserve historical data, receive no Audit 10 output, and are reconsidered only in Audit 11 one vehicle at a time. Reintroduction does not imply weekly cadence.
''',
    '''## Priority 4 — Optional curiosity searches

### Ford F-150

There is no current purchase or ownership need. Audit 11A enables F-150 only for explicit manual, non-publishing single-pair searches. It receives current source/canonical/lifecycle evidence and a temporary optional-curiosity summary, but no specialized buyer intelligence, secondary-purpose output, rank, score, appraisal, or recommendation. Manual enablement does not place F-150 in weekly collection, health, anomaly, retention, or publication scope.

### Toyota Tundra

Tundra remains paused with historical data preserved. Any reconsideration requires a separate Audit 11B package and owner approval; it may remain paused permanently.
''',
)

baseline = ROOT / "docs" / "REPOSITORY_BASELINE.md"
replace_once(baseline, "**Baseline date:** July 23, 2026  \n", "**Baseline date:** July 24, 2026  \n")
replace_once(
    baseline,
    "**Baseline source:** `main` through Audit 09, updated by Audit 10 implementation and Kijiji corrective validation  \n",
    "**Baseline source:** `main` through merged Audit 10, updated by Audit 11A implementation  \n",
)
replace_once(
    baseline,
    "This document records current supported behaviour. Audit 10 implementation and live validation are complete on the branch; owner review and merge remain pending.\n",
    "This document records current supported behaviour. Audit 10 is merged. Audit 11A implementation is on a draft branch; live F-150 validation, owner review, and merge remain pending.\n",
)
replace_once(
    baseline,
    "- build profile-specific outputs for RAM 3500, Subaru Forester, Honda Odyssey, and Kia Carnival\n",
    "- build profile-specific outputs for RAM 3500, Subaru Forester, Honda Odyssey, and Kia Carnival\n- expose F-150 as a manual-only optional-curiosity source-evidence search without weekly scheduling or publication\n",
)
replace_once(
    baseline,
    "A narrow run builds only the selected vehicle's applicable F-350 or secondary-purpose output, uploads seven-day evidence, and never publishes generated data. Evidence preparation and upload run under `always()` so available status and adapter evidence survive an unhealthy source result.\n",
    "A narrow run builds only the selected vehicle's applicable F-350 or secondary-purpose output, or the F-150 optional-curiosity summary, uploads seven-day evidence, and never publishes generated data. Evidence preparation and upload run under `always()` so available status and adapter evidence survive an unhealthy source result.\n",
)
replace_once(
    baseline,
    '''| Vehicle | State | Purpose | Analysis profile |
|---|---|---|---|
| Ford F-350 | Enabled | Primary purchase research | `f350_purchase` |
| RAM 3500 | Enabled | Owned-vehicle value monitoring | `owned_vehicle_value` |
| Subaru Forester | Enabled | Owned-vehicle value monitoring | `owned_vehicle_value` |
| Honda Odyssey | Enabled | Family-friend purchase search | `family_friend_purchase` |
| Kia Carnival | Enabled | Family-friend purchase search | `family_friend_purchase` |
| Ford F-150 | Paused | Optional curiosity | `optional_curiosity` |
| Toyota Tundra | Paused | Optional curiosity | `optional_curiosity` |

F-150 and Tundra receive no current collection, evidence, lifecycle, review, purpose output, retention deletion, or publication update until Audit 11.
''',
    '''| Vehicle | State | Cadence | Purpose | Analysis profile |
|---|---|---|---|---|
| Ford F-350 | Enabled | Weekly | Primary purchase research | `f350_purchase` |
| RAM 3500 | Enabled | Weekly | Owned-vehicle value monitoring | `owned_vehicle_value` |
| Subaru Forester | Enabled | Weekly | Owned-vehicle value monitoring | `owned_vehicle_value` |
| Honda Odyssey | Enabled | Weekly | Family-friend purchase search | `family_friend_purchase` |
| Kia Carnival | Enabled | Weekly | Family-friend purchase search | `family_friend_purchase` |
| Ford F-150 | Enabled | Manual only | Optional curiosity | `optional_curiosity` |
| Toyota Tundra | Paused | Not runnable | Optional curiosity | `optional_curiosity` |

The weekly plan remains five vehicles and ten source runs. F-150 may run only as an explicit non-publishing single pair and is excluded from weekly reporting, health, anomalies, retention, and publication. Tundra remains paused.
''',
)
replace_once(
    baseline,
    "16. no supported output contains purchase `rank` or `score`\n",
    "16. no supported output contains purchase `rank` or `score`\n17. registry cadence keeps manual F-150 source pairs out of every weekly/full subsystem\n18. paused Tundra cannot be selected for single-pair collection\n",
)

limitations = ROOT / "docs" / "LIMITATIONS_REGISTER.md"
for old, new in (
    (
        "| LIM-026 | Medium | Implemented, validation pending | Purpose-specific secondary outputs did not exist | Audit 10 purpose-input/output/validation schemas | Audit 10 |",
        "| LIM-026 | Medium | Resolved | Purpose-specific secondary outputs did not exist | Audit 10 purpose-input/output/validation schemas and merged live validation | Audit 10 |",
    ),
    (
        "| LIM-027 | Medium | Deferred by owner | F-150 and Tundra are not polished | Both remain paused | Audit 11 |",
        "| LIM-027 | Medium | Implemented, validation pending | Optional F-150/Tundra state lacked a bounded reintroduction path | F-150 manual-only Audit 11A; Tundra remains paused for separate Audit 11B decision | Audit 11A/11B |",
    ),
    (
        "| LIM-029 | Low | Implemented, validation pending | Registry analysis profiles were not operationalized | F-350 and Audit 10 profile-specific outputs | Audit 10 |",
        "| LIM-029 | Low | Resolved | Registry analysis profiles were not operationalized | F-350 and Audit 10 profile-specific outputs, merged and validated | Audit 10 |",
    ),
    (
        "| LIM-048 | High | Implemented, validation pending | RAM historical odometer context could be mistaken for current odometer | Separate historical field; current odometer remains required | Audit 10 |",
        "| LIM-048 | High | Controlled, not fixed | RAM historical odometer context could be mistaken for current odometer | Separate historical field; current odometer remains required | Audit 10/current control |",
    ),
    (
        "| LIM-049 | Medium | Implemented, validation pending | Forester lacks subject year/trim/powertrain/drivetrain/current odometer input | `subject_profile_incomplete` and owner-input gaps | Audit 10 |",
        "| LIM-049 | Medium | Controlled, not fixed | Forester lacks subject year/trim/powertrain/drivetrain/current odometer input | `subject_profile_incomplete` and owner-input gaps | Audit 10/current control |",
    ),
    (
        "| LIM-050 | High | Implemented, validation pending | Odyssey/Carnival friend requirements are not yet supplied | `candidate_pending_requirements` and explicit friend questions | Audit 10 |",
        "| LIM-050 | High | Controlled, not fixed | Odyssey/Carnival friend requirements are not yet supplied | `candidate_pending_requirements` and explicit friend questions | Audit 10/current control |",
    ),
    (
        "| LIM-054 | High | Implemented, validation pending | Secondary artifacts could diverge from current evidence | Fail-closed underlying-evidence validator and data-PR integration | Audit 10 |",
        "| LIM-054 | High | Resolved | Secondary artifacts could diverge from current evidence | Merged fail-closed underlying-evidence validator and data-PR integration | Audit 10 |",
    ),
    (
        "| LIM-055 | High | Implemented, validation pending | Kijiji structured `vehicleEngine.fuelType` was ignored, falsely rejecting valid gas and diesel listings as unknown fuel | Structured engine/fuel parsing, hostile tests, sanitized response signatures, failed-run evidence artifacts, and five-profile live validation | Audit 10 corrective work |",
        "| LIM-055 | High | Resolved | Kijiji structured `vehicleEngine.fuelType` was ignored, falsely rejecting valid gas and diesel listings as unknown fuel | Structured engine/fuel parsing, hostile tests, sanitized response signatures, failed-run evidence artifacts, five-profile validation, and owner merge | Audit 10 corrective work |\n| LIM-056 | High | Implemented, validation pending | Enabling a manual optional vehicle could silently add it to weekly collection/reporting/retention/publication | Operational cadence plans, explicit weekly filters, F-150 profile isolation, and hostile tests | Audit 11A |",
    ),
):
    replace_once(limitations, old, new)

test = ROOT / "tests" / "test_documentation_contract.py"
replace_once(
    test,
    '            "AUDIT_10_SECONDARY_PURPOSE_OUTPUTS.md",\n',
    '            "AUDIT_10_SECONDARY_PURPOSE_OUTPUTS.md",\n            "AUDIT_11A_F150_MANUAL_REINTRODUCTION.md",\n',
)
replace_once(
    test,
    '''            "| 09 | F-350 Buyer Intelligence | Complete and merged |",
            "| 10 | Secondary Purpose Outputs | Implemented; deterministic and narrow validation pending |",
            "| 11 | Optional Search Reintroduction | Approved final stage |",
''',
    '''            "| 09 | F-350 Buyer Intelligence | Complete and merged |",
            "| 10 | Secondary Purpose Outputs | Complete and merged |",
            "| 11A | Ford F-150 Manual Reintroduction | Implemented; live validation pending |",
            "| 11B | Toyota Tundra Reconsideration | Pending owner decision |",
''',
)
replace_once(
    test,
    '''            "LIM-054",
        ):
''',
    '''            "LIM-054",
            "LIM-055",
            "LIM-056",
        ):
''',
)
replace_once(
    test,
    '''            "AUDIT_10_SECONDARY_PURPOSE_OUTPUTS.md",
        ):
''',
    '''            "AUDIT_10_SECONDARY_PURPOSE_OUTPUTS.md",
            "AUDIT_11A_F150_MANUAL_REINTRODUCTION.md",
        ):
''',
)

print("Applied Audit 11A authority and documentation updates.")
