# Audit 09 — F-350 Buyer Intelligence

## Status

Implemented on `ai/audit-09-f350-buyer-intelligence`; exact-head deterministic validation, narrow live validation, owner review, and merge remain pending.

## Purpose

Turn current governed Ford F-350 listing evidence into a transparent purchase-investigation aid without creating an opaque best-truck ranking, treating asking prices as sale values, or inventing missing configuration, history, usage, or condition information.

Audit 09 supports the repository's primary purpose: investigation of an early-2020s diesel F-350, with 2023 as the ideal model year and with the owner's expected use of approximately 5,000–8,000 km per year.

## Input boundary

Buyer intelligence is built only from current-run, successful, schema-valid evidence:

- source status schema version `8`
- canonical accepted evidence schema version `1`
- source adapter raw-payload evidence schema version `1`
- identity/lifecycle current evidence schema version `2`
- governed `config_f350.json`
- governed `f350_owner_overrides.json` schema version `1`

The builder fails closed when source status is missing, stale, unhealthy, wrong-schema, or wrong-run; accepted and identity counts disagree; a canonical record lacks matching identity evidence; adapter records are missing or discontinuous; or an accepted record cannot be joined to its raw source payload.

Historical Audit 03 review CSVs are not buyer-intelligence input. Audit 09 does not reconstruct current buyer intelligence from stale CSVs or legacy rank/history fields.

## Buyer-intelligence outputs

Current outputs are written under:

```text
data/ford_f350/buyer_intelligence/investigation_latest.jsonl
data/ford_f350/buyer_intelligence/investigation_latest.csv
data/ford_f350/buyer_intelligence/seller_questions_latest.jsonl
data/ford_f350/buyer_intelligence/market_summary_latest.json
data/ford_f350/buyer_intelligence/market_summary_latest.md
```

All use buyer-intelligence schema version `1`.

The JSONL investigation artifact is the richest machine-readable record. The CSV is a decision-review projection. Seller questions remain a separate artifact so questions are not confused with source evidence or owner answers. The market summary reports aggregate coverage and observed asking-price/mileage context.

## Configuration evidence

Audit 09 examines normalized canonical fields together with the preserved raw source payload. It can expose source-text claims for:

- trim: XL, XLT, Lariat, King Ranch, Platinum, or Limited
- packages: STX, FX4, or Tremor
- cab: regular cab, SuperCab/extended cab, or crew cab
- box: long/8-foot claim or short/approximately-6.75-foot claim
- rear-wheel configuration: SRW or DRW/dually
- drivetrain: 4WD/4x4 or 2WD/RWD
- total engine hours
- idle hours
- service-record availability claims
- accident, damage, salvage, or rebuilt-title claims already exposed by canonical evidence
- prior-use claims such as one-owner, highway, towing, fleet, commercial, rental, oilfield, or work-truck use

Every extracted value remains `source_text_reported_unverified` or another explicit unverified evidence status. Package claims are not treated as trim hierarchy. `trim_tiers.json` remains legacy descriptive configuration and is not buyer-intelligence or purchase-classification authority.

When the source does not provide evidence, the field remains unknown. Audit 09 never infers engine hours, idle hours, cab, box, SRW/DRW, drivetrain, service records, accident/title truth, or prior use merely because a configuration would be common.

## Derived usage context

When both mileage and total engine hours are source-reported, Audit 09 may calculate:

```text
kilometres_per_engine_hour = mileage_km / engine_hours
```

When total and idle hours are source-reported and internally possible, it may calculate:

```text
idle_hour_percent = idle_hours / engine_hours × 100
```

These values are usage context only. They do not prove highway use, low wear, good condition, or purchase suitability. Idle hours greater than total engine hours produce a visible warning and no idle percentage.

## Evidence completeness

Each listing exposes whether the investigation evidence is `complete`, `partial`, or `insufficient`, plus the exact missing fields among:

- VIN
- cab configuration
- box configuration
- rear-wheel configuration
- drivetrain
- engine hours
- idle hours
- service history
- accident/title evidence
- prior-use evidence

Completeness describes the presence of evidence, not its independent truth or the condition of the truck.

## Asking-price bands

Price bands are observed quartiles of current accepted listing claims. Cohorts are selected transparently in this order:

1. exact model year when at least three comparables exist
2. target year plus or minus one year when at least three exist
3. early-2020s model years 2020–2023 when relevant and sufficient
4. all current accepted F-350 claims as broad context

The output exposes cohort basis, comparable count, first quartile, median, third quartile, listing position relative to the observed interquartile range, and difference from the observed median.

These are asking-price observations from configured queries. They are not sale-price evidence, appraisal, fair-market-value authority, or complete-market coverage.

## Mileage-adjusted projection

When a cohort contains at least five valid price/mileage pairs with enough mileage variation, Audit 09 calculates a transparent ordinary least-squares relationship between asking price and mileage. It exposes:

- sample count
- projected asking-price context at the listing mileage
- slope in CAD per 10,000 km
- intercept
- coefficient of determination (`r_squared`)

This is descriptive current asking-price context only. It is not depreciation forecasting, future resale value, appraisal, or causal evidence. Insufficient samples or variation produce an explicit unavailable status rather than a number.

## Owner-use mileage scenario

For each listing with a mileage claim, Audit 09 shows a five-year mileage scenario using the owner's stated expected use:

```text
current mileage + 25,000 km
current mileage + 40,000 km
```

The range is an owner-use scenario, not an odometer or future-value guarantee.

## Explainable classifications

Computed classifications are labels, not scores or ranks:

- `investigate_priority`
- `investigate_with_evidence_gaps`
- `investigate_price_concern`
- `concern_review`
- `market_context_only`
- `insufficient_evidence`

Every computed classification includes visible reasons such as year fit, evidence completeness, observed price position, broad-market-only year, or a source-reported accident/title concern.

Audit 09 does not emit `rank`, `score`, weighted purchase points, or an automatic best-truck decision. Output ordering is deterministic for review convenience and has no recommendation meaning.

## Seller questions

Questions are generated from visible evidence gaps and concerns. They may request:

- full VIN plus VIN-plate and registration images
- instrument-cluster evidence of total and idle hours
- cab, box, SRW/DRW, and drivetrain confirmation
- maintenance and repair records
- current vehicle-history report and accident/title documents
- prior personal, fleet, commercial, rental, oilfield, towing, plowing, or idle use
- documentation for source-reported accident or title concerns
- major repair history for high-mileage trucks
- stock versus tuned/deleted/modified engine, emissions, fuel, and transmission systems
- true cold start, independent pre-purchase inspection, and diagnostic scan

Questions are investigation prompts. Their presence is not evidence that a defect exists, and unanswered questions do not become inferred negative claims.

## Owner annotations and overrides

`f350_owner_overrides.json` is a governed, reviewable owner-input file keyed by `canonical_listing_id`.

Supported owner fields are:

- `owner_disposition`: `unreviewed`, `contacted`, `inspection_planned`, `hold`, `pass`, or `purchased`
- `owner_note`
- `owner_tags`
- `classification_override`: `priority_investigate`, `investigate`, `hold`, `pass`, or `market_context_only`
- `override_reason`

A classification override requires a reason. The output always preserves:

- the computed classification
- computed reasons
- owner classification override
- owner override reason
- effective classification

Owner input never rewrites canonical evidence, source claims, identity evidence, market calculations, or the computed classification.

## Workflow integration

For an F-350 `single_pair` validation, buyer intelligence builds from only the selected current source and is included in the seven-day smoke artifact. It does not publish generated data.

For a full run, combined AutoTrader/Kijiji buyer intelligence builds only after all source health passes. It is included in full-run diagnostics and in the governed staged data set when publication is authorized.

Single-pair runs for RAM 3500, Subaru Forester, Honda Odyssey, or Kia Carnival do not build F-350 buyer intelligence. Purpose-specific outputs for those vehicles remain Audit 10 scope.

## Acceptance gate

Audit 09 is acceptable only when deterministic and hostile tests prove:

- missing evidence stays unknown
- configuration and usage claims preserve unverified status
- hour calculations are guarded and labelled as context
- stale, unhealthy, wrong-run, wrong-schema, count-mismatched, or disconnected evidence fails closed
- price cohorts and quartiles are deterministic and expose sample counts
- regression is unavailable below its minimum evidence threshold
- regression exposes assumptions and does not claim appraisal/future value
- five-year mileage output uses the approved owner-use range
- seller questions correspond to missing evidence or visible concerns
- owner overrides require valid values and reasons
- computed and overridden classifications remain separate
- supported outputs contain no rank or score
- workflow integration is F-350-specific and follows source-health gates
- source collection, parsing, canonical equations, identity rules, retention limits, and other vehicle outputs remain unchanged

A narrow live F-350 source run on the exact final implementation head must also prove raw-payload joining, identity joining, artifact generation, and the no-publication boundary.

## Stop conditions

Stop and revise before merge if:

- stale or legacy CSV data can become current buyer intelligence
- missing evidence is inferred as a positive or negative fact
- package names become trim-value authority
- a rank, score, or hidden weighted recommendation appears
- asking-price bands are described as sale prices or appraisal
- a regression is presented without sample count, slope, and interpretation limits
- an owner override rewrites source or computed evidence
- buyer intelligence can build before current source health and identity evidence pass
- non-F-350 outputs or optional vehicles enter this package
- source requests, parsing, filters, pagination, geography, distance, identity/lifecycle thresholds, or retention limits change without a separately approved reason

## Non-scope

Audit 09 does not independently verify VIN, configuration, service history, accidents, title, prior use, condition, availability, sale price, fair value, sold state, or mechanical fitness. It does not fetch proprietary vehicle-history reports, decode VINs against an external authority, contact sellers, inspect trucks, predict repair costs, create purpose-specific RAM/Forester/Odyssey/Carnival outputs, or re-enable F-150/Tundra.
