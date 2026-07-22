from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class DistanceResult:
    distance_km: int | None
    method: str
    evidence_status: str


def build_distance_resolver(config: dict[str, Any]) -> Callable[[dict[str, Any]], DistanceResult]:
    from geopy.distance import geodesic
    from geopy.geocoders import Nominatim
    import requests

    geolocator = Nominatim(user_agent="vehicle_scraper_autotrader_adapter")
    home = tuple(config["origin"]["home_coords"])
    api_key = os.environ.get("ORS_API_KEY", "")
    cache: dict[str, tuple[float, float] | None] = {}

    def geocode(text: str) -> tuple[float, float] | None:
        if not text:
            return None
        if text in cache:
            return cache[text]
        try:
            time.sleep(1)
            found = geolocator.geocode(text if "Canada" in text else f"{text}, Canada")
            coords = (found.latitude, found.longitude) if found else None
        except Exception:
            coords = None
        cache[text] = coords
        return coords

    def route(coords: tuple[float, float]) -> int | None:
        if not api_key:
            return None
        try:
            response = requests.post(
                "https://api.openrouteservice.org/v2/directions/driving-car",
                json={"coordinates": [[home[1], home[0]], [coords[1], coords[0]]]},
                headers={"Authorization": api_key, "Content-Type": "application/json"},
                timeout=10,
            )
            if not 200 <= response.status_code < 300:
                return None
            return round(response.json()["routes"][0]["summary"]["distance"] / 1000)
        except Exception:
            return None

    def resolve(listing: dict[str, Any]) -> DistanceResult:
        for field, suffix in (("dealer_address", "address"), ("location", "city_center")):
            coords = geocode(str(listing.get(field) or "").strip())
            if coords is None:
                continue
            routed = route(coords)
            if routed is not None:
                return DistanceResult(
                    routed, f"route_api_{suffix}",
                    "route_distance_from_source_reported_location",
                )
            return DistanceResult(
                round(geodesic(home, coords).km), f"geodesic_{suffix}",
                "straight_line_estimate_from_source_reported_location",
            )
        return DistanceResult(None, "unavailable", "location_or_geocode_unavailable")

    return resolve
