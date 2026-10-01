#!/usr/bin/env python3
"""Selectively extract Kraken EUR 15m OHLCVT CSVs from a verified full ZIP.

Safety:
- local files only; no network;
- exact immutable source ZIP hash must match the pinned Kraken checksum;
- only members whose basename ends with EUR_15.csv are eligible;
- path traversal is impossible because output names are flattened to basenames;
- existing conflicting files fail closed unless byte-identical;
- active Paper/Shadow runtime is never touched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

EXPECTED_ARCHIVE_SHA256 = "fc81b54cba6e12af3e9422dde9416179e6ef76af4831d48d839fbdb43018eaa4"
EUR15_RE = re.compile(r"(?i)(^|/)([^/]+EUR)_15\.csv$")


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def copy_member(zf: zipfile.ZipFile, member: zipfile.ZipInfo, dest: Path) -> tuple[int, str]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    written = 0
    with tempfile.NamedTemporaryFile("wb", delete=False, dir=dest.parent, prefix=dest.name + ".", suffix=".tmp") as tmp:
        tmp_path = Path(tmp.name)
        with zf.open(member, "r") as src:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                tmp.write(chunk)
                h.update(chunk)
                written += len(chunk)
    try:
        if dest.exists():
            existing_sha = sha256_file(dest)
            new_sha = h.hexdigest()
            if existing_sha != new_sha:
                raise RuntimeError(f"existing conflicting file: {dest}")
            tmp_path.unlink(missing_ok=True)
            return dest.stat().st_size, existing_sha
        os.replace(tmp_path, dest)
        return written, h.hexdigest()
    finally:
        tmp_path.unlink(missing_ok=True)


def inspect_csv_shape(path: Path) -> dict:
    rows = 0
    first_ts: int | None = None
    last_ts: int | None = None
    prev_ts: int | None = None
    bad_columns = 0
    non_monotonic = 0
    with path.open("r", encoding="utf-8", errors="strict") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line:
                continue
            parts = line.split(",")
            rows += 1
            if len(parts) != 7:
                bad_columns += 1
                continue
            ts = int(parts[0])
            if first_ts is None:
                first_ts = ts
            if prev_ts is not None and ts <= prev_ts:
                non_monotonic += 1
            prev_ts = ts
            last_ts = ts
    return {
        "rows": rows,
        "first_timestamp": first_ts,
        "last_timestamp": last_ts,
        "bad_column_rows": bad_columns,
        "non_monotonic_rows": non_monotonic,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("archive", type=Path)
    ap.add_argument("destination", type=Path)
    ap.add_argument("catalog", type=Path)
    ap.add_argument("--expected-count", type=int, default=608)
    ap.add_argument("--validate-csv", action="store_true")
    args = ap.parse_args()

    archive_sha = sha256_file(args.archive)
    if archive_sha != EXPECTED_ARCHIVE_SHA256:
        raise SystemExit(
            f"archive SHA-256 mismatch: expected {EXPECTED_ARCHIVE_SHA256} got {archive_sha}"
        )

    if not zipfile.is_zipfile(args.archive):
        raise SystemExit("source is not a valid ZIP archive")

    entries: list[dict] = []
    with zipfile.ZipFile(args.archive, "r") as zf:
        members = [
            m for m in zf.infolist()
            if not m.is_dir() and EUR15_RE.search(m.filename.replace("\\", "/"))
        ]
        members.sort(key=lambda m: m.filename.upper())

        if len(members) != args.expected_count:
            raise SystemExit(
                f"eligible EUR 15m member count mismatch: expected {args.expected_count}, got {len(members)}"
            )

        basenames = [Path(m.filename).name for m in members]
        if len(set(x.upper() for x in basenames)) != len(basenames):
            raise SystemExit("duplicate EUR 15m basenames detected; refusing flattened extraction")

        args.destination.mkdir(parents=True, exist_ok=True)
        for index, member in enumerate(members, 1):
            dest = args.destination / Path(member.filename).name
            size, sha = copy_member(zf, member, dest)
            row = {
                "member": member.filename,
                "file": dest.name,
                "uncompressed_bytes": size,
                "sha256": sha,
            }
            if args.validate_csv:
                row["csv_validation"] = inspect_csv_shape(dest)
                check = row["csv_validation"]
                if check["bad_column_rows"] or check["non_monotonic_rows"]:
                    raise SystemExit(f"CSV validation failed: {dest}")
            entries.append(row)
            if index % 50 == 0 or index == len(members):
                print(f"EUR15_EXTRACT progress={index}/{len(members)}", flush=True)

    total_bytes = sum(x["uncompressed_bytes"] for x in entries)
    result = {
        "kind": "KRAKEN_OHLCVT_EUR15_EXTRACTION_V1",
        "status": "PASS",
        "archive": str(args.archive),
        "archive_sha256": archive_sha,
        "destination": str(args.destination),
        "file_count": len(entries),
        "total_uncompressed_bytes": total_bytes,
        "validate_csv": bool(args.validate_csv),
        "entries": entries,
        "source_provenance": {
            "provider": "Kraken",
            "dataset": "Kraken_OHLCVT_Full_2026Q2.zip",
            "cutoff": "2026-06-30",
        },
        "guardrails": {
            "network_used": False,
            "active_strategy_changed": False,
            "paper_shadow_runtime_changed": False,
        },
        "next_gate": "normalize_eur15_point_in_time_dataset",
    }

    args.catalog.parent.mkdir(parents=True, exist_ok=True)
    tmp_catalog = args.catalog.with_suffix(args.catalog.suffix + ".tmp")
    tmp_catalog.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", "utf-8")
    os.replace(tmp_catalog, args.catalog)

    compact = {
        "kind": result["kind"],
        "status": result["status"],
        "file_count": result["file_count"],
        "total_uncompressed_bytes": result["total_uncompressed_bytes"],
        "destination": result["destination"],
        "catalog": str(args.catalog),
        "archive_sha256": result["archive_sha256"],
        "validate_csv": result["validate_csv"],
        "next_gate": result["next_gate"],
        "guardrails": result["guardrails"],
    }
    print("KRAKEN_OHLCVT_EUR15_EXTRACTION " + json.dumps(compact, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
