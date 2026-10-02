#!/usr/bin/env python3
"""Deterministic fixed review for V3 H1/H6 incremental reports.

No threshold search, p-values, feature selection, winner selection, holdout access,
strategy mutation or promotion. It only summarizes the preregistered metrics already
present in the exact physical report payloads.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from typing import Any

SPLITS=("research_train","calibration","validation")
H1_FEATURES=("leader_minus_target_return_1h","target_minus_peer_median_return_1h")
H6_STRATA=("down","up")

def file_sha(p:Path)->str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def same_sign(values:list[float|None])->bool|None:
    xs=[x for x in values if x is not None]
    if len(xs)!=len(values) or not xs:return None
    return all(x>0 for x in xs) or all(x<0 for x in xs)

def require_base(x:dict[str,Any],trial_id:str,kind:str)->None:
    if x.get("status")!="PASS":raise RuntimeError(f"{trial_id}: status not PASS")
    if x.get("trial_id")!=trial_id:raise RuntimeError(f"{trial_id}: trial id mismatch")
    if x.get("kind")!=kind:raise RuntimeError(f"{trial_id}: kind mismatch")
    g=x.get("guardrails") or {}
    i=x.get("interpretation") or {}
    for k in ("holdout_opened","orders","real_money_actions","threshold_search"):
        if g.get(k) is not False:raise RuntimeError(f"{trial_id}: guard {k} failed")
    if i.get("automatic_winner_selected") is not False:raise RuntimeError(f"{trial_id}: winner guard failed")
    if i.get("promotion_allowed") is not False:raise RuntimeError(f"{trial_id}: promotion guard failed")
    if (x.get("dataset") or {}).get("holdout_status")!="LOCKED_DO_NOT_READ_OR_LABEL":
        raise RuntimeError(f"{trial_id}: holdout status mismatch")
    claimed=x.get("deterministic_summary_sha256")
    if not isinstance(claimed,str) or len(claimed)!=64:raise RuntimeError(f"{trial_id}: missing deterministic hash")
    y=dict(x);y.pop("deterministic_summary_sha256",None)
    actual=hashlib.sha256(json.dumps(y,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    if actual!=claimed:raise RuntimeError(f"{trial_id}: deterministic hash mismatch")

def h1_review(x:dict[str,Any])->dict[str,Any]:
    out={}
    for feat in H1_FEATURES:
        obs=[];pairs=[];ns=[];eligible=[]
        for sp in SPLITS:
            r=x["splits"][sp][feat]
            obs.append(r["observation_weighted"]["partial_r_y_incremental_given_control"])
            pairs.append(r["equal_pair_weighted"]["median_pair_partial_r"])
            ns.append(r["complete_cases"])
            eligible.append(r["equal_pair_weighted"]["eligible_pair_count"])
        out[feat]={
            "observation_weighted_partial_r":obs,
            "equal_pair_median_partial_r":pairs,
            "complete_cases":ns,
            "eligible_pair_counts":eligible,
            "observation_sign_consistent":same_sign(obs),
            "pair_sign_consistent":same_sign(pairs)
        }
    return out

def h6_review(x:dict[str,Any])->dict[str,Any]:
    out={}
    for stratum in H6_STRATA:
        partial=[];pairs=[];effects=[];cases=[];ntrue=[];nfalse=[]
        for sp in SPLITS:
            r=x["splits"][sp][stratum]
            partial.append(r["observation_weighted"]["partial_r_y_volume_given_price"])
            pairs.append(r["equal_pair_weighted"]["median_pair_partial_r"])
            effects.append(r["simple_effect"]["true_minus_false_mean"])
            cases.append(r["coverage"]["complete_cases"])
            ntrue.append(r["coverage"]["volume_expansion_true"])
            nfalse.append(r["coverage"]["volume_expansion_false"])
        out[stratum]={
            "observation_weighted_partial_r":partial,
            "equal_pair_median_partial_r":pairs,
            "simple_true_minus_false_mean":effects,
            "complete_cases":cases,
            "volume_expansion_true_counts":ntrue,
            "volume_expansion_false_counts":nfalse,
            "observation_partial_sign_consistent":same_sign(partial),
            "pair_partial_sign_consistent":same_sign(pairs),
            "simple_effect_sign_consistent":same_sign(effects)
        }
    return out

def review(h1p:Path,h6p:Path)->dict[str,Any]:
    h1=json.loads(h1p.read_text("utf-8"))
    h6=json.loads(h6p.read_text("utf-8"))
    require_base(h1,"V3-H1-INCR-001","V3_H1_INCREMENTAL_RELATIVE_CONTEXT_RESULT_V1")
    require_base(h6,"V3-H6-INCR-001","V3_H6_INCREMENTAL_VOLUME_CONTRIBUTION_RESULT_V1")
    return {
      "schema_version":1,
      "kind":"V3_H1_H6_INCREMENTAL_FIXED_REVIEW_V1",
      "status":"PASS_FIXED_DESCRIPTIVE_REVIEW_HOLDOUT_SEALED",
      "source_reports":{
        "h1":{"filename":h1p.name,"file_sha256":file_sha(h1p),"summary_sha256":h1["deterministic_summary_sha256"]},
        "h6":{"filename":h6p.name,"file_sha256":file_sha(h6p),"summary_sha256":h6["deterministic_summary_sha256"]}
      },
      "fixed_split_order":list(SPLITS),
      "h1":h1_review(h1),
      "h6":h6_review(h6),
      "governance":{
        "search_accounted_trials":["V3-H1-INCR-001","V3-H6-INCR-001"],
        "parent_results_influenced_design":True,
        "threshold_search_performed":False,
        "feature_or_stratum_search_performed":False,
        "p_value_selection_performed":False,
        "holdout_opened":False,
        "automatic_winner_selected":False,
        "automatic_shadow_candidate_selected":False,
        "automatic_strategy_promotion":False,
        "orders":False,
        "real_money_actions":False
      },
      "interpretation":{
        "descriptive_incremental_effect_review_only":True,
        "sign_consistency_is_not_a_promotion_criterion":True,
        "no_winner_is_valid_outcome":True,
        "next_decision":"HUMAN_PROJECT_REVIEW_OF_FIXED_EFFECT_SIZES_VERSUS_EXISTING_EVIDENCE_BEFORE_ANY_ONE_CHANGE_SHADOW_MATERIALIZATION"
      }
    }

def self_test()->int:
    assert same_sign([.1,.2,.3]) is True
    assert same_sign([-.1,-.2,-.3]) is True
    assert same_sign([-.1,.2,-.3]) is False
    assert same_sign([-.1,None,-.3]) is None
    print("V3_H1_H6_INCREMENTAL_REVIEW_SELFTEST PASS fixed-sign/no-selection")
    return 0

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("h1",type=Path,nargs="?")
    ap.add_argument("h6",type=Path,nargs="?")
    ap.add_argument("--output",type=Path)
    ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test:return self_test()
    if not a.h1 or not a.h6:raise SystemExit("h1 and h6 reports required")
    out=review(a.h1,a.h6)
    raw=json.dumps(out,indent=2,sort_keys=True)+"\n"
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(raw,"utf-8")
    print("V3_H1_H6_INCREMENTAL_REVIEW "+json.dumps(out,sort_keys=True,separators=(",",":")))
    return 0

if __name__=="__main__":raise SystemExit(main())
