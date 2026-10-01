#!/usr/bin/env python3
"""Normalize selectively extracted Kraken EUR 15m OHLCVT CSVs.

Design goals:
- local/offline only;
- deterministic gzip outputs (mtime=0);
- explicit bar-start and bar-end timestamps;
- no synthetic gap filling;
- raw decimal text preserved exactly;
- one normalized gzip CSV per pair;
- provenance + gap statistics in a compact catalog;
- active Paper/Shadow runtime is never touched.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "KRAKEN_EUR15_NORMALIZED_V1"
INTERVAL_SECONDS = 15 * 60
NAME_RE = re.compile(r"(?i)^(.+EUR)_15\.csv$")


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def iso_utc(epoch_seconds: int) -> str:
    return (
        datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def normalize_one(src: Path, dst: Path) -> dict:
    match = NAME_RE.match(src.name)
    if not match:
        raise ValueError(f"unexpected EUR15 filename: {src.name}")
    pair = match.group(1).upper()

    dst.parent.mkdir(parents=True, exist_ok=True)

    rows = 0
    first_start: int | None = None
    last_start: int | None = None
    previous_start: int | None = None
    missing_intervals = 0
    gap_events = 0
    max_gap_intervals = 0

    fd, tmp_name = tempfile.mkstemp(prefix=dst.name + ".", suffix=".tmp", dir=dst.parent)
    os.close(fd)
    tmp_path = Path(tmp_name)

    try:
        with src.open("r", encoding="utf-8", newline="") as in_fh, tmp_path.open("wb") as raw_out:
            with gzip.GzipFile(fileobj=raw_out, mode="wb", mtime=0, filename="") as gz:
                with io.TextIOWrapper(gz, encoding="utf-8", newline="") as text_out:
                    writer = csv.writer(text_out, lineterminator="\n")
                    writer.writerow(
                        [
                            "bar_start_epoch",
                            "bar_end_epoch",
                            "bar_start_utc",
                            "bar_end_utc",
                            "open",
                            "high",
                            "low",
                            "close",
                            "volume",
                            "trades",
                        ]
                    )

                    reader = csv.reader(in_fh)
                    for line_no, row in enumerate(reader, 1):
                        if len(row) != 7:
                            raise ValueError(f"{src.name}:{line_no}: expected 7 columns")
                        ts_text, open_, high, low, close, volume, trades = row
                        start = int(ts_text)
                        end = start + INTERVAL_SECONDS

                        # Validate numeric fields without reformatting them.
                        for label, value in (
                            ("open", open_),
                            ("high", high),
                            ("low", low),
                            ("close", close),
                            ("volume", volume),
                        ):
                            try:
                                float(value)
                            except ValueError as exc:
                                raise ValueError(
                                    f"{src.name}:{line_no}: invalid {label}={value!r}"
                                ) from exc
                        trade_count = int(trades)
                        if trade_count < 0:
                            raise ValueError(f"{src.name}:{line_no}: negative trade count")

                        if previous_start is not None:
                            delta = start - previous_start
                            if delta <= 0:
                                raise ValueError(
                                    f"{src.name}:{line_no}: non-monotonic timestamp"
                                )
                            if delta > INTERVAL_SECONDS:
                                gap_events += 1
                                gap_intervals = max((delta // INTERVAL_SECONDS) - 1, 0)
                                missing_intervals += gap_intervals
                                max_gap_intervals = max(max_gap_intervals, gap_intervals)

                        if first_start is None:
                            first_start = start
                        last_start = start
                        previous_start = start
                        rows += 1

                        writer.writerow(
                            [
                                str(start),
                                str(end),
                                iso_utc(start),
                                iso_utc(end),
                                open_,
                                high,
                                low,
                                close,
                                volume,
                                str(trade_count),
                            ]
                        )
                    text_out.flush()

        if rows == 0:
            raise ValueError(f"empty source CSV: {src}")

        digest = sha256_file(tmp_path)

        if dst.exists():
            existing = sha256_file(dst)
            if existing != digest:
                raise RuntimeError(f"existing normalized file conflicts: {dst}")
            tmp_path.unlink(missing_ok=True)
        else:
            os.replace(tmp_path, dst)

        return {
            "pair": pair,
            "source_file": src.name,
            "normalized_file": dst.name,
            "rows": rows,
            "first_bar_start_epoch": first_start,
            "last_bar_start_epoch": last_start,
            "first_bar_start_utc": iso_utc(first_start),
            "last_bar_start_utc": iso_utc(last_start),
            "gap_events": gap_events,
            "missing_intervals": missing_intervals,
            "max_gap_intervals": max_gap_intervals,
            "normalized_sha256": digest,
        }
    finally:
        tmp_path.unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source_dir", type=Path)
    ap.add_argument("destination_dir", type=Path)
    ap.add_argument("catalog", type=Path)
    ap.add_argument("--extraction-catalog", type=Path)
    ap.add_argument("--expected-count", type=int, default=648)
    args = ap.parse_args()

    sources = sorted(args.source_dir.glob("*EUR_15.csv"), key=lambda p: p.name.upper())
    if len(sources) != args.expected_count:
        raise SystemExit(
            f"source EUR15 count mismatch: expected {args.expected_count}, got {len(sources)}"
        )

    extraction_catalog_sha256 = None
    source_archive_sha256 = None
    if args.extraction_catalog:
        if not args.extraction_catalog.exists():
            raise SystemExit(f"extraction catalog missing: {args.extraction_catalog}")
        extraction_catalog_sha256 = sha256_file(args.extraction_catalog)
        obj = json.loads(args.extraction_catalog.read_text("utf-8"))
        if obj.get("status") != "PASS":
            raise SystemExit("extraction catalog status is not PASS")
        if int(obj.get("file_count", -1)) != len(sources):
            raise SystemExit("extraction catalog file_count does not match source directory")
        source_archive_sha256 = obj.get("archive_sha256")

    results: list[dict] = []
    args.destination_dir.mkdir(parents=True, exist_ok=True)

    for index, src in enumerate(sources, 1):
        pair = NAME_RE.match(src.name).group(1).upper()  # count/name validated above
        dst = args.destination_dir / f"{pair}_15.normalized.csv.gz"
        results.append(normalize_one(src, dst))
        if index % 50 == 0 or index == len(sources):
            print(f"EUR15_NORMALIZE progress={index}/{len(sources)}", flush=True)

    pair_names = [r["pair"] for r in results]
    if len(set(pair_names)) != len(pair_names):
        raise SystemExit("duplicate normalized pair names detected")

    catalog = {
        "kind": "KRAKEN_EUR15_NORMALIZATION_V1",
        "status": "PASS",
        "schema_version": SCHEMA_VERSION,
        "interval_seconds": INTERVAL_SECONDS,
        "source_dir": str(args.source_dir),
        "destination_dir": str(args.destination_dir),
        "file_count": len(results),
        "total_rows": sum(r["rows"] for r in results),
        "pairs_with_gaps": sum(1 for r in results if r["gap_events"] > 0),
        "total_gap_events": sum(r["gap_events"] for r in results),
        "total_missing_intervals_not_filled": sum(r["missing_intervals"] for r in results),
        "extraction_catalog": str(args.extraction_catalog) if args.extraction_catalog else None,
        "extraction_catalog_sha256": extraction_catalog_sha256,
        "source_archive_sha256": source_archive_sha256,
        "files": results,
        "point_in_time_contract": {
            "feature_visibility_rule": "bar_end_epoch <= data_cutoff_epoch",
            "bar_start_is_not_close_time": True,
            "synthetic_gap_fill_used": False,
            "missing_intervals_preserved": True,
            "future_labels_not_generated_here": True,
        },
        "guardrails": {
            "network_used": False,
            "raw_source_modified": False,
            "active_strategy_changed": False,
            "paper_shadow_runtime_changed": False,
        },
        "next_gate": "historical_real_pair_point_in_time_replay_smoke",
    }

    args.catalog.parent.mkdir(parents=True, exist_ok=True)
    tmp_catalog = args.catalog.with_suffix(args.catalog.suffix + ".tmp")
    tmp_catalog.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", "utf-8")
    os.replace(tmp_catalog, args.catalog)

    compact = {
        "kind": catalog["kind"],
        "status": catalog["status"],
        "schema_version": catalog["schema_version"],
        "file_count": catalog["file_count"],
        "total_rows": catalog["total_rows"],
        "pairs_with_gaps": catalog["pairs_with_gaps"],
        "total_gap_events": catalog["total_gap_events"],
        "total_missing_intervals_not_filled": catalog["total_missing_intervals_not_filled"],
        "destination_dir": catalog["destination_dir"],
        "catalog": str(args.catalog),
        "next_gate": catalog["next_gate"],
        "guardrails": catalog["guardrails"],
    }
    print("KRAKEN_EUR15_NORMALIZATION " + json.dumps(compact, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
