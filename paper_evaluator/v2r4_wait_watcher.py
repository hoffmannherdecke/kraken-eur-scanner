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
from collections import OrderedDict
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
import sys

# Direct file execution uses paper_evaluator/ as sys.path[0], not the repo
# root. Include the existing repo root so the original market_data module
# works in both CI and standalone scheduled-task modes.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from .v2r4_trigger_contract import evaluate_plan, validate_plan
except ImportError:  # direct script execution
    from v2r4_trigger_contract import evaluate_plan, validate_plan

# Source budget is explicitly enabled per MINI-PC task. The isolated
# WAIT launcher can load the same pinned module beside its source overlay;
# never bypass an enabled budget silently if the module is absent.
try:
    from market_data.kraken_public_budget import (
        reserve_public_request, report_public_rate_limit
    )
except ImportError:
    from kraken_public_budget import (
        reserve_public_request, report_public_rate_limit
    )

UA = "kraken-v2r4-wait-watcher/0.1-paper-only"

# Only successful, CLOSED candles are reused within their UTC candle bucket.
# No disk persistence, no cross-process or cross-interval sharing, and no
# ticker reuse: every WAIT decision still fetches a fresh public Kraken ticker.
# The bounded in-memory cache is intentionally process-local; a separate host
# request-budget gate is required for all competing MINI-PC consumers.
_CLOSED_OHLC_CACHE_MAX = 256
_CLOSED_OHLC_CACHE = OrderedDict()



def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def http_json(url: str, timeout: int = 10) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "application/json"},
    )
    reserve_public_request(url, max_wait_seconds=0.0)  # WAIT may defer; never send unbudgeted
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            report_public_rate_limit(url, http_status=429)
        raise
    report_public_rate_limit(url, payload)
    return payload


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
    # Kraken's final row is the still-running candle; closed rows cannot
    # normally change until the next UTC interval boundary. Reuse strictly
    # within that bucket, never across boundaries or after an API error.
    # All endpoint requests that do occur retain their original semantics.
    if interval not in (1, 5, 15):
        raise ValueError("unsupported WAIT OHLC interval")
    bucket = int(time.time() // (interval * 60))
    key = (altname, interval)
    prior = _CLOSED_OHLC_CACHE.get(key)
    if prior is not None and prior[0] == bucket:
        _CLOSED_OHLC_CACHE.move_to_end(key)
        return [list(row) for row in prior[1]]

    # Explicitly clear an expired record before attempting a new fetch.
    # If Kraken throttles or is unavailable, NEVER fall back to stale data.
    _CLOSED_OHLC_CACHE.pop(key, None)
    query = urllib.parse.urlencode({"pair": altname, "interval": interval})
    payload = http_json("https://api.kraken.com/0/public/OHLC?" + query)
    if payload.get("error"):
        raise RuntimeError("Kraken OHLC error: " + repr(payload["error"]))
    rows = next(v for k, v in payload["result"].items() if k != "last")
    # Kraken can publish a just-closed candle with a delay or have no trade
    # in the newly opened bucket. In those cases NEVER pin an older bar for
    # the entire new interval. Reuse only if both latest bar timestamps prove
    # that Kraken has supplied this bucket's live row and the immediately
    # preceding, genuinely closed row. If a request crosses a UTC boundary,
    # force another lookup on the next WAIT cycle instead of caching it.
    closed = rows[:-1] if len(rows) > 1 else []
    boundary_after_fetch = int(time.time() // (interval * 60))
    cacheable = False
    if closed and boundary_after_fetch == bucket:
        try:
            seconds = interval * 60
            cacheable = (
                int(float(closed[-1][0])) == (bucket - 1) * seconds
                and int(float(rows[-1][0])) == bucket * seconds
            )
        except (ValueError, TypeError, IndexError):
            cacheable = False
    if cacheable:
        _CLOSED_OHLC_CACHE[key] = (
            bucket, tuple(tuple(row) for row in closed)
        )
        while len(_CLOSED_OHLC_CACHE) > _CLOSED_OHLC_CACHE_MAX:
            _CLOSED_OHLC_CACHE.popitem(last=False)
    return [list(row) for row in closed]


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
