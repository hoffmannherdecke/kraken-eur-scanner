#!/usr/bin/env python3
"""Transition-/dedupe-controlled Slack routing for CRYPTO_PROCESS_HEALTH_V2.

Only actionable CRITICAL states create an iPhone-push-capable Slack mention.
Repeated identical incidents are suppressed for two hours. A changed CRITICAL
fingerprint alerts immediately. Recovery from CRITICAL emits exactly one
mention. WARNING/HEALTHY states are otherwise silent.

Persistent state lives in Supabase and has no strategy/trading authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

WATCH_ID="CRYPTO_PROCESS_HEALTH_V2"
REPEAT_AFTER_SECONDS=7200

def utcnow():
    return datetime.now(timezone.utc)

def parse_dt(raw):
    if not raw:
        return None
    return datetime.fromisoformat(str(raw).replace("Z","+00:00"))

def critical_codes(report:dict[str,Any])->list[str]:
    return sorted({str(i.get("code")) for i in report.get("issues",[]) if i.get("severity")=="CRITICAL" and i.get("code")})

def fingerprint(codes:list[str])->str|None:
    if not codes:
        return None
    return hashlib.sha256("|".join(codes).encode("utf-8")).hexdigest()

def route_decision(report:dict[str,Any],state:dict[str,Any]|None,now:datetime)->dict[str,Any]:
    state=state or {}
    codes=critical_codes(report)
    condition="CRITICAL" if codes else "OK"
    fp=fingerprint(codes)
    previous=str(state.get("last_condition") or "UNKNOWN").upper()
    prev_fp=state.get("last_fingerprint")
    last_alert=parse_dt(state.get("last_alert_at"))

    if condition=="CRITICAL":
        due=(
            previous!="CRITICAL"
            or fp!=prev_fp
            or last_alert is None
            or (now-last_alert).total_seconds()>=REPEAT_AFTER_SECONDS
        )
        return {
            "action":"ALERT" if due else "NONE",
            "condition":condition,
            "codes":codes,
            "fingerprint":fp,
            "previous":previous,
        }

    if previous=="CRITICAL":
        return {
            "action":"RECOVERY",
            "condition":"OK",
            "codes":[],
            "fingerprint":None,
            "previous":previous,
        }

    return {
        "action":"NONE",
        "condition":"OK",
        "codes":[],
        "fingerprint":None,
        "previous":previous,
    }

class SupabaseState:
    def __init__(self):
        self.url=os.environ.get("SUPABASE_URL","").rstrip("/")
        self.key=(os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
        if not self.url or not self.key:
            raise RuntimeError("Supabase backend configuration missing")
        self.headers={"apikey":self.key,"Content-Type":"application/json"}
        if not self.key.startswith("sb_secret_"):
            self.headers["Authorization"]="Bearer "+self.key

    def request(self,method,path,body=None,extra_headers=None):
        h=dict(self.headers)
        if extra_headers:
            h.update(extra_headers)
        data=None if body is None else json.dumps(body,separators=(",",":")).encode("utf-8")
        req=urllib.request.Request(self.url+path,data=data,method=method,headers=h)
        with urllib.request.urlopen(req,timeout=20) as resp:
            raw=resp.read().decode("utf-8","replace")
            return resp.status,json.loads(raw) if raw else None

    def load(self):
        path=(
            "/rest/v1/process_health_alert_state"
            "?select=watch_id,last_condition,last_fingerprint,last_issue_codes,last_alert_at,last_recovery_at,updated_at"
            "&watch_id=eq."+urllib.parse.quote(WATCH_ID,safe="")
        )
        _,rows=self.request("GET",path)
        return rows[0] if rows else None

    def save(self,decision,state,now,alert_sent=False,recovery_sent=False):
        previous=state or {}
        row={
            "watch_id":WATCH_ID,
            "last_condition":decision["condition"],
            "last_fingerprint":decision["fingerprint"],
            "last_issue_codes":decision["codes"],
            "last_alert_at":now.isoformat() if alert_sent else previous.get("last_alert_at"),
            "last_recovery_at":now.isoformat() if recovery_sent else previous.get("last_recovery_at"),
            "updated_at":now.isoformat(),
        }
        self.request(
            "POST",
            "/rest/v1/process_health_alert_state?on_conflict=watch_id",
            [row],
            {"Prefer":"resolution=merge-duplicates,return=minimal"},
        )

def post_slack(text):
    webhook=os.environ.get("SLACK_WEBHOOK_URL","").strip()
    user_id=os.environ.get("SLACK_USER_ID","").strip()
    if not webhook:
        raise RuntimeError("SLACK_WEBHOOK_URL missing")
    if not user_id:
        raise RuntimeError("SLACK_USER_ID missing")
    payload={"text":f"<@{user_id}> {text}"}
    req=urllib.request.Request(
        webhook,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type":"application/json"},
    )
    with urllib.request.urlopen(req,timeout=15) as resp:
        body=resp.read().decode("utf-8","replace").strip()
        print(f"Slack response: {resp.status} {body}")
        if not 200<=resp.status<300:
            raise RuntimeError(f"Slack HTTP {resp.status}")

def format_alert(report,codes):
    details=[]
    by_code={str(i.get("code")):i for i in report.get("issues",[]) if i.get("severity")=="CRITICAL"}
    for code in codes[:4]:
        detail=str((by_code.get(code) or {}).get("detail") or "").strip()
        details.append(code+(f": {detail[:160]}" if detail else ""))
    tail="" if len(codes)<=4 else f" (+{len(codes)-4} weitere)"
    return (
        "SYSTEMKRITISCH | Crypto-Prozess-Health | "
        + "; ".join(details)+tail+
        " | Bitte Infrastruktur prüfen. Kein Handelssignal."
    )

def self_test():
    t=utcnow()
    healthy={"status":"HEALTHY","issues":[]}
    warning={"status":"WARNING","issues":[{"code":"NO_PAPER_TRADES","severity":"WARNING"}]}
    crit_a={"status":"CRITICAL","issues":[{"code":"OVERDUE_WAIT","severity":"CRITICAL"}]}
    crit_b={"status":"CRITICAL","issues":[{"code":"ORPHAN_CANDIDATES","severity":"CRITICAL"}]}

    assert route_decision(healthy,None,t)["action"]=="NONE"
    assert route_decision(warning,None,t)["action"]=="NONE"
    d=route_decision(crit_a,None,t); assert d["action"]=="ALERT"
    state={"last_condition":"CRITICAL","last_fingerprint":d["fingerprint"],"last_alert_at":t.isoformat()}
    assert route_decision(crit_a,state,t+timedelta(minutes=10))["action"]=="NONE"
    assert route_decision(crit_a,state,t+timedelta(hours=2,seconds=1))["action"]=="ALERT"
    assert route_decision(crit_b,state,t+timedelta(minutes=10))["action"]=="ALERT"
    assert route_decision(healthy,state,t+timedelta(minutes=10))["action"]=="RECOVERY"
    assert route_decision(warning,state,t+timedelta(minutes=10))["action"]=="RECOVERY"
    print("PROCESS_HEALTH_ALERT_ROUTER_SELFTEST PASS transition/dedupe/new-fingerprint/2h-repeat/recovery")
    return 0

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("report",nargs="?",default="process_health.json")
    ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()

    if a.self_test:
        return self_test()

    report=json.loads(Path(a.report).read_text("utf-8"))
    if report.get("kind")!="CRYPTO_PROCESS_HEALTH_V2":
        raise RuntimeError("unexpected process health report kind")

    now=utcnow()
    store=SupabaseState()
    state=store.load()
    decision=route_decision(report,state,now)

    sent_alert=False
    sent_recovery=False
    if decision["action"]=="ALERT":
        post_slack(format_alert(report,decision["codes"]))
        sent_alert=True
    elif decision["action"]=="RECOVERY":
        post_slack(
            "SYSTEM-RECOVERY | Crypto-Prozess-Health wieder ohne CRITICAL-Zustand. "
            "Recovery bestätigt. Keine Handelsaktion."
        )
        sent_recovery=True

    store.save(decision,state,now,alert_sent=sent_alert,recovery_sent=sent_recovery)
    print("PROCESS_HEALTH_ALERT_ROUTING "+json.dumps({
        "action":decision["action"],
        "condition":decision["condition"],
        "critical_codes":decision["codes"],
        "previous":decision["previous"],
        "alert_sent":sent_alert,
        "recovery_sent":sent_recovery,
        "repeat_after_seconds":REPEAT_AFTER_SECONDS,
    },sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
