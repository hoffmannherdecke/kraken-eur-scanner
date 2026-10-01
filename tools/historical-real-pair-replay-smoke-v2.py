#!/usr/bin/env python3
"""Point-in-time replay smoke V2 on one normalized Kraken EUR 15m pair.

V2 tightens the V1 methodology by requiring a fully contiguous 15-minute
history window for time-labelled features (1h/3h) and a fully contiguous
future horizon for labels. This prevents sparse/no-trade rows from silently
turning "4 rows" into more than one wall-clock hour.

Methodology/integrity only. No trading-edge claim is permitted.
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
INTERVAL_SECONDS = 900
KIND = "KRAKEN_EUR15_REAL_PAIR_PIT_REPLAY_SMOKE_V2"
FEATURE_SCHEMA = "KRAKEN_EUR15_REAL_PAIR_FEATURES_V2_CONTIGUOUS"


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
            if end - start != INTERVAL_SECONDS:
                raise ValueError(f"line {line_no}: unexpected bar duration")
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


def contiguous(starts: list[int]) -> bool:
    return all((b - a) == INTERVAL_SECONDS for a, b in zip(starts, starts[1:]))


def eligible_index(
    rows: list[dict[str, Any]],
    idx: int,
    lookback: int,
    horizon: int,
) -> bool:
    history_start = idx - (lookback - 1)
    future_end = idx + horizon
    if history_start < 0 or future_end >= len(rows):
        return False

    history = rows[history_start : idx + 1]
    future = rows[idx + 1 : idx + 1 + horizon]

    history_starts = [r["bar_start_epoch"] for r in history]
    future_starts = [rows[idx]["bar_start_epoch"]] + [
        r["bar_start_epoch"] for r in future
    ]
    return contiguous(history_starts) and contiguous(future_starts)


def eligible_indices(
    rows: list[dict[str, Any]],
    lookback: int,
    horizon: int,
) -> list[int]:
    minimum = max(lookback - 1, 12)
    maximum = len(rows) - horizon - 1
    if maximum < minimum:
        return []
    return [
        idx
        for idx in range(minimum, maximum + 1)
        if eligible_index(rows, idx, lookback, horizon)
    ]


def choose_index(
    rows: list[dict[str, Any]],
    lookback: int,
    horizon: int,
    explicit: int | None,
) -> tuple[int, int]:
    eligible = eligible_indices(rows, lookback, horizon)
    if not eligible:
        raise ValueError(
            f"no contiguous replay window: rows={len(rows)} lookback={lookback} horizon={horizon}"
        )
    if explicit is not None:
        if explicit not in set(eligible):
            raise ValueError("explicit decision-index is not a contiguous eligible window")
        return explicit, len(eligible)
    return eligible[len(eligible) // 2], len(eligible)


def build_decision(rows: list[dict[str, Any]], idx: int, lookback: int) -> dict[str, Any]:
    decision_bar = rows[idx]
    cutoff = decision_bar["bar_end_epoch"]
    visible = [r for r in rows if r["bar_end_epoch"] <= cutoff]

    if not visible or visible[-1]["bar_start_epoch"] != decision_bar["bar_start_epoch"]:
        raise AssertionError("decision bar is not the final visible closed bar")

    window = rows[idx - (lookback - 1) : idx + 1]
    if len(window) != lookback:
        raise AssertionError("lookback window incomplete")
    if not contiguous([r["bar_start_epoch"] for r in window]):
        raise AssertionError("lookback window is not contiguous")

    if rows[idx - 4]["bar_start_epoch"] != decision_bar["bar_start_epoch"] - 4 * INTERVAL_SECONDS:
        raise AssertionError("1h feature anchor is not exactly 1h earlier")
    if rows[idx - 12]["bar_start_epoch"] != decision_bar["bar_start_epoch"] - 12 * INTERVAL_SECONDS:
        raise AssertionError("3h feature anchor is not exactly 3h earlier")

    closes = [r["close"] for r in window]
    volumes = [r["volume"] for r in window]
    trades = [r["trades"] for r in window]

    decision = {
        "kind": "KRAKEN_EUR15_REAL_PAIR_PIT_DECISION_V2",
        "feature_schema_version": FEATURE_SCHEMA,
        "decision_index": idx,
        "event_time_utc": decision_bar["bar_end_utc"],
        "data_cutoff_epoch": cutoff,
        "data_cutoff_utc": decision_bar["bar_end_utc"],
        "decision_time_utc": decision_bar["bar_end_utc"],
        "last_visible_bar_start_epoch": decision_bar["bar_start_epoch"],
        "last_visible_bar_end_epoch": decision_bar["bar_end_epoch"],
        "visible_closed_bar_count": len(visible),
        "lookback_bars": lookback,
        "lookback_wall_clock_seconds": (lookback - 1) * INTERVAL_SECONDS,
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
            "history_contiguous_15m": True,
            "return_1h_exact_wall_clock": True,
            "return_3h_exact_wall_clock": True,
        },
    }
    if decision["point_in_time_assertions"]["future_bar_in_features"]:
        raise AssertionError("future bar leaked into feature window")
    return decision


def build_label(
    rows: list[dict[str, Any]],
    idx: int,
    horizon: int,
    decision_hash: str,
) -> dict[str, Any]:
    decision_bar = rows[idx]
    future = rows[idx + 1 : idx + 1 + horizon]
    if len(future) != horizon:
        raise AssertionError("future label horizon incomplete")

    starts = [decision_bar["bar_start_epoch"]] + [r["bar_start_epoch"] for r in future]
    if not contiguous(starts):
        raise AssertionError("future label horizon is not contiguous")

    cutoff = decision_bar["bar_end_epoch"]
    if future[0]["bar_start_epoch"] != cutoff:
        raise AssertionError("future label does not start exactly at decision cutoff")

    expected_end = cutoff + horizon * INTERVAL_SECONDS
    if future[-1]["bar_end_epoch"] != expected_end:
        raise AssertionError("future label wall-clock horizon mismatch")

    entry = decision_bar["close"]
    return {
        "kind": "KRAKEN_EUR15_REAL_PAIR_PIT_LABEL_V2",
        "decision_sha256": decision_hash,
        "generated_after_decision_freeze": True,
        "horizon_bars": horizon,
        "horizon_wall_clock_seconds": horizon * INTERVAL_SECONDS,
        "label_first_bar_start_epoch": future[0]["bar_start_epoch"],
        "label_last_bar_end_epoch": future[-1]["bar_end_epoch"],
        "future_contiguous_15m": True,
        "entry_reference_close": entry,
        "end_return_pct": round(pct(future[-1]["close"], entry), 12),
        "mfe_pct": round(pct(max(r["high"] for r in future), entry), 12),
        "mae_pct": round(pct(min(r["low"] for r in future), entry), 12),
    }


def run_replay(
    normalized_pair: Path,
    lookback_bars: int,
    horizon_bars: int,
    decision_index: int | None = None,
) -> dict[str, Any]:
    rows = load_rows(normalized_pair)
    idx, eligible_count = choose_index(
        rows,
        lookback_bars,
        horizon_bars,
        decision_index,
    )

    decision_a = build_decision(rows, idx, lookback_bars)
    decision_b = build_decision(list(rows), idx, lookback_bars)
    decision_sha_a = canonical_sha(decision_a)
    decision_sha_b = canonical_sha(decision_b)
    if decision_sha_a != decision_sha_b:
        raise AssertionError("decision record is not deterministic")

    label = build_label(rows, idx, horizon_bars, decision_sha_a)

    return {
        "kind": KIND,
        "status": "PASS",
        "normalized_pair": str(normalized_pair),
        "normalized_pair_sha256": sha256_file(normalized_pair),
        "row_count": len(rows),
        "eligible_contiguous_decision_windows": eligible_count,
        "decision": decision_a,
        "decision_sha256": decision_sha_a,
        "label": label,
        "interpretation_guardrail": (
            "Methodology/integrity smoke only. No strategy-performance conclusion "
            "may be drawn from this selected contiguous observation."
        ),
        "methodology_revision": {
            "supersedes": "KRAKEN_EUR15_REAL_PAIR_PIT_REPLAY_SMOKE_V1",
            "reason": (
                "V2 requires exact 15m contiguity so row-count based 1h/3h "
                "features and label horizons equal wall-clock time."
            ),
        },
        "guardrails": {
            "network_used": False,
            "active_strategy_changed": False,
            "paper_shadow_runtime_changed": False,
            "historical_strategy_tuning_performed": False,
        },
        "next_gate": "broader_historical_point_in_time_replay_v2",
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

    result = run_replay(
        args.normalized_pair,
        args.lookback_bars,
        args.horizon_bars,
        args.decision_index,
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        tmp = args.output.with_suffix(args.output.suffix + ".tmp")
        tmp.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", "utf-8")
        tmp.replace(args.output)

    print("KRAKEN_EUR15_REAL_PAIR_PIT_REPLAY_V2 " + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
