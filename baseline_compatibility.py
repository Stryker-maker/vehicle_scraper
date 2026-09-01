from __future__ import annotations

import hashlib
import json
from typing import Any

from canonical_evidence import EVIDENCE_SCHEMA_VERSION
from kijiji_locations import LOCATION_REGISTRY_VERSION
from vehicle_config import CONFIG_SCHEMA_VERSION

COMPATIBILITY_SCHEMA_VERSION = 1


def _canonical_json(value: Any) -> str:
    """Serialize a compatibility value deterministically for hashing."""
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


def _canonical_locations(values: list[str]) -> list[str]:
    """Return query locations in canonical, order-independent form."""
    return sorted((str(value) for value in values), key=str.casefold)


def build_compatibility_identity(
    *,
    config: dict[str, Any],
    source: str,
    collection_scope: str,
    adapter_schema_version: int,
) -> dict[str, Any]:
    """Build the semantic collection contract used for baseline comparison."""
    if source not in config.get("sources", {}):
        raise ValueError(f"Unsupported source for compatibility: {source!r}")

    source_config = dict(config["sources"][source])
    locations = _canonical_locations(source_config["search_locations"])
    source_config["search_locations"] = locations
    config_identity = {
        "schema_version": config["schema_version"],
        "vehicle_key": config["vehicle_key"],
        "make": config["make"],
        "model": config["model"],
        "criteria": config["criteria"],
        "origin": config["origin"],
        "source": source,
        "source_config": source_config,
    }
    identity: dict[str, Any] = {
        "compatibility_schema_version": COMPATIBILITY_SCHEMA_VERSION,
        "vehicle": str(config["vehicle_key"]),
        "source": source,
        "collection_scope": collection_scope,
        "query_locations": locations,
        "query_location_count": len(locations),
        "configuration_schema_version": CONFIG_SCHEMA_VERSION,
        "config_identity": config_identity,
        "location_registry_version": (
            LOCATION_REGISTRY_VERSION if source == "kijiji" else None
        ),
        "adapter_schema_version": adapter_schema_version,
        "canonical_evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
    }
    return identity


def compatibility_fingerprint(identity: dict[str, Any]) -> str:
    """Return the SHA-256 fingerprint of a compatibility identity."""
    return hashlib.sha256(_canonical_json(identity).encode("utf-8")).hexdigest()


def build_compatibility_fingerprint(
    *,
    config: dict[str, Any],
    source: str,
    collection_scope: str,
    adapter_schema_version: int,
) -> tuple[dict[str, Any], str]:
    """Build and fingerprint a deterministic semantic collection contract."""
    identity = build_compatibility_identity(
        config=config,
        source=source,
        collection_scope=collection_scope,
        adapter_schema_version=adapter_schema_version,
    )
    return identity, compatibility_fingerprint(identity)
