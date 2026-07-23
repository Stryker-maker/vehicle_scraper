from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from kijiji_adapter import build_search_url, default_session
from kijiji_locations import validate_query_locations
from phase1_common import utc_now
from vehicle_config import load_vehicle_config

PROBE_SCHEMA_VERSION = 2
PUBLIC_RESPONSE_HEADERS = (
    "content-type",
    "content-length",
    "content-encoding",
    "cache-control",
    "server",
    "via",
    "x-cache",
    "x-request-id",
)
BLOCK_MARKERS = (
    "access denied",
    "captcha",
    "cloudflare",
    "datadome",
    "incapsula",
    "perimeterx",
    "px-captcha",
    "robot check",
    "verify you are human",
)
DATA_MARKERS = (
    "__next_data__",
    "__apollo_state__",
    "application/ld+json",
    "itemlistelement",
    "searchresults",
    "listingcard",
    "/v-cars-trucks/",
)
HEADER_PROFILES: dict[str, dict[str, str]] = {
    "production_adapter_v1": {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "Chrome/120 VehicleScraper/1.0"
        ),
        "Accept-Language": "en-CA,en;q=0.9",
    },
    "browser_compatible_v1": {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-CA,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    },
}


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "query"


def response_summary(response: Any, requested_url: str) -> dict[str, Any]:
    text = str(getattr(response, "text", "") or "")
    encoded = text.encode("utf-8", errors="replace")
    soup = BeautifulSoup(text, "html.parser")
    scripts = soup.find_all("script")
    lowered = text.casefold()
    response_headers = {
        str(name).casefold(): value
        for name, value in dict(getattr(response, "headers", {}) or {}).items()
    }
    title = soup.title.get_text(" ", strip=True) if soup.title else None
    script_inventory = []
    for index, script in enumerate(scripts):
        script_text = script.string or script.get_text() or ""
        script_inventory.append(
            {
                "index": index,
                "type": script.get("type"),
                "id": script.get("id"),
                "src": script.get("src"),
                "text_bytes": len(script_text.encode("utf-8", errors="replace")),
                "text_sha256": hashlib.sha256(
                    script_text.encode("utf-8", errors="replace")
                ).hexdigest(),
            }
        )
    listing_links = sorted(
        {
            str(anchor.get("href"))
            for anchor in soup.find_all("a", href=True)
            if "/v-cars-trucks/" in str(anchor.get("href"))
        }
    )
    return {
        "probe_schema_version": PROBE_SCHEMA_VERSION,
        "requested_url": requested_url,
        "final_url": str(getattr(response, "url", requested_url) or requested_url),
        "http_status": int(getattr(response, "status_code", 0)),
        "generated_at_utc": utc_now(),
        "response_bytes": len(encoded),
        "response_sha256": hashlib.sha256(encoded).hexdigest(),
        "page_title": title,
        "public_response_headers": {
            name: response_headers[name]
            for name in PUBLIC_RESPONSE_HEADERS
            if name in response_headers
        },
        "script_count": len(scripts),
        "script_types": sorted(
            {str(script.get("type") or "") for script in scripts}
        ),
        "script_inventory": script_inventory,
        "block_markers": [marker for marker in BLOCK_MARKERS if marker in lowered],
        "data_markers": [marker for marker in DATA_MARKERS if marker in lowered],
        "listing_link_count": len(listing_links),
        "listing_link_sample": listing_links[:20],
        "text_sample": " ".join(soup.stripped_strings)[:4000],
    }


def run_probe(
    *,
    config_path: Path,
    output_dir: Path,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    config = load_vehicle_config(config_path)
    source = config["sources"]["kijiji"]
    query_plan = validate_query_locations(source["search_locations"])
    output_dir.mkdir(parents=True, exist_ok=True)
    session = default_session()
    records: list[dict[str, Any]] = []
    for query in query_plan:
        url = build_search_url(
            make=source["make"],
            model=source["model"],
            query_location=query,
            page=1,
        )
        for profile_name, headers in HEADER_PROFILES.items():
            record: dict[str, Any] = {
                "header_profile": profile_name,
                "query_location": query["config_label"],
                "query_location_id": query["location_id"],
                "request_url": url,
            }
            try:
                response = session.get(url, headers=headers, timeout=timeout_seconds)
                summary = response_summary(response, url)
                record.update(summary)
                raw_name = (
                    f"{_safe_name(query['config_label'])}-{profile_name}-page-1.html"
                )
                (output_dir / raw_name).write_text(
                    str(getattr(response, "text", "") or ""),
                    encoding="utf-8",
                )
                record["raw_html_file"] = raw_name
            except Exception as exc:
                record.update(
                    {
                        "generated_at_utc": utc_now(),
                        "request_error": f"{type(exc).__name__}: {exc}",
                    }
                )
            records.append(record)
    report = {
        "probe_schema_version": PROBE_SCHEMA_VERSION,
        "vehicle_key": config["vehicle_key"],
        "config_path": str(config_path),
        "query_count": len(query_plan),
        "header_profiles": sorted(HEADER_PROFILES),
        "request_count": len(records),
        "records": records,
    }
    (output_dir / "probe_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return report


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Capture non-publishing Kijiji response diagnostics"
    )
    result.add_argument("--config", required=True)
    result.add_argument("--output-dir", required=True)
    result.add_argument("--timeout-seconds", type=float, default=30.0)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    run_probe(
        config_path=Path(args.config),
        output_dir=Path(args.output_dir),
        timeout_seconds=args.timeout_seconds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
