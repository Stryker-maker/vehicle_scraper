from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

CONFIG_SCHEMA_VERSION = 2
SUPPORTED_SOURCES = ("autotrader", "kijiji")
LEGACY_RANKING_WEIGHTS = {
    "price": 0.5,
    "mileage": 0.2,
    "distance": 0.15,
    "trim": 0.15,
}
VEHICLE_KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
LOCATION_PATTERN = re.compile(r"^.+, (AB|BC|SK)$")


def _require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _validate_keys(
    value: dict[str, Any], *, required: set[str], optional: set[str] | None = None,
    label: str,
) -> None:
    optional = optional or set()
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required - optional)
    if missing:
        raise ValueError(f"{label} is missing required field(s): {', '.join(missing)}")
    if unknown:
        raise ValueError(f"{label} contains unsupported field(s): {', '.join(unknown)}")


def _require_text(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if not allow_empty and not value.strip():
        raise ValueError(f"{label} must not be empty")
    if value != value.strip():
        raise ValueError(f"{label} must not contain leading or trailing whitespace")
    return value


def _require_positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _validate_location(value: Any, label: str) -> str:
    location = _require_text(value, label)
    match = LOCATION_PATTERN.fullmatch(location)
    if not match:
        raise ValueError(f"{label} must use 'City, PROVINCE' format")
    city, province = location.rsplit(", ", 1)
    if re.search(rf"(?:^|\s){re.escape(province)}$", city, flags=re.IGNORECASE):
        raise ValueError(f"{label} repeats the province abbreviation in the city name")
    return location


def validate_vehicle_config(config: dict[str, Any], *, label: str = "vehicle config") -> dict[str, Any]:
    config = _require_object(config, label)
    _validate_keys(
        config,
        required={"schema_version", "vehicle_key", "make", "model", "criteria", "origin", "sources"},
        label=label,
    )
    if config["schema_version"] != CONFIG_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported vehicle config schema version: {config['schema_version']!r}"
        )

    vehicle_key = _require_text(config["vehicle_key"], f"{label}.vehicle_key")
    if not VEHICLE_KEY_PATTERN.fullmatch(vehicle_key):
        raise ValueError(f"{label}.vehicle_key must use lowercase snake_case")
    _require_text(config["make"], f"{label}.make")
    _require_text(config["model"], f"{label}.model")

    criteria = _require_object(config["criteria"], f"{label}.criteria")
    _validate_keys(
        criteria,
        required={"min_year", "max_year", "max_price_cad", "fuel", "engine"},
        label=f"{label}.criteria",
    )
    min_year = _require_positive_int(criteria["min_year"], f"{label}.criteria.min_year")
    max_year = _require_positive_int(criteria["max_year"], f"{label}.criteria.max_year")
    if min_year > max_year:
        raise ValueError(f"{label}.criteria.min_year must not exceed max_year")
    _require_positive_int(criteria["max_price_cad"], f"{label}.criteria.max_price_cad")
    _require_text(criteria["fuel"], f"{label}.criteria.fuel")
    _require_text(criteria["engine"], f"{label}.criteria.engine", allow_empty=True)

    origin = _require_object(config["origin"], f"{label}.origin")
    _validate_keys(
        origin,
        required={"home_city", "home_coords", "max_distance_km"},
        label=f"{label}.origin",
    )
    _validate_location(origin["home_city"], f"{label}.origin.home_city")
    coords = origin["home_coords"]
    if not isinstance(coords, list) or len(coords) != 2:
        raise ValueError(f"{label}.origin.home_coords must contain [latitude, longitude]")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in coords):
        raise ValueError(f"{label}.origin.home_coords values must be numeric")
    latitude, longitude = float(coords[0]), float(coords[1])
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError(f"{label}.origin.home_coords are outside valid coordinate bounds")
    _require_positive_int(origin["max_distance_km"], f"{label}.origin.max_distance_km")

    sources = _require_object(config["sources"], f"{label}.sources")
    _validate_keys(sources, required=set(SUPPORTED_SOURCES), label=f"{label}.sources")
    for source in SUPPORTED_SOURCES:
        source_config = _require_object(sources[source], f"{label}.sources.{source}")
        _validate_keys(
            source_config,
            required={"make", "model", "search_locations"},
            label=f"{label}.sources.{source}",
        )
        _require_text(source_config["make"], f"{label}.sources.{source}.make")
        _require_text(source_config["model"], f"{label}.sources.{source}.model")
        locations = source_config["search_locations"]
        if not isinstance(locations, list) or not locations:
            raise ValueError(f"{label}.sources.{source}.search_locations must be a non-empty list")
        seen: set[str] = set()
        for index, raw_location in enumerate(locations):
            location_label = f"{label}.sources.{source}.search_locations[{index}]"
            location = _validate_location(raw_location, location_label)
            canonical = location.casefold()
            if canonical in seen:
                raise ValueError(
                    f"{label}.sources.{source}.search_locations contains duplicate: {location}"
                )
            seen.add(canonical)
    return config


def load_vehicle_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    return validate_vehicle_config(value, label=str(path))


def legacy_runtime_config(
    config: dict[str, Any], *, source: str, max_results: int,
) -> dict[str, Any]:
    """Project governed schema v2 into the temporary flat schema required by legacy collectors."""
    validate_vehicle_config(config)
    if source not in SUPPORTED_SOURCES:
        raise ValueError(f"Unsupported source: {source}")
    criteria = config["criteria"]
    origin = config["origin"]
    sources = config["sources"]
    selected = sources[source]
    return {
        "vehicle_key": config["vehicle_key"],
        "make": config["make"],
        "model": config["model"],
        "autotrader_make": sources["autotrader"]["make"],
        "autotrader_model": sources["autotrader"]["model"],
        "kijiji_make": sources["kijiji"]["make"],
        "kijiji_model": sources["kijiji"]["model"],
        "min_year": criteria["min_year"],
        "max_year": criteria["max_year"],
        "max_price": criteria["max_price_cad"],
        "fuel": criteria["fuel"],
        "engine": criteria["engine"],
        "home_city": origin["home_city"],
        "home_coords": list(origin["home_coords"]),
        "max_distance_km": origin["max_distance_km"],
        "max_results": max_results,
        "ranking_weights": dict(LEGACY_RANKING_WEIGHTS),
        "search_locations": list(selected["search_locations"]),
    }
