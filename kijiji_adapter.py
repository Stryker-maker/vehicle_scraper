from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from kijiji_history import apply_price_history, load_trim_tiers, write_csv_outputs
from kijiji_locations import LOCATION_REGISTRY_VERSION, validate_query_locations
from kijiji_response_diagnostics import summarize_kijiji_html
from phase1_common import utc_now, write_json, chrome_desktop_headers
from vehicle_config import load_vehicle_config

ADAPTER_SCHEMA_VERSION = 1
DEFAULT_PAGE_SIZE = 40
DEFAULT_MAX_PAGES = 50
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class ResponseLike(Protocol):
    status_code: int
    text: str


class SessionLike(Protocol):
    def get(
        self, url: str, *, headers: dict[str, str], timeout: float
    ) -> ResponseLike: ...


class RequestFailure(RuntimeError):
    def __init__(self, message: str, attempts: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.attempts = attempts


def artifact_paths(root: Path, config: dict[str, Any]) -> dict[str, Path]:
    base = root / "data" / str(config["vehicle_key"]) / "adapter_evidence" / "kijiji"
    return {
        "requests": base / "requests_latest.jsonl",
        "records": base / "records_latest.jsonl",
        "reconciliation": base / "reconciliation_latest.json",
    }


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            json.dump(record, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
    temporary.replace(path)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "vehicles"


def build_search_url(
    *, make: str, model: str, query_location: dict[str, str], page: int
) -> str:
    if page < 1:
        raise ValueError("Kijiji page must be positive")
    page_segment = f"page-{page}/" if page > 1 else ""
    query = slugify(f"{make} {model}")
    return (
        f"https://www.kijiji.ca/b-cars-trucks/{query_location['slug']}/"
        f"{query}/{page_segment}k0c174l{query_location['location_id']}"
    )


def extract_url_region_hint(url: str) -> str:
    try:
        parts = [part for part in urlparse(url).path.split("/") if part]
        index = parts.index("v-cars-trucks")
    except (TypeError, ValueError):
        return ""
    return parts[index + 1] if index + 1 < len(parts) else ""


def _json_ld_items(value: Any) -> list[Any]:
    if isinstance(value, list):
        result: list[Any] = []
        for element in value:
            result.extend(_json_ld_items(element))
        return result
    if not isinstance(value, dict):
        return []
    kind = value.get("@type")
    if kind == "ItemList":
        elements = value.get("itemListElement")
        if not isinstance(elements, list):
            return []
        return [
            element.get("item")
            if isinstance(element, dict) and "item" in element
            else element
            for element in elements
        ]
    kinds = set(kind) if isinstance(kind, list) else {kind}
    result = [value] if kinds & {"Car", "Vehicle", "Product"} else []
    graph = value.get("@graph")
    if isinstance(graph, list):
        for element in graph:
            result.extend(_json_ld_items(element))
    return result


def extract_page_payload(html: str) -> tuple[list[Any], list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[Any] = []
    errors: list[str] = []
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    for index, script in enumerate(scripts):
        text = script.string or script.get_text() or ""
        if not text.strip():
            continue
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            errors.append(f"invalid_json_ld_script:{index}")
            continue
        items.extend(_json_ld_items(value))
    return items, errors


def request_with_retry(
    session: SessionLike,
    *,
    url: str,
    headers: dict[str, str],
    timeout: float,
    max_attempts: int,
    sleep: Callable[[float], None],
    backoff_seconds: float,
) -> tuple[ResponseLike, list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = session.get(url, headers=headers, timeout=timeout)
            status = int(getattr(response, "status_code", 0))
            attempts.append({"attempt": attempt, "http_status": status, "error": None})
            if 200 <= status < 300:
                return response, attempts
            if status not in RETRYABLE_STATUS_CODES:
                attempts[-1]["error"] = f"non_retryable_http_status:{status}"
                raise RequestFailure(
                    f"non_retryable_http_status:{status}", attempts
                )
            last_error = RuntimeError(f"retryable_http_status:{status}")
        except Exception as exc:
            if attempts and attempts[-1]["error"] is None and attempts[-1]["http_status"]:
                attempts[-1]["error"] = str(exc)
            else:
                attempts.append(
                    {
                        "attempt": attempt,
                        "http_status": None,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            last_error = exc
            if isinstance(exc, RequestFailure):
                raise
        if attempt < max_attempts:
            sleep(backoff_seconds * attempt)
    raise RequestFailure(f"request_attempts_exhausted:{last_error}", attempts)


def clean_int(value: Any) -> int | None:
    if isinstance(value, dict):
        value = value.get("value")
    cleaned = re.sub(r"[^0-9-]", "", "" if value is None else str(value))
    try:
        return int(cleaned) if cleaned else None
    except ValueError:
        return None


def trim_tier(text: str, tiers: dict[str, list[str]]) -> int:
    lowered = text.casefold()
    if any(keyword.casefold() in lowered for keyword in tiers.get("tier3", [])):
        return 3
    if any(keyword.casefold() in lowered for keyword in tiers.get("tier2", [])):
        return 2
    return 1


def trim_name(text: str, tiers: dict[str, list[str]]) -> str:
    for group in ("tier3", "tier2", "tier1"):
        for keyword in tiers.get(group, []):
            if keyword.casefold() in text.casefold():
                return keyword
    return "Unknown"


def accident_claim(text: str) -> str:
    lowered = text.casefold()
    if any(term in lowered for term in ("salvage", "rebuilt title", "structural damage")):
        return "Salvage/rebuilt"
    if any(
        term in lowered
        for term in (
            "no accident",
            "clean carfax",
            "accident free",
            "0 accident",
            "zero accident",
            "no reported accident",
        )
    ):
        return "No accidents reported"
    if any(term in lowered for term in ("accident", "collision", "damage reported")):
        return "Accident reported"
    return "Unknown"


def _address_parts(value: Any) -> tuple[str, str]:
    if not isinstance(value, dict):
        return "", ""
    locality = str(value.get("addressLocality") or value.get("city") or "").strip()
    region = str(value.get("addressRegion") or value.get("province") or "").strip()
    street = str(value.get("streetAddress") or value.get("street") or "").strip()
    postal = str(value.get("postalCode") or value.get("zip") or "").strip()
    location = ", ".join(part for part in (locality, region) if part)
    address = ", ".join(part for part in (street, locality, region, postal) if part)
    return location, address


def extract_listing_geography(item: dict[str, Any]) -> tuple[str, str, str, str]:
    candidates: list[Any] = [item.get("address"), item.get("contentLocation")]
    location = item.get("location")
    if isinstance(location, dict):
        candidates.extend([location.get("address"), location])
    offers = item.get("offers")
    if isinstance(offers, dict):
        candidates.extend([offers.get("availableAtOrFrom"), offers.get("areaServed")])
    candidates.append(item.get("availableAtOrFrom"))
    seller = item.get("seller")
    if isinstance(seller, dict):
        candidates.append(seller.get("address"))
    expanded: list[Any] = []
    for candidate in candidates:
        expanded.append(candidate)
        if isinstance(candidate, dict) and isinstance(candidate.get("address"), dict):
            expanded.append(candidate["address"])
    for candidate in expanded:
        found_location, found_address = _address_parts(candidate)
        if found_location:
            status = "source_reported_listing_specific_unverified"
            return found_location, found_address, status, status
    return "", "", "unknown", "unknown"


def _listing_id(item: dict[str, Any], url: str) -> str:
    for key in ("sku", "productID", "identifier"):
        value = item.get(key)
        if isinstance(value, dict):
            value = value.get("value")
        if value not in (None, ""):
            return str(value).strip()
    matches = re.findall(r"/(
