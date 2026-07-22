from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from phase1_common import SOURCES, row_quality_warnings, safe_int, utc_now

EVIDENCE_SCHEMA_VERSION = 1
UNKNOWN_TEXT = {"", "unknown", "n/a", "na", "none", "null", "not available", "unavailable"}


def _stable_id(prefix: str, *parts: object) -> str:
    payload = "\x1f".join("" if part is None else str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return None if cleaned.lower() in UNKNOWN_TEXT else cleaned


def _integer(value: Any, *, unknown_values: set[int] | None = None) -> int | None:
    parsed = safe_int(value)
    if parsed is None or (unknown_values and parsed in unknown_values):
        return None
    return parsed


def _number(value: Any) -> float | None:
    text = _text(value)
    if text is None:
        return None
    try:
        cleaned = "".join(character for character in text if character.isdigit() or character in ".-")
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _evidence(
    raw_value: Any, normalized_value: Any, *, status: str, source_field: str,
) -> dict[str, Any]:
    return {
        "source_field": source_field,
        "raw_value": raw_value,
        "normalized_value": normalized_value,
        "evidence_status": status,
    }


def canonical_artifact_paths(
    root: Path, config: dict[str, Any], source: str,
) -> dict[str, Path]:
    if source not in SOURCES:
        raise ValueError(f"Unsupported source: {source}")
    base = root / "data" / str(config["vehicle_key"]) / "evidence" / source
    return {
        "raw": base / "raw_latest.jsonl",
        "normalized": base / "normalized_latest.jsonl",
        "accepted": base / "accepted_latest.jsonl",
        "rejected": base / "rejected_latest.jsonl",
        "parse_failures": base / "parse_failures_latest.jsonl",
        "reconciliation": base / "reconciliation_latest.json",
    }


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            json.dump(record, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
    temporary.replace(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} is not a JSON object")
            records.append(value)
    return records


def _normalized_record(
    *, row: dict[str, Any], config: dict[str, Any], source: str, run_id: str,
    source_record_index: int, raw_ref: str, normalized_ref: str,
) -> dict[str, Any]:
    vehicle_key = str(config["vehicle_key"])
    raw_listing_id = row.get("listing_id")
    source_listing_id = _text(raw_listing_id)
    listing_url = _text(row.get("url"))
    identity_basis = source_listing_id or listing_url or f"row-{source_record_index}"
    canonical_listing_id = _stable_id(
        "listing", vehicle_key, source, identity_basis
    )
    observation_id = _stable_id(
        "observation", canonical_listing_id, run_id, source_record_index
    )

    year = _integer(row.get("year"))
    price_cad = _integer(row.get("price"))
    mileage_km = _integer(row.get("mileage"), unknown_values={999999})
    distance_km = None if source == "kijiji" else _number(row.get("distance_km"))
    raw_location = _text(row.get("location"))
    location = None if source == "kijiji" else raw_location
    raw_dealer_address = _text(row.get("dealer_address"))
    dealer_address = None if source == "kijiji" else raw_dealer_address

    normalized = {
        "year": year,
        "make": _text(row.get("make")),
        "model": _text(row.get("model")),
        "trim": _text(row.get("trim")),
        "trim_tier": _integer(row.get("trim_tier")),
        "price_cad": price_cad,
        "mileage_km": mileage_km,
        "engine": _text(row.get("engine")),
        "fuel": _text(row.get("fuel")),
        "accident_claim": _text(row.get("accident_flag")),
        "dealer": _text(row.get("dealer")),
        "seller_type_claim": _text(row.get("seller_type")),
        "dealer_address": dealer_address,
        "location": location,
        "distance_km": distance_km,
        "distance_method": (
            "disabled_unverified_location"
            if source == "kijiji"
            else _text(row.get("distance_method"))
        ),
        "source_listing_id": source_listing_id,
        "url_region_hint": _text(row.get("url_region_hint")),
        "url_region_status": _text(row.get("url_region_status")),
        "listing_url": listing_url,
        "source_name": _text(row.get("source")) or source,
        "observation_count": _integer(row.get("weeks_tracked")),
        "first_observed_price_cad": _integer(row.get("price_first_seen")),
        "previous_observation_price_cad": _integer(row.get("price_last_week")),
        "change_from_previous_observation_cad": _integer(row.get("price_change_week")),
        "change_from_first_observation_cad": _integer(row.get("price_change_total")),
        "source_price_history_text": _text(row.get("price_history")),
        "legacy_trend_text": _text(row.get("trend")),
        "days_on_market_claim": _text(row.get("days_on_market")),
    }

    location_status = (
        "quarantined_unverified_search_origin"
        if source == "kijiji"
        else "source_reported_not_independently_verified"
    )
    distance_status = (
        "disabled_due_to_unverified_location"
        if source == "kijiji"
        else "legacy_method_not_yet_disambiguated"
    )
    fields = {
        "year": _evidence(row.get("year"), year, status="source_reported_unverified" if year is not None else "unknown", source_field="year"),
        "make": _evidence(row.get("make"), normalized["make"], status="source_reported_or_configured_unverified" if normalized["make"] is not None else "unknown", source_field="make"),
        "model": _evidence(row.get("model"), normalized["model"], status="source_reported_or_configured_unverified" if normalized["model"] is not None else "unknown", source_field="model"),
        "trim": _evidence(row.get("trim"), normalized["trim"], status="source_reported_unverified" if normalized["trim"] is not None else "unknown", source_field="trim"),
        "price_cad": _evidence(row.get("price"), price_cad, status="source_reported_unverified" if price_cad is not None else "unknown", source_field="price"),
        "mileage_km": _evidence(row.get("mileage"), mileage_km, status="source_reported_unverified" if mileage_km is not None else "unknown", source_field="mileage"),
        "engine": _evidence(row.get("engine"), normalized["engine"], status="source_reported_unverified" if normalized["engine"] is not None else "unknown", source_field="engine"),
        "fuel": _evidence(row.get("fuel"), normalized["fuel"], status="source_reported_or_inferred_unverified" if normalized["fuel"] is not None else "unknown", source_field="fuel"),
        "accident_claim": _evidence(row.get("accident_flag"), normalized["accident_claim"], status="source_text_claim_unverified" if normalized["accident_claim"] is not None else "unknown", source_field="accident_flag"),
        "dealer": _evidence(row.get("dealer"), normalized["dealer"], status="source_reported_unverified" if normalized["dealer"] is not None else "unknown", source_field="dealer"),
        "seller_type_claim": _evidence(row.get("seller_type"), normalized["seller_type_claim"], status="source_reported_or_inferred_unverified" if normalized["seller_type_claim"] is not None else "unknown", source_field="seller_type"),
        "dealer_address": _evidence(row.get("dealer_address"), dealer_address, status=location_status if raw_dealer_address is not None else "unknown", source_field="dealer_address"),
        "location": _evidence(row.get("location"), location, status=location_status if raw_location is not None else "unknown", source_field="location"),
        "distance_km": _evidence(row.get("distance_km"), distance_km, status=distance_status, source_field="distance_km"),
        "distance_method": _evidence(row.get("distance_method"), normalized["distance_method"], status=distance_status, source_field="distance_method"),
        "source_listing_id": _evidence(raw_listing_id, source_listing_id, status="source_identifier_claim_not_vin" if source_listing_id is not None else "unknown", source_field="listing_id"),
        "url_region_hint": _evidence(row.get("url_region_hint"), normalized["url_region_hint"], status="unverified_url_evidence" if normalized["url_region_hint"] is not None else "unavailable", source_field="url_region_hint"),
        "listing_url": _evidence(row.get("url"), listing_url, status="source_reported_unverified" if listing_url is not None else "unknown", source_field="url"),
    }

    rejection_reasons: list[str] = []
    if source_listing_id is None:
        rejection_reasons.append("missing_source_listing_id")
    if listing_url is None:
        rejection_reasons.append("missing_listing_url")

    warnings = row_quality_warnings(
        {str(key): "" if value is None else str(value) for key, value in row.items()},
        source,
    )
    return {
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "record_stage": "rejected" if rejection_reasons else "accepted",
        "vehicle_key": vehicle_key,
        "source": source,
        "run_id": run_id,
        "source_record_index": source_record_index,
        "canonical_listing_id": canonical_listing_id,
        "observation_id": observation_id,
        "source_listing_id": source_listing_id,
        "source_listing_id_status": "source_identifier_claim_not_vin" if source_listing_id else "unknown",
        "source_claim_status": "unverified_source_claims",
        "raw_record_ref": raw_ref,
        "normalized_record_ref": normalized_ref,
        "normalized": normalized,
        "field_evidence": fields,
        "quality_warnings": warnings,
        "rejection_reasons": rejection_reasons,
    }


def build_canonical_evidence(
    *, root: Path, config: dict[str, Any], source: str, csv_path: Path,
    run_id: str, completed_at_utc: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    csv_path = csv_path if csv_path.is_absolute() else root / csv_path
    paths = canonical_artifact_paths(root, config, source)
    relative = {name: str(path.relative_to(root)) for name, path in paths.items()}
    raw_records: list[dict[str, Any]] = []
    normalized_records: list[dict[str, Any]] = []
    accepted_records: list[dict[str, Any]] = []
    rejected_records: list[dict[str, Any]] = []
    parse_failures: list[dict[str, Any]] = []
    completed_at_utc = completed_at_utc or utc_now()

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        try:
            for index, row in enumerate(reader):
                raw_values = {
                    str(key): value for key, value in row.items() if key is not None
                }
                raw_record = {
                    "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
                    "record_stage": "raw",
                    "vehicle_key": str(config["vehicle_key"]),
                    "source": source,
                    "run_id": run_id,
                    "source_record_index": index,
                    "source_row_number": index + 2,
                    "observed_at_utc": completed_at_utc,
                    "raw_values": raw_values,
                }
                raw_records.append(raw_record)
                raw_ref = f"{relative['raw']}#record={index}"
                normalized_ref = f"{relative['normalized']}#source_record_index={index}"
                malformed = None in row or any(isinstance(value, list) for value in row.values())
                if malformed:
                    parse_failures.append({
                        **raw_record,
                        "record_stage": "parse_failure",
                        "parse_failure_reasons": ["malformed_column_count"],
                        "raw_record_ref": raw_ref,
                    })
                    continue
                try:
                    record = _normalized_record(
                        row=raw_values, config=config, source=source, run_id=run_id,
                        source_record_index=index, raw_ref=raw_ref,
                        normalized_ref=normalized_ref,
                    )
                except Exception as exc:
                    parse_failures.append({
                        **raw_record,
                        "record_stage": "parse_failure",
                        "parse_failure_reasons": [f"normalization_error:{type(exc).__name__}"],
                        "error_message": str(exc),
                        "raw_record_ref": raw_ref,
                    })
                    continue
                normalized_records.append({**record, "record_stage": "normalized"})
                if record["rejection_reasons"]:
                    rejected_records.append(record)
                else:
                    accepted_records.append(record)
        except csv.Error as exc:
            index = len(raw_records)
            failure = {
                "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
                "record_stage": "parse_failure",
                "vehicle_key": str(config["vehicle_key"]),
                "source": source,
                "run_id": run_id,
                "source_record_index": index,
                "source_row_number": getattr(reader, "line_num", None),
                "observed_at_utc": completed_at_utc,
                "raw_values": {},
                "parse_failure_reasons": ["csv_reader_error"],
                "error_message": str(exc),
                "raw_record_ref": None,
            }
            parse_failures.append(failure)

    fetched_records = len(raw_records) + (
        1 if parse_failures and parse_failures[-1].get("parse_failure_reasons") == ["csv_reader_error"] else 0
    )
    reconciled = fetched_records == (
        len(accepted_records) + len(rejected_records) + len(parse_failures)
    )
    reconciliation = {
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "vehicle_key": str(config["vehicle_key"]),
        "source": source,
        "run_id": run_id,
        "generated_at_utc": utc_now(),
        "fetched_record_scope": "legacy_collector_emitted_csv_rows",
        "source_fetch_completeness": "not_proven_by_legacy_collector",
        "fetched_records": fetched_records,
        "normalized_records": len(normalized_records),
        "accepted_records": len(accepted_records),
        "rejected_records": len(rejected_records),
        "parse_failures": len(parse_failures),
        "reconciled": reconciled,
        "reconciliation_equation": "fetched_records = accepted_records + rejected_records + parse_failures",
        "artifacts": relative,
    }

    write_jsonl(paths["raw"], raw_records)
    write_jsonl(paths["normalized"], normalized_records)
    write_jsonl(paths["accepted"], accepted_records)
    write_jsonl(paths["rejected"], rejected_records)
    write_jsonl(paths["parse_failures"], parse_failures)
    paths["reconciliation"].parent.mkdir(parents=True, exist_ok=True)
    temporary = paths["reconciliation"].with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(reconciliation, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(paths["reconciliation"])
    return reconciliation
