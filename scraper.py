"""
AutoTrader Vehicle Scraper
Usage: python scraper.py --config config_f350.json
"""
import argparse
import requests
import json
import csv
import time
import os
import re
import shutil
from datetime import datetime
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# ─────────────────────────────────────────────
# Args
# ─────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--config", required=True)
args = parser.parse_args()

with open(args.config, "r") as f:
    cfg = json.load(f)

with open("trim_tiers.json", "r") as f:
    all_trim_tiers = json.load(f)

# ─────────────────────────────────────────────
# Config
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
CITY_STATS_FILE     = f"data/{vehicle_key}/city_stats_autotrader.json"

# Output folders
ARCHIVE_DIR = f"data/{vehicle_key}/autotrader"
LATEST_DIR  = f"data/{vehicle_key}/latest"
LATEST_FILE = f"{LATEST_DIR}/{vehicle_key}_autotrader_latest.csv"

# ─────────────────────────────────────────────
# ORS / Geocoder
# ─────────────────────────────────────────────
ORS_API_KEY       = os.environ.get("ORS_API_KEY", "")
ORS_URL           = "https://api.openrouteservice.org/v2/directions/driving-car"
geolocator        = Nominatim(user_agent="vehicle_scraper_tool")
city_coords_cache = {}
drive_dist_cache  = {}


def get_city_coords(city_name):
    if city_name in city_coords_cache:
        return city_coords_cache[city_name]
    try:
        time.sleep(1)
        loc = geolocator.geocode(city_name + ", Canada")
        if loc:
            coords = (loc.latitude, loc.longitude)
            city_coords_cache[city_name] = coords
            return coords
    except Exception as e:
        print(f"    [geocode error] {city_name}: {e}")
    return None


def get_address_coords(address):
    try:
        time.sleep(1)
        loc = geolocator.geocode(address)
        if loc:
            return (loc.latitude, loc.longitude)
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
        r = requests.post(ORS_URL, json=payload, headers=hdrs, timeout=10)
        km = round(r.json()["routes"][0]["summary"]["distance"] / 1000)
        drive_dist_cache[cache_key] = km
        time.sleep(0.5)
        return km
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
            lc = get_city_coords(loc)
            if lc:
                d = geodesic(listing_coords, lc).km
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
def get_trim_tier(text):
    if not text:
        return 1, 0.0
    t = text.lower()
    for kw in trim_tiers.get("tier3", []):
        if kw.lower() in t:
            return 3, 1.0
    for kw in trim_tiers.get("tier2", []):
        if kw.lower() in t:
            return 2, 0.5
    return 1, 0.0


# ─────────────────────────────────────────────
# Enrichment helpers
# ─────────────────────────────────────────────
def parse_accident_flag(item):
    text_fields = [
        item.get("description", "") or "",
        item.get("vehicle", {}).get("modelVersionInput", "") or "",
    ]
    for detail in item.get("vehicleDetails", []):
        text_fields.append(detail.get("data", "") or "")
    combined = " ".join(text_fields).lower()
    for kw in ["salvage", "rebuilt title", "structural damage"]:
        if kw in combined:
            return "Salvage/rebuilt"
    for kw in ["no accident", "clean carfax", "accident free", "0 accident",
                "zero accident", "no reported accident"]:
        if kw in combined:
            return "No accidents reported"
    for kw in ["accident", "collision", "damage reported"]:
        if kw in combined:
            return "Accident reported"
    return "Unknown"


def parse_price_history(item):
    old = item.get("superDeal", {}).get("oldPriceFormatted", "")
    if old and old.strip():
        return f"Reduced from {old.strip()}"
    return "No change noted"


# ─────────────────────────────────────────────
# Price trend tracking
# ─────────────────────────────────────────────
def load_price_history():
    """Load price history index from disk — {listing_id: [{date, price, rank}]}"""
    path = f"data/{vehicle_key}/price_history_autotrader.json"
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_price_history(history):
    path = f"data/{vehicle_key}/price_history_autotrader.json"
    os.makedirs(f"data/{vehicle_key}", exist_ok=True)
    with open(path, "w") as f:
        json.dump(history, f, indent=2)


def apply_price_trends(ranked):
    """
    Compare current prices against historical data.
    Adds fields: weeks_tracked, price_at_first_seen,
                 price_last_week, price_change_total,
                 price_change_vs_listed
    """
    history = load_price_history()
    today   = datetime.now().strftime("%Y-%m-%d")

    for v in ranked:
        lid   = v["listing_id"]
        price = v["price"]

        if lid not in history:
            history[lid] = []

        records = history[lid]

        # Price change vs last week
        if records:
            last_price           = records[-1]["price"]
            first_price          = records[0]["price"]
            weeks_tracked        = len(records)
            price_change_week    = price - last_price
            price_change_total   = price - first_price
            v["weeks_tracked"]        = weeks_tracked
            v["price_first_seen"]     = first_price
            v["price_last_week"]      = last_price
            v["price_change_week"]    = price_change_week
            v["price_change_total"]   = price_change_total

            if price_change_total < 0:
                v["trend"] = f"Down ${abs(price_change_total):,} over {weeks_tracked} weeks"
            elif price_change_total > 0:
                v["trend"] = f"Up ${price_change_total:,} over {weeks_tracked} weeks"
            else:
                v["trend"] = f"Unchanged for {weeks_tracked} weeks"
        else:
            v["weeks_tracked"]      = 0
            v["price_first_seen"]   = price
            v["price_last_week"]    = price
            v["price_change_week"]  = 0
            v["price_change_total"] = 0
            v["trend"]              = "First seen this week"

        # Append today's record
        records.append({"date": today, "price": price, "rank": v.get("score", 0)})
        history[lid] = records

    save_price_history(history)
    return ranked


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
    os.makedirs(f"data/{vehicle_key}", exist_ok=True)
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
    norm_search = {normalize_city(c) for c in search_locations}

    for v in matches:
        city = normalize_city(v.get("location", ""))
        if city and city not in norm_search:
            candidates[city] = candidates.get(city, 0) + 1

    for city, count in list(candidates.items()):
        if count >= CANDIDATE_THRESHOLD:
            coords = get_city_coords(city)
            if coords:
                dist = get_driving_distance_km(coords)
                if dist <= max_distance_km:
                    search_locations.append(city)
                    norm_search.add(city)
                    del candidates[city]
                    zero_weeks.pop(city, None)
                    print(f"  [AUTO-ADD] '{city}' added ({count} appearances, {dist} km)")
                else:
                    del candidates[city]
            else:
                del candidates[city]

    cities_with_matches = {normalize_city(v.get("location", "")) for v in matches}
    for city in list(search_locations):
        norm = normalize_city(city)
        if norm in cities_with_matches:
            zero_weeks.pop(norm, None)
        else:
            zero_weeks[norm] = zero_weeks.get(norm, 0) + 1
            if zero_weeks[norm] >= ZERO_WEEK_THRESHOLD:
                search_locations = [c for c in search_locations
                                    if normalize_city(c) != norm]
                del zero_weeks[norm]
                print(f"  [AUTO-REMOVE] '{city}' removed after {ZERO_WEEK_THRESHOLD} empty weeks")

    if True:
        cfg["search_locations"] = search_locations
        with open(args.config, "w") as f:
            json.dump(cfg, f, indent=2)

    stats["candidates"] = candidates
    stats["zero_weeks"] = zero_weeks
    save_city_stats(stats)

    print(f"\n  Location summary ({vehicle_key} AutoTrader):")
    print(f"    Active cities: {len(search_locations)}")
    if candidates:
        for city, count in sorted(candidates.items(), key=lambda x: x[1], reverse=True):
            print(f"      Candidate: {city}: {count}/{CANDIDATE_THRESHOLD}")
    if zero_weeks:
        for city, weeks in sorted(zero_weeks.items(), key=lambda x: x[1], reverse=True):
            print(f"      On watch:  {city}: {weeks}/{ZERO_WEEK_THRESHOLD}")


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

                    price_raw   = item.get("price", {}).get("priceFormatted", "0")
                    price_clean = int(price_raw.replace("$", "").replace(",", "").replace(" ", ""))

                    engine_raw  = item["vehicle"].get("engineDisplacementInCCM", "")
                    engine_str  = str(engine_raw)
                    if "6,700" in engine_str or "6700" in engine_str:
                        engine_clean = "6.7L"
                    elif engine_str:
                        try:
                            ccm = float(re.sub(r"[^\d.]", "", engine_str))
                            engine_clean = f"{round(ccm/1000, 1)}L"
                        except Exception:
                            engine_clean = engine_str
                    else:
                        engine_clean = "Unknown"

                    mileage_raw = item["vehicle"].get("mileageInKm", None)
                    if mileage_raw and isinstance(mileage_raw, str):
                        try:
                            mileage = int(mileage_raw.replace(",", "").replace(" km", "").strip())
                        except (ValueError, TypeError):
                            mileage = 999999
                    elif isinstance(mileage_raw, (int, float)):
                        mileage = int(mileage_raw)
                    else:
                        mileage = 999999

                    fuel_type = item["vehicle"].get("fuel", "")

                    try:
                        year = int(item["vehicle"].get("modelYear", 0))
                    except Exception:
                        year = 0

                    trim_str  = item["vehicle"].get("modelVersionInput", "") or ""
                    trim_tier_val, trim_score = get_trim_tier(trim_str)

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

                    dealer_name    = item.get("seller", {}).get("companyName", "Unknown")
                    accident_flag  = parse_accident_flag(item)
                    price_history  = parse_price_history(item)
                    listing_url    = item.get("url", "") or \
                                     f"https://www.autotrader.ca/a/{at_make}/{at_model}/{listing_id}/"

                    listing = {
                        "year":            year,
                        "make":            item["vehicle"].get("make", make),
                        "model":           item["vehicle"].get("model", model),
                        "trim":            trim_str,
                        "trim_tier":       trim_tier_val,
                        "trim_score":      trim_score,
                        "price":           price_clean,
                        "price_history":   price_history,
                        "engine":          engine_clean,
                        "fuel":            fuel_type,
                        "mileage":         mileage,
                        "accident_flag":   accident_flag,
                        "days_on_market":  "N/A",
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
    tier_labels = {1: "Base", 2: "Mid", 3: "Premium"}
    print(f"\n{'=' * 50}")
    print(f"  TOP {len(display)} RESULTS — {make} {model}")
    print(f"{'=' * 50}")
    for i, v in enumerate(display):
        mileage_str = f"{v['mileage']:,} km" if v["mileage"] != 999999 else "Unknown"
        print(f"\n  Rank {i+1}")
        print(f"  {v['year']} {v['make']} {v['model']} {v['trim']}")
        print(f"  Trim tier:     {tier_labels.get(v['trim_tier'], '?')} (Tier {v['trim_tier']})")
        print(f"  Price:         ${v['price']:,}  [{v['price_history']}]")
        print(f"  Mileage:       {mileage_str}")
        print(f"  Accidents:     {v['accident_flag']}")
        print(f"  Trend:         {v.get('trend', 'First seen this week')}")
        print(f"  Dealer:        {v['dealer']} ({v['seller_type']})")
        print(f"  Location:      {v['location']}")
        print(f"  Distance:      {v['distance_km']} km ({v['distance_method']})")
        print(f"  Score:         {round(v['score'], 4)}")
        print(f"  URL:           {v['url']}")


# ─────────────────────────────────────────────
# Save CSV
# ─────────────────────────────────────────────
def save_results(ranked):
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    os.makedirs(LATEST_DIR,  exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename  = f"{ARCHIVE_DIR}/{vehicle_key}_autotrader_{timestamp}.csv"

    fields = [
        "rank", "year", "make", "model", "trim", "trim_tier",
        "price", "price_history", "trend",
        "weeks_tracked", "price_first_seen", "price_last_week",
        "price_change_week", "price_change_total",
        "mileage", "engine", "fuel",
        "accident_flag", "days_on_market",
        "dealer", "seller_type", "dealer_address", "location",
        "distance_km", "distance_method",
        "listing_id", "url", "score", "source"
    ]

    rows = []
    for i, v in enumerate(ranked[:max_results]):
        row = {field: v.get(field, "") for field in fields}
        row["rank"]    = i + 1
        row["mileage"] = v["mileage"] if v["mileage"] != 999999 else "Unknown"
        rows.append(row)

    for path in [filename, LATEST_FILE]:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    print(f"\n  Archived: {filename}")
    print(f"  Latest:   {LATEST_FILE}")
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
        ranked = apply_price_trends(ranked)
        display_results(ranked)
        save_results(ranked)
    else:
        print("\nNo matches found.")

    print("\nUpdating location list...")
    update_locations(matches)
