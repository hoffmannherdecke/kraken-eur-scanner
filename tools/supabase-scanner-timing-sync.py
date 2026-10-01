#!/usr/bin/env python3
"""Archive scanner handoff timing evidence to Supabase.

Backend-only GitHub Action helper. Requires existing Supabase archive credentials.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path):
    return json.loads(path.read_text("utf-8"))


def main() -> int:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = (
        os.environ.get("SUPABASE_SECRET_KEY", "").strip()
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )
    if not url or not key:
        raise SystemExit("Supabase archive credentials missing")

    rows = []
    q = ROOT / "handoff_queue"
    for path in sorted(q.glob("*.json")) if q.exists() else []:
        try:
            h = load(path)
        except Exception:
            continue

        pair = h.get("pair")
        detected = h.get("candidate_detected_at_utc")
        queued = h.get("queued_at")
        if not pair or not detected or not queued:
            continue

        rows.append(
            {
                "handoff_id": path.stem,
                "pair": pair,
                "detected_at": detected,
                "queued_at": queued,
                "source_run_id": h.get("source_run_id"),
                "rank": h.get("rank"),
                "score": h.get("score"),
                "payload": h,
            }
        )

    if not rows:
        print(json.dumps({"scanner_handoffs": 0}, sort_keys=True))
        return 0

    endpoint = (
        url.rstrip("/")
        + "/rest/v1/scanner_detection_evidence?on_conflict="
        + urllib.parse.quote("handoff_id")
    )
    headers = {
        "apikey": key,
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
        "User-Agent": "kraken-scanner-timing-sync/1.0",
    }
    if not key.startswith("sb_secret_"):
        headers["Authorization"] = "Bearer " + key

    # Handoff payloads are small, but batch anyway to keep this robust as history grows.
    uploaded = 0
    for start in range(0, len(rows), 100):
        batch = rows[start : start + 100]
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(batch, separators=(",", ":")).encode("utf-8"),
            method="POST",
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            if not 200 <= resp.status < 300:
                raise RuntimeError(f"scanner_detection_evidence HTTP {resp.status}")
        uploaded += len(batch)

    print(json.dumps({"scanner_handoffs": uploaded}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
