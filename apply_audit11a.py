from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one match in {path}: found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


registry_py = ROOT / "vehicle_registry.py"
replace_once(
    registry_py,
    '''def active_entries(*, root: Path, registry_path: Path = DEFAULT_REGISTRY_PATH) -> list[dict[str, Any]]:
    return [entry for entry in registry_entries(root=root, registry_path=registry_path) if entry["enabled"]]


def active_config_paths(*, root: Path, registry_path: Path = DEFAULT_REGISTRY_PATH) -> list[Path]:
    return [Path(entry["config_path"]) for entry in active_entries(root=root, registry_path=registry_path)]


def active_source_plan(
    *, root: Path, registry_path: Path = DEFAULT_REGISTRY_PATH,
) -> list[tuple[Path, tuple[str, ...]]]:
    return [
        (Path(entry["config_path"]), tuple(entry["enabled_sources"]))
        for entry in active_entries(root=root, registry_path=registry_path)
    ]


def active_runs(*, root: Path, registry_path: Path = DEFAULT_REGISTRY_PATH) -> list[tuple[Path, str]]:
    return [
        (config_path, source)
        for config_path, sources in active_source_plan(root=root, registry_path=registry_path)
        for source in sources
    ]
''',
    '''def enabled_entries(*, root: Path, registry_path: Path = DEFAULT_REGISTRY_PATH) -> list[dict[str, Any]]:
    return [
        entry
        for entry in registry_entries(root=root, registry_path=registry_path)
        if entry["enabled"]
    ]


def active_entries(*, root: Path, registry_path: Path = DEFAULT_REGISTRY_PATH) -> list[dict[str, Any]]:
    return enabled_entries(root=root, registry_path=registry_path)


def cadence_entries(
    *, root: Path, cadence: str, registry_path: Path = DEFAULT_REGISTRY_PATH
) -> list[dict[str, Any]]:
    if cadence not in ALLOWED_CADENCES:
        raise ValueError(f"Unsupported registry cadence: {cadence}")
    return [
        entry
        for entry in enabled_entries(root=root, registry_path=registry_path)
        if entry["cadence"] == cadence
    ]


def active_config_paths(*, root: Path, registry_path: Path = DEFAULT_REGISTRY_PATH) -> list[Path]:
    return [Path(entry["config_path"]) for entry in enabled_entries(root=root, registry_path=registry_path)]


def active_source_plan(
    *, root: Path, registry_path: Path = DEFAULT_REGISTRY_PATH,
) -> list[tuple[Path, tuple[str, ...]]]:
    return [
        (Path(entry["config_path"]), tuple(entry["enabled_sources"]))
        for entry in enabled_entries(root=root, registry_path=registry_path)
    ]


def source_plan_for_cadence(
    *, root: Path, cadence: str, registry_path: Path = DEFAULT_REGISTRY_PATH
) -> list[tuple[Path, tuple[str, ...]]]:
    return [
        (Path(entry["config_path"]), tuple(entry["enabled_sources"]))
        for entry in cadence_entries(
            root=root, cadence=cadence, registry_path=registry_path
        )
    ]


def active_runs(*, root: Path, registry_path: Path = DEFAULT_REGISTRY_PATH) -> list[tuple[Path, str]]:
    return [
        (config_path, source)
        for config_path, sources in active_source_plan(root=root, registry_path=registry_path)
        for source in sources
    ]


def runs_for_cadence(
    *, root: Path, cadence: str, registry_path: Path = DEFAULT_REGISTRY_PATH
) -> list[tuple[Path, str]]:
    return [
        (config_path, source)
        for config_path, sources in source_plan_for_cadence(
            root=root, cadence=cadence, registry_path=registry_path
        )
        for source in sources
    ]
''',
)
replace_once(
    registry_py,
    '        "action", choices=("validate", "active-configs", "active-runs", "summary")\n',
    '        "action", choices=("validate", "active-configs", "active-runs", "weekly-runs", "manual-runs", "summary")\n',
)
replace_once(
    registry_py,
    '''    if args.action == "active-configs":
        for entry in active:
            print(entry["config_path"])
    elif args.action == "active-runs":
        for config_path, source in active_runs(root=root, registry_path=registry_path):
            print(f"{config_path}\t{source}")
    elif args.action == "summary":
        for entry in entries:
            state = "ACTIVE" if entry["enabled"] else "PAUSED"
            reason = f" — {entry.get('pause_reason')}" if entry.get("pause_reason") else ""
            sources = ",".join(entry["enabled_sources"])
            print(
                f"{state}: {entry['vehicle_key']} | purpose={entry['purpose']} | "
                f"priority={entry['priority']} | cadence={entry['cadence']} | "
                f"sources={sources}{reason}"
            )
    else:
        run_count = sum(len(entry["enabled_sources"]) for entry in active)
        print(
            f"Vehicle registry valid: {len(active)} active, "
            f"{len(entries) - len(active)} paused, {run_count} enabled source runs."
        )
''',
    '''    if args.action == "active-configs":
        for entry in active:
            print(entry["config_path"])
    elif args.action == "active-runs":
        for config_path, source in active_runs(root=root, registry_path=registry_path):
            print(f"{config_path}\t{source}")
    elif args.action in {"weekly-runs", "manual-runs"}:
        cadence = args.action.removesuffix("-runs")
        for config_path, source in runs_for_cadence(
            root=root, cadence=cadence, registry_path=registry_path
        ):
            print(f"{config_path}\t{source}")
    elif args.action == "summary":
        for entry in entries:
            state = "ENABLED" if entry["enabled"] else "PAUSED"
            reason = f" — {entry.get('pause_reason')}" if entry.get("pause_reason") else ""
            sources = ",".join(entry["enabled_sources"])
            print(
                f"{state}: {entry['vehicle_key']} | purpose={entry['purpose']} | "
                f"priority={entry['priority']} | cadence={entry['cadence']} | "
                f"sources={sources}{reason}"
            )
    else:
        weekly_count = len(
            runs_for_cadence(root=root, cadence="weekly", registry_path=registry_path)
        )
        manual_count = len(
            runs_for_cadence(root=root, cadence="manual", registry_path=registry_path)
        )
        print(
            f"Vehicle registry valid: {len(active)} enabled, "
            f"{len(entries) - len(active)} paused, {weekly_count} weekly source runs, "
            f"{manual_count} manual source runs."
        )
''',
)

workflow_control = ROOT / "workflow_control.py"
replace_once(
    workflow_control,
    "from vehicle_registry import DEFAULT_REGISTRY_PATH, active_runs, registry_entries\n",
    "from vehicle_registry import (\n"
    "    ALLOWED_CADENCES, DEFAULT_REGISTRY_PATH, registry_entries, runs_for_cadence,\n"
    ")\n",
)
replace_once(
    workflow_control,
    '''    scope: str,
    vehicle_key: str | None = None,
    source: str | None = None,
) -> list[tuple[Path, str]]:
''',
    '''    scope: str,
    vehicle_key: str | None = None,
    source: str | None = None,
    cadence: str = "weekly",
) -> list[tuple[Path, str]]:
''',
)
replace_once(
    workflow_control,
    '''    if scope == "full":
        plan = active_runs(root=root, registry_path=registry_path)
    else:
''',
    '''    if scope == "full":
        if cadence not in ALLOWED_CADENCES:
            raise ValueError(f"Unsupported collection cadence: {cadence}")
        plan = runs_for_cadence(
            root=root, cadence=cadence, registry_path=registry_path
        )
    else:
''',
)
replace_once(
    workflow_control,
    '    plan.add_argument("--scope", choices=COLLECTION_SCOPES, required=True)\n',
    '    plan.add_argument("--scope", choices=COLLECTION_SCOPES, required=True)\n'
    '    plan.add_argument("--cadence", choices=sorted(ALLOWED_CADENCES), default="weekly")\n',
)
replace_once(
    workflow_control,
    '''            vehicle_key=args.vehicle_key,
            source=args.source,
        )
''',
    '''            vehicle_key=args.vehicle_key,
            source=args.source,
            cadence=args.cadence,
        )
''',
)

pipeline = ROOT / "phase1_pipeline.py"
replace_once(
    pipeline,
    "from vehicle_registry import DEFAULT_REGISTRY_PATH, active_source_plan\n",
    "from vehicle_registry import (\n"
    "    ALLOWED_CADENCES, DEFAULT_REGISTRY_PATH, source_plan_for_cadence,\n"
    ")\n",
)
replace_once(
    pipeline,
    '''    scope.add_argument("--registry")
    scope.add_argument("--configs", nargs="+")
''',
    '''    scope.add_argument("--registry")
    scope.add_argument("--configs", nargs="+")
    action.add_argument(
        "--cadence", choices=sorted(ALLOWED_CADENCES), default="weekly"
    )
''',
)
replace_once(
    pipeline,
    '''    if args.registry:
        return active_source_plan(root=root, registry_path=Path(args.registry))
''',
    '''    if args.registry:
        return source_plan_for_cadence(
            root=root,
            cadence=args.cadence,
            registry_path=Path(args.registry),
        )
''',
)

retention = ROOT / "storage_retention.py"
replace_once(
    retention,
    "from vehicle_registry import DEFAULT_REGISTRY_PATH, registry_entries\n",
    "from vehicle_registry import (\n"
    "    ALLOWED_CADENCES, DEFAULT_REGISTRY_PATH, cadence_entries, registry_entries,\n"
    ")\n",
)
replace_once(
    retention,
    '''    run_id: str = "local",
    deleted_at_utc: str | None = None,
) -> dict[str, Any]:
''',
    '''    run_id: str = "local",
    deleted_at_utc: str | None = None,
    cadence: str | None = None,
) -> dict[str, Any]:
''',
)
replace_once(
    retention,
    '''    entries = registry_entries(root=root, registry_path=registry_path)
    active_keys = [str(entry["vehicle_key"]) for entry in entries if entry["enabled"]]
    deleted_at_utc = deleted_at_utc or utc_now()
''',
    '''    entries = (
        cadence_entries(root=root, cadence=cadence, registry_path=registry_path)
        if cadence is not None
        else registry_entries(root=root, registry_path=registry_path)
    )
    active_keys = [str(entry["vehicle_key"]) for entry in entries if entry["enabled"]]
    deleted_at_utc = deleted_at_utc or utc_now()
''',
)
replace_once(
    retention,
    '''def verify_retention(
    *, root: Path, registry_path: Path = DEFAULT_REGISTRY_PATH
) -> dict[str, Any]:
''',
    '''def verify_retention(
    *,
    root: Path,
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    cadence: str | None = None,
) -> dict[str, Any]:
''',
)
replace_once(
    retention,
    '''    entries = registry_entries(root=root, registry_path=registry_path)
    active_keys = [str(entry["vehicle_key"]) for entry in entries if entry["enabled"]]
    errors = [
''',
    '''    entries = (
        cadence_entries(root=root, cadence=cadence, registry_path=registry_path)
        if cadence is not None
        else registry_entries(root=root, registry_path=registry_path)
    )
    active_keys = [str(entry["vehicle_key"]) for entry in entries if entry["enabled"]]
    errors = [
''',
)
replace_once(
    retention,
    '''    for name in ("apply", "verify", "validate-staged"):
        action = sub.add_parser(name)
        action.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH))
''',
    '''    for name in ("apply", "verify", "validate-staged"):
        action = sub.add_parser(name)
        action.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH))
        if name != "validate-staged":
            action.add_argument("--cadence", choices=sorted(ALLOWED_CADENCES))
''',
)
replace_once(
    retention,
    '''            registry_path=registry,
            run_id=run_id,
        )
''',
    '''            registry_path=registry,
            run_id=run_id,
            cadence=args.cadence,
        )
''',
)
replace_once(
    retention,
    "        report = verify_retention(root=root, registry_path=registry)\n",
    "        report = verify_retention(\n"
    "            root=root, registry_path=registry, cadence=args.cadence\n"
    "        )\n",
)

registry_test = ROOT / "tests" / "test_vehicle_registry.py"
replace_once(
    registry_test,
    "from vehicle_registry import active_config_paths, active_runs, registry_entries\n",
    "from vehicle_registry import (\n"
    "    active_config_paths, active_runs, registry_entries, runs_for_cadence,\n"
    ")\n",
)
replace_once(
    registry_test,
    '''    enabled: bool = True,
    enabled_sources: list[str] | None = None,
) -> dict:
''',
    '''    enabled: bool = True,
    enabled_sources: list[str] | None = None,
    cadence: str = "weekly",
) -> dict:
''',
)
replace_once(
    registry_test,
    '        "cadence": "weekly",\n',
    '        "cadence": cadence,\n',
)
replace_once(
    registry_test,
    '''        self.assertEqual(
            active,
            [
                "ford_f350",
                "ram_3500",
                "subaru_forester",
                "honda_odyssey",
                "kia_carnival",
            ],
        )
        self.assertEqual(paused, ["ford_f150", "toyota_tundra"])
        self.assertEqual(
            [str(path) for path in active_config_paths(root=root)],
            [
                "config_f350.json",
                "config_ram3500.json",
                "config_forester.json",
                "config_odyssey.json",
                "config_carnival.json",
            ],
        )
        runs = [(str(path), source) for path, source in active_runs(root=root)]
        self.assertEqual(len(runs), 10)
        self.assertEqual(
            runs[:2],
            [
                ("config_f350.json", "autotrader"),
                ("config_f350.json", "kijiji"),
            ],
        )
        self.assertFalse(
            any("f150" in path or "tundra" in path for path, _ in runs)
        )
        for entry in entries:
            self.assertEqual(entry["cadence"], "weekly")
            self.assertEqual(entry["enabled_sources"], ["autotrader", "kijiji"])
''',
    '''        self.assertEqual(
            active,
            [
                "ford_f350",
                "ram_3500",
                "subaru_forester",
                "honda_odyssey",
                "kia_carnival",
                "ford_f150",
            ],
        )
        self.assertEqual(paused, ["toyota_tundra"])
        self.assertEqual(
            [str(path) for path in active_config_paths(root=root)],
            [
                "config_f350.json",
                "config_ram3500.json",
                "config_forester.json",
                "config_odyssey.json",
                "config_carnival.json",
                "config_f150.json",
            ],
        )
        all_runs = [(str(path), source) for path, source in active_runs(root=root)]
        self.assertEqual(len(all_runs), 12)
        weekly_runs = [
            (str(path), source)
            for path, source in runs_for_cadence(root=root, cadence="weekly")
        ]
        manual_runs = [
            (str(path), source)
            for path, source in runs_for_cadence(root=root, cadence="manual")
        ]
        self.assertEqual(len(weekly_runs), 10)
        self.assertFalse(any("f150" in path or "tundra" in path for path, _ in weekly_runs))
        self.assertEqual(
            manual_runs,
            [
                ("config_f150.json", "autotrader"),
                ("config_f150.json", "kijiji"),
            ],
        )
        cadence_by_key = {entry["vehicle_key"]: entry["cadence"] for entry in entries}
        self.assertEqual(cadence_by_key["ford_f150"], "manual")
        self.assertEqual(cadence_by_key["toyota_tundra"], "weekly")
        for entry in entries:
            self.assertEqual(entry["enabled_sources"], ["autotrader", "kijiji"])
''',
)

hardening_test = ROOT / "tests" / "test_workflow_hardening.py"
replace_once(
    hardening_test,
    '''        self.assertEqual(len(full), 10)
        single = build_collection_plan(
''',
    '''        self.assertEqual(len(full), 10)
        self.assertFalse(any("f150" in str(path) for path, _ in full))
        manual = build_collection_plan(
            root=root,
            scope="full",
            cadence="manual",
            registry_path=Path("vehicle_registry.json"),
        )
        self.assertEqual(
            manual,
            [
                (Path("config_f150.json"), "autotrader"),
                (Path("config_f150.json"), "kijiji"),
            ],
        )
        single = build_collection_plan(
''',
)
replace_once(
    hardening_test,
    '''        with self.assertRaisesRegex(ValueError, "paused"):
            build_collection_plan(
                root=root,
                scope="single_pair",
                registry_path=Path("vehicle_registry.json"),
                vehicle_key="ford_f150",
                source="autotrader",
            )
''',
    '''        f150 = build_collection_plan(
            root=root,
            scope="single_pair",
            registry_path=Path("vehicle_registry.json"),
            vehicle_key="ford_f150",
            source="autotrader",
        )
        self.assertEqual(f150, [(Path("config_f150.json"), "autotrader")])
        with self.assertRaisesRegex(ValueError, "paused"):
            build_collection_plan(
                root=root,
                scope="single_pair",
                registry_path=Path("vehicle_registry.json"),
                vehicle_key="toyota_tundra",
                source="autotrader",
            )
''',
)

workflow_test = ROOT / "tests" / "test_workflow_contract.py"
replace_once(
    workflow_test,
    '            "options: [ford_f350, ram_3500, subaru_forester, honda_odyssey, kia_carnival]",\n',
    '            "options: [ford_f350, ram_3500, subaru_forester, honda_odyssey, kia_carnival, ford_f150]",\n',
)
replace_once(
    workflow_test,
    '''        self.assertIn("if: env.COLLECTION_SCOPE == 'single_pair'", self.collection)
        self.assertIn("if: env.COLLECTION_SCOPE == 'full'", self.collection)
''',
    '''        self.assertIn("if: env.COLLECTION_SCOPE == 'single_pair'", self.collection)
        self.assertIn("if: env.COLLECTION_SCOPE == 'full'", self.collection)
        self.assertGreaterEqual(self.collection.count("--cadence weekly"), 3)
''',
)
replace_once(
    workflow_test,
    '            "if: env.COLLECTION_SCOPE == \'single_pair\' && env.VEHICLE_KEY != \'ford_f350\'",\n',
    '            "env.VEHICLE_KEY == \'ram_3500\' ||",\n',
)
replace_once(
    workflow_test,
    '''        self.assertNotIn("data/ford_f350/purpose_output", self.collection)
        self.assertNotIn("config_f150.json", self.collection)
        self.assertNotIn("config_tundra.json", self.collection)
''',
    '''        self.assertNotIn("data/ford_f350/purpose_output", self.collection)
        self.assertNotIn("data/ford_f150/purpose_output", self.collection)
        self.assertNotIn("config_f150.json", self.collection)
        self.assertNotIn("config_tundra.json", self.collection)

    def test_f150_is_manual_nonpublishing_and_profile_isolated(self):
        for value in (
            "ford_f150",
            "Write optional-curiosity manual summary",
            "optional-curiosity-summary.md",
            "No purchase need, rank, score, appraisal, or recommendation is implied.",
            "env.VEHICLE_KEY == 'ford_f150'",
        ):
            self.assertIn(value, self.collection)
        self.assertIn(
            "env.COLLECTION_SCOPE == 'full' && env.PUBLISH_GENERATED_DATA == 'true'",
            self.collection,
        )
        self.assertNotIn("config_tundra.json", self.collection)
''',
)
replace_once(
    workflow_test,
    '''            "storage_retention.py apply",
            "storage_retention.py verify",
''',
    '''            "storage_retention.py apply",
            "storage_retention.py verify",
            "--cadence weekly",
''',
)

scrape = ROOT / ".github" / "workflows" / "scrape.yml"
replace_once(
    scrape,
    "        options: [ford_f350, ram_3500, subaru_forester, honda_odyssey, kia_carnival]\n",
    "        options: [ford_f350, ram_3500, subaru_forester, honda_odyssey, kia_carnival, ford_f150]\n",
)
replace_once(
    scrape,
    '''            --scope "$COLLECTION_SCOPE" \\
            --vehicle-key "$VEHICLE_KEY" \\
''',
    '''            --scope "$COLLECTION_SCOPE" \\
            --cadence weekly \\
            --vehicle-key "$VEHICLE_KEY" \\
''',
)
replace_once(
    scrape,
    "        if: env.COLLECTION_SCOPE == 'single_pair' && env.VEHICLE_KEY != 'ford_f350'\n",
    "        if: env.COLLECTION_SCOPE == 'single_pair' && (env.VEHICLE_KEY == 'ram_3500' || env.VEHICLE_KEY == 'subaru_forester' || env.VEHICLE_KEY == 'honda_odyssey' || env.VEHICLE_KEY == 'kia_carnival')\n",
)
replace_once(
    scrape,
    '''          find "data/$VEHICLE_KEY/purpose_output" -name '*_latest.md' -type f -print -exec cat {} \; >> "$GITHUB_STEP_SUMMARY"

      - name: Prepare single-pair validation artifact
''',
    '''          find "data/$VEHICLE_KEY/purpose_output" -name '*_latest.md' -type f -print -exec cat {} \; >> "$GITHUB_STEP_SUMMARY"

      - name: Write optional-curiosity manual summary
        if: env.COLLECTION_SCOPE == 'single_pair' && env.VEHICLE_KEY == 'ford_f150'
        run: |
          python - <<'PY'
          import json
          import os
          from pathlib import Path

          vehicle = os.environ["VEHICLE_KEY"]
          source = os.environ["SELECTED_SOURCE"]
          status_path = Path("data") / vehicle / "run_status" / f"{source}_latest.json"
          status = json.loads(status_path.read_text(encoding="utf-8"))
          output = Path(os.environ["RUNNER_TEMP"]) / "optional-curiosity-summary.md"
          output.write_text(
              "# Optional F-150 manual search\n\n"
              f"- Source: {source}\n"
              f"- Fetched records: {status.get('fetched_record_count', 0)}\n"
              f"- Accepted records: {status.get('accepted_record_count', 0)}\n"
              f"- Rejected records: {status.get('rejected_record_count', 0)}\n"
              f"- Parse failures: {status.get('parse_failure_count', 0)}\n"
              f"- Pagination complete: {status.get('pagination_complete')}\n"
              f"- Identity/lifecycle status: {status.get('identity_lifecycle_status')}\n\n"
              "No purchase need, rank, score, appraisal, or recommendation is implied. "
              "The accepted CSV and evidence files are a manual optional-curiosity result only.\n",
              encoding="utf-8",
          )
          print(output.read_text(encoding="utf-8"))
          PY
          cat "$RUNNER_TEMP/optional-curiosity-summary.md" >> "$GITHUB_STEP_SUMMARY"

      - name: Prepare single-pair validation artifact
''',
)
replace_once(
    scrape,
    '''          copy_dir "data/$VEHICLE_KEY/purpose_output" "$artifact/purpose_output"
          cp "${{ steps.collection-plan.outputs.path }}" "$artifact/source-plan.tsv"
''',
    '''          copy_dir "data/$VEHICLE_KEY/purpose_output" "$artifact/purpose_output"
          copy_file "$RUNNER_TEMP/optional-curiosity-summary.md" "$artifact/optional_curiosity"
          cp "${{ steps.collection-plan.outputs.path }}" "$artifact/source-plan.tsv"
''',
)
replace_once(
    scrape,
    "        run: python phase1_pipeline.py build-manual-review --registry vehicle_registry.json\n",
    "        run: python phase1_pipeline.py build-manual-review --registry vehicle_registry.json --cadence weekly\n",
)
replace_once(
    scrape,
    "          python phase1_pipeline.py report-health --registry vehicle_registry.json\n",
    "          python phase1_pipeline.py report-health --registry vehicle_registry.json --cadence weekly\n",
)
replace_once(
    scrape,
    '''          python storage_retention.py apply --registry vehicle_registry.json
          python storage_retention.py verify --registry vehicle_registry.json
''',
    '''          python storage_retention.py apply --registry vehicle_registry.json --cadence weekly
          python storage_retention.py verify --registry vehicle_registry.json --cadence weekly
''',
)

print("Applied Audit 11A cadence, F-150 manual workflow, retention, and tests.")
