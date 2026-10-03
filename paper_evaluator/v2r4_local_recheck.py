#!/usr/bin/env python3
"""Local paper-only V2R4 trigger -> fresh recheck bridge.

This module is intentionally separate from the active V2R3 runtime. It consumes
one already-matched V2R4 trigger receipt, re-fetches current public Kraken
execution/context data and performs one fresh PAPER evaluator call.

It never uses private Kraken credentials and contains no order endpoint.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

try:
    from .evaluate import (
        FEE_PCT,
        apply_public_tradability_gate,
        apply_sample_cap,
        call_evaluator,
        enrich_derivatives_delta,
        fail_safe_normalize,
        kraken_ticker,
        validate_candidate,
        zdt,
    )
except ImportError:
    from evaluate import (
        FEE_PCT,
        apply_public_tradability_gate,
        apply_sample_cap,
        call_evaluator,
        enrich_derivatives_delta,
        fail_safe_normalize,
        kraken_ticker,
        validate_candidate,
        zdt,
    )

from paper_context import build_context
try:
    from .v2r4_trigger_plan import build_wait_trigger_plan
except ImportError:
    from v2r4_trigger_plan import build_wait_trigger_plan


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def load_api_key(path: Path | None) -> None:
    if os.environ.get("OPENAI_API_KEY", "").strip():
        return
    if path is None or not path.exists():
        raise RuntimeError("OPENAI_API_KEY missing and api-key file unavailable")
    key = path.read_text("utf-8").strip()
    if len(key) < 20:
        raise RuntimeError("OpenAI API key file is empty/too short")
    os.environ["OPENAI_API_KEY"] = key


def validate_trigger_receipt(receipt: dict[str, Any], candidate: dict[str, Any]) -> None:
    if receipt.get("kind") != "V2R4_PAPER_WAIT_TRIGGER_RECEIPT":
        raise ValueError("unsupported trigger receipt kind")
    if receipt.get("paper_only") is not True:
        raise ValueError("trigger receipt must be paper-only")
    if receipt.get("matched") is not True:
        raise ValueError("trigger receipt must be matched")
    if receipt.get("expired") is True:
        raise ValueError("expired trigger receipt cannot request recheck")
    if receipt.get("next_action") != "FRESH_PAPER_RECHECK_ONLY":
        raise ValueError("unsafe trigger next_action")
    if receipt.get("real_money_actions_enabled") is not False:
        raise ValueError("real-money flag must be false")
    if receipt.get("candidate_id") != candidate.get("candidate_id"):
        raise ValueError("trigger/candidate identity mismatch")
    if receipt.get("pair") != candidate.get("pair"):
        raise ValueError("trigger/candidate pair mismatch")


def make_paper_entry(decision: dict[str, Any], ticker: dict[str, float], spec: dict[str, Any], opened_at: str) -> dict[str, Any]:
    scout = float(spec["entry"]["scout_notional_eur"])
    stage2 = float(spec["entry"]["stage2_notional_eur"])
    fill = float(ticker["ask"])
    ttl = int(decision["stage2_ttl_minutes"])
    opened = zdt(opened_at)
    return {
        "status": "SCOUT_FILLED_SIMULATED_AT_FRESH_ASK_AFTER_V2R4_TRIGGER",
        "scout_notional_eur": scout,
        "fill_price_eur": fill,
        "quantity": scout / fill,
        "entry_fee_eur": scout * FEE_PCT / 100,
        "entry_spread_pct": ticker["spread_pct"],
        "slippage_model": "fresh best ask; paper only",
        "stop_eur": decision["stop_eur"],
        "opened_at_utc": opened_at,
        "stage2_plan": {
            "status": "PENDING",
            "trigger_eur": float(decision["stage2_trigger_eur"]),
            "notional_eur": stage2,
            "ttl_minutes": ttl,
            "expires_at_utc": (opened + timedelta(minutes=ttl)).isoformat().replace("+00:00", "Z"),
            "execution_type": "SIMULATED_STOP_BUY_CONFIRMATION",
        },
    }


def run_recheck(
    *,
    candidate_path: Path,
    receipt_path: Path,
    spec_path: Path,
    control_path: Path,
    out_dir: Path,
    api_key_file: Path | None,
) -> Path:
    candidate = read_json(candidate_path)
    validate_candidate(candidate, candidate_path)
    receipt = read_json(receipt_path)
    validate_trigger_receipt(receipt, candidate)

    spec = read_json(spec_path)
    control = read_json(control_path)
    if spec.get("paper_only") is not True or spec.get("real_money_actions_enabled") is not False:
        raise ValueError("V2R4 spec safety flags invalid")
    if control.get("enabled") is not True or control.get("real_money_actions_enabled") is not False:
        raise ValueError("V2R4 control safety flags invalid")

    load_api_key(api_key_file)

    started = utcnow()
    ticker = kraken_ticker(candidate["altname"])
    external = enrich_derivatives_delta(
        build_context(candidate, ticker),
        candidate["pair"],
        control["series_id"],
    )

    enriched = dict(candidate)
    enriched["v2r4_fresh_recheck_context"] = {
        "kind": "V2R4_TRIGGERED_FRESH_PAPER_RECHECK",
        "trigger_receipt": receipt,
        "fresh_kraken_ticker": ticker,
        "instruction": (
            "A deterministic local WAIT trigger matched. Perform one fresh PAPER "
            "evaluation using current Kraken execution/context data. Trigger match "
            "is not a buy signal and must never bypass costs, stop, tradability, "
            "late-chase or stage-2 confirmation requirements."
        ),
    }

    raw, api = call_evaluator(enriched, ticker, external, spec, control)
    decision = apply_public_tradability_gate(
        apply_sample_cap(fail_safe_normalize(raw, ticker), control),
        ticker,
        external,
        spec,
    )
    completed = utcnow()

    record = {
        "schema_version": 1,
        "kind": "V2R4_LOCAL_TRIGGER_RECHECK_V1",
        "test_id": control["test_id"],
        "series_id": control["series_id"],
        "strategy_revision": spec["strategy_revision"],
        "candidate_id": candidate["candidate_id"],
        "pair": candidate["pair"],
        "trigger_receipt_file": str(receipt_path),
        "recheck_started_at_utc": started,
        "recheck_completed_at_utc": completed,
        "trigger_observed_at_utc": receipt.get("observed_at_utc"),
        "fresh_kraken_ticker": ticker,
        "decision_context": external,
        "decision": decision,
        "evaluator": api,
        "paper_entry": None,
        "next_wait_trigger_plan": None,
        "paper_only": True,
        "real_money_actions_enabled": False,
        "order_api": False,
    }

    if decision["decision"] == "BUY_SCOUT":
        record["paper_entry"] = make_paper_entry(decision, ticker, spec, completed)
    elif decision["decision"] == "WAIT":
        record["next_wait_trigger_plan"] = build_wait_trigger_plan(candidate, decision, completed)

    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = out_dir / f"{stamp}-{candidate['candidate_id']}.json"
    target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", "utf-8")

    print("V2R4_LOCAL_RECHECK_RESULT " + json.dumps({
        "candidate_id": candidate["candidate_id"],
        "pair": candidate["pair"],
        "decision": decision["decision"],
        "paper_entry": record["paper_entry"] is not None,
        "next_wait_trigger_plan": record["next_wait_trigger_plan"] is not None,
        "real_money_actions_enabled": False,
        "output": str(target),
    }, sort_keys=True))
    return target


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--trigger-receipt", type=Path, required=True)
    ap.add_argument("--spec", type=Path, required=True)
    ap.add_argument("--control", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--api-key-file", type=Path)
    args = ap.parse_args()

    run_recheck(
        candidate_path=args.candidate,
        receipt_path=args.trigger_receipt,
        spec_path=args.spec,
        control_path=args.control,
        out_dir=args.out_dir,
        api_key_file=args.api_key_file,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
