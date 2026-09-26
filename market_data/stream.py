"""Shared, read-only Kraken Spot WebSocket v2 transport.

This module owns connection/reconnection, subscriptions, and raw message
delivery. It deliberately has no candidate selection, persistence, strategy,
account, or order behavior. Consumers supply a symbol provider and event
callbacks.
"""
import asyncio
import json
import time

from .microstructure import BOOK_DEPTH

WEBSOCKET_URL = "wss://ws.kraken.com/v2"


def subscription_payloads(symbols):
    symbols = sorted(set(symbols))
    if not symbols:
        return []
    return [
        {"method": "subscribe", "params": {"channel": "book", "symbol": symbols,
                                               "snapshot": True, "depth": BOOK_DEPTH}},
        {"method": "subscribe", "params": {"channel": "trade", "symbol": symbols,
                                               "snapshot": True}},
    ]


async def run_kraken_v2_stream(*, stop_at, symbols_provider, on_connection_start,
                               on_subscribe, on_wire, on_connection_end, on_gap):
    """Deliver raw Kraken messages in local receive order until ``stop_at``."""
    from websockets.asyncio.client import connect

    connection = 0
    while time.monotonic() < stop_at:
        connection += 1
        subscribed = set()
        try:
            async with connect(WEBSOCKET_URL, open_timeout=15, ping_interval=10,
                               ping_timeout=10, max_size=8 * 1024 * 1024) as ws:
                await on_connection_start(connection)
                while time.monotonic() < stop_at:
                    fresh = sorted(set(symbols_provider()) - subscribed)
                    if fresh:
                        for payload in subscription_payloads(fresh):
                            await ws.send(json.dumps(payload))
                        subscribed.update(fresh)
                        await on_subscribe(connection, fresh)
                    try:
                        raw = await asyncio.wait_for(
                            ws.recv(), timeout=min(2, max(.01, stop_at - time.monotonic())))
                    except asyncio.TimeoutError:
                        continue
                    await on_wire(raw, connection)
                await on_connection_end(connection, "scheduled_end")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await on_gap(connection, exc)
            await asyncio.sleep(min(5, max(0, stop_at - time.monotonic())))
