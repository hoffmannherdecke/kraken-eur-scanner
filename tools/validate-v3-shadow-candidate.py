#!/usr/bin/env python3
"""Validate a V3 shadow candidate against the one-change contract."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT=ROOT/"research/v3/shadow-candidate-contract-v1.json"

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("candidate",type=Path)
    ap.add_argument("--contract",type=Path,default=DEFAULT_CONTRACT)
    args=ap.parse_args()

    contract=json.loads(args.contract.read_text("utf-8"))
    cand=json.loads(args.candidate.read_text("utf-8"))
    errors=[]

    for k in contract["required_candidate_fields"]:
        if k not in cand:
            errors.append(f"missing required field: {k}")

    allowed_status=set(contract["allowed_candidate_statuses"])
    if cand.get("status") not in allowed_status:
        errors.append(f"invalid status: {cand.get('status')!r}")

    changed=cand.get("changed_components")
    if not isinstance(changed,list):
        errors.append("changed_components must be list")
        changed=[]
    if len(changed)!=int(contract["one_change_rule"]["changed_components_exact_count"]):
        errors.append("exactly one changed component is required")
    allowed_components=set(contract["one_change_rule"]["allowed_component_classes"])
    for x in changed:
        if x not in allowed_components:
            errors.append(f"unsupported changed component: {x}")

    cid=str(cand.get("candidate_id") or "")
    if not re.fullmatch(r"[A-Za-z0-9._-]+",cid):
        errors.append("candidate_id format invalid")
    if cand.get("baseline_strategy_revision")==cand.get("candidate_strategy_revision"):
        errors.append("candidate revision must differ from baseline revision")

    sha=str(cand.get("frozen_config_sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}",sha):
        errors.append("frozen_config_sha256 must be lowercase sha256")

    guard=cand.get("guardrails") or {}
    if guard.get("active_baseline_changed") is not False:
        errors.append("active baseline must remain unchanged")
    if guard.get("midrun_tuning_allowed") is not False:
        errors.append("midrun tuning must be false")
    if guard.get("real_money_actions") is not False:
        errors.append("real-money actions must be false")

    plan=cand.get("evidence_plan") or {}
    if plan.get("same_candidate_stream") is not True:
        errors.append("same candidate stream must be true")
    if plan.get("shared_market_clock") is not True:
        errors.append("shared market clock must be true")

    promo=cand.get("promotion_gate") or {}
    if promo.get("automatic_promotion") is not False:
        errors.append("automatic promotion must be false")

    status=cand.get("status")
    if status in {"FROZEN_FOR_SHADOW","SHADOW_RUNNING","SHADOW_COMPLETE","PROMOTION_REVIEW"}:
        if str(plan.get("minimum_gate") or "").startswith("MUST_BE_DEFINED"):
            errors.append("minimum gate must be frozen before shadow")
        if str(plan.get("cost_model_reference") or "").startswith("MUST_BE_DEFINED"):
            errors.append("cost model must be frozen before shadow")
        if promo.get("predefined") is not True:
            errors.append("promotion gate must be predefined before shadow")

    result={
      "kind":"V3_SHADOW_CANDIDATE_VALIDATION_V1",
      "status":"PASS" if not errors else "FAIL",
      "candidate_id":cand.get("candidate_id"),
      "changed_components":changed,
      "errors":errors,
      "guardrails":{
        "baseline_mutated":False,
        "strategy_promoted":False,
        "orders":False,
        "real_money_actions":False
      }
    }
    print(json.dumps(result,sort_keys=True))
    return 0 if not errors else 2

if __name__=="__main__":
    raise SystemExit(main())
