#!/usr/bin/env python3
"""Project-wide, read-only Work handoff: route every registered stream and due decision.

No network calls, no state mutation, no strategy execution and no task scheduling.
Run in the EXISTING daily Work phase 1; scheduled GitHub controller stays the watchdog.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc
SAFE_STATUSES = {"COMPLETED", "DECISION_PACKET_READY", "BLOCKED_WITH_ACTION"}
RELEASE_DENY = {"ACTIVE_STRATEGY_OR_EXECUTION", "PAPER_OR_SHADOW_ACTIVATION",
                "H3_H6_PROMOTION", "KRAKEN_ORDER_PERMISSION_OR_REAL_MONEY",
                "SECRETS_OR_NEW_PRIVILEGES", "PAID_SERVICE_OR_BUDGET",
                "IRREVERSIBLE_CHANGE"}


def require(value: bool, reason: str) -> None:
    if not value:
        raise ValueError("FAIL_CLOSED: " + reason)


def read_json(root: Path, name: str) -> dict:
    return json.loads((root / name).read_text(encoding="utf-8"))


def utc(value: str) -> dt.datetime:
    stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(stamp.tzinfo is not None, "timestamp must carry offset")
    return stamp.astimezone(UTC)


def valid_receipt(root: Path, reviews: dict, key: str, due: dt.datetime, now: dt.datetime) -> bool:
    receipt = reviews.get(key)
    if not isinstance(receipt, dict) or receipt.get("status") not in SAFE_STATUSES:
        return False
    report = receipt.get("report")
    completed = receipt.get("completed_at_utc")
    if not (isinstance(report, str)
            and re.fullmatch(r"research/work-analysis/[A-Za-z0-9_.-]+[.]md", report)
            and isinstance(completed, str)):
        return False
    try:
        completion = utc(completed)
    except (ValueError, TypeError):
        return False
    return due <= completion <= now and (root / report).is_file()


# The daily existing Work route is the executor handoff, not itself an executor.
# Documentary ACKs need original owner+consumer references; these are not a
# substitute for an independent Supabase/physical Mini-PC readback.
SOURCE_ACK = "OWNER_TO_V3_CONSUMER_E2E_REVIEWED"
STEWARD_ACK = "UNATTENDED_RESEARCH_STEWARD_E2E_REVIEWED"


def v3_five_source_followthrough(root: Path, state: dict, ack: dict,
                                now: dt.datetime) -> dict:
    manifest=read_json(root, "research/project-followthrough-routing-v1.json")
    plan=manifest.get("v3_paper_five_source_followthrough") or {}
    require(plan.get("kind") ==
            "V3_PAPER_FIVE_OPTIONAL_SOURCE_POST_CUTOVER_FOLLOWTHROUGH_V1"
            and plan.get("owner") == "EXISTING_DAILY_1015_WORK_ONCE_PER_GATE"
            and plan.get("watcher") ==
                "EXISTING_AUTONOMOUS_PROJECT_MILESTONE_CONTROLLER"
            and plan.get("trigger") ==
                "ONLY_AFTER_V3_PAPER_ACTIVE_VERIFIED_WITH_PHYSICAL_SINGLE_WRITER_CLOUD_ACK"
            and plan.get("action_budget_per_work_run") == 2,
            "missing original five-source Work followthrough contract")
    for key in ("fail_open_optional_context","does_not_block_v3_paper_start",
                "no_new_scheduler","no_source_runtime_replacement",
                "no_orders_or_paper_promotion","no_claim_of_execution_from_queued_work"):
        require(plan.get(key) is True, "five-source safety invariant missing: "+key)
    roles=plan.get("source_roles") or []
    keys=("smart_money_h10","polymarket_h11","market_phase_radar",
          "news_sentiment","source_stewardship")
    expected_streams=("smartmoney_h10","prediction_h11","market_regime",
                      "news_event_context","source_quality")
    require(len(roles)==len(keys)
            and tuple(r.get("id") for r in roles)==keys
            and tuple(r.get("stream_id") for r in roles)==expected_streams
            and all(r.get("owner") and r.get("acceptance") for r in roles),
            "five-source role/stream mapping inconsistent")
    transition=state.get("pending_strategy_transition") or {}
    active=state.get("active_strategy") or {}
    revision=active.get("strategy_revision")
    series=active.get("series_id")
    activated=(isinstance(revision,str) and revision.startswith("V3-")
               and isinstance(series,str) and series.startswith("PAPER-V3-")
               and transition.get("status")=="V3_PAPER_ACTIVE_VERIFIED"
               and (transition.get("verified_cutover_evidence") or {}).get(
                   "mini_pc_and_single_active_supabase_series_ack") is True)
    if not activated:
        return {"kind":plan["kind"],"status":"WAIT_FOR_REAL_V3_PAPER_CUTOVER",
                "open_roles":[r["id"] for r in roles],
                "next_safe_actions":[],"acknowledged_roles":[],
                "no_paper_start_block":True,"runtime_changed":False}
    records=((ack.get("acknowledgements") or {})
             .get("v3_paper_source_e2e") or {})
    require(isinstance(records,dict),"invalid source acknowledgement ledger")
    open_roles,accepted=[],[]
    for role in roles:
        item=records.get(role["id"])
        ok=False
        if isinstance(item,dict):
            report=item.get("report")
            verified=item.get("verified_at_utc")
            digest=item.get("evidence_sha256")
            src=item.get("source_original_ref")
            consumer=item.get("consumer_original_ref")
            expected=STEWARD_ACK if role["id"]=="source_stewardship" else SOURCE_ACK
            if (item.get("status")==expected
                    and item.get("series_id")==series
                    and item.get("strategy_revision")==revision
                    and isinstance(report,str)
                    and re.fullmatch(r"research/work-analysis/[A-Za-z0-9_.-]+[.]md",report)
                    and isinstance(digest,str)
                    and re.fullmatch(r"[0-9a-f]{64}",digest)
                    and isinstance(src,str) and len(src)>10
                    and isinstance(consumer,str) and len(consumer)>10
                    and src!=consumer
                    and item.get("independent_owner_consumer_readback") is True
                    and isinstance(verified,str)):
                try:
                    stamped=utc(verified)
                    path=root/report
                    if (stamped<=now and path.is_file()
                            and hashlib.sha256(path.read_bytes()).hexdigest()==digest):
                        ok=True
                except (ValueError,OSError,TypeError):
                    pass
        (accepted if ok else open_roles).append(role["id"])
    return {"kind":plan["kind"],
            "status":"SOURCE_WORK_OPEN" if open_roles else
                     "FIVE_SOURCE_DOCUMENTARY_ACKS_RECORDED_LIVE_RECHECK_STILL_REQUIRED",
            "open_roles":open_roles,"acknowledged_roles":accepted,
            "next_safe_actions":[{"id":r["id"],"canonical_owner":r["owner"],
                                  "existing_stream":r["stream_id"],
                                  "evidence_gate":r["acceptance"],
                                  "executor":plan["owner"],
                                  "permission":"SAFE_RESEARCH_PR_OR_READONLY_ONLY"}
                                 for r in roles if r["id"] in open_roles][:
                                     plan["action_budget_per_work_run"]],
            "no_paper_start_block":True,"runtime_changed":False,
            "ack_is_documentary_not_independent_cloud_authentication":True}



# Registered *accepted* future work shares this EXISTING ownership manifest.
# Coverage of 26 streams is NOT proof that a concrete user commitment will run.
def project_implementation_commitments(root: Path, state: dict, ack: dict,
                                       now: dt.datetime) -> dict:
    manifest=read_json(root,"research/project-followthrough-routing-v1.json")
    cfg=manifest.get("project_wide_implementation_commitments") or {}
    require(cfg.get("kind")=="PROJECT_WIDE_IMPLEMENTATION_COMMITMENTS_V1"
            and cfg.get("intake_authority")=="PROJECT_BACKLOG.md"
            and cfg.get("work_executor")=="EXISTING_DAILY_1015_WORK_ONCE_PER_GATE"
            and cfg.get("milestone_watcher")==
                "EXISTING_AUTONOMOUS_PROJECT_MILESTONE_CONTROLLER"
            and cfg.get("max_concurrent_active_work_packages")==2,
            "missing canonical implementation commitment followthrough")
    for k in ("no_new_scheduler","no_auto_release",
              "acknowledgement_never_proves_physical_cloud_truth"):
        require(cfg.get(k) is True,"unsafe commitment control: "+k)
    routing=read_json(root,"research/monitoring-evidence-routing-v1.json")
    known={r.get("id") for r in routing.get("streams",[])}
    backlog=(root/"PROJECT_BACKLOG.md").read_text(encoding="utf-8")
    obligations=cfg.get("obligations")
    require(isinstance(obligations,list) and obligations,
            "no declared future commitment catalogue")
    ids=[o.get("id") for o in obligations]
    require(len(ids)==len(set(ids)) and all(isinstance(x,str) for x in ids),
            "duplicate/unregistered future commitment")
    t=state.get("pending_strategy_transition") or {}
    a=state.get("active_strategy") or {}
    physical=(str(a.get("strategy_revision") or "").startswith("V3-")
              and str(a.get("series_id") or "").startswith("PAPER-V3-")
              and t.get("status")=="V3_PAPER_ACTIVE_VERIFIED"
              and (t.get("verified_cutover_evidence") or {}).get(
                  "mini_pc_and_single_active_supabase_series_ack") is True)
    records=((ack.get("acknowledgements") or {})
             .get("project_implementation_commitments") or {})
    require(isinstance(records,dict),"invalid implementation evidence state")
    states=[]
    for ob in obligations:
        ident=ob["id"]
        require(ob.get("stream_id") in known and
                isinstance(ob.get("backlog_marker"),str) and
                ob["backlog_marker"] in backlog and
                isinstance(ob.get("owner"),str) and ob["owner"] and
                isinstance(ob.get("allowed_action"),str) and
                len(ob["allowed_action"])>=30 and
                isinstance(ob.get("completion_gate"),str) and
                len(ob["completion_gate"])>=30 and
                type(ob.get("priority")) is int and 0<=ob["priority"]<=5 and
                type(ob.get("safe_work")) is bool and
                type(ob.get("requires_user_release")) is bool,
                "future commitment missing original owner/gate/backlog backlink: "+ident)
        trigger=ob.get("trigger")
        require(trigger in ("IMMEDIATE","AFTER_CANARY_CLOCK","AFTER_V3_PAPER",
                            "AFTER_REAL_PAPER_TRADES"),
                "unknown commitment trigger "+ident)
        if trigger=="IMMEDIATE": ready=True; block=None
        elif trigger=="AFTER_CANARY_CLOCK":
            ready=now>=utc("2026-10-13T12:00:12Z")
            block=None if ready else "WAIT_ACTUAL_28H_DEADLINE_NO_PREMATURE_PASS"
        elif trigger=="AFTER_V3_PAPER":
            ready=physical
            block=None if ready else "WAIT_VERIFIED_PHYSICAL_V3_PAPER"
        else:
            ready=False
            block="WAIT_GENUINE_V3_PAPER_FILL_AND_MATURE_OUTCOME"
        item=records.get(ident)
        audited=False
        if isinstance(item,dict):
            report=item.get("report")
            proof=item.get("evidence_sha256")
            when=item.get("completed_at_utc")
            src=item.get("source_original_ref")
            consumer=item.get("consumer_original_ref")
            if (item.get("status")=="INDEPENDENT_EVIDENCE_REVIEWED"
                and isinstance(report,str) and
                re.fullmatch(r"research/work-analysis/[A-Za-z0-9_.-]+[.]md",report)
                and isinstance(proof,str) and re.fullmatch(r"[a-f0-9]{64}",proof)
                and isinstance(when,str) and isinstance(src,str)
                and isinstance(consumer,str) and src!=consumer
                and len(src)>10 and len(consumer)>10
                and item.get("independent_live_readback_confirmed") is True):
                if ident.startswith("V3_") or ident.startswith("MINIPC_"):
                    if not physical and trigger=="AFTER_V3_PAPER":
                        audited=False
                    elif trigger=="AFTER_V3_PAPER":
                        audited=(item.get("series_id")==a.get("series_id") and
                                 item.get("strategy_revision")==a.get("strategy_revision"))
                    else: audited=True
                else: audited=True
                try:
                    p=root/report
                    audited=(audited and p.is_file()
                       and utc(when)<=now and
                       hashlib.sha256(p.read_bytes()).hexdigest()==proof)
                except (OSError,TypeError,ValueError):
                    audited=False
        state_name=("DOCUMENTARY_ACK_RECORDED_VERIFY_PHYSICAL_INDEPENDENTLY" if audited
                    else "READY_SAFE_IMPLEMENTATION" if ready and ob["safe_work"]
                    else "READY_REVIEW_RELEASE_GATED" if ready
                    else "WAIT_FOR_EVIDENCE_GATE")
        states.append({"id":ident,"stream_id":ob["stream_id"],
            "owner":ob["owner"],"trigger":trigger,
            "state":state_name,"blocker":block,
            "priority":ob["priority"],
            "allowed_action":ob["allowed_action"],
            "completion_gate":ob["completion_gate"],
            "requires_user_release":ob["requires_user_release"],
            "safe_work":ob["safe_work"],
            "completion_is_documentary_not_independent_runtime_proof":audited})
    open_tasks=[s for s in states if not s["completion_is_documentary_not_independent_runtime_proof"]]
    # Return ALL ready obligations. The existing Work selector reserves at most
    # two CONCURRENT active packages, then refills on a genuine receipt in the
    # same bounded 10:15 run. Never silently truncate due owners here.
    safe=sorted((s for s in open_tasks if s["state"]=="READY_SAFE_IMPLEMENTATION"),
                key=lambda x:(x["priority"],x["id"]))
    return {"kind":cfg["kind"],"status":"OPEN_GATED_OR_SAFE_WORK" if open_tasks
            else "DOCUMENTARY_ACKS_RECORDED_LIVE_VALIDATION_STILL_REQUIRED",
            "registered_count":len(states),"open_count":len(open_tasks),
            "items":states,"ready_safe_actions":safe,
            "ready_release_reviews":[x for x in open_tasks if
                         x["state"]=="READY_REVIEW_RELEASE_GATED"],
            "no_auto_paper_release":True,"no_auto_trades":True}


def historical_backlog_reconciliation(root:Path,ack:dict,now:dt.datetime)->dict:
    """All unchecked historic notes remain visible until independently disposed."""
    config=read_json(root,"research/project-followthrough-routing-v1.json").get(
        "historical_backlog_reconciliation") or {}
    require(config.get("kind")=="EXISTING_BACKLOG_UNDISPOSED_HISTORICAL_COMMITMENTS_V1"
            and config.get("owner")=="EXISTING_DAILY_1015_WORK_ONCE_PER_GATE"
            and config.get("source")=="PROJECT_BACKLOG.md"
            and config.get("max_review_rows_per_run")==3,
            "missing canonical historical backlog reconciliation owner")
    for flag in ("do_not_silently_assume_old_checkbox_is_current_task",
                 "no_new_schedule","no_auto_release","no_auto_cleanup",
                 "no_runtime_truth_from_backlog"):
        require(config.get(flag) is True,"unsafe historic backlog handling "+flag)
    ledger=((ack.get("acknowledgements") or {})
            .get("historical_backlog_dispositions") or {})
    require(isinstance(ledger,dict),"historic backlog ACK malformed")
    pending=[];disposed=[]
    lines=(root/"PROJECT_BACKLOG.md").read_text(encoding="utf-8").splitlines()
    for number,line in enumerate(lines,1):
        if not re.match(r"^\s*[-*] \[ \] ",line):
            continue
        wording=line.strip()
        token="BACKLOG-"+hashlib.sha256(wording.encode("utf-8")).hexdigest()[:20]
        item=ledger.get(token)
        evidenced=False
        if isinstance(item,dict):
            proof=item.get("evidence_sha256"); report=item.get("report")
            status=item.get("disposition")
            valid=(status in ("OPEN_REGISTERED","DEFERRED_WITH_GATE",
                              "SUPERSEDED_WITH_CANONICAL_OWNER","COMPLETED_VERIFIED")
                   and isinstance(item.get("owner"),str) and len(item["owner"])>5
                   and isinstance(item.get("next_gate"),str) and len(item["next_gate"])>8
                   and isinstance(proof,str) and re.fullmatch(r"[a-f0-9]{64}",proof)
                   and isinstance(report,str) and
                   re.fullmatch(r"research/work-analysis/[A-Za-z0-9_.-]+[.]md",report))
            if valid:
                try:
                    path=root/report
                    evidenced=(path.is_file()
                         and hashlib.sha256(path.read_bytes()).hexdigest()==proof
                         and utc(item["reviewed_at_utc"])<=now)
                except (OSError,KeyError,ValueError,TypeError): pass
        (disposed if evidenced else pending).append({
            "id":token,"line":number,
            "priority":"V3_REVIEW_FIRST" if "V3" in wording.upper() else
                       "OLDER_OR_CROSS_PROJECT_RECONCILIATION",
            "excerpt":wording[:220]})
    priority=sorted(pending,key=lambda x:(
        x["priority"]!="V3_REVIEW_FIRST",x["line"]))
    return {"kind":config["kind"],"open_checkboxes_total":len(disposed)+len(pending),
            "dispositions_provenance_reviewed":len(disposed),
            "still_unclassified":len(pending),
            "next_review":priority[:config["max_review_rows_per_run"]],
            "legacy_open_box_not_a_live_task_without_review":True,
            "no_auto_changes":True}


def route(root: Path, now: dt.datetime) -> dict:
    manifest = read_json(root, "research/project-followthrough-routing-v1.json")
    routing = read_json(root, "research/monitoring-evidence-routing-v1.json")
    state = read_json(root, "project-current-state.json")
    ack = read_json(root, "research/work-analysis-state.json")
    require(manifest.get("kind") == "PROJECT_WIDE_FOLLOWTHROUGH_ROUTING_V1"
            and manifest.get("schema_version") == 1, "followthrough schema changed")
    require(manifest.get("stream_coverage") ==
            "ALL_MONITORING_EVIDENCE_ROUTING_STREAMS_DYNAMIC", "partial stream coverage")
    require(manifest.get("stream_source") ==
            "research/monitoring-evidence-routing-v1.json", "routing source mismatch")
    require(manifest.get("executor") == "EXISTING_DAILY_1015_WORK_ONCE_PER_GATE",
            "wrong executor")
    require(manifest.get("watcher") ==
            "EXISTING_AUTONOMOUS_PROJECT_MILESTONE_CONTROLLER", "wrong watcher")
    safe = manifest.get("safety") or {}
    for flag in ("no_new_scheduler", "no_runtime_mutation", "no_trade_or_orders",
                 "no_auto_activation", "no_unverified_chat_ingestion", "no_fake_completion"):
        require(safe.get(flag) is True, "unsafe policy: " + flag)
    require(set(manifest.get("user_release_required") or []) == RELEASE_DENY,
            "release boundaries differ")
    context = manifest.get("context_preflight") or {}
    require(context.get("kind") == "CONTEXT_BEFORE_ACTION_HANDOFF_V1"
            and context.get("command") == "tools/context_before_action.py"
            and context.get("routing") == "research/context-before-action-routing-v1.json"
            and context.get("scopes") == ["strategy", "architecture", "operations", "research"]
            and context.get("activation") ==
                "ONLY_BEFORE_MATERIAL_REVIEW_OR_ALLOWED_SAFE_IMPLEMENTATION"
            and context.get("no_substitute_for_actual_source_reading") is True
            and context.get("receipt_not_authorization") is True
            and context.get("no_new_work_run") is True,
            "context before material action handoff missing/unsafe")
    require(state.get("kind") == "PROJECT_CURRENT_STATE_V1"
            and state.get("active_strategy", {}).get("real_money_actions") is False
            and state.get("active_strategy", {}).get("automatic_activation_allowed") is False,
            "current-state activation boundary changed")
    streams = routing.get("streams") or []
    stream_ids = [s.get("id") for s in streams]
    required_stream_ids = manifest.get("required_stream_ids") or []
    require(len(required_stream_ids) == len(set(required_stream_ids))
            and len(required_stream_ids) >= 26
            and set(required_stream_ids).issubset(set(stream_ids))
            and len(stream_ids) == len(set(stream_ids)),
            "missing/duplicate monitoring route")
    for stream in streams:
        require(all(isinstance(stream.get(k), str) and stream[k]
                    for k in ("id", "canonical_owner", "consumer", "next_gate")),
                "stream without owner/consumer/next gate")
    extra = manifest.get("extra_project_areas") or []
    extra_ids = [e.get("id") for e in extra]
    require(len(extra) >= 8 and len(extra_ids) == len(set(extra_ids)),
            "missing/duplicate cross-cutting workstream")
    for area in extra:
        name = area.get("owner")
        require(isinstance(name, str) and re.fullmatch(r"[a-zA-Z0-9_./-]+", name)
                and ".." not in name and (root / name).is_file()
                and isinstance(area.get("gate"), str) and len(area["gate"]) > 5,
                "cross-cutting area without real canonical owner/gate")
    decisions = state.get("next_control_decisions") or []
    decision_ids = [d.get("id") for d in decisions]
    require(len(decision_ids) == len(set(decision_ids)), "duplicate control decisions")
    reviews = ((ack.get("acknowledgements") or {}).get("control_decision_reviews") or {})
    ready, gated, closed = [], [], []
    for task in decisions:
        task_id = task.get("id")
        require(isinstance(task_id, str) and task_id and task.get("trigger")
                and task.get("action"), "control decision has no trigger/action")
        due_str, key, lag = (task.get("due_at_utc"),
                             task.get("followthrough_ack_key"),
                             task.get("followthrough_max_lag_hours"))
        if any(x is not None for x in (due_str, key, lag)):
            require(isinstance(due_str, str) and isinstance(key, str)
                    and re.fullmatch(r"[A-Za-z0-9_.-]{5,120}", key)
                    and type(lag) is int and 1 <= lag <= 168,
                    "incomplete timed-gate contract")
            due = utc(due_str)
            if now < due:
                gated.append({"id": task_id, "gate": "WAIT_FOR_DUE_TIME", "due_at_utc": due_str})
            elif valid_receipt(root, reviews, key, due, now):
                closed.append(task_id)
            else:
                ready.append({"id": task_id, "gate": "DUE_REVIEW",
                              "ack_key": key, "owner": "EXISTING_DAILY_1015_WORK",
                              "release": "SEPARATE_USER_APPROVAL_FOR_MATERIAL_CHANGE"})
        elif "REVIEW_DUE" in str(task.get("status", "")):
            ready.append({"id": task_id, "gate": "DECLARED_REVIEW_DUE",
                          "owner": "EXISTING_DAILY_1015_WORK",
                          "release": "SEPARATE_USER_APPROVAL_FOR_MATERIAL_CHANGE"})
        else:
            gated.append({"id": task_id, "gate": "CHECK_DECLARED_TRIGGER_NO_AUTO_START"})
    source_followthrough=v3_five_source_followthrough(root,state,ack,now)
    generic_commitments=project_implementation_commitments(root,state,ack,now)
    legacy_backlog=historical_backlog_reconciliation(root,ack,now)
    return {
        "v3_paper_five_source_followthrough":source_followthrough,
        "project_implementation_commitments":generic_commitments,
        "historical_backlog_reconciliation":legacy_backlog,
        "kind": "PROJECT_WIDE_WORK_HANDOFF_V1",
        "status": "REVIEW_DUE" if ready else "NO_DUE_CONTROL_GATE",
        "stream_coverage_count": len(streams),
        "crosscut_coverage_count": len(extra),
        "covered_stream_ids": stream_ids,
        "ready_control_decisions": ready,
        "gated_control_decisions": gated,
        "previously_acknowledged": closed,
        "backlog_owner": "PROJECT_BACKLOG.md",
        "safe_work_selector": "tools/select-autonomous-implementation.py",
        "context_before_material_work": {
            "required": True,
            "when": "ONLY_ACTUALLY_DUE_MATERIAL_REVIEW_OR_READY_SAFE_WORK",
            "command": "tools/context_before_action.py",
            "routing": "research/context-before-action-routing-v1.json",
            "scopes": context["scopes"],
            "must_read_original_relevant_sources": True,
            "receipt_does_not_grant_release": True,
            "required_not_evidence_of_execution": True
        },
        "executor": "EXISTING_DAILY_1015_WORK_ONCE_PER_GATE",
        "may_change_strategy": False, "may_execute_orders": False,
        "may_start_shadow_or_live": False, "may_schedule_new_runs": False,
        "unregistered_conversations_are_not_automatically_imported": True,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--at-utc", type=str)
    args = p.parse_args()
    now = utc(args.at_utc) if args.at_utc else dt.datetime.now(UTC)
    print(json.dumps(route(args.root, now), sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
