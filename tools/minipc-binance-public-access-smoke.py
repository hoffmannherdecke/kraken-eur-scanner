#!/usr/bin/env python3
"""Public-only Binance connectivity smoke for the MINI-PC.

No API key, account endpoint, private data, order path, leverage action, or
real-money action exists here. The goal is only to prove whether the local
infrastructure can reach the public Spot and USD-M Futures endpoints used as
supplementary cross-market context.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


UA = "kraken-eur-scanner-binance-public-smoke/1.0"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_json(url: str, timeout: float) -> tuple[dict[str, Any], float]:
    started = time.monotonic()
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}: {raw[:180]}")
        data = json.loads(raw)
    return data, round((time.monotonic() - started) * 1000.0, 1)


def probe(name: str, url: str, timeout: float, validator) -> dict[str, Any]:
    out: dict[str, Any] = {"name": name, "ok": False, "url_host": urllib.parse.urlparse(url).netloc}
    try:
        data, latency = get_json(url, timeout)
        validator(data)
        out.update({"ok": True, "latency_ms": latency})
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")[:240]
        except Exception:
            pass
        out.update({"error": "HTTPError", "http_status": exc.code, "detail": body})
    except Exception as exc:
        out.update({"error": type(exc).__name__, "detail": str(exc)[:240]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout-seconds", type=float, default=12.0)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    if args.timeout_seconds < 2 or args.timeout_seconds > 30:
        raise SystemExit("--timeout-seconds must be between 2 and 30")

    checks = [
        probe(
            "spot_server_time",
            "https://api.binance.com/api/v3/time",
            args.timeout_seconds,
            lambda d: d["serverTime"],
        ),
        probe(
            "futures_premium_index_btcusdt",
            "https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT",
            args.timeout_seconds,
            lambda d: (d["symbol"], d["markPrice"], d["lastFundingRate"]),
        ),
        probe(
            "futures_open_interest_btcusdt",
            "https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT",
            args.timeout_seconds,
            lambda d: (d["symbol"], d["openInterest"]),
        ),
    ]

    ok_count = sum(1 for c in checks if c["ok"])
    if ok_count == len(checks):
        status = "HEALTHY"
    elif ok_count == 0:
        status = "BLOCKED_OR_UNAVAILABLE"
    else:
        status = "PARTIAL"

    result = {
        "schema_version": 1,
        "kind": "MINIPC_BINANCE_PUBLIC_ACCESS_SMOKE_V1",
        "checked_at_utc": utcnow(),
        "status": status,
        "checks": checks,
        "guardrails": {
            "public_endpoints_only": True,
            "api_key_used": False,
            "account_endpoint_used": False,
            "private_data_accessed": False,
            "orders": False,
            "leverage_action": False,
            "real_money_actions": False,
            "active_strategy_changed": False,
            "paper_shadow_runtime_changed": False,
        },
        "interpretation": (
            "Connectivity only. A HEALTHY result proves public endpoint reachability "
            "from this machine, not signal quality or permission to use Binance as "
            "Kraken EUR execution truth."
        ),
    }

    raw = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, "utf-8")
    print(raw, end="")
    return 0 if status == "HEALTHY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
