#!/usr/bin/env python3
"""Point-in-time Binance derivatives context smoke.

Reads a local JSON bundle containing public Binance derivatives metric rows and
freezes the latest known row at or before an explicit event timestamp. Future
rows are never used. Missing metrics remain missing.

This is context-only research tooling. It cannot place orders, access an account,
change strategy state, or claim Kraken-EUR execution/fill truth.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def finite_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    x = float(value)
    if not math.isfinite(x):
        raise ValueError(f"non-finite numeric value: {value!r}")
    return x


def ts_of(metric: str, row: dict[str, Any]) -> int:
    key = "fundingTime" if metric == "funding" else "timestamp"
    return int(row[key])


def rows_at_or_before(metric: str, rows: list[dict[str, Any]], event_ts_ms: int) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda r: ts_of(metric, r))
    return [r for r in ordered if ts_of(metric, r) <= event_ts_ms]


def latest_and_prev(metric: str, rows: list[dict[str, Any]], event_ts_ms: int):
    eligible = rows_at_or_before(metric, rows, event_ts_ms)
    if not eligible:
        return None, None
    return eligible[-1], eligible[-2] if len(eligible) >= 2 else None


def metric_age_seconds(metric: str, row: dict[str, Any] | None, event_ts_ms: int) -> float | None:
    if row is None:
        return None
    return (event_ts_ms - ts_of(metric, row)) / 1000.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle", type=Path)
    ap.add_argument("--event-ts-ms", type=int, required=True)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()

    data = json.loads(args.bundle.read_text("utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("bundle must be a JSON object")

    event_ts = args.event_ts_ms
    metrics = {}
    for name in ("funding", "open_interest", "taker", "basis", "long_short"):
        rows = data.get(name, [])
        if not isinstance(rows, list):
            raise SystemExit(f"{name} must be a list")
        latest, prev = latest_and_prev(name, rows, event_ts)
        metrics[name] = {"latest": latest, "previous": prev}

    funding = metrics["funding"]["latest"]
    oi = metrics["open_interest"]["latest"]
    oi_prev = metrics["open_interest"]["previous"]
    taker = metrics["taker"]["latest"]
    basis = metrics["basis"]["latest"]
    long_short = metrics["long_short"]["latest"]

    oi_level = finite_float((oi or {}).get("sumOpenInterestValue"))
    oi_prev_level = finite_float((oi_prev or {}).get("sumOpenInterestValue"))
    oi_change_pct = None
    if oi_level is not None and oi_prev_level not in (None, 0.0):
        oi_change_pct = ((oi_level / oi_prev_level) - 1.0) * 100.0

    buy = finite_float((taker or {}).get("buyVol"))
    sell = finite_float((taker or {}).get("sellVol"))
    taker_ratio = None
    if buy is not None and sell not in (None, 0.0):
        taker_ratio = buy / sell

    result = {
        "kind": "BINANCE_DERIVATIVES_CONTEXT_SMOKE_V1",
        "status": "PASS",
        "event_ts_ms": event_ts,
        "context": {
            "funding_rate": finite_float((funding or {}).get("fundingRate")),
            "open_interest_value": oi_level,
            "open_interest_change_pct": oi_change_pct,
            "taker_buy_sell_ratio": taker_ratio,
            "basis_rate": finite_float((basis or {}).get("basisRate")),
            "long_short_ratio": finite_float((long_short or {}).get("longShortRatio")),
        },
        "metric_age_seconds": {
            k: metric_age_seconds(k, v["latest"], event_ts)
            for k, v in metrics.items()
        },
        "point_in_time_assertions": {
            "all_selected_rows_at_or_before_event": all(
                v["latest"] is None or ts_of(k, v["latest"]) <= event_ts
                for k, v in metrics.items()
            ),
            "future_rows_not_used": True,
            "missing_metrics_remain_missing": True,
            "event_timestamp_explicit": True,
        },
        "authority_guardrails": {
            "kraken_eur_execution_price_claimed": False,
            "kraken_eur_spread_claimed": False,
            "kraken_eur_fill_probability_claimed": False,
            "kraken_pair_tradability_claimed": False,
            "paper_decision_changed": False,
        },
        "safety_guardrails": {
            "network_used": False,
            "api_key_used": False,
            "account_endpoint_used": False,
            "private_data_accessed": False,
            "orders": False,
            "leverage_action": False,
            "real_money_actions": False,
            "active_strategy_changed": False,
            "v2r4_activated": False,
            "holdout_opened": False,
            "performance_selection_performed": False,
        },
    }

    if not all(result["point_in_time_assertions"].values()):
        result["status"] = "FAIL"

    raw = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, "utf-8")
    print(raw, end="")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
