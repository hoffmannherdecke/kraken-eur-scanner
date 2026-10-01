#!/usr/bin/env python3
"""Prospective outcome tracker for V2R4 WS-shadow discovery events.

This is evidence collection only. It never invokes the evaluator, never accesses
an exchange account, and never places orders.

For shadow events that occur *after this tracker starts*, it measures:
- point return at 5m / 15m / 30m / 1h / 3h / 6h,
- running MFE / MAE from the shadow-event price,
- sampling lag and freshness.

Older events are deliberately not backfilled from the current price, because
that would create invalid point-in-time evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = 1
HORIZONS = (
    ("5m", 5 * 60),
    ("15m", 15 * 60),
    ("30m", 30 * 60),
    ("1h", 60 * 60),
    ("3h", 3 * 60 * 60),
    ("6h", 6 * 60 * 60),
)
FINAL_HORIZON_SECONDS = HORIZONS[-1][1]
MAX_EVENT_ENROLL_AGE_SECONDS = 90
MAX_PAIR_AGE_SECONDS = 180
INCOMPLETE_TIMEOUT_SECONDS = 7 * 60 * 60


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("missing timestamp")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")
    tmp.replace(path)


def append_jsonl(path: Path, payload: dict[str, Any], max_bytes: int = 20 * 1024 * 1024) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size >= max_bytes:
        stamp = utcnow().strftime("%Y%m%d-%H%M%S")
        path.replace(path.with_name(f"{path.stem}-{stamp}{path.suffix}"))
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")


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


def pct(price: float, entry: float) -> float:
    return 100.0 * (price / entry - 1.0)


def load_state(path: Path, now: datetime) -> dict[str, Any]:
    if path.exists():
        try:
            state = load_json(path)
            if int(state.get("schema_version", 0)) == SCHEMA:
                state.setdefault("active", {})
                state.setdefault("ignored_ids", [])
                state.setdefault("counters", {})
                for k in (
                    "events_seen",
                    "events_enrolled",
                    "events_ignored_pretracker",
                    "events_completed",
                    "events_incomplete_timeout",
                    "fresh_samples",
                    "stale_pair_samples",
                ):
                    state["counters"].setdefault(k, 0)
                return state
        except Exception:
            pass
    return {
        "schema_version": SCHEMA,
        "tracker_started_at_utc": iso(now),
        "active": {},
        "ignored_ids": [],
        "counters": {
            "events_seen": 0,
            "events_enrolled": 0,
            "events_ignored_pretracker": 0,
            "events_completed": 0,
            "events_incomplete_timeout": 0,
            "fresh_samples": 0,
            "stale_pair_samples": 0,
        },
    }


def enroll_events(
    state: dict[str, Any],
    event_dir: Path,
    outcome_dir: Path,
    now: datetime,
) -> None:
    ignored = set(str(x) for x in state.get("ignored_ids", []))
    active = state["active"]

    for path in sorted(event_dir.glob("*.json")):
        try:
            event = load_json(path)
        except Exception:
            continue
        if event.get("kind") != "V2R4_WS_SHADOW_DISCOVERY":
            continue
        eid = event_id(event)
        if eid in active or eid in ignored or (outcome_dir / f"{eid}.json").exists():
            continue

        state["counters"]["events_seen"] += 1
        try:
            observed = parse_utc(event.get("observed_at_utc"))
            entry = float(event.get("last_eur"))
        except Exception:
            ignored.add(eid)
            continue
        if not math.isfinite(entry) or entry <= 0:
            ignored.add(eid)
            continue

        age = (now - observed).total_seconds()
        if age > MAX_EVENT_ENROLL_AGE_SECONDS:
            ignored.add(eid)
            state["counters"]["events_ignored_pretracker"] += 1
            continue
        if age < -30:
            ignored.add(eid)
            continue

        active[eid] = {
            "event_id": eid,
            "pair": str(event.get("pair") or ""),
            "observed_at_utc": iso(observed),
            "entry_price_eur": entry,
            "event_reasons": list(event.get("reasons") or []),
            "feed_to_shadow_latency_ms": event.get("feed_to_shadow_latency_ms"),
            "source_pair_received_at_utc": event.get("source_pair_received_at_utc"),
            "max_return_pct": 0.0,
            "min_return_pct": 0.0,
            "last_sample_at_utc": None,
            "last_price_eur": None,
            "horizons": {},
        }
        state["counters"]["events_enrolled"] += 1

    # Bound ignored IDs; event files are audit evidence, so old IDs need not live forever.
    state["ignored_ids"] = list(sorted(ignored))[-5000:]


def sample_active(
    state: dict[str, Any],
    snapshot: dict[str, Any],
    outcome_dir: Path,
    outcome_ledger: Path,
    now: datetime,
) -> None:
    pairs = snapshot.get("pairs") or {}
    completed: list[str] = []

    for eid, item in list(state["active"].items()):
        observed = parse_utc(item["observed_at_utc"])
        elapsed = (now - observed).total_seconds()
        pair = item["pair"]
        row = pairs.get(pair)

        fresh_sample = False
        if isinstance(row, dict):
            try:
                received = parse_utc(row.get("received_at_utc"))
                row_age = (now - received).total_seconds()
                price = float(row.get("last_eur"))
                fresh_sample = (
                    row_age <= MAX_PAIR_AGE_SECONDS
                    and math.isfinite(price)
                    and price > 0
                )
            except Exception:
                fresh_sample = False

        if fresh_sample:
            state["counters"]["fresh_samples"] += 1
            ret = pct(price, float(item["entry_price_eur"]))
            item["max_return_pct"] = max(float(item["max_return_pct"]), ret)
            item["min_return_pct"] = min(float(item["min_return_pct"]), ret)
            item["last_sample_at_utc"] = iso(now)
            item["last_price_eur"] = price

            for name, seconds in HORIZONS:
                if name in item["horizons"] or elapsed < seconds:
                    continue
                item["horizons"][name] = {
                    "target_seconds": seconds,
                    "sampled_at_utc": iso(now),
                    "sample_lag_seconds": round(elapsed - seconds, 3),
                    "price_eur": price,
                    "return_pct": round(ret, 6),
                    "mfe_pct": round(float(item["max_return_pct"]), 6),
                    "mae_pct": round(float(item["min_return_pct"]), 6),
                }
        else:
            state["counters"]["stale_pair_samples"] += 1

        if "6h" in item["horizons"]:
            outcome = {
                "schema_version": SCHEMA,
                "kind": "V2R4_WS_SHADOW_OUTCOME_V1",
                "status": "COMPLETE",
                **item,
                "completed_at_utc": iso(now),
                "guardrails": {
                    "shadow_only": True,
                    "evaluator_invoked": False,
                    "order_api": False,
                    "real_money_actions": False,
                },
            }
            atomic_json(outcome_dir / f"{eid}.json", outcome)
            append_jsonl(outcome_ledger, outcome)
            completed.append(eid)
            state["counters"]["events_completed"] += 1
        elif elapsed >= INCOMPLETE_TIMEOUT_SECONDS:
            outcome = {
                "schema_version": SCHEMA,
                "kind": "V2R4_WS_SHADOW_OUTCOME_V1",
                "status": "INCOMPLETE_TIMEOUT",
                **item,
                "completed_at_utc": iso(now),
                "missing_horizons": [name for name, _ in HORIZONS if name not in item["horizons"]],
                "guardrails": {
                    "shadow_only": True,
                    "evaluator_invoked": False,
                    "order_api": False,
                    "real_money_actions": False,
                },
            }
            atomic_json(outcome_dir / f"{eid}.json", outcome)
            append_jsonl(outcome_ledger, outcome)
            completed.append(eid)
            state["counters"]["events_incomplete_timeout"] += 1

    for eid in completed:
        state["active"].pop(eid, None)


def run_once(args: argparse.Namespace, state: dict[str, Any] | None = None) -> dict[str, Any]:
    now = utcnow()
    state = state or load_state(args.state, now)
    args.outcome_dir.mkdir(parents=True, exist_ok=True)

    enroll_events(state, args.event_dir, args.outcome_dir, now)

    snapshot = load_json(args.snapshot)
    if snapshot.get("kind") != "MINIPC_KRAKEN_EUR_TICKER_LATEST_V1":
        raise RuntimeError("unexpected Kraken snapshot kind")

    sample_active(state, snapshot, args.outcome_dir, args.outcome_ledger, now)
    state["updated_at_utc"] = iso(now)
    atomic_json(args.state, state)

    heartbeat = {
        "schema_version": SCHEMA,
        "kind": "V2R4_WS_SHADOW_OUTCOME_HEARTBEAT_V1",
        "checked_at_utc": iso(now),
        "status": "HEALTHY",
        "tracker_started_at_utc": state["tracker_started_at_utc"],
        "active_events": len(state["active"]),
        "counters": state["counters"],
        "strategy_action": "NONE_EVIDENCE_ONLY",
        "real_money_actions": False,
        "order_api": False,
        "evaluator_invoked": False,
    }
    atomic_json(args.heartbeat, heartbeat)
    print("V2R4_WS_SHADOW_OUTCOME " + json.dumps(heartbeat, sort_keys=True), flush=True)
    return state


def parse_args() -> argparse.Namespace:
    trading = Path.home() / "Trading"
    ap = argparse.ArgumentParser()
    ap.add_argument("--trading-root", type=Path, default=trading)
    ap.add_argument("--event-dir", type=Path, default=None)
    ap.add_argument("--snapshot", type=Path, default=None)
    ap.add_argument("--state", type=Path, default=None)
    ap.add_argument("--heartbeat", type=Path, default=None)
    ap.add_argument("--outcome-dir", type=Path, default=None)
    ap.add_argument("--outcome-ledger", type=Path, default=None)
    ap.add_argument("--interval-seconds", type=float, default=10.0)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    root = args.trading_root
    args.event_dir = args.event_dir or root / "State" / "v2r4-ws-shadow-events"
    args.snapshot = args.snapshot or root / "State" / "kraken-eur-ticker-latest.json"
    args.state = args.state or root / "State" / "v2r4-ws-shadow-outcome-state.json"
    args.heartbeat = args.heartbeat or root / "State" / "v2r4-ws-shadow-outcome-heartbeat.json"
    args.outcome_dir = args.outcome_dir or root / "State" / "v2r4-ws-shadow-outcomes"
    args.outcome_ledger = args.outcome_ledger or root / "Logs" / "v2r4-ws-shadow-outcomes.jsonl"
    if args.interval_seconds < 2:
        raise SystemExit("--interval-seconds must be >= 2")
    return args


def main() -> int:
    args = parse_args()
    state: dict[str, Any] | None = None
    while True:
        try:
            state = run_once(args, state)
        except FileNotFoundError as exc:
            now = utcnow()
            heartbeat = {
                "schema_version": SCHEMA,
                "kind": "V2R4_WS_SHADOW_OUTCOME_HEARTBEAT_V1",
                "checked_at_utc": iso(now),
                "status": "WAITING_FOR_INPUT",
                "detail": str(exc),
                "strategy_action": "NONE_EVIDENCE_ONLY",
                "real_money_actions": False,
                "order_api": False,
                "evaluator_invoked": False,
            }
            atomic_json(args.heartbeat, heartbeat)
            print("V2R4_WS_SHADOW_OUTCOME " + json.dumps(heartbeat, sort_keys=True), flush=True)
        if args.once:
            return 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
