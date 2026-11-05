from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence


def execute_collector(
    command: Sequence[str], *, root: Path, timeout_seconds: float
) -> tuple[int | None, bool, str, str]:
    """Execute a source collector with the established timeout/output contract."""
    stdout = stderr = ""
    returncode: int | None = None
    timed_out = False
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
            env=os.environ.copy(),
        )
        returncode = completed.returncode
        stdout, stderr = completed.stdout or "", completed.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = (
            (exc.stdout or "").decode("utf-8", errors="replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        stderr = (
            (exc.stderr or "").decode("utf-8", errors="replace")
            if isinstance(exc.stderr, bytes)
            else (exc.stderr or "")
        )
    for output, stream in ((stdout, sys.stdout), (stderr, sys.stderr)):
        if output:
            tail = output[-4000:]
            print(tail, file=stream, end="" if tail.endswith("\n") else "\n")
    return returncode, timed_out, stdout, stderr
