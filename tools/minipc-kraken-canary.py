#!/usr/bin/env python3
"""Continuous public/read-only Kraken WebSocket canary for the MINI-PC.

Purpose:
- prove the local 24/7 Python/WebSocket runtime is alive;
- expose a compact heartbeat for the local watchdog;
- exercise reconnect behavior without strategy or order coupling.

This process never accesses an account, never evaluates strategy, and never
places orders. It subscribes only to public BTC/EUR book + trade channels.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_data.runtime import (
    require_live_evaluation_disabled,
    require_real_money_actions_disabled,
)
from market_data.stream import run_kraken_v2_stream


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")
    tmp.replace(path)


async def run_canary(trading_root: Path, seconds: int | None) -> int:
    require_live_evaluation_disabled()
    require_real_money_actions_disabled()

    state_dir = trading_root / "State"
    log_dir = trading_root / "Logs"
    state_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    heartbeat_path = state_dir / "kraken-canary-heartbeat.json"
    log_path = log_dir / "kraken-canary.log"

    started = utc_now()
    stats = {
        "kind": "MINIPC_KRAKEN_PUBLIC_CANARY_V1",
        "status": "STARTING",
        "started_at_utc": started,
        "checked_at_utc": started,
        "last_event_at_utc": None,
        "last_channel": None,
        "connection": 0,
        "connections_started": 0,
        "events_total": 0,
        "book_events": 0,
        "trade_events": 0,
        "subscription_errors": 0,
        "gaps": 0,
        "symbol": "BTC/EUR",
        "strategy_action": "NONE_TRANSPORT_ONLY",
        "public_data_only": True,
        "account_credentials": False,
        "order_api": False,
        "real_money_actions": False,
        "live_evaluation": False,
    }
    last_write = 0.0

    def write_state(force: bool = False) -> None:
        nonlocal last_write
        now = time.monotonic()
        if not force and now - last_write < 2.0:
            return
        stats["checked_at_utc"] = utc_now()
        atomic_json(heartbeat_path, stats)
        last_write = now

    def append_log(message: str) -> None:
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"{utc_now()} {message}\n")

    async def on_connection_start(connection: int):
        stats["connection"] = connection
        stats["connections_started"] += 1
        stats["status"] = "CONNECTED"
        append_log(f"connection_start connection={connection}")
        write_state(True)

    async def on_subscribe(connection: int, fresh):
        append_log(f"subscribed connection={connection} symbols={','.join(fresh)}")

    async def on_wire(raw: str, connection: int):
        stats["events_total"] += 1
        stats["last_event_at_utc"] = utc_now()
        try:
            msg = json.loads(raw)
            channel = msg.get("channel")
            stats["last_channel"] = channel
            if channel == "book":
                stats["book_events"] += 1
            elif channel == "trade":
                stats["trade_events"] += 1
            if msg.get("success") is False:
                stats["subscription_errors"] += 1
                stats["status"] = "DEGRADED"
            elif stats["status"] != "DEGRADED":
                stats["status"] = "HEALTHY"
        except Exception:
            stats["status"] = "DEGRADED"
        write_state(False)

    async def on_connection_end(connection: int, reason: str):
        append_log(f"connection_end connection={connection} reason={reason}")
        if reason != "scheduled_end":
            stats["status"] = "RECONNECTING"
        write_state(True)

    async def on_gap(connection: int, exc: Exception):
        stats["gaps"] += 1
        stats["status"] = "RECONNECTING"
        append_log(
            f"gap connection={connection} error={type(exc).__name__} "
            f"reason={str(exc)[:180]}"
        )
        write_state(True)

    stop_at = time.monotonic() + (seconds if seconds is not None else 3650 * 86400)
    write_state(True)
    await run_kraken_v2_stream(
        stop_at=stop_at,
        symbols_provider=lambda: {"BTC/EUR"},
        on_connection_start=on_connection_start,
        on_subscribe=on_subscribe,
        on_wire=on_wire,
        on_connection_end=on_connection_end,
        on_gap=on_gap,
    )

    if seconds is not None:
        if stats["events_total"] <= 0 or stats["book_events"] <= 0:
            stats["status"] = "FAILED"
            write_state(True)
            return 2
        stats["status"] = "HEALTHY"
        write_state(True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trading-root", default=str(Path.home() / "Trading"))
    parser.add_argument(
        "--seconds",
        type=int,
        default=None,
        help="bounded smoke duration; omit for continuous service mode",
    )
    args = parser.parse_args()

    if args.seconds is not None and not 10 <= args.seconds <= 120:
        raise SystemExit("--seconds must be between 10 and 120")
    return asyncio.run(run_canary(Path(args.trading_root), args.seconds))


if __name__ == "__main__":
    raise SystemExit(main())
