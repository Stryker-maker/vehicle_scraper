#!/usr/bin/env python3
"""Create a byte-preserving archive of CSV files removed by PR #39."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import subprocess
import zipfile
from pathlib import Path


EXPECTED_CSV_COUNT = 161


def git_bytes(*args: str) -> bytes:
    return subprocess.run(
        ["git", *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    paths = [
        item.decode("utf-8")
        for item in git_bytes(
            "diff", "--name-only", "-z", "--diff-filter=D",
            args.base, args.head, "--", "data",
        ).split(b"\0")
        if item.endswith(b".csv")
    ]
    paths.sort()
    if len(paths) != EXPECTED_CSV_COUNT:
        raise SystemExit(
            f"Expected {EXPECTED_CSV_COUNT} deleted historical CSVs; found {len(paths)}"
        )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_buffer = io.StringIO(newline="")
    writer = csv.writer(manifest_buffer, lineterminator="\n")
    writer.writerow(
        ["path", "source_commit", "git_blob_sha1", "sha256", "size_bytes"]
    )

    archived: list[tuple[str, bytes]] = []
    for path in paths:
        data = git_bytes("show", f"{args.base}:{path}")
        blob_sha = git_bytes("rev-parse", f"{args.base}:{path}").decode().strip()
        actual_blob_sha = hashlib.sha1(
            b"blob " + str(len(data)).encode() + b"\0" + data
        ).hexdigest()
        if actual_blob_sha != blob_sha:
            raise SystemExit(f"Git blob verification failed for {path}")
        writer.writerow(
            [
                path,
                args.base,
                blob_sha,
                hashlib.sha256(data).hexdigest(),
                len(data),
            ]
        )
        archived.append((path, data))

    readme = (
        "Historical CSV archive for vehicle_scraper.\n\n"
        f"Contains {len(archived)} CSV files removed from active data/ paths by PR #39.\n"
        f"Original source commit: {args.base}\n"
        f"Archive generated from PR #39 head: {args.head}\n"
        "CSV files retain their original data/... paths and original bytes.\n"
        "Extract this archive at the repository root to restore the historical paths.\n"
        "MANIFEST.csv records each original Git blob SHA-1, SHA-256, and byte length.\n"
    )
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        archive.writestr("ARCHIVE_README.txt", readme)
        archive.writestr("MANIFEST.csv", manifest_buffer.getvalue())
        for path, data in archived:
            archive.writestr(path, data)

    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        if len(names) != EXPECTED_CSV_COUNT + 2:
            raise SystemExit("Archive entry count verification failed")
        if archive.testzip() is not None:
            raise SystemExit("Archive CRC verification failed")
        if set(names[2:]) != set(paths):
            raise SystemExit("Archive path inventory verification failed")

    print(
        f"ARCHIVE_CREATED path={output} csv_files={len(archived)} "
        f"archive_bytes={output.stat().st_size}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
