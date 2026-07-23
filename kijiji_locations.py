from __future__ import annotations

from typing import Any, Iterable

LOCATION_REGISTRY_VERSION = 1
VALIDATED_AT_UTC = "2026-07-22"

# Query hubs were checked against current Kijiji Cars & Trucks category URLs.
# The config label is governed input; slug/location_id form the request path.
KIJIJI_QUERY_LOCATIONS: dict[str, dict[str, str]] = {
    "Edmonton, AB": {
        "display_name": "Edmonton Area, AB",
        "slug": "edmonton-area",
        "location_id": "1700202",
        "validation_url": "https://www.kijiji.ca/b-cars-trucks/edmonton-area/c174l1700202",
    },
    "Calgary, AB": {
        "display_name": "Calgary, AB",
        "slug": "calgary",
        "location_id": "1700199",
        "validation_url": "https://www.kijiji.ca/b-cars-trucks/calgary/c174l1700199",
    },
    "Saskatoon, SK": {
        "display_name": "Saskatoon, SK",
        "slug": "saskatoon",
        "location_id": "1700197",
        "validation_url": "https://www.kijiji.ca/b-cars-trucks/saskatoon/c174l1700197",
    },
    "Regina, SK": {
        "display_name": "Regina Area, SK",
        "slug": "regina-area",
        "location_id": "1700194",
        "validation_url": "https://www.kijiji.ca/b-cars-trucks/regina-area/c174l1700194",
    },
    "Kelowna, BC": {
        "display_name": "Kelowna, BC",
        "slug": "kelowna",
        "location_id": "1700228",
        "validation_url": "https://www.kijiji.ca/b-cars-trucks/kelowna/c174l1700228",
    },
    "Kamloops, BC": {
        "display_name": "Kamloops, BC",
        "slug": "kamloops",
        "location_id": "1700227",
        "validation_url": "https://www.kijiji.ca/b-cars-trucks/kamloops/c174l1700227",
    },
}


def query_location(value: str) -> dict[str, str]:
    try:
        descriptor = KIJIJI_QUERY_LOCATIONS[value]
    except KeyError as exc:
        supported = ", ".join(KIJIJI_QUERY_LOCATIONS)
        raise ValueError(
            f"Unsupported Kijiji query location {value!r}; supported: {supported}"
        ) from exc
    return {"config_label": value, **descriptor}


def validate_query_locations(values: Iterable[Any]) -> list[dict[str, str]]:
    values = list(values)
    if not values:
        raise ValueError("Kijiji query locations must not be empty")
    descriptors: list[dict[str, str]] = []
    labels: set[str] = set()
    ids: set[str] = set()
    for index, raw in enumerate(values):
        if not isinstance(raw, str) or not raw.strip() or raw != raw.strip():
            raise ValueError(
                f"Kijiji query location at index {index} must be a trimmed string"
            )
        descriptor = query_location(raw)
        folded = raw.casefold()
        if folded in labels:
            raise ValueError(f"Duplicate Kijiji query location: {raw}")
        location_id = descriptor["location_id"]
        if location_id in ids:
            raise ValueError(f"Duplicate Kijiji location identifier: {location_id}")
        labels.add(folded)
        ids.add(location_id)
        descriptors.append(descriptor)
    return descriptors
