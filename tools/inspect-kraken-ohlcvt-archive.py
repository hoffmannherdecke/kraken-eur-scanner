#!/usr/bin/env python3
"""Read-only inspector for the verified Kraken OHLCVT ZIP archive.

No extraction, no strategy logic, no network access. The tool inventories archive
members, reads MANIFEST.json when present and identifies likely EUR 15-minute CSV
members for the next selective-extraction gate.
"""
from __future__ import annotations

import argparse
import json
import re
import zipfile
from collections import Counter
from pathlib import Path

TOKEN_SPLIT = re.compile(r"[_./\\-]+")
EUR15_RE = re.compile(r"(?i)(^|/)([^/]+EUR)_15\.csv$")
INTERVALS = {"1", "5", "15", "30", "60", "240", "720", "1440"}


def member_tokens(name: str) -> list[str]:
    stem = name[:-4] if name.lower().endswith(".csv") else name
    return [t for t in TOKEN_SPLIT.split(stem) if t]


def infer_interval(name: str) -> str | None:
    tokens = member_tokens(name)
    for token in reversed(tokens):
        if token in INTERVALS:
            return token
    return None


def looks_eur(name: str) -> bool:
    normalized = name.replace("\\", "/")
    base = Path(normalized).name.upper()
    stem = base[:-4] if base.endswith(".CSV") else base
    pair_token = stem.rsplit("_", 1)[0]
    return pair_token.endswith("EUR") and len(pair_token) > 3


def inspect(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path)
    if not zipfile.is_zipfile(path):
        raise ValueError(f"not a valid ZIP archive: {path}")

    with zipfile.ZipFile(path, "r") as zf:
        members = zf.infolist()
        csvs = [m for m in members if m.filename.lower().endswith(".csv")]
        manifests = [
            m for m in members
            if Path(m.filename).name.upper() == "MANIFEST.JSON"
        ]

        interval_counts: Counter[str] = Counter()
        eur_15: list[str] = []
        for m in csvs:
            interval = infer_interval(m.filename)
            interval_counts[interval or "UNKNOWN"] += 1
            normalized = m.filename.replace("\\", "/")
            if interval == "15" and EUR15_RE.search(normalized) and looks_eur(normalized):
                eur_15.append(m.filename)

        manifest_payload = None
        manifest_error = None
        if manifests:
            target = manifests[0]
            if target.file_size <= 5_000_000:
                try:
                    manifest_payload = json.loads(zf.read(target).decode("utf-8"))
                except Exception as exc:
                    manifest_error = f"{type(exc).__name__}: {exc}"
            else:
                manifest_error = "manifest exceeds 5MB read guardrail"

        bad = zf.testzip()

    return {
        "kind": "KRAKEN_OHLCVT_ARCHIVE_INSPECTION_V1",
        "status": "PASS" if bad is None else "FAIL_CORRUPT_MEMBER",
        "archive": str(path),
        "member_count": len(members),
        "csv_count": len(csvs),
        "interval_counts": dict(sorted(interval_counts.items())),
        "manifest_members": [m.filename for m in manifests],
        "manifest": manifest_payload,
        "manifest_error": manifest_error,
        "likely_eur_15m_count": len(eur_15),
        "likely_eur_15m_sample": sorted(eur_15)[:25],
        "zip_test_bad_member": bad,
        "extraction_performed": False,
        "active_strategy_changed": False,
        "paper_shadow_runtime_changed": False,
        "next_gate": (
            "selective_eur_15m_extraction"
            if bad is None and eur_15
            else "inspect_archive_naming_before_extraction"
        ),
        "interpretation_guardrail": (
            "EUR/interval detection is filename-based inventory only; verify "
            "archive MANIFEST/naming before selective extraction."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("archive", type=Path)
    args = ap.parse_args()
    result = inspect(args.archive)
    print("KRAKEN_OHLCVT_ARCHIVE_INSPECTION " + json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
