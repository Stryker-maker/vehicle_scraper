from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase1_common import SOURCE_FIELDS

EXTRA_FIELDS = [
    "distance_evidence_status", "query_location", "query_page",
    "query_offset", "request_url",
]


LEGACY_HISTORY_NOTICE = (
    "Legacy source history retired; use identity_lifecycle artifacts and supported "
    "manual-review elapsed/price fields"
)


def load_trim_tiers(root: Path, vehicle_key: str) -> dict[str, list[str]]:
    path = root / "trim_tiers.json"
    if not path.exists():
        return {"tier3": [], "tier2": [], "tier1": []}
    value = json.loads(path.read_text(encoding="utf-8"))
    tiers = value.get(vehicle_key, {}) if isinstance(value, dict) else {}
    return {name: list(tiers.get(name, [])) for name in ("tier3", "tier2", "tier1")}


def apply_price_history(
    root: Path, config: dict[str, Any], rows: list[dict[str, Any]]
) -> None:
    """Retain source CSV compatibility fields without trusting legacy history files.

    Audit 06 moves active observation, elapsed-time, lifecycle, and price-change
    semantics into ``identity_lifecycle.py``. Historical ``price_history_*.json``
    files are deliberately not read, migrated, or rewritten here.
    """
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
            writer = csv.DictWriter(
                handle,
                fieldnames=[*SOURCE_FIELDS, *EXTRA_FIELDS],
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(rows)
    return archive, latest
