#!/usr/bin/env python3
"""Independent health audit + bounded technical self-healing for the paper crypto chain."""
import json, os, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=os.environ.get("GITHUB_REPOSITORY","hoffmannherdecke/kraken-eur-scanner")
TOKEN=os.environ.get("GH_TOKEN","")
SLACK=os.environ.get("SLACK_WEBHOOK_URL","")
NOW=int(time.time())
PROSPECTIVE_CUTOFF_TS=1790532491  # evaluator activation 2026-09-27T18:08:11Z
issues=[]; repairs=[]; metrics={}

def add(code,severity,detail,repairable=False):
    issues.append({"code":code,"severity":severity,"detail":detail,"repairable":repairable})

def gh(method,path,body=None):
    if not TOKEN: raise RuntimeError("GH_TOKEN missing")
    data=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request("https://api.github.com/repos/"+REPO+path,data=data,method=method,headers={
      "Authorization":"Bearer "+TOKEN,"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","User-Agent":"crypto-process-audit/1.0"})
    with urllib.request.urlopen(req,timeout=25) as r:
        raw=r.read()
        return json.loads(raw) if raw else {}

def workflow_runs(filename):
    return gh("GET","/actions/workflows/"+filename+"/runs?per_page=5").get("workflow_runs",[])

def dispatch(filename,reason):
    runs=workflow_runs(filename)
    recent=[r for r in runs if r.get("status") in ("queued","in_progress") or NOW-int(datetime.fromisoformat(r["created_at"].replace("Z","+00:00")).timestamp())<600]
    if recent:
        repairs.append({"workflow":filename,"action":"SKIP_RECENT_RUN","reason":reason}); return
    gh("POST","/actions/workflows/"+filename+"/dispatches",{"ref":"main"})
    repairs.append({"workflow":filename,"action":"DISPATCH","reason":reason})

def latest_health(filename,max_age):
    try: runs=workflow_runs(filename)
    except Exception as e:
        add("WORKFLOW_API_"+filename,"ERROR",repr(e)); return
    if not runs:
        add("NO_RUN_"+filename,"CRITICAL","No workflow run visible",True); return
    r=runs[0]; age=NOW-int(datetime.fromisoformat(r["created_at"].replace("Z","+00:00")).timestamp())
    metrics[filename]={"run_id":r["id"],"status":r["status"],"conclusion":r.get("conclusion"),"age_seconds":age}
    if age>max_age:
        add("STALE_"+filename,"CRITICAL",f"latest run age {age}s > {max_age}s",True)
    elif r["status"]=="completed" and r.get("conclusion")!="success":
        add("FAILED_"+filename,"CRITICAL",f"latest conclusion={r.get('conclusion')}",True)

def load_dir(name):
    out={}
    p=ROOT/name
    if not p.exists(): return out
    for f in p.glob("*.json"):
        try: out[f.name]=json.loads(f.read_text())
        except Exception as e: add("BAD_JSON","CRITICAL",f"{f}: {e}")
    return out

queue=load_dir("handoff_queue"); decisions=load_dir("paper_decisions"); revals=load_dir("paper_revalidations")
metrics.update({"queue_files":len(queue),"decision_files":len(decisions),"revalidation_files":len(revals)})

# Core safety and identity invariants.
for name,d in decisions.items():
    if d.get("real_money_actions_enabled") is not False: add("REAL_MONEY_FLAG","CRITICAL",name)
    if d.get("decision",{}).get("decision") not in {"BUY_SCOUT","WAIT","REJECT"}: add("BAD_DECISION","CRITICAL",name)
for name,d in revals.items():
    if d.get("real_money_actions_enabled") is not False: add("REAL_MONEY_FLAG_REVAL","CRITICAL",name)
    if d.get("decision",{}).get("decision") not in {"BUY_SCOUT","REJECT"}: add("BAD_REVALIDATION","CRITICAL",name)

# Handoff liveness: every recent candidate should get a decision soon.
orphans=[]
for name,c in queue.items():
    age=NOW-int(c.get("event_ts",0))
    if int(c.get("event_ts",0)) >= PROSPECTIVE_CUTOFF_TS and 1200 < age <= 7200 and name not in decisions:
        orphans.append(name)
if orphans: add("ORPHAN_CANDIDATES","CRITICAL",f"{len(orphans)} candidates >20m without decision: "+",".join(orphans[:5]),True)
metrics["orphan_candidates"]=len(orphans)

# WAIT liveness: due WAIT must get exactly one terminal revalidation.
overdue=[]
for name,d in decisions.items():
    if d.get("decision",{}).get("decision")!="WAIT" or name in revals: continue
    ev=datetime.fromisoformat(d["evaluated_at_utc"].replace("Z","+00:00")).timestamp()
    due=ev+60*int(d["decision"].get("ttl_minutes",0))
    if NOW>due+1200: overdue.append(name)
if overdue: add("OVERDUE_WAIT","CRITICAL",f"{len(overdue)} WAITs >20m past TTL: "+",".join(overdue[:5]),True)
metrics["overdue_waits"]=len(overdue)

# Trade drought is an anomaly, not an automatic strategy change.
terminal=[]
buys=[]
for d in list(decisions.values())+list(revals.values()):
    x=d.get("decision",{}).get("decision")
    if x in {"BUY_SCOUT","REJECT"}: terminal.append(x)
    if x=="BUY_SCOUT": buys.append(d)
metrics["terminal_decisions"]=len(terminal); metrics["paper_buys"]=len(buys)
if len(terminal)>=10 and not buys:
    add("NO_PAPER_TRADES","WARNING",f"0 BUY_SCOUT across {len(terminal)} terminal decisions; investigate technical gates vs strategy strictness")
if len(terminal)>=20 and len(buys)/len(terminal)<0.05:
    add("VERY_LOW_TRADE_RATE","WARNING",f"{len(buys)}/{len(terminal)} BUY_SCOUT; strategy review required, no automatic threshold change")

# A BUY without a lifecycle tracker is unsafe even in paper because outcome statistics would be invalid.
if buys and not (ROOT/"paper_positions").exists():
    add("POSITION_LIFECYCLE_MISSING","CRITICAL","Paper BUY exists but no paper_positions lifecycle evidence")

# Independent workflow liveness.
latest_health("scan.yml",2700)
latest_health("paper-capture.yml",9000)
latest_health("paper-evaluator.yml",2700)
latest_health("paper-revalidator.yml",2700)

# Bounded technical self-healing only. Never modify strategy/risk/real-money settings.
try:
    if orphans: dispatch("paper-evaluator.yml","orphan candidate recovery")
    if overdue: dispatch("paper-revalidator.yml","overdue WAIT recovery")
    for code,wf in [("STALE_scan.yml","scan.yml"),("FAILED_scan.yml","scan.yml"),
                    ("STALE_paper-capture.yml","paper-capture.yml"),("FAILED_paper-capture.yml","paper-capture.yml"),
                    ("STALE_paper-evaluator.yml","paper-evaluator.yml"),("FAILED_paper-evaluator.yml","paper-evaluator.yml"),
                    ("STALE_paper-revalidator.yml","paper-revalidator.yml"),("FAILED_paper-revalidator.yml","paper-revalidator.yml"),
                    ("NO_RUN_paper-revalidator.yml","paper-revalidator.yml"),("NO_RUN_paper-evaluator.yml","paper-evaluator.yml")]:
        if any(i["code"]==code for i in issues): dispatch(wf,code)
except Exception as e:
    add("SELF_HEAL_FAILED","ERROR",repr(e))

report={"schema_version":1,"kind":"CRYPTO_PROCESS_HEALTH_V1","audited_at_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "status":"CRITICAL" if any(i["severity"]=="CRITICAL" for i in issues) else ("WARNING" if issues else "HEALTHY"),
        "metrics":metrics,"issues":issues,"repairs":repairs,
        "guardrails":{"strategy_auto_change":False,"real_money_enable":False,"technical_dispatch_only":True}}
Path("process_health.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
print("PROCESS_HEALTH "+json.dumps(report,sort_keys=True))

if issues and SLACK:
    msg="CRYPTO_HEALTH "+report["status"]+" | "+"; ".join(i["code"] for i in issues[:8])
    req=urllib.request.Request(SLACK,data=json.dumps({"text":msg}).encode(),method="POST",headers={"Content-Type":"application/json"})
    try: urllib.request.urlopen(req,timeout=15).read()
    except Exception as e: print("WARN slack health alert failed",repr(e))

# Critical findings fail the audit after repair dispatches, making the fault visible in Actions.
if any(i["severity"]=="CRITICAL" for i in issues):
    raise SystemExit(2)
