#!/usr/bin/env python3
"""Manual SINGLE-CANDIDATE PAPER-only model comparison on the Mini-PC.

All V2R4 runtime paths are READ ONLY. No state writes, trading API, Supabase,
GitHub runtime updates, scheduled tasks, position simulator, secrets output.
Only two isolated research LLM evaluations, each with the SAME fresh snapshot.
This is an input/decision-path experiment, NOT a net-profit or promotion gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from paper_evaluator import evaluate
from paper_evaluator.v3_entry_handoff_probe import (
    attach_to_future_evaluator, now_utc, utc,
)
from paper_evaluator.successor_coin_entry_evidence_v1 import fetch_public_entry_evidence
from paper_context import build_context


def select_fresh_handoff(directory: Path, control: dict, *,
                         observed_now: datetime | None = None,
                         max_age_seconds: int = 900) -> tuple[Path, dict] | None:
    now = observed_now or datetime.now(timezone.utc)
    start = utc(control["series_started_at_utc"])
    if not directory.is_dir():
        return None
    # Deterministic finite scan; no re-evaluation or backfill of old events.
    files = sorted(directory.glob("*.json"), key=lambda p:(p.stat().st_mtime,p.name),reverse=True)[:40]
    for path in files:
        try:
            item=json.loads(path.read_text("utf-8"))
            evaluate.validate_candidate(item,str(path))
            ts=utc(item["event_time_utc"])
            age=(now-ts).total_seconds()
            if start <= ts <= now and 0 <= age <= max_age_seconds:
                return path,item
        except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError):
            continue
    return None


def freeze_runtime_provenance(runtime_app: Path, code_root: Path,
                              control: dict) -> dict[str,str]:
    if control.get("enabled") is not True or control.get("real_money_actions_enabled") is not False:
        raise ValueError("expected active PAPER-only V2R4 control")
    if control.get("strategy_revision") != "V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION":
        raise ValueError("unexpected source strategy revision")
    paths=("paper_evaluator/evaluate.py","paper_context.py")
    result={}
    for path in paths:
        running=runtime_app/path
        prepared=code_root/path
        if not running.is_file() or not prepared.is_file():
            raise ValueError("required frozen evaluator/context file missing")
        h1=hashlib.sha256(running.read_bytes()).hexdigest()
        h2=hashlib.sha256(prepared.read_bytes()).hexdigest()
        if h1!=h2:
            raise ValueError("frozen active evaluator code differs from detached research checkout: "+path)
        result[path]=h1
    return result


def clean_decision(raw: dict, ticker: dict, external: dict, spec: dict) -> dict:
    # No apply_sample_cap/position side effects: this is a decision-input probe,
    # NOT an official paper fill or recheck. Kraken public execution gates remain.
    d=evaluate.apply_public_tradability_gate(
        evaluate.fail_safe_normalize(raw,ticker),ticker,external,spec)
    return {"decision":d["decision"],"setup_lane":d["setup_lane"],
            "reason_codes":(d.get("reason_codes") or [])[:8],
            "valid_stop_below_ask":(
                d.get("decision")=="BUY_SCOUT"
                and isinstance(d.get("stop_eur"),(int,float))
                and 0 < d["stop_eur"] < ticker["ask"]),
            "valid_stage2_above_ask":(
                d.get("decision")=="BUY_SCOUT"
                and isinstance(d.get("stage2_trigger_eur"),(int,float))
                and d["stage2_trigger_eur"]>ticker["ask"]),
            "expected_remaining_move_pct":d.get("expected_remaining_move_pct"),
            "risk_reward_after_costs":d.get("risk_reward_after_costs"),
            "wait_conditions":len(d.get("watch_conditions") or [])}


def execute_one_shot(trading_root:Path,code_root:Path) -> dict:
    runtime=trading_root/"Runtime"/"v2r4-paper-app"
    control=json.loads((runtime/"paper_runtime_control.json").read_text("utf-8"))
    spec=json.loads((runtime/"paper_strategy_spec.json").read_text("utf-8"))
    checked=freeze_runtime_provenance(runtime,code_root,control)
    selected=select_fresh_handoff(runtime/"handoff_queue",control)
    if selected is None:
        return {"status":"BLOCKED_NO_FRESH_CANONICAL_CANDIDATE_IN_LAST_15M",
                "source_series_id":control["series_id"],"model_calls":0,
                "active_v2r4_changed":False,"orders":False}
    path,c=selected
    # Snapshot is collected ONCE for both branches, and all observations are
    # prospective. No replay using OHLC published after candidate detection.
    current=evaluate.kraken_ticker(c["altname"])
    base_context=build_context(c,current)
    entry=fetch_public_entry_evidence(c["altname"],c["pair"])
    observed_at=now_utc()
    enriched=attach_to_future_evaluator(c,base_context,entry,observed_at)
    # Block API/model calls if context fetch took too long or source is missing.
    model_current=utc(observed_at)
    if (model_current-utc(c["event_time_utc"])).total_seconds()>900:
        raise ValueError("candidate aged out during context acquisition")

    keyfile=trading_root/"Secrets"/"openai-api-key.txt"
    key=keyfile.read_text("utf-8").strip()
    if len(key)<20:
        raise ValueError("existing local OpenAI key not readable/valid")
    os.environ["OPENAI_API_KEY"]=key
    # No additional archive; same score/snapshot, candidate and V2R4 spec.
    baseline_raw,baseline_meta=evaluate.call_evaluator(c,current,base_context,spec,control)
    successor_raw,successor_meta=evaluate.call_evaluator(c,current,enriched,spec,control)
    base=clean_decision(baseline_raw,current,base_context,spec)
    nextv=clean_decision(successor_raw,current,enriched,spec)
    return {
      "kind":"V3_ONE_SHOT_SAME_SNAPSHOT_MODEL_COMPARISON_V1",
      "status":"ISOLATED_MODEL_PAIR_COMPLETE_NOT_A_PROFITABILITY_RESULT",
      "candidate_id":c["candidate_id"],"pair":c["pair"],
      "source_series_id":control["series_id"],
      "source_strategy_revision":control["strategy_revision"],
      "source_candidate_event_utc":c["event_time_utc"],
      "evidence_known_at_utc":entry["known_at_utc"],
      "model_snapshot_at_utc":observed_at,
      "same_candidate_same_ticker_same_standard_context":True,
      "coin_evidence_only_changed_input":True,
      "baseline_is_new_independent_replay_not_official_original_decision":True,
      "candidate_specific_features_ready":True,
      "frozen_evaluator_hashes":checked,
      "baseline":base,"successor_with_coin_evidence":nextv,
      "baseline_response_id":baseline_meta.get("response_id"),
      "successor_response_id":successor_meta.get("response_id"),
      "model_calls":2,"paper_positions_created":0,"real_orders":0,
      "active_v2r4_changed":False,"active_h3_changed":False,
      "automatic_promotion":False,"valid_paper_trade_proven":False,
      "economic_edge_proven":False,
      "note":"Only a one-candidate input sensitivity experiment. BUY here is model suggestion, NOT prospective completed Paper trade or net edge."
    }


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--trading-root",type=Path,required=True)
    parser.add_argument("--code-root",type=Path,required=True)
    args=parser.parse_args()
    try:
        r=execute_one_shot(args.trading_root,args.code_root)
    except Exception as e:
        # Exclude exception messages because they could carry source/secret data.
        r={"kind":"V3_ONE_SHOT_SAME_SNAPSHOT_MODEL_COMPARISON_V1",
           "status":"BLOCKED_PRECONDITION_OR_SOURCE",
           "failure_type":type(e).__name__,
           "model_calls_proven":False,
           "active_v2r4_changed":False,"real_orders":0}
    print(json.dumps(r,sort_keys=True))
    return 0 if r.get("status")=="ISOLATED_MODEL_PAIR_COMPLETE_NOT_A_PROFITABILITY_RESULT" else 2


if __name__=="__main__":
    raise SystemExit(main())
