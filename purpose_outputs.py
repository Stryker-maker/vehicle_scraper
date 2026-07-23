from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any, Iterable, Sequence

from canonical_evidence import read_jsonl, write_jsonl
from identity_lifecycle import IDENTITY_LIFECYCLE_SCHEMA_VERSION, load_current_identity_records
from phase1_common import load_json, source_status_path, status_is_current_success, utc_now, write_json
from vehicle_config import load_vehicle_config

PURPOSE_OUTPUT_SCHEMA_VERSION = 1
PURPOSE_INPUT_SCHEMA_VERSION = 1
SOURCE_STATUS_SCHEMA_VERSION = 8
SUPPORTED_SOURCES = ("autotrader", "kijiji")
SUPPORTED_PROFILES = ("owned_vehicle_value", "family_friend_purchase")
OWNED_VEHICLES = ("ram_3500", "subaru_forester")
FAMILY_VEHICLES = ("honda_odyssey", "kia_carnival")
FORBIDDEN_KEYS = {"rank", "score"}
UNKNOWN = {"", "unknown", "n/a", "na", "none", "null", "unavailable"}
MIN_DIRECTION_OBSERVATIONS = 3

OWNED_SUBJECT_FIELDS = (
    "year",
    "trim",
    "fuel",
    "engine",
    "drivetrain",
    "current_odometer_km",
    "odometer_context",
)
FAMILY_PREFERENCE_FIELDS = (
    "budget_max_cad",
    "min_year",
    "max_year",
    "max_mileage_km",
    "minimum_seating",
    "cargo_requirements",
    "max_distance_km",
    "accident_title_requirement",
    "service_history_requirement",
    "acceptable_seller_types",
    "availability_constraints",
)

OWNED_CSV_FIELDS = (
    "purpose_output_schema_version",
    "run_id",
    "scope",
    "vehicle_key",
    "analysis_profile",
    "source",
    "canonical_listing_id",
    "source_listing_id",
    "listing_url",
    "lifecycle_state",
    "year",
    "trim_claim",
    "fuel_claim",
    "engine_claim",
    "drivetrain_claim",
    "price_cad",
    "mileage_km",
    "distance_km",
    "price_observation_count",
    "previous_observation_price_cad",
    "change_from_previous_observation_cad",
    "change_from_first_observation_cad",
    "subject_comparability",
    "subject_comparability_reasons",
    "subject_profile_missing_fields",
    "market_role",
    "raw_record_ref",
    "source_adapter_record_ref",
)

FAMILY_CSV_FIELDS = (
    "purpose_output_schema_version",
    "run_id",
    "scope",
    "vehicle_key",
    "analysis_profile",
    "source",
    "canonical_listing_id",
    "source_listing_id",
    "listing_url",
    "lifecycle_state",
    "year",
    "price_cad",
    "mileage_km",
    "distance_km",
    "seller_type_claim",
    "seating_claim",
    "seating_evidence_status",
    "cargo_feature_claims",
    "service_history_claim",
    "service_history_evidence_status",
    "accident_title_claim",
    "accident_title_evidence_status",
    "missing_preference_fields",
    "preference_match_status",
    "preference_match_reasons",
    "candidate_classification",
    "candidate_classification_reasons",
    "seller_question_count",
    "seller_questions_ref",
    "raw_record_ref",
    "source_adapter_record_ref",
)


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
        _text(normalized.get("trim")),
        _text(normalized.get("engine")),
        _text(normalized.get("fuel")),
        _text(normalized.get("accident_claim")),
        _text(normalized.get("seller_type_claim")),
        *_flatten(raw_payload),
    ]
    return " | ".join(value for value in values if value)


def _field(value: Any, evidence_status: str) -> dict[str, Any]:
    return {"value": value, "evidence_status": evidence_status}


def _validate_input_field(name: str, value: Any, allowed_statuses: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"value", "evidence_status"}:
        raise ValueError(f"{name} must contain value and evidence_status")
    if value["evidence_status"] not in allowed_statuses:
        raise ValueError(f"{name} has unsupported evidence_status")
    return value


def load_purpose_inputs(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != PURPOSE_INPUT_SCHEMA_VERSION:
        raise ValueError("Purpose-input schema version mismatch")
    vehicles = value.get("vehicles")
    if not isinstance(vehicles, dict) or set(vehicles) != set(OWNED_VEHICLES + FAMILY_VEHICLES):
        raise ValueError("Purpose-input vehicle set mismatch")
    for vehicle_key, entry in vehicles.items():
        if not isinstance(entry, dict):
            raise ValueError(f"{vehicle_key}: purpose input must be an object")
        expected_profile = "owned_vehicle_value" if vehicle_key in OWNED_VEHICLES else "family_friend_purchase"
        if entry.get("analysis_profile") != expected_profile:
            raise ValueError(f"{vehicle_key}: analysis profile mismatch")
        if expected_profile == "owned_vehicle_value":
            if set(entry) != {"analysis_profile", "subject_profile", "sale_goal"}:
                raise ValueError(f"{vehicle_key}: unknown owned-value input field")
            subject = entry.get("subject_profile")
            if not isinstance(subject, dict) or set(subject) != set(OWNED_SUBJECT_FIELDS):
                raise ValueError(f"{vehicle_key}: subject profile field set mismatch")
            for field_name in OWNED_SUBJECT_FIELDS:
                _validate_input_field(
                    f"{vehicle_key}.{field_name}",
                    subject[field_name],
                    {"owner_reported_historical_unverified", "owner_input_required"},
                )
            if not _text(entry.get("sale_goal")):
                raise ValueError(f"{vehicle_key}: sale_goal is required")
        else:
            if set(entry) != {"analysis_profile", "preferences"}:
                raise ValueError(f"{vehicle_key}: unknown family input field")
            preferences = entry.get("preferences")
            if not isinstance(preferences, dict) or set(preferences) != set(FAMILY_PREFERENCE_FIELDS):
                raise ValueError(f"{vehicle_key}: preference field set mismatch")
            for field_name in FAMILY_PREFERENCE_FIELDS:
                _validate_input_field(
                    f"{vehicle_key}.{field_name}",
                    preferences[field_name],
                    {"friend_input_required", "friend_reported_unverified"},
                )
    return value


def artifact_paths(root: Path, config: dict[str, Any], profile: str) -> dict[str, Path]:
    base = root / "data" / str(config["vehicle_key"]) / "purpose_output"
    if profile == "owned_vehicle_value":
        directory = base / "value_monitor"
        return {
            "records_jsonl": directory / "comparables_latest.jsonl",
            "records_csv": directory / "comparables_latest.csv",
            "input_gaps": directory / "owner_input_gaps_latest.json",
            "summary_json": directory / "market_snapshot_latest.json",
            "summary_markdown": directory / "market_snapshot_latest.md",
        }
    if profile == "family_friend_purchase":
        directory = base / "family_candidate"
        return {
            "records_jsonl": directory / "candidate_review_latest.jsonl",
            "records_csv": directory / "candidate_review_latest.csv",
            "questions_jsonl": directory / "seller_questions_latest.jsonl",
            "summary_json": directory / "requirements_summary_latest.json",
            "summary_markdown": directory / "requirements_summary_latest.md",
        }
    raise ValueError(f"Unsupported purpose profile: {profile}")


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
        bundles.append(
            {
                "record": record,
                "identity": identity_by_id[canonical_id],
                "raw_payload": raw_by_index[index],
            }
        )
    return bundles


def percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def distribution(values: Iterable[int | float | None]) -> dict[str, Any]:
    valid = [float(value) for value in values if isinstance(value, (int, float)) and not isinstance(value, bool)]
    if not valid:
        return {"count": 0, "minimum": None, "q1": None, "median": None, "q3": None, "maximum": None}
    return {
        "count": len(valid),
        "minimum": round(min(valid)),
        "q1": round(percentile(valid, 0.25) or 0),
        "median": round(percentile(valid, 0.5) or 0),
        "q3": round(percentile(valid, 0.75) or 0),
        "maximum": round(max(valid)),
    }


def _profile_value(profile: dict[str, Any], field_name: str) -> Any:
    return profile[field_name]["value"]


def _missing_input_fields(fields: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for name, value in fields.items():
        raw = value.get("value") if isinstance(value, dict) else None
        if raw is None or raw == [] or raw == "":
            missing.append(name)
    return sorted(missing)


def _listing_drivetrain(text: str) -> str | None:
    if re.search(r"\b(?:4x4|4wd|four[-\s]*wheel\s*drive)\b", text, flags=re.IGNORECASE):
        return "4wd"
    if re.search(r"\b(?:2wd|rwd|rear[-\s]*wheel\s*drive)\b", text, flags=re.IGNORECASE):
        return "2wd"
    return None


def _service_history(text: str) -> dict[str, Any]:
    if re.search(r"\b(?:no|without)\s+(?:service|maintenance)\s+records?\b", text, flags=re.IGNORECASE):
        return _field("records_not_available_claim", "source_text_reported_unverified")
    if re.search(
        r"\b(?:full\s+service\s+history|service\s+records?\s+(?:available|included)|maintenance\s+records?\s+(?:available|included)|dealer[-\s]+maintained)\b",
        text,
        flags=re.IGNORECASE,
    ):
        return _field("records_available_claim", "source_text_reported_unverified")
    return _field(None, "unknown")


def _seating_claim(text: str) -> dict[str, Any]:
    match = re.search(r"\b([6-9])[-\s]*(?:passenger|passengers|seat|seater)\b", text, flags=re.IGNORECASE)
    if match:
        return _field(int(match.group(1)), "source_text_reported_unverified")
    return _field(None, "unknown")


def _cargo_claims(text: str) -> dict[str, Any]:
    claims: list[str] = []
    patterns = (
        ("fold_flat_seating_claim", r"\bfold[-\s]*flat\b"),
        ("removable_seating_claim", r"\bremovable\s+(?:seat|seats|seating)\b"),
        ("power_sliding_doors_claim", r"\bpower\s+sliding\s+doors?\b"),
        ("rear_entertainment_claim", r"\b(?:rear|dvd)\s+entertainment\b"),
        ("roof_rack_claim", r"\broof\s+rack\b"),
        ("cargo_space_claim", r"\bcargo\s+(?:space|area|capacity)\b"),
    )
    for label, pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            claims.append(label)
    return _field(sorted(set(claims)), "source_text_reported_unverified" if claims else "unknown")


def _accident_title(normalized: dict[str, Any], text: str) -> dict[str, Any]:
    normalized_claim = _text(normalized.get("accident_claim"))
    if normalized_claim:
        return _field(normalized_claim, "source_reported_unverified")
    match = re.search(r"\b(?:no\s+accidents?|accident|collision|rebuilt|salvage|structural\s+damage|clean\s+title)\b", text, flags=re.IGNORECASE)
    if match:
        return _field(match.group(0), "source_text_reported_unverified")
    return _field(None, "unknown")


def _base_record(bundle: dict[str, Any], profile: str, scope: str) -> dict[str, Any]:
    record = bundle["record"]
    identity = bundle["identity"]
    normalized = record.get("normalized", {})
    return {
        "purpose_output_schema_version": PURPOSE_OUTPUT_SCHEMA_VERSION,
        "run_id": record.get("run_id"),
        "scope": scope,
        "vehicle_key": record.get("vehicle_key"),
        "analysis_profile": profile,
        "source": record.get("source"),
        "canonical_listing_id": record.get("canonical_listing_id"),
        "source_listing_id": record.get("source_listing_id"),
        "listing_url": normalized.get("listing_url"),
        "lifecycle_state": identity.get("lifecycle_state"),
        "year": _int(normalized.get("year")),
        "price_cad": _int(normalized.get("price_cad")),
        "mileage_km": _int(normalized.get("mileage_km")),
        "distance_km": _float(normalized.get("distance_km")),
        "raw_record_ref": record.get("raw_record_ref"),
        "source_adapter_record_ref": record.get("source_adapter_record_ref"),
        "normalized": normalized,
        "identity": identity,
    }


def _string_match(subject: str, listing: str) -> bool:
    subject_tokens = [
        token
        for token in re.findall(r"[a-z0-9.]+", subject.casefold())
        if len(token) >= 3 or token.replace(".", "").isdigit()
    ]
    listing_text = listing.casefold()
    return bool(subject_tokens) and all(token in listing_text for token in subject_tokens[:2])


def owned_comparability(
    base: dict[str, Any],
    bundle: dict[str, Any],
    subject: dict[str, Any],
) -> tuple[str, list[str], list[str]]:
    missing_subject = _missing_input_fields(subject)
    normalized = base["normalized"]
    text = source_text(bundle["raw_payload"], normalized)
    listing_values = {
        "year": base["year"],
        "trim": _text(normalized.get("trim")),
        "fuel": _text(normalized.get("fuel")),
        "engine": " ".join(value for value in (_text(normalized.get("engine")), text) if value),
        "drivetrain": _listing_drivetrain(text),
    }
    matches: list[str] = []
    conflicts: list[str] = []
    unknown_listing: list[str] = []
    for field_name in ("year", "trim", "fuel", "engine", "drivetrain"):
        subject_value = _profile_value(subject, field_name)
        listing_value = listing_values[field_name]
        if subject_value in (None, "", []):
            continue
        if listing_value in (None, "", []):
            unknown_listing.append(field_name)
            continue
        if field_name == "year":
            matched = _int(subject_value) == _int(listing_value)
        elif field_name in {"trim", "engine"}:
            matched = _string_match(str(subject_value), str(listing_value))
        else:
            matched = str(subject_value).casefold() == str(listing_value).casefold()
        (matches if matched else conflicts).append(field_name)
    reasons = [
        *(f"subject_match:{name}" for name in matches),
        *(f"subject_conflict:{name}" for name in conflicts),
        *(f"listing_evidence_missing:{name}" for name in unknown_listing),
    ]
    if len(missing_subject) >= 4:
        return "subject_profile_incomplete", reasons + ["owner_profile_requires_input"], missing_subject
    if conflicts and "year" in conflicts:
        return "broad_market_context", reasons + ["model_year_differs_from_subject"], missing_subject
    if "year" in matches and len(matches) >= 3 and not conflicts:
        return "close_subject_comparable", reasons + ["multiple_subject_attributes_match"], missing_subject
    if "year" in matches or len(matches) >= 2:
        return "partial_subject_comparable", reasons + ["some_subject_attributes_match"], missing_subject
    if matches:
        return "broad_market_context", reasons + ["limited_subject_attribute_match"], missing_subject
    return "insufficient_configuration_evidence", reasons + ["no_supported_subject_match"], missing_subject


def _owned_record(bundle: dict[str, Any], subject: dict[str, Any], scope: str) -> dict[str, Any]:
    base = _base_record(bundle, "owned_vehicle_value", scope)
    normalized = base.pop("normalized")
    identity = base.pop("identity")
    text = source_text(bundle["raw_payload"], normalized)
    comparability, reasons, missing_subject = owned_comparability(
        {**base, "normalized": normalized}, bundle, subject
    )
    market_role = {
        "close_subject_comparable": "subject_context",
        "partial_subject_comparable": "subject_context",
        "broad_market_context": "broad_market_context",
        "subject_profile_incomplete": "broad_market_context",
        "insufficient_configuration_evidence": "evidence_gap",
    }[comparability]
    return {
        **base,
        "trim_claim": _text(normalized.get("trim")) or None,
        "fuel_claim": _text(normalized.get("fuel")) or None,
        "engine_claim": _text(normalized.get("engine")) or None,
        "drivetrain_claim": _listing_drivetrain(text),
        "price_observation_count": _int(identity.get("price_observation_count")) or 0,
        "previous_observation_price_cad": _int(identity.get("previous_observation_price_cad")),
        "change_from_previous_observation_cad": _int(identity.get("change_from_previous_observation_cad")),
        "change_from_first_observation_cad": _int(identity.get("change_from_first_observation_cad")),
        "subject_comparability": comparability,
        "subject_comparability_reasons": reasons,
        "subject_profile_missing_fields": missing_subject,
        "market_role": market_role,
        "interpretation_contract": "observed_asking_price_context_not_appraisal_not_sale_probability",
    }


def _direction(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    changes = [
        record["change_from_previous_observation_cad"]
        for record in records
        if isinstance(record.get("change_from_previous_observation_cad"), int)
    ]
    decreases = sum(value < 0 for value in changes)
    increases = sum(value > 0 for value in changes)
    unchanged = sum(value == 0 for value in changes)
    if len(changes) < MIN_DIRECTION_OBSERVATIONS:
        status = "insufficient_multi_run_history"
        median = None
    else:
        status = "observed_asking_price_change_context_available"
        median = round(statistics.median(changes))
    return {
        "status": status,
        "listings_with_previous_price_observation": len(changes),
        "asking_price_decrease_count": decreases,
        "asking_price_increase_count": increases,
        "asking_price_unchanged_count": unchanged,
        "median_change_from_previous_observation_cad": median,
        "meaning": "listing_asking_price_changes_only_not_market_value_trend_or_sale_evidence",
    }


def _owned_summary(
    config: dict[str, Any],
    run_id: str,
    sources: Sequence[str],
    scope: str,
    records: Sequence[dict[str, Any]],
    input_entry: dict[str, Any],
    paths: dict[str, Path],
    root: Path,
) -> dict[str, Any]:
    source_counts = {source: sum(record["source"] == source for record in records) for source in sources}
    year_counts: dict[str, int] = {}
    comparability_counts: dict[str, int] = {}
    for record in records:
        year = str(record["year"] if record["year"] is not None else "unknown")
        year_counts[year] = year_counts.get(year, 0) + 1
        label = record["subject_comparability"]
        comparability_counts[label] = comparability_counts.get(label, 0) + 1
    subject_context = [
        record
        for record in records
        if record["subject_comparability"] in {"close_subject_comparable", "partial_subject_comparable"}
    ]
    cohort = subject_context if len(subject_context) >= 3 else list(records)
    cohort_basis = (
        "close_or_partial_subject_comparables"
        if len(subject_context) >= 3
        else "all_configured_query_accepted_listings"
    )
    price_stats = distribution(record["price_cad"] for record in cohort)
    odometer = _profile_value(input_entry["subject_profile"], "current_odometer_km")
    missing_inputs = _missing_input_fields(input_entry["subject_profile"])
    if odometer is None:
        personalized_status = "unavailable_current_odometer_required"
    elif len(subject_context) < 3:
        personalized_status = "insufficient_subject_comparables"
    else:
        personalized_status = "observed_asking_context_available_not_valuation"
    return {
        "purpose_output_schema_version": PURPOSE_OUTPUT_SCHEMA_VERSION,
        "purpose_input_schema_version": PURPOSE_INPUT_SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at_utc": utc_now(),
        "scope": scope,
        "vehicle_key": config["vehicle_key"],
        "analysis_profile": "owned_vehicle_value",
        "sources": list(sources),
        "record_count": len(records),
        "source_record_counts": source_counts,
        "year_counts": dict(sorted(year_counts.items())),
        "subject_comparability_counts": dict(sorted(comparability_counts.items())),
        "subject_profile": input_entry["subject_profile"],
        "subject_profile_missing_fields": missing_inputs,
        "sale_goal": input_entry["sale_goal"],
        "subject_market_context_status": personalized_status,
        "cohort_basis": cohort_basis,
        "cohort_count": len(cohort),
        "asking_price_distribution_cad": price_stats,
        "mileage_distribution_km": distribution(record["mileage_km"] for record in cohort),
        "competitive_asking_context": {
            "lower_observed_asking_bound_cad": price_stats["q1"],
            "upper_observed_asking_bound_cad": price_stats["median"],
            "meaning": "lower_observed_asking_band_not_verified_faster_sale_range_or_sale_probability",
        },
        "multi_run_direction": _direction(records),
        "market_scope": "configured_query_accepted_listing_claims_not_complete_market",
        "interpretation_contract": "asking_price_context_not_appraisal_not_transaction_price_not_sale_probability",
        "artifacts": {name: str(path.relative_to(root)) for name, path in paths.items()},
    }


def _family_evidence(bundle: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    normalized = base["normalized"]
    text = source_text(bundle["raw_payload"], normalized)
    return {
        "seating": _seating_claim(text),
        "cargo_features": _cargo_claims(text),
        "service_history": _service_history(text),
        "accident_title": _accident_title(normalized, text),
    }


def evaluate_preferences(
    base: dict[str, Any],
    evidence: dict[str, Any],
    preferences: dict[str, Any],
) -> tuple[str, list[str], list[str]]:
    missing_preferences = _missing_input_fields(preferences)
    reasons: list[str] = []
    mismatches: list[str] = []
    unknown_listing: list[str] = []

    def numeric_check(field_name: str, listing_value: int | float | None, relation: str) -> None:
        preferred = _profile_value(preferences, field_name)
        if preferred is None:
            return
        if listing_value is None:
            unknown_listing.append(field_name)
            return
        if relation == "max" and listing_value > preferred:
            mismatches.append(field_name)
        elif relation == "min" and listing_value < preferred:
            mismatches.append(field_name)
        else:
            reasons.append(f"preference_match:{field_name}")

    numeric_check("budget_max_cad", base["price_cad"], "max")
    numeric_check("min_year", base["year"], "min")
    numeric_check("max_year", base["year"], "max")
    numeric_check("max_mileage_km", base["mileage_km"], "max")
    numeric_check("max_distance_km", base["distance_km"], "max")
    numeric_check("minimum_seating", evidence["seating"]["value"], "min")

    seller_types = _profile_value(preferences, "acceptable_seller_types")
    seller_type = _text(base["normalized"].get("seller_type_claim"))
    if seller_types:
        if not seller_type:
            unknown_listing.append("acceptable_seller_types")
        elif seller_type.casefold() not in {str(value).casefold() for value in seller_types}:
            mismatches.append("acceptable_seller_types")
        else:
            reasons.append("preference_match:acceptable_seller_types")

    for field_name, evidence_key in (
        ("accident_title_requirement", "accident_title"),
        ("service_history_requirement", "service_history"),
    ):
        required = _profile_value(preferences, field_name)
        if required is not None:
            if evidence[evidence_key]["value"] is None:
                unknown_listing.append(field_name)
            else:
                reasons.append(f"source_claim_present_unverified:{field_name}")

    cargo_requirements = _profile_value(preferences, "cargo_requirements")
    if cargo_requirements:
        claims = set(evidence["cargo_features"]["value"] or [])
        required = {str(value) for value in cargo_requirements}
        if not claims:
            unknown_listing.append("cargo_requirements")
        elif not required.issubset(claims):
            mismatches.append("cargo_requirements")
        else:
            reasons.append("preference_match:cargo_requirements")

    availability = _profile_value(preferences, "availability_constraints")
    if availability:
        unknown_listing.append("availability_constraints")

    reasons.extend(f"preference_mismatch:{name}" for name in sorted(set(mismatches)))
    reasons.extend(f"listing_evidence_missing:{name}" for name in sorted(set(unknown_listing)))
    if missing_preferences:
        status = "preferences_incomplete"
    elif mismatches:
        status = "outside_stated_preferences"
    elif unknown_listing:
        status = "preference_match_unresolved_by_missing_listing_evidence"
    else:
        status = "within_stated_preferences_based_on_unverified_listing_claims"
    return status, reasons, missing_preferences


def family_seller_questions(base: dict[str, Any], evidence: dict[str, Any]) -> list[dict[str, str]]:
    questions: list[dict[str, str]] = []

    def add(category: str, priority: str, question: str, reason: str) -> None:
        questions.append({"category": category, "priority": priority, "question": question, "reason": reason})

    add(
        "identity",
        "high",
        "What is the full VIN, and can you provide clear photos of the VIN plate and current registration?",
        "independent_identity_verification_required",
    )
    if evidence["accident_title"]["value"] is None:
        add(
            "history",
            "high",
            "Can you provide a current vehicle-history report and confirm any accidents, insurance claims, rebuilt/salvage status, or structural repairs?",
            "accident_title_evidence_missing",
        )
    else:
        add(
            "history",
            "high",
            "Please provide documents supporting the listing's accident and title claims.",
            "source_accident_title_claim_unverified",
        )
    if evidence["service_history"]["value"] is None:
        add(
            "history",
            "high",
            "What maintenance and repair records are available, and what major work is currently due?",
            "service_history_evidence_missing",
        )
    if evidence["seating"]["value"] is None:
        add(
            "configuration",
            "high",
            "How many usable seating positions are installed, and can you provide photos of every seating row?",
            "seating_capacity_missing",
        )
    add(
        "family_use",
        "medium",
        "Do all sliding doors, seat-folding/removal mechanisms, climate controls, cameras, sensors, and child-seat anchors operate correctly?",
        "family_use_feature_verification_required",
    )
    add(
        "availability",
        "high",
        "Is the vehicle currently available, and can it be held long enough for an independent inspection and history review?",
        "availability_not_proven_by_listing",
    )
    add(
        "inspection",
        "high",
        "Can the vehicle undergo an independent pre-purchase inspection, diagnostic scan, and road test before any deposit or purchase?",
        "independent_condition_verification_required",
    )
    return questions


def _family_record(
    bundle: dict[str, Any],
    preferences: dict[str, Any],
    scope: str,
    questions_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    base = _base_record(bundle, "family_friend_purchase", scope)
    normalized = base["normalized"]
    evidence = _family_evidence(bundle, base)
    status, match_reasons, missing_preferences = evaluate_preferences(base, evidence, preferences)
    evidence_gaps = [name for name, claim in evidence.items() if claim["value"] in (None, [], "")]
    if status == "preferences_incomplete":
        classification = "candidate_pending_requirements"
        classification_reasons = [
            "friend_preferences_incomplete",
            *(f"missing_preference:{name}" for name in missing_preferences),
        ]
    elif status == "outside_stated_preferences":
        classification = "candidate_outside_stated_preferences"
        classification_reasons = [
            reason for reason in match_reasons if reason.startswith("preference_mismatch:")
        ]
    elif evidence_gaps or status == "preference_match_unresolved_by_missing_listing_evidence":
        classification = "candidate_with_evidence_gaps"
        classification_reasons = [
            "listing_evidence_requires_confirmation",
            *(f"missing_listing_evidence:{name}" for name in evidence_gaps),
        ]
    else:
        classification = "candidate_for_manual_review"
        classification_reasons = [
            "stated_preferences_match_unverified_listing_claims",
            "manual_inspection_still_required",
        ]
    questions = family_seller_questions(base, evidence)
    question_record = {
        "purpose_output_schema_version": PURPOSE_OUTPUT_SCHEMA_VERSION,
        "run_id": base["run_id"],
        "vehicle_key": base["vehicle_key"],
        "analysis_profile": "family_friend_purchase",
        "source": base["source"],
        "canonical_listing_id": base["canonical_listing_id"],
        "listing_url": base["listing_url"],
        "questions": questions,
    }
    record = {
        **{key: value for key, value in base.items() if key not in {"normalized", "identity"}},
        "seller_type_claim": _text(normalized.get("seller_type_claim")) or None,
        "seating_claim": evidence["seating"]["value"],
        "seating_evidence_status": evidence["seating"]["evidence_status"],
        "cargo_feature_claims": evidence["cargo_features"]["value"],
        "cargo_feature_evidence_status": evidence["cargo_features"]["evidence_status"],
        "service_history_claim": evidence["service_history"]["value"],
        "service_history_evidence_status": evidence["service_history"]["evidence_status"],
        "accident_title_claim": evidence["accident_title"]["value"],
        "accident_title_evidence_status": evidence["accident_title"]["evidence_status"],
        "missing_preference_fields": missing_preferences,
        "preference_match_status": status,
        "preference_match_reasons": match_reasons,
        "candidate_classification": classification,
        "candidate_classification_reasons": classification_reasons,
        "seller_question_count": len(questions),
        "seller_questions_ref": f"{questions_path.as_posix()}#canonical_listing_id={base['canonical_listing_id']}",
        "decision_contract": "purpose_specific_candidate_classification_not_rank_not_score",
    }
    return record, question_record


def _family_summary(
    config: dict[str, Any],
    run_id: str,
    sources: Sequence[str],
    scope: str,
    records: Sequence[dict[str, Any]],
    preferences: dict[str, Any],
    paths: dict[str, Path],
    root: Path,
) -> dict[str, Any]:
    source_counts = {source: sum(record["source"] == source for record in records) for source in sources}
    classification_counts: dict[str, int] = {}
    for record in records:
        label = record["candidate_classification"]
        classification_counts[label] = classification_counts.get(label, 0) + 1
    missing_preferences = _missing_input_fields(preferences)
    preference_questions = [
        {
            "field": field_name,
            "question": {
                "budget_max_cad": "What is the maximum all-in purchase budget?",
                "min_year": "What is the oldest acceptable model year?",
                "max_year": "What is the newest acceptable model year?",
                "max_mileage_km": "What is the maximum acceptable odometer reading?",
                "minimum_seating": "How many usable seating positions are required?",
                "cargo_requirements": "Which cargo or seat-folding features are required?",
                "max_distance_km": "How far is the buyer willing to travel?",
                "accident_title_requirement": "What accident and title-history conditions are acceptable?",
                "service_history_requirement": "How much service-history evidence is required?",
                "acceptable_seller_types": "Are dealer, private, or both seller types acceptable?",
                "availability_constraints": "What timing, deposit, inspection, or availability constraints apply?",
            }[field_name],
        }
        for field_name in missing_preferences
    ]
    return {
        "purpose_output_schema_version": PURPOSE_OUTPUT_SCHEMA_VERSION,
        "purpose_input_schema_version": PURPOSE_INPUT_SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at_utc": utc_now(),
        "scope": scope,
        "vehicle_key": config["vehicle_key"],
        "analysis_profile": "family_friend_purchase",
        "sources": list(sources),
        "record_count": len(records),
        "source_record_counts": source_counts,
        "candidate_classification_counts": dict(sorted(classification_counts.items())),
        "preferences": preferences,
        "missing_preference_fields": missing_preferences,
        "requirements_status": "friend_input_required" if missing_preferences else "requirements_recorded_unverified",
        "questions_for_friend": preference_questions,
        "asking_price_distribution_cad": distribution(record["price_cad"] for record in records),
        "mileage_distribution_km": distribution(record["mileage_km"] for record in records),
        "market_scope": "configured_query_accepted_listing_claims_not_complete_market",
        "interpretation_contract": "candidate_review_not_rank_not_recommendation_not_condition_verification",
        "artifacts": {name: str(path.relative_to(root)) for name, path in paths.items()},
    }


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return "" if value is None else value


def _write_csv(path: Path, fieldnames: Sequence[str], records: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({field: _csv_value(record.get(field)) for field in fieldnames})


def _owned_markdown(summary: dict[str, Any]) -> str:
    price = summary["asking_price_distribution_cad"]
    direction = summary["multi_run_direction"]
    return "\n".join(
        [
            f"# {summary['vehicle_key']} Owned-Vehicle Value Monitor",
            "",
            f"- Run ID: `{summary['run_id']}`",
            f"- Listing claims: {summary['record_count']}",
            f"- Subject context: `{summary['subject_market_context_status']}`",
            f"- Cohort basis: `{summary['cohort_basis']}` ({summary['cohort_count']} records)",
            f"- Asking-price Q1 / median / Q3: {price['q1']} / {price['median']} / {price['q3']} CAD",
            f"- Multi-run direction: `{direction['status']}`",
            "",
            "Observed asking-price context only. This is not an appraisal, transaction-price estimate, or verified faster-sale range.",
            "",
        ]
    )


def _family_markdown(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {summary['vehicle_key']} Family-Vehicle Candidate Review",
            "",
            f"- Run ID: `{summary['run_id']}`",
            f"- Listing claims: {summary['record_count']}",
            f"- Requirements status: `{summary['requirements_status']}`",
            f"- Missing preference fields: {', '.join(summary['missing_preference_fields']) or 'none'}",
            f"- Candidate classifications: `{json.dumps(summary['candidate_classification_counts'], sort_keys=True)}`",
            "",
            "Candidate review only. No rank, recommendation, condition verification, or sale-value authority is created.",
            "",
        ]
    )


def build(
    *,
    root: Path,
    config_path: Path,
    run_id: str,
    sources: Sequence[str],
    inputs_path: Path = Path("purpose_inputs.json"),
) -> dict[str, Any]:
    root = root.resolve()
    config_path = config_path if config_path.is_absolute() else root / config_path
    inputs_path = inputs_path if inputs_path.is_absolute() else root / inputs_path
    config = load_vehicle_config(config_path)
    vehicle_key = str(config["vehicle_key"])
    purpose_inputs = load_purpose_inputs(inputs_path)
    if vehicle_key not in purpose_inputs["vehicles"]:
        raise ValueError(f"{vehicle_key}: no governed purpose input")
    entry = purpose_inputs["vehicles"][vehicle_key]
    profile = str(entry["analysis_profile"])
    if profile not in SUPPORTED_PROFILES:
        raise ValueError(f"{vehicle_key}: unsupported analysis profile")
    if len(sources) != len(set(sources)) or not sources or any(source not in SUPPORTED_SOURCES for source in sources):
        raise ValueError("Source scope must contain unique supported sources")
    scope = "single_source" if len(sources) == 1 else "combined_sources"
    bundles: list[dict[str, Any]] = []
    for source in sources:
        bundles.extend(load_source_bundles(root, config, source, run_id))
    paths = artifact_paths(root, config, profile)

    if profile == "owned_vehicle_value":
        subject = entry["subject_profile"]
        records = [_owned_record(bundle, subject, scope) for bundle in bundles]
        summary = _owned_summary(config, run_id, sources, scope, records, entry, paths, root)
        input_gaps = {
            "purpose_output_schema_version": PURPOSE_OUTPUT_SCHEMA_VERSION,
            "purpose_input_schema_version": PURPOSE_INPUT_SCHEMA_VERSION,
            "run_id": run_id,
            "vehicle_key": vehicle_key,
            "analysis_profile": profile,
            "subject_profile_missing_fields": summary["subject_profile_missing_fields"],
            "required_owner_actions": [
                {"field": field_name, "action": f"Record current owner input for {field_name}."}
                for field_name in summary["subject_profile_missing_fields"]
            ],
            "meaning": "missing_owner_inputs_limit_personalized_subject_context",
        }
        write_jsonl(paths["records_jsonl"], records)
        _write_csv(paths["records_csv"], OWNED_CSV_FIELDS, records)
        write_json(paths["input_gaps"], input_gaps)
        write_json(paths["summary_json"], summary)
        paths["summary_markdown"].parent.mkdir(parents=True, exist_ok=True)
        paths["summary_markdown"].write_text(_owned_markdown(summary), encoding="utf-8")
    else:
        preferences = entry["preferences"]
        record_pairs = [
            _family_record(
                bundle,
                preferences,
                scope,
                paths["questions_jsonl"].relative_to(root),
            )
            for bundle in bundles
        ]
        records = [pair[0] for pair in record_pairs]
        questions = [pair[1] for pair in record_pairs]
        summary = _family_summary(config, run_id, sources, scope, records, preferences, paths, root)
        write_jsonl(paths["records_jsonl"], records)
        _write_csv(paths["records_csv"], FAMILY_CSV_FIELDS, records)
        write_jsonl(paths["questions_jsonl"], questions)
        write_json(paths["summary_json"], summary)
        paths["summary_markdown"].parent.mkdir(parents=True, exist_ok=True)
        paths["summary_markdown"].write_text(_family_markdown(summary), encoding="utf-8")
    return summary


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Build governed secondary-purpose vehicle outputs")
    sub = result.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--config", required=True)
    build_parser.add_argument("--run-id", required=True)
    build_parser.add_argument("--source", action="append", choices=SUPPORTED_SOURCES, required=True)
    build_parser.add_argument("--inputs", default="purpose_inputs.json")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "build":
        summary = build(
            root=Path.cwd(),
            config_path=Path(args.config),
            run_id=args.run_id,
            sources=args.source,
            inputs_path=Path(args.inputs),
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
