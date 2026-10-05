#!/usr/bin/env python3
"""Fail-soft cloud archive sync for local V2R4 WS-shadow evidence.

Uploads only observation/evidence payloads to an authenticated Supabase Edge Function.
No exchange account, evaluator, order API, or real-money action.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_ENDPOINT = "https://nlgzjmqgwueojlyqmoru.supabase.co/functions/v1/v2r4-shadow-evidence-relay"
BATCH_SIZE = 50


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")
    tmp.replace(path)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text("utf-8"))


def event_id(event: dict[str, Any]) -> str:
    material = "|".join(
        [
            str(event.get("pair") or ""),
            str(event.get("observed_at_utc") or ""),
            str(event.get("source_pair_received_at_utc") or ""),
            str(event.get("last_eur") or ""),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def load_token(root: Path) -> str:
    env = os.environ.get("SHADOW_EVIDENCE_TOKEN", "").strip()
    if env:
        return env
    dedicated = root / "Secrets" / "shadow-evidence-token.txt"
    return dedicated.read_text("utf-8").strip() if dedicated.exists() else ""


def post_batch(endpoint: str, token: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    body = json.dumps({"records": records}, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "minipc-v2r4-shadow-cloud-sync/1.0",
            "X-Shadow-Evidence-Token": token,
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8")
        payload = json.loads(raw)
        if resp.status != 200 or not payload.get("ok"):
            raise RuntimeError(f"relay HTTP {resp.status}: {raw[:240]}")
        return payload


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": 1, "sent": {}}
    try:
        state = load_json(path)
        if int(state.get("schema_version", 0)) != 1:
            raise ValueError("unexpected state schema")
        state.setdefault("sent", {})
        return state
    except Exception:
        return {"schema_version": 1, "sent": {}}


def collect_records(
    root: Path,
    state: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    event_dir = root / "State" / "v2r4-ws-shadow-events"
    outcome_dir = root / "State" / "v2r4-ws-shadow-outcomes"
    manifest_path = root / "State" / "v2r4-ws-shadow-runtime.json"

    runtime_commit = None
    if manifest_path.exists():
        try:
            runtime_commit = load_json(manifest_path).get("runtime_commit")
        except Exception:
            runtime_commit = None

    records: list[dict[str, Any]] = []
    marks: dict[str, dict[str, Any]] = {}
    sent = state.get("sent", {})

    for path in sorted(event_dir.glob("*.json")):
        try:
            event = load_json(path)
        except Exception:
            continue
        if event.get("kind") != "V2R4_WS_SHADOW_DISCOVERY":
            continue

        eid = event_id(event)
        outcome_path = outcome_dir / f"{eid}.json"
        outcome = None
        outcome_status = None
        if outcome_path.exists():
            try:
                outcome = load_json(outcome_path)
                if outcome.get("kind") == "V2R4_WS_SHADOW_OUTCOME_V1":
                    outcome_status = outcome.get("status")
                else:
                    outcome = None
            except Exception:
                outcome = None

        previous = sent.get(eid, {}) if isinstance(sent, dict) else {}
        need_event = not bool(previous.get("event_sent"))
        need_outcome = outcome is not None and previous.get("outcome_status") != outcome_status
        if not need_event and not need_outcome:
            continue

        record = {
            "event_id": eid,
            "pair": event.get("pair"),
            "observed_at": event.get("observed_at_utc"),
            "event_payload": event,
            "source_runtime_commit": runtime_commit,
        }
        if outcome is not None:
            record["outcome_status"] = outcome_status
            record["outcome_payload"] = outcome

        records.append(record)
        marks[eid] = {
            "event_sent": True,
            "outcome_status": outcome_status,
        }

    return records, marks


def run_once(args: argparse.Namespace) -> dict[str, Any]:
    root = args.trading_root
    state_path = root / "State" / "v2r4-shadow-cloud-sync-state.json"
    heartbeat_path = root / "State" / "v2r4-shadow-cloud-sync-heartbeat.json"
    state = load_state(state_path)
    token = load_token(root)

    result: dict[str, Any] = {
        "kind": "V2R4_SHADOW_CLOUD_SYNC_HEARTBEAT_V1",
        "checked_at_utc": utc_now(),
        "status": "UNKNOWN",
        "pending_records": 0,
        "uploaded_records": 0,
        "batches": 0,
        "strategy_action": "NONE_ARCHIVE_ONLY",
        "real_money_actions": False,
        "order_api": False,
        "evaluator_invoked": False,
    }

    if len(token) < 24:
        result["status"] = "DEGRADED"
        result["detail"] = "shadow-evidence token missing/too short"
        atomic_json(heartbeat_path, result)
        return result

    try:
        records, marks = collect_records(root, state)
        result["pending_records"] = len(records)

        for start in range(0, len(records), BATCH_SIZE):
            batch = records[start : start + BATCH_SIZE]
            response = post_batch(args.endpoint, token, batch)
            accepted = int(response.get("accepted", 0))
            if accepted != len(batch):
                raise RuntimeError(
                    f"relay accepted {accepted}/{len(batch)} records"
                )
            result["uploaded_records"] += accepted
            result["batches"] += 1
            for record in batch:
                eid = str(record["event_id"])
                state["sent"][eid] = marks[eid]
            atomic_json(state_path, state)

        result["status"] = "HEALTHY"
        result["detail"] = (
            "archive relay reachable; no pending changes"
            if not records
            else f"uploaded {result['uploaded_records']} evidence records"
        )
    except Exception as exc:
        result["status"] = "DEGRADED"
        result["detail"] = f"{type(exc).__name__}: {str(exc)[:260]}"

    atomic_json(heartbeat_path, result)
    return result


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--trading-root",
        type=Path,
        default=Path.home() / "Trading",
    )
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    ap.add_argument("--interval-seconds", type=int, default=60)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    if args.interval_seconds < 30 or args.interval_seconds > 3600:
        raise SystemExit("--interval-seconds must be between 30 and 3600")
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
