#!/usr/bin/env python3
"""Idempotent Slack outbox for the active V2R4 PAPER series."""
from __future__ import annotations
import hashlib, json, math, os, re, urllib.parse, urllib.request
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
    # Exactly one global Paper authority, not the first V2R4 row left behind
    # after a separately authorized, real V3 Cloud CAS cutover.
    q=urllib.parse.urlencode({
        "status":"eq.active",
        "select":"series_id,test_id,strategy_revision,started_at,config",
        "order":"started_at.desc",
        "limit":"2",
    },safe=".*,:")
    rows=get(url,key,"paper_series?"+q)
    if not isinstance(rows,list) or len(rows)>1:
        raise RuntimeError("PAPER_ALERT_ACTIVE_SERIES_CARDINALITY_NOT_ONE")
    if not rows: return None
    row=rows[0]
    sid,revision=row.get("series_id"),row.get("strategy_revision")
    if not isinstance(sid,str) or not isinstance(revision,str):
        raise RuntimeError("PAPER_ALERT_ACTIVE_SERIES_IDENTITY_MISSING")
    if (revision.startswith("V2R4-") and
            re.fullmatch(r"PAPER-V2R4-[0-9]{8}T[0-9]{6}Z",sid)):
        return row
    if (revision.startswith("V3-") and
            re.fullmatch(r"PAPER-V3-[0-9]{8}T[0-9]{6}Z",sid)):
        cfg=row.get("config")
        if (not isinstance(cfg,dict) or cfg.get("paper_only") is not True
                or cfg.get("real_money_actions_enabled") is not False):
            raise RuntimeError("V3_ALERT_NO_PAPER_ONLY_SERIES_AUTHORITY")
        return row
    raise RuntimeError("PAPER_ALERT_UNSUPPORTED_ACTIVE_SERIES")


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

def _v3_fill_pages(url,key,sid):
    # Bound work and GET volume within the existing hourly alert job.
    # Refuse to silently miss rows when the bounded inventory is exceeded.
    sidq=urllib.parse.quote(sid,safe="")
    all_rows=[]
    for offset in range(0,2000,200):
        q=(f"v3_paper_event_receipts?series_id=eq.{sidq}"
           "&phase=eq.PAPER_FILL&result=eq.PAPER_FILLED"
           "&select=event_id,series_id,candidate_id,pair,phase,result,"
           "source_known_at,content_sha256,payload"
           f"&order=received_at.asc&limit=200&offset={offset}")
        batch=get(url,key,q)
        if not isinstance(batch,list) or len(batch)>200:
            raise RuntimeError("V3_ALERT_RECEIPT_QUERY_UNTRUSTED")
        all_rows.extend(batch)
        if len(batch)<200: return all_rows
    raise RuntimeError("V3_ALERT_RECEIPT_PAGINATION_CAP_REACHED")


def _v3_single_source(url,key,sid,cid,phase):
    sidq=urllib.parse.quote(sid,safe="")
    cidq=urllib.parse.quote(cid,safe="")
    rows=get(url,key,
        f"v3_paper_event_receipts?series_id=eq.{sidq}&candidate_id=eq.{cidq}"
        f"&phase=eq.{phase}&select=event_id,series_id,candidate_id,pair,phase,result,"
        "source_known_at,payload&limit=2")
    if not isinstance(rows,list) or len(rows)!=1:
        raise RuntimeError("V3_ALERT_MISSING_UNIQUE_"+phase)
    return rows[0]


def _v3_original(row,sid,cid,pair,phase,result):
    if (not isinstance(row,dict) or row.get("series_id")!=sid
            or row.get("candidate_id")!=cid or row.get("pair")!=pair
            or row.get("phase")!=phase or row.get("result")!=result):
        raise RuntimeError("V3_ALERT_SOURCE_IDENTITY_MISMATCH")
    p=row.get("payload")
    if (not isinstance(p,dict)
            or p.get("kind")!="V3_EXPERIMENTAL_PAPER_CANDIDATE_EVENT_V1"
            or p.get("orders") is not False
            or p.get("real_money_actions") is not False
            or p.get("series_id")!=sid or p.get("candidate_id")!=cid
            or p.get("pair")!=pair or p.get("phase")!=phase
            or p.get("result")!=result
            or not isinstance(p.get("data"),dict)):
        raise RuntimeError("V3_ALERT_NOT_IMMUTABLE_PAPER_ORIGINAL")
    return p["data"]


def _v3_buy_from_originals(url,key,sid,row):
    cid,pair=row.get("candidate_id"),row.get("pair")
    event=row.get("event_id")
    if (not isinstance(cid,str) or not cid or not isinstance(pair,str)
            or not re.fullmatch(r"[A-Z0-9]{2,20}/EUR",pair)
            or not isinstance(event,str) or not re.fullmatch(r"[0-9a-f]{64}",event)
            or not isinstance(row.get("content_sha256"),str)
            or not re.fullmatch(r"[0-9a-f]{64}",row["content_sha256"])):
        raise RuntimeError("V3_ALERT_FILL_ORIGINAL_IDENTITY_INVALID")
    f=_v3_original(row,sid,cid,pair,"PAPER_FILL","PAPER_FILLED")
    p4=_v3_single_source(url,key,sid,cid,"P4_VALIDATION")
    pd=_v3_original(p4,sid,cid,pair,"P4_VALIDATION","BUY_SCOUT")
    model=_v3_single_source(url,key,sid,cid,"MODEL_RESPONSE")
    md=_v3_original(model,sid,cid,pair,"MODEL_RESPONSE","PASS")
    if (pd.get("p4_decision")!="BUY_SCOUT"
            or md.get("raw_model_decision")!="BUY_SCOUT"):
        raise RuntimeError("V3_ALERT_NO_ORIGINAL_MODEL_P4_BUY_CHAIN")
    def numeric(value):
        if type(value) not in (int,float) or not math.isfinite(value):
            raise RuntimeError("V3_ALERT_NONFINITE_FILL")
        return float(value)
    ask=numeric(f.get("paper_entry_ask_eur"))
    stop=numeric(f.get("validated_stop_eur"))
    stage2=numeric(f.get("validated_stage2_eur"))
    qty=numeric(f.get("paper_entry_qty"))
    fee=numeric(f.get("paper_entry_fee_eur"))
    original_ask=numeric(pd.get("ask_eur"))
    if (not 0<stop<ask<stage2 or qty<=0
            or abs(ask-original_ask)>1e-6*ask
            or abs(stop-numeric(pd.get("validated_stop_eur")))>1e-8
            or abs(stage2-numeric(pd.get("validated_stage2_eur")))>1e-8
            or abs(ask*qty-50.0)>0.001 or abs(fee-0.30)>0.00001):
        raise RuntimeError("V3_ALERT_FILL_MODEL_P4_ECONOMICS_MISMATCH")
    stamp=row.get("source_known_at")
    if not isinstance(stamp,str) or "T" not in stamp:
        raise RuntimeError("V3_ALERT_FILL_SOURCE_CLOCK_INVALID")
    return {"candidate_id":cid,"pair":pair,"event_id":event,
            "ask":ask,"stop":stop,"stage2":stage2,"fee":fee,
            "stamp":stamp}


def _v3_buy_text(user,buy):
    return (
        f"<@{user}> KRYPTOSIGNAL | {buy['pair']} | V3 PAPER BUY_SCOUT\\n"
        f"Original-Cloud-Fill: Entry {fmt(buy['ask'])} EUR | "
        f"Stop {fmt(buy['stop'])} EUR | Stage 2 {fmt(buy['stage2'])} EUR | "
        f"Scout 50 EUR, Gebuehr {fmt(buy['fee'],2)} EUR\\n"
        "Nur Paper-Test und bestaetigter Journal-Fill – keine Echtgeldorder."
    )


def _deliver_v3(url,key,webhook,user,series):
    if series["strategy_revision"].startswith("V3-"):
        _deliver_v3(url,key,webhook,user,series)
        return
    sid=series["series_id"]
    sidq=urllib.parse.quote(sid,safe="")
    receipts=get(url,key,
        f"v2r4_paper_alert_receipts?series_id=eq.{sidq}&select=event_key")
    if not isinstance(receipts,list):
        raise RuntimeError("V3_ALERT_DEDUPE_RECEIPTS_UNAVAILABLE")
    sent={r["event_key"] for r in receipts}
    # Resolve and validate all original positive chains BEFORE sending any
    # notification; a WAIT or P4-only BUY is never an actual Paper fill.
    buys=[]
    for row in _v3_fill_pages(url,key,sid):
        keyname=key_for("V3",sid,row.get("event_id"),"PAPER_FILL")
        if keyname in sent: continue
        buys.append((keyname,_v3_buy_from_originals(url,key,sid,row)))
    count=0
    for keyname,buy in buys:
        accepted=post_slack(webhook,_v3_buy_text(user,buy))
        insert_receipt(url,key,{
            "event_key":keyname,"series_id":sid,
            "candidate_id":buy["candidate_id"],"pair":buy["pair"],
            "event_type":"BUY_SCOUT","event_at":buy["stamp"],
            "slack_webhook_accepted_at":accepted,
            "payload":{"paper_only":True,"real_money_actions_enabled":False,
                       "source":"V3_ORIGINAL_PAPER_FILL",
                       "original_event_id":buy["event_id"]},
        })
        sent.add(keyname);count+=1
    print(json.dumps({"status":"PASS_V3_ORIGINAL_FILLS_ONLY",
                      "series_id":sid,"delivered":count},sort_keys=True))


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
