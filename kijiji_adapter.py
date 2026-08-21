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
    matches = re.findall(r"/(\d+)(?=[/?#]|$)", url)
    return matches[-1] if matches else ""


def _offers(item: dict[str, Any]) -> dict[str, Any]:
    value = item.get("offers")
    if isinstance(value, list):
        value = next((entry for entry in value if isinstance(entry, dict)), {})
    return value if isinstance(value, dict) else {}


def _structured_engine_parts(item: dict[str, Any]) -> list[str]:
    value = item.get("vehicleEngine")
    values = value if isinstance(value, list) else [value]
    parts: list[str] = []
    for entry in values:
        if isinstance(entry, dict):
            for key in (
                "fuelType",
                "name",
                "description",
                "engineDisplacement",
                "engineType",
                "configuration",
            ):
                field = entry.get(key)
                if isinstance(field, dict):
                    field = field.get("value") or field.get("name")
                if field not in (None, ""):
                    parts.append(str(field).strip())
        elif entry not in (None, ""):
            parts.append(str(entry).strip())
    return [part for part in parts if part]


def _fuel_and_engine(item: dict[str, Any], text: str) -> tuple[str, str]:
    structured_parts = _structured_engine_parts(item)
    combined = " ".join([text, *structured_parts]).strip()
    lowered = combined.casefold()
    structured_fuel = " ".join(
        part for part in structured_parts if part.casefold() in {
            "gas", "gasoline", "petrol", "diesel", "hybrid", "electric"
        }
    ).casefold()
    fuel_text = structured_fuel or lowered
    if "hybrid" in fuel_text:
        fuel = "Hybrid"
    elif "electric" in fuel_text:
        fuel = "Electric"
    elif "diesel" in fuel_text:
        fuel = "Diesel"
    elif re.search(r"\b(?:gas|gasoline|petrol|unleaded)\b", fuel_text):
        fuel = "Gas"
    else:
        fuel = "Unknown"
    match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:l|litre|liter)\b",
        combined,
        flags=re.IGNORECASE,
    )
    return fuel, f"{match.group(1)}L" if match else "Unknown"


def _source_text(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("name") or value.get("value")
    return "" if value is None else str(value).strip()


def parse_listing(
    item: dict[str, Any],
    *,
    config: dict[str, Any],
    tiers: dict[str, list[str]],
    provenance: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    url = str(item.get("url") or item.get("@id") or "").strip()
    listing_id = _listing_id(item, url)
    title = str(item.get("name") or "").strip()
    description = str(item.get("description") or "").strip()
    configuration = str(item.get("vehicleConfiguration") or "").strip()
    combined = " ".join((title, description, configuration))
    offers = _offers(item)
    price = clean_int(offers.get("price"))
    year = clean_int(item.get("vehicleModelDate"))
    if year is None:
        match = re.search(r"\b(?:19|20)\d{2}\b", title)
        year = int(match.group(0)) if match else None
    parse_failures = [
        name
        for name, value in (("invalid_price", price), ("invalid_year", year))
        if value is None
    ]
    if parse_failures:
        return None, [], parse_failures

    mileage = clean_int(item.get("mileageFromOdometer"))
    fuel, engine = _fuel_and_engine(item, combined)
    location, address, location_status, address_status = extract_listing_geography(item)
    seller = item.get("seller") if isinstance(item.get("seller"), dict) else {}
    seller_name = str(seller.get("name") or seller.get("legalName") or "Unknown").strip()
    seller_type = "Dealer" if seller_name and seller_name != "Unknown" else "Unknown"
    region_hint = extract_url_region_hint(url)
    criteria = config["criteria"]
    rejections: list[str] = []
    if not listing_id:
        rejections.append("missing_source_listing_id")
    if not url:
        rejections.append("missing_listing_url")
    if not criteria["min_year"] <= year <= criteria["max_year"]:
        rejections.append("year_out_of_range")
    if not 0 < price <= criteria["max_price_cad"]:
        rejections.append("price_out_of_range")
    required_fuel = str(criteria.get("fuel") or "").strip()
    if required_fuel and required_fuel.casefold() not in fuel.casefold():
        rejections.append("fuel_unknown" if fuel == "Unknown" else "fuel_mismatch")
    required_engine = str(criteria.get("engine") or "").strip()
    if required_engine and required_engine.casefold() not in engine.casefold():
        rejections.append("engine_unknown" if engine == "Unknown" else "engine_mismatch")

    trim_source = configuration or title
    row = {
        "year": year,
        "make": _source_text(item.get("manufacturer"))
        or config["sources"]["kijiji"]["make"],
        "model": _source_text(item.get("model"))
        or config["sources"]["kijiji"]["model"],
        "trim": trim_name(trim_source, tiers),
        "trim_tier": trim_tier(trim_source, tiers),
        "price": price,
        "price_history": "No change noted",
        "trend": "",
        "weeks_tracked": 0,
        "price_first_seen": price,
        "price_last_week": price,
        "price_change_week": 0,
        "price_change_total": 0,
        "mileage": "" if mileage is None else mileage,
        "engine": engine,
        "fuel": fuel,
        "accident_flag": accident_claim(combined),
        "days_on_market": "",
        "dealer": seller_name or "Unknown",
        "seller_type": seller_type,
        "dealer_address": address,
        "dealer_address_evidence_status": address_status,
        "location": location,
        "location_evidence_status": location_status,
        "distance_km": "",
        "distance_method": "disabled_listing_location_not_routed",
        "distance_evidence_status": "disabled_no_verified_route",
        "listing_id": listing_id,
        "url_region_hint": region_hint,
        "url_region_status": "unverified_url_evidence" if region_hint else "unavailable",
        "url": url,
        "source": "Kijiji",
        **provenance,
    }
    return row, sorted(set(rejections)), []


def default_session() -> SessionLike:
    import requests

    return requests.Session()


def collect_kijiji(
    *,
    root: Path,
    config_path: Path,
    run_id: str | None = None,
    session: SessionLike | None = None,
    sleep: Callable[[float], None] = time.sleep,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: int = DEFAULT_MAX_PAGES,
    request_timeout_seconds: float = 20.0,
    max_attempts: int = 3,
    backoff_seconds: float = 1.0,
) -> dict[str, Any]:
    root = root.resolve()
    config_path = config_path if config_path.is_absolute() else root / config_path
    config = load_vehicle_config(config_path)
    active_run = run_id or os.environ.get("GITHUB_RUN_ID", "local")
    session = session or default_session()
    tiers = load_trim_tiers(root, str(config["vehicle_key"]))
    source_config = config["sources"]["kijiji"]
    query_plan = validate_query_locations(source_config["search_locations"])
    headers = chrome_desktop_headers()
    requests_evidence: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    first_identity: dict[str, int] = {}
    pagination_complete = True
    source_index = 0

    for query in query_plan:
        previous_fingerprint: str | None = None
        query_complete = False
        for page in range(1, max_pages + 1):
            url = build_search_url(
                make=source_config["make"],
                model=source_config["model"],
                query_location=query,
                page=page,
            )
            request_record: dict[str, Any] = {
                "adapter_schema_version": ADAPTER_SCHEMA_VERSION,
                "run_id": active_run,
                "vehicle_key": config["vehicle_key"],
                "source": "kijiji",
                "query_location": query["config_label"],
                "query_display_name": query["display_name"],
                "query_location_id": query["location_id"],
                "query_slug": query["slug"],
                "query_page": page,
                "request_url": url,
                "attempts": [],
                "http_status": None,
                "returned_listing_objects": 0,
                "json_ld_errors": [],
                "page_status": "failed",
                "stop_reason": None,
            }
            try:
                response, attempts = request_with_retry(
                    session,
                    url=url,
                    headers=headers,
                    timeout=request_timeout_seconds,
                    max_attempts=max_attempts,
                    sleep=sleep,
                    backoff_seconds=backoff_seconds,
                )
                request_record["attempts"] = attempts
                request_record["http_status"] = int(response.status_code)
                items, json_errors = extract_page_payload(response.text)
                request_record["json_ld_errors"] = json_errors
                request_record["response_diagnostics"] = summarize_kijiji_html(
                    response.text
                )
            except Exception as exc:
                request_record["attempts"] = (
                    exc.attempts
                    if isinstance(exc, RequestFailure)
                    else [
                        {
                            "attempt": None,
                            "http_status": None,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    ]
                )
                request_record["stop_reason"] = "request_or_payload_failure"
                requests_evidence.append(request_record)
                pagination_complete = False
                break

            fingerprint = hashlib.sha256(
                json.dumps(items, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()
            if previous_fingerprint is not None and fingerprint == previous_fingerprint and items:
                request_record.update(
                    page_status="failed",
                    returned_listing_objects=len(items),
                    stop_reason="repeated_page_payload",
                )
                requests_evidence.append(request_record)
                pagination_complete = False
                break
            previous_fingerprint = fingerprint
            request_record["page_status"] = "success"
            request_record["returned_listing_objects"] = len(items)

            for item_index, item in enumerate(items):
                provenance = {
                    "query_location": query["config_label"],
                    "query_display_name": query["display_name"],
                    "query_location_id": query["location_id"],
                    "query_slug": query["slug"],
                    "query_page": page,
                    "request_url": url,
                    "response_item_index": item_index,
                }
                adapter_record: dict[str, Any] = {
                    "adapter_schema_version": ADAPTER_SCHEMA_VERSION,
                    "run_id": active_run,
                    "vehicle_key": config["vehicle_key"],
                    "source": "kijiji",
                    "source_record_index": source_index,
                    "record_stage": "parse_failure",
                    "raw_payload": item,
                    "provenance": provenance,
                    "parsed_row": None,
                    "rejection_reasons": [],
                    "parse_failure_reasons": [],
                }
                if not isinstance(item, dict):
                    adapter_record["parse_failure_reasons"] = [
                        "listing_payload_not_object"
                    ]
                else:
                    parsed, rejections, parse_failures = parse_listing(
                        item,
                        config=config,
                        tiers=tiers,
                        provenance=provenance,
                    )
                    if parse_failures:
                        adapter_record["parse_failure_reasons"] = parse_failures
                    else:
                        adapter_record["parsed_row"] = parsed
                        identity = str(parsed.get("listing_id") or parsed.get("url") or "")
                        if identity and identity in first_identity:
                            rejections = sorted(
                                set([*rejections, "duplicate_source_listing_identity"])
                            )
                            adapter_record["duplicate_of_source_record_index"] = (
                                first_identity[identity]
                            )
                        elif identity:
                            first_identity[identity] = source_index
                        adapter_record["rejection_reasons"] = rejections
                        adapter_record["record_stage"] = (
                            "rejected" if rejections else "accepted"
                        )
                records.append(adapter_record)
                source_index += 1

            if not items:
                diag = request_record.get("response_diagnostics") or summarize_kijiji_html(
                    response.text
                )
                is_legitimate_empty = (
                    not request_record.get("json_ld_errors")
                    and not diag.get("block_markers")
                    and bool(diag.get("next_data_present"))
                    and (
                        bool(diag.get("item_list_marker_present"))
                        or int(diag.get("json_ld_script_count") or 0) > 0
                    )
                )
                if not is_legitimate_empty:
                    request_record["page_status"] = "failed"
                    request_record["stop_reason"] = "suspected_block"
                    requests_evidence.append(request_record)
                    break

                request_record["stop_reason"] = "empty_page"
                query_complete = True
                requests_evidence.append(request_record)
                break
            if len(items) < page_size:
                request_record["stop_reason"] = "short_page"
                query_complete = True
                requests_evidence.append(request_record)
                break
            requests_evidence.append(request_record)
        if not query_complete:
            pagination_complete = False

    accepted_rows = [
        record["parsed_row"]
        for record in records
        if record["record_stage"] == "accepted"
        and isinstance(record.get("parsed_row"), dict)
    ]
    accepted_rows.sort(
        key=lambda row: (
            int(row.get("year") or 0),
            int(row.get("price") or 0),
            int(row.get("mileage") or 999999),
            str(row.get("listing_id") or ""),
        )
    )
    apply_price_history(root, config, accepted_rows)
    archive, latest = write_csv_outputs(root, config, accepted_rows)

    paths = artifact_paths(root, config)
    write_jsonl(paths["requests"], requests_evidence)
    for index, record in enumerate(records):
        record["source_adapter_record_ref"] = (
            f"{paths['records'].relative_to(root)}#source_record_index={index}"
        )
    write_jsonl(paths["records"], records)
    accepted = sum(record["record_stage"] == "accepted" for record in records)
    rejected = sum(record["record_stage"] == "rejected" for record in records)
    parse_failures = sum(
        record["record_stage"] == "parse_failure" for record in records
    )
    fetched = len(records)
    reconciled = fetched == accepted + rejected + parse_failures
    actual_locations = sum(
        record.get("parsed_row", {}).get("location_evidence_status")
        == "source_reported_listing_specific_unverified"
        for record in records
        if isinstance(record.get("parsed_row"), dict)
    )
    report = {
        "adapter_schema_version": ADAPTER_SCHEMA_VERSION,
        "location_registry_version": LOCATION_REGISTRY_VERSION,
        "vehicle_key": config["vehicle_key"],
        "source": "kijiji",
        "run_id": active_run,
        "generated_at_utc": utc_now(),
        "fetched_record_scope": "kijiji_adapter_json_ld_listing_objects",
        "source_fetch_completeness": (
            "configured_validated_hub_queries_only_not_marketplace_complete"
        ),
        "query_location_count": len(query_plan),
        "query_locations": [query["config_label"] for query in query_plan],
        "request_attempt_count": sum(
            len(entry.get("attempts", [])) for entry in requests_evidence
        ),
        "page_request_count": len(requests_evidence),
        "successful_page_count": sum(
            entry["page_status"] == "success" for entry in requests_evidence
        ),
        "failed_page_count": sum(
            entry["page_status"] != "success" for entry in requests_evidence
        ),
        "pagination_complete": pagination_complete,
        "fetched_records": fetched,
        "accepted_records": accepted,
        "rejected_records": rejected,
        "parse_failures": parse_failures,
        "listing_specific_location_records": actual_locations,
        "unknown_location_records": fetched - actual_locations,
        "reconciled": reconciled,
        "reconciliation_equation": (
            "fetched_records = accepted_records + rejected_records + parse_failures"
        ),
        "latest_output": str(latest.relative_to(root)),
        "archive_output": str(archive.relative_to(root)),
        "artifacts": {
            name: str(path.relative_to(root)) for name, path in paths.items()
        },
    }
    write_json(paths["reconciliation"], report)
    print(
        f"[{config['vehicle_key']}:kijiji-adapter] fetched={fetched} "
        f"| accepted={accepted} | rejected={rejected} "
        f"| parse_failures={parse_failures} | pages={len(requests_evidence)} "
        f"| pagination_complete={pagination_complete}"
    )
    return report


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Collect Kijiji listings through the direct evidence adapter"
    )
    result.add_argument("--config", required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    report = collect_kijiji(root=Path.cwd(), config_path=Path(args.config))
    return 0 if report["reconciled"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
