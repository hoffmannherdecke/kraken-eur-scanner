#!/usr/bin/env python3
"""Validate ownership, overlap, safe consequence routing and present control-plane safety.

Offline only; no API, no orders, no secrets, no runtime mutation.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT/"research/monitoring-evidence-routing-v1.json"
ALLOWED_CONSUMERS={
    "SCANNER_AND_PAPER","GATED_STRATEGY_REVIEW","V3_FIXED_REVIEW",
    "V3_ONE_CHANGE_GATE","SOURCE_STEWARD_REVIEW","OPS_REMEDIATE_ESCALATE",
    "REVIEW_READINESS_ONLY","INACTIVE_TRIAL_OR_DISPOSITION"
}
ALLOWED_AUTHORITIES={
    "EXISTING_OPERATIONAL_HARD_GATE","EXISTING_FROZEN_STRATEGY",
    "RESEARCH_ONLY","REJECTED_STANDALONE_ONLY","OPERATIONS_ONLY",
    "CONTROL_PLANE_ONLY","REVIEW_ONLY","EVIDENCE_ONLY"
}
MANDATORY={
 "kraken_tradability","kraken_eur_price","scanner_detection","paper_lifecycle",
 "productivity_missed_moves","realtime_timing","market_regime",
 "h1_breadth_diagnostic","global_market_crosscheck","news_event_context",
 "source_quality","milestone_controller","gated_strategy_analysis",
 "health_watchdog","storage_and_cost","delivery_notifications"
}|{f"{key}_h{i}" for i,key in enumerate(
  ("derivatives","orderflow","stop_ttl","macro","price_volume",
   "meta","onchain","execution","smartmoney","prediction"),start=2)}
# H2 through H11: each hypothesis must have exactly one owner record.
# No implied authority for a research/observational stream.
OVERLAP_CRITICAL={
 frozenset(("market_regime","h1_breadth_diagnostic")),
 frozenset(("market_regime","global_market_crosscheck")),
 frozenset(("macro_h5","news_event_context")),
 frozenset(("macro_h5","prediction_h11")),
 frozenset(("orderflow_h3","execution_h9")),
 frozenset(("onchain_h8","smartmoney_h10")),
 frozenset(("scanner_detection","realtime_timing")),
}

def validate(j:dict, state:dict)->list[str]:
    errs=[]
    if j.get("schema_version")!=1 or j.get("kind")!="MONITORING_EVIDENCE_ROUTING_V1":
        errs.append("unexpected evidence topology schema")
    for field,value in {
        "source_quality_scoring_is_trading_authority":False,
        "optional_source_failures_can_block_buy":False,
        "automatic_strategy_promotion":False,
        "automatic_real_money_actions":False,
        "work_gate_from_observation":False,
        "requires_point_in_time_for_research":True,
        "one_strategy_changing_shadow_max":1,
        "current_status_authority":"project-current-state.json"
    }.items():
        if j.get(field)!=value: errs.append("safety invariant changed: "+field)
    xs=j.get("streams")
    if not isinstance(xs,list):
        return errs+["streams missing"]
    ids=[s.get("id") for s in xs if isinstance(s,dict)]
    if len(ids)!=len(xs):errs.append("non-object stream")
    if len(ids)!=len(set(ids)):errs.append("duplicate stream owner id")
    unknown=MANDATORY-set(ids)
    if unknown:errs.append("missing coverage "+",".join(sorted(unknown)))
    facts=set()
    mapping={s.get("id"):s for s in xs if isinstance(s,dict)}
    for s in xs:
        if not isinstance(s,dict): continue
        ident=str(s.get("id") or "")
        if not re.fullmatch(r"[a-z][a-z0-9_]*",ident):errs.append("bad stream id "+ident)
        for field in ("role","canonical_owner","evidence_status","fact_key","evidence_outcome"):
            if not str(s.get(field) or "").strip():errs.append(ident+": missing "+field)
        if s.get("consumer") not in ALLOWED_CONSUMERS:errs.append(ident+": bad consumer")
        if s.get("authority") not in ALLOWED_AUTHORITIES:errs.append(ident+": bad authority")
        fact=s.get("fact_key")
        if fact in facts:errs.append(ident+": two authorities for fact "+str(fact))
        facts.add(fact)
        refs=s.get("overlaps")
        if not isinstance(refs,list): errs.append(ident+": overlap list missing");continue
        for o in refs:
            if o not in mapping or o==ident:errs.append(ident+": unknown/self overlap "+str(o))
        if len(refs)!=len(set(refs)):errs.append(ident+": duplicate overlap")
        optional=s.get("optional_research")
        if type(optional) is not bool:errs.append(ident+": optional_research not boolean")
        if optional:
            if s.get("on_missing")!="UNKNOWN_NO_VETO":errs.append(ident+": missing optional feed can veto")
            if s.get("authority") in {"EXISTING_OPERATIONAL_HARD_GATE","EXISTING_FROZEN_STRATEGY","CONTROL_PLANE_ONLY"}:
                errs.append(ident+": optional source illegally claims hard decision authority")
            if s.get("source_known_at_required") is not True:
                errs.append(ident+": optional PIT requirement disabled")
            if s.get("strategy_change_requires_release") is not True:
                errs.append(ident+": optional strategy change bypasses release")
        if s.get("consumer")=="OPS_REMEDIATE_ESCALATE" and s.get("authority") not in {"OPERATIONS_ONLY"}:
            errs.append(ident+": operations cannot rewrite strategies")
        if s.get("consumer")=="SOURCE_STEWARD_REVIEW" and s.get("authority")!="RESEARCH_ONLY":
            errs.append(ident+": source quality can become trade authority")
    for pair in OVERLAP_CRITICAL:
        if not any(other in mapping.get(stream,{}).get("overlaps",[]) for stream in pair for other in pair if other!=stream):
            errs.append("missing critical duplication disclosure "+str(sorted(pair)))
    h1=mapping.get("h1_breadth_diagnostic",{})
    if h1.get("authority")!="REJECTED_STANDALONE_ONLY":
        errs.append("H1 standalone has been improperly reactivated")
    if mapping.get("market_regime",{}).get("evidence_status")=="VERIFIED_HISTORICALLY":
        errs.append("unattended regime proof was presumed rather than evidenced")
    if state.get("active_strategy",{}).get("real_money_actions") is not False:
        errs.append("current strategy authority unexpectedly enables real money")
    shadows=state.get("strategy_changing_shadow_wip",{}).get("active",[])
    if len(shadows)>1:errs.append("current state has simultaneous decision shadows")
    if any(sh.get("candidate_id")=="V3-H1-SHADOW-001" for sh in shadows):
        errs.append("H1 was reopened")
    return errs

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--registry",type=Path,default=DEFAULT)
    ap.add_argument("--state",type=Path,default=ROOT/"project-current-state.json")
    args=ap.parse_args()
    j=json.loads(args.registry.read_text(encoding="utf-8"))
    state=json.loads(args.state.read_text(encoding="utf-8"))
    errors=validate(j,state)
    print(json.dumps({"kind":"MONITORING_EVIDENCE_ROUTING_GUARD_V1",
       "status":"PASS" if not errors else "FAIL",
       "streams":len(j.get("streams",[])),
       "errors":errors,
       "orders":False,"real_money_actions":False},sort_keys=True))
    return 0 if not errors else 2

if __name__=="__main__":
    raise SystemExit(main())
