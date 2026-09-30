#!/usr/bin/env python3
"""Read-only Altrady trigger transport consumer for the MINI-PC.

This component does NOT place orders and does NOT change strategy state.
It only consumes authenticated trigger events from the relay, writes local
heartbeat/event evidence, and acknowledges transport delivery.

Strategy coupling (fresh paper recheck) is a separate release-gated step.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_ENDPOINT = "https://nlgzjmqgwueojlyqmoru.supabase.co/functions/v1/altrady-trigger-relay"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_token(path: Path) -> str:
    env = os.environ.get("ALTRADY_WEBHOOK_TOKEN", "").strip()
    if env:
        return env
    if path.exists():
        return path.read_text("utf-8").strip()
    return ""


def request_json(url: str, token: str, *, method: str = "GET", body=None, timeout=10):
    data = None
    headers = {
        "User-Agent": "kraken-mini-pc-altrady-poller/1.0",
        "X-Altrady-Relay-Token": token,
    }
    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        return resp.status, json.loads(raw.decode("utf-8"))


def atomic_json(path: Path, payload: dict):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")
    tmp.replace(path)


def append_jsonl(path: Path, payload: dict):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")


def run_once(endpoint: str, token: str, state_dir: Path, log_dir: Path) -> dict:
    heartbeat = state_dir / "altrady-trigger-heartbeat.json"
    events_log = log_dir / "altrady-trigger-events.jsonl"

    result = {
        "kind": "ALTRADY_TRIGGER_POLL_V1",
        "checked_at_utc": utc_now(),
        "status": "UNKNOWN",
        "events_received": 0,
        "events_acknowledged": 0,
        "strategy_action": "NONE_TRANSPORT_ONLY",
    }

    try:
        status, payload = request_json(endpoint + "?limit=20", token)
        if status != 200 or not payload.get("ok"):
            raise RuntimeError(f"relay HTTP {status}: {payload}")

        events = payload.get("events") or []
        if not isinstance(events, list):
            raise RuntimeError("relay events must be a list")

        ids = []
        for event in events:
            if not isinstance(event, dict) or not event.get("id"):
                continue
            append_jsonl(events_log, {
                "kind": "ALTRADY_TRIGGER_RECEIVED_V1",
                "received_by_minipc_at_utc": utc_now(),
                "event": event,
                "strategy_action": "NONE_TRANSPORT_ONLY",
            })
            ids.append(str(event["id"]))

        result["events_received"] = len(ids)

        if ids:
            ack_status, ack = request_json(
                endpoint + "?mode=ack",
                token,
                method="POST",
                body={"ids": ids},
            )
            if ack_status != 200 or not ack.get("ok"):
                raise RuntimeError(f"relay ack HTTP {ack_status}: {ack}")
            result["events_acknowledged"] = int(ack.get("acknowledged", 0))

        result["status"] = "HEALTHY"
        result["detail"] = "relay reachable; transport-only mode"
    except Exception as exc:
        result["status"] = "DEGRADED"
        result["detail"] = f"{type(exc).__name__}: {exc}"

    atomic_json(heartbeat, result)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    ap.add_argument("--trading-root", default=str(Path.home() / "Trading"))
    ap.add_argument("--interval-seconds", type=int, default=10)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    root = Path(args.trading_root)
    state_dir = root / "State"
    log_dir = root / "Logs"
    secret_path = root / "Secrets" / "altrady-webhook-token.txt"
    state_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    token = load_token(secret_path)
    if not token:
        raise SystemExit(
            "ALTRADY_WEBHOOK_TOKEN missing. Store it only in "
            f"{secret_path} or the process environment."
        )

    interval = max(5, min(60, args.interval_seconds))
    while True:
        result = run_once(args.endpoint, token, state_dir, log_dir)
        print(json.dumps(result, sort_keys=True), flush=True)
        if args.once:
            raise SystemExit(0 if result["status"] == "HEALTHY" else 2)
        time.sleep(interval)


if __name__ == "__main__":
    main()
