from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase1_common import SOURCE_FIELDS, write_json

EXTRA_FIELDS = [
    "distance_evidence_status", "query_location", "query_page",
    "query_offset", "request_url",
]


def load_trim_tiers(root: Path, vehicle_key: str) -> dict[str, list[str]]:
    path = root / "trim_tiers.json"
    if not path.exists():
        return {"tier3": [], "tier2": [], "tier1": []}
    value = json.loads(path.read_text(encoding="utf-8"))
    tiers = value.get(vehicle_key, {}) if isinstance(value, dict) else {}
    return {name: list(tiers.get(name, [])) for name in ("tier3", "tier2", "tier1")}


def apply_price_history(root: Path, config: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    path = root / "data" / str(config["vehicle_key"]) / "price_history_autotrader.json"
    try:
        history = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError, json.JSONDecodeError):
        history = {}
    if not isinstance(history, dict):
        history = {}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for row in rows:
        records = history.setdefault(str(row["listing_id"]), [])
        if not isinstance(records, list):
            records = []
            history[str(row["listing_id"])] = records
        first = records[0].get("price") if records else row["price"]
        previous = records[-1].get("price") if records else row["price"]
        count = len(records)
        row.update(
            weeks_tracked=count,
            price_first_seen=first,
            price_last_week=previous,
            price_change_week=row["price"] - previous,
            price_change_total=row["price"] - first,
        )
        change = row["price_change_total"]
        row["trend"] = (
            "First observed this run" if not records
            else f"Down ${abs(change):,} over {count} observations" if change < 0
            else f"Up ${change:,} over {count} observations" if change > 0
            else f"Unchanged for {count} observations"
        )
        records.append({"date": today, "price": row["price"]})
    write_json(path, history)


def write_csv_outputs(root: Path, config: dict[str, Any], rows: list[dict[str, Any]]) -> tuple[Path, Path]:
    import csv

    key = str(config["vehicle_key"])
    archive_dir = root / "data" / key / "autotrader"
    latest_dir = root / "data" / key / "latest"
    archive_dir.mkdir(parents=True, exist_ok=True)
    latest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M")
    archive = archive_dir / f"{key}_autotrader_{timestamp}.csv"
    latest = latest_dir / f"{key}_autotrader_latest.csv"
    for path in (archive, latest):
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=[*SOURCE_FIELDS, *EXTRA_FIELDS], extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    return archive, latest
