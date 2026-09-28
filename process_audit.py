#!/usr/bin/env python3
"""Independent health audit + bounded technical self-healing for the paper crypto chain."""
from __future__ import annotations
import json, os, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=os.environ.get("GITHUB_REPOSITORY","hoffmannherdecke/kraken-eur-scanner")
TOKEN=os.environ.get("GH_TOKEN","")
SLACK=os.environ.get("SLACK_WEBHOOK_URL","")
NOW=int(time.time())
CONTROL_PATH=ROOT/"paper_runtime_control.json"

try:
    CONTROL=json.loads(CONTROL_PATH.read_text("utf-8"))
except Exception as exc:
    CONTROL={"enabled":False,"control_error":repr(exc)}

ENABLED=CONTROL.get("enabled") is True
SERIES_ID=CONTROL.get("series_id")
try:
    SERIES_START_TS=int(datetime.fromisoformat(CONTROL["series_started_at_utc"].replace("Z","+00:00")).timestamp())
except Exception:
    SERIES_START_TS=0

issues=[]
repairs=[]
metrics={
    "paper_runtime_enabled":ENABLED,
    "series_id":SERIES_ID,
    "series_start_ts":SERIES_START_TS,
}

def add(code,severity,detail,repairable=False):
    issues.append({"code":code,"severity":severity,"detail":detail,"repairable":repairable})

def gh(method,path,body=None):
    if not TOKEN:
        raise RuntimeError("GH_TOKEN missing")
    data=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request(
        "https://api.github.com/repos/"+REPO+path,
        data=data,method=method,
        headers={
            "Authorization":"Bearer "+TOKEN,
            "Accept":"application/vnd.github+json",
            "X-GitHub-Api-Version":"2022-11-28",
            "User-Agent":"crypto-process-audit/2.0",
            "Content-Type":"application/json",
        }
    )
    with urllib.request.urlopen(req,timeout=25) as r:
        raw=r.read()
        return json.loads(raw) if raw else {}

def workflow_runs(filename):
    return gh("GET","/actions/workflows/"+filename+"/runs?per_page=5").get("workflow_runs",[])

def dispatch(filename,reason):
    runs=workflow_runs(filename)
    if any(r.get("status") in ("queued","in_progress") for r in runs):
        repairs.append({"workflow":filename,"action":"SKIP_ACTIVE_RUN","reason":reason})
        return
    gh("POST","/actions/workflows/"+filename+"/dispatches",{"ref":"main"})
    repairs.append({"workflow":filename,"action":"DISPATCH","reason":reason})

def latest_health(filename,max_age):
    try:
        runs=workflow_runs(filename)
    except Exception as exc:
        add("WORKFLOW_API_"+filename,"ERROR",repr(exc))
        return
    if not runs:
        add("NO_RUN_"+filename,"CRITICAL","No workflow run visible",True)
        return
    r=runs[0]
    age=NOW-int(datetime.fromisoformat(r["created_at"].replace("Z","+00:00")).timestamp())
    metrics[filename]={"run_id":r["id"],"status":r["status"],"conclusion":r.get("conclusion"),"age_seconds":age}
    if age>max_age:
        add("STALE_"+filename,"CRITICAL",f"latest run age {age}s > {max_age}s",True)
    elif r["status"]=="completed" and r.get("conclusion")!="success":
        add("FAILED_"+filename,"CRITICAL",f"latest conclusion={r.get('conclusion')}",True)

def load_dir(name):
    out={}
    p=ROOT/name
    if not p.exists():
        return out
    for f in p.glob("*.json"):
        try:
            out[f.name]=json.loads(f.read_text("utf-8"))
        except Exception as exc:
            add("BAD_JSON","CRITICAL",f"{f}: {exc}")
    return out

queue=load_dir("handoff_queue")
decisions=load_dir("paper_decisions")
revals=load_dir("paper_revalidations")
positions=load_dir("paper_positions")
followups=load_dir("paper_followups")
metrics.update({
    "queue_files":len(queue),"decision_files":len(decisions),
    "revalidation_files":len(revals),"position_files":len(positions),
    "followup_files":len(followups)
})

if ENABLED and not SERIES_ID:
    add("MISSING_SERIES_ID","CRITICAL","Enabled runtime has no series_id")

# Safety invariants across all persisted trade-capable records.
for name,d in decisions.items():
    if d.get("real_money_actions_enabled") is not False:
        add("REAL_MONEY_FLAG","CRITICAL",name)
for name,d in revals.items():
    if d.get("real_money_actions_enabled") is not False:
        add("REAL_MONEY_FLAG_REVAL","CRITICAL",name)
for name,d in positions.items():
    if d.get("real_money_actions_enabled") is not False:
        add("REAL_MONEY_FLAG_POSITION","CRITICAL",name)

active_decisions={n:d for n,d in decisions.items() if d.get("series_id")==SERIES_ID}
active_revals={n:d for n,d in revals.items() if d.get("series_id")==SERIES_ID}
active_positions={n:d for n,d in positions.items() if d.get("series_id")==SERIES_ID}
active_followups={n:d for n,d in followups.items() if d.get("series_id")==SERIES_ID}
metrics.update({
    "active_decisions":len(active_decisions),
    "active_revalidations":len(active_revals),
    "active_positions":len(active_positions),
    "active_followups":len(active_followups),
})

orphans=[]
due_waits=[]
overdue_waits=[]
if ENABLED:
    for name,c in queue.items():
        ts=int(c.get("event_ts",0))
        age=NOW-ts
        if ts>=SERIES_START_TS and 600<age<=7200 and name not in decisions:
            orphans.append(name)
    if orphans:
        add("ORPHAN_CANDIDATES","CRITICAL",f"{len(orphans)} candidates >10m without decision: "+",".join(orphans[:5]),True)

    for name,d in active_decisions.items():
        if d.get("decision",{}).get("decision")!="WAIT" or name in active_revals:
            continue
        ev=datetime.fromisoformat(d["evaluated_at_utc"].replace("Z","+00:00")).timestamp()
        due=ev+60*int(d["decision"].get("ttl_minutes",0))
        lag=NOW-due
        if lag>=0:
            due_waits.append((name,int(lag)))
        if lag>300:
            overdue_waits.append((name,int(lag)))
    if overdue_waits:
        add("OVERDUE_WAIT","CRITICAL",
            f"{len(overdue_waits)} WAITs >5m past TTL: "+",".join(f"{n}:{lag}s" for n,lag in overdue_waits[:5]),True)

metrics["orphan_candidates"]=len(orphans)
metrics["due_waits"]=len(due_waits)
metrics["overdue_waits"]=len(overdue_waits)
metrics["max_wait_ttl_lag_seconds"]=max((lag for _,lag in due_waits),default=0)

# Current BUY -> position lifecycle completeness.
current_buys=[]
for d in list(active_decisions.values())+list(active_revals.values()):
    if d.get("decision",{}).get("decision")=="BUY_SCOUT" and d.get("paper_entry"):
        current_buys.append(d)
missing_positions=[d["candidate_id"] for d in current_buys if (d["candidate_id"]+".json") not in active_positions]
if missing_positions:
    add("POSITION_LIFECYCLE_MISSING","CRITICAL",
        f"{len(missing_positions)} BUYs lack position state: "+",".join(missing_positions[:5]),True)

closed=[p for p in active_positions.values() if p.get("status")=="CLOSED"]
open_pos=[p for p in active_positions.values() if p.get("status")=="OPEN"]
stale_open=[p for p in open_pos if p.get("stale_position_review_due")]
metrics.update({
    "paper_buys":len(current_buys),
    "missing_position_states":len(missing_positions),
    "completed_paper_trades":len(closed),
    "open_paper_positions":len(open_pos),
    "stale_open_positions":len(stale_open),
    "target_completed_paper_trades":int(CONTROL.get("target_completed_paper_trades",20)),
    "net_pnl_eur":round(sum(float(p.get("exit",{}).get("net_pnl_eur") or 0) for p in closed),4)
})
if stale_open:
    add("STALE_OPEN_POSITION","WARNING",f"{len(stale_open)} open positions exceed review-age threshold")

# Decision-rate diagnostics, never automatic strategy changes.
terminal=[]
for d in list(active_decisions.values())+list(active_revals.values()):
    x=d.get("decision",{}).get("decision")
    if x in {"BUY_SCOUT","REJECT"}:
        terminal.append(x)
metrics["terminal_decisions"]=len(terminal)
if len(terminal)>=10 and not current_buys:
    add("NO_PAPER_TRADES","WARNING",f"0 BUY_SCOUT across {len(terminal)} active-series terminal decisions")
if len(terminal)>=20 and current_buys and len(current_buys)/len(terminal)<0.05:
    add("VERY_LOW_TRADE_RATE","WARNING",f"{len(current_buys)}/{len(terminal)} active-series BUY_SCOUT")

# Compact follow-up coverage and missed-move counters.
followup_due=[]
for name,d in active_decisions.items():
    if d.get("decision",{}).get("decision") not in {"WAIT","REJECT"}:
        continue
    ev=int(datetime.fromisoformat(d["evaluated_at_utc"].replace("Z","+00:00")).timestamp())
    if NOW>=ev+35*60 and name not in active_followups:
        followup_due.append(name)
if followup_due:
    add("FOLLOWUP_LAG","WARNING",f"{len(followup_due)} candidates lack due compact follow-up",True)

mature=[x for x in active_followups.values() if x.get("horizons",{}).get("360",{}).get("complete")]
metrics["six_hour_followups"]=len(mature)
metrics["missed_5pct_6h"]=sum(bool(x.get("six_hour_flags",{}).get("missed_5pct")) for x in mature)
metrics["missed_8pct_6h"]=sum(bool(x.get("six_hour_flags",{}).get("missed_8pct")) for x in mature)
metrics["missed_10pct_6h"]=sum(bool(x.get("six_hour_flags",{}).get("missed_10pct")) for x in mature)

# Workflow liveness for the unified architecture.
latest_health("scan.yml",2100)
if ENABLED:
    latest_health("paper-evaluator.yml",2100)
else:
    metrics["paper_runtime_pause_reason"]=CONTROL.get("reason")

# Bounded technical self-healing only.
try:
    runtime_reasons=[]
    if ENABLED:
        if orphans:
            runtime_reasons.append("orphan candidate recovery")
        if due_waits:
            runtime_reasons.append("due WAIT revalidation")
        if missing_positions:
            runtime_reasons.append("missing position lifecycle")
        if followup_due:
            runtime_reasons.append("follow-up recovery")
        if runtime_reasons:
            dispatch("paper-evaluator.yml","; ".join(runtime_reasons))

    for code,wf in [
        ("STALE_scan.yml","scan.yml"),("FAILED_scan.yml","scan.yml"),
        ("NO_RUN_scan.yml","scan.yml"),
        ("STALE_paper-evaluator.yml","paper-evaluator.yml"),
        ("FAILED_paper-evaluator.yml","paper-evaluator.yml"),
        ("NO_RUN_paper-evaluator.yml","paper-evaluator.yml"),
    ]:
        if any(i["code"]==code for i in issues):
            dispatch(wf,code)
except Exception as exc:
    add("SELF_HEAL_FAILED","ERROR",repr(exc))

report={
    "schema_version":2,
    "kind":"CRYPTO_PROCESS_HEALTH_V2",
    "audited_at_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
    "status":"CRITICAL" if any(i["severity"]=="CRITICAL" for i in issues) else ("WARNING" if issues else "HEALTHY"),
    "metrics":metrics,"issues":issues,"repairs":repairs,
    "guardrails":{"strategy_auto_change":False,"real_money_enable":False,"technical_dispatch_only":True}
}
Path("process_health.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
print("PROCESS_HEALTH "+json.dumps(report,sort_keys=True))

if issues and SLACK:
    msg="CRYPTO_HEALTH "+report["status"]+" | "+"; ".join(i["code"] for i in issues[:8])
    req=urllib.request.Request(SLACK,data=json.dumps({"text":msg}).encode(),method="POST",headers={"Content-Type":"application/json"})
    try:
        urllib.request.urlopen(req,timeout=15).read()
    except Exception as exc:
        print("WARN slack health alert failed",repr(exc))

if any(i["severity"]=="CRITICAL" for i in issues):
    raise SystemExit(2)
