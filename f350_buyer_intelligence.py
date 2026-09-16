from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any, Sequence

from canonical_evidence import read_jsonl, write_jsonl
from identity_lifecycle import IDENTITY_LIFECYCLE_SCHEMA_VERSION, load_current_identity_records
from phase1_common import load_json, source_status_path, status_is_current_success, utc_now, write_json
from vehicle_config import load_vehicle_config

BUYER_SCHEMA_VERSION = 1
OWNER_OVERRIDE_SCHEMA_VERSION = 1
SOURCE_STATUS_SCHEMA_VERSION = 8
SUPPORTED_SOURCES = ("autotrader", "kijiji")
OWNER_ANNUAL_KM_MIN = 5_000
OWNER_ANNUAL_KM_MAX = 8_000
PROJECTION_YEARS = 5
MIN_BAND_COHORT = 3
MIN_REGRESSION_COHORT = 5
UNKNOWN = {"", "unknown", "n/a", "na", "none", "null", "unavailable"}
OWNER_DISPOSITIONS = {"unreviewed", "contacted", "inspection_planned", "hold", "pass", "purchased"}
OWNER_CLASSIFICATIONS = {"priority_investigate", "investigate", "hold", "pass", "market_context_only"}

CSV_FIELDS = (
    "buyer_intelligence_schema_version", "run_id", "scope", "vehicle_key", "source",
    "canonical_listing_id", "source_listing_id", "listing_url", "lifecycle_state",
    "vin_claim", "vin_evidence_status", "year", "year_fit", "price_cad", "mileage_km",
    "distance_km", "trim_claim", "trim_evidence_status", "package_claims",
    "cab_configuration_claim", "cab_configuration_evidence_status", "box_configuration_claim",
    "box_configuration_evidence_status", "rear_wheel_configuration_claim",
    "rear_wheel_configuration_evidence_status", "drivetrain_claim", "drivetrain_evidence_status",
    "engine_hours_claim", "engine_hours_evidence_status", "idle_hours_claim",
    "idle_hours_evidence_status", "km_per_engine_hour", "idle_hour_percent",
    "service_history_claim", "service_history_evidence_status", "accident_title_claim",
    "accident_title_evidence_status", "prior_use_claims", "evidence_completeness",
    "missing_investigation_fields", "price_band_basis", "price_band_comparable_count",
    "price_band_q1_cad", "price_band_median_cad", "price_band_q3_cad", "price_position",
    "price_difference_from_median_cad", "mileage_adjusted_projection_cad",
    "projection_slope_cad_per_10000_km", "projection_r_squared",
    "projected_mileage_5y_min_km", "projected_mileage_5y_max_km",
    "computed_classification", "computed_classification_reasons", "owner_disposition",
    "owner_note", "owner_tags", "owner_classification_override", "owner_override_reason",
    "override_applied", "effective_classification", "seller_question_count",
    "seller_questions_ref", "raw_record_ref", "source_adapter_record_ref",
)


def artifact_paths(root: Path, config: dict[str, Any]) -> dict[str, Path]:
    base = root / "data" / str(config["vehicle_key"]) / "buyer_intelligence"
    return {
        "investigation_jsonl": base / "investigation_latest.jsonl",
        "investigation_csv": base / "investigation_latest.csv",
        "seller_questions": base / "seller_questions_latest.jsonl",
        "market_summary_json": base / "market_summary_latest.json",
        "market_summary_markdown": base / "market_summary_latest.md",
    }


def _text(value: Any) -> str:
    if value is None:
        return ""
    cleaned = str(value).strip()
    return "" if cleaned.casefold() in UNKNOWN else cleaned


def _int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    cleaned = re.sub(r"[^0-9-]", "", _text(value))
    try:
        return int(cleaned) if cleaned else None
    except ValueError:
        return None


def _float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _flatten(value: Any, path: str = "") -> list[str]:
    result: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            result.extend(_flatten(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.extend(_flatten(child, f"{path}[{index}]"))
    elif isinstance(value, (str, int, float)) and not isinstance(value, bool):
        text = str(value).strip()
        if text:
            result.append(f"{path}={text}" if path else text)
    return result


def source_text(raw_payload: Any, normalized: dict[str, Any]) -> str:
    values = [
        _text(normalized.get("trim")), _text(normalized.get("engine")),
        _text(normalized.get("fuel")), _text(normalized.get("accident_claim")),
        *_flatten(raw_payload),
    ]
    return " | ".join(value for value in values if value)


def _match(text: str, options: Sequence[tuple[str, Sequence[str]]]) -> tuple[str | None, str | None]:
    for value, patterns in options:
        for pattern in patterns:
            found = re.search(pattern, text, flags=re.IGNORECASE)
            if found:
                return value, found.group(0)
    return None, None


def _claim(value: Any, matched: Any = None) -> dict[str, Any]:
    known = value not in (None, "", [], "unknown", "Unknown")
    return {
        "value": value,
        "evidence_status": "source_text_reported_unverified" if known else "unknown",
        "matched_text": matched,
    }


def _hours(text: str, kind: str) -> tuple[int | None, str | None]:
    label = "engine" if kind == "engine" else "idle"
    patterns = (
        rf"\b(?:total\s+)?{label}\s*(?:hours?|hrs?)\s*[:#-]?\s*([0-9][0-9,]*)\b",
        rf"\b([0-9][0-9,]*)\s*(?:total\s+)?{label}\s*(?:hours?|hrs?)\b",
    )
    for pattern in patterns:
        found = re.search(pattern, text, flags=re.IGNORECASE)
        if found:
            value = _int(found.group(1))
            if value is not None:
                return value, found.group(0)
    return None, None


def extract_configuration_evidence(normalized: dict[str, Any], raw_payload: Any) -> dict[str, Any]:
    text = source_text(raw_payload, normalized)
    trim, trim_match = _match(text, (
        ("Limited", (r"\blimited\b",)), ("Platinum", (r"\bplatinum\b",)),
        ("King Ranch", (r"\bking\s+ranch\b",)), ("Lariat", (r"\blariat\b",)),
        ("XLT", (r"\bxlt\b",)), ("XL", (r"\bxl\b",)),
    ))
    packages: list[str] = []
    package_matches: list[str] = []
    for value, patterns in (("Tremor", (r"\btremor\b",)), ("FX4", (r"\bfx4\b",)), ("STX", (r"\bstx\b",))):
        matched, raw = _match(text, ((value, patterns),))
        if matched:
            packages.append(matched)
            if raw:
                package_matches.append(raw)
    cab, cab_match = _match(text, (
        ("crew_cab", (r"\bcrew\s*cab\b", r"\bsuper\s*crew\b")),
        ("supercab", (r"\bsuper\s*cab\b", r"\bextended\s*cab\b", r"\bext\.?\s*cab\b")),
        ("regular_cab", (r"\bregular\s*cab\b", r"\breg\.?\s*cab\b", r"\bstandard\s*cab\b")),
    ))
    box, box_match = _match(text, (
        ("long_box_or_8ft_claim", (r"\blong\s+(?:box|bed)\b", r"\b8(?:\.0)?\s*(?:ft|foot|feet)\s*(?:box|bed)?\b", r"\b8['’]\s*(?:box|bed)?\b")),
        ("short_box_or_6_75ft_claim", (r"\bshort\s+(?:box|bed)\b", r"\b6(?:\.75|\s*3\s*/\s*4)\s*(?:ft|foot|feet)\s*(?:box|bed)?\b", r"\b6['’]\s*9(?:[\"”]|in(?:ch(?:es)?)?)?\s*(?:box|bed)?\b")),
    ))
    rear, rear_match = _match(text, (
        ("drw", (r"\bdrw\b", r"\bdually\b", r"\bdual\s+rear\s+wheel(?:s)?\b")),
        ("srw", (r"\bsrw\b", r"\bsingle\s+rear\s+wheel(?:s)?\b")),
    ))
    drivetrain, drivetrain_match = _match(text, (
        ("4wd", (r"\b4x4\b", r"\b4wd\b", r"\bfour[-\s]*wheel\s*drive\b")),
        ("2wd", (r"\b2wd\b", r"\brwd\b", r"\brear[-\s]*wheel\s*drive\b")),
    ))
    engine_hours, engine_match = _hours(text, "engine")
    idle_hours, idle_match = _hours(text, "idle")
    lowered = text.casefold()
    if re.search(r"\b(?:no|without)\s+(?:service|maintenance)\s+records?\b", lowered):
        service, service_match = "records_not_available_claim", "no service records"
    else:
        service, service_match = _match(text, (("records_available_claim", (
            r"\bfull\s+service\s+history\b", r"\bservice\s+records?\s+(?:available|included)\b",
            r"\bmaintenance\s+records?\s+(?:available|included)\b", r"\bdealer[-\s]+maintained\b",
        )),))
    accident = _text(normalized.get("accident_claim")) or "Unknown"
    use_claims: list[str] = []
    negative_commercial = bool(re.search(r"\b(?:never|not|no)\s+(?:used\s+)?(?:as\s+)?(?:a\s+)?(?:fleet|commercial|rental)\b", lowered))
    for label, pattern in (
        ("fleet_use_claim", r"\bfleet\b"), ("commercial_use_claim", r"\bcommercial(?:ly)?\b"),
        ("rental_use_claim", r"\brental\b"), ("oilfield_use_claim", r"\boil\s*field\b|\boilfield\b"),
        ("work_truck_claim", r"\bwork\s+truck\b"),
        ("highway_use_claim", r"\bhighway\s+(?:km|kms|kilometres|miles|use)\b"),
        ("towing_use_claim", r"\btow(?:ed|ing)?\b"), ("one_owner_claim", r"\bone[-\s]+owner\b"),
    ):
        if re.search(pattern, text, flags=re.IGNORECASE):
            if negative_commercial and label in {"fleet_use_claim", "commercial_use_claim", "rental_use_claim"}:
                continue
            use_claims.append(label)
    if negative_commercial:
        use_claims.append("no_fleet_commercial_rental_use_claim")
    return {
        "source_text_digest_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "trim": _claim(trim, trim_match),
        "packages": _claim(sorted(set(packages)), sorted(set(package_matches))),
        "cab_configuration": _claim(cab, cab_match),
        "box_configuration": _claim(box, box_match),
        "rear_wheel_configuration": _claim(rear, rear_match),
        "drivetrain": _claim(drivetrain, drivetrain_match),
        "engine_hours": _claim(engine_hours, engine_match),
        "idle_hours": _claim(idle_hours, idle_match),
        "service_history": _claim(service, service_match),
        "accident_title": {
            "value": accident,
            "evidence_status": "source_reported_or_text_derived_unverified" if _text(accident) else "unknown",
            "matched_text": None,
        },
        "prior_use_claims": _claim(sorted(set(use_claims))),
    }


def year_fit(year: int | None) -> str:
    if year == 2023:
        return "ideal_2023"
    if isinstance(year, int) and 2020 <= year <= 2022:
        return "early_2020s_target"
    if isinstance(year, int) and 2015 <= year <= 2019:
        return "broad_market_context"
    return "unknown"


def percentile(values: Sequence[float], quantile: float) -> float | None:
    clean = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    position = (len(clean) - 1) * quantile
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return clean[lower]
    weight = position - lower
    return clean[lower] * (1 - weight) + clean[upper] * weight


def cohort(rows: Sequence[dict[str, Any]], target: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    priced = [row for row in rows if isinstance(row.get("price_cad"), int) and row["price_cad"] > 0]
    year = target.get("year")
    if isinstance(year, int):
        exact = [row for row in priced if row.get("year") == year]
        if len(exact) >= MIN_BAND_COHORT:
            return f"exact_model_year_{year}", exact
        adjacent = [row for row in priced if isinstance(row.get("year"), int) and abs(row["year"] - year) <= 1]
        if len(adjacent) >= MIN_BAND_COHORT:
            return f"model_year_{year}_plus_minus_1", adjacent
        if 2020 <= year <= 2023:
            target_rows = [row for row in priced if isinstance(row.get("year"), int) and 2020 <= row["year"] <= 2023]
            if len(target_rows) >= MIN_BAND_COHORT:
                return "early_2020s_2020_2023", target_rows
    return "all_current_accepted_f350_claims", priced


def regression(rows: Sequence[dict[str, Any]], mileage_km: int | None) -> dict[str, Any]:
    pairs = [(float(row["mileage_km"]), float(row["price_cad"])) for row in rows
             if isinstance(row.get("mileage_km"), int) and row["mileage_km"] >= 0
             and isinstance(row.get("price_cad"), int) and row["price_cad"] > 0]
    base = {"sample_count": len(pairs), "projected_asking_price_cad": None,
            "slope_cad_per_10000_km": None, "intercept_cad": None, "r_squared": None,
            "meaning": "asking_price_context_not_appraisal_or_future_value"}
    if mileage_km is None or len(pairs) < MIN_REGRESSION_COHORT or len({x for x, _ in pairs}) < 3:
        return {**base, "status": "insufficient_comparables"}
    mean_x = statistics.fmean(x for x, _ in pairs)
    mean_y = statistics.fmean(y for _, y in pairs)
    denominator = sum((x - mean_x) ** 2 for x, _ in pairs)
    if denominator <= 0:
        return {**base, "status": "insufficient_mileage_variation"}
    slope = sum((x - mean_x) * (y - mean_y) for x, y in pairs) / denominator
    intercept = mean_y - slope * mean_x
    total = sum((y - mean_y) ** 2 for _, y in pairs)
    residual = sum((y - (intercept + slope * x)) ** 2 for x, y in pairs)
    r2 = 1 - residual / total if total > 0 else 0.0
    return {**base, "status": "available", "projected_asking_price_cad": round(intercept + slope * mileage_km),
            "slope_cad_per_10000_km": round(slope * 10_000, 2), "intercept_cad": round(intercept, 2),
            "r_squared": round(r2, 4)}


def market_context(rows: Sequence[dict[str, Any]], target: dict[str, Any]) -> dict[str, Any]:
    basis, selected = cohort(rows, target)
    prices = [float(row["price_cad"]) for row in selected]
    q1, median, q3 = percentile(prices, 0.25), percentile(prices, 0.5), percentile(prices, 0.75)
    price = target.get("price_cad")
    if not isinstance(price, int) or len(selected) < MIN_BAND_COHORT or None in (q1, median, q3):
        position, difference = "insufficient_comparables", None
    elif price < q1:
        position, difference = "below_observed_interquartile_range", round(price - median)
    elif price > q3:
        position, difference = "above_observed_interquartile_range", round(price - median)
    else:
        position, difference = "within_observed_interquartile_range", round(price - median)
    return {
        "cohort_basis": basis, "comparable_count": len(selected),
        "price_q1_cad": None if q1 is None else round(q1),
        "price_median_cad": None if median is None else round(median),
        "price_q3_cad": None if q3 is None else round(q3),
        "price_position": position, "price_difference_from_median_cad": difference,
        "mileage_adjusted_asking_price_projection": regression(selected, target.get("mileage_km")),
        "market_scope": "configured_query_accepted_listing_claims_not_complete_market",
    }


def evidence_completeness(configuration: dict[str, Any], identity: dict[str, Any]) -> tuple[str, list[str]]:
    present = {
        "vin": identity.get("vin_evidence_status") == "source_reported_format_valid_unverified",
        "cab_configuration": configuration["cab_configuration"]["value"] is not None,
        "box_configuration": configuration["box_configuration"]["value"] is not None,
        "rear_wheel_configuration": configuration["rear_wheel_configuration"]["value"] is not None,
        "drivetrain": configuration["drivetrain"]["value"] is not None,
        "engine_hours": configuration["engine_hours"]["value"] is not None,
        "idle_hours": configuration["idle_hours"]["value"] is not None,
        "service_history": configuration["service_history"]["value"] is not None,
        "accident_title": bool(_text(configuration["accident_title"]["value"])),
        "prior_use": bool(configuration["prior_use_claims"]["value"]),
    }
    missing = sorted(key for key, value in present.items() if not value)
    known = len(present) - len(missing)
    return ("complete" if known >= 8 else "partial" if known >= 4 else "insufficient"), missing


def hour_context(mileage: int | None, engine_hours: int | None, idle_hours: int | None) -> dict[str, Any]:
    km_per_hour = round(mileage / engine_hours, 2) if isinstance(mileage, int) and isinstance(engine_hours, int) and engine_hours > 0 else None
    warnings: list[str] = []
    idle_percent = None
    if isinstance(engine_hours, int) and engine_hours > 0 and isinstance(idle_hours, int) and idle_hours >= 0:
        if idle_hours > engine_hours:
            warnings.append("idle_hours_exceed_engine_hours")
        else:
            idle_percent = round(idle_hours / engine_hours * 100, 2)
    return {"km_per_engine_hour": km_per_hour, "idle_hour_percent": idle_percent,
            "warnings": warnings, "meaning": "usage_context_only_not_condition_proof"}


def classify(year_fit_value: str, completeness: str, market: dict[str, Any], accident: str) -> tuple[str, list[str]]:
    reasons = [f"year_fit:{year_fit_value}", f"evidence_completeness:{completeness}"]
    if any(term in accident.casefold() for term in ("salvage", "rebuilt", "structural")):
        return "concern_review", reasons + ["source_accident_or_title_concern"]
    if year_fit_value == "broad_market_context":
        return "market_context_only", reasons + ["outside_early_2020s_target"]
    if year_fit_value == "unknown":
        return "insufficient_evidence", reasons + ["year_fit_unknown"]
    if market["price_position"] == "above_observed_interquartile_range":
        return "investigate_price_concern", reasons + ["asking_price_above_observed_interquartile_range"]
    if completeness == "insufficient":
        return "investigate_with_evidence_gaps", reasons + ["multiple_investigation_fields_missing"]
    return "investigate_priority", reasons + ["target_year_without_visible_hard_concern"]


def seller_questions(normalized: dict[str, Any], configuration: dict[str, Any], missing: Sequence[str]) -> list[dict[str, str]]:
    questions: list[dict[str, str]] = []
    def add(category: str, priority: str, question: str, reason: str) -> None:
        questions.append({"category": category, "priority": priority, "question": question, "reason": reason})
    gaps = set(missing)
    if "vin" in gaps:
        add("identity", "high", "What is the full VIN, and can you provide a clear photo of the VIN plate and registration?", "vin_not_source_reported")
    if "engine_hours" in gaps or "idle_hours" in gaps:
        add("usage", "high", "What are the total engine hours and idle hours? Please provide a current instrument-cluster photo showing both.", "engine_or_idle_hours_missing")
    if "cab_configuration" in gaps or "box_configuration" in gaps:
        add("configuration", "high", "Please confirm the cab configuration and box length, with photos showing the full side profile and bed.", "cab_or_box_configuration_missing")
    if "rear_wheel_configuration" in gaps:
        add("configuration", "high", "Is the truck single-rear-wheel or dual-rear-wheel?", "rear_wheel_configuration_missing")
    if "drivetrain" in gaps:
        add("configuration", "high", "Is the truck four-wheel drive, and does the 4x4 system operate correctly in all modes?", "drivetrain_missing")
    if "service_history" in gaps:
        add("history", "high", "What maintenance and repair records are available, including engine, transmission, fuel, emissions, cooling, brakes, steering, and front-end work?", "service_history_missing")
    if "accident_title" in gaps:
        add("history", "high", "Can you provide a current vehicle-history report and confirm any accidents, insurance claims, rebuilt/salvage status, or structural repairs?", "accident_title_evidence_missing")
    if "prior_use" in gaps:
        add("prior_use", "medium", "How was the truck used previously—personal, fleet, commercial, oilfield, towing, plowing, or extended idling?", "prior_use_evidence_missing")
    accident = _text(configuration["accident_title"]["value"]).casefold()
    if accident and accident != "no accidents reported":
        add("history", "high", "Please provide repair invoices, damage photos, inspection records, and title-status documents for the reported accident or damage history.", "source_accident_or_title_claim_requires_documents")
    mileage = _int(normalized.get("mileage_km"))
    if isinstance(mileage, int) and mileage >= 200_000:
        add("high_mileage", "high", "At this mileage, what major repairs or replacements have been completed, and what known work is currently due?", "mileage_at_or_above_200000_km")
    add("modifications", "high", "Are the engine, emissions, fuel, and transmission systems stock? List any tuning, deletes, aftermarket parts, or major replacements.", "modification_state_required_for_diesel_purchase")
    add("inspection", "high", "Can the truck be viewed from a true cold start and undergo an independent pre-purchase inspection and diagnostic scan?", "independent_condition_verification_required")
    return questions


def load_owner_overrides(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": OWNER_OVERRIDE_SCHEMA_VERSION, "vehicle_key": "ford_f350", "overrides": {}}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != OWNER_OVERRIDE_SCHEMA_VERSION:
        raise ValueError("Owner override schema version mismatch")
    if value.get("vehicle_key") != "ford_f350" or not isinstance(value.get("overrides"), dict):
        raise ValueError("Owner override vehicle or overrides mismatch")
    allowed = {"owner_disposition", "owner_note", "owner_tags", "classification_override", "override_reason"}
    for canonical_id, override in value["overrides"].items():
        if not isinstance(canonical_id, str) or not canonical_id or not isinstance(override, dict):
            raise ValueError("Owner override entries must be canonical-ID objects")
        unknown = sorted(set(override) - allowed)
        if unknown:
            raise ValueError(f"Unknown owner override field(s) for {canonical_id}: {', '.join(unknown)}")
        disposition = override.get("owner_disposition", "unreviewed")
        if disposition not in OWNER_DISPOSITIONS:
            raise ValueError(f"Unsupported owner disposition for {canonical_id}: {disposition}")
        classification = override.get("classification_override")
        if classification is not None and classification not in OWNER_CLASSIFICATIONS:
            raise ValueError(f"Unsupported classification override for {canonical_id}: {classification}")
        if classification and not _text(override.get("override_reason")):
            raise ValueError(f"classification_override requires override_reason for {canonical_id}")
        tags = override.get("owner_tags", [])
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            raise ValueError(f"owner_tags must be a string list for {canonical_id}")
    return value


def owner_annotation(canonical_id: str, overrides: dict[str, Any], computed: str) -> dict[str, Any]:
    override = overrides.get("overrides", {}).get(canonical_id, {})
    classification = override.get("classification_override")
    return {
        "owner_disposition": override.get("owner_disposition", "unreviewed"),
        "owner_note": _text(override.get("owner_note")),
        "owner_tags": sorted(set(override.get("owner_tags", []))),
        "classification_override": classification,
        "override_reason": _text(override.get("override_reason")),
        "override_applied": classification is not None,
        "effective_classification": classification or computed,
        "override_contract": "owner_classification_only_source_evidence_unchanged",
    }


def _raw_payloads(root: Path, status: dict[str, Any], source: str, run_id: str) -> dict[int, Any]:
    relative = status.get("source_adapter_artifacts", {}).get("records")
    if not relative:
        raise ValueError(f"{source}: missing adapter records artifact")
    records = read_jsonl(root / str(relative))
    result: dict[int, Any] = {}
    for expected, record in enumerate(records):
        if record.get("run_id") != run_id or record.get("source") != source:
            raise ValueError(f"{source}: adapter record run/source mismatch")
        if record.get("source_record_index") != expected:
            raise ValueError(f"{source}: adapter record index discontinuity")
        result[expected] = record.get("raw_payload")
    return result


def load_source_bundles(root: Path, config: dict[str, Any], source: str, run_id: str) -> list[dict[str, Any]]:
    if source not in SUPPORTED_SOURCES:
        raise ValueError(f"Unsupported source: {source}")
    status_path = source_status_path(root, config, source)
    if not status_path.exists():
        raise ValueError(f"{source}: source status missing")
    status = load_json(status_path)
    if status.get("schema_version") != SOURCE_STATUS_SCHEMA_VERSION or not status_is_current_success(status, run_id):
        raise ValueError(f"{source}: source status is not current schema-v8 success")
    if status.get("identity_lifecycle_schema_version") != IDENTITY_LIFECYCLE_SCHEMA_VERSION:
        raise ValueError(f"{source}: identity lifecycle schema mismatch")
    accepted_path = status.get("canonical_evidence_artifacts", {}).get("accepted")
    if not accepted_path:
        raise ValueError(f"{source}: accepted canonical artifact missing")
    accepted = read_jsonl(root / str(accepted_path))
    identities = load_current_identity_records(root=root, config=config, source=source, run_id=run_id)
    if len(accepted) != int(status.get("accepted_record_count", -1)) or len(identities) != len(accepted):
        raise ValueError(f"{source}: accepted/identity count mismatch")
    identity_by_id = {str(record.get("canonical_listing_id")): record for record in identities}
    raw_by_index = _raw_payloads(root, status, source, run_id)
    bundles: list[dict[str, Any]] = []
    for record in accepted:
        if record.get("run_id") != run_id or record.get("source") != source or record.get("record_stage") != "accepted":
            raise ValueError(f"{source}: accepted canonical record mismatch")
        canonical_id = _text(record.get("canonical_listing_id"))
        index = record.get("source_record_index")
        if not canonical_id or canonical_id not in identity_by_id or not isinstance(index, int) or index not in raw_by_index:
            raise ValueError(f"{source}: accepted record lacks identity or raw payload")
        bundles.append({"record": record, "identity": identity_by_id[canonical_id], "raw_payload": raw_by_index[index]})
    return bundles


def _base(bundle: dict[str, Any], scope: str) -> dict[str, Any]:
    record, identity = bundle["record"], bundle["identity"]
    normalized = record.get("normalized", {})
    return {
        "buyer_intelligence_schema_version": BUYER_SCHEMA_VERSION, "run_id": record.get("run_id"),
        "scope": scope, "vehicle_key": record.get("vehicle_key"), "source": record.get("source"),
        "canonical_listing_id": record.get("canonical_listing_id"), "source_listing_id": record.get("source_listing_id"),
        "listing_url": normalized.get("listing_url"), "lifecycle_state": identity.get("lifecycle_state"),
        "vin_claim": identity.get("vin_claim"), "vin_evidence_status": identity.get("vin_evidence_status"),
        "year": _int(normalized.get("year")), "price_cad": _int(normalized.get("price_cad")),
        "mileage_km": _int(normalized.get("mileage_km")), "distance_km": _float(normalized.get("distance_km")),
        "raw_record_ref": record.get("raw_record_ref"), "source_adapter_record_ref": record.get("source_adapter_record_ref"),
        "normalized": normalized,
    }


def _listing(bundle: dict[str, Any], market_rows: Sequence[dict[str, Any]], overrides: dict[str, Any], paths: dict[str, str], scope: str) -> tuple[dict[str, Any], dict[str, Any]]:
    base = _base(bundle, scope)
    identity = bundle["identity"]
    configuration = extract_configuration_evidence(base["normalized"], bundle["raw_payload"])
    completeness, missing = evidence_completeness(configuration, identity)
    hours = hour_context(base["mileage_km"], configuration["engine_hours"]["value"], configuration["idle_hours"]["value"])
    market = market_context(market_rows, base)
    fit = year_fit(base["year"])
    computed, reasons = classify(fit, completeness, market, _text(configuration["accident_title"]["value"]))
    owner = owner_annotation(str(base["canonical_listing_id"]), overrides, computed)
    questions = seller_questions(base["normalized"], configuration, missing)
    projected_min = base["mileage_km"] + OWNER_ANNUAL_KM_MIN * PROJECTION_YEARS if isinstance(base["mileage_km"], int) else None
    projected_max = base["mileage_km"] + OWNER_ANNUAL_KM_MAX * PROJECTION_YEARS if isinstance(base["mileage_km"], int) else None
    rich = {**{key: value for key, value in base.items() if key != "normalized"},
            "year_fit": fit, "configuration_evidence": configuration, "derived_hour_context": hours,
            "evidence_completeness": completeness, "missing_investigation_fields": missing,
            "market_context": market,
            "ownership_mileage_projection": {"annual_km_min": OWNER_ANNUAL_KM_MIN, "annual_km_max": OWNER_ANNUAL_KM_MAX,
                "projection_years": PROJECTION_YEARS, "projected_mileage_min_km": projected_min,
                "projected_mileage_max_km": projected_max,
                "meaning": "owner_usage_scenario_not_odometer_or_value_guarantee"},
            "computed_classification": computed, "computed_classification_reasons": reasons,
            "owner_annotation": owner, "seller_question_count": len(questions),
            "seller_questions_ref": f"{paths['seller_questions']}#canonical_listing_id={base['canonical_listing_id']}",
            "decision_contract": "explainable_classification_not_rank_not_score_manual_override_preserves_source_evidence"}
    question_record = {"buyer_intelligence_schema_version": BUYER_SCHEMA_VERSION, "run_id": base["run_id"],
                       "vehicle_key": base["vehicle_key"], "source": base["source"],
                       "canonical_listing_id": base["canonical_listing_id"], "listing_url": base["listing_url"],
                       "questions": questions}
    return rich, question_record


def csv_row(value: dict[str, Any]) -> dict[str, Any]:
    config, market, owner = value["configuration_evidence"], value["market_context"], value["owner_annotation"]
    projection, hours, regression_value = value["ownership_mileage_projection"], value["derived_hour_context"], market["mileage_adjusted_asking_price_projection"]
    return {
        "buyer_intelligence_schema_version": value["buyer_intelligence_schema_version"], "run_id": value["run_id"],
        "scope": value["scope"], "vehicle_key": value["vehicle_key"], "source": value["source"],
        "canonical_listing_id": value["canonical_listing_id"], "source_listing_id": value["source_listing_id"],
        "listing_url": value["listing_url"], "lifecycle_state": value["lifecycle_state"], "vin_claim": value["vin_claim"],
        "vin_evidence_status": value["vin_evidence_status"], "year": value["year"], "year_fit": value["year_fit"],
        "price_cad": value["price_cad"], "mileage_km": value["mileage_km"], "distance_km": value["distance_km"],
        "trim_claim": config["trim"]["value"], "trim_evidence_status": config["trim"]["evidence_status"],
        "package_claims": ";".join(config["packages"]["value"]),
        "cab_configuration_claim": config["cab_configuration"]["value"], "cab_configuration_evidence_status": config["cab_configuration"]["evidence_status"],
        "box_configuration_claim": config["box_configuration"]["value"], "box_configuration_evidence_status": config["box_configuration"]["evidence_status"],
        "rear_wheel_configuration_claim": config["rear_wheel_configuration"]["value"], "rear_wheel_configuration_evidence_status": config["rear_wheel_configuration"]["evidence_status"],
        "drivetrain_claim": config["drivetrain"]["value"], "drivetrain_evidence_status": config["drivetrain"]["evidence_status"],
        "engine_hours_claim": config["engine_hours"]["value"], "engine_hours_evidence_status": config["engine_hours"]["evidence_status"],
        "idle_hours_claim": config["idle_hours"]["value"], "idle_hours_evidence_status": config["idle_hours"]["evidence_status"],
        "km_per_engine_hour": hours["km_per_engine_hour"], "idle_hour_percent": hours["idle_hour_percent"],
        "service_history_claim": config["service_history"]["value"], "service_history_evidence_status": config["service_history"]["evidence_status"],
        "accident_title_claim": config["accident_title"]["value"], "accident_title_evidence_status": config["accident_title"]["evidence_status"],
        "prior_use_claims": ";".join(config["prior_use_claims"]["value"]), "evidence_completeness": value["evidence_completeness"],
        "missing_investigation_fields": ";".join(value["missing_investigation_fields"]),
        "price_band_basis": market["cohort_basis"], "price_band_comparable_count": market["comparable_count"],
        "price_band_q1_cad": market["price_q1_cad"], "price_band_median_cad": market["price_median_cad"], "price_band_q3_cad": market["price_q3_cad"],
        "price_position": market["price_position"], "price_difference_from_median_cad": market["price_difference_from_median_cad"],
        "mileage_adjusted_projection_cad": regression_value["projected_asking_price_cad"],
        "projection_slope_cad_per_10000_km": regression_value["slope_cad_per_10000_km"], "projection_r_squared": regression_value["r_squared"],
        "projected_mileage_5y_min_km": projection["projected_mileage_min_km"], "projected_mileage_5y_max_km": projection["projected_mileage_max_km"],
        "computed_classification": value["computed_classification"], "computed_classification_reasons": ";".join(value["computed_classification_reasons"]),
        "owner_disposition": owner["owner_disposition"], "owner_note": owner["owner_note"], "owner_tags": ";".join(owner["owner_tags"]),
        "owner_classification_override": owner["classification_override"], "owner_override_reason": owner["override_reason"],
        "override_applied": str(owner["override_applied"]).lower(), "effective_classification": owner["effective_classification"],
        "seller_question_count": value["seller_question_count"], "seller_questions_ref": value["seller_questions_ref"],
        "raw_record_ref": value["raw_record_ref"], "source_adapter_record_ref": value["source_adapter_record_ref"],
    }


def year_groups(listings: Sequence[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, Any] = {}
    for year in sorted({value["year"] for value in listings if isinstance(value.get("year"), int)}):
        rows = [value for value in listings if value.get("year") == year]
        prices = [value["price_cad"] for value in rows if isinstance(value.get("price_cad"), int)]
        mileages = [value["mileage_km"] for value in rows if isinstance(value.get("mileage_km"), int)]
        groups[str(year)] = {"listing_claim_count": len(rows),
            "price_q1_cad": None if not prices else round(percentile(prices, .25) or 0),
            "price_median_cad": None if not prices else round(percentile(prices, .5) or 0),
            "price_q3_cad": None if not prices else round(percentile(prices, .75) or 0),
            "mileage_q1_km": None if not mileages else round(percentile(mileages, .25) or 0),
            "mileage_median_km": None if not mileages else round(percentile(mileages, .5) or 0),
            "mileage_q3_km": None if not mileages else round(percentile(mileages, .75) or 0)}
    return groups


def market_summary(listings: Sequence[dict[str, Any]], run_id: str, scope: str, sources: Sequence[str], override_digest: str) -> dict[str, Any]:
    coverage: dict[str, Any] = {}
    for field in ("trim", "cab_configuration", "box_configuration", "rear_wheel_configuration", "drivetrain", "engine_hours", "idle_hours", "service_history", "accident_title", "prior_use_claims"):
        count = sum(value["configuration_evidence"][field]["value"] not in (None, "", [], "unknown", "Unknown") for value in listings)
        coverage[field] = {"known_listing_count": count, "total_listing_count": len(listings),
                           "coverage_percent": round(count / len(listings) * 100, 2) if listings else 0.0}
    classifications: dict[str, int] = {}
    for listing in listings:
        key = str(listing["owner_annotation"]["effective_classification"])
        classifications[key] = classifications.get(key, 0) + 1
    return {"buyer_intelligence_schema_version": BUYER_SCHEMA_VERSION, "run_id": run_id, "generated_at_utc": utc_now(),
            "vehicle_key": "ford_f350", "scope": scope, "sources": list(sources), "listing_claim_count": len(listings),
            "source_listing_claim_counts": {source: sum(value["source"] == source for value in listings) for source in sources},
            "year_groups": year_groups(listings), "field_coverage": coverage,
            "effective_classification_counts": classifications, "owner_override_digest_sha256": override_digest,
            "owner_usage_projection": {"annual_km_min": OWNER_ANNUAL_KM_MIN, "annual_km_max": OWNER_ANNUAL_KM_MAX, "projection_years": PROJECTION_YEARS},
            "market_scope": "configured_query_accepted_listing_claims_not_complete_market",
            "price_band_contract": "observed_quartiles_not_appraisal",
            "projection_contract": "mileage_adjusted_asking_price_context_and_owner_mileage_scenario_not_future_value",
            "classification_contract": "explainable_no_rank_no_score_manual_override_preserves_computed_result",
            "limitations": ["source claims are not independently verified", "duplicate candidates remain separate listing claims",
                "missing engine, idle, service, history, and configuration evidence is not inferred",
                "asking-price bands do not establish sale price or fair value",
                "mileage-adjusted projections are descriptive regression context, not appraisal",
                "five-year mileage projection uses the owner's 5000-8000 km annual-use scenario"]}


def write_summary_markdown(path: Path, summary: dict[str, Any]) -> None:
    lines = ["# F-350 Buyer Intelligence", "", f"- Run ID: `{summary['run_id']}`", f"- Scope: `{summary['scope']}`",
             f"- Sources: {', '.join(summary['sources'])}", f"- Current accepted listing claims: {summary['listing_claim_count']}",
             f"- Market scope: `{summary['market_scope']}`", "", "## Evidence coverage", "",
             "| Field | Known | Total | Coverage |", "|---|---:|---:|---:|"]
    for field, value in summary["field_coverage"].items():
        lines.append(f"| {field} | {value['known_listing_count']} | {value['total_listing_count']} | {value['coverage_percent']}% |")
    lines.extend(["", "## Year price and mileage context", "",
                  "| Year | Listings | Price Q1 | Median | Price Q3 | Mileage Q1 | Median | Mileage Q3 |",
                  "|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for year, value in summary["year_groups"].items():
        lines.append(f"| {year} | {value['listing_claim_count']} | {value['price_q1_cad'] or '—'} | {value['price_median_cad'] or '—'} | {value['price_q3_cad'] or '—'} | {value['mileage_q1_km'] or '—'} | {value['mileage_median_km'] or '—'} | {value['mileage_q3_km'] or '—'} |")
    lines.extend(["", "## Interpretation limits", ""])
    lines.extend(f"- {value}" for value in summary["limitations"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build(root: Path, config_path: Path, run_id: str, sources: Sequence[str] | None = None,
          overrides_path: Path = Path("f350_owner_overrides.json")) -> dict[str, Any]:
    root = root.resolve()
    config_path = config_path if config_path.is_absolute() else root / config_path
    config = load_vehicle_config(config_path)
    if config.get("vehicle_key") != "ford_f350":
        raise ValueError("F-350 buyer intelligence requires config_f350")
    selected = tuple(sources or SUPPORTED_SOURCES)
    if not selected or any(source not in SUPPORTED_SOURCES for source in selected) or len(selected) != len(set(selected)):
        raise ValueError("Buyer intelligence source plan is invalid")
    scope = "full_sources" if set(selected) == set(SUPPORTED_SOURCES) else "single_source"
    override_file = overrides_path if overrides_path.is_absolute() else root / overrides_path
    overrides = load_owner_overrides(override_file)
    override_bytes = override_file.read_bytes() if override_file.exists() else json.dumps(overrides, sort_keys=True).encode("utf-8")
    bundles: list[dict[str, Any]] = []
    for source in selected:
        bundles.extend(load_source_bundles(root, config, source, run_id))
    market_rows = [_base(bundle, scope) for bundle in bundles]
    paths = artifact_paths(root, config)
    relative = {key: str(value.relative_to(root)) for key, value in paths.items()}
    listings: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    for bundle in bundles:
        listing, question_record = _listing(bundle, market_rows, overrides, relative, scope)
        listings.append(listing)
        questions.append(question_record)
    listings.sort(key=lambda value: (-int(value.get("year") or 0), int(value.get("price_cad") or 10**12), str(value.get("source")), str(value.get("canonical_listing_id"))))
    questions.sort(key=lambda value: (str(value.get("source")), str(value.get("canonical_listing_id"))))
    write_jsonl(paths["investigation_jsonl"], listings)
    write_jsonl(paths["seller_questions"], questions)
    paths["investigation_csv"].parent.mkdir(parents=True, exist_ok=True)
    with paths["investigation_csv"].open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(csv_row(value) for value in listings)
    summary = market_summary(listings, run_id, scope, selected, hashlib.sha256(override_bytes).hexdigest())
    summary["artifacts"] = relative
    write_json(paths["market_summary_json"], summary)
    write_summary_markdown(paths["market_summary_markdown"], summary)
    print(f"[ford_f350:buyer_intelligence] scope={scope} | listings={len(listings)} | sources={','.join(selected)}")
    return summary


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Build transparent F-350 buyer-investigation outputs")
    sub = root.add_subparsers(dest="action", required=True)
    command = sub.add_parser("build")
    command.add_argument("--config", default="config_f350.json")
    command.add_argument("--run-id", required=True)
    command.add_argument("--source", action="append", choices=SUPPORTED_SOURCES)
    command.add_argument("--overrides", default="f350_owner_overrides.json")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.action == "build":
        build(Path.cwd(), Path(args.config), args.run_id, args.source, Path(args.overrides))
        return 0
    raise AssertionError(args.action)


if __name__ == "__main__":
    raise SystemExit(main())
