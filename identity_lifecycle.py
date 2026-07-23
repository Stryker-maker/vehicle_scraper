from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from canonical_evidence import read_jsonl, write_jsonl
from phase1_common import SOURCES, write_json

IDENTITY_LIFECYCLE_SCHEMA_VERSION = 1
RETIRE_AFTER_CONSECUTIVE_MISSES = 3
RETIRE_AFTER_MISSING_DAYS = 14.0
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


def snapshot_artifacts(root: Path, config: dict[str, Any], source: str) -> dict[str, bytes | None]:
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


def _price_summary(observations: list[dict[str, Any]]) -> dict[str, Any]:
    first = observations[0].get("price_cad") if observations else None
    current = observations[-1].get("price_cad") if observations else None
    previous = observations[-2].get("price_cad") if len(observations) > 1 else None
    return {
        "price_observation_count": len(observations),
        "first_observed_price_cad": first,
        "previous_observation_price_cad": previous,
        "current_price_cad": current,
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
        key: value
        for key, value in listing.items()
        if key != "price_observations"
    }
    projection["identity_lifecycle_schema_version"] = IDENTITY_LIFECYCLE_SCHEMA_VERSION
    projection["run_id"] = run_id
    projection["record_stage"] = "current_identity_lifecycle"
    return projection


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
    if paths["state"].exists():
        loaded = json.loads(paths["state"].read_text(encoding="utf-8"))
        if (
            isinstance(loaded, dict)
            and loaded.get("identity_lifecycle_schema_version")
            == IDENTITY_LIFECYCLE_SCHEMA_VERSION
            and loaded.get("vehicle_key") == config["vehicle_key"]
            and loaded.get("source") == source
        ):
            previous = loaded
    listings = {
        str(key): dict(value)
        for key, value in previous.get("listings", {}).items()
        if isinstance(value, dict)
    }
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
            observations: list[dict[str, Any]] = []
            reappearance_count = 0
        else:
            first_seen = str(old["first_seen_at_utc"])
            observations = [
                dict(value)
                for value in old.get("price_observations", [])
                if isinstance(value, dict) and value.get("run_id") != run_id
            ]
            reappearance_count = int(old.get("reappearance_count", 0))
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

        normalized = record.get("normalized", {})
        price = normalized.get("price_cad")
        observations.append(
            {
                "run_id": run_id,
                "observed_at_utc": observed_at_utc,
                "price_cad": price if isinstance(price, int) else None,
            }
        )
        observations.sort(key=lambda value: (str(value.get("observed_at_utc")), str(value.get("run_id"))))
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
            "observation_count": len(observations),
            "successful_seen_run_count": len(observations),
            "missing_run_count": 0,
            "reappearance_count": reappearance_count,
            "elapsed_since_first_seen_seconds": elapsed_seconds,
            "elapsed_since_first_seen_days": elapsed_days,
            "elapsed_since_last_seen_seconds": 0,
            "elapsed_since_last_seen_days": 0.0,
            "price_observations": observations,
            **_price_summary(observations),
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

    state = {
        "identity_lifecycle_schema_version": IDENTITY_LIFECYCLE_SCHEMA_VERSION,
        "vehicle_key": config["vehicle_key"],
        "source": source,
        "last_successful_run_id": run_id,
        "last_successful_run_at_utc": observed_at_utc,
        "successful_source_run_count": successful_source_run_count,
        "retirement_policy": {
            "minimum_consecutive_missing_successful_runs": RETIRE_AFTER_CONSECUTIVE_MISSES,
            "minimum_elapsed_missing_days": RETIRE_AFTER_MISSING_DAYS,
            "meaning": "operational lifecycle inference_not_source_sold_claim",
        },
        "listings": dict(sorted(listings.items())),
    }
    counts = {
        lifecycle: sum(
            listing.get("lifecycle_state") == lifecycle for listing in listings.values()
        )
        for lifecycle in ("active", "reappeared", "missing", "retired")
    }
    relative = {name: str(path.relative_to(root)) for name, path in paths.items()}
    summary = {
        "identity_lifecycle_schema_version": IDENTITY_LIFECYCLE_SCHEMA_VERSION,
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
        "source_identity_contract": "source_scoped_identifier_distinct_from_vin",
        "vin_contract": "source_reported_claim_unverified_never_inferred_from_listing_id",
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
        and left.get("vin_evidence_status") == "source_reported_format_valid_unverified"
        and right.get("vin_evidence_status") == "source_reported_format_valid_unverified"
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
        left_price, right_price = left_components.get("price_cad"), right_components.get("price_cad")
        left_mileage, right_mileage = left_components.get("mileage_km"), right_components.get("mileage_km")
        price_delta = abs(left_price - right_price) if isinstance(left_price, int) and isinstance(right_price, int) else None
        mileage_delta = abs(left_mileage - right_mileage) if isinstance(left_mileage, int) and isinstance(right_mileage, int) else None
        support: list[str] = ["year_make_model_match"]
        if left.get("identity_fingerprint_strict") == right.get("identity_fingerprint_strict"):
            support.append("strict_fingerprint_match")
        if left.get("identity_fingerprint_loose") == right.get("identity_fingerprint_loose"):
            support.append("loose_fingerprint_match")
        if left_components.get("dealer") and left_components.get("dealer") == right_components.get("dealer"):
            support.append("seller_name_match")
        if left_components.get("location") and left_components.get("location") == right_components.get("location"):
            support.append("location_claim_match")
        trim_overlap = set(left_components.get("trim_tokens", [])) & set(right_components.get("trim_tokens", []))
        if trim_overlap:
            support.append("trim_token_overlap")
        if mileage_delta is not None and mileage_delta <= 1000 and price_delta is not None and price_delta <= 1500 and len(support) >= 2:
            confidence, score = "medium", 0.78
            reasons.extend(support + ["mileage_within_1000_km", "price_within_1500_cad"])
        elif mileage_delta is not None and mileage_delta <= 3000 and price_delta is not None and price_delta <= 3000 and len(support) >= 2:
            confidence, score = "low", 0.56
            reasons.extend(support + ["mileage_within_3000_km", "price_within_3000_cad"])
        else:
            return None

    ordered = sorted(
        [left, right], key=lambda value: (str(value.get("source")), str(value.get("canonical_listing_id")))
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
                left, right, vehicle_key=str(config["vehicle_key"]), run_id=run_id
            )
            if candidate is not None:
                candidates.append(candidate)
    candidates.sort(key=lambda value: (str(value["confidence"]), str(value["candidate_id"])))
    path = duplicate_candidate_path(root, config)
    write_jsonl(path, candidates)
    return {
        "identity_lifecycle_schema_version": IDENTITY_LIFECYCLE_SCHEMA_VERSION,
        "run_id": run_id,
        "vehicle_key": config["vehicle_key"],
        "candidate_count": len(candidates),
        "high_confidence_count": sum(value["confidence"] == "high" for value in candidates),
        "medium_confidence_count": sum(value["confidence"] == "medium" for value in candidates),
        "low_confidence_count": sum(value["confidence"] == "low" for value in candidates),
        "artifact": str(path.relative_to(root)),
        "candidates": candidates,
    }


def candidate_index(candidates: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        for side in ("left", "right"):
            canonical_id = str(candidate.get(side, {}).get("canonical_listing_id") or "")
            if canonical_id:
                result.setdefault(canonical_id, []).append(candidate)
    return result
