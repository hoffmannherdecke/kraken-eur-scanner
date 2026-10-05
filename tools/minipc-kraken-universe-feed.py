#!/usr/bin/env python3
"""Continuous broad Kraken EUR public ticker feed for the MINI-PC.

Infrastructure-only transport:
- REST AssetPairs is the operational online Spot-EUR universe gate.
- Kraken WebSocket v2 ticker is the event-driven primary market feed.
- Only compact latest-per-pair state + a heartbeat are persisted.
- No account credentials, strategy evaluation, order API, or real-money action.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from market_data.universe import online_eur_universe, ticker_record

WS_URL = "wss://ws.kraken.com/v2"
UA = "kraken-eur-minipc-universe/1.0-public-only"
SUBSCRIBE_CHUNK = 80
HEALTHY_COVERAGE = 0.80


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")
    tmp.replace(path)


def append_log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"{utc_now()} {message}\n")


def public_json(url: str, timeout: int = 20) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("error"):
        raise RuntimeError("Kraken public REST error: " + ";".join(payload["error"]))
    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("Kraken public REST returned no result object")
    return result


def fetch_online_eur_universe() -> list[dict[str, str]]:
    result = public_json("https://api.kraken.com/0/public/AssetPairs")
    rows = online_eur_universe(result)
    if not rows:
        raise RuntimeError("Kraken AssetPairs yielded zero online EUR spot pairs")
    return rows


def universe_hash(symbols: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(symbols)).encode("utf-8")).hexdigest()


def chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


async def run_feed(trading_root: Path, seconds: int | None, refresh_seconds: int) -> int:
    from websockets.asyncio.client import connect

    state_dir = trading_root / "State"
    log_dir = trading_root / "Logs"
    heartbeat_path = state_dir / "kraken-eur-universe-heartbeat.json"
    snapshot_path = state_dir / "kraken-eur-ticker-latest.json"
    log_path = log_dir / "kraken-eur-universe.log"
    state_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    started_at = utc_now()
    stop_at = None if seconds is None else time.monotonic() + seconds
    stats: dict[str, Any] = {
        "schema_version": 1,
        "kind": "MINIPC_KRAKEN_EUR_UNIVERSE_V1",
        "status": "STARTING",
        "started_at_utc": started_at,
        "checked_at_utc": started_at,
        "last_universe_refresh_at_utc": None,
        "last_wire_at_utc": None,
        "last_ticker_at_utc": None,
        "last_error": None,
        "connection": 0,
        "connections_started": 0,
        "reconnects": 0,
        "wire_messages": 0,
        "ticker_messages": 0,
        "ticker_rows": 0,
        "ticker_updates": 0,
        "subscription_errors": 0,
        "pair_count": 0,
        "requested_pair_count": 0,
        "observed_pair_count": 0,
        "coverage_pct": 0.0,
        "universe_sha256": None,
        "event_trigger": "trades",
        "universe_source": "kraken_public_rest_assetpairs_online_eur",
        "transport": "kraken_websocket_v2_ticker",
        "strategy_action": "NONE_TRANSPORT_ONLY",
        "public_data_only": True,
        "account_credentials": False,
        "order_api": False,
        "real_money_actions": False,
        "live_evaluation": False,
    }
    latest: dict[str, dict[str, Any]] = {}
    last_heartbeat_write = 0.0
    last_snapshot_write = 0.0
    snapshot_dirty = False
    ever_healthy = False

    def remaining() -> float | None:
        if stop_at is None:
            return None
        return max(0.0, stop_at - time.monotonic())

    def recalc_coverage() -> None:
        pair_count = int(stats.get("pair_count") or 0)
        observed = len(latest)
        stats["observed_pair_count"] = observed
        stats["coverage_pct"] = round((100.0 * observed / pair_count) if pair_count else 0.0, 2)

    def write_heartbeat(force: bool = False) -> None:
        nonlocal last_heartbeat_write
        now = time.monotonic()
        if not force and now - last_heartbeat_write < 5.0:
            return
        recalc_coverage()
        stats["checked_at_utc"] = utc_now()
        atomic_json(heartbeat_path, stats)
        last_heartbeat_write = now

    def write_snapshot(force: bool = False) -> None:
        nonlocal last_snapshot_write, snapshot_dirty
        now = time.monotonic()
        if not snapshot_dirty and not force:
            return
        if not force and now - last_snapshot_write < 2.0:
            return
        atomic_json(
            snapshot_path,
            {
                "schema_version": 1,
                "kind": "MINIPC_KRAKEN_EUR_TICKER_LATEST_V1",
                "written_at_utc": utc_now(),
                "universe_sha256": stats.get("universe_sha256"),
                "pair_count": stats.get("pair_count"),
                "observed_pair_count": len(latest),
                "pairs": latest,
                "retention": "latest_snapshot_only_no_raw_tick_archive",
                "public_data_only": True,
            },
        )
        last_snapshot_write = now
        snapshot_dirty = False

    write_heartbeat(True)

    while stop_at is None or time.monotonic() < stop_at:
        try:
            universe = await asyncio.to_thread(fetch_online_eur_universe)
            symbols = [row["symbol"] for row in universe]
            stats["pair_count"] = len(symbols)
            stats["requested_pair_count"] = len(symbols)
            stats["universe_sha256"] = universe_hash(symbols)
            stats["last_universe_refresh_at_utc"] = utc_now()
            allowed = set(symbols)

            # Remove pairs that are no longer in the current REST online-EUR universe.
            for stale in [symbol for symbol in latest if symbol not in allowed]:
                del latest[stale]
                snapshot_dirty = True

            stats["connection"] = int(stats["connection"]) + 1
            stats["connections_started"] = int(stats["connections_started"]) + 1
            stats["status"] = "CONNECTING"
            stats["last_error"] = None
            write_heartbeat(True)

            connection_number = int(stats["connection"])
            append_log(
                log_path,
                f"connection_start connection={connection_number} pairs={len(symbols)} "
                f"universe={stats['universe_sha256'][:12]}",
            )

            async with connect(
                WS_URL,
                open_timeout=15,
                ping_interval=10,
                ping_timeout=10,
                max_size=8 * 1024 * 1024,
            ) as ws:
                for batch in chunks(symbols, SUBSCRIBE_CHUNK):
                    payload = {
                        "method": "subscribe",
                        "params": {
                            "channel": "ticker",
                            "symbol": batch,
                            "event_trigger": "trades",
                            "snapshot": True,
                        },
                    }
                    await ws.send(json.dumps(payload))
                stats["status"] = "CONNECTED"
                write_heartbeat(True)

                reconnect_at = time.monotonic() + refresh_seconds
                while (stop_at is None or time.monotonic() < stop_at) and time.monotonic() < reconnect_at:
                    timeout = 1.0
                    rem = remaining()
                    if rem is not None:
                        timeout = max(0.05, min(timeout, rem))
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                    except asyncio.TimeoutError:
                        write_snapshot(False)
                        write_heartbeat(False)
                        continue

                    received_at = utc_now()
                    stats["wire_messages"] = int(stats["wire_messages"]) + 1
                    stats["last_wire_at_utc"] = received_at
                    try:
                        msg = json.loads(raw)
                    except Exception as exc:
                        stats["status"] = "DEGRADED"
                        stats["last_error"] = f"json:{type(exc).__name__}"
                        write_heartbeat(True)
                        continue

                    if msg.get("success") is False:
                        stats["subscription_errors"] = int(stats["subscription_errors"]) + 1
                        stats["status"] = "DEGRADED"
                        stats["last_error"] = str(msg.get("error") or "subscription failed")[:240]
                        append_log(log_path, "subscription_error " + stats["last_error"])
                        write_heartbeat(True)
                        continue

                    if msg.get("channel") != "ticker":
                        write_heartbeat(False)
                        continue

                    stats["ticker_messages"] = int(stats["ticker_messages"]) + 1
                    if msg.get("type") == "update":
                        stats["ticker_updates"] = int(stats["ticker_updates"]) + 1

                    data = msg.get("data") or []
                    if not isinstance(data, list):
                        data = []
                    for row in data:
                        if not isinstance(row, dict):
                            continue
                        symbol = str(row.get("symbol") or "")
                        if symbol not in allowed:
                            continue
                        latest[symbol] = ticker_record(row, received_at)
                        stats["ticker_rows"] = int(stats["ticker_rows"]) + 1
                        snapshot_dirty = True
                    if data:
                        stats["last_ticker_at_utc"] = received_at

                    recalc_coverage()
                    coverage_fraction = (
                        len(latest) / len(symbols) if symbols else 0.0
                    )
                    if (
                        coverage_fraction >= HEALTHY_COVERAGE
                        and int(stats["subscription_errors"]) == 0
                    ):
                        stats["status"] = "HEALTHY"
                        ever_healthy = True
                    elif stats["status"] != "DEGRADED":
                        stats["status"] = "CONNECTED"

                    write_snapshot(False)
                    write_heartbeat(False)

                append_log(
                    log_path,
                    f"connection_refresh connection={connection_number} "
                    f"coverage={stats['coverage_pct']}%",
                )
                if stop_at is None or time.monotonic() < stop_at:
                    stats["reconnects"] = int(stats["reconnects"]) + 1
                    stats["status"] = "REFRESHING_UNIVERSE"
                    write_snapshot(True)
                    write_heartbeat(True)

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            stats["status"] = "RECONNECTING"
            stats["last_error"] = f"{type(exc).__name__}: {str(exc)[:220]}"
            stats["reconnects"] = int(stats["reconnects"]) + 1
            append_log(log_path, "reconnect " + stats["last_error"])
            write_snapshot(True)
            write_heartbeat(True)
            rem = remaining()
            if rem is not None and rem <= 0:
                break
            await asyncio.sleep(5 if rem is None else min(5, rem))

    write_snapshot(True)
    recalc_coverage()
    if seconds is not None:
        enough_pairs = int(stats["pair_count"]) > 0
        enough_coverage = float(stats["coverage_pct"]) >= HEALTHY_COVERAGE * 100.0
        no_sub_errors = int(stats["subscription_errors"]) == 0
        if ever_healthy and enough_pairs and enough_coverage and no_sub_errors:
            stats["status"] = "HEALTHY"
            write_heartbeat(True)
            return 0
        stats["status"] = "FAILED"
        if not stats.get("last_error"):
            stats["last_error"] = (
                f"bounded smoke incomplete: pairs={stats['pair_count']} "
                f"observed={stats['observed_pair_count']} coverage={stats['coverage_pct']}% "
                f"subscription_errors={stats['subscription_errors']}"
            )
        write_heartbeat(True)
        return 2

    write_heartbeat(True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trading-root", default=str(Path.home() / "Trading"))
    parser.add_argument(
        "--seconds",
        type=int,
        default=None,
        help="bounded proof duration; omit for continuous service mode",
    )
    parser.add_argument(
        "--universe-refresh-seconds",
        type=int,
        default=900,
        help="re-read REST AssetPairs and refresh subscriptions on this cadence",
    )
    args = parser.parse_args()
    if args.seconds is not None and not 15 <= args.seconds <= 180:
        raise SystemExit("--seconds must be between 15 and 180")
    if not 300 <= args.universe_refresh_seconds <= 3600:
        raise SystemExit("--universe-refresh-seconds must be between 300 and 3600")
    return asyncio.run(
        run_feed(
            Path(args.trading_root),
            args.seconds,
            args.universe_refresh_seconds,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
