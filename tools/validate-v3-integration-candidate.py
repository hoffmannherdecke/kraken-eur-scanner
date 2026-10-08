#!/usr/bin/env python3
"""Validate a multi-component V3+ integration candidate."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/"research/v3/integration-candidate-contract-v1.json"
STATE=ROOT/"project-current-state.json"

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("candidate",type=Path)
    args=ap.parse_args()
    c=json.loads(CONTRACT.read_text("utf-8"))
    x=json.loads(args.candidate.read_text("utf-8"))
    state=json.loads(STATE.read_text("utf-8"))
    errors=[]
    for k in c["required_candidate_fields"]:
        if k not in x: errors.append(f"missing required field: {k}")
    if x.get("status") not in set(c["allowed_statuses"]):
        errors.append("invalid status")
    comps=x.get("integrated_components")
    if not isinstance(comps,list) or len(comps)<2 or len(comps)!=len(set(comps or [])):
        errors.append("integration candidate requires at least two unique integrated_components")
        comps=comps or []
    reviews=x.get("prerequisite_component_reviews")
    if not isinstance(reviews,list) or len(reviews)!=len(comps):
        errors.append("every integrated component requires exactly one prerequisite review record")
    else:
        seen=set()
        for r in reviews:
            if not isinstance(r,dict) or not r.get("component") or not r.get("review_artifact"):
                errors.append("invalid prerequisite component review")
                continue
            seen.add(r["component"])
            p=ROOT/r["review_artifact"]
            if not p.is_file(): errors.append(f"review artifact missing: {r['review_artifact']}")
        if seen!=set(comps):
            errors.append("prerequisite reviews must match integrated_components exactly")
    sha=str(x.get("frozen_config_sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}",sha):
        errors.append("frozen_config_sha256 must be lowercase sha256")
    plan=x.get("evidence_plan") or {}
    if plan.get("same_candidate_stream") is not True: errors.append("same candidate stream required")
    if plan.get("shared_market_clock") is not True: errors.append("shared market clock required")
    if plan.get("baseline_replay_required_for_causal_divergence") is not True: errors.append("baseline replay required")
    if not str(plan.get("baseline_replay_stability_gate") or "").strip(): errors.append("baseline replay stability gate required")
    if not str(plan.get("minimum_gate") or "").strip(): errors.append("minimum gate required")
    if not str(plan.get("cost_model_reference") or "").strip(): errors.append("cost model reference required")
    promo=x.get("promotion_gate") or {}
    if promo.get("automatic_promotion") is not False: errors.append("automatic promotion must be false")
    guard=x.get("guardrails") or {}
    if guard.get("active_baseline_changed") is not False: errors.append("active baseline must remain unchanged")
    if guard.get("midrun_tuning_allowed") is not False: errors.append("midrun tuning must be false")
    if guard.get("real_money_actions") is not False: errors.append("real money must be false")
    active_status={"FROZEN_FOR_SHADOW","SHADOW_RUNNING","SHADOW_COMPLETE","PROMOTION_REVIEW"}
    if x.get("status") in active_status:
        current=state.get("active_strategy") or {}
        if x.get("baseline_strategy_revision")!=current.get("strategy_revision"): errors.append("baseline strategy must match current active strategy")
        if x.get("baseline_series_id")!=current.get("series_id"): errors.append("baseline series must match current active series")
        active=(state.get("strategy_changing_shadow_wip") or {}).get("active") or []
        if x.get("status")=="SHADOW_RUNNING" and active and not any(a.get("candidate_id")==x.get("candidate_id") for a in active):
            errors.append("running integration candidate must own the single strategy-changing shadow slot")
    print(json.dumps({"kind":"V3_INTEGRATION_CANDIDATE_VALIDATION_V1","status":"PASS" if not errors else "FAIL","candidate_id":x.get("candidate_id"),"integrated_components":comps,"errors":errors},sort_keys=True))
    return 0 if not errors else 2
if __name__=="__main__":
    raise SystemExit(main())
