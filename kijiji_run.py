from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from baseline_compatibility import build_compatibility_fingerprint
from canonical_evidence import EVIDENCE_SCHEMA_VERSION
from identity_lifecycle import (
    IDENTITY_LIFECYCLE_SCHEMA_VERSION,
    restore_artifacts,
    snapshot_artifacts,
    update_source_identity_lifecycle,
)
from kijiji_adapter import ADAPTER_SCHEMA_VERSION
from kijiji_canonical import build_kijiji_canonical_evidence
from kijiji_locations import LOCATION_REGISTRY_VERSION
from phase1_common import (
    DEFAULT_TIMEOUT_SECONDS,
    analyze_csv_quality,
    expected_output_path,
    file_signature,
    source_status_path,
    utc_now,
    validate_csv,
    write_json,
)
from phase1_source_runner_common import (
    assess_source_output,
    build_source_evidence_and_identity,
    collector_quality_report,
    collector_status_name,
    execute_source_collector,
    finalize_source_status_from_context,
    print_source_summary,
    resolve_collector_command,
    restore_config_if_mutated,
    restore_identity_if_unhealthy,
    snapshot_archive_signatures,
    snapshot_reconciliation_signature,
    source_evidence_status_fields,
    source_execution_outcome_fields,
    source_runtime_contract_fields,
    source_schema_version_fields,
    source_status_identity_fields,
    source_status_metrics_from_context,
    validate_collection_scope,
)
from vehicle_config import CONFIG_SCHEMA_VERSION, load_vehicle_config

SOURCE_STATUS_SCHEMA_VERSION = 8
COLLECTION_SCOPE = "full"
VALID_COLLECTION_SCOPES = ("full", "single_pair")


def run_kijiji(
    *,
    root: Path,
    config_path: Path,
    command: Sequence[str] | None = None,
    run_id: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    root = root.resolve()
    config_path = root / config_path
    original_config = config_path.read_bytes()
    config = load_vehicle_config(config_path)
    collection_scope = os.environ.get("COLLECTION_SCOPE", COLLECTION_SCOPE)
    validate_collection_scope(collection_scope, VALID_COLLECTION_SCOPES)
    compatibility_identity, compatibility_fingerprint = build_compatibility_fingerprint(
        config=config,
        source="kijiji",
        collection_scope=collection_scope,
        adapter_schema_version=ADAPTER_SCHEMA_VERSION,
    )
    active_run = run_id or os.environ.get("GITHUB_RUN_ID", "local")
    output_path = expected_output_path(root, config, "kijiji")
    status_path = source_status_path(root, config, "kijiji")
    identity_before = snapshot_artifacts(root, config, "kijiji")
    rec_path = root / "data" / config["vehicle_key"] / "adapter_evidence" / "kijiji" / "reconciliation_latest.json"
    rec_before_sig = snapshot_reconciliation_signature(rec_path)
    archive_dir = root / "data" / config["vehicle_key"] / "kijiji"
    archive_before_sigs = snapshot_archive_signatures(archive_dir)
    before_signature = file_signature(output_path)
    started_at = utc_now()
    started_ns = time.time_ns()
    command = resolve_collector_command(
        command,
        [
            sys.executable,
            "kijiji_adapter.py",
            "--config",
            str(config_path.relative_to(root)),
        ],
    )

    returncode, timed_out, stdout, stderr = execute_source_collector(
        command,
        root=root,
        timeout_seconds=timeout_seconds,
        subprocess_module=subprocess,
    )

    (
        fresh,
        validation,
        observed_rows,
        current_rows,
        stale_rows,
        failures,
    ) = assess_source_output(
        output_path,
        before_signature=before_signature,
        started_ns=started_ns,
        returncode=returncode,
        timed_out=timed_out,
        file_signature_func=file_signature,
        validate_csv_func=validate_csv,
    )

    completed_at = utc_now()
    evidence, evidence_error, identity, identity_error = build_source_evidence_and_identity(
        root=root,
        config=config,
        source="kijiji",
        active_run=active_run,
        completed_at=completed_at,
        fresh=fresh,
        validation=validation,
        current_rows=current_rows,
        failures=failures,
        adapter_schema_version=ADAPTER_SCHEMA_VERSION,
        evidence_schema_version=EVIDENCE_SCHEMA_VERSION,
        build_canonical_evidence=build_kijiji_canonical_evidence,
        update_identity=update_source_identity_lifecycle,
        additional_evidence_defaults={
            "query_location_count": 0,
            "listing_specific_location_records": 0,
            "unknown_location_records": 0,
        },
    )

    config_isolated = restore_config_if_mutated(
        config_path, original_config, failures
    )
    status_name = collector_status_name(timed_out, returncode, failures)
    restore_identity_if_unhealthy(status_name, identity_before, restore_artifacts)

    quality = collector_quality_report(
        output_path,
        "kijiji",
        fresh,
        validation["schema_valid"],
        stale_rows,
        analyze_csv_quality_func=analyze_csv_quality,
    )

    status = {
        "schema_version": SOURCE_STATUS_SCHEMA_VERSION,
        "location_registry_version": LOCATION_REGISTRY_VERSION,
        "distance_processing_disabled": True,
        "distance_filter_disabled": True,
        "location_evidence_contract": (
            "listing_specific_source_geography_or_unknown_"
            "query_origin_never_location"
        ),
        "distance_evidence_contract": (
            "disabled_until_listing_specific_geography_is_routable_and_verified"
        ),
        "query_location_count": int(evidence.get("query_location_count", 0)),
        "listing_specific_location_record_count": int(
            evidence.get("listing_specific_location_records", 0)
        ),
        "unknown_location_record_count": int(
            evidence.get("unknown_location_records", 0)
        ),
        "canonical_evidence_artifacts": evidence.get("artifacts", {}),
        **{**validation, "row_count": current_rows},
        **quality,
    }
    status.update(source_status_identity_fields(locals(), source="kijiji"))
    status.update(
        source_schema_version_fields(
            config_schema_version=CONFIG_SCHEMA_VERSION,
            evidence_schema_version=EVIDENCE_SCHEMA_VERSION,
            adapter_schema_version=ADAPTER_SCHEMA_VERSION,
            identity_schema_version=IDENTITY_LIFECYCLE_SCHEMA_VERSION,
        )
    )
    status.update(source_status_metrics_from_context(locals()))
    status.update(source_evidence_status_fields(locals()))
    status.update(source_runtime_contract_fields(locals()))
    status.update(source_execution_outcome_fields(locals()))
    finalize_source_status_from_context(status, locals(), source="kijiji")
    write_json(status_path, status)
    print_source_summary(config["vehicle_key"], "kijiji", status_name, status)
    return status


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Run the direct Kijiji adapter with bounded status evidence"
    )
    result.add_argument("--config", required=True)
    result.add_argument(
        "--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS
    )
    result.add_argument("--fail-on-unhealthy", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    status = run_kijiji(
        root=Path.cwd(),
        config_path=Path(args.config),
        timeout_seconds=args.timeout_seconds,
    )
    return (
        1
        if args.fail_on_unhealthy
        and status["execution_status"] != "success"
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
