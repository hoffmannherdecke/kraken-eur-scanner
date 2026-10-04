#!/usr/bin/env python3
"""MINI-PC watchdog for missing/delayed GitHub scanner cadence.

This tool never evaluates trades and never calls an order API. It only observes
GitHub Actions liveness for scan.yml and, after a bounded stale/failure gate,
may dispatch the existing scanner workflow. The normal 10-minute scanner
schedule remains authoritative; this is recovery-only.

A dedicated no-op workflow can be used to prove the local token's Actions-write
permission without creating an extra scanner/evaluator observation.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_REPO="hoffmannherdecke/kraken-eur-scanner"
DEFAULT_WORKFLOW="scan.yml"
DEFAULT_AUTH_SMOKE_WORKFLOW="minipc-dispatch-auth-smoke.yml"
STALE_AFTER_SECONDS=1200
FAILED_GRACE_SECONDS=300
MIN_DISPATCH_INTERVAL_SECONDS=900
ACTIVE_STATUSES={"queued","in_progress","requested","waiting","pending"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00","Z")


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z","+00:00")).astimezone(timezone.utc)


def atomic_json(path: Path,payload: dict[str,Any]) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n","utf-8")
    tmp.replace(path)


def load_json(path: Path) -> dict[str,Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return {}


def load_token(root: Path) -> str:
    env=os.environ.get("MINIPC_GITHUB_ACTIONS_TOKEN","").strip()
    if env:
        return env
    path=root/"Secrets"/"github-actions-dispatch-token.txt"
    return path.read_text("utf-8").strip() if path.exists() else ""


def api(token: str,method: str,url: str,body: dict[str,Any] | None=None) -> tuple[int,Any]:
    headers={
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"minipc-github-cadence-guard/1.0",
    }
    if token:
        headers["Authorization"]="Bearer "+token
    data=None
    if body is not None:
        headers["Content-Type"]="application/json"
        data=json.dumps(body,separators=(",",":")).encode("utf-8")
    req=urllib.request.Request(url,data=data,method=method,headers=headers)
    with urllib.request.urlopen(req,timeout=20) as resp:
        raw=resp.read().decode("utf-8","replace")
        return resp.status,(json.loads(raw) if raw else None)


def runs_url(repo: str,workflow: str) -> str:
    safe=urllib.parse.quote(workflow,safe="")
    return f"https://api.github.com/repos/{repo}/actions/workflows/{safe}/runs?per_page=10"


def dispatch_url(repo: str,workflow: str) -> str:
    safe=urllib.parse.quote(workflow,safe="")
    return f"https://api.github.com/repos/{repo}/actions/workflows/{safe}/dispatches"


def compact_run(run: dict[str,Any] | None,now: datetime) -> dict[str,Any] | None:
    if not run:
        return None
    created=parse_dt(run.get("created_at"))
    return {
        "id":run.get("id"),
        "event":run.get("event"),
        "status":run.get("status"),
        "conclusion":run.get("conclusion"),
        "created_at":run.get("created_at"),
        "age_seconds":int(max(0,(now-created).total_seconds())) if created else None,
    }


def choose_action(
    runs: list[dict[str,Any]],
    now: datetime,
    last_dispatch_at: datetime | None,
    stale_after_seconds: int=STALE_AFTER_SECONDS,
    failed_grace_seconds: int=FAILED_GRACE_SECONDS,
    min_dispatch_interval_seconds: int=MIN_DISPATCH_INTERVAL_SECONDS,
) -> dict[str,Any]:
    active=[r for r in runs if str(r.get("status") or "").lower() in ACTIVE_STATUSES]
    if active:
        return {"action":"SKIP_ACTIVE","reason":"scanner_run_already_active","latest":runs[0] if runs else active[0]}

    latest=runs[0] if runs else None
    if last_dispatch_at and (now-last_dispatch_at).total_seconds()<min_dispatch_interval_seconds:
        return {"action":"BACKOFF","reason":"bounded_dispatch_backoff","latest":latest}

    if latest is None:
        return {"action":"DISPATCH","reason":"no_scanner_run_history","latest":None}

    created=parse_dt(latest.get("created_at"))
    if created is None:
        return {"action":"DISPATCH","reason":"latest_run_timestamp_missing","latest":latest}
    age=max(0,(now-created).total_seconds())
    status=str(latest.get("status") or "").lower()
    conclusion=str(latest.get("conclusion") or "").lower()

    if status=="completed" and conclusion=="success" and age<=stale_after_seconds:
        return {"action":"NONE_FRESH","reason":"latest_success_within_recovery_window","latest":latest}

    if status=="completed" and conclusion!="success":
        if age<failed_grace_seconds:
            return {"action":"WAIT_FAILURE_GRACE","reason":"recent_failure_inside_grace","latest":latest}
        return {"action":"DISPATCH","reason":"latest_scanner_run_failed","latest":latest}

    if age>stale_after_seconds:
        return {"action":"DISPATCH","reason":"scanner_cadence_stale","latest":latest}

    return {"action":"NONE_FRESH","reason":"latest_run_within_recovery_window","latest":latest}


def fetch_runs(token: str,repo: str,workflow: str) -> list[dict[str,Any]]:
    status,payload=api(token,"GET",runs_url(repo,workflow))
    if status!=200 or not isinstance(payload,dict):
        raise RuntimeError(f"unexpected workflow-runs response HTTP {status}")
    rows=payload.get("workflow_runs") or []
    if not isinstance(rows,list):
        raise RuntimeError("workflow_runs is not a list")
    return rows


def dispatch(token: str,repo: str,workflow: str) -> None:
    status,_=api(token,"POST",dispatch_url(repo,workflow),{"ref":"main"})
    if status!=204:
        raise RuntimeError(f"workflow dispatch returned HTTP {status}")


def run_once(args: argparse.Namespace) -> dict[str,Any]:
    now=utcnow()
    state_path=args.trading_root/"State"/"github-cadence-guard.json"
    previous=load_json(state_path)
    previous_dispatch=parse_dt(previous.get("last_dispatch_at_utc"))
    report: dict[str,Any]={
        "schema_version":1,
        "kind":"MINIPC_GITHUB_CADENCE_GUARD_V1",
        "checked_at_utc":iso(now),
        "status":"UNKNOWN",
        "action":"NONE",
        "detail":"",
        "repo":args.repo,
        "workflow":args.workflow,
        "stale_after_seconds":args.stale_after_seconds,
        "failed_grace_seconds":args.failed_grace_seconds,
        "min_dispatch_interval_seconds":args.min_dispatch_interval_seconds,
        "last_dispatch_at_utc":previous.get("last_dispatch_at_utc"),
        "latest_scan_run":None,
        "guardrails":{
            "recovery_only":True,
            "strategy_changes":False,
            "threshold_changes":False,
            "evaluator_invoked_directly":False,
            "order_api":False,
            "real_money_actions":False,
        },
    }

    try:
        token=load_token(args.trading_root)
        if len(token)<20:
            raise RuntimeError("GitHub Actions dispatch token missing/too short")

        if args.verify_dispatch_auth:
            dispatch(token,args.repo,args.auth_smoke_workflow)
            report["status"]="HEALTHY"
            report["action"]="AUTH_SMOKE_DISPATCHED"
            report["detail"]="no-op Actions-write verification dispatched; scanner untouched"
            atomic_json(state_path,report)
            return report

        rows=fetch_runs(token,args.repo,args.workflow)
        decision=choose_action(
            rows,now,previous_dispatch,
            args.stale_after_seconds,args.failed_grace_seconds,args.min_dispatch_interval_seconds,
        )
        report["latest_scan_run"]=compact_run(decision.get("latest"),now)
        report["action"]=decision["action"]
        report["detail"]=decision["reason"]

        if decision["action"]=="DISPATCH":
            dispatch(token,args.repo,args.workflow)
            report["action"]="DISPATCHED_RECOVERY"
            report["last_dispatch_at_utc"]=iso(now)
            report["detail"]=decision["reason"]+"; existing scan.yml dispatched once"

        report["status"]="HEALTHY"
    except urllib.error.HTTPError as exc:
        # Never include Authorization/token data in state or logs.
        report["status"]="DEGRADED"
        report["action"]="ERROR"
        report["detail"]=f"GitHub HTTP {exc.code}: {str(exc.reason)[:160]}"
    except Exception as exc:
        report["status"]="DEGRADED"
        report["action"]="ERROR"
        report["detail"]=f"{type(exc).__name__}: {str(exc)[:220]}"

    atomic_json(state_path,report)
    return report


def self_test() -> int:
    t=datetime(2026,10,4,6,0,tzinfo=timezone.utc)
    fresh={"id":1,"status":"completed","conclusion":"success","created_at":iso(t)}
    stale={"id":2,"status":"completed","conclusion":"success","created_at":iso(t.replace(hour=5,minute=30))}
    failed={"id":3,"status":"completed","conclusion":"failure","created_at":iso(t.replace(minute=50,hour=5))}
    recent_failed={"id":4,"status":"completed","conclusion":"failure","created_at":iso(t.replace(minute=58,hour=5))}
    active={"id":5,"status":"in_progress","conclusion":None,"created_at":iso(t)}

    assert choose_action([fresh],t,None)["action"]=="NONE_FRESH"
    assert choose_action([active,fresh],t,None)["action"]=="SKIP_ACTIVE"
    assert choose_action([stale],t,None)["action"]=="DISPATCH"
    assert choose_action([],t,None)["action"]=="DISPATCH"
    assert choose_action([failed],t,None)["action"]=="DISPATCH"
    assert choose_action([recent_failed],t,None)["action"]=="WAIT_FAILURE_GRACE"
    assert choose_action([stale],t,t.replace(minute=55,hour=5))["action"]=="BACKOFF"
    print("MINIPC_GITHUB_CADENCE_GUARD_SELFTEST PASS fresh/active/stale/failure/backoff")
    return 0


def parse_args() -> argparse.Namespace:
    ap=argparse.ArgumentParser()
    ap.add_argument("--trading-root",type=Path,default=Path.home()/"Trading")
    ap.add_argument("--repo",default=DEFAULT_REPO)
    ap.add_argument("--workflow",default=DEFAULT_WORKFLOW)
    ap.add_argument("--auth-smoke-workflow",default=DEFAULT_AUTH_SMOKE_WORKFLOW)
    ap.add_argument("--stale-after-seconds",type=int,default=STALE_AFTER_SECONDS)
    ap.add_argument("--failed-grace-seconds",type=int,default=FAILED_GRACE_SECONDS)
    ap.add_argument("--min-dispatch-interval-seconds",type=int,default=MIN_DISPATCH_INTERVAL_SECONDS)
    ap.add_argument("--verify-dispatch-auth",action="store_true")
    ap.add_argument("--self-test",action="store_true")
    args=ap.parse_args()
    if args.stale_after_seconds<900:
        raise SystemExit("--stale-after-seconds must be >= 900 to preserve recovery-only behavior")
    if args.min_dispatch_interval_seconds<600:
        raise SystemExit("--min-dispatch-interval-seconds must be >= 600")
    return args


def main() -> int:
    args=parse_args()
    if args.self_test:
        return self_test()
    report=run_once(args)
    print(json.dumps(report,sort_keys=True),flush=True)
    return 0 if report["status"]=="HEALTHY" else 2


if __name__=="__main__":
    raise SystemExit(main())
