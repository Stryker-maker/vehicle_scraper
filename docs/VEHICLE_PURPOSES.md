# Vehicle Purposes and Priorities

## Authority

This document defines why each vehicle exists in the repository and how engineering effort should be prioritized. Operational enablement remains controlled by `vehicle_registry.json`.

The purposes below supersede any inference based only on result volume, current ownership, configuration age or historical collector behaviour.

## Priority 1 — Ford F-350 purchase research

### Purpose

The repository was originally created to gather Ford F-350 market data. Its primary goal is to help the owner make an informed purchase of an early-2020s used diesel F-350.

### Preferred target

- ideal model year: 2023
- diesel engine
- reasonable purchase price
- acceptable kilometres
- evidence about total engine hours and idle hours
- evidence about service history, accident/title history and prior commercial or fleet use
- configuration details such as cab, box length, SRW/DRW and four-wheel drive

### Mileage context

The owner drives approximately 5,000–8,000 km per year. Over five years, expected additional use is approximately 25,000–40,000 km.

A truck with above-average kilometres may still be attractive when evidence suggests more highway-oriented use and lower idle or worksite exposure. Kilometres per engine hour may provide context, but it is not proof of good condition and must never be invented when engine-hour evidence is unavailable.

### Required eventual outputs

- broad early-2020s market context
- specific highlighting of 2023 candidates
- transparent filters and candidate classifications
- visible reasons for inclusion, exclusion and missing evidence
- price-versus-mileage and year comparisons
- engine-hour and idle-hour context when verified data exists
- listing-change and candidate-watch monitoring
- manual owner notes and overrides

### Ranking rule

No opaque automated best-truck ranking is approved. Later candidate classifications must remain explainable, evidence-based and manually overridable.

## Priority 2 — Owned-vehicle value monitoring

### RAM 3500

Current owner vehicle:

- late-model-year 2013 RAM 3500 Laramie
- 6.7 Cummins diesel
- four-wheel drive
- automatic climate control
- 8.4-inch UConnect
- just over 400,000 km at the time this purpose was recorded

Purpose:

- estimate approximate current market position
- understand likely asking-price and faster-sale ranges
- support sale of the RAM to help fund the F-350 purchase

This vehicle requires a credible lightweight valuation snapshot, not an elaborate appraisal engine unless later evidence shows that additional depth is necessary.

### Subaru Forester

Purpose:

- monitor approximate current market value of the owner’s existing Forester
- provide comparable count, price and mileage ranges and multi-run market direction

The Forester is not the primary engineering focus.

## Priority 3 — Family-friend family-vehicle search

### Honda Odyssey

### Kia Carnival

These searches support a family friend who needs a family vehicle and specifically requested these two models.

The eventual review process should consider the friend’s actual:

- budget
- acceptable model years and mileage
- seating and cargo needs
- travel radius
- accident/title and service-history requirements
- dealer versus private-seller preferences
- availability and inspection constraints

These vehicles should receive practical shortlisting and missing-information checks. They must not be evaluated using F-350-specific assumptions.

## Priority 4 — Optional curiosity searches

### Ford F-150

### Toyota Tundra

There is no current purchase or ownership need for these models. They previously generated substantial runtime and data volume without contributing to an active decision.

Current rule:

- remain paused throughout the core audit
- preserve existing historical data
- do not spend core engineering or analysis effort on them
- reintroduce only at the final audit stage
- validate one optional vehicle at a time before selecting a future cadence

Reintroduction does not imply weekly scheduling. Manual-only or less-frequent collection may be more appropriate.

## Engineering priority rule

When package scope or implementation choices compete:

1. protect trustworthy collection and evidence
2. protect the F-350 purchase use case
3. preserve lightweight owned-vehicle monitoring
4. preserve practical minivan shortlisting
5. defer optional F-150 and Tundra work

Large result volume does not establish higher priority.

## Scope-change rule

A vehicle purpose, priority or enabled state must not be changed merely because a collector returns many or few records. Purpose changes require repository-owner approval; operational state changes must be made through the authoritative registry and tested against workflow expectations.