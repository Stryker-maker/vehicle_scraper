# Audit 09 — F-350 Buyer Intelligence

## Status

Complete and merged through PR #11 on July 23, 2026.

Exact implementation head `fde06703cbe4ba3307262df3e832bcce0c49687a` passed deterministic CI and narrow live run `30017275049` before owner merge.

## Purpose

Turn current governed Ford F-350 evidence into a transparent purchase-investigation aid without opaque ranking, sale-price claims, or invented configuration/history/condition facts.

## Current evidence boundary

```text
source status schema v8
  + accepted canonical evidence v1
  + preserved adapter raw payload v1
  + current identity/lifecycle v2
  + f350_owner_overrides.json v1
  → F-350 buyer intelligence v1
```

Stale, unhealthy, wrong-run, wrong-schema, count-mismatched, discontinuous, or disconnected evidence fails closed.

## Outputs

```text
data/ford_f350/buyer_intelligence/investigation_latest.jsonl
data/ford_f350/buyer_intelligence/investigation_latest.csv
data/ford_f350/buyer_intelligence/seller_questions_latest.jsonl
data/ford_f350/buyer_intelligence/market_summary_latest.json
data/ford_f350/buyer_intelligence/market_summary_latest.md
```

## Supported context

The output may expose `source_text_reported_unverified` claims for trim, packages, cab, box, SRW/DRW, drivetrain, engine/idle hours, service records, accident/title language, and prior use. Missing evidence remains unknown.

Guarded calculations include:

```text
kilometres_per_engine_hour = mileage_km / engine_hours
idle_hour_percent = idle_hours / engine_hours × 100
```

These are usage context, not condition proof.

Observed quartiles and ordinary least squares expose cohort/sample/method details and remain asking-price context, not appraisal, transaction price, causal depreciation, or future value.

Computed classifications are explainable labels with visible reasons and no rank or score. Seller questions are prompts. Owner overrides require a reason and preserve the computed classification and source evidence.

## Live acceptance evidence

Run `30017275049` produced:

- 174 fetched = 20 accepted + 152 rejected + 2 parse failures
- 20 one-to-one buyer investigation and seller-question records
- visible unknown engine hours, idle hours, service history, VIN, and accident/title evidence
- visible unverified configuration coverage
- no rank or score
- no generated-data publication

## Stop conditions

Stop and revise before merge if stale evidence can become current buyer intelligence, missing evidence is inferred, rank/score appears, asking-price math is described as appraisal/sale value, owner overrides erase computed/source evidence, or non-F-350 assumptions enter this module.

## Non-scope

Audit 09 does not independently verify VIN, configuration, history, condition, availability, sale price, fair value, sold state, or mechanical fitness. It does not own RAM/Forester/Odyssey/Carnival outputs or F-150/Tundra reintroduction.
