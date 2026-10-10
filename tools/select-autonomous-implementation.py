#!/usr/bin/env python3
"""Bounded safe-work selector for existing Work Phase 1 (offline, no side effects).

Does not mutate files, GitHub, Supabase, Work, any strategy or account.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SUPPORTED_CONTROL={"V3-H3-ARCHIVE-DISPOSITION","V2R4-PRODUCTIVITY-REVIEW",
                   "V3-EXTENDED-SECOND-LEG-LEARNING-GATE"}
ID_TO_GATE={
 "H10_PROSPECTIVE_JOIN_CONTRACT":"H10_FIRST_REVIEW_COMPLETE_AND_CONTRACT_ABSENT",
 "UNKNOWN_CONTROL_DECISION_ADAPTER":"UNSUPPORTED_NEXT_CONTROL_DECISION",
 "UNKNOWN_SHADOW_ADAPTER":"UNKNOWN_ACTIVE_SHADOW_ADAPTER",
 "MINIPC_ANALYTICS_READONLY_PREP":"APPROVED_MINIPC_ANALYTICS_PLAN_AND_MISSING_INACTIVE_REUSE_PREP",
}
EFFECTS={"READ_ONLY_EVIDENCE_REVIEW","RESEARCH_ONLY_CONTRACT","VERSIONED_TESTS","DOCUMENTATION","NON_RUNTIME_PR"}
FORBIDDEN={"TRADE_OR_ORDER","PRIVILEGE_OR_SECRET_CHANGE","FROZEN_STRATEGY_CHANGE",
 "RUNTIME_TRIGGER_OR_THRESHOLD_CHANGE","SHADOW_START_OR_PROMOTION","LIVE_RELEASE",
 "DATA_DESTRUCTION","NEW_SCHEDULER"}

def select(root:Path, queue:dict, state:dict, ack:dict|None=None)->dict:
    errs=[]
    if queue.get("kind")!="SAFE_AUTONOMOUS_IMPLEMENTATION_QUEUE_V1" or queue.get("schema_version")!=1:
        errs.append("invalid queue kind/version")
    if queue.get("status_authority")!="project-current-state.json" or queue.get("no_orphan_requirement") is not True:
        errs.append("wrong autonomy/control-plane authority")
    if queue.get("max_safe_actions_per_open_work_run")!=2 or queue.get("max_concurrent_implementation_branches")!=1:
        errs.append("unsafe work limits")
    if set(queue.get("allowed_effects") or [])!=EFFECTS or set(queue.get("forbidden_effects") or [])!=FORBIDDEN:
        errs.append("safe authority scope drift")
    if state.get("kind")!="PROJECT_CURRENT_STATE_V1" or (state.get("active_strategy") or {}).get("real_money_actions") is not False:
        errs.append("current state invalid/not paper")
    if (state.get("active_strategy") or {}).get("automatic_activation_allowed") is not False:
        errs.append("automatic activation authority drift")
    shadows=(state.get("strategy_changing_shadow_wip") or {}).get("active") or []
    if len(shadows)>1:
        errs.append("multiple active strategy-changing shadows")
    tasks=queue.get("tasks") or []
    ids=[x.get("id") for x in tasks]
    if len(ids)!=len(set(ids)) or set(ids)!=set(ID_TO_GATE):
        errs.append("unreviewed/duplicate safe tasks")
    for x in tasks:
        tid=x.get("id")
        if tid not in ID_TO_GATE:continue
        if x.get("gate")!=ID_TO_GATE[tid] or x.get("status")!="APPROVED_SAFE_SCOPE":
            errs.append("unapproved task gate/status "+tid)
        if x.get("owner")!="EXISTING_WORK_SAFE_IMPLEMENTATION":
            errs.append("unapproved executor "+tid)
        if not x.get("target") or not x.get("source_ref") or not x.get("allowlist") or not x.get("limits"):
            errs.append("task scope/provenance missing "+tid)
        if not x.get("proof_of_completion") or not x.get("action"):
            errs.append("task has no completion/decision "+tid)
    if errs:
        return {"kind":"AUTONOMOUS_IMPLEMENTATION_GATE_V1","status":"BLOCKED","errors":errs,
                "ready":[],"safe_work_requested":False,"strategy_changed":False,"orders":False,
                "real_money_actions":False}
    open_work=[]
    tracks=state.get("observational_research_tracks") or []
    h10=next((x for x in tracks if x.get("id")=="V3-H10-CAPTURE-001"),None)
    if (h10 and "FIRST_REVIEW_COMPLETE" in str(h10.get("status")) and
            not (root/"research/v3/h10-kraken-outcome-context-join-contract-v1.json").exists()):
        open_work.append("H10_PROSPECTIVE_JOIN_CONTRACT")
    next_ids=[x.get("id") for x in state.get("next_control_decisions") or []]
    if any(t not in SUPPORTED_CONTROL for t in next_ids):
        open_work.append("UNKNOWN_CONTROL_DECISION_ADAPTER")
    if any(x.get("candidate_id")!="V3-H3-SHADOW-001" for x in shadows):
        open_work.append("UNKNOWN_SHADOW_ADAPTER")
    # Pre-authorized Mini-PC work is a SINGLE, NON-RUNTIME research-prep task.
    # Existing 10:15 Work consumes this deterministic gate; the plan alone is not execution.
    mini_plan=root/"docs/minipc-analytics-rollout-v1.md"
    mini_backlog=root/"PROJECT_BACKLOG.md"
    mini_target=root/"research/v3/minipc-analytics-readonly-reuse-preflight-v1.md"
    mini_plan_ready=(mini_plan.is_file() and mini_backlog.is_file()
        and "PLAN_APPROVED_PREP_ONLY" in mini_plan.read_text(encoding="utf-8")
        and "MINIPC_ANALYTICS_ROLLOUT_V1" in mini_backlog.read_text(encoding="utf-8"))
    if mini_plan_ready and not mini_target.exists():
        open_work.append("MINIPC_ANALYTICS_READONLY_PREP")
    digest=hashlib.sha256(json.dumps({
        "strategy_revision":(state.get("active_strategy") or {}).get("strategy_revision"),
        "series_id":(state.get("active_strategy") or {}).get("series_id"),
        "shadow":[x.get("candidate_id") for x in shadows],
        "next_control_decisions":next_ids,
        "h10_review_status":h10.get("status") if h10 else None,
        "h10_contract_present":(root/"research/v3/h10-kraken-outcome-context-join-contract-v1.json").exists(),
        "mini_plan_ready":mini_plan_ready,
        "mini_preflight_present":mini_target.exists(),
        "open_work":open_work
    },sort_keys=True).encode()).hexdigest()[:20]
    attempts=((ack or {}).get("autonomy_task_attempts") or {})
    ready=[]
    blocked_attempts=[]
    for tid in open_work:
        record=attempts.get(tid)
        if isinstance(record,dict) and record.get("gate_fingerprint")==digest and record.get("status") in {"BLOCKED","ACTIVE_PR","COMPLETED"}:
            blocked_attempts.append({"id":tid,"status":record["status"]})
            continue
        ready.append(next(x for x in tasks if x["id"]==tid))
    ready.sort(key=lambda x:(x["priority"],x["id"]))
    ready=[{"id":x["id"],"action":x["action"],"target":x["target"],
            "gate":x["gate"],"evidence":x["evidence"],"allowlist":x["allowlist"],
            "source_ref":x["source_ref"],"proof_of_completion":x["proof_of_completion"],
            "gate_fingerprint":digest} for x in ready[:queue["max_safe_actions_per_open_work_run"]]]
    return {"kind":"AUTONOMOUS_IMPLEMENTATION_GATE_V1","status":"READY_SAFE_WORK" if ready else "NO_SAFE_WORK",
            "fingerprint":digest,"open_work_count":len(open_work),"ready":ready,
            "suppressed_prior_attempts":blocked_attempts,"safe_work_requested":bool(ready),
            "strategy_changed":False,"orders":False,"real_money_actions":False}

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=ROOT)
    p.add_argument("--queue",type=Path)
    p.add_argument("--state",type=Path)
    p.add_argument("--ack",type=Path)
    args=p.parse_args()
    base=args.root
    j=json.loads((args.queue or base/"research/autonomous-implementation-queue-v1.json").read_text("utf-8"))
    state=json.loads((args.state or base/"project-current-state.json").read_text("utf-8"))
    path=args.ack or base/"research/work-analysis-state.json"
    ack=json.loads(path.read_text("utf-8")) if path.exists() else {}
    out=select(base,j,state,ack)
    print(json.dumps(out,ensure_ascii=False,sort_keys=True))
    return 0 if out["status"]!="BLOCKED" else 2

if __name__=="__main__":
    raise SystemExit(main())
