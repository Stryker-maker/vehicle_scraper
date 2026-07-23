from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEPENDENCY_LOCK_SCHEMA_VERSION = 1


def validate_lock(path: Path) -> dict[str, Any]:
    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    errors: list[str] = []
    if not lines:
        errors.append("lock_is_empty")
    invalid = [
        line
        for line in lines
        if line.count("==") != 1
        or any(token in line for token in (">=", "<=", "~=", "!=", " @ "))
    ]
    if invalid:
        errors.extend(f"non_exact_pin:{line}" for line in invalid)
    names = [line.split("==", 1)[0].strip().casefold() for line in lines if "==" in line]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    errors.extend(f"duplicate_package:{name}" for name in duplicates)
    return {
        "dependency_lock_schema_version": DEPENDENCY_LOCK_SCHEMA_VERSION,
        "validation_status": "pass" if not errors else "fail",
        "package_count": len(lines),
        "packages": lines,
        "validation_errors": errors,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Validate exact Python dependency pins")
    result.add_argument("--lock", default="requirements.lock")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    report = validate_lock(Path(args.lock))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["validation_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
