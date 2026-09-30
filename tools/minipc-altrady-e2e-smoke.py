#!/usr/bin/env python3
"""Synthetic E2E transport smoke for the Altrady relay.

Requires the shared token to already exist in the local MINI-PC secret file and
in the deployed Supabase Edge Function environment.

The smoke:
1) posts one synthetic webhook-shaped event to the relay,
2) waits for the existing MINI-PC poller to receive and acknowledge it,
3) verifies the local event log contains the unique marker.

It never changes strategy state and never calls an exchange/order endpoint.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_ENDPOINT = "https://nlgzjmqgwueojlyqmoru.supabase.co/functions/v1/altrady-trigger-relay"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def post_json(url: str, payload: dict, timeout: int = 10) -> dict:
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "minipc-altrady-e2e-smoke/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        if resp.status != 200:
            raise RuntimeError(f"relay HTTP {resp.status}: {raw[:200]}")
        return json.loads(raw)


def log_contains_marker(path: Path, marker: str) -> bool:
    if not path.exists():
        return False
    # Bounded tail scan: this is a transport proof, not a full-log parser.
    lines = path.read_text("utf-8", errors="replace").splitlines()[-200:]
    for line in lines:
        try:
            row = json.loads(line)
        except Exception:
            continue
        event = row.get("event") if isinstance(row, dict) else None
        if isinstance(event, dict) and event.get("direction") == marker:
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trading-root", default=str(Path.home() / "Trading"))
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    ap.add_argument("--timeout-seconds", type=int, default=35)
    args = ap.parse_args()

    root = Path(args.trading_root)
    token_path = root / "Secrets" / "altrady-webhook-token.txt"
    heartbeat_path = root / "State" / "altrady-trigger-heartbeat.json"
    events_log = root / "Logs" / "altrady-trigger-events.jsonl"

    token = token_path.read_text("utf-8").strip() if token_path.exists() else ""
    if len(token) < 24:
        raise SystemExit("local Altrady relay token missing/too short")

    marker = "SMOKE_" + uuid.uuid4().hex[:12].upper()
    payload = {
        "token": token,
        "exchange": "KRAKEN",
        "symbol": "BTC/EUR",
        "direction": marker,
        "close": 1.0,
        "low": 1.0,
        "high": 1.0,
        "time": utc_now(),
        "transport_smoke": True,
    }

    response = post_json(args.endpoint, payload)
    if not response.get("ok") or not response.get("accepted"):
        raise SystemExit(f"relay did not accept synthetic event: {response}")

    deadline = time.monotonic() + max(10, min(90, args.timeout_seconds))
    while time.monotonic() < deadline:
        if log_contains_marker(events_log, marker):
            hb = {}
            if heartbeat_path.exists():
                try:
                    hb = json.loads(heartbeat_path.read_text("utf-8"))
                except Exception:
                    hb = {}
            if hb.get("status") != "HEALTHY":
                raise SystemExit(f"event arrived but poller heartbeat is not HEALTHY: {hb}")
            print(json.dumps({
                "kind": "ALTRADY_TRANSPORT_E2E_SMOKE_V1",
                "status": "PASS",
                "marker": marker,
                "relay_accepted": True,
                "local_event_observed": True,
                "poller_status": hb.get("status"),
                "strategy_action": hb.get("strategy_action"),
                "real_money_actions": False,
                "order_api": False,
            }, sort_keys=True))
            return 0
        time.sleep(1)

    raise SystemExit("relay accepted event but MINI-PC poller did not observe it before timeout")


if __name__ == "__main__":
    raise SystemExit(main())
