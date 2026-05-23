"""
Kijiji diagnostic script.
Fetches one search page and prints the raw HTML structure
so we can identify the correct listing selectors.
"""
import requests
import json
import re
from bs4 import BeautifulSoup

hdrs = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-CA,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

url = "https://www.kijiji.ca/b-cars-trucks/calgary/ford-f-350/k0c174l1700199"
print(f"Fetching: {url}")
response = requests.get(url, headers=hdrs, timeout=15)
print(f"Status code: {response.status_code}")
print(f"Response length: {len(response.text)} chars")

soup = BeautifulSoup(response.text, "html.parser")

# ── Check for JSON-LD structured data ─────────────────────────────────
print("\n=== JSON-LD SCRIPTS ===")
json_ld_count = 0
for script in soup.find_all("script", type="application/ld+json"):
    try:
        data = json.loads(script.string)
        print(json.dumps(data, indent=2)[:2000])
        json_ld_count += 1
        if json_ld_count >= 2:
            break
    except Exception:
        continue
if json_ld_count == 0:
    print("None found")

# ── Check for __NEXT_DATA__ or similar embedded JSON ──────────────────
print("\n=== EMBEDDED JSON (__NEXT_DATA__ / window.__data__) ===")
for script in soup.find_all("script"):
    if script.string and ("__NEXT_DATA__" in script.string or
                          "__INITIAL_STATE__" in script.string or
                          '"listings"' in script.string or
                          '"adId"' in script.string):
        print("Found embedded JSON script tag:")
        print(script.string[:3000])
        break
else:
    print("None found")

# ── Check what top-level tags/classes exist ───────────────────────────
print("\n=== ALL DATA-* ATTRIBUTES ON PAGE (first 20) ===")
data_attrs = []
for tag in soup.find_all(True):
    for attr in tag.attrs:
        if attr.startswith("data-") and attr not in data_attrs:
            data_attrs.append(attr)
for a in data_attrs[:20]:
    print(f"  {a}")

# ── Try common Kijiji listing containers ──────────────────────────────
print("\n=== LISTING CONTAINER SEARCH ===")
selectors = [
    ("li", {"data-listing-id": True}),
    ("div", {"data-listing-id": True}),
    ("li", {"data-ad-id": True}),
    ("article", {}),
    ("li", re.compile(r"regular-ad|search-item|listing", re.I)),
    ("div", re.compile(r"regular-ad|search-item|listing-card", re.I)),
]
for tag, attrs in selectors:
    if isinstance(attrs, dict):
        found = soup.find_all(tag, attrs=attrs)
    else:
        found = soup.find_all(tag, class_=attrs)
    if found:
        print(f"  FOUND: <{tag}> with {attrs} — {len(found)} items")
        print("  First item snippet:")
        print(str(found[0])[:1000])
        break
else:
    print("  No common listing containers found")

# ── Print page title and first 2000 chars of body text ────────────────
print("\n=== PAGE TITLE ===")
print(soup.title.string if soup.title else "No title")

print("\n=== BODY TEXT SAMPLE (first 1000 chars) ===")
body = soup.find("body")
if body:
    print(body.get_text()[:1000])
