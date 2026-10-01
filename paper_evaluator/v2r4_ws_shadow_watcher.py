#!/usr/bin/env python3
"""V2R4 MINI-PC WebSocket-feed shadow discovery consumer.

Consumes the compact latest-per-pair snapshot written by the already running
CryptoMiniPC-KrakenUniverse service.  It does *not* connect to an exchange,
invoke the evaluator, place orders, or mutate the active V2R3 series.

Purpose:
- prove that V2R4 discovery can consume the event-driven Kraken WS-v2 feed;
- measure feed -> shadow-consumer latency;
- build point-in-time rolling returns without REST ticker polling;
- reject stale/duplicate input and suppress one cycle after a data gap so an
  old signal is never blindly replayed after reconnect.

Shadow only.  No private credentials.  No order endpoint.  No real-money action.
"""
from __future__ import annotations

import argparse
import bisect
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .v2r4_precandidate_discovery import (
        FRESH_PAPER_RECHECK_ONLY,
        WATCH_ONLY,
        assess_discovery,
    )
except ImportError:
    from v2r4_precandidate_discovery import (
        FRESH_PAPER_RECHECK_ONLY,
        WATCH_ONLY,
        assess_discovery,
    )

SNAPSHOT_KIND = "MINIPC_KRAKEN_EUR_TICKER_LATEST_V1"
STATE_SCHEMA = 1
HEARTBEAT_SCHEMA = 1
EVENT_SCHEMA = 1
DEFAULT_SAMPLE_SECONDS = 60
KEEP_SECONDS = 16 * 60 * 60
WINDOWS_SECONDS = {
    "ret10m": 10 * 60,
    "ret30m": 30 * 60,
    "ret1h": 60 * 60,
    "ret3h": 3 * 60 * 60,
    "ret6h": 6 * 60 * 60,
    "ret12h": 12 * 60 * 60,
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("missing UTC timestamp")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return dt.astimezone(timezone.utc)


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n", "utf-8")
    tmp.replace(path)


def append_jsonl(path: Path, payload: dict[str, Any], max_bytes: int = 20 * 1024 * 1024) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size >= max_bytes:
        stamp = utcnow().strftime("%Y%m%d-%H%M%S")
        rotated = path.with_name(f"{path.stem}-{stamp}{path.suffix}")
        path.replace(rotated)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text("utf-8"))


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": STATE_SCHEMA,
            "last_source_written_at_utc": None,
            "recovery_epoch": 0,
            "pairs": {},
            "counters": {
                "snapshots_processed": 0,
                "duplicates_skipped": 0,
                "stale_inputs": 0,
                "gap_recoveries": 0,
                "events_emitted": 0,
            },
        }
    try:
        state = load_json(path)
    except Exception:
        return load_state(Path("__missing__"))
    if int(state.get("schema_version", 0)) != STATE_SCHEMA:
        return load_state(Path("__missing__"))
    state.setdefault("pairs", {})
    state.setdefault("counters", {})
    for key in (
        "snapshots_processed",
        "duplicates_skipped",
        "stale_inputs",
        "gap_recoveries",
        "events_emitted",
    ):
        state["counters"].setdefault(key, 0)
    state.setdefault("recovery_epoch", 0)
    state.setdefault("last_source_written_at_utc", None)
    return state


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def pct_change(new: float | None, old: float | None) -> float | None:
    if new is None or old is None or old <= 0:
        return None
    return 100.0 * (new / old - 1.0)


def compute_returns(samples: list[list[float]], now_ts: int, current_price: float) -> dict[str, float | None]:
    if not samples:
        return {**{name: None for name in WINDOWS_SECONDS}, "ret_day_open": None}
    times = [int(row[0]) for row in samples]
    out: dict[str, float | None] = {}
    for name, seconds in WINDOWS_SECONDS.items():
        target = now_ts - seconds
        idx = bisect.bisect_right(times, target) - 1
        if idx < 0:
            out[name] = None
            continue
        anchor_ts = int(samples[idx][0])
        anchor_price = float(samples[idx][1])
        drift = target - anchor_ts
        max_drift = max(120, int(seconds * 0.10))
        out[name] = pct_change(current_price, anchor_price) if drift <= max_drift else None
    # WS ticker exposes rolling 24h change, not the old REST day-open semantic.
    # Keep this field missing rather than silently changing the V2R4 hypothesis.
    out["ret_day_open"] = None
    return out


def normalize_market(row: dict[str, Any]) -> dict[str, float | None]:
    bid = _num(row.get("bid_eur"))
    ask = _num(row.get("ask_eur"))
    last = _num(row.get("last_eur"))
    spread = _num(row.get("spread_pct"))
    turnover = _num(row.get("turnover24_est_eur"))
    if last is None or last <= 0:
        raise ValueError("missing positive last_eur")
    if spread is None and bid and ask and ask >= bid:
        mid = (bid + ask) / 2.0
        spread = 100.0 * (ask - bid) / mid if mid > 0 else None
    return {
        "bid_eur": bid,
        "ask_eur": ask,
        "last_eur": last,
        "spread_pct": spread,
        "turnover24h_eur": turnover,
    }


def add_sample(pair_state: dict[str, Any], ts: int, price: float, sample_seconds: int) -> None:
    samples = pair_state.setdefault("samples", [])
    if samples and ts - int(samples[-1][0]) < sample_seconds:
        # Keep the latest price in the current bucket, but do not increase state size.
        samples[-1] = [ts, price]
    else:
        samples.append([ts, price])
    keep_after = ts - KEEP_SECONDS
    first = 0
    while first < len(samples) and int(samples[first][0]) < keep_after:
        first += 1
    if first:
        del samples[:first]


def _latency_ms(newer: datetime, older: datetime) -> float:
    return round(max(0.0, (newer - older).total_seconds() * 1000.0), 3)


def process_snapshot(
    snapshot: dict[str, Any],
    state: dict[str, Any],
    *,
    now: datetime,
    max_snapshot_age_seconds: float,
    max_pair_age_seconds: float,
    max_gap_seconds: float,
    cooldown_seconds: int,
    sample_seconds: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    if snapshot.get("kind") != SNAPSHOT_KIND:
        raise ValueError(f"unexpected snapshot kind: {snapshot.get('kind')!r}")
    source_written = parse_utc(snapshot.get("written_at_utc"))
    source_age = (now - source_written).total_seconds()

    if source_age > max_snapshot_age_seconds:
        state["counters"]["stale_inputs"] += 1
        heartbeat = {
            "status": "STALE_INPUT",
            "source_written_at_utc": iso(source_written),
            "source_age_seconds": round(source_age, 3),
            "events_emitted_cycle": 0,
            "gap_suppressed": False,
        }
        return state, [], heartbeat

    source_key = iso(source_written)
    if state.get("last_source_written_at_utc") == source_key:
        state["counters"]["duplicates_skipped"] += 1
        heartbeat = {
            "status": "DUPLICATE_SKIPPED",
            "source_written_at_utc": source_key,
            "source_age_seconds": round(source_age, 3),
            "events_emitted_cycle": 0,
            "gap_suppressed": False,
        }
        return state, [], heartbeat

    gap_suppressed = False
    previous_source = state.get("last_source_written_at_utc")
    if previous_source:
        gap_seconds = (source_written - parse_utc(previous_source)).total_seconds()
        if gap_seconds > max_gap_seconds:
            state["recovery_epoch"] = int(state.get("recovery_epoch", 0)) + 1
            state["counters"]["gap_recoveries"] += 1
            gap_suppressed = True

    pair_rows = snapshot.get("pairs")
    if not isinstance(pair_rows, dict):
        raise ValueError("snapshot pairs must be an object")

    events: list[dict[str, Any]] = []
    now_ts = int(now.timestamp())
    stale_pairs = 0
    changed_pairs = 0
    triggered_pairs = 0

    for pair, raw in pair_rows.items():
        if not isinstance(raw, dict):
            continue
        received_raw = raw.get("received_at_utc")
        try:
            received = parse_utc(received_raw)
        except Exception:
            stale_pairs += 1
            continue
        pair_age = (now - received).total_seconds()
        if pair_age > max_pair_age_seconds:
            stale_pairs += 1
            continue

        pair_state = state["pairs"].setdefault(
            pair,
            {
                "samples": [],
                "last_pair_received_at_utc": None,
                "last_event_ts": 0,
                "last_liquidity_class": WATCH_ONLY,
            },
        )
        received_key = iso(received)
        if pair_state.get("last_pair_received_at_utc") == received_key:
            continue
        changed_pairs += 1

        market = normalize_market(raw)
        current_price = float(market["last_eur"])
        returns = compute_returns(pair_state.get("samples", []), now_ts, current_price)
        add_sample(pair_state, now_ts, current_price, sample_seconds)
        pair_state["last_pair_received_at_utc"] = received_key

        turnover = market["turnover24h_eur"]
        spread = market["spread_pct"]
        if turnover is None or spread is None:
            continue

        assessment = assess_discovery(
            returns=returns,
            turnover24h_eur=float(turnover),
            spread_pct=float(spread),
            depth_1pct_eur=None,
            intended_notional_eur=150.0,
        )
        pair_state["last_liquidity_class"] = assessment.liquidity_class
        if not assessment.triggered:
            continue
        triggered_pairs += 1

        # After any material source gap, consume exactly one fresh snapshot without
        # emitting.  This prevents a stale pre-gap condition from being replayed.
        if gap_suppressed:
            continue

        last_event = int(pair_state.get("last_event_ts", 0) or 0)
        if now_ts - last_event < cooldown_seconds:
            continue

        event = {
            "schema_version": EVENT_SCHEMA,
            "kind": "V2R4_WS_SHADOW_DISCOVERY",
            "shadow_only": True,
            "paper_only": True,
            "real_money_actions_enabled": False,
            "fresh_recheck_invoked": False,
            "next_action": "SHADOW_OBSERVE_ONLY",
            "would_request_fresh_recheck": assessment.next_action == FRESH_PAPER_RECHECK_ONLY,
            "observed_at_utc": iso(now),
            "source_snapshot_written_at_utc": source_key,
            "source_pair_received_at_utc": received_key,
            "feed_to_shadow_latency_ms": _latency_ms(now, received),
            "snapshot_to_shadow_latency_ms": _latency_ms(now, source_written),
            "recovery_epoch": int(state.get("recovery_epoch", 0)),
            "pair": pair,
            "reasons": list(assessment.reasons),
            "returns": assessment.returns,
            "last_eur": current_price,
            "spread_pct": spread,
            "turnover24h_eur": turnover,
            "liquidity_class_without_depth": assessment.liquidity_class,
            "note": "Shadow consumer only; no evaluator call and no order/action path.",
        }
        events.append(event)
        pair_state["last_event_ts"] = now_ts

    state["last_source_written_at_utc"] = source_key
    state["last_source_universe_sha256"] = snapshot.get("universe_sha256")
    state["updated_at_utc"] = iso(now)
    state["counters"]["snapshots_processed"] += 1
    state["counters"]["events_emitted"] += len(events)

    heartbeat = {
        "status": "HEALTHY",
        "source_written_at_utc": source_key,
        "source_age_seconds": round(source_age, 3),
        "snapshot_pair_count": int(snapshot.get("pair_count") or len(pair_rows)),
        "snapshot_observed_pair_count": int(snapshot.get("observed_pair_count") or len(pair_rows)),
        "changed_pairs": changed_pairs,
        "stale_pairs": stale_pairs,
        "triggered_pairs": triggered_pairs,
        "events_emitted_cycle": len(events),
        "gap_suppressed": gap_suppressed,
        "recovery_epoch": int(state.get("recovery_epoch", 0)),
    }
    return state, events, heartbeat


def run_once(
    args: argparse.Namespace,
    *,
    state: dict[str, Any] | None = None,
    persist_state: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    now = utcnow()
    snapshot = load_json(args.snapshot)
    if state is None:
        state = load_state(args.state)
    state, events, cycle = process_snapshot(
        snapshot,
        state,
        now=now,
        max_snapshot_age_seconds=args.max_snapshot_age_seconds,
        max_pair_age_seconds=args.max_pair_age_seconds,
        max_gap_seconds=args.max_gap_seconds,
        cooldown_seconds=args.cooldown_seconds,
        sample_seconds=args.sample_seconds,
    )

    if persist_state:
        atomic_json(args.state, state)

    for event in events:
        safe_pair = event["pair"].replace("/", "-")
        stamp = event["observed_at_utc"].replace(":", "").replace("-", "")
        path = args.event_dir / f"{stamp}-{safe_pair}.json"
        atomic_json(path, event)
        append_jsonl(args.ledger, {"record_type": "event", **event})

    ledger_cycle = {
        "record_type": "cycle",
        "observed_at_utc": iso(now),
        **cycle,
        "counters": dict(state["counters"]),
        "guardrails": {
            "source": "local_kraken_ws_v2_snapshot",
            "shadow_only": True,
            "evaluator_invoked": False,
            "order_api": False,
            "real_money_actions": False,
        },
    }
    # A continuously polled local snapshot will naturally be unchanged for some
    # one-second cycles.  Do not turn those duplicates into an unbounded ledger.
    if cycle["status"] != "DUPLICATE_SKIPPED":
        append_jsonl(args.ledger, ledger_cycle)

    heartbeat = {
        "schema_version": HEARTBEAT_SCHEMA,
        "kind": "V2R4_WS_SHADOW_HEARTBEAT_V1",
        "checked_at_utc": iso(now),
        **cycle,
        "counters": dict(state["counters"]),
        "source_path": str(args.snapshot),
        "strategy_action": "NONE_SHADOW_ONLY",
        "paper_only": True,
        "real_money_actions": False,
    }
    atomic_json(args.heartbeat, heartbeat)
    print("V2R4_WS_SHADOW " + json.dumps(heartbeat, separators=(",", ":"), sort_keys=True), flush=True)
    for event in events:
        print("V2R4_WS_SHADOW_EVENT " + json.dumps(event, separators=(",", ":"), sort_keys=True), flush=True)
    return heartbeat, state


def parse_args() -> argparse.Namespace:
    home = Path.home()
    trading = home / "Trading"
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=trading / "State" / "kraken-eur-ticker-latest.json")
    parser.add_argument("--state", type=Path, default=trading / "State" / "v2r4-ws-shadow-state.json")
    parser.add_argument("--event-dir", type=Path, default=trading / "State" / "v2r4-ws-shadow-events")
    parser.add_argument("--ledger", type=Path, default=trading / "Logs" / "v2r4-ws-shadow-ledger.jsonl")
    parser.add_argument("--heartbeat", type=Path, default=trading / "State" / "v2r4-ws-shadow-heartbeat.json")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument(
        "--max-runtime-seconds",
        type=float,
        default=None,
        help="bounded shadow runtime for smoke tests; omit for continuous mode",
    )
    parser.add_argument("--max-snapshot-age-seconds", type=float, default=15.0)
    parser.add_argument("--max-pair-age-seconds", type=float, default=180.0)
    parser.add_argument("--max-gap-seconds", type=float, default=45.0)
    parser.add_argument("--cooldown-seconds", type=int, default=1800)
    parser.add_argument("--sample-seconds", type=int, default=DEFAULT_SAMPLE_SECONDS)
    parser.add_argument(
        "--state-flush-seconds",
        type=float,
        default=30.0,
        help="continuous-mode interval for compact state persistence",
    )
    args = parser.parse_args()
    if args.poll_seconds < 0.25:
        raise SystemExit("--poll-seconds must be >= 0.25")
    if args.sample_seconds < 10:
        raise SystemExit("--sample-seconds must be >= 10")
    if args.max_runtime_seconds is not None and args.max_runtime_seconds < 2:
        raise SystemExit("--max-runtime-seconds must be >= 2")
    if args.state_flush_seconds < 5:
        raise SystemExit("--state-flush-seconds must be >= 5")
    return args


def main() -> int:
    args = parse_args()
    stop_at = (
        time.monotonic() + args.max_runtime_seconds
        if args.max_runtime_seconds is not None
        else None
    )
    state = load_state(args.state)
    last_state_flush = time.monotonic()

    try:
        while True:
            try:
                _heartbeat, state = run_once(
                    args,
                    state=state,
                    persist_state=args.once,
                )
            except FileNotFoundError:
                now = utcnow()
                heartbeat = {
                    "schema_version": HEARTBEAT_SCHEMA,
                    "kind": "V2R4_WS_SHADOW_HEARTBEAT_V1",
                    "checked_at_utc": iso(now),
                    "status": "WAITING_FOR_FEED",
                    "source_path": str(args.snapshot),
                    "strategy_action": "NONE_SHADOW_ONLY",
                    "paper_only": True,
                    "real_money_actions": False,
                }
                atomic_json(args.heartbeat, heartbeat)
                print("V2R4_WS_SHADOW " + json.dumps(heartbeat, separators=(",", ":"), sort_keys=True), flush=True)

            if args.once:
                return 0

            now_mono = time.monotonic()
            if now_mono - last_state_flush >= args.state_flush_seconds:
                atomic_json(args.state, state)
                last_state_flush = now_mono

            if stop_at is not None and now_mono >= stop_at:
                return 0
            sleep_for = args.poll_seconds
            if stop_at is not None:
                sleep_for = min(sleep_for, max(0.0, stop_at - time.monotonic()))
            if sleep_for <= 0:
                return 0
            time.sleep(sleep_for)
    finally:
        atomic_json(args.state, state)


if __name__ == "__main__":
    raise SystemExit(main())
