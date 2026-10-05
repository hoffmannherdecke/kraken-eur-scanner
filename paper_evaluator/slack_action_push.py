#!/usr/bin/env python3
"""Reliable Slack outbox for actionable paper entries and position lifecycle events."""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIFECYCLE_PUSH_TYPES={"STAGE2_FILLED","TRAIL_TIER","CLOSED","DATA_GAP_UNVERIFIED"}

def fmt_num(value):
    if value is None:
        return "n/a"
    v=float(value)
    if abs(v)>=100:
        return f"{v:.2f}"
    if abs(v)>=1:
        return f"{v:.4f}".rstrip("0").rstrip(".")
    return f"{v:.6f}".rstrip("0").rstrip(".")

def fmt_signed(value, digits=2):
    if value is None:
        return "n/a"
    v=float(value)
    return f"{v:+.{digits}f}"

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

def lifecycle_receipt_path(receipts,position,event_index,event):
    typ=re.sub(r"[^A-Z0-9_-]+","_",str(event.get("type","UNKNOWN")).upper())
    return receipts/f"{position['candidate_id']}--lifecycle-{event_index:03d}-{typ}.json"

def discover_lifecycle(series_id,receipts):
    actions=[]
    directory=ROOT/"paper_positions"
    if not directory.exists():
        return actions
    for p in sorted(directory.glob("*.json")):
        try:
            position=load_json(p)
        except Exception:
            continue
        if position.get("series_id")!=series_id:
            continue
        if position.get("real_money_actions_enabled") is not False:
            raise RuntimeError(f"unsafe real-money flag in {p}")
        for index,event in enumerate(position.get("events") or []):
            if event.get("type") not in LIFECYCLE_PUSH_TYPES:
                continue
            receipt_path=lifecycle_receipt_path(receipts,position,index,event)
            if receipt_path.exists():
                continue
            actions.append((str(event.get("at_utc") or ""),position["candidate_id"],index,position,event,receipt_path))
    actions.sort(key=lambda x:(x[0],x[1],x[2]))
    return actions

def lifecycle_text(user_id,position,event):
    pair=position.get("pair","n/a")
    typ=event.get("type")
    if typ=="STAGE2_FILLED":
        return (
            f"<@{user_id}> KRYPTOSIGNAL | {pair} | PAPER STAGE2_FILLED\n"
            f"Stage 2 ~{fmt_num(event.get('fill_price_eur'))} EUR | "
            f"+{fmt_num(event.get('notional_eur'))} EUR | "
            f"Gesamt {fmt_num(position.get('entry_notional_eur'))} EUR | "
            f"Ø Entry {fmt_num(position.get('weighted_entry_eur'))} EUR | "
            f"Stop {fmt_num(position.get('active_stop_eur'))} EUR\n"
            "Nur Paper-Test – keine Echtgeldorder."
        )
    if typ=="TRAIL_TIER":
        return (
            f"<@{user_id}> KRYPTOSIGNAL | {pair} | PAPER TRAIL_UPDATE\n"
            f"Peak {fmt_num(event.get('peak_price_eur'))} EUR | "
            f"Trailing {fmt_num(event.get('trail_distance_pct'))}% | "
            f"neuer Stop {fmt_num(event.get('active_stop_eur'))} EUR\n"
            "Nur Paper-Test – keine Echtgeldorder."
        )
    if typ=="CLOSED":
        exit_rec=position.get("exit") or {}
        return (
            f"<@{user_id}> KRYPTOSIGNAL | {pair} | PAPER EXIT | {event.get('reason','n/a')}\n"
            f"Exit ~{fmt_num(event.get('fill_price_eur'))} EUR | "
            f"Netto {fmt_signed(exit_rec.get('net_pnl_eur'))} EUR "
            f"({fmt_signed(exit_rec.get('net_return_pct'))}%) | "
            f"Kapital {fmt_num(exit_rec.get('entry_notional_eur'))} EUR\n"
            "Position geschlossen (Simulation) – keine Echtgeldorder."
        )
    if typ=="DATA_GAP_UNVERIFIED":
        return (
            f"<@{user_id}> KRYPTOSIGNAL | {pair} | PAPER DATA_QUALITY_CRITICAL\n"
            f"Positions-Lifecycle ist wegen Datenlücke UNVERIFIED: {event.get('reason','n/a')}. "
            "Der Trade darf bis zur Klärung nicht als belastbares Ergebnis gezählt werden."
        )
    raise RuntimeError(f"unsupported lifecycle event {typ}")

def main():
    manifest=Path(sys.argv[1]) if len(sys.argv)>=2 else None
    series_id,actionable=discover_actionable(manifest)

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

    lifecycle=discover_lifecycle(series_id,receipts)
    for _,_,event_index,position,event,receipt_path in lifecycle:
        pending+=1
        text=lifecycle_text(user_id,position,event)
        accepted=post_slack(text)
        receipt={
            "schema_version":1,
            "kind":"PAPER_SLACK_LIFECYCLE_RECEIPT_V1",
            "candidate_id":position["candidate_id"],
            "series_id":series_id,
            "pair":position.get("pair"),
            "event_index":event_index,
            "event_type":event.get("type"),
            "event_at_utc":event.get("at_utc"),
            "slack_webhook_accepted_at_utc":accepted,
            "real_money_actions_enabled":False,
            "delivery_scope":"Slack webhook accepted; device delivery is not observable here",
        }
        receipt_path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n","utf-8")
        sent+=1
        print("SLACK_LIFECYCLE_PUSH_SENT",position.get("pair"),event.get("type"),position["candidate_id"],accepted)

    if not actionable and not lifecycle:
        print("SLACK_NO_ACTIONABLE_PAPER_EVENTS")
    print("SLACK_OUTBOX_SUMMARY",json.dumps({
        "series_id":series_id,
        "buy_actions":len(actionable),
        "lifecycle_pending":len(lifecycle),
        "pending_before_send":pending,
        "sent":sent,
    },sort_keys=True))

if __name__=="__main__":
    main()
