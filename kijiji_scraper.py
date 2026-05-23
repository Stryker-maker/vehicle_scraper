"""
Kijiji Vehicle Scraper
Supports multiple vehicles via config files.
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
CITY_STATS_FILE     = f"data/city_stats_kijiji_{vehicle_key}.json"

# ─────────────────────────────────────────────
# Kijiji location mapping
# Cities map to Kijiji's location URL slugs
# ─────────────────────────────────────────────
KIJIJI_LOCATION_MAP = {
    "Red Deer, AB":        "red-deer",
    "Edmonton, AB":        "edmonton",
    "Calgary, AB":         "calgary",
    "Lethbridge, AB":      "lethbridge",
    "Medicine Hat, AB":    "medicine-hat",
    "Grande Prairie, AB":  "grande-prairie",
    "Fort McMurray, AB":   "fort-mcmurray",
    "Lloydminster, AB":    "lloydminster",
    "Camrose, AB":         "camrose",
    "Wetaskiwin, AB":      "wetaskiwin",
    "Lacombe, AB":         "lacombe",
    "Ponoka, AB":          "ponoka",
    "Sylvan Lake, AB":     "sylvan-lake",
    "Innisfail, AB":       "innisfail",
    "Olds, AB":            "olds",
    "Didsbury, AB":        "didsbury",
    "Cochrane, AB":        "cochrane",
    "Airdrie, AB":         "airdrie",
    "Okotoks, AB":         "okotoks",
    "High River, AB":      "high-river",
    "Drumheller, AB":      "drumheller",
    "Stettler, AB":        "stettler",
    "Wainwright, AB":      "wainwright",
    "Saskatoon, SK":       "saskatoon",
    "Regina, SK":          "regina",
    "Prince Albert, SK":   "prince-albert",
    "Swift Current, SK":   "swift-current",
    "Kelowna, BC":         "kelowna",
    "Kamloops, BC":        "kamloops",
    "Moose Jaw, SK":       "moose-jaw",
    "Maple Creek, SK":     "maple-creek",
    "Spruce Grove, AB":    "spruce-grove",
    "Sherwood Park, AB":   "sherwood-park",
}

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
# Kijiji helpers
# ─────────────────────────────────────────────
def parse_kijiji_price(text):
    """Extract integer price from Kijiji price string."""
    if not text:
        return 0
    cleaned = re.sub(r"[^\d]", "", text)
    try:
        return int(cleaned)
    except ValueError:
        return 0


def parse_kijiji_mileage(text):
    """Extract integer mileage from Kijiji mileage string."""
    if not text:
        return 999999
    cleaned = re.sub(r"[^\d]", "", text)
    try:
        return int(cleaned)
    except ValueError:
        return 999999


def parse_kijiji_year(text):
    """Extract 4-digit year from title or year field."""
    if not text:
        return 0
    match = re.search(r"\b(19|20)\d{2}\b", text)
    if match:
        return int(match.group())
    return 0


def parse_seller_type(soup_item):
    """Return 'Dealer' or 'Private' based on listing badge."""
    badges = soup_item.find_all(class_=re.compile(r"dealer|professional", re.I))
    if badges:
        return "Dealer"
    dealer_logo = soup_item.find(class_=re.compile(r"dealerLogo|dealer-logo", re.I))
    if dealer_logo:
        return "Dealer"
    return "Private"


def parse_days_on_market_kijiji(soup_item):
    """Extract listing date and calculate days on market."""
    date_el = soup_item.find(class_=re.compile(r"date|posted|listing-date", re.I))
    if not date_el:
        date_el = soup_item.find("time")
    if date_el:
        return date_el.get_text(strip=True)
    return "N/A"


def parse_accident_flag_kijiji(title, description):
    """Scan title and description for accident/salvage/clean keywords."""
    combined = f"{title} {description}".lower()
    salvage_kw = ["salvage", "rebuilt title", "rebuilt status", "structural damage"]
    accident_kw = ["accident", "collision", "damage reported"]
    clean_kw = ["no accident", "clean carfax", "accident free", "0 accident",
                 "zero accident", "no reported accident", "carfax clean"]
    for kw in salvage_kw:
        if kw in combined:
            return "Salvage/rebuilt"
    for kw in clean_kw:
        if kw in combined:
            return "No accidents reported"
    for kw in accident_kw:
        if kw in combined:
            return "Accident reported"
    return "Unknown"


def parse_price_history_kijiji(soup_item):
    """Check for strikethrough/original price indicating a reduction."""
    strike = soup_item.find("s")
    if strike:
        old = strike.get_text(strip=True)
        if "$" in old or any(c.isdigit() for c in old):
            return f"Reduced from {old}"
    return "No change noted"


# ─────────────────────────────────────────────
# Fetch Kijiji listings
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

    make_slug  = kijiji_make.lower().replace(" ", "-")
    model_slug = kijiji_model.lower().replace(" ", "-").replace("/", "-")

    for i, city in enumerate(search_locations):
        location_slug = KIJIJI_LOCATION_MAP.get(city, city.lower().split(",")[0].strip().replace(" ", "-"))

        url = (
            f"https://www.kijiji.ca/b-cars-trucks/{location_slug}/"
            f"{make_slug}-{model_slug}/"
            f"k0c174l0?ll={home_coords[0]},{home_coords[1]}"
            f"&radius=100"
            f"&price=0__{max_price}"
            f"&minyear={min_year}&maxyear={max_year}"
        )

        print(f"\n  [{i+1}/{len(search_locations)}] Kijiji — {city}...")

        try:
            response = requests.get(url, headers=hdrs, timeout=15)
            if response.status_code == 403:
                print(f"    Blocked (403) — skipping")
                time.sleep(3)
                continue

            soup = BeautifulSoup(response.text, "html.parser")

            # Try JSON-LD structured data first
            json_ld_listings = []
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        json_ld_listings.extend(data)
                    elif isinstance(data, dict):
                        json_ld_listings.append(data)
                except Exception:
                    continue

            # Fall back to HTML parsing
            items = soup.find_all("li", class_=re.compile(r"regular-ad|search-item", re.I))
            if not items:
                items = soup.find_all("div", attrs={"data-listing-id": True})

            new_count = 0
            for item in items:
                try:
                    # Listing ID
                    listing_id = (
                        item.get("data-listing-id") or
                        item.get("data-ad-id") or
                        ""
                    )
                    if not listing_id:
                        link = item.find("a", href=re.compile(r"/v-"))
                        if link:
                            id_match = re.search(r"(\d{10,})", link.get("href", ""))
                            if id_match:
                                listing_id = id_match.group(1)
                    if not listing_id or listing_id in seen_ids:
                        continue
                    seen_ids.add(listing_id)

                    # Title
                    title_el = (
                        item.find(class_=re.compile(r"title|listing-title", re.I)) or
                        item.find("a", class_=re.compile(r"title", re.I))
                    )
                    title = title_el.get_text(strip=True) if title_el else ""

                    # URL
                    link_el = item.find("a", href=re.compile(r"/v-"))
                    item_url = ""
                    if link_el:
                        href = link_el.get("href", "")
                        item_url = f"https://www.kijiji.ca{href}" if href.startswith("/") else href

                    # Price
                    price_el = item.find(class_=re.compile(r"price", re.I))
                    price = parse_kijiji_price(price_el.get_text() if price_el else "0")

                    # Year from title
                    year = parse_kijiji_year(title)

                    # Mileage
                    mileage_el = item.find(text=re.compile(r"\d[\d,]* km", re.I))
                    mileage = parse_kijiji_mileage(str(mileage_el) if mileage_el else "")

                    # Location
                    loc_el = item.find(class_=re.compile(r"location|address", re.I))
                    location_text = loc_el.get_text(strip=True) if loc_el else city

                    # Description snippet
                    desc_el = item.find(class_=re.compile(r"description|snippet", re.I))
                    description = desc_el.get_text(strip=True) if desc_el else ""

                    # Seller type
                    seller_type = parse_seller_type(item)

                    # Trim — extract from title
                    trim_str = ""
                    title_lower = title.lower()
                    all_trims = (
                        trim_tiers.get("tier3", []) +
                        trim_tiers.get("tier2", []) +
                        trim_tiers.get("tier1", [])
                    )
                    for t in all_trims:
                        if t.lower() in title_lower:
                            trim_str = t
                            break
                    trim_tier_val, trim_score = get_trim_tier(trim_str or title)

                    # Enrichment
                    accident_flag  = parse_accident_flag_kijiji(title, description)
                    price_history  = parse_price_history_kijiji(item)
                    days_on_market = parse_days_on_market_kijiji(item)

                    # Fuel check from title/description
                    fuel_found = ""
                    combined_text = f"{title} {description}".lower()
                    if "diesel" in combined_text:
                        fuel_found = "Diesel"
                    elif "hybrid" in combined_text:
                        fuel_found = "Hybrid"
                    elif "electric" in combined_text or " ev " in combined_text:
                        fuel_found = "Electric"
                    else:
                        fuel_found = "Gas"

                    listing = {
                        "year":            year,
                        "make":            kijiji_make,
                        "model":           kijiji_model,
                        "trim":            trim_str or "Unknown",
                        "trim_tier":       trim_tier_val,
                        "trim_score":      trim_score,
                        "price":           price,
                        "price_history":   price_history,
                        "engine":          "Unknown",
                        "fuel":            fuel_found,
                        "mileage":         mileage,
                        "accident_flag":   accident_flag,
                        "days_on_market":  days_on_market,
                        "dealer":          "Private Seller" if seller_type == "Private" else "Dealer",
                        "seller_type":     seller_type,
                        "dealer_address":  location_text,
                        "location":        location_text,
                        "distance_km":     None,
                        "distance_method": None,
                        "listing_id":      listing_id,
                        "url":             item_url,
                        "source":          "Kijiji"
                    }
                    all_listings.append(listing)
                    new_count += 1

                except Exception:
                    continue

            print(f"    +{new_count} new | Total: {len(all_listings)}")
            time.sleep(2)  # Kijiji needs slightly longer delay

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

        if year_ok and price_ok and dist_ok and fuel_ok:
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

    for city, count in list(candidates.items()):
        if count >= CANDIDATE_THRESHOLD:
            coords = get_city_coords(city)
            if coords:
                dist = get_driving_distance_km(coords)
                if dist <= max_distance_km:
                    search_locations.append(city)
                    normalized_search.add(city)
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


# ─────────────────────────────────────────────
# Display
# ─────────────────────────────────────────────
def display_results(ranked):
    display = ranked[:max_results]
    print(f"\n{'=' * 50}")
    print(f"  TOP {len(display)} KIJIJI RESULTS — {make} {model}")
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
        print(f"  Seller:        {v['dealer']} ({v['seller_type']})")
        print(f"  Location:      {v['location']}")
        print(f"  Distance:      {v['distance_km']} km ({v['distance_method']})")
        print(f"  Listed:        {v['days_on_market']}")
        print(f"  Score:         {round(v['score'], 4)}")
        print(f"  URL:           {v['url']}")


# ─────────────────────────────────────────────
# Save CSV
# ─────────────────────────────────────────────
def save_results(ranked):
    os.makedirs("data", exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename  = f"data/{vehicle_key}_kijiji_{timestamp}.csv"

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
        display_results(ranked)
        save_results(ranked)
    else:
        print("\nNo matches found.")

    print("\nUpdating location list...")
    update_locations(matches)
