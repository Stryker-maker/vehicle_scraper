from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SOURCES = ("autotrader", "kijiji")
DEFAULT_TIMEOUT_SECONDS = 75 * 60
UNBOUNDED_MAX_RESULTS = 10_000_000
REQUIRED_COLUMNS = {
    "listing_id", "url", "source", "price", "mileage", "location", "distance_km"
}
SOURCE_FIELDS = [
    "year", "make", "model", "trim", "trim_tier", "price", "price_history",
    "trend", "weeks_tracked", "price_first_seen", "price_last_week",
    "price_change_week", "price_change_total", "mileage", "engine", "fuel",
    "accident_flag", "days_on_market", "dealer", "seller_type",
    "dealer_address", "location", "distance_km", "distance_method",
    "listing_id", "url_region_hint", "url_region_status", "url", "source",
]
MANUAL_REVIEW_FIELDS = [
    "evidence_schema_version", "vehicle_key", "source", "canonical_listing_id", "observation_id",
    "source_listing_id", "source_listing_id_status", "source_claim_status",
    "raw_record_ref", "normalized_record_ref",
    "ranking_status", "review_status", "collection_status", "data_quality_status",
    "quality_warnings", "source_run_status", "source_completed_at_utc",
    "year", "year_evidence_status", "make", "make_evidence_status",
    "model", "model_evidence_status", "trim", "trim_evidence_status",
    "price_cad", "price_evidence_status", "mileage_km",
    "mileage_evidence_status", "engine", "engine_evidence_status",
    "fuel", "fuel_evidence_status", "accident_claim",
    "accident_evidence_status", "dealer", "dealer_evidence_status",
    "seller_type_claim", "seller_type_evidence_status", "dealer_address",
    "dealer_address_evidence_status", "location", "location_evidence_status",
    "unverified_location_value", "distance_km", "distance_evidence_status",
    "distance_method", "url_region_hint", "url_region_evidence_status",
    "listing_url", "listing_url_evidence_status", "observation_count",
    "first_observed_price_cad", "previous_observation_price_cad",
    "change_from_previous_observation_cad", "change_from_first_observation_cad",
    "source_price_history_text", "legacy_trend_text", "days_on_market_claim",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    temporary.replace(path)


def expected_output_path(root: Path, config: dict[str, Any], source: str) -> Path:
    if source not in SOURCES:
        raise ValueError(f"Unsupported source: {source}")
    key = str(config["vehicle_key"])
    return root / "data" / key / "latest" / f"{key}_{source}_latest.csv"


def source_status_path(root: Path, config: dict[str, Any], source: str) -> Path:
    key = str(config["vehicle_key"])
    return root / "data" / key / "run_status" / f"{source}_latest.json"


def price_history_path(root: Path, config: dict[str, Any], source: str) -> Path:
    key = str(config["vehicle_key"])
    return root / "data" / key / f"price_history_{source}.json"


def file_signature(path: Path) -> tuple[int, int] | None:
    if not path.exists():
        return None
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def validate_csv(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_valid": False, "row_count": 0,
        "missing_columns": sorted(REQUIRED_COLUMNS), "validation_error": None,
    }
    if not path.exists():
        result["validation_error"] = "output_file_missing"
        return result
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(REQUIRED_COLUMNS - set(reader.fieldnames or []))
            row_count = sum(1 for _ in reader)
        result.update(schema_valid=not missing, row_count=row_count, missing_columns=missing)
    except (OSError, csv.Error, UnicodeError) as exc:
        result["validation_error"] = f"{type(exc).__name__}: {exc}"
    return result


def safe_int(value: Any) -> int | None:
    try:
        cleaned = re.sub(r"[^0-9-]", "", str(value))
        return int(cleaned) if cleaned else None
    except (TypeError, ValueError):
        return None


def row_quality_warnings(
    row: dict[str, str], source: str, *, current_year: int | None = None
) -> list[str]:
    warnings: list[str] = []
    year = safe_int(row.get("year"))
    mileage = safe_int(row.get("mileage"))
    current_year = current_year or datetime.now(timezone.utc).year
    if source.strip().lower() == "kijiji":
        warnings.append("unverified_kijiji_location")
    url_years = {
        int(match)
        for match in re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", row.get("url", ""))
        if 1980 <= int(match) <= current_year + 2
    }
    if year and len(url_years) == 1 and year not in url_years:
        warnings.append("url_year_conflicts_with_parsed_year")
    if year and mileage is not None and mileage <= 100 and year <= current_year - 1:
        warnings.append("suspiciously_low_mileage")
    if not year or year <= 0:
        warnings.append("year_unknown")
    if mileage is None or mileage >= 999999:
        warnings.append("mileage_unknown")
    return warnings


def analyze_csv_quality(path: Path, source: str) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    warning_rows = 0
    if path.exists():
        try:
            for row in read_csv_rows(path):
                warnings = row_quality_warnings(row, source)
                if warnings:
                    warning_rows += 1
                    counts.update(warnings)
        except (OSError, csv.Error, UnicodeError):
            pass
    return {
        "data_quality_status": "warnings_present" if warning_rows else "clean",
        "quality_warning_rows": warning_rows,
        "quality_warning_count": sum(counts.values()),
        "quality_warning_summary": dict(sorted(counts.items())),
    }


def status_is_current_success(status: dict[str, Any], run_id: str) -> bool:
    return (
        status.get("run_id") == run_id
        and status.get("execution_status") == "success"
        and status.get("output_updated_this_run") is True
        and status.get("schema_valid") is True
        and int(status.get("current_row_count", status.get("row_count", 0))) > 0
        and int(status.get("accepted_record_count", 0)) > 0
        and status.get("evidence_reconciliation_status") == "reconciled"
        and status.get("canonical_evidence_schema_version") == 1
        and status.get("row_cap_disabled") is True
        and status.get("config_isolated") is True
    )
