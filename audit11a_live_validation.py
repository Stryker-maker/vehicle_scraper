from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
RESULT_PATH = ROOT / "AUDIT_11A_F150_LIVE_VALIDATION_RESULT.json"


def run(command: list[str], *, output_path: Path | None = None) -> str:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="")
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(completed.stdout, encoding="utf-8")
    return completed.stdout


def read_status(source: str) -> dict[str, Any]:
    path = ROOT / "data" / "ford_f150" / "run_status" / f"{source}_latest.json"
    if not path.exists():
        return {"status_evidence_present": False}
    status = json.loads(path.read_text(encoding="utf-8"))
    return {
        "status_evidence_present": True,
        "execution_status": status.get("execution_status"),
        "collection_status": status.get("collection_status"),
        "data_quality_status": status.get("data_quality_status"),
        "fetched_record_count": status.get("fetched_record_count"),
        "accepted_record_count": status.get("accepted_record_count"),
        "rejected_record_count": status.get("rejected_record_count"),
        "parse_failure_count": status.get("parse_failure_count"),
        "output_row_count": status.get("output_row_count"),
        "pagination_complete": status.get("pagination_complete"),
        "request_attempt_count": status.get("request_attempt_count"),
        "successful_page_count": status.get("successful_page_count"),
        "failed_page_count": status.get("failed_page_count"),
        "identity_lifecycle_status": status.get("identity_lifecycle_status"),
        "identity_observed_current_count": status.get(
            "identity_observed_current_count"
        ),
        "run_id": status.get("run_id"),
        "status_path": str(path.relative_to(ROOT)),
    }


def write_result(
    *,
    outcomes: dict[str, str],
    error: str | None,
    weekly_runs: list[str],
    manual_runs: list[str],
) -> dict[str, Any]:
    registry = json.loads((ROOT / "vehicle_registry.json").read_text(encoding="utf-8"))
    by_key = {entry["vehicle_key"]: entry for entry in registry["vehicles"]}
    passed = error is None and all(value == "success" for value in outcomes.values())
    result = {
        "schema_version": 1,
        "audit": "11A",
        "validation_status": "success" if passed else "failure",
        "step_outcomes": outcomes,
        "error": error,
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "source_sha": os.environ.get("GITHUB_SHA"),
        "branch": os.environ.get("GITHUB_REF_NAME"),
        "event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "publication_performed": False,
        "weekly_source_run_count": len(weekly_runs),
        "weekly_source_pairs": weekly_runs,
        "manual_source_pairs": manual_runs,
        "ford_f150": {
            "enabled": by_key["ford_f150"]["enabled"],
            "cadence": by_key["ford_f150"]["cadence"],
            "analysis_profile": by_key["ford_f150"]["analysis_profile"],
        },
        "toyota_tundra": {
            "enabled": by_key["toyota_tundra"]["enabled"],
            "pause_reason": by_key["toyota_tundra"].get("pause_reason"),
        },
        "sources": {
            "autotrader": read_status("autotrader"),
            "kijiji": read_status("kijiji"),
        },
        "interpretation": (
            "manual_optional_curiosity_not_rank_not_score_"
            "not_appraisal_not_recommendation"
        ),
    }
    RESULT_PATH.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> int:
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    temp = Path(os.environ.get("RUNNER_TEMP", ROOT / ".tmp-audit11a"))
    temp.mkdir(parents=True, exist_ok=True)
    outcomes = {"cadence": "pending", "autotrader": "pending", "kijiji": "pending"}
    weekly_runs: list[str] = []
    manual_runs: list[str] = []
    error: str | None = None

    try:
        run(["python", "vehicle_registry.py", "validate", "--registry", "vehicle_registry.json"])
        weekly_text = run(
            ["python", "vehicle_registry.py", "weekly-runs", "--registry", "vehicle_registry.json"],
            output_path=temp / "weekly-runs.tsv",
        )
        manual_text = run(
            ["python", "vehicle_registry.py", "manual-runs", "--registry", "vehicle_registry.json"],
            output_path=temp / "manual-runs.tsv",
        )
        weekly_runs = weekly_text.splitlines()
        manual_runs = manual_text.splitlines()
        expected_manual = [
            "config_f150.json\tautotrader",
            "config_f150.json\tkijiji",
        ]
        if len(weekly_runs) != 10:
            raise ValueError(f"Expected 10 weekly source pairs, found {len(weekly_runs)}")
        if any("f150" in row or "tundra" in row for row in weekly_runs):
            raise ValueError("Optional vehicle leaked into weekly plan")
        if manual_runs != expected_manual:
            raise ValueError(f"Unexpected manual plan: {manual_runs!r}")
        outcomes["cadence"] = "success"

        autotrader_plan = temp / "autotrader-plan.tsv"
        run(
            [
                "python",
                "workflow_control.py",
                "plan",
                "--registry",
                "vehicle_registry.json",
                "--scope",
                "single_pair",
                "--cadence",
                "weekly",
                "--vehicle-key",
                "ford_f150",
                "--source",
                "autotrader",
                "--output",
                str(autotrader_plan),
            ]
        )
        if autotrader_plan.read_text(encoding="utf-8").strip() != expected_manual[0]:
            raise ValueError("AutoTrader single-pair plan drifted")
        run(
            [
                "python",
                "autotrader_run.py",
                "--config",
                "config_f150.json",
                "--timeout-seconds",
                "4200",
                "--fail-on-unhealthy",
            ]
        )
        run(
            [
                "python",
                "workflow_control.py",
                "validate-single-pair",
                "--plan",
                str(autotrader_plan),
                "--run-id",
                run_id,
            ]
        )
        outcomes["autotrader"] = "success"

        kijiji_plan = temp / "kijiji-plan.tsv"
        run(
            [
                "python",
                "workflow_control.py",
                "plan",
                "--registry",
                "vehicle_registry.json",
                "--scope",
                "single_pair",
                "--cadence",
                "weekly",
                "--vehicle-key",
                "ford_f150",
                "--source",
                "kijiji",
                "--output",
                str(kijiji_plan),
            ]
        )
        if kijiji_plan.read_text(encoding="utf-8").strip() != expected_manual[1]:
            raise ValueError("Kijiji single-pair plan drifted")
        run(
            [
                "python",
                "kijiji_run.py",
                "--config",
                "config_f150.json",
                "--timeout-seconds",
                "4200",
                "--fail-on-unhealthy",
            ]
        )
        run(
            [
                "python",
                "workflow_control.py",
                "validate-single-pair",
                "--plan",
                str(kijiji_plan),
                "--run-id",
                run_id,
            ]
        )
        outcomes["kijiji"] = "success"
    except Exception as exc:  # fail-visible evidence is written below
        error = f"{type(exc).__name__}: {exc}"
        for key, value in list(outcomes.items()):
            if value == "pending":
                outcomes[key] = "not_completed"

    result = write_result(
        outcomes=outcomes,
        error=error,
        weekly_runs=weekly_runs,
        manual_runs=manual_runs,
    )
    return 0 if result["validation_status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
