from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from canonical_evidence import read_jsonl, write_jsonl
from phase1_common import SOURCES, write_json

IDENTITY_LIFECYCLE_SCHEMA_VERSION = 2
SUPPORTED_PREVIOUS_IDENTITY_SCHEMAS = {1, 2}
RETIRE_AFTER_CONSECUTIVE_MISSES = 3
RETIRE_AFTER_MISSING_DAYS = 14.0
MAX_RETAINED_PRICE_OBSERVATIONS = 13
MAX_RETIRED_LISTINGS_PER_SOURCE = 500
RETIRED_LISTING_MAX_AGE_DAYS = 365.0
MAX_RECENT_STATE_DELETIONS = 100
ZERO_DIGEST = "0" * 64
VIN_PATTERN = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
VIN_KEYS = {
    "vin",
    "vehicleidentificationnumber",
    "vehicle_identification_number",
    "vehicle-id-number",
}
UNKNOWN_TEXT = {"", "unknown", "n/a", "na", "none", "null", "unavailable"}


def artifact_paths(root: Path, config: dict[str, Any], source: str) -> dict[str, Path]:
    if source not in SOURCES:
        raise ValueError(f"Unsupported source: {source}")
    base = root / "data" / str(config["vehicle_key"]) / "identity_lifecycle" / source
    return {
        "state": base / "state_latest.json",
        "current": base / "current_latest.jsonl",
        "events": base / "events_latest.jsonl",
        "summary": base / "summary_latest.json",
    }


def duplicate_candidate_path(root: Path, config: dict[str, Any]) -> Path:
    return (
        root
        / "data"
        / str(config["vehicle_key"])
        / "identity_lifecycle"
        / "duplicate_candidates_latest.jsonl"
    )


def snapshot_artifacts(
    root: Path, config: dict[str, Any], source: str
) -> dict[str, bytes | None]:
    snapshot: dict[str, bytes | None] = {}
    for path in artifact_paths(root, config, source).values():
        snapshot[str(path)] = path.read_bytes() if path.exists() else None
    return snapshot


def restore_artifacts(snapshot: dict[str, bytes | None]) -> None:
    for raw_path, content in snapshot.items():
        path = Path(raw_path)
        if content is None:
            if path.exists():
                path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _elapsed(start: str, end: str) -> tuple[int, float]:
    seconds = max(0, int((_parse_time(end) - _parse_time(start)).total_seconds()))
    return seconds, round(seconds / 86400, 6)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return None if cleaned.casefold() in UNKNOWN_TEXT else cleaned


def _normalized_token(value: Any) -> str:
    text = _text(value) or ""
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _trim_tokens(value: Any) -> list[str]:
    return sorted(
        token
        for token in set(_normalized_token(value).split())
        if len(token) > 1 and token not in {"the", "and", "with"}
    )


def _stable_id(prefix: str, *parts: object) -> str:
    payload = "\x1f".join("" if part is None else str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _json_digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _chain_digest(previous: str, values: Iterable[dict[str, Any]]) -> str:
    digest = previous if re.fullmatch(r"[0-9a-f]{64}", previous or "") else ZERO_DIGEST
    for value in values:
        payload = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        digest = hashlib.sha256(bytes.fromhex(digest) + payload).hexdigest()
    return digest


def _walk_explicit_vin_claims(value: Any) -> list[str]:
    claims: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = re.sub(r"[^a-z0-9_-]", "", str(key).casefold())
            if normalized_key in VIN_KEYS:
                values = child if isinstance(child, list) else [child]
                for candidate in values:
                    if isinstance(candidate, (str, int)):
                        claims.append(str(candidate).strip())
            else:
                claims.extend(_walk_explicit_vin_claims(child))
    elif isinstance(value, list):
        for child in value:
            claims.extend(_walk_explicit_vin_claims(child))
    return claims


def vin_claim_evidence(raw_payload: Any) -> dict[str, Any]:
    raw_claims = sorted({claim for claim in _walk_explicit_vin_claims(raw_payload) if claim})
    normalized_claims = sorted(
        {
            re.sub(r"[^A-Z0-9]", "", claim.upper())
            for claim in raw_claims
            if claim
        }
    )
    valid = [claim for claim in normalized_claims if VIN_PATTERN.fullmatch(claim)]
    if len(set(valid)) > 1:
        return {
            "vin_claim": None,
            "vin_evidence_status": "conflicting_source_reported_claims",
            "vin_raw_claims": raw_claims,
        }
    if len(valid) == 1:
        return {
            "vin_claim": valid[0],
            "vin_evidence_status": "source_reported_format_valid_unverified",
            "vin_raw_claims": raw_claims,
        }
    if raw_claims:
        return {
            "vin_claim": None,
            "vin_evidence_status": "source_reported_invalid_format_unverified",
            "vin_raw_claims": raw_claims,
        }
    return {
        "vin_claim": None,
        "vin_evidence_status": "not_reported",
        "vin_raw_claims": [],
    }


def _identity_components(record: dict[str, Any]) -> dict[str, Any]:
    normalized = record.get("normalized", {})
    year = normalized.get("year")
    price = normalized.get("price_cad")
    mileage = normalized.get("mileage_km")
    return {
        "year": year if isinstance(year, int) else None,
        "make": _normalized_token(normalized.get("make")),
        "model": _normalized_token(normalized.get("model")),
        "trim_tokens": _trim_tokens(normalized.get("trim")),
        "mileage_km": mileage if isinstance(mileage, int) else None,
        "mileage_bucket_1000": int(mileage / 1000) if isinstance(mileage, int) else None,
        "mileage_bucket_3000": int(mileage / 3000) if isinstance(mileage, int) else None,
        "price_cad": price if isinstance(price, int) else None,
        "price_bucket_1000": int(price / 1000) if isinstance(price, int) else None,
        "dealer": _normalized_token(normalized.get("dealer")),
        "location": _normalized_token(normalized.get("location")),
    }


def _fingerprints(components: dict[str, Any]) -> tuple[str, str]:
    strict = _stable_id(
        "fingerprint_strict",
        components.get("year"),
        components.get("make"),
        components.get("model"),
        ",".join(components.get("trim_tokens", [])),
        components.get("mileage_bucket_1000"),
        components.get("dealer"),
    )
    loose = _stable_id(
        "fingerprint_loose",
        components.get("year"),
        components.get("make"),
        components.get("model"),
        ",".join(components.get("trim_tokens", [])),
        components.get("mileage_bucket_3000"),
    )
    return strict, loose


def _adapter_payloads(root: Path, adapter_records_path: str | None) -> dict[int, Any]:
    if not adapter_records_path:
        return {}
    path = root / adapter_records_path
    if not path.exists():
        return {}
    records = read_jsonl(path)
    return {
        int(record["source_record_index"]): record.get("raw_payload")
        for record in records
        if isinstance(record.get("source_record_index"), int)
    }


def _retained_observations(old: dict[str, Any] | None, run_id: str) -> list[dict[str, Any]]:
    if not old:
        return []
    return [
        dict(value)
        for value in old.get("price_observations", [])
        if isinstance(value, dict) and value.get("run_id") != run_id
    ]


def _compact_observations(
    *,
    observations: list[dict[str, Any]],
    previous_digest: str,
    previous_compacted_count: int,
) -> tuple[list[dict[str, Any]], str, int, str | None]:
    observations.sort(
        key=lambda value: (
            str(value.get("observed_at_utc")),
            str(value.get("run_id")),
        )
    )
    remove_count = max(0, len(observations) - MAX_RETAINED_PRICE_OBSERVATIONS)
    removed = observations[:remove_count]
    retained = observations[remove_count:]
    digest = _chain_digest(previous_digest, removed)
    compacted_count = previous_compacted_count + len(removed)
    compacted_through = (
        str(removed[-1].get("observed_at_utc")) if removed else None
    )
    return retained, digest, compacted_count, compacted_through


def _price_summary(
    *,
    old: dict[str, Any] | None,
    retained: list[dict[str, Any]],
    total_count: int,
    compacted_count: int,
    digest: str,
    compacted_through: str | None,
    observed_at_utc: str,
) -> dict[str, Any]:
    current = retained[-1].get("price_cad") if retained else None
    previous = retained[-2].get("price_cad") if len(retained) > 1 else None
    old_first = old.get("first_observed_price_cad") if old else None
    first = old_first if old_first is not None else current
    numeric_prices = [
        value.get("price_cad")
        for value in retained
        if isinstance(value.get("price_cad"), int)
    ]
    old_min = old.get("minimum_observed_price_cad") if old else None
    old_max = old.get("maximum_observed_price_cad") if old else None
    minimum_candidates = [
        value for value in [old_min, *numeric_prices] if isinstance(value, int)
    ]
    maximum_candidates = [
        value for value in [old_max, *numeric_prices] if isinstance(value, int)
    ]
    old_compacted_through = old.get("price_observations_compacted_through_at_utc") if old else None
    return {
        "price_observation_count": total_count,
        "retained_price_observation_count": len(retained),
        "compacted_price_observation_count": compacted_count,
        "price_observation_retention_limit": MAX_RETAINED_PRICE_OBSERVATIONS,
        "price_observation_compaction_digest_sha256": digest,
        "price_observations_compacted_through_at_utc": (
            compacted_through or old_compacted_through
        ),
        "first_observed_price_cad": first,
        "first_price_observed_at_utc": (
            old.get("first_price_observed_at_utc")
            if old and old.get("first_price_observed_at_utc")
            else observed_at_utc
        ),
        "previous_observation_price_cad": previous,
        "current_price_cad": current,
        "minimum_observed_price_cad": min(minimum_candidates) if minimum_candidates else None,
        "maximum_observed_price_cad": max(maximum_candidates) if maximum_candidates else None,
        "change_from_previous_observation_cad": (
            current - previous
            if isinstance(current, int) and isinstance(previous, int)
            else None
        ),
        "change_from_first_observation_cad": (
            current - first
            if isinstance(current, int) and isinstance(first, int)
            else None
        ),
    }


def _current_projection(listing: dict[str, Any], run_id: str) -> dict[str, Any]:
    projection = {
        key: value for key, value in listing.items() if key != "price_observations"
    }
    projection["identity_lifecycle_schema_version"] = IDENTITY_LIFECYCLE_SCHEMA_VERSION
    projection["run_id"] = run_id
    projection["record_stage"] = "current_identity_lifecycle"
    return projection


def _state_retention_ledger(previous: dict[str, Any]) -> dict[str, Any]:
    value = previous.get("state_retention_ledger", {})
    if not isinstance(value, dict):
        value = {}
    recent = [
        dict(entry)
        for entry in value.get("recent_deletions", [])
        if isinstance(entry, dict)
    ][-MAX_RECENT_STATE_DELETIONS:]
    return {
        "deleted_retired_listing_count_total": int(
            value.get("deleted_retired_listing_count_total", 0)
        ),
        "deleted_retired_listing_bytes_total": int(
            value.get("deleted_retired_listing_bytes_total", 0)
        ),
        "deletion_chain_sha256": str(
            value.get("deletion_chain_sha256") or ZERO_DIGEST
        ),
        "recent_deletions": recent,
        "recent_deletion_limit": MAX_RECENT_STATE_DELETIONS,
    }


def _retired_deletion_record(
    *,
    listing: dict[str, Any],
    source: str,
    vehicle_key: str,
    run_id: str,
    deleted_at_utc: str,
    reason: str,
) -> dict[str, Any]:
    payload = json.dumps(
        listing, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "identity_lifecycle_schema_version": IDENTITY_LIFECYCLE_SCHEMA_VERSION,
        "run_id": run_id,
        "vehicle_key": vehicle_key,
        "source": source,
        "deleted_at_utc": deleted_at_utc,
        "reason": reason,
        "canonical_listing_id": listing.get("canonical_listing_id"),
        "source_listing_id": listing.get("source_listing_id"),
        "first_seen_at_utc": listing.get("first_seen_at_utc"),
        "last_seen_at_utc": listing.get("last_seen_at_utc"),
        "last_evaluated_at_utc": listing.get("last_evaluated_at_utc"),
        "final_lifecycle_state": listing.get("lifecycle_state"),
        "observation_count": listing.get("observation_count"),
        "first_observed_price_cad": listing.get("first_observed_price_cad"),
        "current_price_cad": listing.get("current_price_cad"),
        "vin_evidence_status": listing.get("vin_evidence_status"),
        "listing_bytes": len(payload),
        "listing_sha256": hashlib.sha256(payload).hexdigest(),
    }


def _prune_retired_listings(
    *,
    listings: dict[str, dict[str, Any]],
    ledger: dict[str, Any],
    source: str,
    vehicle_key: str,
    run_id: str,
    evaluated_at_utc: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    retired = [
        listing
        for listing in listings.values()
        if listing.get("lifecycle_state") == "retired"
    ]
    retired.sort(
        key=lambda value: (
            str(value.get("last_seen_at_utc") or ""),
            str(value.get("canonical_listing_id") or ""),
        ),
        reverse=True,
    )
    deletions: list[dict[str, Any]] = []
    for index, listing in enumerate(retired):
        last_seen = str(listing.get("last_seen_at_utc") or evaluated_at_utc)
        _, elapsed_days = _elapsed(last_seen, evaluated_at_utc)
        reason = None
        if elapsed_days > RETIRED_LISTING_MAX_AGE_DAYS:
            reason = "retired_tombstone_age_limit_exceeded"
        elif index >= MAX_RETIRED_LISTINGS_PER_SOURCE:
            reason = "retired_tombstone_count_limit_exceeded"
        if reason is None:
            continue
        canonical_id = str(listing.get("canonical_listing_id") or "")
        if canonical_id:
            deletions.append(
                _retired_deletion_record(
                    listing=listing,
                    source=source,
                    vehicle_key=vehicle_key,
                    run_id=run_id,
                    deleted_at_utc=evaluated_at_utc,
                    reason=reason,
                )
            )
            listings.pop(canonical_id, None)
    if not deletions:
        return [], ledger
    recent = [
        *[
            dict(value)
            for value in ledger.get("recent_deletions", [])
            if isinstance(value, dict)
        ],
        *deletions,
    ][-MAX_RECENT_STATE_DELETIONS:]
    updated = {
        "deleted_retired_listing_count_total": int(
            ledger.get("deleted_retired_listing_count_total", 0)
        )
        + len(deletions),
        "deleted_retired_listing_bytes_total": int(
            ledger.get("deleted_retired_listing_bytes_total", 0)
        )
        + sum(int(value["listing_bytes"]) for value in deletions),
        "deletion_chain_sha256": _chain_digest(
            str(ledger.get("deletion_chain_sha256") or ZERO_DIGEST), deletions
        ),
        "recent_deletions": recent,
        "recent_deletion_limit": MAX_RECENT_STATE_DELETIONS,
        "last_deletion_run_id": run_id,
        "last_deletion_at_utc": evaluated_at_utc,
    }
    return deletions, updated


def update_source_identity_lifecycle(
    *,
    root: Path,
    config: dict[str, Any],
    source: str,
    run_id: str,
    observed_at_utc: str,
    accepted_artifact: str,
    adapter_records_artifact: str | None,
) -> dict[str, Any]:
    root = root.resolve()
    paths = artifact_paths(root, config, source)
    previous: dict[str, Any] = {}
    migrated_from_schema: int | None = None
    if paths["state"].exists():
        loaded = json.loads(paths["state"].read_text(encoding="utf-8"))
        if (
            isinstance(loaded, dict)
            and loaded.get("identity_lifecycle_schema_version")
            in SUPPORTED_PREVIOUS_IDENTITY_SCHEMAS
            and loaded.get("vehicle_key") == config["vehicle_key"]
            and loaded.get("source") == source
        ):
            previous = loaded
            if loaded.get("identity_lifecycle_schema_version") != IDENTITY_LIFECYCLE_SCHEMA_VERSION:
                migrated_from_schema = int(loaded["identity_lifecycle_schema_version"])
    listings = {
        str(key): dict(value)
        for key, value in previous.get("listings", {}).items()
        if isinstance(value, dict)
    }
    ledger = _state_retention_ledger(previous)
    accepted_records = read_jsonl(root / accepted_artifact)
    for record in accepted_records:
        if record.get("run_id") != run_id or record.get("record_stage") != "accepted":
            raise ValueError("Accepted evidence is not current accepted identity input")
    adapter_payloads = _adapter_payloads(root, adapter_records_artifact)
    is_new_successful_run = previous.get("last_successful_run_id") != run_id
    successful_source_run_count = int(previous.get("successful_source_run_count", 0))
    if is_new_successful_run:
        successful_source_run_count += 1

    observed_ids: set[str] = set()
    current_records: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    new_count = 0
    reappeared_count = 0
    price_observations_compacted_this_run = 0

    for record in accepted_records:
        canonical_id = str(record.get("canonical_listing_id") or "")
        if not canonical_id:
            raise ValueError("Accepted record is missing canonical_listing_id")
        observed_ids.add(canonical_id)
        old = listings.get(canonical_id)
        prior_state = str(old.get("lifecycle_state")) if old else None
        if old is None:
            new_count += 1
            first_seen = observed_at_utc
            lifecycle_state = "active"
            lifecycle_reason = "first_successful_observation"
            reappearance_count = 0
            prior_total = 0
            prior_compacted_count = 0
            prior_digest = ZERO_DIGEST
        else:
            first_seen = str(old["first_seen_at_utc"])
            reappearance_count = int(old.get("reappearance_count", 0))
            prior_total = int(
                old.get(
                    "price_observation_count",
                    old.get("observation_count", len(old.get("price_observations", []))),
                )
            )
            prior_compacted_count = int(
                old.get(
                    "compacted_price_observation_count",
                    max(0, prior_total - len(old.get("price_observations", []))),
                )
            )
            prior_digest = str(
                old.get("price_observation_compaction_digest_sha256") or ZERO_DIGEST
            )
            if prior_state in {"missing", "retired"} and is_new_successful_run:
                lifecycle_state = "reappeared"
                lifecycle_reason = f"observed_after_{prior_state}"
                reappearance_count += 1
                reappeared_count += 1
            elif prior_state == "reappeared" and is_new_successful_run:
                lifecycle_state = "active"
                lifecycle_reason = "observed_consecutively_after_reappearance"
            else:
                lifecycle_state = "active"
                lifecycle_reason = "observed_in_successful_source_run"

        observations = _retained_observations(old, run_id)
        normalized = record.get("normalized", {})
        price = normalized.get("price_cad")
        observations.append(
            {
                "run_id": run_id,
                "observed_at_utc": observed_at_utc,
                "price_cad": price if isinstance(price, int) else None,
            }
        )
        total_count = (
            1
            if old is None
            else prior_total + (1 if is_new_successful_run else 0)
        )
        before_compacted = prior_compacted_count
        observations, digest, compacted_count, compacted_through = _compact_observations(
            observations=observations,
            previous_digest=prior_digest,
            previous_compacted_count=prior_compacted_count,
        )
        price_observations_compacted_this_run += compacted_count - before_compacted
        components = _identity_components(record)
        strict_fingerprint, loose_fingerprint = _fingerprints(components)
        vin = vin_claim_evidence(
            adapter_payloads.get(int(record.get("source_record_index", -1)))
        )
        elapsed_seconds, elapsed_days = _elapsed(first_seen, observed_at_utc)
        listing = {
            "canonical_listing_id": canonical_id,
            "source": source,
            "source_listing_id": record.get("source_listing_id"),
            "source_listing_id_status": "source_identifier_claim_not_vin",
            "listing_url": normalized.get("listing_url"),
            **vin,
            "identity_fingerprint_strict": strict_fingerprint,
            "identity_fingerprint_loose": loose_fingerprint,
            "identity_fingerprint_components": components,
            "lifecycle_state": lifecycle_state,
            "lifecycle_state_reason": lifecycle_reason,
            "first_seen_at_utc": first_seen,
            "last_seen_at_utc": observed_at_utc,
            "last_observed_run_id": run_id,
            "last_evaluated_at_utc": observed_at_utc,
            "last_evaluated_run_id": run_id,
            "observation_count": total_count,
            "successful_seen_run_count": total_count,
            "missing_run_count": 0,
            "reappearance_count": reappearance_count,
            "elapsed_since_first_seen_seconds": elapsed_seconds,
            "elapsed_since_first_seen_days": elapsed_days,
            "elapsed_since_last_seen_seconds": 0,
            "elapsed_since_last_seen_days": 0.0,
            "price_observations": observations,
            **_price_summary(
                old=old,
                retained=observations,
                total_count=total_count,
                compacted_count=compacted_count,
                digest=digest,
                compacted_through=compacted_through,
                observed_at_utc=observed_at_utc,
            ),
        }
        listings[canonical_id] = listing
        current_records.append(_current_projection(listing, run_id))
        if old is None or prior_state != lifecycle_state:
            events.append(
                {
                    "identity_lifecycle_schema_version": IDENTITY_LIFECYCLE_SCHEMA_VERSION,
                    "run_id": run_id,
                    "vehicle_key": config["vehicle_key"],
                    "source": source,
                    "canonical_listing_id": canonical_id,
                    "event_at_utc": observed_at_utc,
                    "previous_state": prior_state,
                    "new_state": lifecycle_state,
                    "reason": lifecycle_reason,
                }
            )

    if is_new_successful_run:
        for canonical_id, old in list(listings.items()):
            if canonical_id in observed_ids:
                continue
            prior_state = str(old.get("lifecycle_state") or "active")
            missing_run_count = int(old.get("missing_run_count", 0)) + 1
            last_seen = str(old["last_seen_at_utc"])
            elapsed_seconds, elapsed_days = _elapsed(last_seen, observed_at_utc)
            if prior_state == "retired":
                lifecycle_state = "retired"
                lifecycle_reason = "remains_unobserved_after_retirement"
            elif (
                missing_run_count >= RETIRE_AFTER_CONSECUTIVE_MISSES
                and elapsed_days >= RETIRE_AFTER_MISSING_DAYS
            ):
                lifecycle_state = "retired"
                lifecycle_reason = "retirement_threshold_met"
            else:
                lifecycle_state = "missing"
                lifecycle_reason = "not_observed_in_successful_source_run"
            old.update(
                lifecycle_state=lifecycle_state,
                lifecycle_state_reason=lifecycle_reason,
                missing_run_count=missing_run_count,
                last_evaluated_at_utc=observed_at_utc,
                last_evaluated_run_id=run_id,
                elapsed_since_last_seen_seconds=elapsed_seconds,
                elapsed_since_last_seen_days=elapsed_days,
            )
            if prior_state != lifecycle_state:
                events.append(
                    {
                        "identity_lifecycle_schema_version": IDENTITY_LIFECYCLE_SCHEMA_VERSION,
                        "run_id": run_id,
                        "vehicle_key": config["vehicle_key"],
                        "source": source,
                        "canonical_listing_id": canonical_id,
                        "event_at_utc": observed_at_utc,
                        "previous_state": prior_state,
                        "new_state": lifecycle_state,
                        "reason": lifecycle_reason,
                    }
                )

    retired_deletions, ledger = _prune_retired_listings(
        listings=listings,
        ledger=ledger,
        source=source,
        vehicle_key=str(config["vehicle_key"]),
        run_id=run_id,
        evaluated_at_utc=observed_at_utc,
    )
    counts = {
        lifecycle: sum(
            listing.get("lifecycle_state") == lifecycle for listing in listings.values()
        )
        for lifecycle in ("active", "reappeared", "missing", "retired")
    }
    state = {
        "identity_lifecycle_schema_version": IDENTITY_LIFECYCLE_SCHEMA_VERSION,
        "migrated_from_identity_lifecycle_schema_version": migrated_from_schema,
        "vehicle_key": config["vehicle_key"],
        "source": source,
        "last_successful_run_id": run_id,
        "last_successful_run_at_utc": observed_at_utc,
        "successful_source_run_count": successful_source_run_count,
        "retirement_policy": {
            "minimum_consecutive_missing_successful_runs": RETIRE_AFTER_CONSECUTIVE_MISSES,
            "minimum_elapsed_missing_days": RETIRE_AFTER_MISSING_DAYS,
            "meaning": "operational_lifecycle_inference_not_source_sold_claim",
        },
        "storage_retention_policy": {
            "retained_price_observations_per_listing": MAX_RETAINED_PRICE_OBSERVATIONS,
            "maximum_retired_listings_per_source": MAX_RETIRED_LISTINGS_PER_SOURCE,
            "maximum_retired_listing_age_days": RETIRED_LISTING_MAX_AGE_DAYS,
            "recent_deletion_records": MAX_RECENT_STATE_DELETIONS,
            "compacted_history_contract": "digest_backed_not_raw_reconstructable",
        },
        "state_retention_ledger": ledger,
        "listings": dict(sorted(listings.items())),
    }
    relative = {name: str(path.relative_to(root)) for name, path in paths.items()}
    summary = {
        "identity_lifecycle_schema_version": IDENTITY_LIFECYCLE_SCHEMA_VERSION,
        "migrated_from_identity_lifecycle_schema_version": migrated_from_schema,
        "run_id": run_id,
        "vehicle_key": config["vehicle_key"],
        "source": source,
        "generated_at_utc": observed_at_utc,
        "successful_source_run_count": successful_source_run_count,
        "observed_current_count": len(current_records),
        "tracked_listing_count": len(listings),
        "new_listing_count": new_count,
        "reappeared_listing_count": reappeared_count,
        "active_listing_count": counts["active"],
        "current_reappeared_listing_count": counts["reappeared"],
        "missing_listing_count": counts["missing"],
        "retired_listing_count": counts["retired"],
        "transition_event_count": len(events),
        "price_observations_compacted_this_run": price_observations_compacted_this_run,
        "retired_listings_pruned_this_run": len(retired_deletions),
        "retired_listing_deletion_count_total": ledger[
            "deleted_retired_listing_count_total"
        ],
        "retired_listing_deletion_chain_sha256": ledger["deletion_chain_sha256"],
        "retained_price_observation_limit": MAX_RETAINED_PRICE_OBSERVATIONS,
        "retired_listing_count_limit": MAX_RETIRED_LISTINGS_PER_SOURCE,
        "retired_listing_age_limit_days": RETIRED_LISTING_MAX_AGE_DAYS,
        "source_identity_contract": "source_scoped_identifier_distinct_from_vin",
        "vin_contract": "source_reported_claim_unverified_never_inferred_from_listing_id",
        "storage_retention_contract": "bounded_state_digest_backed_deletion_evidence",
        "artifacts": relative,
    }
    write_json(paths["state"], state)
    write_jsonl(paths["current"], current_records)
    write_jsonl(paths["events"], events)
    write_json(paths["summary"], summary)
    return summary


def load_current_identity_records(
    *, root: Path, config: dict[str, Any], source: str, run_id: str
) -> list[dict[str, Any]]:
    path = artifact_paths(root, config, source)["current"]
    records = read_jsonl(path)
    for record in records:
        if (
            record.get("identity_lifecycle_schema_version")
            != IDENTITY_LIFECYCLE_SCHEMA_VERSION
            or record.get("run_id") != run_id
            or record.get("source") != source
        ):
            raise ValueError("Identity lifecycle current artifact mismatch")
    return records


def _candidate_for_pair(
    left: dict[str, Any], right: dict[str, Any], *, vehicle_key: str, run_id: str
) -> dict[str, Any] | None:
    if left.get("source") == right.get("source"):
        return None
    left_components = left.get("identity_fingerprint_components", {})
    right_components = right.get("identity_fingerprint_components", {})
    reasons: list[str] = []
    confidence: str | None = None
    score: float | None = None

    left_vin = left.get("vin_claim")
    right_vin = right.get("vin_claim")
    if (
        left_vin
        and left_vin == right_vin
        and left.get("vin_evidence_status")
        == "source_reported_format_valid_unverified"
        and right.get("vin_evidence_status")
        == "source_reported_format_valid_unverified"
    ):
        confidence, score = "high", 0.98
        reasons.append("exact_source_reported_vin_claim_match")
    else:
        identity_match = all(
            left_components.get(field)
            and left_components.get(field) == right_components.get(field)
            for field in ("year", "make", "model")
        )
        if not identity_match:
            return None
        left_price = left_components.get("price_cad")
        right_price = right_components.get("price_cad")
        left_mileage = left_components.get("mileage_km")
        right_mileage = right_components.get("mileage_km")
        price_delta = (
            abs(left_price - right_price)
            if isinstance(left_price, int) and isinstance(right_price, int)
            else None
        )
        mileage_delta = (
            abs(left_mileage - right_mileage)
            if isinstance(left_mileage, int) and isinstance(right_mileage, int)
            else None
        )
        support: list[str] = ["year_make_model_match"]
        if (
            left.get("identity_fingerprint_strict")
            == right.get("identity_fingerprint_strict")
        ):
            support.append("strict_fingerprint_match")
        if (
            left.get("identity_fingerprint_loose")
            == right.get("identity_fingerprint_loose")
        ):
            support.append("loose_fingerprint_match")
        if (
            left_components.get("dealer")
            and left_components.get("dealer") == right_components.get("dealer")
        ):
            support.append("seller_name_match")
        if (
            left_components.get("location")
            and left_components.get("location") == right_components.get("location")
        ):
            support.append("location_claim_match")
        trim_overlap = set(left_components.get("trim_tokens", [])) & set(
            right_components.get("trim_tokens", [])
        )
        if trim_overlap:
            support.append("trim_token_overlap")
        if (
            mileage_delta is not None
            and mileage_delta <= 1000
            and price_delta is not None
            and price_delta <= 1500
            and len(support) >= 2
        ):
            confidence, score = "medium", 0.78
            reasons.extend(
                support + ["mileage_within_1000_km", "price_within_1500_cad"]
            )
        elif (
            mileage_delta is not None
            and mileage_delta <= 3000
            and price_delta is not None
            and price_delta <= 3000
            and len(support) >= 2
        ):
            confidence, score = "low", 0.56
            reasons.extend(
                support + ["mileage_within_3000_km", "price_within_3000_cad"]
            )
        else:
            return None

    ordered = sorted(
        [left, right],
        key=lambda value: (
            str(value.get("source")),
            str(value.get("canonical_listing_id")),
        ),
    )
    left_ref, right_ref = ordered
    candidate_id = _stable_id(
        "duplicate_candidate",
        vehicle_key,
        left_ref.get("canonical_listing_id"),
        right_ref.get("canonical_listing_id"),
    )
    return {
        "identity_lifecycle_schema_version": IDENTITY_LIFECYCLE_SCHEMA_VERSION,
        "run_id": run_id,
        "vehicle_key": vehicle_key,
        "candidate_id": candidate_id,
        "confidence": confidence,
        "confidence_score": score,
        "reasons": sorted(set(reasons)),
        "decision_status": "candidate_only_not_merged",
        "left": {
            "source": left_ref.get("source"),
            "canonical_listing_id": left_ref.get("canonical_listing_id"),
            "source_listing_id": left_ref.get("source_listing_id"),
            "vin_claim": left_ref.get("vin_claim"),
        },
        "right": {
            "source": right_ref.get("source"),
            "canonical_listing_id": right_ref.get("canonical_listing_id"),
            "source_listing_id": right_ref.get("source_listing_id"),
            "vin_claim": right_ref.get("vin_claim"),
        },
    }


def build_duplicate_candidates(
    *,
    root: Path,
    config: dict[str, Any],
    run_id: str,
    identity_records: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    records = list(identity_records)
    candidates: list[dict[str, Any]] = []
    for left_index, left in enumerate(records):
        for right in records[left_index + 1 :]:
            candidate = _candidate_for_pair(
                left,
                right,
                vehicle_key=str(config["vehicle_key"]),
                run_id=run_id,
            )
            if candidate is not None:
                candidates.append(candidate)
    candidates.sort(
        key=lambda value: (str(value["confidence"]), str(value["candidate_id"]))
    )
    path = duplicate_candidate_path(root, config)
    write_jsonl(path, candidates)
    return {
        "identity_lifecycle_schema_version": IDENTITY_LIFECYCLE_SCHEMA_VERSION,
        "run_id": run_id,
        "vehicle_key": config["vehicle_key"],
        "candidate_count": len(candidates),
        "high_confidence_count": sum(
            value["confidence"] == "high" for value in candidates
        ),
        "medium_confidence_count": sum(
            value["confidence"] == "medium" for value in candidates
        ),
        "low_confidence_count": sum(
            value["confidence"] == "low" for value in candidates
        ),
        "artifact": str(path.relative_to(root)),
        "candidates": candidates,
    }


def candidate_index(
    candidates: Iterable[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        for side in ("left", "right"):
            canonical_id = str(
                candidate.get(side, {}).get("canonical_listing_id") or ""
            )
            if canonical_id:
                result.setdefault(canonical_id, []).append(candidate)
    return result
