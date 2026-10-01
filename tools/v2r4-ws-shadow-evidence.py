#!/usr/bin/env python3
"""Read-only local evidence summary for the active V2R4 WS shadow runtime."""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)


def stats(values: list[float]) -> dict[str, Any]:
    clean = sorted(v for v in values if math.isfinite(v))
    if not clean:
        return {"n": 0, "mean": None, "median": None, "p90": None, "max": None}
    p90_idx = min(len(clean) - 1, max(0, math.ceil(0.9 * len(clean)) - 1))
    return {
        "n": len(clean),
        "mean": round(statistics.fmean(clean), 3),
        "median": round(statistics.median(clean), 3),
        "p90": round(clean[p90_idx], 3),
        "max": round(clean[-1], 3),
    }


def load_lines(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    return rows


def main() -> int:
    home = Path.home()
    trading = home / "Trading"

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ledger",
        type=Path,
        default=trading / "Logs" / "v2r4-ws-shadow-ledger.jsonl",
    )
    parser.add_argument(
        "--heartbeat",
        type=Path,
        default=trading / "State" / "v2r4-ws-shadow-heartbeat.json",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=trading / "State" / "v2r4-ws-shadow-runtime.json",
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=24.0,
        help="summarize rows observed within the most recent N hours",
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if args.hours <= 0:
        raise SystemExit("--hours must be > 0")

    now = datetime.now(timezone.utc)
    cutoff = now.timestamp() - args.hours * 3600.0

    ledger_paths = []
    if args.ledger.exists():
        ledger_paths.append(args.ledger)
    ledger_paths.extend(sorted(args.ledger.parent.glob(args.ledger.stem + "-*" + args.ledger.suffix)))

    rows = []
    for row in load_lines(ledger_paths):
        observed = row.get("observed_at_utc")
        if not observed:
            continue
        try:
            if parse_utc(str(observed)).timestamp() < cutoff:
                continue
        except Exception:
            continue
        rows.append(row)

    cycles = [r for r in rows if r.get("record_type") == "cycle"]
    events = [r for r in rows if r.get("record_type") == "event"]

    status_counts = Counter(str(r.get("status") or "UNKNOWN") for r in cycles)
    reason_counts: Counter[str] = Counter()
    pair_counts: Counter[str] = Counter()
    source_age: list[float] = []
    feed_latency_ms: list[float] = []
    snapshot_latency_ms: list[float] = []

    stale_pairs_total = 0
    changed_pairs_total = 0
    triggered_pairs_total = 0
    gap_suppressed_cycles = 0
    max_recovery_epoch = 0

    for row in cycles:
        value = row.get("source_age_seconds")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            source_age.append(float(value))
        stale_pairs_total += int(row.get("stale_pairs") or 0)
        changed_pairs_total += int(row.get("changed_pairs") or 0)
        triggered_pairs_total += int(row.get("triggered_pairs") or 0)
        if row.get("gap_suppressed") is True:
            gap_suppressed_cycles += 1
        max_recovery_epoch = max(max_recovery_epoch, int(row.get("recovery_epoch") or 0))

    for event in events:
        pair_counts[str(event.get("pair") or "UNKNOWN")] += 1
        for reason in event.get("reasons") or []:
            reason_counts[str(reason)] += 1
        for bucket, key in (
            (feed_latency_ms, "feed_to_shadow_latency_ms"),
            (snapshot_latency_ms, "snapshot_to_shadow_latency_ms"),
        ):
            value = event.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                bucket.append(float(value))

    heartbeat = None
    if args.heartbeat.exists():
        try:
            heartbeat = json.loads(args.heartbeat.read_text("utf-8"))
        except Exception:
            heartbeat = None

    manifest = None
    if args.manifest.exists():
        try:
            manifest = json.loads(args.manifest.read_text("utf-8"))
        except Exception:
            manifest = None

    report = {
        "kind": "V2R4_WS_SHADOW_EVIDENCE_V1",
        "generated_at_utc": now.isoformat().replace("+00:00", "Z"),
        "window_hours": args.hours,
        "ledger_files": [str(p) for p in ledger_paths if p.exists()],
        "cycle_count": len(cycles),
        "event_count": len(events),
        "cycle_status_counts": dict(status_counts),
        "source_age_seconds": stats(source_age),
        "feed_to_shadow_latency_ms": stats(feed_latency_ms),
        "snapshot_to_shadow_latency_ms": stats(snapshot_latency_ms),
        "stale_pairs_total": stale_pairs_total,
        "changed_pairs_total": changed_pairs_total,
        "triggered_pairs_total": triggered_pairs_total,
        "gap_suppressed_cycles": gap_suppressed_cycles,
        "max_recovery_epoch": max_recovery_epoch,
        "top_event_pairs": pair_counts.most_common(20),
        "top_trigger_reasons": reason_counts.most_common(20),
        "latest_heartbeat": heartbeat,
        "runtime_manifest": manifest,
        "guardrails": {
            "read_only_summary": True,
            "evaluator_invoked": False,
            "order_api": False,
            "real_money_actions": False,
            "promotion_decision_made": False,
        },
    }

    out = args.out or (trading / "Logs" / "v2r4-ws-shadow-evidence-latest.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", "utf-8")

    print(
        "V2R4_WS_SHADOW_EVIDENCE "
        + json.dumps(
            {
                "window_hours": args.hours,
                "cycles": len(cycles),
                "events": len(events),
                "status_counts": dict(status_counts),
                "source_age_median_s": report["source_age_seconds"]["median"],
                "source_age_p90_s": report["source_age_seconds"]["p90"],
                "feed_to_shadow_p90_ms": report["feed_to_shadow_latency_ms"]["p90"],
                "triggered_pairs_total": triggered_pairs_total,
                "gap_suppressed_cycles": gap_suppressed_cycles,
                "max_recovery_epoch": max_recovery_epoch,
                "heartbeat_status": (heartbeat or {}).get("status"),
                "runtime_commit": (manifest or {}).get("runtime_commit"),
            },
            sort_keys=True,
        )
    )
    print("V2R4_WS_SHADOW_TOP_PAIRS " + json.dumps(pair_counts.most_common(10)))
    print("V2R4_WS_SHADOW_TOP_REASONS " + json.dumps(reason_counts.most_common(10)))
    print("Report: " + str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
