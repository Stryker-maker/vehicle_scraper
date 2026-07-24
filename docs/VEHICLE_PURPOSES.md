# Vehicle Purposes and Priorities

## Authority

This document defines why each vehicle exists and how engineering effort is prioritized. Operational enablement remains controlled by `vehicle_registry.json`. Purpose inputs remain separate from collection criteria.

## Priority 1 — Ford F-350 purchase research

The primary goal is an informed early-2020s used diesel F-350 purchase, ideally model year 2023. Relevant evidence includes price, kilometres, engine/idle hours, service and accident/title history, prior use, cab, box, SRW/DRW, and drivetrain.

Owner use is approximately 5,000–8,000 km per year. Kilometres per engine hour may provide context but never proves condition.

Audit 09 supplies transparent, non-ranked investigation output, seller questions, asking-price context, and owner overrides. No opaque best-truck ranking is approved.

## Priority 2 — Owned-vehicle value monitoring

### RAM 3500

Known historical owner-reported profile:

- late-model-year 2013 RAM 3500 Laramie
- 6.7 Cummins diesel
- four-wheel drive
- automatic climate control
- 8.4-inch UConnect
- just over 400,000 km when this purpose was recorded

Purpose:

- estimate approximate current market position
- understand observed asking-price context
- identify an observed lower asking band that may inform sale planning
- support sale of the RAM to help fund the F-350 purchase

The historical odometer statement is not current odometer. Audit 10 requires a current owner input before personalized subject context can be treated as current.

The repository has no transaction-price, time-to-sale, or sale-probability evidence. It must not call an observed lower asking band a verified faster-sale range.

### Subaru Forester

Purpose:

- monitor approximate current market context
- provide comparable count, asking-price and mileage ranges, and multi-run listing-price direction

The current subject year, trim, powertrain, drivetrain, and odometer are not yet governed inputs. Until supplied, output must remain broad market context and explicitly list owner-input gaps.

### Owned-value output rule

RAM and Forester outputs may use:

- `close_subject_comparable`
- `partial_subject_comparable`
- `broad_market_context`
- `subject_profile_incomplete`
- `insufficient_configuration_evidence`

These labels need visible reasons and are not ranks, scores, appraisals, or physical-vehicle identity claims.

## Priority 3 — Family-friend family-vehicle search

### Honda Odyssey

### Kia Carnival

These searches support a family friend. Personalized review requires explicit friend input for:

- maximum all-in budget
- acceptable model-year range
- maximum mileage
- required seating
- cargo/seat-folding requirements
- travel radius
- accident/title requirements
- service-history requirements
- acceptable seller types
- availability, deposit, and inspection constraints

Until those inputs exist, accepted listings remain `candidate_pending_requirements`. Broad operational config criteria are collection boundaries, not personalized friend preferences.

Once preferences are recorded, outputs may use:

- `candidate_outside_stated_preferences`
- `candidate_with_evidence_gaps`
- `candidate_for_manual_review`

Every label requires visible reasons. Listing claims for seating, cargo features, service history, accident/title, seller, and availability remain unverified or unknown. Seller questions and independent inspection remain necessary.

Truck-specific assumptions—engine/idle hours, cab, box, SRW/DRW, towing/worksite exposure, diesel modifications, or F-350 year priorities—must never be applied to Odyssey or Carnival output.

## Priority 4 — Optional curiosity searches

### Ford F-150

There is no current purchase or ownership need. Audit 11A enables F-150 only for explicit manual, non-publishing single-pair searches. It receives current source/canonical/lifecycle evidence and a temporary optional-curiosity summary, but no specialized buyer intelligence, secondary-purpose output, rank, score, appraisal, or recommendation. Manual enablement does not place F-150 in weekly collection, health, anomaly, retention, or publication scope.

### Toyota Tundra

Tundra remains paused with historical data preserved. Any reconsideration requires a separate Audit 11B package and owner approval; it may remain paused permanently.

## Engineering priority rule

1. protect trustworthy collection and evidence
2. protect the F-350 purchase use case
3. preserve lightweight owned-vehicle monitoring
4. preserve practical family-vehicle candidate review
5. defer optional F-150 and Tundra work

Large result volume does not establish higher priority.

## Scope-change rule

Purpose, priority, inputs, or enabled state must not change merely because a collector returns many or few records. Purpose/input changes require owner authority; operational state changes require registry updates and tests.
