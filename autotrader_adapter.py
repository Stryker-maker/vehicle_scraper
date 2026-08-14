from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol
from urllib.parse import urlencode

from autotrader_distance import DistanceResult, build_distance_resolver
from autotrader_history import apply_price_history, load_trim_tiers, write_csv_outputs
from phase1_common import utc_now, write_json
from vehicle_config import load_vehicle_config

ADAPTER_SCHEMA_VERSION = 1
DEFAULT_PAGE_SIZE = 100
DEFAULT_MAX_PAGES = 50
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class ResponseLike(Protocol):
    status_code: int
    text: str


class SessionLike(Protocol):
    def get(self, url: str, *, headers: dict[str, str], timeout: float) -> ResponseLike: ...


class ScriptCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.inside = False
        self.parts: list[str] = []
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "script":
            self.inside, self.parts = True, []

    def handle_data(self, data: str) -> None:
        if self.inside:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self.inside:
            self.scripts.append("".join(self.parts))
            self.inside, self.parts = False, []


def artifact_paths(root: Path, config: dict[str, Any]) -> dict[str, Path]:
    base = root / "data" / str(config["vehicle_key"]) / "adapter_evidence" / "autotrader"
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


def build_search_url(
    *, make_slug: str, model_slug: str, location: str, fuel: str,
    offset: int, page_size: int = DEFAULT_PAGE_SIZE,
) -> str:
    query: list[tuple[str, str | int]] = [
        ("rcp", page_size), ("rcs", offset), ("srt", 35), ("loc", location),
    ]
    fuel_value = {"diesel": "Diesel", "gas": "Gas", "gasoline": "Gas", "hybrid": "Hybrid"}.get(fuel.lower())
    if fuel_value:
        query.append(("fuel", fuel_value))
    query.extend([
        ("hprc", "True"), ("wcp", "True"), ("inMarket", "advancedSearch"),
        ("sts", "New-Used"), ("prx", 100),
    ])
    return f"https://www.autotrader.ca/cars/{make_slug}/{model_slug}/?{urlencode(query)}"


def extract_page_payload(html: str) -> tuple[list[Any], int | None]:
    collector = ScriptCollector()
    collector.feed(html)
    for script in collector.scripts:
        if '"listings"' not in script:
            continue
        try:
            value = json.loads(script.strip())
        except json.JSONDecodeError:
            continue
        page = value.get("props", {}).get("pageProps", {}) if isinstance(value, dict) else {}
        listings = page.get("listings") if isinstance(page, dict) else None
        if not isinstance(listings, list):
            continue
        total = None
        candidates = [page.get("totalResults"), page.get("totalCount"), page.get("count")]
        pagination = page.get("pagination")
        if isinstance(pagination, dict):
            candidates.extend([pagination.get("total"), pagination.get("totalResults"), pagination.get("count")])
        for candidate in candidates:
            try:
                total = int(candidate)
                break
            except (TypeError, ValueError):
                pass
        return list(listings), total
    raise ValueError("autotrader_listing_payload_not_found")


def request_with_retry(
    session: SessionLike, *, url: str, headers: dict[str, str], timeout: float,
    max_attempts: int, sleep: Callable[[float], None], backoff_seconds: float,
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
                raise RuntimeError(f"non_retryable_http_status:{status}")
            last_error = RuntimeError(f"retryable_http_status:{status}")
        except Exception as exc:
            if attempts and attempts[-1]["error"] is None and attempts[-1]["http_status"]:
                attempts[-1]["error"] = str(exc)
            else:
                attempts.append({"attempt": attempt, "http_status": None, "error": f"{type(exc).__name__}: {exc}"})
            last_error = exc
            if str(exc).startswith("non_retryable_http_status"):
                raise
        if attempt < max_attempts:
            sleep(backoff_seconds * attempt)
    raise RuntimeError(f"request_attempts_exhausted:{last_error}")


def clean_int(value: Any) -> int | None:
    cleaned = re.sub(r"[^0-9-]", "", "" if value is None else str(value))
    try:
        return int(cleaned) if cleaned else None
    except ValueError:
        return None


def engine_text(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if "6,700" in text or "6700" in text:
        return "6.7L"
    numeric = re.sub(r"[^0-9.]", "", text)
    try:
        number = float(numeric)
    except ValueError:
        return text
    return f"{round(number / 1000, 1)}L" if number >= 100 else text


def trim_tier(text: str, tiers: dict[str, list[str]]) -> int:
    lowered = text.lower()
    if any(keyword.lower() in lowered for keyword in tiers.get("tier3", [])):
        return 3
    if any(keyword.lower() in lowered for keyword in tiers.get("tier2", [])):
        return 2
    return 1


def accident_claim(item: dict[str, Any]) -> str:
    vehicle = item.get("vehicle") if isinstance(item.get("vehicle”), dict) else {}
    parts = [str(item.get("description") or ""), str(vehicle.get("modelVersionInput") or "")]
    for detail in item.get("vehicleDetails", []) if isinstance(item.get("vehicleDetails"), list) else []:
        if isinstance(detail, dict):
            parts.append(str(detail.get("data") or ""))
    text = " ".join(parts).lower()
    if any(term in text for term in ("salvage", "rebuilt title", "structural damage")):
        return "Salvage/rebuilt"
    if any(term in text for term in ("no accident", "clean carfax", "accident free", "0 accident", "zero accident", "no reported accident")):
        return "No accidents reported"
    if any(term in text for term in ("accident", "collision", "damage reported")):
        return "Accident reported"
    return "Unknown"


def parse_listing(
    item: dict[str, Any], *, config: dict[str, Any], tiers: dict[str, list[str]],
    distance_resolver: Callable[[dict[str, Any]], DistanceResult], provenance: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    try:
        vehicle = item.get("vehicle")
        if not isinstance(vehicle, dict):
            return None, [], ["missing_vehicle_object"]
        listing_id, listing_url = str(item.get("id") or "").strip(), str(item.get("url") or "").strip()
        price_obj = item.get("price") if isinstance(item.get("price"), dict) else {}
        price, year = clean_int(price_obj.get("priceFormatted")), clean_int(vehicle.get("modelYear"))
        parse_failures = [name for name, value in (("invalid_price", price), ("invalid_year", year)) if value is None]
        if parse_failures:
            return None, [], parse_failures

        mileage = clean_int(vehicle.get("mileageInKm"))
        engine, fuel = engine_text(vehicle.get("engineDisplacementInCCM")), str(vehicle.get("fuel") or "").strip()
        trim = str(vehicle.get("modelVersionInput") or "").strip()
        location_obj = item.get("location") if isinstance(item.get("location"), dict) else {}
        city, province = str(location_obj.get("city") or "").strip(), str(location_obj.get("provinceCode") or "").strip()
        street, postal = str(location_obj.get("street") or "").strip(), str(location_obj.get("zip") or "").strip()
        location = ", ".join(part for part in (city, province) if part)
        address = ", ".join(part for part in (street, city, province, postal) if part)
        distance = distance_resolver({"dealer_address": address, "location": location})

        criteria, rejections = config["criteria"], []
        if not listing_id: rejections.append("missing_source_listing_id")
        if not listing_url: rejections.append("missing_listing_url")
        if not criteria["min_year"] <= year <= criteria["max_year"]: rejections.append("year_out_of_range")
        if not 0 < price <= criteria["max_price_cad"]: rejections.append("price_out_of_range")
        required_fuel = str(criteria.get("fuel") or "").strip()
        if required_fuel and required_fuel.lower() not in fuel.lower(): rejections.append("fuel_unknown" if not fuel else "fuel_mismatch")
        required_engine = str(criteria.get("engine") or "").strip()
        if required_engine and required_engine.lower() not in engine.lower(): rejections.append("engine_unknown" if not engine else "engine_mismatch")
        if distance.distance_km is None:
            rejections.append("distance_unavailable")
        elif distance.distance_km > config["origin"]["max_distance_km"]:
            rejections.append("distance_out_of_range")

        seller = item.get("seller") if isinstance(item.get("seller"), dict) else {}
        super_deal = item.get("superDeal") if isinstance(item.get("superDeal"), dict) else {}
        old_price = str(super_deal.get("oldPriceFormatted") or "").strip()
        row = {
            "year": year, "make": vehicle.get("make") or config["make"],
            "model": vehicle.get("model") or config["model"], "trim": trim,
            "trim_tier": trim_tier(trim, tiers), "price": price,
            "price_history": f"Reduced from {old_price}" if old_price else "No change noted",
            "trend": "", "weeks_tracked": 0, "price_first_seen": price,
            "price_last_week": price, "price_change_week": 0, "price_change_total": 0,
            "mileage": "" if mileage is None else mileage, "engine": engine, "fuel": fuel,
            "accident_flag": accident_claim(item), "days_on_market": "",
            "dealer": seller.get("companyName") or "Unknown", "seller_type": "Dealer",
            "dealer_address": address, "location": location,
            "distance_km": "" if distance.distance_km is None else distance.distance_km,
            "distance_method": distance.method, "distance_evidence_status": distance.evidence_status,
            "listing_id": listing_id, "url_region_hint": "", "url_region_status": "unavailable",
            "url": listing_url, "source": "AutoTrader", **provenance,
        }
        return row, sorted(set(rejections)), []
    except Exception as exc:
        return None, [], [f"unexpected_parse_failure:{type(exc).__name__}"]


def default_session() -> SessionLike:
    import requests
    return requests.Session()


def collect_autotrader(
    *, root: Path, config_path: Path, run_id: str | None = None,
    session: SessionLike | None = None,
    distance_resolver: Callable[[dict[str, Any]], DistanceResult] | None = None,
    sleep: Callable[[float], None] = time.sleep, page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: int = DEFAULT_MAX_PAGES, request_timeout_seconds: float = 20.0,
    max_attempts: int = 3, backoff_seconds: float = 1.0,
) -> dict[str, Any]:
    root, config_path = root.resolve(), config_path if config_path.is_absolute() else root / config_path
    config, active_run = load_vehicle_config(config_path), run_id or os.environ.get("GITHUB_RUN_ID", "local")
    session, distance_resolver = session or default_session(), distance_resolver or build_distance_resolver(config)
    tiers, source_config = load_trim_tiers(root, str(config["vehicle_key"])), config["sources"]["autotrader"]
    headers = {"User-Agent": "Mozilla/5.0 Chrome/120 VehicleScraper/1.0"}
    requests_evidence: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    first_identity: dict[str, int] = {}
    pagination_complete, source_index = True, 0

    for location in source_config["search_locations"]:
        previous_fingerprint = None
        for page in range(1, max_pages + 1):
            offset = (page - 1) * page_size
            url = build_search_url(
                make_slug=source_config["make"], model_slug=source_config["model"],
                location=location, fuel=config["criteria"].get("fuel", ""),
                offset=offset, page_size=page_size,
            )
            request = {
                "adapter_schema_version": ADAPTER_SCHEMA_VERSION, "vehicle_key": config["vehicle_key"],
                "source": "autotrader", "run_id": active_run, "query_location": location,
                "query_page": page, "query_offset": offset, "request_url": url,
                "attempts": [], "outcome": "unknown", "listing_count": 0,
                "pagination_stop_reason": None,
            }
            try:
                response, attempts = request_with_retry(
                    session, url=url, headers=headers, timeout=request_timeout_seconds,
                    max_attempts=max_attempts, sleep=sleep, backoff_seconds=backoff_seconds,
                )
                request["attempts"] = attempts
                listings, total = extract_page_payload(response.text)
            except Exception as exc:
                request.update(outcome="failed", error=f"{type(exc).__name__}: {exc}")
                requests_evidence.append(request)
                pagination_complete = False
                break

            request.update(outcome="success", listing_count=len(listings), reported_total_count=total)
            fingerprint = hashlib.sha256(json.dumps([
                item.get("id") if isinstance(item, dict) else item for item in listings
            ], sort_keys=True, default=str).encode()).hexdigest()
            if previous_fingerprint == fingerprint and listings:
                request["pagination_stop_reason"] = "repeated_page_fingerprint"
                requests_evidence.append(request)
                pagination_complete = False
                break
            previous_fingerprint = fingerprint

            for item in listings:
                provenance = {"query_location": location, "query_page": page, "query_offset": offset, "request_url": url}
                identity = str(item.get("id") or item.get("url") or f"row-{source_index}").strip() if isinstance(item, dict) else f"row-{source_index}"
                record = {
                    "adapter_schema_version": ADAPTER_SCHEMA_VERSION, "vehicle_key": config["vehicle_key"],
                    "source": "autotrader", "run_id": active_run, "source_record_index": source_index,
                    "record_stage": "unknown", "provenance": provenance, "raw_payload": item,
                    "parsed_row": None, "rejection_reasons": [], "parse_failure_reasons": [],
                }
                if not isinstance(item, dict):
                    record.update(record_stage="parse_failure", parse_failure_reasons=["listing_payload_not_object"])
                elif identity in first_identity:
                    record.update(
                        record_stage="rejected", rejection_reasons=["duplicate_source_listing_identity"],
                        duplicate_of_source_record_index=first_identity[identity],
                    )
                else:
                    first_identity[identity] = source_index
                    row, rejected, failed = parse_listing(
                        item, config=config, tiers=tiers,
                        distance_resolver=distance_resolver, provenance=provenance,
                    )
                    if failed:
                        record.update(record_stage="parse_failure", parse_failure_reasons=failed)
                    else:
                        record.update(parsed_row=row, rejection_reasons=rejected, record_stage="rejected" if rejected else "accepted")
                records.append(record)
                source_index += 1

            stop = (
                "reported_total_reached" if total is not None and offset + len(listings) >= total
                else "short_page" if len(listings) < page_size else None
            )
            request["pagination_stop_reason"] = stop
            requests_evidence.append(request)
            if stop:
                break
        else:
            pagination_complete = False
            requests_evidence.append({
                "adapter_schema_version": ADAPTER_SCHEMA_VERSION, "vehicle_key": config["vehicle_key"],
                "source": "autotrader", "run_id": active_run, "query_location": location,
                "query_page": max_pages, "query_offset": max_pages * page_size,
                "request_url": None, "attempts": [], "outcome": "failed", "listing_count": 0,
                "pagination_stop_reason": "max_pages_reached", "error": "pagination_limit_reached",
            })

    accepted_rows = [record["parsed_row"] for record in records if record["record_stage"] == "accepted" and isinstance(record.get("parsed_row"), dict)]
    apply_price_history(root, config, accepted_rows)
    archive = latest = None
    if accepted_rows:
        archive, latest = write_csv_outputs(root, config, accepted_rows)
    paths = artifact_paths(root, config)
    relative = {name: str(path.relative_to(root)) for name, path in paths.items()}
    counts = {stage: sum(record["record_stage"] == stage for record in records) for stage in ("accepted", "rejected", "parse_failure")}
    failed_pages = sum(record["outcome"] == "failed" for record in requests_evidence)
    report = {
        "adapter_schema_version": ADAPTER_SCHEMA_VERSION, "vehicle_key": config["vehicle_key"],
        "source": "autotrader", "run_id": active_run, "generated_at_utc": utc_now(),
        "fetched_record_scope": "autotrader_adapter_response_listing_objects",
        "source_fetch_completeness": "pagination_observed_complete_for_configured_queries" if pagination_complete and not failed_pages else "incomplete_due_to_request_or_pagination_failure",
        "page_request_count": len(requests_evidence),
        "request_attempt_count": sum(len(record.get("attempts", [])) for record in requests_evidence),
        "successful_page_count": len(requests_evidence) - failed_pages, "failed_page_count": failed_pages,
        "pagination_complete": pagination_complete and not failed_pages, "fetched_records": len(records),
        "parsed_records": sum(isinstance(record.get("parsed_row”), dict) for record in records),
        "accepted_records": counts["accepted"], "rejected_records": counts["rejected"],
        "parse_failures": counts["parse_failure"],
        "duplicate_records": sum("duplicate_source_listing_identity" in record["rejection_reasons"] for record in records),
        "reconciled": len(records) == sum(counts.values()),
        "reconciliation_equation": "fetched_records = accepted_records + rejected_records + parse_failures",
        "artifacts": relative, "archive_output": str(archive.relative_to(root)) if archive else None,
        "latest_output": str(latest.relative_to(root)) if latest else None,
    }
    write_jsonl(paths["requests"], requests_evidence)
    write_jsonl(paths["records"], records)
    write_json(paths["reconciliation"], report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Direct AutoTrader source adapter")
    parser.add_argument("--config", required=True)
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    args = parser.parse_args(argv)
    report = collect_autotrader(root=Path.cwd(), config_path=Path(args.config), page_size=args.page_size, max_pages=args.max_pages)
    print(
        f"[autotrader-adapter] fetched={report['fetched_records']} accepted={report['accepted_records']} "
        f"rejected={report['rejected_records']} parse_failures={report['parse_failures']} "
        f"pages={report['page_request_count']} pagination_complete={report['pagination_complete']}"
    )
    return 0 if report["reconciled"] and report["pagination_complete"] and report["accepted_records"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
