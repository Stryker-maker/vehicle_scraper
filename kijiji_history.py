from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autotrader_history import LEGACY_HISTORY_NOTICE, load_trim_tiers
from phase1_common import SOURCE_FIELDS

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
    """Retain source CSV compatibility fields without trusting legacy history files."""
    del root, config
    for row in rows:
        row.update(
            weeks_tracked="",
            price_first_seen="",
            price_last_week="",
            price_change_week="",
            price_change_total="",
            trend=LEGACY_HISTORY_NOTICE,
        )


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
