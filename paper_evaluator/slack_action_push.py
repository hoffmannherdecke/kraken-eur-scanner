#!/usr/bin/env python3
"""Reliable Slack outbox for actionable PAPER BUY_SCOUT decisions only."""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def fmt_num(value):
    if value is None:
        return "n/a"
    v=float(value)
    if abs(v)>=100:
        return f"{v:.2f}"
    if abs(v)>=1:
        return f"{v:.4f}".rstrip("0").rstrip(".")
    return f"{v:.6f}".rstrip("0").rstrip(".")

def utcnow():
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def post_slack(text):
    webhook=os.environ.get("SLACK_WEBHOOK_URL","").strip()
    if not webhook:
        raise RuntimeError("missing SLACK_WEBHOOK_URL")
    req=urllib.request.Request(
        webhook,
        data=json.dumps({"text":text}).encode("utf-8"),
        headers={"Content-Type":"application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req,timeout=15) as resp:
        body=resp.read().decode("utf-8","replace").strip()
        print(f"Slack response: {resp.status} {body}")
        if not 200<=resp.status<300:
            raise RuntimeError(f"Slack HTTP {resp.status}")
        return utcnow()

def load_json(path):
    return json.loads(path.read_text("utf-8"))

def discover_actionable(manifest_path):
    control=load_json(ROOT/"paper_runtime_control.json")
    series_id=control.get("series_id")
    paths=set()

    if manifest_path and manifest_path.exists():
        try:
            for raw in load_json(manifest_path):
                paths.add(ROOT/raw)
        except Exception as exc:
            print("WARN manifest unreadable",repr(exc))

    for directory in ("paper_decisions","paper_revalidations"):
        d=ROOT/directory
        if not d.exists():
            continue
        for p in d.glob("*.json"):
            try:
                rec=load_json(p)
            except Exception:
                continue
            if rec.get("series_id")!=series_id:
                continue
            if rec.get("decision",{}).get("decision")=="BUY_SCOUT" and rec.get("paper_entry"):
                paths.add(p)

    actionable=[]
    for p in sorted(paths):
        if not p.exists():
            continue
        rec=load_json(p)
        if rec.get("series_id")!=series_id:
            continue
        if rec.get("decision",{}).get("decision")!="BUY_SCOUT":
            continue
        if rec.get("real_money_actions_enabled") is not False:
            raise RuntimeError(f"unsafe real-money flag in {p}")
        entry=rec.get("paper_entry")
        if not entry or "FILLED_SIMULATED" not in str(entry.get("status","")):
            raise RuntimeError(f"BUY_SCOUT without simulated scout fill in {p}")
        actionable.append(rec)
    return series_id,actionable

def main():
    manifest=Path(sys.argv[1]) if len(sys.argv)>=2 else None
    series_id,actionable=discover_actionable(manifest)
    if not actionable:
        print("SLACK_NO_ACTIONABLE_PAPER_DECISIONS")
        return

    user_id=os.environ.get("SLACK_USER_ID","").strip()
    if not user_id:
        raise RuntimeError("missing SLACK_USER_ID")

    receipts=ROOT/"paper_alerts"
    receipts.mkdir(exist_ok=True)
    pending=0
    sent=0
    for record in actionable:
        d=record["decision"]
        entry=record["paper_entry"]
        pair=record["pair"]
        receipt_path=receipts/f"{record['candidate_id']}.json"
        if receipt_path.exists():
            print("SLACK_ACTION_PUSH_IDEMPOTENT",pair,record["candidate_id"])
            continue
        pending+=1
        text=(
            f"<@{user_id}> KRYPTOSIGNAL | {pair} | PAPER BUY_SCOUT\n"
            f"Entry ~{fmt_num(entry.get('fill_price_eur'))} EUR | "
            f"Stop {fmt_num(entry.get('stop_eur'))} EUR | "
            f"Scout {fmt_num(entry.get('scout_notional_eur'))} EUR (Simulation) | "
            f"Stage 2 Trigger {fmt_num((entry.get('stage2_plan') or {}).get('trigger_eur'))} EUR | "
            f"Stage 2 {fmt_num((entry.get('stage2_plan') or {}).get('notional_eur'))} EUR\n"
            f"Setup: {d.get('setup_lane','n/a')} | {d.get('summary','').strip()}\n"
            "Nur Paper-Test – keine Echtgeldorder."
        )
        accepted=post_slack(text)
        receipt={
            "schema_version":2,
            "kind":"PAPER_SLACK_ALERT_RECEIPT_V2",
            "candidate_id":record["candidate_id"],
            "series_id":series_id,
            "pair":pair,
            "decision":"BUY_SCOUT",
            "slack_webhook_accepted_at_utc":accepted,
            "real_money_actions_enabled":False,
            "delivery_scope":"Slack webhook accepted; device delivery is not observable here",
        }
        receipt_path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n","utf-8")
        sent+=1
        print("SLACK_ACTION_PUSH_SENT",pair,record["candidate_id"],accepted)

    print("SLACK_OUTBOX_SUMMARY",json.dumps({"series_id":series_id,"actionable":len(actionable),"pending_before_send":pending,"sent":sent},sort_keys=True))

if __name__=="__main__":
    main()
