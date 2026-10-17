#!/usr/bin/env python3
"""Bounded safe-work selector for existing Work Phase 1 (offline, no side effects).

Does not mutate files, GitHub, Supabase, Work, any strategy or account.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
try:
    from tools.project_followthrough_router import v3_five_source_followthrough, project_implementation_commitments, historical_backlog_reconciliation
except ModuleNotFoundError:
    from project_followthrough_router import v3_five_source_followthrough, project_implementation_commitments, historical_backlog_reconciliation
import datetime as dt

ROOT=Path(__file__).resolve().parents[1]
SUPPORTED_CONTROL={"V3-H3-ARCHIVE-DISPOSITION","V2R4-PRODUCTIVITY-REVIEW",
                   "V3-EXTENDED-SECOND-LEG-LEARNING-GATE"}
ID_TO_GATE={
 "H10_PROSPECTIVE_JOIN_CONTRACT":"H10_FIRST_REVIEW_COMPLETE_AND_CONTRACT_ABSENT",
 "UNKNOWN_CONTROL_DECISION_ADAPTER":"UNSUPPORTED_NEXT_CONTROL_DECISION",
 "UNKNOWN_SHADOW_ADAPTER":"UNKNOWN_ACTIVE_SHADOW_ADAPTER",
 "MINIPC_ANALYTICS_READONLY_PREP":"APPROVED_MINIPC_ANALYTICS_PLAN_AND_MISSING_INACTIVE_REUSE_PREP",
 "V3_PAPER_FIVE_SOURCE_FOLLOWTHROUGH":"REAL_V3_PAPER_ACTIVE_AND_POST_CUTOVER_SOURCE_E2E_WORK_OPEN",
 "PROJECT_WIDE_COMMITMENT_SAFE_WORK":"REGISTERED_PROJECT_COMMITMENT_WITH_SAFE_EVIDENCE_GATE_READY",
 "HISTORICAL_BACKLOG_RECONCILIATION":"HISTORIC_UNDISPOSED_CHECKBOX_REQUIRES_REAL_OWNER_AND_GATE",
}
EFFECTS={"READ_ONLY_EVIDENCE_REVIEW","RESEARCH_ONLY_CONTRACT","VERSIONED_TESTS","DOCUMENTATION","NON_RUNTIME_PR"}
FORBIDDEN={"TRADE_OR_ORDER","PRIVILEGE_OR_SECRET_CHANGE","FROZEN_STRATEGY_CHANGE",
 "RUNTIME_TRIGGER_OR_THRESHOLD_CHANGE","SHADOW_START_OR_PROMOTION","LIVE_RELEASE",
 "DATA_DESTRUCTION","NEW_SCHEDULER"}

def verified_completed_work_receipt(root: Path, receipt: dict) -> bool:
    """Trust a COMPLETED slot only with an actual local SHA-256-pinned report.

    This verifies the repository artifact, NOT a remote PR merge, physical
    deployment, Cloud upload, a V3 model decision or a strategy release.
    Other independent gates must still check their own original evidence.
    """
    if not isinstance(receipt, dict) or receipt.get("status") != "COMPLETED":
        return False
    report, digest = receipt.get("report"), receipt.get("report_sha256")
    completed, reason = receipt.get("completed_at_utc"), receipt.get("reason")
    if (not isinstance(report, str) or not report.startswith("research/work-analysis/")
            or "\\" in report or not isinstance(digest, str)
            or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest)
            or not isinstance(completed, str) or not isinstance(reason, str)
            or not reason.strip()):
        return False
    try:
        at = dt.datetime.fromisoformat(completed.replace("Z", "+00:00"))
        if at.tzinfo is None or at.utcoffset() is None:
            return False
        file = (root / report).resolve()
        base = root.resolve()
        if not file.is_relative_to(base) or not file.is_file():
            return False
        if file.stat().st_size > 2_000_000:
            return False
        return hashlib.sha256(file.read_bytes()).hexdigest() == digest
    except (OSError, ValueError, TypeError):
        return False


def select(root:Path, queue:dict, state:dict, ack:dict|None=None)->dict:
    errs=[]
    if queue.get("kind")!="SAFE_AUTONOMOUS_IMPLEMENTATION_QUEUE_V1" or queue.get("schema_version")!=1:
        errs.append("invalid queue kind/version")
    if queue.get("status_authority")!="project-current-state.json" or queue.get("no_orphan_requirement") is not True:
        errs.append("wrong autonomy/control-plane authority")
    if (queue.get("max_concurrent_active_work_packages")!=2
            or queue.get("max_concurrent_implementation_branches")!=1
            or queue.get("work_run_rule")!=
            "EXISTING_DAILY_WORK_ONLY_CHEAP_PRECHECK_MAX_TWO_ACTIVE_EVIDENCED_REFILL"):
        errs.append("unsafe concurrent work limits")
    # Existing Work owns the start/finish receipts; this selector never
    # creates tasks or PRs. A started package occupies a slot until an
    # evidenced completion or exact foreign/approval gate releases it.
    attempts=(ack or {}).get("autonomy_task_attempts",{})
    if not isinstance(attempts,dict):
        errs.append("invalid work attempt ledger")
        attempts={}
    active_work_packages=sorted(
        key for key,receipt in attempts.items()
        if isinstance(key,str) and isinstance(receipt,dict)
        and receipt.get("status") in ("IN_PROGRESS","ACTIVE_PR"))
    active_pr_count=sum(
        isinstance(receipt,dict) and receipt.get("status")=="ACTIVE_PR"
        for receipt in attempts.values())
    if len(active_work_packages)>2 or active_pr_count>1:
        errs.append("overcommitted active work / implementation PR")
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
    # Existing 10:15 Work alone executes bounded safe implementation;
    # physical Cloud-verified V3 release is mandatory before followthrough.
    source_gate={"status":"WAIT_FOR_REAL_V3_PAPER_CUTOVER","open_roles":[]}
    # No manifest read/cost for ordinary V2R4 or offline research fixtures.
    # The existing Work route validates the five-role contract itself.
    transition=state.get("pending_strategy_transition") or {}
    active=state.get("active_strategy") or {}
    if (str(active.get("strategy_revision") or "").startswith("V3-")
            and transition.get("status")=="V3_PAPER_ACTIVE_VERIFIED"
            and (transition.get("verified_cutover_evidence") or {}).get(
                "mini_pc_and_single_active_supabase_series_ack") is True):
        source_gate=v3_five_source_followthrough(
            root,state,ack or {},dt.datetime.now(dt.timezone.utc))
        if source_gate["status"]=="SOURCE_WORK_OPEN":
            open_work.append("V3_PAPER_FIVE_SOURCE_FOLLOWTHROUGH")
    # All accepted future commitments are checked via ONE existing
    # routing manifest; safe work is dynamically selected, not an ID-specific
    # hotfix that leaves the next user commitment invisible.
    # Only the real canonical root (or explicit full fixture) can request
    # these tasks. Minimal unrelated offline selector fixtures stay isolated.
    available=[]
    if all((root/p).is_file() for p in (
        "research/project-followthrough-routing-v1.json",
        "research/monitoring-evidence-routing-v1.json","PROJECT_BACKLOG.md")):
        registered=project_implementation_commitments(
            root,state,ack or {},dt.datetime.now(dt.timezone.utc))
        available=registered["ready_safe_actions"]
    attempts=((ack or {}).get("autonomy_task_attempts") or {})
    selected_obligation=None
    selected_attempt_key=None
    selected_gate_fp=None
    for item in available:
        # Distinct Work attempt identity per original registered obligation:
        # a blocked V3 evidence gate cannot starve unrelated safe obligations.
        key="PROJECT_WIDE_COMMITMENT_SAFE_WORK:"+item["id"]
        fp=hashlib.sha256(json.dumps({
            "obligation":item["id"],
            "trigger":item["trigger"],
            "strategy":(state.get("active_strategy") or {}).get("strategy_revision"),
            "series":(state.get("active_strategy") or {}).get("series_id"),
            "state":item["state"]},sort_keys=True).encode()).hexdigest()[:20]
        previous=attempts.get(key)
        if (isinstance(previous, dict)
                and previous.get("gate_fingerprint") == fp
                and previous.get("status") == "COMPLETED"
                and not verified_completed_work_receipt(root, previous)):
            errs.append("unverified completion receipt " + key)
        if not (isinstance(previous,dict)
                and previous.get("gate_fingerprint")==fp
                and previous.get("status") in ("BLOCKED","ACTIVE_PR","COMPLETED")):
            selected_obligation=item
            selected_attempt_key=key
            selected_gate_fp=fp
            break
    if selected_obligation:
        open_work.append("PROJECT_WIDE_COMMITMENT_SAFE_WORK")
    legacy_next=[]
    if (root/"research/project-followthrough-routing-v1.json").is_file() and (root/"PROJECT_BACKLOG.md").is_file():
        legacy=historical_backlog_reconciliation(
            root,ack or {},dt.datetime.now(dt.timezone.utc))
        legacy_next=legacy["next_review"]
        if legacy_next:
            open_work.append("HISTORICAL_BACKLOG_RECONCILIATION")
    digest=hashlib.sha256(json.dumps({
        "v3_source_followthrough":source_gate["open_roles"],
        "v3_source_status":source_gate["status"],
        "commitment_ready_ids":[x["id"] for x in available],
        "legacy_next_ids":[x["id"] for x in legacy_next],
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
    ready=[]
    blocked_attempts=[]
    for tid in open_work:
        record=attempts.get(tid)
        if isinstance(record,dict) and record.get("gate_fingerprint")==digest and record.get("status") in {"BLOCKED","ACTIVE_PR","COMPLETED"}:
            if (record["status"] == "COMPLETED"
                    and not verified_completed_work_receipt(root, record)):
                errs.append("unverified completion receipt " + tid)
            blocked_attempts.append({"id":tid,"status":record["status"],
                                     "local_report_sha256_verified":
                                         record["status"] == "COMPLETED"})
            continue
        ready.append(next(x for x in tasks if x["id"]==tid))
    if errs:
        # Never free a capacity slot from an unsupported "COMPLETED" label.
        # Work must reconcile its existing receipt with the original artifact.
        return {"kind":"AUTONOMOUS_IMPLEMENTATION_GATE_V1","status":"BLOCKED",
                "errors":errs,"ready":[],"safe_work_requested":False,
                "strategy_changed":False,"orders":False,
                "real_money_actions":False}
    ready.sort(key=lambda x:(x["priority"],x["id"]))
    # Return no more than the free *concurrent* slots. Work must re-run
    # this cheap selector after each real ACK in the SAME allowed 10:15 run;
    # no fixed two-per-run truncation or automatic infinite loop exists here.
    free_slots=max(0,queue["max_concurrent_active_work_packages"]-
                   len(active_work_packages))
    waiting_due=[{"id":x["id"],"gate":x["gate"],"source_ref":x["source_ref"],
                  "wait_reason":"ACTIVE_PACKAGE_CAPACITY"}
                 for x in ready[free_slots:]]
    ready=[{"id":x["id"],"action":x["action"],"target":x["target"],
            "gate":x["gate"],"evidence":x["evidence"],"allowlist":x["allowlist"],
            "source_ref":x["source_ref"],"proof_of_completion":x["proof_of_completion"],
            "gate_fingerprint":selected_gate_fp if x["id"]==
                    "PROJECT_WIDE_COMMITMENT_SAFE_WORK" else digest,
            "attempt_key":selected_attempt_key if x["id"]==
                    "PROJECT_WIDE_COMMITMENT_SAFE_WORK" else x["id"],
            "registered_obligation":selected_obligation if x["id"]==
                    "PROJECT_WIDE_COMMITMENT_SAFE_WORK" else None,
            "legacy_backlog_review":legacy_next if x["id"]==
                    "HISTORICAL_BACKLOG_RECONCILIATION" else []}
            for x in ready[:free_slots]]
    return {"kind":"AUTONOMOUS_IMPLEMENTATION_GATE_V1","status":"READY_SAFE_WORK" if ready else "NO_SAFE_WORK",
            "fingerprint":digest,"open_work_count":len(open_work),"ready":ready,
            "active_work_package_count":len(active_work_packages),
            "active_work_package_ids":active_work_packages,
            "active_implementation_pr_count":active_pr_count,
            "max_concurrent_active_work_packages":2,
            "max_concurrent_implementation_branches":1,
            "waiting_due":waiting_due,
            "waiting_registered_obligations":[
                {"id":x["id"],"owner":x["owner"],"trigger":x["trigger"],
                 "state":x["state"],"priority":x["priority"]}
                for x in available if not selected_obligation or
                x["id"]!=selected_obligation["id"]],
            "refill_after_evidenced_ack_same_run":True,
            "work_must_enforce_existing_time_cost_budget":True,
            "external_github_pr_count_must_be_verified_by_work":True,
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
