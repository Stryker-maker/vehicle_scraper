"""
Kijiji Vehicle Scraper — JSON-LD based
Usage: python kijiji_scraper.py --config config_f350.json
"""
import argparse
import requests
import json
import csv
import time
import os
import re
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
kijiji_make      = cfg["kijiji_make"]
kijiji_model     = cfg["kijiji_model"]
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
CITY_STATS_FILE     = f"data/{vehicle_key}/city_stats_kijiji.json"

ARCHIVE_DIR = f"data/{vehicle_key}/kijiji"
LATEST_DIR  = f"data/{vehicle_key}/latest"
LATEST_FILE = f"{LATEST_DIR}/{vehicle_key}_kijiji_latest.csv"

# ─────────────────────────────────────────────
# Kijiji location map
# ─────────────────────────────────────────────
KIJIJI_LOCATIONS = {
    "Red Deer, AB":       ("red-deer",       "1700228"),
    "Edmonton, AB":       ("edmonton",        "1700203"),
    "Calgary, AB":        ("calgary",         "1700199"),
    "Lethbridge, AB":     ("lethbridge",      "1700229"),
    "Medicine Hat, AB":   ("medicine-hat",    "1700230"),
    "Grande Prairie, AB": ("grande-prairie",  "1700211"),
    "Fort McMurray, AB":  ("fort-mcmurray",   "1700208"),
    "Lloydminster, AB":   ("lloydminster",    "1700221"),
    "Camrose, AB":        ("camrose",         "1700202"),
    "Wetaskiwin, AB":     ("wetaskiwin",      "1700241"),
    "Lacombe, AB":        ("lacombe",         "1700218"),
    "Ponoka, AB":         ("ponoka",          "1700232"),
    "Sylvan Lake, AB":    ("sylvan-lake",     "1700237"),
    "Innisfail, AB":      ("innisfail",       "1700215"),
    "Olds, AB":           ("olds",            "1700231"),
    "Didsbury, AB":       ("didsbury",        "1700204"),
    "Cochrane, AB":       ("cochrane",        "1700201"),
    "Airdrie, AB":        ("airdrie",         "1700198"),
    "Okotoks, AB":        ("okotoks",         "1700226"),
    "High River, AB":     ("high-river",      "1700212"),
    "Drumheller, AB":     ("drumheller",      "1700205"),
    "Stettler, AB":       ("stettler",        "1700236"),
    "Wainwright, AB":     ("wainwright",      "1700240"),
    "Saskatoon, SK":      ("saskatoon",       "1700197"),
    "Regina, SK":         ("regina",          "1700192"),
    "Prince Albert, SK":  ("prince-albert",   "1700187"),
    "Swift Current, SK":  ("swift-current",   "1700195"),
    "Kelowna, BC":        ("kelowna",         "1700228"),
    "Kamloops, BC":       ("kamloops",        "1700173"),
    "Moose Jaw, SK":      ("moose-jaw",       "1700184"),
    "Maple Creek, SK":    ("maple-creek",     "1700183"),
    "Spruce Grove, AB":   ("spruce-grove",    "1700235"),
    "Sherwood Park, AB":  ("sherwood-park",   "1700234"),
}

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
def parse_accident_flag(text):
    t = text.lower()
    for kw in ["salvage", "rebuilt title", "structural damage"]:
        if kw in t:
            return "Salvage/rebuilt"
    for kw in ["no accident", "clean carfax", "accident free", "0 accident",
                "zero accident", "no reported accident"]:
        if kw in t:
            return "No accidents reported"
    for kw in ["accident", "collision", "damage reported"]:
        if kw in t:
            return "Accident reported"
    return "Unknown"


def parse_seller_type(card):
    text = card.get_text().lower()
    badges = card.find_all(attrs={"data-testid": re.compile(r"dealer|pro", re.I)})
    if badges or "+ gst" in text or "dealer" in text:
        return "Dealer"
    return "Private"


def parse_price_history(card):
    strike = card.find("s")
    if strike:
        old = strike.get_text(strip=True)
        if "$" in old or any(c.isdigit() for c in old):
            return f"Reduced from {old}"
    return "No change noted"


def parse_days_on_market(card):
    time_el = card.find("time")
    if time_el:
        return time_el.get("datetime", time_el.get_text(strip=True))
    date_el = card.find(attrs={"data-testid": re.compile(r"date|posted|time", re.I)})
    if date_el:
        return date_el.get_text(strip=True)
    return "N/A"


# ─────────────────────────────────────────────
# Price trend tracking
# ─────────────────────────────────────────────
def load_price_history():
    path = f"data/{vehicle_key}/price_history_kijiji.json"
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_price_history(history):
    path = f"data/{vehicle_key}/price_history_kijiji.json"
    os.makedirs(f"data/{vehicle_key}", exist_ok=True)
    with open(path, "w") as f:
        json.dump(history, f, indent=2)


def apply_price_trends(ranked):
    history = load_price_history()
    today   = datetime.now().strftime("%Y-%m-%d")

    for v in ranked:
        lid   = v["listing_id"]
        price = v["price"]

        if lid not in history:
            history[lid] = []

        records = history[lid]

        if records:
            last_price         = records[-1]["price"]
            first_price        = records[0]["price"]
            weeks_tracked      = len(records)
            price_change_week  = price - last_price
            price_change_total = price - first_price
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

        records.append({"date": today, "price": price, "rank": v.get("score", 0)})
        history[lid] = records

    save_price_history(history)
    return ranked


# ─────────────────────────────────────────────
# Build Kijiji URL
# ─────────────────────────────────────────────
def build_kijiji_url(city, page=1):
    make_slug  = kijiji_make.lower().replace(" ", "-")
    model_slug = kijiji_model.lower().replace(" ", "-").replace("/", "-")
    loc_data   = KIJIJI_LOCATIONS.get(city)
    if loc_data:
        city_slug, loc_id = loc_data
    else:
        city_slug = city.lower().split(",")[0].strip().replace(" ", "-")
        loc_id    = "0"
    page_param = f"page-{page}/" if page > 1 else ""
    return (
        f"https://www.kijiji.ca/b-cars-trucks/{city_slug}/"
        f"{make_slug}-{model_slug}/"
        f"{page_param}k0c174l{loc_id}"
    )


# ─────────────────────────────────────────────
# Parse JSON-LD listings
# ─────────────────────────────────────────────
def parse_json_ld_listings(soup, search_city):
    listings = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
        except Exception:
            continue

        items = []
        if isinstance(data, dict):
            if data.get("@type") == "ItemList":
                for el in data.get("itemListElement", []):
                    item = el.get("item", {})
                    if item:
                        items.append(item)
            elif data.get("@type") in ("Car", "Vehicle"):
                items.append(data)
        elif isinstance(data, list):
            for el in data:
                if isinstance(el, dict) and el.get("@type") in ("Car", "Vehicle"):
                    items.append(el)

        for item in items:
            try:
                name        = item.get("name", "")
                url         = item.get("url", "")
                description = item.get("description", "")
                config_str  = item.get("vehicleConfiguration", "")

                listing_id = ""
                id_match = re.search(r"/(\d+)$", url)
                if id_match:
                    listing_id = id_match.group(1)

                price = 0
                try:
                    price = int(float(item.get("offers", {}).get("price", 0)))
                except (ValueError, TypeError):
                    pass

                year = 0
                try:
                    year = int(item.get("vehicleModelDate", 0))
                except (ValueError, TypeError):
                    m = re.search(r"\b(19|20)\d{2}\b", name)
                    if m:
                        year = int(m.group())

                mileage = 999999
                try:
                    mileage = int(float(item.get("mileageFromOdometer", {}).get("value", 999999)))
                except (ValueError, TypeError):
                    pass

                fuel_raw = item.get("vehicleEngine", {}).get("fuelType", "").lower()
                combined = f"{config_str} {name} {description} {fuel_raw}".lower()
                if "diesel" in combined:
                    fuel_type = "Diesel"
                elif "hybrid" in combined:
                    fuel_type = "Hybrid"
                elif "electric" in combined:
                    fuel_type = "Electric"
                else:
                    fuel_type = "Gas"

                engine_clean = "Unknown"
                eng_match = re.search(r"(\d+\.\d+)\s*[lL]", config_str + " " + name)
                if eng_match:
                    engine_clean = f"{eng_match.group(1)}L"

                trim_source = config_str if config_str else name
                trim_tier_val, trim_score = get_trim_tier(trim_source)
                trim_str = ""
                all_kws = (
                    trim_tiers.get("tier3", []) +
                    trim_tiers.get("tier2", []) +
                    trim_tiers.get("tier1", [])
                )
                for kw in all_kws:
                    if kw.lower() in trim_source.lower():
                        trim_str = kw
                        break
                if not trim_str:
                    trim_str = "Unknown"

                combined_text = f"{name} {description} {config_str}"
                accident_flag = parse_accident_flag(combined_text)

                listings.append({
                    "year":            year,
                    "make":            kijiji_make,
                    "model":           kijiji_model,
                    "trim":            trim_str,
                    "trim_tier":       trim_tier_val,
                    "trim_score":      trim_score,
                    "price":           price,
                    "price_history":   "No change noted",
                    "engine":          engine_clean,
                    "fuel":            fuel_type,
                    "mileage":         mileage,
                    "accident_flag":   accident_flag,
                    "days_on_market":  "N/A",
                    "dealer":          "Unknown",
                    "seller_type":     "Unknown",
                    "dealer_address":  search_city,
                    "location":        search_city,
                    "distance_km":     None,
                    "distance_method": None,
                    "listing_id":      listing_id,
                    "url":             url,
                    "source":          "Kijiji"
                })
            except Exception:
                continue
    return listings


def enrich_from_html(soup, listings_by_id):
    cards = soup.find_all(attrs={"data-listingid": True})
    for card in cards:
        lid = card.get("data-listingid", "")
        if lid in listings_by_id:
            listings_by_id[lid]["seller_type"]    = parse_seller_type(card)
            listings_by_id[lid]["price_history"]  = parse_price_history(card)
            listings_by_id[lid]["days_on_market"] = parse_days_on_market(card)
            dealer_el = card.find(attrs={"data-testid": re.compile(r"dealer|seller", re.I)})
            if dealer_el:
                listings_by_id[lid]["dealer"] = dealer_el.get_text(strip=True)
    return listings_by_id


# ─────────────────────────────────────────────
# Fetch listings
# ─────────────────────────────────────────────
def fetch_kijiji_listings():
    all_listings = []
    seen_ids     = set()
    hdrs = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-CA,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    for i, city in enumerate(search_locations):
        print(f"\n  [{i+1}/{len(search_locations)}] Kijiji — {city}...")
        new_count = 0
        page      = 1

        while True:
            url = build_kijiji_url(city, page)
            try:
                response = requests.get(url, headers=hdrs, timeout=15)
                if response.status_code in (403, 404):
                    print(f"    HTTP {response.status_code} — skipping")
                    break

                soup          = BeautifulSoup(response.text, "html.parser")
                page_listings = parse_json_ld_listings(soup, city)

                if not page_listings:
                    if page == 1:
                        print(f"    No JSON-LD listings found")
                    break

                listings_by_id = {l["listing_id"]: l for l in page_listings if l["listing_id"]}
                enrich_from_html(soup, listings_by_id)

                added = 0
                for listing in page_listings:
                    lid = listing["listing_id"]
                    if not lid or lid in seen_ids:
                        continue
                    seen_ids.add(lid)
                    all_listings.append(listing)
                    new_count += 1
                    added += 1

                if added == 0 or len(page_listings) < 10:
                    break

                page += 1
                time.sleep(2)

            except Exception as e:
                print(f"    Error on page {page}: {e}")
                break

        print(f"    +{new_count} new | Total: {len(all_listings)}")
        time.sleep(2)

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
    stats       = load_city_stats()
    candidates  = stats["candidates"]
    zero_weeks  = stats["zero_weeks"]
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

    cfg["search_locations"] = search_locations
    with open(args.config, "w") as f:
        json.dump(cfg, f, indent=2)

    stats["candidates"] = candidates
    stats["zero_weeks"] = zero_weeks
    save_city_stats(stats)

    print(f"\n  Location summary (Kijiji — {vehicle_key}):")
    print(f"    Active cities: {len(search_locations)}")


# ─────────────────────────────────────────────
# Display
# ─────────────────────────────────────────────
def display_results(ranked):
    display = ranked[:max_results]
    tier_labels = {1: "Base", 2: "Mid", 3: "Premium"}
    print(f"\n{'=' * 50}")
    print(f"  TOP {len(display)} KIJIJI RESULTS — {make} {model}")
    print(f"{'=' * 50}")
    for i, v in enumerate(display):
        mileage_str = f"{v['mileage']:,} km" if v["mileage"] != 999999 else "Unknown"
        print(f"\n  Rank {i+1}")
        print(f"  {v['year']} {v['make']} {v['model']} {v['trim']}")
        print(f"  Trim tier:  {tier_labels.get(v['trim_tier'], '?')} (Tier {v['trim_tier']})")
        print(f"  Price:      ${v['price']:,}  [{v['price_history']}]")
        print(f"  Mileage:    {mileage_str}")
        print(f"  Accidents:  {v['accident_flag']}")
        print(f"  Trend:      {v.get('trend', 'First seen this week')}")
        print(f"  Seller:     {v['dealer']} ({v['seller_type']})")
        print(f"  Location:   {v['location']}")
        print(f"  Distance:   {v['distance_km']} km ({v['distance_method']})")
        print(f"  Listed:     {v['days_on_market']}")
        print(f"  Score:      {round(v['score'], 4)}")
        print(f"  URL:        {v['url']}")


# ─────────────────────────────────────────────
# Save CSV
# ─────────────────────────────────────────────
def save_results(ranked):
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    os.makedirs(LATEST_DIR,  exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename  = f"{ARCHIVE_DIR}/{vehicle_key}_kijiji_{timestamp}.csv"

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
    print("=" * 50)
    print(f"KIJIJI SCRAPER — {make} {model}")
    print("=" * 50)
    print(f"  Years:        {min_year} – {max_year}")
    print(f"  Max price:    ${max_price:,}")
    print(f"  Fuel:         {fuel}")
    print(f"  Cities:       {len(search_locations)}")
    print("=" * 50)

    print("\nFetching listings from Kijiji...")
    listings = fetch_kijiji_listings()
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
