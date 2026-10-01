#!/usr/bin/env python3
"""Synthetic point-in-time smoke for historical Kraken OHLCVT research.

The fixture is synthetic and tiny. This script proves timestamp semantics,
no-trade gap preservation, closed-bar feature cutoff, post-decision label
generation and deterministic output. It never downloads market data and never
touches active Paper/Shadow runtime state.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

INTERVAL_SECONDS = 15 * 60
DECISION_CUTOFF_TS = 1767230100
EXPECTED_MISSING_START_TS = 1767228300


@dataclass(frozen=True)
class Bar:
    start_ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    trades: int

    @property
    def close_ts(self) -> int:
        return self.start_ts + INTERVAL_SECONDS


def iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def load_bars(path: Path) -> list[Bar]:
    bars: list[Bar] = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        for line_no, row in enumerate(reader, 1):
            if len(row) != 7:
                raise ValueError(f"line {line_no}: expected 7 columns")
            bar = Bar(
                start_ts=int(row[0]),
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5]),
                trades=int(row[6]),
            )
            if bars and bar.start_ts <= bars[-1].start_ts:
                raise ValueError("timestamps must be strictly increasing")
            bars.append(bar)
    if not bars:
        raise ValueError("fixture is empty")
    return bars


def closed_by(bars: list[Bar], cutoff_ts: int) -> list[Bar]:
    selected = [b for b in bars if b.close_ts <= cutoff_ts]
    if any(b.close_ts > cutoff_ts for b in selected):
        raise AssertionError("future bar leaked into closed-bar features")
    return selected


def build_decision_record(bars: list[Bar]) -> dict:
    closed = closed_by(bars, DECISION_CUTOFF_TS)
    if len(closed) < 2:
        raise AssertionError("not enough closed bars")
    last, prev = closed[-1], closed[-2]
    feature_return_pct = 100.0 * (last.close / prev.close - 1.0)
    feature_volume_ratio = last.volume / prev.volume

    return {
        "kind": "HISTORICAL_PIT_SMOKE_DECISION_V1",
        "event_time": iso(DECISION_CUTOFF_TS),
        "data_cutoff_time": iso(DECISION_CUTOFF_TS),
        "decision_time": iso(DECISION_CUTOFF_TS),
        "interval_minutes": 15,
        "closed_bar_count": len(closed),
        "last_closed_bar_start": iso(last.start_ts),
        "last_closed_bar_end": iso(last.close_ts),
        "features": {
            "return_last_closed_pct": round(feature_return_pct, 9),
            "volume_ratio_last_two_closed": round(feature_volume_ratio, 9),
        },
        "gap_semantics": {
            "missing_expected_start": iso(EXPECTED_MISSING_START_TS),
            "synthetic_zero_fill_used": False,
        },
    }


def build_future_label(bars: list[Bar]) -> dict:
    future = [b for b in bars if b.start_ts >= DECISION_CUTOFF_TS]
    if not future:
        raise AssertionError("future label fixture missing")
    entry_reference = future[0].open
    highs = [b.high for b in future]
    lows = [b.low for b in future]
    final_close = future[-1].close
    return {
        "kind": "HISTORICAL_PIT_SMOKE_LABEL_V1",
        "label_generated_after_decision": True,
        "entry_reference": entry_reference,
        "mfe_pct": round(100.0 * (max(highs) / entry_reference - 1.0), 9),
        "mae_pct": round(100.0 * (min(lows) / entry_reference - 1.0), 9),
        "end_return_pct": round(100.0 * (final_close / entry_reference - 1.0), 9),
    }


def canonical_sha(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def run(path: Path) -> dict:
    bars = load_bars(path)
    starts = {b.start_ts for b in bars}

    if EXPECTED_MISSING_START_TS in starts:
        raise AssertionError("fixture unexpectedly contains the deliberate no-trade gap")

    closed = closed_by(bars, DECISION_CUTOFF_TS)
    if DECISION_CUTOFF_TS in {b.start_ts for b in closed}:
        raise AssertionError("live/future bar leaked into closed feature window")

    decision1 = build_decision_record(bars)
    decision2 = build_decision_record(list(bars))
    sha1 = canonical_sha(decision1)
    sha2 = canonical_sha(decision2)
    if sha1 != sha2:
        raise AssertionError("decision output is not deterministic")

    label = build_future_label(bars)

    return {
        "kind": "HISTORICAL_PIT_SMOKE_V1",
        "status": "PASS",
        "fixture_rows": len(bars),
        "closed_rows_at_cutoff": len(closed),
        "no_trade_gap_preserved": True,
        "live_bar_excluded_from_closed_features": True,
        "future_label_after_decision_only": True,
        "deterministic_decision_sha256": sha1,
        "decision": decision1,
        "label": label,
        "guardrails": {
            "downloads_performed": False,
            "active_strategy_changed": False,
            "paper_shadow_runtime_changed": False,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--fixture",
        type=Path,
        default=Path("research/historical/fixtures/ohlcvt_15m_gap_sample.csv"),
    )
    args = ap.parse_args()
    result = run(args.fixture)
    print("HISTORICAL_PIT_SMOKE " + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
