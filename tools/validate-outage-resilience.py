#!/usr/bin/env python3
"""Offline cross-domain outage safety validator. No API, secrets, schedule or writes."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {"kraken_public", "mini_pc_power", "home_internet", "github_public",
            "github_private", "supabase", "kraken_ws_shadow", "paper_candidates",
            "paper_wait", "paper_lifecycle", "paper_followups", "shadow_h3",
            "research_h10", "slack", "work", "backup", "secrets"}
SAFETY_FALSE = {"automatic_real_money_actions", "automatic_strategy_promotion",
                "automatic_scheduler_addition", "missing_optional_inputs_can_reject_buy",
                "failed_backfill_can_count_as_complete", "old_snapshot_can_authorize_new_paper_buy"}

def validate(doc:dict)->list[str]:
    errors=[]
    if doc.get("schema_version")!=1 or doc.get("kind")!="GLOBAL_OUTAGE_RECONCILIATION_CONTRACT_V1":
        errors.append("unknown outage contract version")
    if doc.get("declared_strategy")!="project-current-state.json" or doc.get("active_release_unmodified") is not True:
        errors.append("current strategy source of truth changed")
    for key in SAFETY_FALSE:
        if doc.get(key) is not False:
            errors.append(f"forbidden unsafe authority {key}")
    if doc.get("paper_only") is not True:
        errors.append("paper lock missing")
    if doc.get("max_auto_restart_per_task_per_hour",999)>5 or doc.get("max_restart_backoff_seconds")!=3600:
        errors.append("unbounded self healing")
    if doc.get("minimum_proof")!="FRESH_PIT_INPUT_AND_IDEMPOTENT_OUTPUT_OR_EXPLICIT_GAP_ACK":
        errors.append("missing post-outage evidence gate")
    states=set(doc.get("states",[]))
    expected={"HEALTHY","SOURCE_DOWN","LOCAL_DOWN","RECOVERING","RECONCILING",
              "DEGRADED_GAP","HEALTHY_RESTORED","ACTION_REQUIRED"}
    if states!=expected:errors.append("invalid recovery state machine")
    transitions={tuple(x) for x in doc.get("transitions",[]) if isinstance(x,list) and len(x)==2}
    for pair in [("HEALTHY","SOURCE_DOWN"),("HEALTHY","LOCAL_DOWN"),
                 ("SOURCE_DOWN","RECOVERING"),("LOCAL_DOWN","RECOVERING"),
                 ("RECOVERING","RECONCILING"),("RECONCILING","DEGRADED_GAP"),
                 ("RECONCILING","HEALTHY_RESTORED"),("DEGRADED_GAP","HEALTHY_RESTORED"),
                 ("HEALTHY_RESTORED","HEALTHY")]:
        if pair not in transitions:errors.append(f"missing transition {pair}")
    if any(a not in states or b not in states for a,b in transitions):
        errors.append("transition references unknown state")
    domains=doc.get("domains") or []
    ids=[x.get("id") for x in domains]
    if len(ids)!=len(set(ids)) or set(ids)!=REQUIRED:
        errors.append("missing or duplicate outage failure domain")
    for row in domains:
        for name in ("component","role","recovery_path","evidence","on_gap","return_gate","failure"):
            if not row.get(name):errors.append(f"domain {row.get('id')} missing {name}")
        if row.get("on_gap") in {"MAKE_UP_PROSPECTIVE_BUY","REJECT_BUY","COUNT_AS_COMPLETE","REPLAY_WITH_CURRENT_PRICE"}:
            errors.append(f"unsafe gap handling {row.get('id')}")
    return errors

def main():
    p=ROOT/"research/global-outage-recovery-contract-v1.json"
    doc=json.loads(p.read_text("utf-8"))
    errors=validate(doc)
    if errors:raise SystemExit("OUTAGE_GUARD_FAIL "+json.dumps(errors))
    print("OUTAGE_GUARD_PASS domains="+str(len(doc["domains"])))
if __name__=="__main__":
    main()
