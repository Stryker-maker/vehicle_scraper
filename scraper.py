import requests
import json
import csv
import time
import os
from datetime import datetime
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# ─────────────────────────────────────────────
# Load config
# ─────────────────────────────────────────────
with open("config.json", "r") as f:
    cfg = json.load(f)

make             = cfg["make"]
model            = cfg["model"]
min_year         = cfg["min_year"]
max_year         = cfg["max_year"]
max_price        = cfg["max_price"]
fuel             = cfg["fuel"]
engine           = cfg["engine"]
home_city        = cfg["home_city"]
home_coords      = tuple(cfg["home_coords"])
max_distance_km  = cfg["max_distance_km"]
max_results      = cfg["max_results"]
search_locations = cfg["search_locations"]
weights          = cfg["ranking_weights"]

# ─────────────────────────────────────────────
# OpenRouteService setup
# ─────────────────────────────────────────────
ORS_API_KEY = os.environ.get("ORS_API_KEY", "")
ORS_URL     = "https://api.openrouteservice.org/v2/directions/driving-car"

# ─────────────────────────────────────────────
# Geocoder setup
# ─────────────────────────────────────────────
geolocator        = Nominatim(user_agent="vehicle_scraper_tool")
city_coords_cache = {}
drive_dist_cache  = {}


def get_city_coords(city_name):
    """Return (lat, lon) for a city name, cached."""
    if city_name in city_coords_cache:
        return city_coords_cache[city_name]
    try:
        time.sleep(1)  # Nominatim rate limit
        location = geolocator.geocode(city_name + ", Canada")
        if location:
            coords = (location.latitude, location.longitude)
            city_coords_cache[city_name] = coords
            return coords
    except Exception as e:
        print(f"    [geocode error] {city_name}: {e}")
    return None


def get_address_coords(address):
    """Return (lat, lon) for a full street address."""
    try:
        time.sleep(1)
        location = geolocator.geocode(address)
        if location:
            return (location.latitude, location.longitude)
    except Exception as e:
        print(f"    [address geocode error] {address}: {e}")
    return None


def get_driving_distance_km(dest_coords):
    """
    Return driving distance in km from home_coords to dest_coords
    using OpenRouteService. Falls back to straight-line if API fails.
    """
    if not ORS_API_KEY:
        return round(geodesic(home_coords, dest_coords).km)

    cache_key = f"{dest_coords[0]:.4f},{dest_coords[1]:.4f}"
    if cache_key in drive_dist_cache:
        return drive_dist_cache[cache_key]

    try:
        # ORS expects [longitude, latitude]
        payload = {
            "coordinates": [
                [home_coords[1], home_coords[0]],
                [dest_coords[1], dest_coords[0]]
            ]
        }
        headers = {
            "Authorization": ORS_API_KEY,
            "Content-Type": "application/json"
        }
        response = requests.post(ORS_URL, json=payload, headers=headers, timeout=10)
        data = response.json()
        distance_m = data["routes"][0]["summary"]["distance"]
        distance_km = round(distance_m / 1000)
        drive_dist_cache[cache_key] = distance_km
        time.sleep(0.5)  # gentle rate limiting
        return distance_km
    except Exception as e:
        print(f"    [ORS error] falling back to straight-line: {e}")
        return round(geodesic(home_coords, dest_coords).km)


def resolve_distance(listing):
    """
    Attempt to resolve driving distance using:
    1. Dealer street address (if available)
    2. Listing city center
    3. Closest search_location city center (fallback)
    Returns (distance_km, method_used)
    """
    # Try dealer address first
    address = listing.get("dealer_address", "")
    if address and len(address) > 5:
        coords = get_address_coords(address)
        if coords:
            return get_driving_distance_km(coords), "address"

    # Try listing city
    city = listing.get("location", "")
    if city:
        coords = get_city_coords(city)
        if coords:
            return get_driving_distance_km(coords), "city_center"

    # Fallback: find closest search_location to listing city
    best_dist = 9999
    best_city = None
    listing_coords = get_city_coords(city) if city else None
    if listing_coords:
        for loc in search_locations:
            loc_coords = get_city_coords(loc)
            if loc_coords:
                d = geodesic(listing_coords, loc_coords).km
                if d < best_dist:
                    best_dist = d
                    best_city = loc
    if best_city:
        coords = get_city_coords(best_city)
        if coords:
            return get_driving_distance_km(coords), f"nearest_city ({best_city})"

    return 9999, "unknown"


# ─────────────────────────────────────────────
# Search summary
# ─────────────────────────────────────────────
def search_summary():
    print("=" * 50)
    print("VEHICLE SCRAPER - Search Parameters")
    print("=" * 50)
    print(f"  Vehicle:      {make} {model}")
    print(f"  Years:        {min_year} – {max_year}")
    print(f"  Max price:    ${max_price:,}")
    print(f"  Fuel:         {fuel}")
    print(f"  Engine:       {engine}")
    print(f"  Home base:    {home_city}")
    print(f"  Max distance: {max_distance_km} km (driving)")
    print(f"  Cities:       {len(search_locations)}")
    print(f"  Max results:  {max_results}")
    print(f"  Ranking:      Price {int(weights['price']*100)}% | "
          f"Mileage {int(weights['mileage']*100)}% | "
          f"Distance {int(weights['distance']*100)}%")
    print("=" * 50)


# ─────────────────────────────────────────────
# Fetch listings from AutoTrader
# ─────────────────────────────────────────────
def fetch_autotrader_listings():
    all_listings = []
    seen_ids     = set()
    headers      = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    for i, city in enumerate(search_locations):
        city_encoded = city.replace(" ", "%20").replace(",", "%2C")
        url = (
            f"https://www.autotrader.ca/cars/ford/f-350/"
            f"?rcp=100&rcs=0&srt=35&loc={city_encoded}"
            f"&fuel=Diesel&hprc=True&wcp=True"
            f"&inMarket=advancedSearch&sts=New-Used&prx=100"
        )
        print(f"\n  [{i+1}/{len(search_locations)}] Searching {city}...")

        try:
            response = requests.get(url, headers=headers, timeout=15)
            soup     = BeautifulSoup(response.text, "html.parser")
            scripts  = soup.find_all("script")

            data = None
            for script in scripts:
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
                    engine_clean = (
                        "6.7L"
                        if "6,700" in str(engine_raw) or "6700" in str(engine_raw)
                        else str(engine_raw)
                    )

                    # Mileage
                    mileage = item["vehicle"].get("mileageInKm", None)
                    if mileage is None:
                        mileage = 999999  # unknown mileage ranked last

                    # Fuel
                    fuel_type = item["vehicle"].get("fuel", "")

                    # Year
                    year = item["vehicle"].get("modelYear", 0)
                    try:
                        year = int(year)
                    except Exception:
                        year = 0

                    # Location
                    loc_city     = item.get("location", {}).get("city", "")
                    loc_province = item.get("location", {}).get("provinceCode", "")
                    listing_city = f"{loc_city}, {loc_province}".strip(", ")

                    # Dealer info
                    dealer_name    = item.get("seller", {}).get("companyName", "Unknown")
                    dealer_address = item.get("seller", {}).get("address", "")

                    # Build URL
                    autotrader_url = (
                        f"https://www.autotrader.ca/a/ford/f-350/{listing_id}/"
                    )

                    listing = {
                        "year":           year,
                        "make":           item["vehicle"].get("make", make),
                        "model":          item["vehicle"].get("model", model),
                        "trim":           item["vehicle"].get("modelVersionInput", "Unknown"),
                        "price":          price_clean,
                        "engine":         engine_clean,
                        "fuel":           fuel_type,
                        "mileage":        mileage,
                        "dealer":         dealer_name,
                        "dealer_address": dealer_address,
                        "location":       listing_city,
                        "distance_km":    None,   # resolved after fetch
                        "distance_method": None,
                        "listing_id":     listing_id,
                        "url":            autotrader_url
                    }
                    all_listings.append(listing)
                    new_count += 1

                except Exception:
                    continue

            print(f"    +{new_count} new unique listings | Total: {len(all_listings)}")
            time.sleep(1.5)

        except Exception as e:
            print(f"    Error: {e}")
            continue

    return all_listings


# ─────────────────────────────────────────────
# Resolve driving distances
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
# Filter listings
# ─────────────────────────────────────────────
def filter_listings(listings):
    matches = []
    for v in listings:
        if (
            v["engine"]      == "6.7L"         and
            v["fuel"]        == "Diesel"        and
            v["price"]        > 0               and
            v["price"]       <= max_price       and
            v["year"]        >= min_year        and
            v["year"]        <= max_year        and
            v["distance_km"] <= max_distance_km
        ):
            matches.append(v)
    return matches


# ─────────────────────────────────────────────
# Rank listings
# ─────────────────────────────────────────────
def rank_listings(matches):
    pw = weights["price"]
    mw = weights["mileage"]
    dw = weights["distance"]

    max_price_val    = max(v["price"]        for v in matches)
    max_mileage_val  = max(v["mileage"]      for v in matches)
    max_distance_val = max(v["distance_km"]  for v in matches)

    for v in matches:
        price_score    = v["price"]       / max_price_val    if max_price_val    > 0 else 0
        mileage_score  = v["mileage"]     / max_mileage_val  if max_mileage_val  > 0 else 0
        distance_score = v["distance_km"] / max_distance_val if max_distance_val > 0 else 0
        v["score"] = (
            (price_score    * pw) +
            (mileage_score  * mw) +
            (distance_score * dw)
        )

    matches.sort(key=lambda v: v["score"])
    return matches


# ─────────────────────────────────────────────
# Display results
# ─────────────────────────────────────────────
def display_results(ranked):
    display = ranked[:max_results]
    print(f"\n{'=' * 50}")
    print(f"  TOP {len(display)} RANKED RESULTS")
    print(f"{'=' * 50}")
    for i, v in enumerate(display):
        mileage_display = (
            f"{v['mileage']:,} km"
            if v["mileage"] != 999999
            else "Unknown"
        )
        print(f"\n  Rank {i+1}")
        print(f"  {v['year']} {v['make']} {v['model']} {v['trim']}")
        print(f"  Price:     ${v['price']:,}")
        print(f"  Mileage:   {mileage_display}")
        print(f"  Dealer:    {v['dealer']}")
        print(f"  Location:  {v['location']}")
        print(f"  Distance:  {v['distance_km']} km driving ({v['distance_method']})")
        print(f"  Score:     {round(v['score'], 4)}")
        print(f"  URL:       {v['url']}")


# ─────────────────────────────────────────────
# Save results to CSV
# ─────────────────────────────────────────────
def save_results(ranked):
    os.makedirs("data", exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename  = f"data/f350_results_{timestamp}.csv"

    fields = [
        "rank", "year", "make", "model", "trim",
        "price", "mileage", "engine", "fuel",
        "dealer", "dealer_address", "location",
        "distance_km", "distance_method",
        "listing_id", "url", "score"
    ]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for i, v in enumerate(ranked[:max_results]):
            row          = {field: v.get(field, "") for field in fields}
            row["rank"]  = i + 1
            row["mileage"] = (
                v["mileage"] if v["mileage"] != 999999 else "Unknown"
            )
            writer.writerow(row)

    print(f"\n  Results saved to: {filename}")
    return filename


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
if __name__ == "__main__":
    search_summary()

    print("\nFetching live listings from AutoTrader...")
    listings = fetch_autotrader_listings()
    print(f"\nRaw listings retrieved: {len(listings)}")

    listings = resolve_all_distances(listings)

    matches = filter_listings(listings)
    print(f"Matches after filtering: {len(matches)}")

    if matches:
        ranked = rank_listings(matches)
        display_results(ranked)
        save_results(ranked)
    else:
        print("\nNo vehicles matched your criteria.")
