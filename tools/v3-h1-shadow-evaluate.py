#!/usr/bin/env python3
"""Evaluate frozen V3-H1-SHADOW-001 without mutating active V2R3.

The shadow evaluator reuses the exact persisted baseline candidate snapshot,
fresh Kraken ticker, and public decision context from the active V2R3 decision.
Its only decision-affecting delta is the additional fixed H1 relative-context
sidecar. It writes research evidence only: no paper position, Slack action,
order, private API, baseline mutation, or automatic promotion.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
BASE_PATH=ROOT/"paper_evaluator/evaluate.py"
_spec=importlib.util.spec_from_file_location("v2r3_base_eval",BASE_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError("unable to load baseline evaluator")
base=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

CANDIDATE_ID="V3-H1-SHADOW-001"
CONFIG=ROOT/"research/v3/shadow-candidates/v3-h1-shadow-001-config.json"
EXPECTED_CONFIG_SHA="24b381673094ec3ff2451ad06d8889c90e1a00956cc13e64083ed20640b71e9a"

def sha256_file(p:Path)->str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def require(condition:bool,msg:str)->None:
    if not condition:
        raise RuntimeError(msg)

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--candidate",type=Path,required=True)
    ap.add_argument("--baseline-decision",type=Path,required=True)
    ap.add_argument("--h1-context",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()

    require(sha256_file(CONFIG)==EXPECTED_CONFIG_SHA,"frozen H1 config hash mismatch")
    cfg=json.loads(CONFIG.read_text("utf-8"))
    require(cfg.get("candidate_id")==CANDIDATE_ID,"unexpected H1 config candidate")

    candidate=json.loads(a.candidate.read_text("utf-8"))
    base.validate_candidate(candidate,str(a.candidate))
    baseline=json.loads(a.baseline_decision.read_text("utf-8"))
    h1=json.loads(a.h1_context.read_text("utf-8"))

    require(baseline.get("kind")=="PAPER_V2_DECISION_V2","baseline decision kind mismatch")
    require(baseline.get("candidate_id")==candidate.get("candidate_id"),"baseline/candidate id mismatch")
    require(baseline.get("strategy_revision")=="V2R3-2026-09-28","baseline strategy revision mismatch")
    require(baseline.get("real_money_actions_enabled") is False,"baseline real-money guard mismatch")
    require(h1.get("kind")=="V3_H1_SHADOW_CONTEXT_SIDECAR_V1","H1 context kind mismatch")
    require(h1.get("candidate_id")==candidate.get("candidate_id"),"H1/candidate id mismatch")
    require(h1.get("shadow_candidate_id")==CANDIDATE_ID,"H1 shadow candidate id mismatch")

    control,spec,_=base.load_runtime()
    require(control.get("series_id")==baseline.get("series_id"),"active series/baseline series mismatch")
    require(spec.get("strategy_revision")=="V2R3-2026-09-28","active spec no longer matches frozen baseline")

    if h1.get("status")!="PASS":
        out={
          "schema_version":1,
          "kind":"V3_H1_SHADOW_DECISION_V1",
          "status":"SKIPPED_H1_CONTEXT_MISSING",
          "shadow_candidate_id":CANDIDATE_ID,
          "candidate_id":candidate["candidate_id"],
          "series_id":baseline["series_id"],
          "pair":candidate["pair"],
          "baseline_decision":baseline["decision"]["decision"],
          "shadow_decision":None,
          "decision_diverged":False,
          "h1_context":h1,
          "guardrails":{
            "baseline_mutated":False,"paper_position_created":False,"orders":False,
            "real_money_actions":False,"automatic_promotion":False
          }
        }
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n","utf-8")
        print("V3_H1_SHADOW_EVAL "+json.dumps({"status":out["status"],"candidate_id":out["candidate_id"]},sort_keys=True))
        return 0

    current=copy.deepcopy(baseline["fresh_kraken_ticker"])
    external=copy.deepcopy(baseline["decision_context"])
    external["v3_h1_relative_context"]={
      "schema_version":1,
      "source":"same-scan frozen sidecar",
      "leader_minus_target_return_1h_pct":h1["features"]["leader_minus_target_return_1h_pct"],
      "target_minus_peer_median_return_1h_pct":h1["features"]["target_minus_peer_median_return_1h_pct"],
      "leader_median_return_1h_pct":h1["features"]["leader_median_return_1h_pct"],
      "peer_median_return_1h_pct":h1["features"]["peer_median_return_1h_pct"],
      "target_return_1h_pct":h1["features"]["target_return_1h_pct"],
      "eligible_peer_count":h1["features"]["eligible_peer_count"],
      "available_leader_count":h1["features"]["available_leader_count"],
      "interpretation":"Additional relative-market context only. No fixed threshold, transform, score weight or automatic trade rule."
    }

    shadow_spec=copy.deepcopy(spec)
    shadow_spec["strategy_revision"]=CANDIDATE_ID
    raw,api=base.call_evaluator(candidate,current,external,shadow_spec,control)
    normalized=base.fail_safe_normalize(raw,current)
    # Keep the same public tradability/minimum-order gate. Sample-cap state is not
    # re-applied because this pilot does not reserve/open positions and must not
    # depend on later baseline reservation counts.
    decision=base.apply_public_tradability_gate(normalized,current,external,shadow_spec)

    baseline_action=baseline["decision"]["decision"]
    shadow_action=decision["decision"]
    out={
      "schema_version":1,
      "kind":"V3_H1_SHADOW_DECISION_V1",
      "status":"PASS",
      "shadow_candidate_id":CANDIDATE_ID,
      "candidate_id":candidate["candidate_id"],
      "queue_id":candidate["queue_id"],
      "series_id":baseline["series_id"],
      "pair":candidate["pair"],
      "candidate_event_time_utc":candidate["event_time_utc"],
      "baseline_evaluated_at_utc":baseline["evaluated_at_utc"],
      "baseline_strategy_revision":baseline["strategy_revision"],
      "shadow_strategy_revision":CANDIDATE_ID,
      "baseline_decision":baseline_action,
      "shadow_decision":shadow_action,
      "decision_diverged":baseline_action!=shadow_action,
      "baseline_decision_payload":baseline["decision"],
      "shadow_decision_payload":decision,
      "frozen_market_snapshot":{
        "fresh_kraken_ticker":current,
        "baseline_decision_context_reused":True
      },
      "h1_context":h1,
      "evaluator":api,
      "cost_reference_pct_per_side":0.60,
      "guardrails":{
        "same_candidate_snapshot_as_baseline":True,
        "same_fresh_ticker_as_baseline":True,
        "same_public_context_as_baseline_except_h1_addition":True,
        "baseline_mutated":False,
        "paper_position_created":False,
        "slack_action_created":False,
        "orders":False,
        "real_money_actions":False,
        "threshold_search":False,
        "feature_transform_search":False,
        "model_change":False,
        "automatic_winner_selection":False,
        "automatic_promotion":False
      }
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    if a.output.exists():
        existing=a.output.read_text("utf-8")
        encoded=json.dumps(out,indent=2,sort_keys=True)+"\n"
        if existing!=encoded:
            raise RuntimeError("shadow output collision with different content")
    else:
        a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n","utf-8")
    print("V3_H1_SHADOW_EVAL "+json.dumps({
      "status":out["status"],"candidate_id":out["candidate_id"],
      "baseline":baseline_action,"shadow":shadow_action,"diverged":out["decision_diverged"]
    },sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
