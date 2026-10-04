#!/usr/bin/env python3
"""Transition-/dedupe-controlled Slack routing for CRYPTO_PROCESS_HEALTH_V2.

Repairable CRITICAL states first get a bounded self-heal grace period. Only if
the same incident persists beyond that grace is an iPhone-push-capable Slack
mention sent. Non-repairable CRITICAL states alert immediately. Once an
incident has alerted, repeated identical incidents are suppressed for six
hours. Recovery from an alerted CRITICAL emits exactly one mention; a
repairable incident that heals during the grace period stays silent.

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
REPAIRABLE_GRACE_SECONDS=900
REMINDER_AFTER_SECONDS=21600

def utcnow():
    return datetime.now(timezone.utc)

def parse_dt(raw):
    if not raw:
        return None
    return datetime.fromisoformat(str(raw).replace("Z","+00:00"))

def critical_items(report:dict[str,Any])->list[dict[str,Any]]:
    return [
        i for i in report.get("issues",[])
        if i.get("severity")=="CRITICAL" and i.get("code")
    ]

def critical_codes(report:dict[str,Any])->list[str]:
    return sorted({str(i.get("code")) for i in critical_items(report)})

def fingerprint(codes:list[str])->str|None:
    if not codes:
        return None
    return hashlib.sha256("|".join(codes).encode("utf-8")).hexdigest()

def route_decision(report:dict[str,Any],state:dict[str,Any]|None,now:datetime)->dict[str,Any]:
    state=state or {}
    items=critical_items(report)
    codes=sorted({str(i.get("code")) for i in items})
    condition="CRITICAL" if codes else "OK"
    fp=fingerprint(codes)
    previous=str(state.get("last_condition") or "UNKNOWN").upper()
    prev_fp=state.get("last_fingerprint")
    same_incident=condition=="CRITICAL" and previous=="CRITICAL" and fp==prev_fp
    alerted=bool(state.get("current_incident_alerted")) if same_incident else False
    last_alert=parse_dt(state.get("last_alert_at"))
    incident_started=(
        parse_dt(state.get("incident_started_at")) if same_incident else None
    ) or now
    repairable=bool(items) and all(bool(i.get("repairable")) for i in items)

    if condition=="CRITICAL":
        incident_age=max(0.0,(now-incident_started).total_seconds())

        if not repairable and not alerted:
            action="ALERT"
            reason="nonrepairable_immediate"
        elif repairable and not alerted and incident_age<REPAIRABLE_GRACE_SECONDS:
            action="PENDING"
            reason="self_heal_grace"
        elif not alerted:
            action="ALERT"
            reason="repairable_grace_expired"
        elif last_alert is None or (now-last_alert).total_seconds()>=REMINDER_AFTER_SECONDS:
            action="ALERT"
            reason="persistent_reminder"
        else:
            action="NONE"
            reason="deduped_active_incident"

        return {
            "action":action,
            "reason":reason,
            "condition":condition,
            "codes":codes,
            "fingerprint":fp,
            "previous":previous,
            "repairable":repairable,
            "incident_started_at":incident_started.isoformat(),
            "incident_age_seconds":int(incident_age),
            "current_incident_alerted":alerted,
        }

    if previous=="CRITICAL" and bool(state.get("current_incident_alerted")):
        return {
            "action":"RECOVERY",
            "reason":"alerted_incident_recovered",
            "condition":"OK",
            "codes":[],
            "fingerprint":None,
            "previous":previous,
            "repairable":False,
            "incident_started_at":None,
            "incident_age_seconds":0,
            "current_incident_alerted":False,
        }

    return {
        "action":"NONE",
        "reason":"healthy_or_transient_recovered",
        "condition":"OK",
        "codes":[],
        "fingerprint":None,
        "previous":previous,
        "repairable":False,
        "incident_started_at":None,
        "incident_age_seconds":0,
        "current_incident_alerted":False,
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
            "?select=watch_id,last_condition,last_fingerprint,last_issue_codes,last_alert_at,last_recovery_at,"
            "incident_started_at,current_incident_alerted,updated_at"
            "&watch_id=eq."+urllib.parse.quote(WATCH_ID,safe="")
        )
        _,rows=self.request("GET",path)
        return rows[0] if rows else None

    def save(self,decision,state,now,alert_sent=False,recovery_sent=False):
        previous=state or {}
        same_incident=(
            decision["condition"]=="CRITICAL"
            and str(previous.get("last_condition") or "").upper()=="CRITICAL"
            and previous.get("last_fingerprint")==decision["fingerprint"]
        )
        if decision["condition"]=="CRITICAL":
            incident_started_at=decision["incident_started_at"]
            incident_alerted=(bool(previous.get("current_incident_alerted")) if same_incident else False) or alert_sent
        else:
            incident_started_at=None
            incident_alerted=False

        row={
            "watch_id":WATCH_ID,
            "last_condition":decision["condition"],
            "last_fingerprint":decision["fingerprint"],
            "last_issue_codes":decision["codes"],
            "last_alert_at":now.isoformat() if alert_sent else previous.get("last_alert_at"),
            "last_recovery_at":now.isoformat() if recovery_sent else previous.get("last_recovery_at"),
            "incident_started_at":incident_started_at,
            "current_incident_alerted":incident_alerted,
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

def format_alert(report,codes,reason):
    details=[]
    by_code={str(i.get("code")):i for i in report.get("issues",[]) if i.get("severity")=="CRITICAL"}
    for code in codes[:4]:
        detail=str((by_code.get(code) or {}).get("detail") or "").strip()
        details.append(code+(f": {detail[:160]}" if detail else ""))
    tail="" if len(codes)<=4 else f" (+{len(codes)-4} weitere)"
    if reason=="repairable_grace_expired":
        qualifier="Self-Heal nach 15 Min weiterhin erfolglos"
    elif reason=="persistent_reminder":
        qualifier="anhaltender kritischer Zustand"
    else:
        qualifier="sofortige Eskalation"
    return (
        "SYSTEMKRITISCH | Crypto-Prozess-Health | "
        +qualifier+" | "
        +"; ".join(details)+tail+
        " | Bitte Infrastruktur prüfen. Kein Handelssignal."
    )

def self_test():
    t=utcnow()
    healthy={"status":"HEALTHY","issues":[]}
    warning={"status":"WARNING","issues":[{"code":"NO_PAPER_TRADES","severity":"WARNING"}]}
    repairable_a={"status":"CRITICAL","issues":[{"code":"OVERDUE_WAIT","severity":"CRITICAL","repairable":True}]}
    repairable_b={"status":"CRITICAL","issues":[{"code":"STALE_scan.yml","severity":"CRITICAL","repairable":True}]}
    nonrepairable={"status":"CRITICAL","issues":[{"code":"BAD_JSON","severity":"CRITICAL","repairable":False}]}

    assert route_decision(healthy,None,t)["action"]=="NONE"
    assert route_decision(warning,None,t)["action"]=="NONE"

    first=route_decision(repairable_a,None,t)
    assert first["action"]=="PENDING"
    state_pending={
        "last_condition":"CRITICAL",
        "last_fingerprint":first["fingerprint"],
        "last_alert_at":None,
        "incident_started_at":first["incident_started_at"],
        "current_incident_alerted":False,
    }
    assert route_decision(repairable_a,state_pending,t+timedelta(minutes=10))["action"]=="PENDING"
    due=route_decision(repairable_a,state_pending,t+timedelta(minutes=16))
    assert due["action"]=="ALERT" and due["reason"]=="repairable_grace_expired"

    state_alerted={
        **state_pending,
        "last_alert_at":(t+timedelta(minutes=16)).isoformat(),
        "current_incident_alerted":True,
    }
    assert route_decision(repairable_a,state_alerted,t+timedelta(hours=1))["action"]=="NONE"
    assert route_decision(repairable_a,state_alerted,t+timedelta(hours=7))["action"]=="ALERT"
    assert route_decision(healthy,state_alerted,t+timedelta(hours=1))["action"]=="RECOVERY"

    # A transient repairable incident that heals inside the grace is silent.
    assert route_decision(healthy,state_pending,t+timedelta(minutes=5))["action"]=="NONE"

    # A changed repairable fingerprint starts a fresh grace window.
    changed=route_decision(repairable_b,state_alerted,t+timedelta(minutes=5))
    assert changed["action"]=="PENDING"
    assert changed["incident_started_at"]==(t+timedelta(minutes=5)).isoformat()

    # Non-repairable critical integrity/safety faults bypass the grace.
    immediate=route_decision(nonrepairable,None,t)
    assert immediate["action"]=="ALERT" and immediate["reason"]=="nonrepairable_immediate"

    print(
        "PROCESS_HEALTH_ALERT_ROUTER_SELFTEST PASS "
        "repairable-grace/nonrepairable-immediate/dedupe/6h-reminder/recovery"
    )
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
        post_slack(format_alert(report,decision["codes"],decision["reason"]))
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
        "reason":decision["reason"],
        "condition":decision["condition"],
        "critical_codes":decision["codes"],
        "previous":decision["previous"],
        "repairable":decision["repairable"],
        "incident_age_seconds":decision["incident_age_seconds"],
        "alert_sent":sent_alert,
        "recovery_sent":sent_recovery,
        "repairable_grace_seconds":REPAIRABLE_GRACE_SECONDS,
        "reminder_after_seconds":REMINDER_AFTER_SECONDS,
    },sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
