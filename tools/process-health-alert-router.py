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
        # SKIP_ACTIVE_RUN is a safe concurrency gate, not a failed restart.
        skipped_scan=any(
            r.get("workflow")=="scan.yml" and r.get("action")=="SKIP_ACTIVE_RUN"
            for r in report.get("repairs",[])
        )
        qualifier=(
            "GitHub meldet Scanlauf weiter aktiv; paralleler Neustart sicherheitsbedingt blockiert"
            if skipped_scan else "Self-Heal nach 15 Min ohne bestätigte Erholung"
        )
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

    # A safety-preserving skip must not be described as a failed restart.
    delayed={**repairable_b, "repairs":[{"workflow":"scan.yml",
              "action":"SKIP_ACTIVE_RUN","reason":"STALE_scan.yml"}]}
    msg=format_alert(delayed,["STALE_scan.yml"],"repairable_grace_expired")
    assert "paralleler Neustart sicherheitsbedingt blockiert" in msg
    assert "erfolglos" not in msg
    assert "Kein Handelssignal" in msg if "Kein Handelssignal" in msg else "Keine Handelsaktion" in msg

    # Non-repairable critical integrity/safety faults bypass the grace.
    immediate=route_decision(nonrepairable,None,t)
    assert immediate["action"]=="ALERT" and immediate["reason"]=="nonrepairable_immediate"

    print(
        "PROCESS_HEALTH_ALERT_ROUTER_SELFTEST PASS "
        "repairable-grace/nonrepairable-immediate/dedupe/6h-reminder/recovery"
    )
    return 0


# Local watchdog extension: the existing decision policy is reused with
# independent per-component incident state on the existing protected host.
# No Supabase credentials, trading authority, or new scheduler are required.
LOCAL_CODES = {
    "LOCAL_GITHUB_UNREACHABLE": "GitHub API dauerhaft vom Mini-PC nicht erreichbar",
    "LOCAL_SUPABASE_UNREACHABLE": "Supabase-Verbindung oder Status-Relay dauerhaft gestoert",
    "LOCAL_ARCHIVE_DRIVES": "Mindestens ein Archivziel vom Watchdog nicht erreichbar",
    "LOCAL_ARCHIVE_JOB": "Automatische Archivierung: Ergebnis fehlt, ist ueberfaellig oder fehlgeschlagen",
    "LOCAL_ARCHIVE_COMPACTION": "Automatische physische Seitenfreigabe fehlgeschlagen",
    "LOCAL_SAFEACCESS_RESTART": "SafeAccess: wiederholte fehlgeschlagene Wiederanlaufversuche",
}
LOCAL_SAMPLE_GAP_SECONDS = REPAIRABLE_GRACE_SECONDS
LOCAL_RETRY_SECONDS = REPAIRABLE_GRACE_SECONDS

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def local_reachable(url):
    # Only an HTTP response header is needed. A 4xx response proves transport
    # reachability, not authentication or service correctness.
    req = urllib.request.Request(url, headers={"User-Agent":"minipc-watchdog/1.0"})
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=5) as resp:
            return 200 <= resp.status < 500
    except urllib.error.HTTPError as exc:
        return 400 <= exc.code < 500
    except Exception:
        return False

def local_age(value, now):
    try:
        dt = parse_dt(value)
        if dt is None:
            return None
        age = (now - dt).total_seconds()
        return age if age >= -5 else None
    except (ValueError, TypeError):
        return None

def local_task_result(value):
    # Windows scheduler state constants 0x41300..0x41308 are not exit failures.
    return isinstance(value, int) and value != 0 and not 0x41300 <= value <= 0x41308

def local_observations(sample, state, now, github_ok, supabase_ok):
    # True = fault, False = normal observation, None = unknown.
    faults = {}
    detail = {}
    faults["LOCAL_GITHUB_UNREACHABLE"] = not github_ok
    hb = sample.get("status_sync") or {}
    hb_age = local_age(hb.get("checked_at_utc"), now)
    relay_healthy = hb.get("status") == "HEALTHY" and hb_age is not None and hb_age <= 180
    relay_transport_failure = hb.get("status") == "DEGRADED" and hb_age is not None and hb_age <= 180 and hb.get("transport_failure") is True
    faults["LOCAL_SUPABASE_UNREACHABLE"] = (not supabase_ok and not relay_healthy) or relay_transport_failure
    detail["supabase_status_relay_fresh_healthy"] = relay_healthy
    detail["supabase_status_relay_status"] = hb.get("status") if hb.get("status") in ("HEALTHY","DEGRADED","UNKNOWN") else "UNKNOWN"

    drives = sample.get("drives") or {}
    values = [drives.get("c"), drives.get("mistral")]
    faults["LOCAL_ARCHIVE_DRIVES"] = True if False in values else False if all(v is True for v in values) else None
    archive = sample.get("archive") or {}
    age = local_age(archive.get("last_run"), now)
    task_state = archive.get("state")
    marks = set(archive.get("markers") or [])
    fresh_log = archive.get("log_matches_run") is True
    archive_ok = None
    if task_state in ("MISSING","Disabled"):
        archive_ok = False
    elif age is not None and age > 26 * 3600:
        archive_ok = False
    elif task_state == "Running":
        # Never judge an in-progress daily archive by its incomplete log.
        archive_ok = None
    elif task_state in ("Ready","Queued"):
        if local_task_result(archive.get("result")):
            archive_ok = False
        elif archive.get("result") == 0 and age is not None:
            archive_ok = fresh_log and bool(marks & {"NO_ARCHIVE_REQUIRED_PASS","ARCHIVE_MAINTENANCE_PASS"}) and "ARCHIVE_HOLD" not in marks
    faults["LOCAL_ARCHIVE_JOB"] = None if archive_ok is None else not archive_ok
    # An unneeded run, a bounded skip or no truncatable tail is not a failure.
    # Actual compaction exceptions are actionable; avoid double-reporting a
    # failed archive run as a separate compaction problem.
    physical = None
    if archive_ok is True:
        if "NO_ARCHIVE_REQUIRED_PASS" in marks:
            physical = False
        elif "PHYSICAL_COMPACTION_DEFERRED" in marks:
            physical = True
        elif marks & {"PHYSICAL_RELATION_BYTES_RELEASED","PHYSICAL_COMPACTION_NO_NEW_DELETE_SKIP","PHYSICAL_COMPACTION_BELOW_START_THRESHOLD_SKIP","PHYSICAL_COMPACTION_TARGET_MET"}:
            physical = False
        elif "ARCHIVE_MAINTENANCE_PASS" in marks:
            # Successful maintenance without a required outcome receipt is
            # unknown, not proof of compaction.
            physical = None
    faults["LOCAL_ARCHIVE_COMPACTION"] = physical
    detail["archive_result_markers"] = sorted(marks)
    detail["archive_physical_bytes_released"] = archive.get("physical_bytes")

    tunnel = sample.get("tunnel") or {}
    old_failures = state.get("tunnel_failed_runs") or []
    failures = set()
    for stamp in list(old_failures) + list(tunnel.get("failed_runs") or []):
        age = local_age(stamp, now)
        if age is not None and age <= 3600:
            failures.add(stamp)
    last_run = tunnel.get("last_run")
    run_age = local_age(last_run, now)
    if run_age is not None and run_age <= 3600 and local_task_result(tunnel.get("result")) and tunnel.get("state") != "Running":
        failures.add(last_run)
    ages = sorted(local_age(x, now) for x in failures)
    # Separate failures at least 45 seconds apart: do not count multiple
    # events belonging to one scheduler attempt as multiple recoveries.
    repeated = len(ages) >= 2 and ages[-1] - ages[0] >= 45
    retry_configured = (tunnel.get("restart_count") or 0) > 0
    running = tunnel.get("state") == "Running"
    stable = running and run_age is not None and run_age >= REPAIRABLE_GRACE_SECONDS and not any(a < run_age for a in ages)
    if stable:
        tunnel_fault = False
        failures.clear()
    elif retry_configured and (repeated or (state.get("tunnel_retry_failed") is True and not running)) and (not running or (ages and ages[0] <= REPAIRABLE_GRACE_SECONDS and run_age is not None and run_age < REPAIRABLE_GRACE_SECONDS)):
        tunnel_fault = True
    elif running and not repeated:
        # A scheduler running state is not a connectivity proof; it does
        # disprove a demonstrated failed-restart incident after stable run.
        tunnel_fault = None
    else:
        tunnel_fault = None
    faults["LOCAL_SAFEACCESS_RESTART"] = tunnel_fault
    detail["safeaccess_failed_attempts_observed"] = len(failures)
    detail["safeaccess_restart_configured"] = retry_configured
    detail["safeaccess_scheduler_running"] = running
    state["tunnel_failed_runs"] = sorted(failures)[-12:]
    if tunnel_fault is not None:
        state["tunnel_retry_failed"] = tunnel_fault
    return faults, detail

def local_report(code, fault):
    return {"issues":[{"code":code,"severity":"CRITICAL","repairable":True,"detail":LOCAL_CODES[code]}] if fault else []}

def local_state_row(decision, prior, now, sent=False, recovered=False):
    same = decision["condition"] == "CRITICAL" and prior.get("last_fingerprint") == decision["fingerprint"] and prior.get("last_condition") == "CRITICAL"
    return {
        "last_condition":decision["condition"],
        "last_fingerprint":decision["fingerprint"],
        "incident_started_at":decision["incident_started_at"],
        "current_incident_alerted":bool(same and prior.get("current_incident_alerted")) or sent,
        "last_alert_at":now.isoformat() if sent else prior.get("last_alert_at"),
        "last_recovery_at":now.isoformat() if recovered else prior.get("last_recovery_at"),
        "last_attempt_at":None if sent or recovered else prior.get("last_attempt_at"),
        "last_sample_at":now.isoformat(),
    }

def local_atomic(path, value):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(value,f,sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp,path)

def local_post(webhook, text):
    # Same existing channel and mention, but independent of the cloud state
    # backend. Never print an exception, request URI or response body.
    if not isinstance(webhook,str) or not __import__("re").fullmatch(r"https://hooks\.slack\.com/services/[-A-Za-z0-9_]+/[-A-Za-z0-9_]+/[-A-Za-z0-9_]+",webhook):
        return False
    payload=json.dumps({"text":"<@U0C39EDQ1H8> "+text}).encode("utf-8")
    req=urllib.request.Request(webhook,data=payload,method="POST",headers={"Content-Type":"application/json"})
    try:
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=10) as resp:
            return resp.status == 200 and resp.read(32).strip() == b"ok"
    except Exception:
        return False

def local_run(root, sample):
    import msvcrt
    secret_dir = root / "Runtime" / "WatchdogSecrets"
    state_path = secret_dir / "infra-alert-state.json"
    if sample.get("system") is not True:
        raise RuntimeError("SYSTEM_REQUIRED")
    # No concurrent local sends or state transitions.
    with (secret_dir / "infra-alert.lock").open("a+b") as lock:
        lock.seek(0,2)
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        now=utcnow()
        state=json.loads(state_path.read_text("utf-8")) if state_path.exists() else {"version":1,"incidents":{}}
        if state.get("version") != 1 or not isinstance(state.get("incidents"),dict):
            raise RuntimeError("LOCAL_STATE_INVALID")
        github_ok=local_reachable("https://api.github.com/repos/hoffmannherdecke/kraken-eur-scanner")
        supabase_ok=local_reachable("https://nlgzjmqgwueojlyqmoru.supabase.co/auth/v1/health")
        faults,detail=local_observations(sample,state,now,github_ok,supabase_ok)
        incidents=state["incidents"]
        due=[]
        recover=[]
        decisions={}
        output={}
        for code,fault in faults.items():
            prior=incidents.get(code) or {}
            if fault is None:
                output[code]="UNKNOWN"
                continue
            sample_age=local_age(prior.get("last_sample_at"),now)
            if fault and not prior.get("current_incident_alerted") and (sample_age is None or sample_age > LOCAL_SAMPLE_GAP_SECONDS):
                prior={}
            decision=route_decision(local_report(code,fault),prior,now)
            row=local_state_row(decision,prior,now)
            decisions[code]=(decision,prior)
            attempt_age=local_age(prior.get("last_attempt_at"),now)
            can_attempt=attempt_age is None or attempt_age >= LOCAL_RETRY_SECONDS
            if decision["action"] == "ALERT" and can_attempt:
                due.append(code)
                row["last_attempt_at"]=now.isoformat()
            elif decision["action"] == "RECOVERY":
                # Preserve the alerted incident until a recovery send succeeds.
                row=dict(prior,last_sample_at=now.isoformat())
                if can_attempt:
                    recover.append(code)
                    row["last_attempt_at"]=now.isoformat()
            incidents[code]=row
            output[code]="ACTIONABLE" if fault and (decision["action"]=="ALERT" or decision.get("current_incident_alerted")) else "PENDING" if fault else "OK"
        # Save before network send to bound retry after ambiguous delivery.
        request=secret_dir / "system-proof-request.txt"
        proof_id=request.read_text("utf-8").strip() if request.exists() else ""
        proof_due=bool(proof_id and len(proof_id)<=64 and state.get("proof_id")!=proof_id)
        if proof_due:
            state["proof_id"]=proof_id
            state["system_proof"]="ATTEMPTED"
        local_atomic(state_path,state)
        delivered=None
        if due or recover or proof_due:
            lines=[]
            if due:
                lines.append("SYSTEMKRITISCH | Lokaler Watchdog | "+ "; ".join(LOCAL_CODES[c] for c in due))
            if recover:
                lines.append("SYSTEM-RECOVERY | Lokaler Watchdog | "+ "; ".join(LOCAL_CODES[c] for c in recover))
            if not lines:
                lines.append("TECHNISCHER ABNAHMETEST | Lokaler Watchdog unter SYSTEM | Keine Stoerung.")
            lines.append("Nur Infrastruktur. Keine Handelsaktion.")
            delivered=local_post(sample.get("webhook"),"\n".join(lines))
            if delivered:
                for code in due+recover:
                    d,p=decisions[code]
                    incidents[code]=local_state_row(d,p,now,sent=code in due,recovered=code in recover)
            if proof_due:
                state["system_proof"]="PASS" if delivered else "HOLD"
            local_atomic(state_path,state)
        return {"kind":"LOCAL_INFRASTRUCTURE_MONITOR_V1","checked_at_utc":now.isoformat(),
                "observations":output,"detail":detail,"delivery_pass":delivered,
                "system_proof":state.get("system_proof","NOT_REQUESTED"),
                "system_proof_id":state.get("proof_id"),"no_trading_authority":True}

def local_self_test():
    t=utcnow()
    fresh=(t-timedelta(minutes=2)).isoformat()
    old=(t-timedelta(hours=6)).isoformat()
    sample={"status_sync":{"status":"HEALTHY","checked_at_utc":fresh},
            "drives":{"c":True,"mistral":True},
            "archive":{"state":"Ready","result":0,"last_run":old,"log_matches_run":True,
                       "markers":["NO_ARCHIVE_REQUIRED_PASS"]},
            "tunnel":{"state":"Running","last_run":old,"restart_count":999,"failed_runs":[]}}
    faults,_=local_observations(sample,{},t,True,True)
    assert all(v is False for v in faults.values())
    faults,_=local_observations(sample,{},t,False,False)
    assert faults["LOCAL_GITHUB_UNREACHABLE"] is True
    assert faults["LOCAL_SUPABASE_UNREACHABLE"] is False
    sample["status_sync"]["status"]="DEGRADED"
    faults,_=local_observations(sample,{},t,True,False)
    assert faults["LOCAL_SUPABASE_UNREACHABLE"] is True
    sample["status_sync"]["transport_failure"]=True
    faults,_=local_observations(sample,{},t,True,True)
    assert faults["LOCAL_SUPABASE_UNREACHABLE"] is True
    sample["drives"]["mistral"]=False
    faults,_=local_observations(sample,{},t,True,True)
    assert faults["LOCAL_ARCHIVE_DRIVES"] is True
    sample["archive"]["markers"]=["ARCHIVE_MAINTENANCE_PASS","PHYSICAL_COMPACTION_DEFERRED"]
    faults,_=local_observations(sample,{},t,True,True)
    assert faults["LOCAL_ARCHIVE_COMPACTION"] is True
    sample["archive"]["markers"]=["ARCHIVE_MAINTENANCE_PASS","PHYSICAL_RELATION_BYTES_RELEASED","PHYSICAL_TARGET_NOT_REACHED"]
    faults,_=local_observations(sample,{},t,True,True)
    assert faults["LOCAL_ARCHIVE_COMPACTION"] is False
    sample["archive"]["result"]=1
    faults,_=local_observations(sample,{},t,True,True)
    assert faults["LOCAL_ARCHIVE_JOB"] is True and faults["LOCAL_ARCHIVE_COMPACTION"] is None
    sample["tunnel"]={"state":"Ready","restart_count":999,"result":1,"last_run":fresh,"failed_runs":[]}
    faults,_=local_observations(sample,{},t,True,True)
    assert faults["LOCAL_SAFEACCESS_RESTART"] is None
    sample["tunnel"]["failed_runs"]=[(t-timedelta(minutes=4)).isoformat(),fresh]
    faults,_=local_observations(sample,{},t,True,True)
    assert faults["LOCAL_SAFEACCESS_RESTART"] is True
    sample["tunnel"]["restart_count"]=0
    faults,_=local_observations(sample,{},t,True,True)
    assert faults["LOCAL_SAFEACCESS_RESTART"] is None
    code="LOCAL_GITHUB_UNREACHABLE"
    first=route_decision(local_report(code,True),None,t)
    row=local_state_row(first,{},t)
    assert first["action"]=="PENDING"
    assert route_decision(local_report(code,True),row,t+timedelta(minutes=14))["action"]=="PENDING"
    due=route_decision(local_report(code,True),row,t+timedelta(minutes=16))
    assert due["action"]=="ALERT"
    row=local_state_row(due,row,t+timedelta(minutes=16),sent=True)
    assert route_decision(local_report(code,True),row,t+timedelta(hours=1))["action"]=="NONE"
    assert route_decision(local_report(code,False),row,t+timedelta(hours=1))["action"]=="RECOVERY"
    print("LOCAL_INFRASTRUCTURE_MONITOR_SELFTEST PASS")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("report",nargs="?",default="process_health.json")
    ap.add_argument("--self-test",action="store_true")
    ap.add_argument("--local-watchdog",type=Path)
    a=ap.parse_args()

    if a.self_test:
        local_self_test()
        return self_test()
    if a.local_watchdog:
        try:
            import sys
            sample=json.loads(sys.stdin.read(65536))
            print(json.dumps(local_run(a.local_watchdog,sample),sort_keys=True))
            return 0
        except Exception:
            print(json.dumps({"kind":"LOCAL_INFRASTRUCTURE_MONITOR_V1","status":"HOLD","no_trading_authority":True}))
            return 2

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
