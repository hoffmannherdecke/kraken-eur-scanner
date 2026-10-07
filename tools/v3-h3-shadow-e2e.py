#!/usr/bin/env python3
"""Physical MINI-PC E2E smoke for V3-H3 shadow wiring.

This is deliberately isolated from active V2R4 persistence:
- reuses the already-PASS physical Kraken WS reconciliation report;
- captures one fresh checksum-valid BTC/EUR depth-10 state;
- builds one synthetic current XBT/EUR paper candidate in memory only;
- evaluates the exact active V2R4 baseline in memory;
- evaluates the same candidate again with only raw H3 context added;
- verifies noneligible/missing-state passthrough and duplicate routing;
- writes only a compact smoke report under Trading/Logs.

No handoff, paper decision, paper position, recheck, order or real-money state is
written by this smoke.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

THIS = Path(__file__).resolve()
REPO = THIS.parents[1]
sys.path.insert(0, str(REPO / "tools"))
from v3_h3_shadow_common import (  # noqa: E402
    MAX_STATE_AGE_MS,
    compact_h3_context,
    context_is_fresh,
    route_shadow,
)

EXPECTED_REVISION = "V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text("utf-8"))
    if not isinstance(obj, dict):
        raise RuntimeError(f"{path}: JSON root must be object")
    return obj


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to import {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def synthetic_candidate(current: dict[str, float]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    event_time = now.isoformat().replace("+00:00", "Z")
    ts = int(now.timestamp())
    run_id = int(hashlib.sha256(event_time.encode()).hexdigest()[:12], 16)
    pair = "XBT/EUR"
    tag = "XBT-EUR"
    cid = f"{now.strftime('%Y%m%d-%H%M%S')}-{tag}-r{run_id}"
    return {
        "schema_version": 1,
        "kind": "CANONICAL_CANDIDATE_HANDOFF_V1",
        "candidate_id": cid,
        "queue_id": f"{run_id}:{tag}:{ts}",
        "source_repo": "hoffmannherdecke/kraken-eur-scanner",
        "source_scanner_run_id": run_id,
        "source_scanner_run_attempt": 1,
        "source_scanner_sha": None,
        "scanner_package_sha256": None,
        "scanner_runtime_settings": {"source": "V3_H3_PHYSICAL_E2E_SYNTHETIC"},
        "event_time_utc": event_time,
        "event_ts": ts,
        "timing": {
            "scan_step_started_at_utc": event_time,
            "candidate_detected_at_utc": event_time,
            "candidate_detected_ts": ts,
            "candidate_snapshot_at_utc": event_time,
            "handoff_written_at_utc": event_time,
            "altrady_detected_at_utc": None,
        },
        "pair": pair,
        "altname": "XXBTZEUR",
        "action": "REVIEW_ONLY_NOT_ORDER",
        "scanner_candidate": {
            "pair": pair,
            "altname": "XXBTZEUR",
            "price": current["last"],
            "score": None,
            "ret10m": None,
            "ret30m": None,
            "ret1h": None,
            "ret3h": None,
            "ret6h": None,
            "ret12h": None,
            "ret_day_open": None,
            "reasons": ["V3_H3_E2E_SYNTHETIC_NOT_ACTIVE_CANDIDATE"],
        },
        "scanner_market_context": {
            "source": "V3_H3_PHYSICAL_E2E_SYNTHETIC",
            "sensor_price_eur": current["last"],
            "spread_pct": current["spread_pct"],
            "turnover24h_eur": None,
            "source_event_id": "SYNTHETIC_E2E_ONLY",
        },
        "scanner_market_breadth": None,
        "review_message": "V3-H3 isolated physical E2E smoke; not an active V2R4 candidate.",
    }


def synthetic_paths(app: Path, candidate_id: str) -> list[Path]:
    return [
        app / "handoff_queue" / f"{candidate_id}.json",
        app / "paper_decisions" / f"{candidate_id}.json",
        app / "paper_positions" / f"{candidate_id}.json",
        app / "paper_rechecks" / f"{candidate_id}.json",
        app / "paper_revalidations" / f"{candidate_id}.json",
    ]


async def capture_h3_context(repo: Path, seconds: float) -> dict[str, Any]:
    smoke_mod = load_module(
        repo / "tools" / "v3-h3-kraken-ws-book-reconciliation-smoke.py",
        "v3_h3_ws_reconciliation_for_e2e",
    )
    from websockets.asyncio.client import connect

    symbol = "BTC/EUR"
    book = smoke_mod.Book(depth=10)
    errors: list[str] = []
    deadline = time.monotonic() + seconds
    async with connect(
        smoke_mod.WS_URL,
        open_timeout=15,
        ping_interval=10,
        ping_timeout=10,
        max_size=8 * 1024 * 1024,
    ) as ws:
        await ws.send(
            json.dumps(
                {
                    "method": "subscribe",
                    "params": {
                        "channel": "book",
                        "symbol": [symbol],
                        "depth": 10,
                        "snapshot": True,
                    },
                    "req_id": 1,
                }
            )
        )
        while time.monotonic() < deadline:
            timeout = max(0.05, min(1.0, deadline - time.monotonic()))
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            except asyncio.TimeoutError:
                continue
            received = utcnow()
            msg = json.loads(raw, parse_float=Decimal)
            if not isinstance(msg, dict):
                continue
            if msg.get("method") == "subscribe":
                if msg.get("success") is not True:
                    errors.append("subscription_failed:" + str(msg.get("error") or "unknown"))
                    break
                continue
            if msg.get("channel") != "book" or msg.get("type") not in {"snapshot", "update"}:
                continue
            for row in msg.get("data") or []:
                if not isinstance(row, dict) or row.get("symbol") != symbol:
                    continue
                try:
                    book.process(str(msg["type"]), row, received)
                except Exception as exc:
                    errors.append(f"{type(exc).__name__}:{str(exc)[:160]}")
                    break
            if errors:
                break
            if book.snapshots >= 1 and book.updates >= 1 and book.checksum_fail == 0:
                break

    if errors:
        raise RuntimeError("H3 fresh capture failed: " + "; ".join(errors))
    if book.snapshots < 1 or book.updates < 1 or book.checksum_pass < 2 or book.checksum_fail:
        raise RuntimeError("H3 fresh capture incomplete")
    if not book.last_exchange_at_utc or not book.last_received_at_utc:
        raise RuntimeError("H3 timestamps missing")

    best_bid = max(book.bids)
    best_ask = min(book.asks)
    if best_ask <= best_bid:
        raise RuntimeError("H3 book crossed")
    mid = (best_bid + best_ask) / Decimal(2)
    bid_depth = sum(p * q for p, q in book.bids.items())
    ask_depth = sum(p * q for p, q in book.asks.items())
    denom = bid_depth + ask_depth
    if denom <= 0:
        raise RuntimeError("H3 depth denominator invalid")

    return compact_h3_context(
        pair="XBT/EUR",
        source_exchange_at_utc=book.last_exchange_at_utc,
        received_at_utc=book.last_received_at_utc,
        spread_bps=float((best_ask - best_bid) / mid * Decimal(10000)),
        bid_depth_quote_top10=float(bid_depth),
        ask_depth_quote_top10=float(ask_depth),
        depth_imbalance_top10=float((bid_depth - ask_depth) / denom),
    )


def latest_physical_report(logs: Path) -> tuple[Path, dict[str, Any]]:
    reports = sorted(
        logs.glob("v3-h3-ws-book-smoke-*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not reports:
        raise RuntimeError("no prior V3-H3 physical WS smoke report found")
    p = reports[0]
    j = load_json(p)
    if j.get("kind") != "V3_H3_KRAKEN_SPOT_WS_BOOK_RECONCILIATION_SMOKE_V1":
        raise RuntimeError("latest H3 physical report kind mismatch")
    if j.get("status") != "PASS":
        raise RuntimeError("latest H3 physical report is not PASS")
    totals = j.get("totals") or {}
    checksum_fail = totals.get("checksum_fail")
    if checksum_fail is None or int(checksum_fail) != 0:
        raise RuntimeError("latest H3 physical report contains checksum failure")
    if (j.get("interpretation") or {}).get("bounded_reconnect_resubscribe_proven") is not True:
        raise RuntimeError("latest H3 physical report lacks reconnect proof")
    return p, j


def evaluate_once(base, candidate, current, external, spec, control):
    raw, api = base.call_evaluator(candidate, current, external, spec, control)
    decision = base.apply_public_tradability_gate(
        base.apply_sample_cap(base.fail_safe_normalize(raw, current), control),
        current,
        external,
        spec,
    )
    return decision, api


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-root", type=Path, required=True)
    ap.add_argument("--trading-root", type=Path, required=True)
    ap.add_argument("--api-key-file", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--capture-seconds", type=float, default=8.0)
    args = ap.parse_args()

    if not 5.0 <= args.capture_seconds <= 20.0:
        raise SystemExit("--capture-seconds must be 5..20")

    physical_path, physical = latest_physical_report(args.trading_root / "Logs")

    evaluator_path = args.app_root / "paper_evaluator" / "evaluate.py"
    if not evaluator_path.exists():
        raise RuntimeError(f"active evaluator missing: {evaluator_path}")
    sys.path.insert(0, str(args.app_root))
    sys.path.insert(0, str(args.app_root / "paper_evaluator"))
    base = load_module(evaluator_path, "v2r4_active_eval_for_v3_h3_e2e")

    control, spec, fingerprint = base.load_runtime()
    if control.get("enabled") is not True:
        raise RuntimeError("active V2R4 app is disabled")
    if control.get("paper_only") is not True or control.get("real_money_actions_enabled") is not False:
        raise RuntimeError("active V2R4 safety flags invalid")
    if control.get("strategy_revision") != EXPECTED_REVISION or spec.get("strategy_revision") != EXPECTED_REVISION:
        raise RuntimeError("active V2R4 strategy revision mismatch")

    api_key = args.api_key_file.read_text("utf-8").strip()
    if len(api_key) < 20:
        raise RuntimeError("OpenAI API key missing/too short")
    os.environ["OPENAI_API_KEY"] = api_key
    os.environ.setdefault("OPENAI_MODEL", "gpt-6-luna")

    current = base.kraken_ticker("XXBTZEUR")
    candidate = synthetic_candidate(current)
    paths = synthetic_paths(args.app_root, candidate["candidate_id"])
    if any(p.exists() for p in paths):
        raise RuntimeError("synthetic candidate unexpectedly collides with active runtime state")

    external = base.enrich_derivatives_delta(
        base.build_context(candidate, current),
        candidate["pair"],
        control["series_id"],
    )
    baseline_decision, baseline_api = evaluate_once(
        base, candidate, current, copy.deepcopy(external), spec, control
    )

    # Capture H3 immediately before the shadow evaluation so the 2s
    # point-in-time freshness contract is actually exercised at handoff.
    h3 = asyncio.run(capture_h3_context(REPO, args.capture_seconds))
    capture_clock = utcnow()
    if not context_is_fresh(
        source_exchange_at_utc=h3["source_exchange_at_utc"],
        received_at_utc=h3["received_at_utc"],
        evaluation_clock_utc=capture_clock,
        maximum_state_age_ms=MAX_STATE_AGE_MS,
    ):
        raise RuntimeError("fresh H3 context exceeded 2000ms gate")

    h3_external = copy.deepcopy(external)
    h3_external["v3_h3_orderbook_context"] = h3
    h3_decision, h3_api = evaluate_once(
        base, candidate, current, h3_external, spec, control
    )

    if any(p.exists() for p in paths):
        raise RuntimeError("E2E smoke mutated active V2R4 candidate/decision/position state")

    routing_checks = {
        "eligible": route_shadow("XBT/EUR", "PASS", False),
        "noneligible": route_shadow("AAVE/EUR", "PASS", False),
        "missing": route_shadow("ETH/EUR", "MISSING_FAIL_CLOSED", False),
        "duplicate": route_shadow("SOL/EUR", "PASS", True),
    }
    expected_routes = {
        "eligible": "EVALUATE_H3_SHADOW",
        "noneligible": "BASELINE_PASSTHROUGH_NONELIGIBLE_PAIR",
        "missing": "BASELINE_PASSTHROUGH_H3_CONTEXT_MISSING",
        "duplicate": "DUPLICATE_SKIPPED",
    }
    if routing_checks != expected_routes:
        raise RuntimeError(f"H3 routing guard mismatch: {routing_checks}")

    out = {
        "schema_version": 1,
        "kind": "V3_H3_PHYSICAL_SHADOW_E2E_V1",
        "status": "PASS",
        "checked_at_utc": utcnow(),
        "active_baseline": {
            "series_id": control["series_id"],
            "strategy_revision": control["strategy_revision"],
            "release_repo_sha": control.get("release_repo_sha"),
            "strategy_fingerprint_sha256": fingerprint,
        },
        "physical_prerequisite": {
            "path": str(physical_path),
            "status": physical["status"],
            "updates": int(physical["totals"]["updates"]),
            "checksum_pass": int(physical["totals"]["checksum_pass"]),
            "checksum_fail": int(physical["totals"]["checksum_fail"]),
            "bounded_reconnect_resubscribe_proven": True,
        },
        "fresh_h3_context": h3,
        "synthetic_candidate_id": candidate["candidate_id"],
        "baseline_decision": baseline_decision,
        "h3_shadow_decision": h3_decision,
        "decision_diverged": baseline_decision.get("decision") != h3_decision.get("decision"),
        "evaluator": {
            "baseline_response_id": baseline_api.get("response_id"),
            "h3_response_id": h3_api.get("response_id"),
            "baseline_model": baseline_api.get("model"),
            "h3_model": h3_api.get("model"),
        },
        "routing_checks": routing_checks,
        "interpretation": {
            "performance_conclusion_allowed": False,
            "e2e_transport_and_isolation_only": True,
            "h3_directional_sign_assumption": False,
            "h3_threshold_selected": False,
            "h3_transform_selected": False,
        },
        "guardrails": {
            "synthetic_candidate_written_to_active_handoff": False,
            "active_paper_decision_written": False,
            "active_paper_position_written": False,
            "active_recheck_written": False,
            "active_v2r4_strategy_changed": False,
            "orders": False,
            "private_api_used": False,
            "real_money_actions": False,
            "automatic_promotion": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", "utf-8")
    print(
        "V3_H3_PHYSICAL_SHADOW_E2E PASS "
        + json.dumps(
            {
                "series_id": control["series_id"],
                "baseline": baseline_decision.get("decision"),
                "h3": h3_decision.get("decision"),
                "diverged": out["decision_diverged"],
                "physical_updates": out["physical_prerequisite"]["updates"],
                "checksum_fail": 0,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
