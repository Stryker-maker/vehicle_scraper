from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from autotrader_adapter import ADAPTER_SCHEMA_VERSION
from autotrader_canonical import build_autotrader_canonical_evidence
from baseline_compatibility import build_compatibility_fingerprint
from canonical_evidence import EVIDENCE_SCHEMA_VERSION
from identity_lifecycle import (
    IDENTITY_LIFECYCLE_SCHEMA_VERSION,
    restore_artifacts,
    snapshot_artifacts,
    update_source_identity_lifecycle,
)
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
    build_source_status,
    collector_quality_report,
    collector_status_name,
    execute_source_collector,
    resolve_collector_command,
    restore_config_if_mutated,
    restore_identity_if_unhealthy,
    snapshot_archive_signatures,
    snapshot_reconciliation_signature,
    source_status_decision_fields,
    validate_collection_scope,
)
from vehicle_config import CONFIG_SCHEMA_VERSION, load_vehicle_config

SOURCE_STATUS_SCHEMA_VERSION = 8
COLLECTION_SCOPE = "full"
VALID_COLLECTION_SCOPES = ("full", "single_pair")


def run_autotrader(
    *, root: Path, config_path: Path, command: Sequence[str] | None = None,
    run_id: str | None = None, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    root = root.resolve()
    config_path = root / config_path
    original_config = config_path.read_bytes()
    config = load_vehicle_config(config_path)
    collection_scope = os.environ.get("COLLECTION_SCOPE", COLLECTION_SCOPE)
    validate_collection_scope(collection_scope, VALID_COLLECTION_SCOPES)
    compatibility_identity, compatibility_fingerprint = build_compatibility_fingerprint(
        config=config,
        source="autotrader",
        collection_scope=collection_scope,
        adapter_schema_version=ADAPTER_SCHEMA_VERSION,
    )
    active_run = run_id or os.environ.get("GITHUB_RUN_ID", "local")
    output_path = expected_output_path(root, config, "autotrader")
    status_path = source_status_path(root, config, "autotrader")
    identity_before = snapshot_artifacts(root, config, "autotrader")
    rec_path = root / "data" / config["vehicle_key"] / "adapter_evidence" / "autotrader" / "reconciliation_latest.json"
    rec_before_sig = snapshot_reconciliation_signature(rec_path)
    archive_dir = root / "data" / config["vehicle_key"] / "autotrader"
    archive_before_sigs = snapshot_archive_signatures(archive_dir)
    before_signature = file_signature(output_path)
    started_at = utc_now()
    started_ns = time.time_ns()
    command = resolve_collector_command(
        command,
        [
            sys.executable,
            "autotrader_adapter.py",
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
        source="autotrader",
        active_run=active_run,
        completed_at=completed_at,
        fresh=fresh,
        validation=validation,
        current_rows=current_rows,
        failures=failures,
        adapter_schema_version=ADAPTER_SCHEMA_VERSION,
        evidence_schema_version=EVIDENCE_SCHEMA_VERSION,
        build_canonical_evidence=build_autotrader_canonical_evidence,
        update_identity=update_source_identity_lifecycle,
    )

    config_isolated = restore_config_if_mutated(
        config_path, original_config, failures
    )

    status_name = collector_status_name(timed_out, returncode, failures)
    restore_identity_if_unhealthy(status_name, identity_before, restore_artifacts)

    quality = collector_quality_report(
        output_path,
        "autotrader",
        fresh,
        validation["schema_valid"],
        stale_rows,
        analyze_csv_quality_func=analyze_csv_quality,
    )

    status = build_source_status(
        source="autotrader",
        status_schema_version=SOURCE_STATUS_SCHEMA_VERSION,
        config_schema_version=CONFIG_SCHEMA_VERSION,
        evidence_schema_version=EVIDENCE_SCHEMA_VERSION,
        adapter_schema_version=ADAPTER_SCHEMA_VERSION,
        identity_schema_version=IDENTITY_LIFECYCLE_SCHEMA_VERSION,
        active_run=active_run,
        config=config,
        collection_scope=collection_scope,
        compatibility_identity=compatibility_identity,
        compatibility_fingerprint=compatibility_fingerprint,
        config_path=config_path,
        root=root,
        command=command,
        started_at=started_at,
        completed_at=completed_at,
        status_name=status_name,
        returncode=returncode,
        timed_out=timed_out,
        timeout_seconds=timeout_seconds,
        failures=failures,
        output_path=output_path,
        fresh=fresh,
        current_rows=current_rows,
        stale_rows=stale_rows,
        observed_rows=observed_rows,
        config_isolated=config_isolated,
        evidence=evidence,
        evidence_error=evidence_error,
        identity_error=identity_error,
        identity=identity,
        validation=validation,
        quality=quality,
        stdout=stdout,
        stderr=stderr,
        source_fields={
            "distance_processing_disabled": False,
            "distance_filter_disabled": False,
            "distance_evidence_contract": (
                "explicit_route_api_or_geodesic_or_unavailable"
            ),
        },
    )
    status.update(
        source_status_decision_fields(
            root=root,
            config=config,
            source="autotrader",
            active_run=active_run,
            started_ns=started_ns,
            rec_before_sig=rec_before_sig,
            archive_before_sigs=archive_before_sigs,
            fresh=fresh,
            output_path=output_path,
            status_name=status_name,
            identity_error=identity_error,
            evidence=evidence,
        )
    )
    write_json(status_path, status)
    print(
        f"[{config['vehicle_key']}:autotrader] {status_name} | fetched={status['fetched_record_count']} "
        f"| accepted={status['accepted_record_count']} | rejected={status['rejected_record_count']} "
        f"| parse_failures={status['parse_failure_count']} "
        f"| lifecycle={status['identity_lifecycle_status']} "
        f"| new={status['identity_new_listing_count']} "
        f"| reappeared={status['identity_reappeared_listing_count']}"
    )
    return status


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Run the direct AutoTrader adapter with bounded status evidence"
    )
    result.add_argument("--config", required=True)
    result.add_argument(
        "--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS
    )
    result.add_argument("--fail-on-unhealthy", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    status = run_autotrader(
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
