#!/usr/bin/env python3
"""Metadata-only preflight for the historical Kraken/backtest layer.

This tool is intentionally incapable of downloading market archives. It validates
the repository manifest and, optionally on a local machine, reports filesystem
free space. It never touches active Paper/Shadow runtime state.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import urlparse

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("manifest must be a JSON object")
    return value


def nearest_existing(path: Path) -> Path | None:
    cur = path
    while True:
        if cur.exists():
            return cur
        parent = cur.parent
        if parent == cur:
            return None
        cur = parent


def validate(manifest: dict) -> tuple[list[str], list[str], dict]:
    errors: list[str] = []
    warnings: list[str] = []

    if manifest.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if manifest.get("mode") != "metadata_only":
        errors.append("mode must remain metadata_only")
    if manifest.get("bulk_downloads_allowed") is not False:
        errors.append("bulk_downloads_allowed must be false")
    if manifest.get("active_strategy_runtime_changes_allowed") is not False:
        errors.append("active_strategy_runtime_changes_allowed must be false")

    root = str(manifest.get("storage_root_windows") or "")
    if not root:
        errors.append("storage_root_windows missing")
    if root.upper().startswith("D:"):
        errors.append("drive D is explicitly blocked until its separate repair gate")
    if (manifest.get("storage_guardrails") or {}).get("drive_d_allowed") is not False:
        errors.append("storage_guardrails.drive_d_allowed must be false")

    pages = manifest.get("source_pages") or {}
    for key in ("ohlcvt", "trades"):
        url = str(pages.get(key) or "")
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.netloc != "support.kraken.com":
            errors.append(f"source_pages.{key} must be an official HTTPS Kraken Support URL")

    datasets = manifest.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        errors.append("datasets must be a non-empty list")
        datasets = []

    ids: set[str] = set()
    total_estimated_compressed_gb = 0.0
    kinds: set[str] = set()

    for idx, ds in enumerate(datasets):
        if not isinstance(ds, dict):
            errors.append(f"datasets[{idx}] must be an object")
            continue
        did = str(ds.get("id") or "")
        kind = str(ds.get("kind") or "")
        if not did:
            errors.append(f"datasets[{idx}].id missing")
        elif did in ids:
            errors.append(f"duplicate dataset id: {did}")
        ids.add(did)
        kinds.add(kind)

        if ds.get("download_enabled") is not False:
            errors.append(f"{did or idx}: download_enabled must remain false")

        part_count = ds.get("part_count")
        approx_part_gb = ds.get("approx_part_gb")
        if not isinstance(part_count, int) or part_count <= 0:
            errors.append(f"{did or idx}: invalid part_count")
        if not isinstance(approx_part_gb, (int, float)) or approx_part_gb <= 0:
            errors.append(f"{did or idx}: invalid approx_part_gb")
        if isinstance(part_count, int) and isinstance(approx_part_gb, (int, float)):
            total_estimated_compressed_gb += part_count * float(approx_part_gb)

        template = str(ds.get("part_url_template") or "")
        parsed = urlparse(template.replace("{part:02d}", "00"))
        if parsed.scheme != "https" or parsed.netloc != "assets.kraken.com":
            errors.append(f"{did or idx}: part_url_template must use assets.kraken.com HTTPS")

        checksum_url = str(ds.get("parts_checksum_url") or "")
        parsed = urlparse(checksum_url)
        if parsed.scheme != "https" or parsed.netloc != "assets.kraken.com":
            errors.append(f"{did or idx}: checksum URL must use assets.kraken.com HTTPS")

        checksum = str(ds.get("archive_sha256") or "")
        if not SHA256_RE.fullmatch(checksum):
            errors.append(f"{did or idx}: archive_sha256 must be 64 lowercase hex chars")

        columns = ds.get("columns")
        if not isinstance(columns, list) or not columns:
            errors.append(f"{did or idx}: columns missing")

        if kind == "ohlcvt":
            intervals = ds.get("intervals_minutes") or []
            if 15 not in intervals:
                errors.append(f"{did or idx}: 15m interval required for first replay")
            if ds.get("no_trade_intervals_omitted") is not True:
                errors.append(f"{did or idx}: no-trade omission semantics must be explicit")
        elif kind == "trades":
            required = {"timestamp", "price", "volume", "type", "order_type", "misc", "trade_id"}
            if not required.issubset(set(columns or [])):
                errors.append(f"{did or idx}: expected trade columns incomplete")
        else:
            errors.append(f"{did or idx}: unsupported dataset kind {kind!r}")

    if kinds != {"ohlcvt", "trades"}:
        errors.append("manifest must describe both ohlcvt and trades datasets")

    pit = manifest.get("point_in_time") or {}
    for key in (
        "forbid_future_features",
        "closed_candles_only_by_default",
        "live_bar_requires_explicit_reconstruction",
        "labels_after_decision_freeze_only",
        "zero_fill_missing_ohlcvt_forbidden",
        "current_online_universe_as_historical_filter_forbidden",
    ):
        if pit.get(key) is not True:
            errors.append(f"point_in_time.{key} must be true")

    execution = manifest.get("execution_baseline") or {}
    if float(execution.get("taker_fee_pct_per_side", -1)) != 0.60:
        errors.append("baseline taker fee must remain explicit at 0.60% per side")
    if execution.get("leverage") is not False:
        errors.append("historical baseline must not introduce leverage")

    storage = manifest.get("storage_guardrails") or {}
    for key in (
        "raw_in_github_allowed",
        "raw_in_supabase_allowed",
        "github_actions_bulk_download_allowed",
    ):
        if storage.get(key) is not False:
            errors.append(f"storage_guardrails.{key} must be false")

    updates = manifest.get("incremental_updates") or []
    if not isinstance(updates, list):
        errors.append("incremental_updates must be a list")
    else:
        for idx, upd in enumerate(updates):
            if upd.get("download_enabled") is not False:
                errors.append(f"incremental_updates[{idx}].download_enabled must remain false")
            parsed = urlparse(str(upd.get("url") or ""))
            if parsed.scheme != "https" or parsed.netloc != "assets.kraken.com":
                errors.append(f"incremental_updates[{idx}] must use assets.kraken.com HTTPS")

    summary = {
        "dataset_count": len(datasets),
        "dataset_ids": sorted(ids),
        "estimated_full_compressed_gb_if_later_enabled": round(total_estimated_compressed_gb, 2),
        "bulk_downloads_allowed": manifest.get("bulk_downloads_allowed"),
        "storage_root_windows": root,
    }
    if total_estimated_compressed_gb >= 30:
        warnings.append(
            "full OHLCVT + Time&Sales plan is large; keep Time&Sales behind its separate benefit/storage gate"
        )
    return errors, warnings, summary


def disk_probe(root_text: str) -> dict:
    if os.name != "nt":
        return {"status": "SKIPPED_NON_WINDOWS"}
    root = Path(root_text)
    anchor = nearest_existing(root)
    if anchor is None:
        return {"status": "UNAVAILABLE", "detail": "no existing ancestor for storage root"}
    usage = shutil.disk_usage(anchor)
    gb = 1024 ** 3
    return {
        "status": "OK",
        "probe_path": str(anchor),
        "total_gb": round(usage.total / gb, 2),
        "used_gb": round(usage.used / gb, 2),
        "free_gb": round(usage.free / gb, 2),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--manifest",
        type=Path,
        default=Path("research/historical/kraken-historical-manifest.json"),
    )
    ap.add_argument("--probe-disk", action="store_true")
    args = ap.parse_args()

    manifest = load_json(args.manifest)
    errors, warnings, summary = validate(manifest)
    result = {
        "kind": "KRAKEN_HISTORICAL_PREFLIGHT_V1",
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "warnings": warnings,
        "summary": summary,
        "guardrails": {
            "downloads_performed": False,
            "active_strategy_changed": False,
            "paper_shadow_runtime_changed": False,
        },
    }
    if args.probe_disk:
        result["disk"] = disk_probe(summary["storage_root_windows"])

    print("HISTORICAL_PREFLIGHT " + json.dumps(result, sort_keys=True))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
