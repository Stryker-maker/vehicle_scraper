from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from canonical_evidence import (
    EVIDENCE_SCHEMA_VERSION,
    _normalized_record,
    canonical_artifact_paths,
    write_jsonl,
)
from kijiji_adapter import ADAPTER_SCHEMA_VERSION, artifact_paths
from phase1_common import utc_now


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} is not a JSON object")
            records.append(value)
    return records


def _minimal_rejected_record(
    *,
    config: dict[str, Any],
    run_id: str,
    adapter_record: dict[str, Any],
    raw_ref: str,
    reasons: list[str],
) -> dict[str, Any]:
    index = int(adapter_record["source_record_index"])
    raw_payload = adapter_record.get("raw_payload")
    raw_id = None
    if isinstance(raw_payload, dict):
        raw_id = raw_payload.get("sku") or raw_payload.get("productID")
    return {
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "record_stage": "rejected",
        "vehicle_key": str(config["vehicle_key"]),
        "source": "kijiji",
        "run_id": run_id,
        "source_record_index": index,
        "canonical_listing_id": None,
        "observation_id": None,
        "source_listing_id": None if raw_id is None else str(raw_id),
        "source_listing_id_status": (
            "source_identifier_claim_not_vin" if raw_id else "unknown"
        ),
        "source_claim_status": "unverified_source_claims",
        "raw_record_ref": raw_ref,
        "normalized_record_ref": None,
        "normalized": {},
        "field_evidence": {},
        "quality_warnings": [],
        "rejection_reasons": reasons,
        "source_adapter_record_ref": adapter_record.get(
            "source_adapter_record_ref"
        ),
        "query_provenance": adapter_record.get("provenance", {}),
    }


def build_kijiji_canonical_evidence(
    *,
    root: Path,
    config: dict[str, Any],
    run_id: str,
    completed_at_utc: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    adapter_paths = artifact_paths(root, config)
    report = json.loads(
        adapter_paths["reconciliation"].read_text(encoding="utf-8")
    )
    if not isinstance(report, dict):
        raise ValueError("Kijiji adapter reconciliation must be a JSON object")
    if report.get("adapter_schema_version") != ADAPTER_SCHEMA_VERSION:
        raise ValueError("Unsupported Kijiji adapter schema version")
    if report.get("run_id") != run_id:
        raise ValueError("Kijiji adapter reconciliation run_id mismatch")
    if (
        report.get("vehicle_key") != config["vehicle_key"]
        or report.get("source") != "kijiji"
    ):
        raise ValueError("Kijiji adapter reconciliation identity mismatch")
    if report.get("reconciled") is not True:
        raise ValueError("Kijiji adapter records are not reconciled")

    adapter_records = _read_jsonl(adapter_paths["records"])
    if int(report.get("fetched_records", -1)) != len(adapter_records):
        raise ValueError(
            "Kijiji adapter fetched count does not match records artifact"
        )

    canonical_paths = canonical_artifact_paths(root, config, "kijiji")
    relative = {
        name: str(path.relative_to(root)) for name, path in canonical_paths.items()
    }
    adapter_relative = {
        name: str(path.relative_to(root)) for name, path in adapter_paths.items()
    }
    completed_at_utc = completed_at_utc or utc_now()
    raw_records: list[dict[str, Any]] = []
    normalized_records: list[dict[str, Any]] = []
    accepted_records: list[dict[str, Any]] = []
    rejected_records: list[dict[str, Any]] = []
    parse_failures: list[dict[str, Any]] = []

    for expected_index, adapter_record in enumerate(adapter_records):
        if adapter_record.get("adapter_schema_version") != ADAPTER_SCHEMA_VERSION:
            raise ValueError(f"Adapter record {expected_index} schema mismatch")
        if adapter_record.get("run_id") != run_id:
            raise ValueError(f"Adapter record {expected_index} run_id mismatch")
        index = int(adapter_record.get("source_record_index", -1))
        if index != expected_index:
            raise ValueError(
                f"Adapter record index discontinuity at {expected_index}"
            )
        adapter_ref = (
            f"{adapter_relative['records']}#source_record_index={index}"
        )
        adapter_record["source_adapter_record_ref"] = adapter_ref
        raw_record = {
            "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
            "record_stage": "raw",
            "vehicle_key": str(config["vehicle_key"]),
            "source": "kijiji",
            "run_id": run_id,
            "source_record_index": index,
            "source_row_number": None,
            "observed_at_utc": completed_at_utc,
            "raw_values": adapter_record.get("raw_payload"),
            "query_provenance": adapter_record.get("provenance", {}),
            "source_adapter_record_ref": adapter_ref,
        }
        raw_records.append(raw_record)
        raw_ref = f"{relative['raw']}#record={index}"
        normalized_ref = (
            f"{relative['normalized']}#source_record_index={index}"
        )
        stage = adapter_record.get("record_stage")

        if stage == "parse_failure":
            reasons = [
                str(value)
                for value in adapter_record.get("parse_failure_reasons", [])
            ]
            parse_failures.append(
                {
                    **raw_record,
                    "record_stage": "parse_failure",
                    "parse_failure_reasons": reasons
                    or ["adapter_parse_failure_without_reason"],
                    "raw_record_ref": raw_ref,
                }
            )
            continue

        parsed_row = adapter_record.get("parsed_row")
        adapter_rejections = [
            str(value)
            for value in adapter_record.get("rejection_reasons", [])
        ]
        if not isinstance(parsed_row, dict):
            if stage != "rejected":
                raise ValueError(
                    f"Adapter record {index} lacks parsed_row for stage {stage}"
                )
            rejected_records.append(
                _minimal_rejected_record(
                    config=config,
                    run_id=run_id,
                    adapter_record=adapter_record,
                    raw_ref=raw_ref,
                    reasons=adapter_rejections
                    or ["adapter_rejection_without_parsed_row"],
                )
            )
            continue

        location_status = str(
            parsed_row.get("location_evidence_status") or "unknown"
        )
        if not parsed_row.get("location") and location_status != "unknown":
            raise ValueError(
                f"Kijiji record {index} has location status without location"
            )
        if (
            parsed_row.get("location")
            and location_status
            != "source_reported_listing_specific_unverified"
        ):
            raise ValueError(
                f"Kijiji record {index} has unsupported location evidence status"
            )

        record = _normalized_record(
            row=parsed_row,
            config=config,
            source="kijiji",
            run_id=run_id,
            source_record_index=index,
            raw_ref=raw_ref,
            normalized_ref=normalized_ref,
        )
        record["source_adapter_record_ref"] = adapter_ref
        record["query_provenance"] = adapter_record.get("provenance", {})

        # Audit 03 quarantined all Kijiji geography because the legacy source
        # copied query origin into listing fields. The direct adapter emits
        # geography only from listing-specific structured source data.
        actual_location = parsed_row.get("location") or None
        actual_address = parsed_row.get("dealer_address") or None
        address_status = str(
            parsed_row.get("dealer_address_evidence_status") or "unknown"
        )
        record["normalized"]["location"] = actual_location
        record["normalized"]["dealer_address"] = actual_address
        record["normalized"]["distance_km"] = None
        record["normalized"]["distance_method"] = str(
            parsed_row.get("distance_method")
            or "disabled_listing_location_not_routed"
        )
        record["field_evidence"]["location"] = {
            "source_field": "location",
            "raw_value": parsed_row.get("location"),
            "normalized_value": actual_location,
            "evidence_status": location_status,
        }
        record["field_evidence"]["dealer_address"] = {
            "source_field": "dealer_address",
            "raw_value": parsed_row.get("dealer_address"),
            "normalized_value": actual_address,
            "evidence_status": address_status,
        }
        distance_status = str(
            parsed_row.get("distance_evidence_status")
            or "disabled_no_verified_route"
        )
        record["field_evidence"]["distance_km"] = {
            "source_field": "distance_km",
            "raw_value": parsed_row.get("distance_km"),
            "normalized_value": None,
            "evidence_status": distance_status,
        }
        record["field_evidence"]["distance_method"] = {
            "source_field": "distance_method",
            "raw_value": parsed_row.get("distance_method"),
            "normalized_value": record["normalized"]["distance_method"],
            "evidence_status": distance_status,
        }
        combined_rejections = sorted(
            set(record["rejection_reasons"] + adapter_rejections)
        )
        record["rejection_reasons"] = combined_rejections
        normalized_records.append({**record, "record_stage": "normalized"})
        if stage == "rejected" or combined_rejections:
            rejected_records.append({**record, "record_stage": "rejected"})
        elif stage == "accepted":
            accepted_records.append({**record, "record_stage": "accepted"})
        else:
            raise ValueError(f"Unsupported adapter record stage: {stage}")

    fetched = len(raw_records)
    reconciled = fetched == (
        len(accepted_records) + len(rejected_records) + len(parse_failures)
    )
    expected = {
        "accepted_records": len(accepted_records),
        "rejected_records": len(rejected_records),
        "parse_failures": len(parse_failures),
    }
    if any(
        int(report.get(name, -1)) != count
        for name, count in expected.items()
    ):
        reconciled = False
    listing_locations = sum(
        record.get("field_evidence", {})
        .get("location", {})
        .get("evidence_status")
        == "source_reported_listing_specific_unverified"
        for record in [*accepted_records, *rejected_records]
    )
    reconciliation = {
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "source_adapter_schema_version": ADAPTER_SCHEMA_VERSION,
        "location_registry_version": report.get("location_registry_version"),
        "vehicle_key": str(config["vehicle_key"]),
        "source": "kijiji",
        "run_id": run_id,
        "generated_at_utc": utc_now(),
        "fetched_record_scope": report.get("fetched_record_scope"),
        "source_fetch_completeness": report.get("source_fetch_completeness"),
        "query_location_count": int(report.get("query_location_count", 0)),
        "page_request_count": int(report.get("page_request_count", 0)),
        "request_attempt_count": int(report.get("request_attempt_count", 0)),
        "successful_page_count": int(report.get("successful_page_count", 0)),
        "failed_page_count": int(report.get("failed_page_count", 0)),
        "pagination_complete": report.get("pagination_complete") is True,
        "fetched_records": fetched,
        "normalized_records": len(normalized_records),
        "accepted_records": len(accepted_records),
        "rejected_records": len(rejected_records),
        "parse_failures": len(parse_failures),
        "listing_specific_location_records": listing_locations,
        "unknown_location_records": fetched - listing_locations,
        "reconciled": reconciled,
        "reconciliation_equation": (
            "fetched_records = accepted_records + rejected_records + parse_failures"
        ),
        "artifacts": relative,
        "source_adapter_artifacts": adapter_relative,
    }
    write_jsonl(canonical_paths["raw"], raw_records)
    write_jsonl(canonical_paths["normalized"], normalized_records)
    write_jsonl(canonical_paths["accepted"], accepted_records)
    write_jsonl(canonical_paths["rejected"], rejected_records)
    write_jsonl(canonical_paths["parse_failures"], parse_failures)
    canonical_paths["reconciliation"].parent.mkdir(
        parents=True, exist_ok=True
    )
    temporary = canonical_paths["reconciliation"].with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(reconciliation, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(canonical_paths["reconciliation"])
    return reconciliation
