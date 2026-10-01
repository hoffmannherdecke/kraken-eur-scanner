#!/usr/bin/env python3
"""Inactive V2R4 local WAIT runtime preparation.

This module is deliberately isolated from the active V2R3 runtime.

It turns persisted V2R4 WAIT plans into a bounded local state machine:
- Kraken public data is always the source of truth for trigger conditions.
- Altrady-consumed events may only wake a same-pair plan early; they never satisfy
  a condition themselves and never create a buy.
- A trigger match can only request one fresh PAPER recheck.
- No private Kraken API and no order endpoint exist here.
- Long-running mode requires --execute-recheck explicitly. Without it, only
  --once receipt-only smoke mode is allowed.

Nothing installs or starts this runtime. Activation remains a later release gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from .v2r4_trigger_contract import evaluate_plan, validate_plan
    from .v2r4_wait_watcher import market_metrics, write_receipt
    from .v2r4_local_recheck import run_recheck
except ImportError:  # direct script execution
    from v2r4_trigger_contract import evaluate_plan, validate_plan
    from v2r4_wait_watcher import market_metrics, write_receipt
    from v2r4_local_recheck import run_recheck


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    value = (dt or utcnow()).astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")
    os.replace(tmp, path)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def plan_key(plan: dict[str, Any]) -> str:
    body = json.dumps(plan, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def canonical_symbol(value: str) -> str:
    s = "".join(ch for ch in str(value).upper() if ch.isalnum())
    # Kraken legacy WS/API notation such as XXBTZEUR -> XBTEUR.
    if s.endswith("ZEUR") and len(s) > 4:
        base = s[:-4]
        if len(base) >= 4 and base[0] in {"X", "Z"}:
            base = base[1:]
        s = base + "EUR"
    s = s.replace("BTCEUR", "XBTEUR")
    return s


def hint_matches_plan(symbol: str, plan: dict[str, Any]) -> bool:
    target = {
        canonical_symbol(plan.get("pair", "")),
        canonical_symbol(plan.get("altname", "")),
    }
    target.discard("")
    return canonical_symbol(symbol) in target


def extract_plan(record: dict[str, Any]) -> dict[str, Any] | None:
    plan = record.get("v2r4_trigger_plan")
    if isinstance(plan, dict):
        return plan
    plan = record.get("next_wait_trigger_plan")
    if isinstance(plan, dict):
        return plan
    return None


def discover_plans(
    decision_dir: Path,
    recheck_dir: Path,
    *,
    now: datetime | None = None,
) -> list[tuple[dict[str, Any], Path]]:
    now = (now or utcnow()).astimezone(timezone.utc)
    found: dict[str, tuple[dict[str, Any], Path]] = {}

    for root in (decision_dir, recheck_dir):
        if not root.exists():
            continue
        for path in sorted(root.glob("*.json")):
            try:
                record = read_json(path)
                plan = extract_plan(record)
                if not plan:
                    continue
                validate_plan(plan)
                if plan.get("paper_only") is not True:
                    continue
                if parse_utc(plan["expires_at_utc"]) <= now:
                    # Expired plans are still returned so they can be terminally
                    # accounted for in runtime state.
                    pass
                key = plan_key(plan)
                # Recheck output is newer authority when the exact same plan
                # somehow appears twice.
                found[key] = (plan, path)
            except Exception:
                # Fail closed: malformed records never become watch plans.
                continue

    return [found[k] for k in sorted(found)]


def read_altrady_hints(
    path: Path,
    offset: int,
) -> tuple[int, set[str], int]:
    """Read only newly appended local Altrady transport evidence.

    Returns (new_offset, normalized_symbols, records_seen).
    The transport poller has already authenticated/ACKed relay delivery.
    These hints merely request an earlier Kraken condition check.
    """
    if not path.exists():
        return 0, set(), 0

    size = path.stat().st_size
    if offset < 0 or offset > size:
        offset = 0

    symbols: set[str] = set()
    seen = 0
    with path.open("rb") as fh:
        fh.seek(offset)
        while True:
            raw = fh.readline()
            if not raw:
                break
            seen += 1
            try:
                row = json.loads(raw.decode("utf-8"))
                event = row.get("event") if isinstance(row, dict) else None
                if not isinstance(event, dict):
                    event = row if isinstance(row, dict) else {}
                symbol = event.get("symbol")
                if symbol:
                    symbols.add(canonical_symbol(str(symbol)))
            except Exception:
                # Local evidence corruption cannot become a strategy trigger.
                continue
        new_offset = fh.tell()
    return new_offset, symbols, seen


def candidate_path(candidate_dir: Path, candidate_id: str) -> Path:
    direct = candidate_dir / f"{candidate_id}.json"
    if direct.exists():
        return direct
    matches = list(candidate_dir.glob(f"*{candidate_id}*.json"))
    if len(matches) == 1:
        return matches[0]
    raise FileNotFoundError(f"candidate file unavailable for {candidate_id}")


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": 1,
            "handled": {},
            "last_polled_at": {},
            "altrady_log_offset": 0,
        }
    state = read_json(path)
    state.setdefault("schema_version", 1)
    state.setdefault("handled", {})
    state.setdefault("last_polled_at", {})
    state.setdefault("altrady_log_offset", 0)
    return state


def bounded_state(state: dict[str, Any], max_entries: int = 1000) -> dict[str, Any]:
    for name in ("handled", "last_polled_at"):
        obj = state.get(name)
        if not isinstance(obj, dict):
            state[name] = {}
            continue
        if len(obj) > max_entries:
            keys = list(obj.keys())[-max_entries:]
            state[name] = {k: obj[k] for k in keys}
    return state


def due_for_fallback(
    state: dict[str, Any],
    key: str,
    now: datetime,
    fallback_seconds: float,
) -> bool:
    value = state.get("last_polled_at", {}).get(key)
    if not value:
        return True
    try:
        age = (now - parse_utc(value)).total_seconds()
    except Exception:
        return True
    return age >= fallback_seconds


def run_cycle(
    *,
    decision_dir: Path,
    recheck_dir: Path,
    candidate_dir: Path,
    receipt_dir: Path,
    state_path: Path,
    heartbeat_path: Path,
    altrady_log: Path,
    spec_path: Path | None,
    control_path: Path | None,
    api_key_file: Path | None,
    fallback_seconds: float,
    execute_recheck: bool,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = (now or utcnow()).astimezone(timezone.utc)
    state = load_state(state_path)
    new_offset, hints, hint_records = read_altrady_hints(
        altrady_log,
        int(state.get("altrady_log_offset", 0)),
    )
    state["altrady_log_offset"] = new_offset

    plans = discover_plans(decision_dir, recheck_dir, now=now)
    counters = {
        "plans_discovered": len(plans),
        "active_plans": 0,
        "expired_plans": 0,
        "fallback_checks": 0,
        "altrady_wakeup_checks": 0,
        "condition_matches": 0,
        "receipts_written": 0,
        "fresh_rechecks": 0,
        "fresh_recheck_failures": 0,
        "altrady_records_seen": hint_records,
    }
    errors: list[str] = []

    for plan, source_path in plans:
        key = plan_key(plan)
        handled = state["handled"].get(key)
        if handled:
            continue

        if parse_utc(plan["expires_at_utc"]) <= now:
            state["handled"][key] = {
                "status": "TTL_EXPIRED",
                "handled_at_utc": iso(now),
                "candidate_id": plan["candidate_id"],
            }
            counters["expired_plans"] += 1
            continue

        counters["active_plans"] += 1
        wake = any(hint_matches_plan(symbol, plan) for symbol in hints)
        fallback = due_for_fallback(state, key, now, fallback_seconds)
        if not wake and not fallback:
            continue
        if wake:
            counters["altrady_wakeup_checks"] += 1
        else:
            counters["fallback_checks"] += 1

        state["last_polled_at"][key] = iso(now)

        try:
            # Critical safety property: even an Altrady wake-up always fetches
            # fresh Kraken public metrics and evaluates the persisted plan.
            metrics = market_metrics(plan["altname"])
            result = evaluate_plan(plan, metrics, now=now)
        except Exception as exc:
            errors.append(
                f"{plan.get('candidate_id')}:DATA_UNAVAILABLE:{type(exc).__name__}"
            )
            continue

        if not result.matched:
            continue

        counters["condition_matches"] += 1
        receipt_path = write_receipt(receipt_dir, plan, metrics, result)
        counters["receipts_written"] += 1

        terminal = {
            "candidate_id": plan["candidate_id"],
            "source": str(source_path),
            "receipt": str(receipt_path),
            "handled_at_utc": iso(now),
        }

        if not execute_recheck:
            terminal["status"] = "MATCH_RECEIPT_ONLY"
            state["handled"][key] = terminal
            continue

        # Persist an IN_FLIGHT terminal marker before invoking the evaluator.
        # If Windows/the process dies during the model call, restart must fail
        # closed rather than silently duplicate a paper decision/entry.
        terminal["status"] = "FRESH_PAPER_RECHECK_IN_FLIGHT"
        state["handled"][key] = terminal
        bounded_state(state)
        atomic_json(state_path, state)

        try:
            if spec_path is None or control_path is None:
                raise RuntimeError("spec/control required for executable paper recheck")
            cpath = candidate_path(candidate_dir, plan["candidate_id"])
            out = run_recheck(
                candidate_path=cpath,
                receipt_path=receipt_path,
                spec_path=spec_path,
                control_path=control_path,
                out_dir=recheck_dir,
                api_key_file=api_key_file,
            )
            terminal["status"] = "FRESH_PAPER_RECHECK_COMPLETE"
            terminal["recheck_output"] = str(out)
            counters["fresh_rechecks"] += 1
        except Exception as exc:
            # Fail closed and do not hammer the model/API automatically. A
            # failed recheck becomes terminal diagnostic evidence.
            terminal["status"] = "FRESH_PAPER_RECHECK_FAILED"
            terminal["error"] = f"{type(exc).__name__}: {exc}"
            counters["fresh_recheck_failures"] += 1
            errors.append(
                f"{plan.get('candidate_id')}:RECHECK_FAILED:{type(exc).__name__}"
            )
        state["handled"][key] = terminal

    bounded_state(state)
    atomic_json(state_path, state)

    status = "HEALTHY" if not errors else "DEGRADED"
    heartbeat = {
        "schema_version": 1,
        "kind": "V2R4_WAIT_RUNTIME_HEARTBEAT_V1",
        "checked_at_utc": iso(now),
        "status": status,
        "paper_only": True,
        "strategy_action": "FRESH_PAPER_RECHECK_ONLY",
        "kraken_public_is_condition_truth": True,
        "altrady_role": "WAKEUP_HINT_ONLY",
        "order_api": False,
        "real_money_actions": False,
        "execute_recheck": execute_recheck,
        "counters": counters,
        "errors": errors[-20:],
    }
    atomic_json(heartbeat_path, heartbeat)
    return heartbeat


def parse_args() -> argparse.Namespace:
    home = Path.home() / "Trading"
    ap = argparse.ArgumentParser()
    ap.add_argument("--decision-dir", type=Path, default=home / "Runtime" / "v2r4-decisions")
    ap.add_argument("--recheck-dir", type=Path, default=home / "Runtime" / "v2r4-rechecks")
    ap.add_argument("--candidate-dir", type=Path, default=home / "Runtime" / "v2r4-candidates")
    ap.add_argument("--receipt-dir", type=Path, default=home / "Runtime" / "v2r4-trigger-receipts")
    ap.add_argument("--state", type=Path, default=home / "State" / "v2r4-wait-runtime-state.json")
    ap.add_argument("--heartbeat", type=Path, default=home / "State" / "v2r4-wait-runtime-heartbeat.json")
    ap.add_argument("--altrady-log", type=Path, default=home / "Logs" / "altrady-trigger-events.jsonl")
    ap.add_argument("--spec", type=Path)
    ap.add_argument("--control", type=Path)
    ap.add_argument("--api-key-file", type=Path, default=home / "Secrets" / "openai-api-key.txt")
    ap.add_argument("--fallback-seconds", type=float, default=10.0)
    ap.add_argument("--loop-seconds", type=float, default=1.0)
    ap.add_argument("--execute-recheck", action="store_true")
    ap.add_argument("--once", action="store_true")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    if args.fallback_seconds < 5 or args.fallback_seconds > 60:
        raise SystemExit("--fallback-seconds must be between 5 and 60")
    if args.loop_seconds < 0.5 or args.loop_seconds > 10:
        raise SystemExit("--loop-seconds must be between 0.5 and 10")
    if not args.once and not args.execute_recheck:
        raise SystemExit(
            "long-running mode requires --execute-recheck; receipt-only mode is smoke-only"
        )
    if args.execute_recheck and (args.spec is None or args.control is None):
        raise SystemExit("--execute-recheck requires --spec and --control")

    for d in (args.decision_dir, args.recheck_dir, args.candidate_dir, args.receipt_dir):
        d.mkdir(parents=True, exist_ok=True)

    while True:
        result = run_cycle(
            decision_dir=args.decision_dir,
            recheck_dir=args.recheck_dir,
            candidate_dir=args.candidate_dir,
            receipt_dir=args.receipt_dir,
            state_path=args.state,
            heartbeat_path=args.heartbeat,
            altrady_log=args.altrady_log,
            spec_path=args.spec,
            control_path=args.control,
            api_key_file=args.api_key_file,
            fallback_seconds=args.fallback_seconds,
            execute_recheck=args.execute_recheck,
        )
        print(json.dumps(result, sort_keys=True), flush=True)
        if args.once:
            return 0 if result["status"] == "HEALTHY" else 2
        time.sleep(args.loop_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
