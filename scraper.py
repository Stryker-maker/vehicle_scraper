"""
AutoTrader Vehicle Scraper
Supports multiple vehicles via config files.
Usage: python scraper.py --config config_f350.json
"""
import argparse
import requests
import json
import csv
import time
import os
import re
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# ─────────────────────────────────────────────
# Args
# ─────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--config", required=True, help="Path to vehicle config JSON")
args = parser.parse_args()

with open(args.config, "r") as f:
    cfg = json.load(f)

with open("trim_tiers.json", "r") as f:
    all_trim_tiers = json.load(f)

# ─────────────────────────────────────────────
# Config values
# ─────────────────────────────────────────────
vehicle_key      = cfg["vehicle_key"]
make             = cfg["make"]
model            = cfg["model"]
at_make          = cfg["autotrader_make"]
at_model         = cfg["autotrader_model"]
min_year         = cfg["min_year"]
max_year         = cfg["max_year"]
max_price        = cfg["max_price"]
fuel             = cfg["fuel"]
engine           = cfg.get("engine", "")
home_city        = cfg["home_city"]
home_coords      = tuple(cfg["home_coords"])
max_distance_km  = cfg["max_distance_km"]
max_results      = cfg["max_results"]
search_locations = cfg["search_locations"]
weights          = cfg["ranking_weights"]
trim_tiers       = all_trim_tiers.get(vehicle_key, {"tier3": [], "tier2": [], "tier1": []})

CANDIDATE_THRESHOLD = 3
ZERO_WEEK_THRESHOLD = 8
CITY_STATS_FILE     = f"data/city_stats_{vehicle_key}.json"

# ─────────────────────────────────────────────
# OpenRouteService
# ─────────────────────────────────────────────
ORS_API_KEY = os.environ.get("ORS_API_KEY", "")
ORS_URL     = "https://api.openrouteservice.org/v2/directions/driving-car"

# ─────────────────────────────────────────────
# Geocoder
# ─────────────────────────────────────────────
geolocator        = Nominatim(user_agent="vehicle_scraper_tool")
city_coords_cache = {}
drive_dist_cache  = {}


def get_city_coords(city_name):
    if city_name in city_coords_cache:
        return city_coords_cache[city_name]
    try:
        time.sleep(1)
        location = geolocator.geocode(city_name + ", Canada")
        if location:
            coords = (location.latitude, location.longitude)
            city_coords_cache[city_name] = coords
            return coords
    except Exception as e:
        print(f"    [geocode error] {city_name}: {e}")
    return None


def get_address_coords(address):
    try:
        time.sleep(1)
        location = geolocator.geocode(address)
        if location:
            return (location.latitude, location.longitude)
    except Exception as e:
        print(f"    [address geocode error] {address}: {e}")
    return None


def get_driving_distance_km(dest_coords):
    if not ORS_API_KEY:
        return round(geodesic(home_coords, dest_coords).km)
    cache_key = f"{dest_coords[0]:.4f},{dest_coords[1]:.4f}"
    if cache_key in drive_dist_cache:
        return drive_dist_cache[cache_key]
    try:
        payload = {
            "coordinates": [
                [home_coords[1], home_coords[0]],
                [dest_coords[1], dest_coords[0]]
            ]
        }
        hdrs = {"Authorization": ORS_API_KEY, "Content-Type": "application/json"}
        response = requests.post(ORS_URL, json=payload, headers=hdrs, timeout=10)
        data = response.json()
        distance_km = round(data["routes"][0]["summary"]["distance"] / 1000)
        drive_dist_cache[cache_key] = distance_km
        time.sleep(0.5)
        return distance_km
    except Exception as e:
        print(f"    [ORS error] straight-line fallback: {e}")
        return round(geodesic(home_coords, dest_coords).km)


def resolve_distance(listing):
    address = listing.get("dealer_address", "")
    if address and len(address) > 5:
        coords = get_address_coords(address)
        if coords:
            return get_driving_distance_km(coords), "address"
    city = listing.get("location", "")
    if city:
        coords = get_city_coords(city)
        if coords:
            return get_driving_distance_km(coords), "city_center"
    best_dist, best_city = 9999, None
    listing_coords = get_city_coords(city) if city else None
    if listing_coords:
        for loc in search_locations:
            loc_coords = get_city_coords(loc)
            if loc_coords:
                d = geodesic(listing_coords, loc_coords).km
                if d < best_dist:
                    best_dist, best_city = d, loc
    if best_city:
        coords = get_city_coords(best_city)
        if coords:
            return get_driving_distance_km(coords), f"nearest_city ({best_city})"
    return 9999, "unknown"


# ─────────────────────────────────────────────
# Trim scoring
# ─────────────────────────────────────────────
def get_trim_tier(trim_str):
    """Return tier 1/2/3 and a normalised score (0=base, 0.5=mid, 1=premium)."""
    if not trim_str:
        return 1, 0.0
    t = trim_str.lower()
    for keyword in trim_tiers.get("tier3", []):
        if keyword.lower() in t:
            return 3, 1.0
    for keyword in trim_tiers.get("tier2", []):
        if keyword.lower() in t:
            return 2, 0.5
    return 1, 0.0


# ─────────────────────────────────────────────
# Data enrichment helpers
# ─────────────────────────────────────────────
def parse_days_on_market(item):
    """
    AutoTrader doesn't expose a direct 'listed date' field in search results.
    We flag it as N/A; individual listing pages have it but require extra fetches.
    """
    return "N/A"


def parse_accident_flag(item):
    """
    Check description and title text for accident/salvage/carfax keywords.
    Returns: 'No accidents reported', 'Accident reported', 'Salvage/rebuilt',
             or 'Unknown'
    """
    text_fields = [
        item.get("description", "") or "",
        item.get("vehicle", {}).get("modelVersionInput", "") or "",
    ]
    # Also check vehicleDetails array
    for detail in item.get("vehicleDetails", []):
        text_fields.append(detail.get("data", "") or "")

    combined = " ".join(text_fields).lower()

    salvage_keywords = ["salvage", "rebuilt title", "rebuilt status", "structural damage"]
    accident_keywords = ["accident", "collision", "damage reported", "carfax shows"]
    clean_keywords = ["no accident", "clean carfax", "accident free", "0 accident",
                      "zero accident", "no reported accident", "carfax clean"]

    for kw in salvage_keywords:
        if kw in combined:
            return "Salvage/rebuilt"
    for kw in clean_keywords:
        if kw in combined:
            return "No accidents reported"
    for kw in accident_keywords:
        if kw in combined:
            return "Accident reported"
    return "Unknown"


def parse_price_history(item):
    """
    Check superDeal field for old price — indicates a price reduction.
    Returns 'Price reduced from $X' or 'No change noted'.
    """
    super_deal = item.get("superDeal", {})
    old_price_str = super_deal.get("oldPriceFormatted", "")
    if old_price_str and old_price_str.strip():
        return f"Reduced from {old_price_str.strip()}"
    return "No change noted"


# ─────────────────────────────────────────────
# Self-managing location system
# ─────────────────────────────────────────────
def load_city_stats():
    if os.path.exists(CITY_STATS_FILE):
        try:
            with open(CITY_STATS_FILE, "r") as f:
                data = json.load(f)
                if "candidates" in data and "zero_weeks" in data:
                    return data
        except Exception:
            pass
    return {"candidates": {}, "zero_weeks": {}}


def save_city_stats(stats):
    os.makedirs("data", exist_ok=True)
    with open(CITY_STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)


def normalize_city(city_raw):
    parts = city_raw.strip().split(",")
    if len(parts) == 2:
        return f"{parts[0].strip().title()}, {parts[1].strip().upper()}"
    return city_raw.strip().title()


def update_locations(matches):
    global search_locations
    stats      = load_city_stats()
    candidates = stats["candidates"]
    zero_weeks = stats["zero_weeks"]

    normalized_search = {normalize_city(c) for c in search_locations}

    for v in matches:
        city = normalize_city(v.get("location", ""))
        if city and city not in normalized_search:
            candidates[city] = candidates.get(city, 0) + 1

    promoted = []
    for city, count in list(candidates.items()):
        if count >= CANDIDATE_THRESHOLD:
            coords = get_city_coords(city)
            if coords:
                dist = get_driving_distance_km(coords)
                if dist <= max_distance_km:
                    search_locations.append(city)
                    normalized_search.add(city)
                    promoted.append(city)
                    del candidates[city]
                    zero_weeks.pop(city, None)
                    print(f"  [AUTO-ADD] '{city}' added ({count} appearances, {dist} km)")
                else:
                    print(f"  [SKIPPED]  '{city}' out of range ({dist} km)")
                    del candidates[city]
            else:
                print(f"  [SKIPPED]  '{city}' could not be geocoded")
                del candidates[city]

    cities_with_matches = {normalize_city(v.get("location", "")) for v in matches}
    removed = []
    for city in list(search_locations):
        norm = normalize_city(city)
        if norm in cities_with_matches:
            zero_weeks.pop(norm, None)
        else:
            zero_weeks[norm] = zero_weeks.get(norm, 0) + 1
            if zero_weeks[norm] >= ZERO_WEEK_THRESHOLD:
                search_locations = [c for c in search_locations
                                    if normalize_city(c) != norm]
                removed.append(city)
                del zero_weeks[norm]
                print(f"  [AUTO-REMOVE] '{city}' removed after {ZERO_WEEK_THRESHOLD} empty weeks")

    if promoted or removed:
        cfg["search_locations"] = search_locations
        with open(args.config, "w") as f:
            json.dump(cfg, f, indent=2)
        print(f"  {args.config} updated — {len(search_locations)} cities")

    stats["candidates"] = candidates
    stats["zero_weeks"] = zero_weeks
    save_city_stats(stats)

    print(f"\n  Location summary for {vehicle_key}:")
    print(f"    Active cities:    {len(search_locations)}")
    print(f"    Candidates:       {len(candidates)}")
    if candidates:
        for city, count in sorted(candidates.items(), key=lambda x: x[1], reverse=True):
            print(f"      {city}: {count}/{CANDIDATE_THRESHOLD}")
    if zero_weeks:
        print(f"    On watch (empty weeks):")
        for city, weeks in sorted(zero_weeks.items(), key=lambda x: x[1], reverse=True):
            print(f"      {city}: {weeks}/{ZERO_WEEK_THRESHOLD}")


# ─────────────────────────────────────────────
# Search summary
# ─────────────────────────────────────────────
def search_summary():
    print("=" * 50)
    print(f"AUTOTRADER SCRAPER — {make} {model}")
    print("=" * 50)
    print(f"  Years:        {min_year} – {max_year}")
    print(f"  Max price:    ${max_price:,}")
    print(f"  Fuel:         {fuel}")
    if engine:
        print(f"  Engine:       {engine}")
    print(f"  Home base:    {home_city}")
    print(f"  Max distance: {max_distance_km} km driving")
    print(f"  Cities:       {len(search_locations)}")
    print(f"  Max results:  {max_results}")
    print(f"  Weights:      Price {int(weights['price']*100)}% | "
          f"Mileage {int(weights['mileage']*100)}% | "
          f"Distance {int(weights['distance']*100)}% | "
          f"Trim {int(weights['trim']*100)}%")
    print("=" * 50)


# ─────────────────────────────────────────────
# Fetch listings
# ─────────────────────────────────────────────
def fetch_autotrader_listings():
    all_listings = []
    seen_ids     = set()
    hdrs = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    # Build fuel param
    fuel_param = ""
    if fuel.lower() == "diesel":
        fuel_param = "&fuel=Diesel"
    elif fuel.lower() in ("gas", "gasoline"):
        fuel_param = "&fuel=Gas"
    elif fuel.lower() == "hybrid":
        fuel_param = "&fuel=Hybrid"

    for i, city in enumerate(search_locations):
        city_encoded = city.replace(" ", "%20").replace(",", "%2C")
        url = (
            f"https://www.autotrader.ca/cars/{at_make}/{at_model}/"
            f"?rcp=100&rcs=0&srt=35&loc={city_encoded}"
            f"{fuel_param}&hprc=True&wcp=True"
            f"&inMarket=advancedSearch&sts=New-Used&prx=100"
        )
        print(f"\n  [{i+1}/{len(search_locations)}] Searching {city}...")

        try:
            response = requests.get(url, headers=hdrs, timeout=15)
            soup     = BeautifulSoup(response.text, "html.parser")
            data     = None
            for script in soup.find_all("script"):
                if script.string and '"listings"' in script.string:
                    try:
                        data = json.loads(script.string)
                        break
                    except Exception:
                        continue

            if not data:
                print(f"    No JSON data found.")
                time.sleep(2)
                continue

            raw_listings = data.get("props", {}).get("pageProps", {}).get("listings", [])
            if not raw_listings:
                print(f"    No listings in response.")
                time.sleep(2)
                continue

            new_count = 0
            for item in raw_listings:
                try:
                    listing_id = str(item.get("id", ""))
                    if not listing_id or listing_id in seen_ids:
                        continue
                    seen_ids.add(listing_id)

                    # Price
                    price_raw   = item.get("price", {}).get("priceFormatted", "0")
                    price_clean = int(
                        price_raw.replace("$", "").replace(",", "").replace(" ", "")
                    )

                    # Engine
                    engine_raw   = item["vehicle"].get("engineDisplacementInCCM", "")
                    engine_str   = str(engine_raw)
                    if "6,700" in engine_str or "6700" in engine_str:
                        engine_clean = "6.7L"
                    elif engine_str:
                        # Convert CCM to litres if numeric
                        try:
                            ccm = float(re.sub(r"[^\d.]", "", engine_str))
                            engine_clean = f"{round(ccm/1000, 1)}L"
                        except Exception:
                            engine_clean = engine_str
                    else:
                        engine_clean = "Unknown"

                    # Mileage
                    mileage_raw = item["vehicle"].get("mileageInKm", None)
                    if mileage_raw and isinstance(mileage_raw, str):
                        try:
                            mileage = int(
                                mileage_raw.replace(",", "").replace(" km", "").strip()
                            )
                        except (ValueError, TypeError):
                            mileage = 999999
                    elif isinstance(mileage_raw, (int, float)):
                        mileage = int(mileage_raw)
                    else:
                        mileage = 999999

                    # Fuel type
                    fuel_type = item["vehicle"].get("fuel", "")

                    # Year
                    try:
                        year = int(item["vehicle"].get("modelYear", 0))
                    except Exception:
                        year = 0

                    # Trim
                    trim_str  = item["vehicle"].get("modelVersionInput", "") or ""
                    trim_tier, trim_score = get_trim_tier(trim_str)

                    # Location / address
                    loc_obj      = item.get("location", {})
                    loc_city     = loc_obj.get("city", "")
                    loc_province = loc_obj.get("provinceCode", "")
                    loc_street   = loc_obj.get("street", "")
                    loc_zip      = loc_obj.get("zip", "")
                    listing_city = f"{loc_city}, {loc_province}".strip(", ")

                    dealer_address = ""
                    if loc_street:
                        parts = [p for p in [loc_street, loc_city, loc_province, loc_zip] if p]
                        dealer_address = ", ".join(parts)

                    dealer_name = item.get("seller", {}).get("companyName", "Unknown")

                    # Enrichment fields
                    accident_flag  = parse_accident_flag(item)
                    price_history  = parse_price_history(item)
                    days_on_market = parse_days_on_market(item)

                    listing_url = item.get("url", "")
                    if not listing_url:
                        listing_url = f"https://www.autotrader.ca/a/{at_make}/{at_model}/{listing_id}/"

                    listing = {
                        "year":            year,
                        "make":            item["vehicle"].get("make", make),
                        "model":           item["vehicle"].get("model", model),
                        "trim":            trim_str,
                        "trim_tier":       trim_tier,
                        "trim_score":      trim_score,
                        "price":           price_clean,
                        "price_history":   price_history,
                        "engine":          engine_clean,
                        "fuel":            fuel_type,
                        "mileage":         mileage,
                        "accident_flag":   accident_flag,
                        "days_on_market":  days_on_market,
                        "dealer":          dealer_name,
                        "seller_type":     "Dealer",
                        "dealer_address":  dealer_address,
                        "location":        listing_city,
                        "distance_km":     None,
                        "distance_method": None,
                        "listing_id":      listing_id,
                        "url":             listing_url,
                        "source":          "AutoTrader"
                    }
                    all_listings.append(listing)
                    new_count += 1

                except Exception:
                    continue

            print(f"    +{new_count} new | Total: {len(all_listings)}")
            time.sleep(1.5)

        except Exception as e:
            print(f"    Error: {e}")
            continue

    return all_listings


# ─────────────────────────────────────────────
# Resolve distances
# ─────────────────────────────────────────────
def resolve_all_distances(listings):
    print(f"\n  Resolving driving distances for {len(listings)} listings...")
    for i, listing in enumerate(listings):
        dist, method = resolve_distance(listing)
        listing["distance_km"]     = dist
        listing["distance_method"] = method
        if (i + 1) % 10 == 0:
            print(f"    Resolved {i+1}/{len(listings)}...")
    return listings


# ─────────────────────────────────────────────
# Filter
# ─────────────────────────────────────────────
def filter_listings(listings):
    matches = []
    for v in listings:
        year_ok  = min_year <= v["year"] <= max_year
        price_ok = 0 < v["price"] <= max_price
        dist_ok  = v["distance_km"] <= max_distance_km
        fuel_ok  = fuel.lower() in v["fuel"].lower() if fuel else True
        eng_ok   = (engine in v["engine"]) if engine else True

        if year_ok and price_ok and dist_ok and fuel_ok and eng_ok:
            matches.append(v)
    return matches


# ─────────────────────────────────────────────
# Rank
# ─────────────────────────────────────────────
def rank_listings(matches):
    pw = weights["price"]
    mw = weights["mileage"]
    dw = weights["distance"]
    tw = weights["trim"]

    for v in matches:
        try:
            v["mileage"] = int(v["mileage"])
        except (ValueError, TypeError):
            v["mileage"] = 999999

    max_price_val    = max(v["price"]       for v in matches)
    max_mileage_val  = max(v["mileage"]     for v in matches)
    max_distance_val = max(v["distance_km"] for v in matches)

    for v in matches:
        price_score    = v["price"]       / max_price_val    if max_price_val    > 0 else 0
        mileage_score  = v["mileage"]     / max_mileage_val  if max_mileage_val  > 0 else 0
        distance_score = v["distance_km"] / max_distance_val if max_distance_val > 0 else 0
        # Trim: higher tier = lower score (better rank). Invert the trim_score.
        trim_penalty   = 1.0 - v["trim_score"]

        v["score"] = (
            (price_score    * pw) +
            (mileage_score  * mw) +
            (distance_score * dw) +
            (trim_penalty   * tw)
        )

    matches.sort(key=lambda v: v["score"])
    return matches


# ─────────────────────────────────────────────
# Display
# ─────────────────────────────────────────────
def display_results(ranked):
    display = ranked[:max_results]
    print(f"\n{'=' * 50}")
    print(f"  TOP {len(display)} RESULTS — {make} {model}")
    print(f"{'=' * 50}")
    tier_labels = {1: "Base", 2: "Mid", 3: "Premium"}
    for i, v in enumerate(display):
        mileage_str = f"{v['mileage']:,} km" if v["mileage"] != 999999 else "Unknown"
        print(f"\n  Rank {i+1}")
        print(f"  {v['year']} {v['make']} {v['model']} {v['trim']}")
        print(f"  Trim tier:     {tier_labels.get(v['trim_tier'], '?')} (Tier {v['trim_tier']})")
        print(f"  Price:         ${v['price']:,}  [{v['price_history']}]")
        print(f"  Mileage:       {mileage_str}")
        print(f"  Accidents:     {v['accident_flag']}")
        print(f"  Dealer:        {v['dealer']} ({v['seller_type']})")
        print(f"  Location:      {v['location']}")
        print(f"  Distance:      {v['distance_km']} km ({v['distance_method']})")
        print(f"  Score:         {round(v['score'], 4)}")
        print(f"  URL:           {v['url']}")


# ─────────────────────────────────────────────
# Save CSV
# ─────────────────────────────────────────────
def save_results(ranked):
    os.makedirs("data", exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename  = f"data/{vehicle_key}_autotrader_{timestamp}.csv"

    fields = [
        "rank", "year", "make", "model", "trim", "trim_tier",
        "price", "price_history", "mileage", "engine", "fuel",
        "accident_flag", "days_on_market",
        "dealer", "seller_type", "dealer_address", "location",
        "distance_km", "distance_method",
        "listing_id", "url", "score", "source"
    ]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for i, v in enumerate(ranked[:max_results]):
            row           = {field: v.get(field, "") for field in fields}
            row["rank"]   = i + 1
            row["mileage"] = v["mileage"] if v["mileage"] != 999999 else "Unknown"
            writer.writerow(row)

    print(f"\n  Saved: {filename}")
    return filename


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
if __name__ == "__main__":
    search_summary()

    print("\nFetching listings from AutoTrader...")
    listings = fetch_autotrader_listings()
    print(f"\nRaw listings: {len(listings)}")

    listings = resolve_all_distances(listings)

    matches = filter_listings(listings)
    print(f"After filtering: {len(matches)}")

    if matches:
        ranked = rank_listings(matches)
        display_results(ranked)
        save_results(ranked)
    else:
        print("\nNo matches found.")

    print("\nUpdating location list...")
    update_locations(matches)
