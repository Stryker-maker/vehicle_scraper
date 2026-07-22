"""
LEGACY / DISABLED: historical cross-source merger and ranker.

This script is not called by the supported GitHub Actions workflow and must not
be used to create current recommendations. Its duplicate logic treats
source-specific listing IDs as though they could be VINs, applies broad
price/mileage tolerances, fills fields across sources without an approved
evidence model, and re-sorts by the disabled legacy score.

It is retained only for audit history until Audit 06 replaces identity,
deduplication, and listing-lifecycle behaviour. See
`docs/LEGACY_COMPONENTS.md` and use the current manual-review CSV instead.
"""
import argparse
import csv
import json
import os
from datetime import datetime

parser = argparse.ArgumentParser()
parser.add_argument("--config", required=True)
args = parser.parse_args()

with open(args.config, "r") as f:
    cfg = json.load(f)

vehicle_key = cfg["vehicle_key"]
make        = cfg["make"]
model       = cfg["model"]

LATEST_DIR  = f"data/{vehicle_key}/latest"
MERGED_DIR  = f"data/{vehicle_key}/merged"
AT_LATEST   = f"{LATEST_DIR}/{vehicle_key}_autotrader_latest.csv"
KJ_LATEST   = f"{LATEST_DIR}/{vehicle_key}_kijiji_latest.csv"

# Duplicate match tolerances
PRICE_TOLERANCE   = 100    # within $100
MILEAGE_TOLERANCE = 1000   # within 1,000 km

MERGED_FIELDS = [
    "rank", "year", "make", "model", "trim", "trim_tier",
    "price", "price_history", "trend",
    "weeks_tracked", "price_first_seen", "price_last_week",
    "price_change_week", "price_change_total",
    "mileage", "engine", "fuel",
    "accident_flag", "days_on_market",
    "dealer", "seller_type", "dealer_address", "location",
    "distance_km", "distance_method",
    "listing_id", "url", "score", "source",
    "duplicate_flag", "kijiji_url", "kijiji_price", "kijiji_seller_type"
]


def load_csv(path):
    if not os.path.exists(path):
        print(f"  File not found: {path}")
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def safe_int(val, default=0):
    try:
        return int(str(val).replace(",", "").replace("$", "").strip())
    except (ValueError, TypeError):
        return default


def is_probable_duplicate(at_row, kj_row):
    """
    Match by VIN if available, otherwise by year + price within $100
    + mileage within 1,000 km.
    """
    # VIN match
    at_vin = at_row.get("listing_id", "")
    kj_vin = kj_row.get("listing_id", "")
    if at_vin and kj_vin and at_vin == kj_vin:
        return True

    # Year must match exactly
    if safe_int(at_row.get("year")) != safe_int(kj_row.get("year")):
        return False

    # Price within tolerance
    at_price = safe_int(at_row.get("price"))
    kj_price = safe_int(kj_row.get("price"))
    if abs(at_price - kj_price) > PRICE_TOLERANCE:
        return False

    # Mileage within tolerance
    at_mile = safe_int(at_row.get("mileage"), default=999999)
    kj_mile = safe_int(kj_row.get("mileage"), default=999999)
    if at_mile == 999999 or kj_mile == 999999:
        return False
    if abs(at_mile - kj_mile) > MILEAGE_TOLERANCE:
        return False

    return True


def merge(at_rows, kj_rows):
    """
    AutoTrader is the base record.
    Kijiji fills gaps and provides seller_type + duplicate flag.
    All unmatched Kijiji rows are appended at the end.
    """
    merged        = []
    matched_kj_ids = set()

    for at_row in at_rows:
        row = dict(at_row)
        row["duplicate_flag"]      = "No"
        row["kijiji_url"]          = ""
        row["kijiji_price"]        = ""
        row["kijiji_seller_type"]  = ""

        for kj_row in kj_rows:
            kj_id = kj_row.get("listing_id", "")
            if kj_id in matched_kj_ids:
                continue
            if is_probable_duplicate(at_row, kj_row):
                matched_kj_ids.add(kj_id)
                row["duplicate_flag"]     = "Yes — also on Kijiji"
                row["kijiji_url"]         = kj_row.get("url", "")
                row["kijiji_price"]       = kj_row.get("price", "")
                row["kijiji_seller_type"] = kj_row.get("seller_type", "")

                # Fill gaps from Kijiji
                if not row.get("seller_type") or row["seller_type"] == "Dealer":
                    if kj_row.get("seller_type") in ("Private", "Dealer"):
                        row["seller_type"] = kj_row["seller_type"]
                if row.get("accident_flag") == "Unknown" and kj_row.get("accident_flag") != "Unknown":
                    row["accident_flag"] = kj_row["accident_flag"]
                if row.get("days_on_market") == "N/A" and kj_row.get("days_on_market") != "N/A":
                    row["days_on_market"] = kj_row["days_on_market"]

                # Note price difference
                at_price = safe_int(at_row.get("price"))
                kj_price = safe_int(kj_row.get("price"))
                diff = kj_price - at_price
                if diff != 0:
                    direction = "cheaper" if diff < 0 else "more expensive"
                    row["duplicate_flag"] += f" (${abs(diff):,} {direction} on Kijiji)"
                break

        merged.append(row)

    # Append unmatched Kijiji listings
    for kj_row in kj_rows:
        kj_id = kj_row.get("listing_id", "")
        if kj_id not in matched_kj_ids:
            row = dict(kj_row)
            row["duplicate_flag"]     = "No"
            row["kijiji_url"]         = ""
            row["kijiji_price"]       = ""
            row["kijiji_seller_type"] = ""
            merged.append(row)

    # Re-rank by score
    merged.sort(key=lambda r: float(r.get("score", 1)))
    for i, row in enumerate(merged):
        row["rank"] = i + 1

    return merged


def save_merged(merged):
    os.makedirs(MERGED_DIR, exist_ok=True)
    timestamp     = datetime.now().strftime("%Y-%m-%d_%H-%M")
    archive_file  = f"{MERGED_DIR}/{vehicle_key}_merged_{timestamp}.csv"
    latest_file   = f"{LATEST_DIR}/{vehicle_key}_merged_latest.csv"

    for path in [archive_file, latest_file]:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=MERGED_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(merged)

    print(f"  Archived: {archive_file}")
    print(f"  Latest:   {latest_file}")
    return archive_file


if __name__ == "__main__":
    print("=" * 50)
    print(f"MERGER — {make} {model}")
    print("=" * 50)

    at_rows = load_csv(AT_LATEST)
    kj_rows = load_csv(KJ_LATEST)

    print(f"  AutoTrader listings: {len(at_rows)}")
    print(f"  Kijiji listings:     {len(kj_rows)}")

    if not at_rows and not kj_rows:
        print("  No data to merge — skipping.")
    else:
        merged = merge(at_rows, kj_rows)
        duplicates = [r for r in merged if r.get("duplicate_flag", "No") != "No"]
        print(f"  Total merged rows:   {len(merged)}")
        print(f"  Duplicates found:    {len(duplicates)}")
        if duplicates:
            print("  Duplicate listings:")
            for r in duplicates:
                print(f"    {r['year']} {r['make']} {r['model']} "
                      f"${safe_int(r['price']):,} — {r['duplicate_flag']}")
        save_merged(merged)
        print("\nMerge complete.")