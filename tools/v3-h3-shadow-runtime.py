#!/usr/bin/env python3
"""Frozen V3-H3-SHADOW-001 runtime for the physical MINI-PC.

Research-only sidecar:
- reads the active isolated V2R4 Paper handoff/decision files read-only;
- maintains public Kraken WS-v2 depth-10 books for BTC/ETH/SOL;
- captures a checksum-valid H3 context prospectively when an eligible candidate
  becomes visible;
- replays the exact frozen V2R4 decision context as a control and once with only
  H3 context added;
- persists bounded local evidence and syncs idempotently to Supabase through the
  existing authenticated evidence relay.

It never writes V2R4 handoffs, V2R4 decisions, positions, rechecks, Slack
actions, private exchange state, orders, leverage, or real-money actions.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import importlib.util
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

APP = Path(__file__).resolve().parent
sys.path.insert(0, str(APP))
from v3_h3_shadow_common import (  # noqa: E402
    MAX_SOURCE_CLOCK_LEAD_MS,
    compact_h3_context,
    context_is_fresh,
)

EXPECTED_SHADOW_ID = "V3-H3-SHADOW-001"
EXPECTED_BASELINE_SERIES = "PAPER-V2R4-20261007T184255Z"
EXPECTED_BASELINE_REVISION = "V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION"
EXPECTED_CONFIG_SHA256 = "e533f05d31a5b80248076b4870addf4606dae3d8f0432a11ae66bea03db73ded"
SUPPORTED_PAIRS = {"XBT/EUR": "BTC/EUR", "ETH/EUR": "ETH/EUR", "SOL/EUR": "SOL/EUR"}
HARD_PASSTHROUGH_REASONS = {"STALE_OVER_60M", "PAPER_SAMPLE_CAP_REACHED"}
RELAY_URL = "https://nlgzjmqgwueojlyqmoru.supabase.co/functions/v1/v2r4-paper-evidence-relay"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def sha256_file(path: Path) -> str:
    import hashlib
    text = path.read_text("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")
    temp.replace(path)


def read_json(path: Path) -> dict[str, Any]:
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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def decision_action(payload: dict[str, Any]) -> str:
    return str((payload.get("decision") or {}).get("decision") or "")


def reason_codes(payload: dict[str, Any]) -> set[str]:
    return {str(x) for x in ((payload.get("decision") or {}).get("reason_codes") or [])}


def local_candidate_ids(context_dir: Path, evidence_dir: Path) -> set[str]:
    return {p.stem for p in context_dir.glob("*.json")} | {
        p.stem for p in evidence_dir.glob("*.json")
    }


def local_retention_backpressure(context_dir: Path, evidence_dir: Path, max_files: int) -> bool:
    require(max_files >= 1, "local retention max must be >=1")
    return len(local_candidate_ids(context_dir, evidence_dir)) >= max_files


def prune_synced_local_pair_files(
    evidence_dir: Path,
    context_dir: Path,
    synced_candidate_ids: set[str],
    max_files: int,
) -> list[str]:
    """Delete only oldest cloud-synced local evidence/context pairs beyond cap."""
    require(max_files >= 1, "local retention max must be >=1")
    files = sorted(evidence_dir.glob("*.json"), key=lambda p: (p.stat().st_mtime, p.name))
    excess = max(0, len(files) - max_files)
    if excess == 0:
        return []

    pruned: list[str] = []
    for evidence_path in files:
        if len(pruned) >= excess:
            break
        cid = evidence_path.stem
        if cid not in synced_candidate_ids:
            continue
        evidence_path.unlink(missing_ok=True)
        (context_dir / f"{cid}.json").unlink(missing_ok=True)
        pruned.append(cid)
    return pruned


class Runtime:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.app_root = args.app_root
        self.v2r4 = args.v2r4_app_root
        self.trading = args.trading_root
        self.context_dir = self.app_root / "contexts"
        self.evidence_dir = self.app_root / "evidence"
        self.state_dir = self.app_root / "state"
        self.heartbeat_path = self.trading / "State" / "v3-h3-shadow-001-heartbeat.json"
        self.status_path = self.state_dir / "status.json"
        self.sync_state_path = self.state_dir / "cloud-sync-state.json"
        self.control_path = self.app_root / "h3-control.json"
        self.config_path = self.app_root / "v3-h3-shadow-001-config.json"
        self.api_key_file = args.api_key_file
        self.relay_token_file = args.relay_token_file
        self.source_commit = args.source_commit

        self.control = read_json(self.control_path)
        self.config = read_json(self.config_path)
        require(self.control.get("enabled") is True, "H3 runtime control disabled")
        require(self.control.get("shadow_candidate_id") == EXPECTED_SHADOW_ID, "H3 shadow id mismatch")
        require(self.control.get("baseline_series_id") == EXPECTED_BASELINE_SERIES, "H3 baseline series mismatch")
        require(self.control.get("baseline_strategy_revision") == EXPECTED_BASELINE_REVISION, "H3 baseline revision mismatch")
        require(self.control.get("orders") is False and self.control.get("real_money_actions") is False, "unsafe H3 control flags")
        require(sha256_file(self.config_path) == EXPECTED_CONFIG_SHA256, "frozen H3 config SHA mismatch")

        self.capture_acceptance_ms = float(self.control["capture_acceptance_age_ms"])
        self.final_freshness_ms = float(self.control["maximum_state_age_ms"])
        self.min_candidates = int(self.control["minimum_eligible_matched_candidates"])
        self.min_dates = int(self.control["minimum_distinct_utc_dates"])
        self.min_capture_pct = float(self.control["minimum_capture_success_pct"])
        self.min_divergences = int(self.control["minimum_causal_divergences_for_non_low_impact"])
        self.local_retention_max = int(self.control["local_retention_max_evidence_files"])
        require(self.local_retention_max >= self.min_candidates, "local retention cap below H3 minimum gate")
        self.synced_candidate_ids: set[str] = set()
        self.last_local_prune_count = 0

        self.book_mod = load_module(self.app_root / "v3-h3-kraken-ws-book-reconciliation-smoke.py", "v3_h3_book_runtime")
        self.books: dict[str, Any] = {symbol: self.book_mod.Book(depth=10) for symbol in SUPPORTED_PAIRS.values()}
        self.ws_connected = False
        self.last_ws_message_utc: str | None = None
        self.last_ws_error: str | None = None
        self.runtime_ready_at_utc: str | None = None
        self.cloud_sync_status = "PENDING"
        self.cloud_sync_error: str | None = None
        self.last_cloud_sync_utc: str | None = None
        self.capture_error: str | None = None
        self.eval_error: str | None = None
        self.last_eval_utc: str | None = None
        self.lock = asyncio.Lock()

        os.environ["OPENAI_API_KEY"] = self.api_key_file.read_text("utf-8").strip()
        require(len(os.environ["OPENAI_API_KEY"]) >= 20, "OpenAI API key missing/too short")
        self.relay_token = self.relay_token_file.read_text("utf-8").strip()
        require(len(self.relay_token) >= 24, "shadow evidence relay token missing/too short")

        evaluator_path = self.v2r4 / "paper_evaluator" / "evaluate.py"
        require(evaluator_path.exists(), f"active V2R4 evaluator missing: {evaluator_path}")
        sys.path.insert(0, str(self.v2r4))
        sys.path.insert(0, str(self.v2r4 / "paper_evaluator"))
        self.base = load_module(evaluator_path, "v2r4_active_eval_for_h3_shadow")
        active_control, active_spec, active_fp = self.base.load_runtime()
        require(active_control.get("enabled") is True, "active V2R4 runtime disabled")
        require(active_control.get("series_id") == EXPECTED_BASELINE_SERIES, "active V2R4 series no longer matches H3 freeze")
        require(active_control.get("strategy_revision") == EXPECTED_BASELINE_REVISION, "active V2R4 revision no longer matches H3 freeze")
        require(active_control.get("paper_only") is True and active_control.get("real_money_actions_enabled") is False, "unsafe active V2R4 flags")
        require(active_spec.get("strategy_revision") == EXPECTED_BASELINE_REVISION, "active V2R4 spec mismatch")
        require(active_fp == self.control.get("baseline_strategy_fingerprint_sha256"), "active V2R4 strategy fingerprint mismatch")
        self.active_control = active_control
        self.active_spec = active_spec

        for d in (self.context_dir, self.evidence_dir, self.state_dir, self.heartbeat_path.parent):
            d.mkdir(parents=True, exist_ok=True)
        if self.sync_state_path.exists():
            try:
                sync_state = read_json(self.sync_state_path)
                self.synced_candidate_ids = {
                    str(x) for x in (sync_state.get("synced_candidate_ids") or []) if str(x)
                }
            except Exception:
                self.synced_candidate_ids = set()

    def persist_sync_state(self) -> None:
        atomic_json(self.sync_state_path, {
            "schema_version": 1,
            "kind": "V3_H3_SHADOW_CLOUD_SYNC_STATE_V1",
            "updated_at_utc": utcnow(),
            "synced_candidate_ids": sorted(self.synced_candidate_ids),
            "local_retention_max_evidence_files": self.local_retention_max,
            "last_local_prune_count": self.last_local_prune_count,
        })

    def local_candidate_footprint(self) -> set[str]:
        return local_candidate_ids(self.context_dir, self.evidence_dir)

    def prune_local_after_successful_sync(self) -> list[str]:
        # Keep headroom below the hard 200-candidate ceiling so a healthy runtime
        # does not oscillate at the cap. Supabase is the primary evidence store.
        target = max(self.min_candidates, self.local_retention_max - 20)
        pruned = prune_synced_local_pair_files(
            self.evidence_dir,
            self.context_dir,
            self.synced_candidate_ids,
            target,
        )
        self.last_local_prune_count = len(pruned)
        self.persist_sync_state()
        return pruned

    def books_ready(self) -> bool:
        return all(
            b.snapshots >= 1 and b.checksum_pass >= 1 and b.checksum_fail == 0 and b.last_received_at_utc
            for b in self.books.values()
        )

    def status_summary(self) -> dict[str, Any]:
        rows = []
        for p in sorted(self.evidence_dir.glob("*.json")):
            try:
                rows.append(read_json(p))
            except Exception:
                continue
        matched = len(rows)
        capture_pass = sum(1 for r in rows if r.get("context_status") == "PASS")
        dates = sorted({str(r.get("candidate_event_time_utc") or "")[:10] for r in rows if r.get("candidate_event_time_utc")})
        causal_div = sum(1 for r in rows if r.get("causal_decision_diverged") is True)
        replay_unstable = sum(1 for r in rows if r.get("baseline_replay_stable") is False)
        capture_pct = round((100.0 * capture_pass / matched), 3) if matched else 0.0
        gate_met = (
            matched >= self.min_candidates
            and len(dates) >= self.min_dates
            and capture_pct >= self.min_capture_pct
        )
        local_footprint = self.local_candidate_footprint()
        retention_backpressure = local_retention_backpressure(
            self.context_dir, self.evidence_dir, self.local_retention_max
        )
        low_impact = gate_met and causal_div < self.min_divergences
        if low_impact:
            classification = "INCONCLUSIVE_LOW_IMPACT"
        elif gate_met:
            classification = "MINIMUM_GATE_MET_REVIEW_REQUIRED"
        elif retention_backpressure:
            classification = "LOCAL_RETENTION_BACKPRESSURE"
        else:
            classification = "COLLECTING"
        return {
            "schema_version": 1,
            "kind": "V3_H3_SHADOW_PILOT_STATUS_V1",
            "shadow_candidate_id": EXPECTED_SHADOW_ID,
            "baseline_series_id": EXPECTED_BASELINE_SERIES,
            "baseline_strategy_revision": EXPECTED_BASELINE_REVISION,
            "generated_at_utc": utcnow(),
            "runtime_ready_at_utc": self.runtime_ready_at_utc,
            "eligible_matched_candidates": matched,
            "h3_context_pass_candidates": capture_pass,
            "capture_success_pct": capture_pct,
            "distinct_utc_dates": dates,
            "causal_decision_divergences": causal_div,
            "baseline_replay_unstable_records": replay_unstable,
            "minimum_gate_met": gate_met,
            "retention_backpressure": retention_backpressure,
            "intake_should_stop": gate_met or retention_backpressure,
            "low_impact_if_gate_met": low_impact,
            "classification": classification,
            "fixed_followup_horizons_minutes": self.control["fixed_followup_horizons_minutes"],
            "outcome_review_ready": False,
            "automatic_extension": False,
            "automatic_promotion": False,
            "local_retention_max_evidence_files": self.local_retention_max,
            "local_evidence_files": len(list(self.evidence_dir.glob("*.json"))),
            "local_context_files": len(list(self.context_dir.glob("*.json"))),
            "local_candidate_footprint": len(local_footprint),
            "cloud_synced_candidate_ids": len(self.synced_candidate_ids),
            "last_local_prune_count": self.last_local_prune_count,
            "orders": False,
            "real_money_actions": False,
        }

    def write_status(self) -> dict[str, Any]:
        status = self.status_summary()
        atomic_json(self.status_path, status)
        return status

    def write_heartbeat(self) -> None:
        status = self.status_summary()
        age = None
        if self.last_ws_message_utc:
            age = round((datetime.now(timezone.utc) - parse_utc(self.last_ws_message_utc)).total_seconds(), 3)
        healthy = (
            self.ws_connected
            and self.books_ready()
            and self.runtime_ready_at_utc is not None
            and (age is None or age <= 15)
            and self.capture_error is None
            and self.eval_error is None
        )
        payload = {
            "schema_version": 1,
            "kind": "V3_H3_SHADOW_RUNTIME_HEARTBEAT_V1",
            "checked_at_utc": utcnow(),
            "status": "HEALTHY" if healthy else "DEGRADED",
            "shadow_candidate_id": EXPECTED_SHADOW_ID,
            "baseline_series_id": EXPECTED_BASELINE_SERIES,
            "runtime_ready": self.runtime_ready_at_utc is not None,
            "runtime_ready_at_utc": self.runtime_ready_at_utc,
            "ws_connected": self.ws_connected,
            "last_ws_message_utc": self.last_ws_message_utc,
            "last_ws_message_age_seconds": age,
            "last_ws_error": self.last_ws_error,
            "books": {
                symbol: {
                    "snapshot": b.snapshots >= 1,
                    "updates": b.updates,
                    "checksum_pass": b.checksum_pass,
                    "checksum_fail": b.checksum_fail,
                    "last_exchange_at_utc": b.last_exchange_at_utc,
                    "last_received_at_utc": b.last_received_at_utc,
                }
                for symbol, b in self.books.items()
            },
            "pilot_status": status,
            "capture_error": self.capture_error,
            "last_eval_utc": self.last_eval_utc,
            "eval_error": self.eval_error,
            "cloud_sync_status": self.cloud_sync_status,
            "cloud_sync_error": self.cloud_sync_error,
            "last_cloud_sync_utc": self.last_cloud_sync_utc,
            "guardrails": {
                "v2r4_mutated": False,
                "orders": False,
                "private_exchange_api": False,
                "real_money_actions": False,
                "automatic_promotion": False,
            },
        }
        atomic_json(self.heartbeat_path, payload)

    async def ws_loop(self) -> None:
        from websockets.asyncio.client import connect
        symbols = list(SUPPORTED_PAIRS.values())
        while True:
            try:
                async with self.lock:
                    self.books = {symbol: self.book_mod.Book(depth=10) for symbol in symbols}
                self.ws_connected = False
                async with connect(
                    self.book_mod.WS_URL,
                    open_timeout=15,
                    ping_interval=10,
                    ping_timeout=10,
                    max_size=8 * 1024 * 1024,
                ) as ws:
                    await ws.send(json.dumps({
                        "method": "subscribe",
                        "params": {"channel": "book", "symbol": symbols, "depth": 10, "snapshot": True},
                        "req_id": 3001,
                    }))
                    self.ws_connected = True
                    self.last_ws_error = None
                    while True:
                        raw = await ws.recv()
                        received = utcnow()
                        self.last_ws_message_utc = received
                        msg = json.loads(raw, parse_float=Decimal)
                        if not isinstance(msg, dict):
                            continue
                        if msg.get("method") == "subscribe":
                            if msg.get("success") is not True:
                                raise RuntimeError("H3 subscribe failed: " + str(msg.get("error") or "unknown"))
                            continue
                        if msg.get("channel") != "book" or msg.get("type") not in {"snapshot", "update"}:
                            continue
                        async with self.lock:
                            for row in msg.get("data") or []:
                                if not isinstance(row, dict):
                                    continue
                                symbol = str(row.get("symbol") or "")
                                if symbol not in self.books:
                                    continue
                                self.books[symbol].process(str(msg["type"]), row, received)
                            if self.runtime_ready_at_utc is None and self.books_ready():
                                self.runtime_ready_at_utc = utcnow()
            except Exception as exc:
                self.ws_connected = False
                self.last_ws_error = f"{type(exc).__name__}:{str(exc)[:240]}"
                await asyncio.sleep(2)

    def candidate_files(self) -> list[Path]:
        return sorted(
            (self.v2r4 / "handoff_queue").glob("*.json"),
            key=lambda p: p.stat().st_mtime,
        )

    async def capture_loop(self) -> None:
        while True:
            try:
                status = self.write_status()
                if self.runtime_ready_at_utc and not status["intake_should_stop"]:
                    for p in self.candidate_files():
                        try:
                            c = read_json(p)
                        except Exception:
                            continue
                        pair = str(c.get("pair") or "")
                        if pair not in SUPPORTED_PAIRS:
                            continue
                        cid = str(c.get("candidate_id") or "")
                        if not cid:
                            continue
                        if cid in self.synced_candidate_ids and not (self.evidence_dir / f"{cid}.json").exists():
                            continue
                        target = self.context_dir / f"{cid}.json"
                        if target.exists():
                            continue
                        event_time = str(c.get("event_time_utc") or "")
                        if not event_time:
                            continue
                        if parse_utc(event_time) < parse_utc(self.runtime_ready_at_utc):
                            continue

                        captured_at = utcnow()
                        symbol = SUPPORTED_PAIRS[pair]
                        async with self.lock:
                            book = self.books.get(symbol)
                            if book is None or not book.last_exchange_at_utc or not book.last_received_at_utc:
                                ctx = None
                            else:
                                fresh = context_is_fresh(
                                    source_exchange_at_utc=book.last_exchange_at_utc,
                                    received_at_utc=book.last_received_at_utc,
                                    evaluation_clock_utc=captured_at,
                                    maximum_state_age_ms=self.capture_acceptance_ms,
                                    maximum_source_clock_lead_ms=MAX_SOURCE_CLOCK_LEAD_MS,
                                )
                                if fresh and book.checksum_fail == 0 and book.checksum_pass >= 1 and book.bids and book.asks:
                                    best_bid = max(book.bids)
                                    best_ask = min(book.asks)
                                    if best_ask > best_bid:
                                        mid = (best_bid + best_ask) / Decimal(2)
                                        bid_depth = sum(x * q for x, q in book.bids.items())
                                        ask_depth = sum(x * q for x, q in book.asks.items())
                                        denom = bid_depth + ask_depth
                                        ctx = compact_h3_context(
                                            pair=pair,
                                            source_exchange_at_utc=book.last_exchange_at_utc,
                                            received_at_utc=book.last_received_at_utc,
                                            spread_bps=float((best_ask - best_bid) / mid * Decimal(10000)),
                                            bid_depth_quote_top10=float(bid_depth),
                                            ask_depth_quote_top10=float(ask_depth),
                                            depth_imbalance_top10=float((bid_depth - ask_depth) / denom) if denom > 0 else 0.0,
                                        )
                                    else:
                                        ctx = None
                                else:
                                    ctx = None

                        if ctx is None:
                            sidecar = {
                                "schema_version": 1,
                                "kind": "V3_H3_SHADOW_CONTEXT_SIDECAR_V1",
                                "status": "MISSING_FAIL_CLOSED",
                                "shadow_candidate_id": EXPECTED_SHADOW_ID,
                                "candidate_id": cid,
                                "queue_id": c.get("queue_id"),
                                "pair": pair,
                                "candidate_event_time_utc": event_time,
                                "captured_at_utc": captured_at,
                                "reason": "no checksum-valid H3 state inside frozen capture freshness gate",
                                "guardrails": {"orders": False, "real_money_actions": False},
                            }
                        else:
                            sidecar = {
                                "schema_version": 1,
                                "kind": "V3_H3_SHADOW_CONTEXT_SIDECAR_V1",
                                "status": "PASS",
                                "shadow_candidate_id": EXPECTED_SHADOW_ID,
                                "candidate_id": cid,
                                "queue_id": c.get("queue_id"),
                                "pair": pair,
                                "candidate_event_time_utc": event_time,
                                "captured_at_utc": captured_at,
                                "context": ctx,
                                "guardrails": {"orders": False, "real_money_actions": False},
                            }
                        atomic_json(target, sidecar)
                self.capture_error = None
                await asyncio.sleep(0.35)
            except Exception as exc:
                self.capture_error = f"{type(exc).__name__}:{str(exc)[:240]}"
                await asyncio.sleep(1)

    def evaluate_pair(self, candidate: dict[str, Any], baseline: dict[str, Any], sidecar: dict[str, Any]) -> dict[str, Any]:
        cid = str(candidate["candidate_id"])
        baseline_action = decision_action(baseline)
        require(baseline.get("kind") == "PAPER_V2_DECISION_V2", "baseline decision kind mismatch")
        require(baseline.get("candidate_id") == cid, "baseline/candidate id mismatch")
        require(baseline.get("series_id") == EXPECTED_BASELINE_SERIES, "baseline series mismatch")
        require(baseline.get("strategy_revision") == EXPECTED_BASELINE_REVISION, "baseline strategy revision mismatch")
        require(baseline.get("real_money_actions_enabled") is False, "baseline real-money guard mismatch")

        if sidecar.get("status") != "PASS":
            return {
                "schema_version": 1,
                "kind": "V3_H3_SHADOW_DECISION_V1",
                "status": "H3_CONTEXT_MISSING_BASELINE_PASSTHROUGH",
                "shadow_candidate_id": EXPECTED_SHADOW_ID,
                "candidate_id": cid,
                "queue_id": candidate.get("queue_id"),
                "baseline_series_id": EXPECTED_BASELINE_SERIES,
                "pair": candidate["pair"],
                "candidate_event_time_utc": candidate["event_time_utc"],
                "context_status": "MISSING_FAIL_CLOSED",
                "baseline_decision": baseline_action,
                "control_replay_decision": baseline_action,
                "h3_shadow_decision": baseline_action,
                "baseline_replay_stable": True,
                "causal_decision_diverged": False,
                "raw_decision_diverged_vs_official": False,
                "h3_context": sidecar,
                "guardrails": {
                    "baseline_mutated": False, "paper_position_created": False,
                    "orders": False, "real_money_actions": False,
                    "automatic_promotion": False,
                },
            }

        if reason_codes(baseline) & HARD_PASSTHROUGH_REASONS:
            return {
                "schema_version": 1,
                "kind": "V3_H3_SHADOW_DECISION_V1",
                "status": "HARD_BASELINE_GATE_PASSTHROUGH",
                "shadow_candidate_id": EXPECTED_SHADOW_ID,
                "candidate_id": cid,
                "queue_id": candidate.get("queue_id"),
                "baseline_series_id": EXPECTED_BASELINE_SERIES,
                "pair": candidate["pair"],
                "candidate_event_time_utc": candidate["event_time_utc"],
                "context_status": "PASS",
                "baseline_decision": baseline_action,
                "control_replay_decision": baseline_action,
                "h3_shadow_decision": baseline_action,
                "baseline_replay_stable": True,
                "causal_decision_diverged": False,
                "raw_decision_diverged_vs_official": False,
                "h3_context": sidecar,
                "guardrails": {
                    "baseline_mutated": False, "paper_position_created": False,
                    "orders": False, "real_money_actions": False,
                    "automatic_promotion": False,
                },
            }

        current = copy.deepcopy(baseline["fresh_kraken_ticker"])
        external = copy.deepcopy(baseline["decision_context"])

        control_raw, control_api = self.base.call_evaluator(
            candidate, current, copy.deepcopy(external), self.active_spec, self.active_control
        )
        control_decision = self.base.apply_public_tradability_gate(
            self.base.fail_safe_normalize(control_raw, current),
            current, external, self.active_spec
        )

        h3_external = copy.deepcopy(external)
        h3_external["v3_h3_orderbook_context"] = {
            **copy.deepcopy(sidecar["context"]),
            "interpretation": (
                "Frozen V3-H3 raw point-in-time context only. No directional sign, threshold, "
                "transform, score weight, ranking or automatic trade rule."
            ),
        }
        h3_raw, h3_api = self.base.call_evaluator(
            candidate, current, h3_external, self.active_spec, self.active_control
        )
        h3_decision = self.base.apply_public_tradability_gate(
            self.base.fail_safe_normalize(h3_raw, current),
            current, h3_external, self.active_spec
        )

        control_action = str(control_decision["decision"])
        h3_action = str(h3_decision["decision"])
        stable = control_action == baseline_action
        causal_diverged = bool(stable and h3_action != control_action)

        return {
            "schema_version": 1,
            "kind": "V3_H3_SHADOW_DECISION_V1",
            "status": "PASS",
            "shadow_candidate_id": EXPECTED_SHADOW_ID,
            "candidate_id": cid,
            "queue_id": candidate.get("queue_id"),
            "baseline_series_id": EXPECTED_BASELINE_SERIES,
            "pair": candidate["pair"],
            "candidate_event_time_utc": candidate["event_time_utc"],
            "baseline_evaluated_at_utc": baseline.get("evaluated_at_utc"),
            "context_status": "PASS",
            "baseline_decision": baseline_action,
            "control_replay_decision": control_action,
            "h3_shadow_decision": h3_action,
            "baseline_replay_stable": stable,
            "causal_divergence_eligible": stable,
            "causal_decision_diverged": causal_diverged,
            "raw_decision_diverged_vs_official": h3_action != baseline_action,
            "baseline_decision_payload": baseline["decision"],
            "control_replay_decision_payload": control_decision,
            "h3_shadow_decision_payload": h3_decision,
            "frozen_market_snapshot": {
                "fresh_kraken_ticker": current,
                "baseline_decision_context_reused": True,
            },
            "h3_context": sidecar,
            "evaluator": {
                "control": control_api,
                "h3": h3_api,
            },
            "cost_reference_pct_per_side": 0.60,
            "guardrails": {
                "same_candidate_snapshot_as_baseline": True,
                "same_fresh_ticker_as_baseline": True,
                "same_public_context_as_baseline_except_h3_addition": True,
                "same_prompt_strategy_revision_as_baseline": True,
                "baseline_mutated": False,
                "paper_position_created": False,
                "slack_action_created": False,
                "orders": False,
                "real_money_actions": False,
                "threshold_search": False,
                "feature_transform_search": False,
                "model_change": False,
                "automatic_winner_selection": False,
                "automatic_promotion": False,
            },
        }

    async def evaluation_loop(self) -> None:
        while True:
            try:
                for cp in sorted(self.context_dir.glob("*.json"), key=lambda p: p.stat().st_mtime):
                    cid = cp.stem
                    target = self.evidence_dir / f"{cid}.json"
                    if target.exists():
                        continue
                    candidate_path = self.v2r4 / "handoff_queue" / f"{cid}.json"
                    baseline_path = self.v2r4 / "paper_decisions" / f"{cid}.json"
                    if not candidate_path.exists() or not baseline_path.exists():
                        continue
                    candidate = read_json(candidate_path)
                    sidecar = read_json(cp)
                    baseline = read_json(baseline_path)
                    evidence = await asyncio.to_thread(self.evaluate_pair, candidate, baseline, sidecar)
                    evidence["recorded_at_utc"] = utcnow()
                    evidence["source_commit"] = self.source_commit
                    atomic_json(target, evidence)
                    self.last_eval_utc = utcnow()
                    self.eval_error = None
                    self.write_status()
                await asyncio.sleep(0.75)
            except Exception as exc:
                self.eval_error = f"evaluate:{type(exc).__name__}:{str(exc)[:300]}"
                await asyncio.sleep(3)

    def relay_sync(self, evidence: list[dict[str, Any]], status: dict[str, Any]) -> dict[str, Any]:
        rows = []
        for ev in evidence:
            rows.append({
                "candidate_id": ev["candidate_id"],
                "shadow_candidate_id": EXPECTED_SHADOW_ID,
                "baseline_series_id": EXPECTED_BASELINE_SERIES,
                "pair": ev.get("pair"),
                "candidate_event_time": ev.get("candidate_event_time_utc"),
                "context_status": ev.get("context_status"),
                "baseline_decision": ev.get("baseline_decision"),
                "control_replay_decision": ev.get("control_replay_decision"),
                "shadow_decision": ev.get("h3_shadow_decision"),
                "baseline_replay_stable": ev.get("baseline_replay_stable"),
                "decision_diverged": ev.get("causal_decision_diverged"),
                "payload": ev,
                "source_commit": self.source_commit,
            })
        body = json.dumps({
            "action": "sync_h3_shadow",
            "shadow_candidate_id": EXPECTED_SHADOW_ID,
            "baseline_series_id": EXPECTED_BASELINE_SERIES,
            "baseline_strategy_revision": EXPECTED_BASELINE_REVISION,
            "evidence": rows,
            "status": {
                "shadow_candidate_id": EXPECTED_SHADOW_ID,
                "generated_at": status["generated_at_utc"],
                "payload": status,
                "source_commit": self.source_commit,
            },
        }).encode()
        req = urllib.request.Request(
            RELAY_URL,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Shadow-Evidence-Token": self.relay_token,
                "User-Agent": "v3-h3-shadow-runtime/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    async def sync_loop(self) -> None:
        while True:
            try:
                evidence = []
                for p in sorted(self.evidence_dir.glob("*.json"), key=lambda x: (x.stat().st_mtime, x.name)):
                    if p.stem in self.synced_candidate_ids:
                        continue
                    try:
                        evidence.append(read_json(p))
                    except Exception:
                        continue
                    if len(evidence) >= 100:
                        break
                status = self.write_status()
                result = await asyncio.to_thread(self.relay_sync, evidence, status)
                require(result.get("ok") is True, "H3 relay did not return ok")
                for ev in evidence:
                    cid = str(ev.get("candidate_id") or "")
                    if cid:
                        self.synced_candidate_ids.add(cid)
                self.prune_local_after_successful_sync()
                self.cloud_sync_status = "PASS"
                self.cloud_sync_error = None
                self.last_cloud_sync_utc = utcnow()
            except Exception as exc:
                self.cloud_sync_status = "DEGRADED"
                self.cloud_sync_error = f"{type(exc).__name__}:{str(exc)[:260]}"
            await asyncio.sleep(30)

    async def heartbeat_loop(self) -> None:
        while True:
            try:
                self.write_heartbeat()
            except Exception:
                pass
            await asyncio.sleep(5)

    async def run(self) -> None:
        await asyncio.gather(
            self.ws_loop(),
            self.capture_loop(),
            self.evaluation_loop(),
            self.sync_loop(),
            self.heartbeat_loop(),
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-root", type=Path, required=True)
    ap.add_argument("--v2r4-app-root", type=Path, required=True)
    ap.add_argument("--trading-root", type=Path, required=True)
    ap.add_argument("--api-key-file", type=Path, required=True)
    ap.add_argument("--relay-token-file", type=Path, required=True)
    ap.add_argument("--source-commit", required=True)
    args = ap.parse_args()
    runtime = Runtime(args)
    asyncio.run(runtime.run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
