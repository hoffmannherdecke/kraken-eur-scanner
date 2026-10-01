#!/usr/bin/env python3
"""Point-in-time replay smoke on one normalized Kraken EUR 15m pair.

This is a methodology/integrity smoke only. It does not evaluate trading edge.
It freezes a feature/decision record using only bars visible by data_cutoff_time,
then generates future MFE/MAE/return labels afterward from later bars.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

EXPECTED_HEADER = [
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


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def canonical_sha(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != EXPECTED_HEADER:
            raise ValueError(f"unexpected normalized header: {reader.fieldnames}")

        previous_start: int | None = None
        for line_no, row in enumerate(reader, 2):
            start = int(row["bar_start_epoch"])
            end = int(row["bar_end_epoch"])
            if end <= start:
                raise ValueError(f"line {line_no}: bar_end <= bar_start")
            if previous_start is not None and start <= previous_start:
                raise ValueError(f"line {line_no}: non-monotonic bar_start")
            previous_start = start

            rows.append(
                {
                    "bar_start_epoch": start,
                    "bar_end_epoch": end,
                    "bar_start_utc": row["bar_start_utc"],
                    "bar_end_utc": row["bar_end_utc"],
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                    "trades": int(row["trades"]),
                }
            )
    if not rows:
        raise ValueError("normalized pair file is empty")
    return rows


def pct(a: float, b: float) -> float:
    return 100.0 * (a / b - 1.0)


def choose_index(row_count: int, lookback: int, horizon: int, explicit: int | None) -> int:
    minimum = max(lookback, 12)
    maximum = row_count - horizon - 1
    if maximum < minimum:
        raise ValueError(
            f"not enough rows for replay: rows={row_count} lookback={lookback} horizon={horizon}"
        )
    if explicit is not None:
        if not (minimum <= explicit <= maximum):
            raise ValueError(f"decision-index must be between {minimum} and {maximum}")
        return explicit
    return minimum + (maximum - minimum) // 2


def build_decision(rows: list[dict[str, Any]], idx: int, lookback: int) -> dict[str, Any]:
    decision_bar = rows[idx]
    cutoff = decision_bar["bar_end_epoch"]

    visible = [r for r in rows if r["bar_end_epoch"] <= cutoff]
    if not visible or visible[-1]["bar_start_epoch"] != decision_bar["bar_start_epoch"]:
        raise AssertionError("decision bar is not the final visible closed bar")

    window = visible[-lookback:]
    if len(window) != lookback:
        raise AssertionError("lookback window incomplete")

    closes = [r["close"] for r in window]
    volumes = [r["volume"] for r in window]
    trades = [r["trades"] for r in window]

    decision = {
        "kind": "KRAKEN_EUR15_REAL_PAIR_PIT_DECISION_V1",
        "feature_schema_version": "KRAKEN_EUR15_REAL_PAIR_FEATURES_V1",
        "decision_index": idx,
        "event_time_utc": decision_bar["bar_end_utc"],
        "data_cutoff_epoch": cutoff,
        "data_cutoff_utc": decision_bar["bar_end_utc"],
        "decision_time_utc": decision_bar["bar_end_utc"],
        "last_visible_bar_start_epoch": decision_bar["bar_start_epoch"],
        "last_visible_bar_end_epoch": decision_bar["bar_end_epoch"],
        "visible_closed_bar_count": len(visible),
        "lookback_bars": lookback,
        "features": {
            "return_1h_pct": round(pct(decision_bar["close"], rows[idx - 4]["close"]), 12),
            "return_3h_pct": round(pct(decision_bar["close"], rows[idx - 12]["close"]), 12),
            "return_lookback_pct": round(pct(closes[-1], closes[0]), 12),
            "mean_volume_lookback": round(sum(volumes) / len(volumes), 12),
            "last_volume_vs_mean": round(volumes[-1] / (sum(volumes) / len(volumes)), 12)
            if sum(volumes) > 0
            else None,
            "mean_trades_lookback": round(sum(trades) / len(trades), 12),
        },
        "point_in_time_assertions": {
            "max_feature_bar_end_epoch": max(r["bar_end_epoch"] for r in window),
            "future_bar_in_features": any(r["bar_end_epoch"] > cutoff for r in window),
            "feature_visibility_rule": "bar_end_epoch <= data_cutoff_epoch",
        },
    }
    if decision["point_in_time_assertions"]["future_bar_in_features"]:
        raise AssertionError("future bar leaked into feature window")
    if decision["point_in_time_assertions"]["max_feature_bar_end_epoch"] > cutoff:
        raise AssertionError("feature window exceeds cutoff")
    return decision


def build_label(
    rows: list[dict[str, Any]],
    idx: int,
    horizon: int,
    decision_hash: str,
) -> dict[str, Any]:
    decision_bar = rows[idx]
    cutoff = decision_bar["bar_end_epoch"]
    future = rows[idx + 1 : idx + 1 + horizon]
    if len(future) != horizon:
        raise AssertionError("future label horizon incomplete")
    if any(r["bar_start_epoch"] < cutoff for r in future):
        raise AssertionError("label contains a bar that starts before decision cutoff")

    entry = decision_bar["close"]
    return {
        "kind": "KRAKEN_EUR15_REAL_PAIR_PIT_LABEL_V1",
        "decision_sha256": decision_hash,
        "generated_after_decision_freeze": True,
        "horizon_bars": horizon,
        "label_first_bar_start_epoch": future[0]["bar_start_epoch"],
        "label_last_bar_end_epoch": future[-1]["bar_end_epoch"],
        "entry_reference_close": entry,
        "end_return_pct": round(pct(future[-1]["close"], entry), 12),
        "mfe_pct": round(pct(max(r["high"] for r in future), entry), 12),
        "mae_pct": round(pct(min(r["low"] for r in future), entry), 12),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("normalized_pair", type=Path)
    ap.add_argument("--lookback-bars", type=int, default=20)
    ap.add_argument("--horizon-bars", type=int, default=24)
    ap.add_argument("--decision-index", type=int)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()

    if args.lookback_bars < 13:
        raise SystemExit("--lookback-bars must be >=13")
    if args.horizon_bars < 1:
        raise SystemExit("--horizon-bars must be >=1")

    rows = load_rows(args.normalized_pair)
    idx = choose_index(len(rows), args.lookback_bars, args.horizon_bars, args.decision_index)

    decision_a = build_decision(rows, idx, args.lookback_bars)
    decision_b = build_decision(list(rows), idx, args.lookback_bars)
    decision_sha_a = canonical_sha(decision_a)
    decision_sha_b = canonical_sha(decision_b)
    if decision_sha_a != decision_sha_b:
        raise AssertionError("decision record is not deterministic")

    label = build_label(rows, idx, args.horizon_bars, decision_sha_a)

    result = {
        "kind": "KRAKEN_EUR15_REAL_PAIR_PIT_REPLAY_SMOKE_V1",
        "status": "PASS",
        "normalized_pair": str(args.normalized_pair),
        "normalized_pair_sha256": sha256_file(args.normalized_pair),
        "row_count": len(rows),
        "decision": decision_a,
        "decision_sha256": decision_sha_a,
        "label": label,
        "interpretation_guardrail": (
            "Methodology/integrity smoke only. The selected midpoint observation and "
            "future label must not be interpreted as strategy-performance evidence."
        ),
        "guardrails": {
            "network_used": False,
            "active_strategy_changed": False,
            "paper_shadow_runtime_changed": False,
            "historical_strategy_tuning_performed": False,
        },
        "next_gate": "record_real_pair_replay_in_trial_ledger_then_broader_historical_replay",
    }

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        tmp = args.output.with_suffix(args.output.suffix + ".tmp")
        tmp.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", "utf-8")
        tmp.replace(args.output)

    print("KRAKEN_EUR15_REAL_PAIR_PIT_REPLAY " + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
