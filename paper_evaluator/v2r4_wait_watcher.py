#!/usr/bin/env python3
"""Local paper-only V2R4 WAIT watcher for the future 24/7 Mini-PC.

Uses only Kraken public market data. It does not hold private Kraken credentials,
does not call an LLM and cannot place orders. A match emits a receipt whose only
allowed next action is one fresh PAPER recheck.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:
    from .v2r4_trigger_contract import evaluate_plan, validate_plan
except ImportError:  # direct script execution
    from v2r4_trigger_contract import evaluate_plan, validate_plan

UA = "kraken-v2r4-wait-watcher/0.1-paper-only"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def http_json(url: str, timeout: int = 10) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def ticker(altname: str) -> dict[str, float]:
    query = urllib.parse.urlencode({"pair": altname})
    payload = http_json("https://api.kraken.com/0/public/Ticker?" + query)
    if payload.get("error"):
        raise RuntimeError("Kraken ticker error: " + repr(payload["error"]))
    row = next(iter(payload["result"].values()))
    bid = float(row["b"][0])
    ask = float(row["a"][0])
    last = float(row["c"][0])
    mid = (ask + bid) / 2.0
    return {
        "bid_eur": bid,
        "ask_eur": ask,
        "last_eur": last,
        "spread_pct": 100.0 * (ask - bid) / mid if mid else 999.0,
    }


def closed_ohlc(altname: str, interval: int) -> list[list]:
    query = urllib.parse.urlencode({"pair": altname, "interval": interval})
    payload = http_json("https://api.kraken.com/0/public/OHLC?" + query)
    if payload.get("error"):
        raise RuntimeError("Kraken OHLC error: " + repr(payload["error"]))
    rows = next(v for k, v in payload["result"].items() if k != "last")
    # Kraken's final row is the current, not-yet-closed candle.
    return rows[:-1] if len(rows) > 1 else []


def volume_ratio(rows: list[list], lookback: int) -> float | None:
    if len(rows) < lookback + 1:
        return None
    current = float(rows[-1][6])
    previous = [float(r[6]) for r in rows[-lookback - 1 : -1]]
    baseline = sum(previous) / len(previous)
    if baseline <= 0:
        return None
    return current / baseline


def market_metrics(altname: str) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    out.update(ticker(altname))
    for interval, suffix, lookback in (
        (1, "1m", 5),
        (5, "5m", 5),
        (15, "15m", 4),
    ):
        rows = closed_ohlc(altname, interval)
        out[f"closed_{suffix}_close_eur"] = float(rows[-1][4]) if rows else None
        out[f"closed_{suffix}_volume_ratio_{lookback}"] = volume_ratio(rows, lookback)
    return out


def write_receipt(directory: Path, plan: dict, metrics: dict, result) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = utcnow()
    receipt = {
        "schema_version": 1,
        "kind": "V2R4_PAPER_WAIT_TRIGGER_RECEIPT",
        "paper_only": True,
        "candidate_id": plan["candidate_id"],
        "pair": plan["pair"],
        "observed_at_utc": iso(stamp),
        "matched": result.matched,
        "expired": result.expired,
        "reason": result.reason,
        "condition_results": list(result.condition_results),
        "metrics": metrics,
        "next_action": "FRESH_PAPER_RECHECK_ONLY" if result.matched else "NONE",
        "real_money_actions_enabled": False,
    }
    safe_id = "".join(c if c.isalnum() or c in "-_." else "_" for c in plan["candidate_id"])
    path = directory / f"{stamp.strftime('%Y%m%dT%H%M%SZ')}-{safe_id}.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", "utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--poll-seconds", type=float, default=10.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--receipt-dir", type=Path, default=Path(".v2r4-trigger-receipts"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.poll_seconds < 5:
        raise SystemExit("--poll-seconds must be >= 5")
    plan = json.loads(args.plan.read_text("utf-8"))
    validate_plan(plan)
    altname = plan.get("altname")
    if not altname:
        raise SystemExit("plan requires altname for Kraken public lookup")

    while True:
        observed = utcnow()
        try:
            metrics = market_metrics(altname)
            result = evaluate_plan(plan, metrics, now=observed)
            print(
                json.dumps(
                    {
                        "observed_at_utc": iso(observed),
                        "candidate_id": plan["candidate_id"],
                        "matched": result.matched,
                        "expired": result.expired,
                        "reason": result.reason,
                        "metrics": metrics,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        except Exception as exc:
            # Fail closed: data errors never become trigger matches.
            print(
                json.dumps(
                    {
                        "observed_at_utc": iso(observed),
                        "candidate_id": plan["candidate_id"],
                        "matched": False,
                        "expired": False,
                        "reason": "DATA_UNAVAILABLE",
                        "error": type(exc).__name__,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            if args.once:
                return 3
            time.sleep(args.poll_seconds)
            continue

        if result.matched or result.expired:
            receipt = write_receipt(args.receipt_dir, plan, metrics, result)
            print(f"RECEIPT {receipt}", flush=True)
            return 0 if result.matched else 2
        if args.once:
            return 1
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
