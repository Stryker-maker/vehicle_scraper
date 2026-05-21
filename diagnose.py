import requests
import json
import time
from bs4 import BeautifulSoup

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

url = (
    "https://www.autotrader.ca/cars/ford/f-350/"
    "?rcp=5&rcs=0&srt=35&loc=Red%20Deer%2C%20AB"
    "&fuel=Diesel&hprc=True&wcp=True"
    "&inMarket=advancedSearch&sts=New-Used&prx=100"
)

print("Fetching sample listing...")
response = requests.get(url, headers=headers, timeout=15)
soup = BeautifulSoup(response.text, "html.parser")
scripts = soup.find_all("script")

data = None
for script in scripts:
    if script.string and '"listings"' in script.string:
        try:
            data = json.loads(script.string)
            break
        except Exception:
            continue

if not data:
    print("No data found")
    exit()

listings = data.get("props", {}).get("pageProps", {}).get("listings", [])
if not listings:
    print("No listings found")
    exit()

# Print full raw data of first listing
item = listings[0]
print("\n=== FULL LISTING JSON ===")
print(json.dumps(item, indent=2))

print("\n=== VEHICLE FIELDS ===")
print(json.dumps(item.get("vehicle", {}), indent=2))

print("\n=== SELLER FIELDS ===")
print(json.dumps(item.get("seller", {}), indent=2))

print("\n=== LOCATION FIELDS ===")
print(json.dumps(item.get("location", {}), indent=2))
