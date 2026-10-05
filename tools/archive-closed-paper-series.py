#!/usr/bin/env python3
"""Idempotently archive every non-active Paper series found in the repository.

This is migration/retention plumbing only. It never evaluates candidates, mutates
strategy decisions, creates orders, or changes the active series.
"""
from __future__ import annotations
import json, os, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(path:Path):
    return json.loads(path.read_text("utf-8"))

def batches(rows,max_rows=50,max_bytes=900_000):
    batch=[]; size=2
    for row in rows:
        enc=json.dumps(row,separators=(",",":")).encode()
        rs=len(enc)+(1 if batch else 0)
        if batch and (len(batch)>=max_rows or size+rs>max_bytes):
            yield batch; batch=[]; size=2
        batch.append(row); size+=rs
    if batch: yield batch

def post(table,rows,on_conflict):
    if not rows: return
    base=os.environ["SUPABASE_URL"].rstrip("/")
    key=(os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not key: raise RuntimeError("Supabase backend credential missing")
    headers={"apikey":key,"Content-Type":"application/json",
             "Prefer":"resolution=merge-duplicates,return=minimal"}
    if not key.startswith("sb_secret_"): headers["Authorization"]="Bearer "+key
    endpoint=f"{base}/rest/v1/{table}?on_conflict={urllib.parse.quote(on_conflict)}"
    for batch in batches(rows):
        payload=json.dumps(batch,separators=(",",":")).encode()
        for attempt in range(3):
            req=urllib.request.Request(endpoint,data=payload,method="POST",headers=headers)
            try:
                with urllib.request.urlopen(req,timeout=30) as resp:
                    if not 200<=resp.status<300: raise RuntimeError(f"{table} HTTP {resp.status}")
                break
            except urllib.error.HTTPError as exc:
                if exc.code not in (429,500,502,503,504) or attempt==2: raise
                time.sleep(2**attempt)

def get(path):
    base=os.environ["SUPABASE_URL"].rstrip("/")
    key=(os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    headers={"apikey":key}
    if not key.startswith("sb_secret_"): headers["Authorization"]="Bearer "+key
    with urllib.request.urlopen(urllib.request.Request(base+path,headers=headers),timeout=30) as resp:
        raw=resp.read().decode("utf-8","replace")
        return json.loads(raw) if raw else None

def main():
    active=load(ROOT/"paper_runtime_control.json")["series_id"]
    revals={}
    for p in (ROOT/"paper_revalidations").glob("*.json"):
        try:
            d=load(p)
        except Exception:
            continue
        sid=d.get("series_id"); cid=d.get("candidate_id")
        if sid and sid!=active and cid: revals[(sid,cid)]=d
    followups={}
    for p in (ROOT/"paper_followups").glob("*.json"):
        try:
            d=load(p)
        except Exception:
            continue
        sid=d.get("series_id"); cid=d.get("candidate_id")
        if sid and sid!=active and cid: followups[(sid,cid)]=d

    outcomes=[]; series_ids=set()
    for p in (ROOT/"paper_decisions").glob("*.json"):
        try:
            d=load(p)
        except Exception:
            continue
        sid=d.get("series_id"); cid=d.get("candidate_id")
        if not sid or sid==active or not cid:
            continue
        terminal=revals.get((sid,cid)) or d
        outcomes.append({
            "candidate_id":cid,
            "series_id":sid,
            "pair":d.get("pair"),
            "decision":terminal.get("decision",{}).get("decision",d.get("decision",{}).get("decision")),
            "evaluated_at":d.get("evaluated_at_utc") or d.get("created_at_utc"),
            "followup":followups.get((sid,cid)),
            "payload":{"decision":d,"revalidation":revals.get((sid,cid))},
        })
        series_ids.add(sid)

    trades=[]
    for p in (ROOT/"paper_positions").glob("*.json"):
        try:
            d=load(p)
        except Exception:
            continue
        sid=d.get("series_id"); cid=d.get("candidate_id")
        if not sid or sid==active or not cid: continue
        exit_=d.get("exit") or {}
        trades.append({
            "candidate_id":cid,"series_id":sid,"pair":d.get("pair"),
            "status":d.get("status"),"opened_at":d.get("opened_at_utc"),
            "closed_at":exit_.get("closed_at_utc"),"net_pnl_eur":exit_.get("net_pnl_eur"),
            "net_return_pct":exit_.get("net_return_pct"),"payload":d,
        })

    post("paper_candidate_outcomes",outcomes,"candidate_id")
    post("paper_trade_results",trades,"candidate_id")

    # Verify every repository closed-series decision is now represented server-side.
    missing=[]
    for sid in sorted(series_ids):
        expected={x["candidate_id"] for x in outcomes if x["series_id"]==sid}
        rows=[]; off=0
        while True:
            q="/rest/v1/paper_candidate_outcomes?select=candidate_id&series_id=eq."+urllib.parse.quote(sid,safe="")+
              f"&limit=1000&offset={off}"
            part=get(q) or []; rows.extend(part)
            if len(part)<1000: break
            off+=1000
        actual={x["candidate_id"] for x in rows}
        absent=sorted(expected-actual)
        if absent: missing.append({"series_id":sid,"missing":absent[:20],"count":len(absent)})
    if missing:
        raise SystemExit("CLOSED_SERIES_ARCHIVE_VERIFY_FAILED "+json.dumps(missing,sort_keys=True))
    print("CLOSED_SERIES_ARCHIVE_PASS "+json.dumps({
        "active_series_preserved":active,
        "closed_series":sorted(series_ids),
        "outcomes_upserted":len(outcomes),
        "trades_upserted":len(trades),
        "real_money_actions":False,
    },sort_keys=True))

if __name__=="__main__":
    main()
