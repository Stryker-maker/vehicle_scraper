from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autotrader_history import load_trim_tiers
from phase1_common import SOURCE_FIELDS, write_json

EXTRA_FIELDS = [
    "location_evidence_status",
    "dealer_address_evidence_status",
    "distance_evidence_status",
    "query_location",
    "query_location_id",
    "query_page",
    "request_url",
]


def apply_price_history(
    root: Path, config: dict[str, Any], rows: list[dict[str, Any]]
) -> None:
    path = root / "data" / str(config["vehicle_key"]) / "price_history_kijiji.json"
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
            "First observed this run"
            if not records
            else f"Down ${abs(change):,} over {count} observations"
            if change < 0
            else f"Up ${change:,} over {count} observations"
            if change > 0
            else f"Unchanged for {count} observations"
        )
        records.append({"date": today, "price": row["price"]})
    write_json(path, history)


def write_csv_outputs(
    root: Path, config: dict[str, Any], rows: list[dict[str, Any]]
) -> tuple[Path, Path]:
    key = str(config["vehicle_key"])
    archive_dir = root / "data" / key / "kijiji"
    latest_dir = root / "data" / key / "latest"
    archive_dir.mkdir(parents=True, exist_ok=True)
    latest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M")
    archive = archive_dir / f"{key}_kijiji_{timestamp}.csv"
    latest = latest_dir / f"{key}_kijiji_latest.csv"
    fields = [*SOURCE_FIELDS, *EXTRA_FIELDS]
    for path in (archive, latest):
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=fields, extrasaction="ignore"
            )
            writer.writeheader()
            writer.writerows(rows)
    return archive, latest
