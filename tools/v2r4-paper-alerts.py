#!/usr/bin/env python3
"""Idempotent Slack outbox for the active V2R4 PAPER series."""
from __future__ import annotations
import hashlib, json, os, urllib.parse, urllib.request
from datetime import datetime, timezone

SERIES_PREFIX="V2R4"
LIFECYCLE_TYPES={"STAGE2_FILLED","TRAIL_TIER","CLOSED","DATA_GAP_UNVERIFIED"}

def utcnow():
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def env():
    url=os.environ.get("SUPABASE_URL","").strip().rstrip("/")
    key=(os.environ.get("SUPABASE_SECRET_KEY","").strip() or os.environ.get("SUPABASE_SERVICE_ROLE_KEY","").strip())
    webhook=os.environ.get("SLACK_WEBHOOK_URL","").strip()
    user=os.environ.get("SLACK_USER_ID","").strip()
    if not url or not key: raise RuntimeError("Supabase backend credentials missing")
    if not webhook or not user: raise RuntimeError("Slack webhook/user missing")
    return url,key,webhook,user

def headers(key,prefer=None):
    h={"apikey":key,"Content-Type":"application/json","User-Agent":"v2r4-paper-alerts/1.0"}
    if not key.startswith("sb_secret_"): h["Authorization"]="Bearer "+key
    if prefer: h["Prefer"]=prefer
    return h

def get(url,key,path):
    req=urllib.request.Request(url+"/rest/v1/"+path,headers=headers(key))
    with urllib.request.urlopen(req,timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def insert_receipt(url,key,row):
    req=urllib.request.Request(
        url+"/rest/v1/v2r4_paper_alert_receipts",
        data=json.dumps(row,separators=(",",":")).encode(),
        method="POST",
        headers=headers(key,"return=minimal"),
    )
    with urllib.request.urlopen(req,timeout=30) as resp:
        if not 200<=resp.status<300: raise RuntimeError(f"receipt HTTP {resp.status}")

def post_slack(webhook,text):
    req=urllib.request.Request(
        webhook,data=json.dumps({"text":text}).encode(),method="POST",
        headers={"Content-Type":"application/json","User-Agent":"v2r4-paper-alerts/1.0"},
    )
    with urllib.request.urlopen(req,timeout=20) as resp:
        body=resp.read().decode("utf-8","replace").strip()
        if not 200<=resp.status<300: raise RuntimeError(f"Slack HTTP {resp.status}: {body[:120]}")
    return utcnow()

def key_for(*parts):
    return hashlib.sha256("|".join(str(x or "") for x in parts).encode()).hexdigest()

def fmt(v,digits=4):
    if v is None: return "n/a"
    try:
        x=float(v)
        return f"{x:.{digits}f}".rstrip("0").rstrip(".")
    except Exception:
        return str(v)

def active_series(url,key):
    q=urllib.parse.urlencode({
        "status":"eq.active",
        "strategy_revision":"like.V2R4*",
        "select":"series_id,test_id,strategy_revision,started_at",
        "order":"started_at.desc",
        "limit":"1",
    },safe=".*,:")
    rows=get(url,key,"paper_series?"+q)
    return rows[0] if rows else None

def effective_buy(row):
    payload=row.get("payload") or {}
    for name in ("recheck","revalidation","decision"):
        rec=payload.get(name)
        if isinstance(rec,dict) and (rec.get("decision") or {}).get("decision")=="BUY_SCOUT" and rec.get("paper_entry"):
            return rec
    return None

def buy_text(user,row,rec):
    e=rec["paper_entry"]; s2=e.get("stage2_plan") or {}; d=rec.get("decision") or {}
    return (
        f"<@{user}> KRYPTOSIGNAL | {row['pair']} | PAPER BUY_SCOUT\n"
        f"Entry ~{fmt(e.get('fill_price_eur'))} EUR | Stop {fmt(e.get('stop_eur'))} EUR | "
        f"Scout {fmt(e.get('scout_notional_eur'),2)} EUR | "
        f"Stage 2 Trigger {fmt(s2.get('trigger_eur'))} EUR | Stage 2 {fmt(s2.get('notional_eur'),2)} EUR\n"
        f"Setup: {d.get('setup_lane','n/a')} | {str(d.get('summary') or '').strip()}\n"
        "Nur Paper-Test – keine Echtgeldorder."
    )

def lifecycle_text(user,pair,pos,event):
    typ=event.get("type")
    if typ=="STAGE2_FILLED":
        msg=f"PAPER STAGE2_FILLED | {fmt(event.get('notional_eur'),2)} EUR @ {fmt(event.get('fill_price_eur'))} EUR"
    elif typ=="TRAIL_TIER":
        msg=f"PAPER TRAIL_UPDATE | Stop {fmt(event.get('active_stop_eur'))} EUR | Trailing {fmt(event.get('trail_distance_pct'),2)}%"
    elif typ=="CLOSED":
        ex=pos.get("exit") or {}
        msg=f"PAPER EXIT | {event.get('reason','n/a')} | Netto {fmt(ex.get('net_pnl_eur'),2)} EUR ({fmt(ex.get('net_return_pct'),2)}%)"
    else:
        msg=f"PAPER DATA_QUALITY_CRITICAL | {event.get('reason','n/a')}"
    return f"<@{user}> KRYPTOSIGNAL | {pair} | {msg}\nNur Paper-Test – keine Echtgeldorder."

def main():
    url,key,webhook,user=env()
    series=active_series(url,key)
    if not series:
        print(json.dumps({"status":"SKIP_NO_ACTIVE_V2R4_SERIES"},sort_keys=True)); return
    sid=series["series_id"]
    sidq=urllib.parse.quote(sid,safe="")
    existing=get(url,key,f"v2r4_paper_alert_receipts?series_id=eq.{sidq}&select=event_key")
    sent={r["event_key"] for r in existing}
    delivered=0

    outcomes=get(url,key,f"paper_candidate_outcomes?series_id=eq.{sidq}&decision=eq.BUY_SCOUT&select=candidate_id,pair,payload")
    for row in outcomes:
        rec=effective_buy(row)
        if not rec: continue
        stamp=rec.get("recheck_completed_at_utc") or rec.get("revalidated_at_utc") or rec.get("evaluated_at_utc") or ""
        ek=key_for(sid,row["candidate_id"],"BUY_SCOUT",stamp)
        if ek in sent: continue
        accepted=post_slack(webhook,buy_text(user,row,rec))
        insert_receipt(url,key,{
            "event_key":ek,"series_id":sid,"candidate_id":row["candidate_id"],"pair":row["pair"],
            "event_type":"BUY_SCOUT","event_at":stamp or None,"slack_webhook_accepted_at":accepted,
            "payload":{"paper_only":True,"real_money_actions_enabled":False},
        })
        sent.add(ek); delivered+=1

    trades=get(url,key,f"paper_trade_results?series_id=eq.{sidq}&select=candidate_id,pair,payload")
    for row in trades:
        pos=row.get("payload") or {}
        if pos.get("real_money_actions_enabled") is not False:
            raise RuntimeError("unsafe position payload")
        for idx,event in enumerate(pos.get("events") or []):
            typ=event.get("type")
            if typ not in LIFECYCLE_TYPES: continue
            stamp=event.get("at_utc") or ""
            ek=key_for(sid,row["candidate_id"],idx,typ,stamp)
            if ek in sent: continue
            accepted=post_slack(webhook,lifecycle_text(user,row["pair"],pos,event))
            insert_receipt(url,key,{
                "event_key":ek,"series_id":sid,"candidate_id":row["candidate_id"],"pair":row["pair"],
                "event_type":typ,"event_at":stamp or None,"slack_webhook_accepted_at":accepted,
                "payload":{"paper_only":True,"real_money_actions_enabled":False,"event_index":idx},
            })
            sent.add(ek); delivered+=1

    print(json.dumps({"status":"PASS","series_id":sid,"delivered":delivered},sort_keys=True))

if __name__=="__main__":
    main()
