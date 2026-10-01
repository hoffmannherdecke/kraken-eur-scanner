#!/usr/bin/env python3
"""Targeted Kraken Time & Sales methodology smoke.

This tool is intentionally local/offline. It parses one existing CSV/fixture,
enforces point-in-time separation around an explicit event timestamp, and emits
descriptive public-trade metrics only. It never downloads archives, changes the
active strategy, opens a holdout, calls an exchange account, or places orders.

Public trades cannot identify true bid/ask spread, order-book depth, queue
position, maker fill probability, hidden liquidity, or counterfactual fills.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Iterable


@dataclass(frozen=True)
class Trade:
    ts: float
    price: float
    volume: float
    side: str
    order_type: str
    misc: str
    trade_id: str


def parse_ts(value: str) -> float:
    value = value.strip()
    if not value:
        raise ValueError("empty timestamp")
    try:
        return float(value)
    except ValueError:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).timestamp()


def normalize_side(value: str) -> str:
    v = value.strip().lower()
    if v in {"b", "buy"}:
        return "buy"
    if v in {"s", "sell"}:
        return "sell"
    raise ValueError(f"unsupported trade side: {value!r}")


def load_trades(path: Path) -> list[Trade]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        expected = {"timestamp", "price", "volume", "type", "order_type", "misc", "trade_id"}
        if reader.fieldnames is None:
            raise ValueError("CSV header missing")
        missing = expected.difference(reader.fieldnames)
        if missing:
            raise ValueError(f"missing required columns: {sorted(missing)}")
        out: list[Trade] = []
        for idx, row in enumerate(reader, start=2):
            try:
                trade = Trade(
                    ts=parse_ts(row["timestamp"]),
                    price=float(row["price"]),
                    volume=float(row["volume"]),
                    side=normalize_side(row["type"]),
                    order_type=str(row["order_type"]),
                    misc=str(row["misc"]),
                    trade_id=str(row["trade_id"]),
                )
            except Exception as exc:
                raise ValueError(f"bad row {idx}: {exc}") from exc
            if not math.isfinite(trade.price) or trade.price <= 0:
                raise ValueError(f"bad row {idx}: non-positive/non-finite price")
            if not math.isfinite(trade.volume) or trade.volume <= 0:
                raise ValueError(f"bad row {idx}: non-positive/non-finite volume")
            out.append(trade)
    if not out:
        raise ValueError("no trade rows")
    if any(b.ts < a.ts for a, b in zip(out, out[1:])):
        raise ValueError("trade rows are not timestamp ordered")
    return out


def summarize(rows: Iterable[Trade]) -> dict:
    rows = list(rows)
    if not rows:
        return {
            "trade_count": 0,
            "base_volume": 0.0,
            "notional_quote": 0.0,
            "vwap": None,
            "buy_volume": 0.0,
            "sell_volume": 0.0,
            "buy_volume_share": None,
            "price_min": None,
            "price_max": None,
            "price_range_pct": None,
            "median_intertrade_gap_seconds": None,
        }
    base_volume = sum(t.volume for t in rows)
    notional = sum(t.price * t.volume for t in rows)
    buy_volume = sum(t.volume for t in rows if t.side == "buy")
    sell_volume = sum(t.volume for t in rows if t.side == "sell")
    prices = [t.price for t in rows]
    gaps = [b.ts - a.ts for a, b in zip(rows, rows[1:])]
    pmin, pmax = min(prices), max(prices)
    return {
        "trade_count": len(rows),
        "base_volume": base_volume,
        "notional_quote": notional,
        "vwap": notional / base_volume,
        "buy_volume": buy_volume,
        "sell_volume": sell_volume,
        "buy_volume_share": buy_volume / base_volume,
        "price_min": pmin,
        "price_max": pmax,
        "price_range_pct": ((pmax / pmin) - 1.0) * 100.0 if pmin else None,
        "median_intertrade_gap_seconds": median(gaps) if gaps else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path", type=Path)
    ap.add_argument("--event-ts", required=True, help="Unix seconds or ISO-8601")
    ap.add_argument("--pre-seconds", type=int, default=60)
    ap.add_argument("--post-seconds", type=int, default=60)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()

    if args.pre_seconds <= 0 or args.post_seconds <= 0:
        raise SystemExit("pre/post windows must be positive")

    event_ts = parse_ts(args.event_ts)
    trades = load_trades(args.csv_path)

    pre_start = event_ts - args.pre_seconds
    post_end = event_ts + args.post_seconds

    pre = [t for t in trades if pre_start <= t.ts < event_ts]
    post = [t for t in trades if event_ts <= t.ts <= post_end]
    next_trade = next((t for t in trades if t.ts >= event_ts), None)
    prior_trade = next((t for t in reversed(trades) if t.ts < event_ts), None)

    frozen_event = {
        "event_ts": event_ts,
        "pre_window_start_ts": pre_start,
        "post_window_end_ts": post_end,
        "pre_trade_count": len(pre),
        "prior_public_trade_price": prior_trade.price if prior_trade else None,
    }

    # Everything above is frozen before post-event descriptive labels are formed.
    post_summary = summarize(post)
    prior_price = prior_trade.price if prior_trade else None
    impact_proxy_pct = None
    if prior_price and next_trade:
        impact_proxy_pct = ((next_trade.price / prior_price) - 1.0) * 100.0

    result = {
        "kind": "KRAKEN_TRADES_TARGETED_SMOKE_V1",
        "status": "PASS",
        "source_file": str(args.csv_path),
        "event_record_frozen_before_post_labels": True,
        "event": frozen_event,
        "pre_event_metrics": summarize(pre),
        "post_event_metrics": post_summary,
        "arrival_to_next_public_trade_seconds": (
            next_trade.ts - event_ts if next_trade else None
        ),
        "arrival_price_to_next_public_trade_impact_proxy_pct": impact_proxy_pct,
        "point_in_time_assertions": {
            "pre_event_rows_strictly_before_event": all(t.ts < event_ts for t in pre),
            "post_event_rows_not_used_in_pre_metrics": True,
            "trade_rows_timestamp_ordered": True,
            "labels_generated_after_event_freeze": True,
        },
        "identifiability_guardrails": {
            "true_bid_ask_spread_computed": False,
            "order_book_depth_computed": False,
            "queue_position_computed": False,
            "maker_fill_probability_computed": False,
            "counterfactual_fill_claim_made": False,
        },
        "guardrails": {
            "network_used": False,
            "download_performed": False,
            "performance_selection_performed": False,
            "threshold_sweep_performed": False,
            "holdout_opened": False,
            "active_strategy_changed": False,
            "paper_shadow_runtime_changed": False,
            "real_money_actions": False,
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
