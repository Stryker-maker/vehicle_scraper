from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from autotrader_adapter import ADAPTER_SCHEMA_VERSION, artifact_paths
from canonical_evidence import (
    EVIDENCE_SCHEMA_VERSION, _normalized_record, canonical_artifact_paths,
    write_jsonl,
)
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
    *, config: dict[str, Any], run_id: str, adapter_record: dict[str, Any],
    raw_ref: str, reasons: list[str],
) -> dict[str, Any]:
    index = int(adapter_record["source_record_index"])
    raw_payload = adapter_record.get("raw_payload")
    raw_id = raw_payload.get("id") if isinstance(raw_payload, dict) else None
    return {
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "record_stage": "rejected",
        "vehicle_key": str(config["vehicle_key"]),
        "source": "autotrader",
        "run_id": run_id,
        "source_record_index": index,
        "canonical_listing_id": None,
        "observation_id": None,
        "source_listing_id": None if raw_id is None else str(raw_id),
        "source_listing_id_status": "source_identifier_claim_not_vin" if raw_id else "unknown",
        "source_claim_status": "unverified_source_claims",
        "raw_record_ref": raw_ref,
        "normalized_record_ref": None,
        "normalized": {},
        "field_evidence": {},
        "quality_warnings": [],
        "rejection_reasons": reasons,
        "source_adapter_record_ref": adapter_record.get("source_adapter_record_ref"),
    }


def build_autotrader_canonical_evidence(
    *, root: Path, config: dict[str, Any], run_id: str,
    completed_at_utc: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    adapter_paths = artifact_paths(root, config)
    report = json.loads(adapter_paths["reconciliation"].read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("AutoTrader adapter reconciliation must be a JSON object")
    if report.get("adapter_schema_version") != ADAPTER_SCHEMA_VERSION:
        raise ValueError("Unsupported AutoTrader adapter schema version")
    if report.get("run_id") != run_id:
        raise ValueError("AutoTrader adapter reconciliation run_id mismatch")
    if report.get("vehicle_key") != config["vehicle_key"] or report.get("source") != "autotrader":
        raise ValueError("AutoTrader adapter reconciliation identity mismatch")
    if report.get("reconciled") is not True:
        raise ValueError("AutoTrader adapter records are not reconciled")

    adapter_records = _read_jsonl(adapter_paths["records"])
    expected_fetched = int(report.get("fetched_records", -1))
    if expected_fetched != len(adapter_records):
        raise ValueError("AutoTrader adapter fetched count does not match records artifact")

    canonical_paths = canonical_artifact_paths(root, config, "autotrader")
    relative = {name: str(path.relative_to(root)) for name, path in canonical_paths.items()}
    adapter_relative = {name: str(path.relative_to(root)) for name, path in adapter_paths.items()}
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
            raise ValueError(f"Adapter record index discontinuity at {expected_index}")
        adapter_ref = f"{adapter_relative['records']}#source_record_index={index}"
        adapter_record["source_adapter_record_ref"] = adapter_ref
        raw_record = {
            "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
            "record_stage": "raw",
            "vehicle_key": str(config["vehicle_key"]),
            "source": "autotrader",
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
        normalized_ref = f"{relative['normalized']}#source_record_index={index}"
        stage = adapter_record.get("record_stage")

        if stage == "parse_failure":
            reasons = [str(value) for value in adapter_record.get("parse_failure_reasons", [])]
            parse_failures.append({
                **raw_record,
                "record_stage": "parse_failure",
                "parse_failure_reasons": reasons or ["adapter_parse_failure_without_reason"],
                "raw_record_ref": raw_ref,
            })
            continue

        parsed_row = adapter_record.get("parsed_row")
        adapter_rejections = [str(value) for value in adapter_record.get("rejection_reasons", [])]
        if not isinstance(parsed_row, dict):
            if stage != "rejected":
                raise ValueError(f"Adapter record {index} lacks parsed_row for stage {stage}")
            rejected_records.append(_minimal_rejected_record(
                config=config, run_id=run_id, adapter_record=adapter_record,
                raw_ref=raw_ref,
                reasons=adapter_rejections or ["adapter_rejection_without_parsed_row"],
            ))
            continue

        record = _normalized_record(
            row=parsed_row, config=config, source="autotrader", run_id=run_id,
            source_record_index=index, raw_ref=raw_ref, normalized_ref=normalized_ref,
        )
        record["source_adapter_record_ref"] = adapter_ref
        record["query_provenance"] = adapter_record.get("provenance", {})
        combined_rejections = sorted(set(record["rejection_reasons"] + adapter_rejections))
        record["rejection_reasons"] = combined_rejections
        normalized_records.append({**record, "record_stage": "normalized"})
        if stage == "rejected" or combined_rejections:
            rejected_records.append({**record, "record_stage": "rejected"})
        elif stage == "accepted":
            accepted_records.append({**record, "record_stage": "accepted"})
        else:
            raise ValueError(f"Unsupported adapter record stage: {stage}")

    fetched_records = len(raw_records)
    reconciled = fetched_records == (
        len(accepted_records) + len(rejected_records) + len(parse_failures)
    )
    if len(accepted_records) != int(report.get("accepted_records", -1)):
        reconciled = False
    if len(rejected_records) != int(report.get("rejected_records", -1)):
        reconciled = False
    if len(parse_failures) != int(report.get("parse_failures", -1)):
        reconciled = False

    reconciliation = {
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "source_adapter_schema_version": ADAPTER_SCHEMA_VERSION,
        "vehicle_key": str(config["vehicle_key"]),
        "source": "autotrader",
        "run_id": run_id,
        "generated_at_utc": utc_now(),
        "fetched_record_scope": report.get("fetched_record_scope"),
        "source_fetch_completeness": report.get("source_fetch_completeness"),
        "page_request_count": int(report.get("page_request_count", 0)),
        "request_attempt_count": int(report.get("request_attempt_count", 0)),
        "successful_page_count": int(report.get("successful_page_count", 0)),
        "failed_page_count": int(report.get("failed_page_count", 0)),
        "pagination_complete": report.get("pagination_complete") is True,
        "fetched_records": fetched_records,
        "normalized_records": len(normalized_records),
        "accepted_records": len(accepted_records),
        "rejected_records": len(rejected_records),
        "parse_failures": len(parse_failures),
        "reconciled": reconciled,
        "reconciliation_equation": "fetched_records = accepted_records + rejected_records + parse_failures",
        "artifacts": relative,
        "source_adapter_artifacts": adapter_relative,
    }
    write_jsonl(canonical_paths["raw"], raw_records)
    write_jsonl(canonical_paths["normalized"], normalized_records)
    write_jsonl(canonical_paths["accepted"], accepted_records)
    write_jsonl(canonical_paths["rejected"], rejected_records)
    write_jsonl(canonical_paths["parse_failures"], parse_failures)
    canonical_paths["reconciliation"].parent.mkdir(parents=True, exist_ok=True)
    temporary = canonical_paths["reconciliation"].with_suffix(".json.tmp")
    temporary.write_text(json.dumps(reconciliation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(canonical_paths["reconciliation"])
    return reconciliation
