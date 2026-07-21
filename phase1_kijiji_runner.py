"""Phase 1 Kijiji runner that preserves listings without trusting location or distance."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import urlparse

PATCHES = (
    (
        "    listings = resolve_all_distances(listings)",
        "    listings = phase1_prepare_kijiji_listings(listings)",
    ),
    (
        "    matches = filter_listings(listings)",
        "    matches = phase1_filter_kijiji_listings(\n"
        "        listings, min_year=min_year, max_year=max_year, max_price=max_price,\n"
        "        fuel=fuel, engine=engine,\n"
        "    )",
    ),
    (
        "        ranked = rank_listings(matches)",
        "        ranked = phase1_order_kijiji_results(matches)",
    ),
    (
        "        display_results(ranked)",
        "        phase1_display_summary(ranked)",
    ),
    (
        "    update_locations(matches)",
        "    phase1_skip_location_updates(matches)",
    ),
    (
        '        "listing_id", "url", "score", "source"',
        '        "listing_id", "url_region_hint", "url_region_status",\n'
        '        "url", "score", "source"',
    ),
)


def extract_url_region_hint(url: str) -> str:
    """Extract Kijiji's URL region segment as unverified navigation evidence."""
    try:
        parts = [part for part in urlparse(url).path.split("/") if part]
    except (TypeError, ValueError):
        return ""
    try:
        index = parts.index("v-cars-trucks")
    except ValueError:
        return ""
    return parts[index + 1] if index + 1 < len(parts) else ""


def phase1_prepare_kijiji_listings(listings: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for listing in listings:
        hint = extract_url_region_hint(str(listing.get("url", "")))
        listing["url_region_hint"] = hint
        listing["url_region_status"] = "unverified_url_evidence" if hint else "unavailable"
        listing["distance_km"] = ""
        listing["distance_method"] = "disabled_unverified_location"
        prepared.append(listing)
    return prepared


def phase1_filter_kijiji_listings(
    listings: Iterable[dict[str, Any]], *, min_year: int, max_year: int,
    max_price: int, fuel: str = "", engine: str = "",
) -> list[dict[str, Any]]:
    """Apply only non-location filters; unverified geography never excludes a record."""
    matches: list[dict[str, Any]] = []
    for vehicle in listings:
        year = int(vehicle.get("year") or 0)
        price = int(vehicle.get("price") or 0)
        vehicle_fuel = str(vehicle.get("fuel", ""))
        vehicle_engine = str(vehicle.get("engine", ""))
        year_ok = min_year <= year <= max_year
        price_ok = 0 < price <= max_price
        fuel_ok = fuel.lower() in vehicle_fuel.lower() if fuel else True
        engine_ok = engine in vehicle_engine if engine else True
        if year_ok and price_ok and fuel_ok and engine_ok:
            matches.append(vehicle)
    return matches


def phase1_order_kijiji_results(matches: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create deterministic, unranked source order without a location-based score."""
    rows = list(matches)
    for vehicle in rows:
        try:
            vehicle["mileage"] = int(vehicle.get("mileage", 999999))
        except (TypeError, ValueError):
            vehicle["mileage"] = 999999
        vehicle["score"] = ""
    rows.sort(key=lambda vehicle: (
        int(vehicle.get("year") or 0), int(vehicle.get("price") or 0),
        int(vehicle.get("mileage") or 999999), str(vehicle.get("listing_id", "")),
    ))
    return rows


def phase1_display_summary(results: Sequence[dict[str, Any]]) -> None:
    print("\n" + "=" * 50)
    print(f"  {len(results)} KIJIJI RECORDS — PHASE 1 MANUAL REVIEW")
    print("  Ranking and distance processing are disabled.")
    print("=" * 50)


def phase1_skip_location_updates(_matches: Sequence[dict[str, Any]]) -> None:
    print("  Phase 1: Kijiji location mutation skipped because location is unverified.")


def patch_legacy_source(source: str) -> str:
    patched = source
    for old, new in PATCHES:
        count = patched.count(old)
        if count != 1:
            raise RuntimeError(f"Expected one Kijiji patch anchor, found {count}: {old!r}")
        patched = patched.replace(old, new, 1)
    return patched


def execute(scraper_path: Path, config_path: str) -> None:
    source = scraper_path.read_text(encoding="utf-8")
    patched = patch_legacy_source(source)
    namespace = {
        "__name__": "__main__",
        "__file__": str(scraper_path),
        "phase1_prepare_kijiji_listings": phase1_prepare_kijiji_listings,
        "phase1_filter_kijiji_listings": phase1_filter_kijiji_listings,
        "phase1_order_kijiji_results": phase1_order_kijiji_results,
        "phase1_display_summary": phase1_display_summary,
        "phase1_skip_location_updates": phase1_skip_location_updates,
    }
    original_argv = sys.argv[:]
    try:
        sys.argv = [str(scraper_path), "--config", config_path]
        exec(compile(patched, str(scraper_path), "exec"), namespace)
    finally:
        sys.argv = original_argv


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--config", required=True)
    result.add_argument("--scraper", default="kijiji_scraper.py")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    execute(Path(args.scraper), args.config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
