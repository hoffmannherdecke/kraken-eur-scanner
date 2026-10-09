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
        for field in ("role","canonical_owner","evidence_status","fact_key","evidence_outcome","next_gate"):
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
    source = mapping.get("source_quality",{})
    gate = source.get("activation_followthrough") or {}
    required_gates = {
        "id": "AUTONOMOUS_ACTIVE_SOURCE_MANAGEMENT_E2E_GATE_V1",
        "status": "OBSERVATION_TASK_ACTIVE_SOURCE_REVIEW_AND_REPLACE_E2E_UNVERIFIED",
        "stage_1": "VERIFY_UNATTENDED_PUBLIC_SOURCE_PILOT_IN_EXISTING_2H_RADAR_WITH_UTC_KNOWN_AT_PRIMARY_EVIDENCE_AND_FAILSOFT",
        "stage_2": "SCORE_AT_LEAST_5_INDEPENDENT_VERIFIED_RELEVANT_EVENTS_ACROSS_AT_LEAST_2_CAPTURE_WINDOWS_WITH_SOURCE_TYPE_MATCHED_BASELINE",
        "stage_3": "ONLY_EVIDENCE_BACKED_KEEP_QUARANTINE_OR_RESEARCH_ONLY_REVERSIBLE_REPLACE_VIA_EXISTING_BRANCH_PR_CI_ROLLBACK",
        "stage_4": "ROUTE_ONLY_PROVEN_INCREMENTAL_SOURCE_FACT_TO_EXISTING_V2R4_V3_V4_PLUS_ONE_CHANGE_ECONOMIC_STRATEGY_REVIEW",
        "open_item": "PROJECT_BACKLOG.md: Autonomes Marktquellen-Controlling",
        "source_catalog": "research/market-source-candidates-v1.json",
        "source_registry": "research/source-registry.json",
        "stage_0": "PROACTIVELY_DISCOVER_NOT_YET_CATALOGUED_SOURCES_AND_CATEGORY_COVERAGE_GAPS_WITHIN_EXISTING_MONITOR_CADENCE",
        "discovery_window": "EXISTING_MON_08_10_UTC_RADAR_WINDOW_AND_MATERIAL_UNCOVERED_EVENTS_ONLY",
        "discovery_selection": "AT_MOST_ONE_GENUINELY_NEW_PUBLIC_CANDIDATE_PER_WEEK_PLUS_REVIEW_AT_MOST_TWO_EXISTING_PILOTS_AND_TWO_CHALLENGERS_WITHOUT_MORE_NEWS_READS",
    }
    for key, expected in required_gates.items():
        if gate.get(key) != expected:
            errs.append("source quality activation handoff missing or drifted: " + key)
    for key, expected in {
        "no_new_schedule": True,
        "no_new_work_run": True,
        "no_trading_or_runtime_source_replacement": True,
        "no_automatic_strategy_rule_change": True,
        "no_automatic_real_money_action": True,
        "source_quality_not_equal_to_trade_profit": True,
        "active_management_not_limited_to_static_27_catalog": True,
        "source_retirement_is_research_only_and_reversible": True,
        "management_run_evidence_not_yet_proven": True,
        "require_prospective_net_trade_impact_before_strategy_use": True,
    }.items():
        if gate.get(key) is not expected:
            errs.append("source quality activation cannot bypass safety: " + key)
    required_management = [
        "DISCOVER_UNKNOWN_SOURCE", "VERIFY_LEGAL_FREE_PUBLIC_ACCESS",
        "VERIFY_UNATTENDED_TIMESTAMPED_DATA", "ASSESS_PRIMARY_ACCURACY",
        "COMPARE_INCREMENTAL_LEADTIME_AND_REDUNDANCY", "ASSESS_COST_ACCESS_STABILITY",
        "KEEP_OR_RESEARCH_PROMOTE", "QUARANTINE_OR_RESEARCH_RETIRE",
        "REPLACE_WITH_BETTER_CHALLENGER", "PERIODICALLY_REVALIDATE",
        "HAND_OFF_MATERIAL_FINDINGS_TO_EXISTING_STRATEGY_GATE",
    ]
    if gate.get("active_management_actions") != required_management:
        errs.append("source stewardship must cover autonomous discovery, maintenance, disposal and learning")
    h3stream = mapping.get("orderflow_h3", {})
    if h3stream.get("evidence_status") != "H3_001_ARCHIVED_INCOMPLETE_0_PROSPECTIVE_CLOUD_ROWS":
        errs.append("monitor evidence registry claims stale active H3")
    if mapping.get("price_volume_h6", {}).get("evidence_status") != "BLOCKED_H3_001_ARCHIVE_DISPOSITION_PENDING":
        errs.append("monitor evidence registry falsely promotes H6")
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
