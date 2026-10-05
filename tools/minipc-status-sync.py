#!/usr/bin/env python3
"""Fail-soft MINI-PC health status sync to Supabase.

Uploads only the compact local watchdog report through an authenticated Edge
Function. No Supabase admin key, exchange credentials, evaluator call, order API,
or real-money action is used on the MINI-PC.
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
from typing import Any

DEFAULT_ENDPOINT = "https://nlgzjmqgwueojlyqmoru.supabase.co/functions/v1/minipc-status-relay"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")
    tmp.replace(path)


def load_token(root: Path) -> str:
    env = os.environ.get("MINIPC_STATUS_TOKEN", "").strip()
    if env:
        return env
    dedicated = root / "Secrets" / "minipc-status-token.txt"
    if dedicated.exists():
        return dedicated.read_text("utf-8").strip()
    legacy = root / "Secrets" / "altrady-webhook-token.txt"
    return legacy.read_text("utf-8").strip() if legacy.exists() else ""


def load_health(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text("utf-8"))
    if payload.get("kind") != "MINIPC_LOCAL_HEALTH_V1":
        raise RuntimeError("unexpected health payload kind")
    return payload


def normalized_status(value: Any) -> str:
    s = str(value or "UNKNOWN").upper()
    return s if s in {"HEALTHY", "WARNING", "CRITICAL"} else "UNKNOWN"


def post_status(endpoint: str, token: str, health: dict[str, Any]) -> dict[str, Any]:
    observed = health.get("checked_at_local")
    node_id = str(health.get("computer_name") or "MINI-PC")
    body = {
        "node_id": node_id,
        "observed_at": observed,
        "status": normalized_status(health.get("status")),
        "payload": health,
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "minipc-status-sync/1.0",
            "X-MiniPC-Status-Token": token,
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8")
        payload = json.loads(raw)
        if resp.status != 200 or not payload.get("ok"):
            raise RuntimeError(f"relay HTTP {resp.status}: {raw[:240]}")
        return payload


def run_once(args: argparse.Namespace) -> dict[str, Any]:
    root = args.trading_root
    heartbeat_path = root / "State" / "minipc-status-sync-heartbeat.json"
    health_path = root / "State" / "minipc-health.json"

    result: dict[str, Any] = {
        "kind": "MINIPC_STATUS_SYNC_HEARTBEAT_V1",
        "checked_at_utc": utc_now(),
        "status": "UNKNOWN",
        "uploaded_health_status": None,
        "strategy_action": "NONE_STATUS_ONLY",
        "real_money_actions": False,
        "order_api": False,
        "evaluator_invoked": False,
    }

    try:
        token = load_token(root)
        if len(token) < 24:
            raise RuntimeError("MINI-PC status token missing/too short")
        health = load_health(health_path)
        response = post_status(args.endpoint, token, health)
        result["status"] = "HEALTHY"
        result["uploaded_health_status"] = normalized_status(health.get("status"))
        result["observed_at"] = health.get("checked_at_local")
        result["node_id"] = response.get("node_id")
        result["detail"] = "compact watchdog state uploaded"
    except Exception as exc:
        result["status"] = "DEGRADED"
        result["detail"] = f"{type(exc).__name__}: {str(exc)[:260]}"

    atomic_json(heartbeat_path, result)
    return result


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trading-root", type=Path, default=Path.home() / "Trading")
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    ap.add_argument("--interval-seconds", type=int, default=300)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    if args.interval_seconds < 60 or args.interval_seconds > 3600:
        raise SystemExit("--interval-seconds must be between 60 and 3600")
    return args


def main() -> int:
    args = parse_args()
    while True:
        result = run_once(args)
        print(json.dumps(result, sort_keys=True), flush=True)
        if args.once:
            return 0 if result["status"] == "HEALTHY" else 2
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
