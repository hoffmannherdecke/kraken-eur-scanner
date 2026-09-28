#!/usr/bin/env python3
"""Optional secure Paper -> Supabase archive sync.

Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in the host environment.
Never commit either value. The script refuses publishable/anon-style keys.
"""
from __future__ import annotations
import json, os, urllib.parse, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def load(path):
    return json.loads(path.read_text("utf-8"))

def post_rows(url,key,table,rows,on_conflict):
    if not rows:
        return
    endpoint=f"{url.rstrip('/')}/rest/v1/{table}?on_conflict={urllib.parse.quote(on_conflict)}"
    req=urllib.request.Request(
        endpoint,
        data=json.dumps(rows,separators=(",",":")).encode("utf-8"),
        method="POST",
        headers={
            "Authorization":"Bearer "+key,
            "apikey":key,
            "Content-Type":"application/json",
            "Prefer":"resolution=merge-duplicates,return=minimal",
            "User-Agent":"kraken-paper-supabase-sync/1.0",
        },
    )
    with urllib.request.urlopen(req,timeout=30) as resp:
        if not 200<=resp.status<300:
            raise RuntimeError(f"{table} HTTP {resp.status}")

def main():
    url=os.environ.get("SUPABASE_URL","").strip()
    key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY","").strip()
    if not url or not key:
        raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing")
    low=key.lower()
    if low.startswith("sb_publishable_") or "anon" in low:
        raise SystemExit("Refusing non-secret Supabase key for archive writer")

    control=load(ROOT/"paper_runtime_control.json")
    series_id=control["series_id"]
    spec=load(ROOT/"paper_strategy_spec.json")
    series=[{
        "series_id":series_id,
        "test_id":control["test_id"],
        "strategy_revision":spec["strategy_revision"],
        "started_at":control["series_started_at_utc"],
        "target_completed_trades":int(control.get("target_completed_paper_trades",20)),
        "status":"active" if control.get("enabled") else "paused",
        "config":control,
    }]

    revals={}
    for p in (ROOT/"paper_revalidations").glob("*.json") if (ROOT/"paper_revalidations").exists() else []:
        try:
            r=load(p)
            if r.get("series_id")==series_id: revals[p.name]=r
        except Exception:
            pass
    followups={}
    for p in (ROOT/"paper_followups").glob("*.json") if (ROOT/"paper_followups").exists() else []:
        try:
            r=load(p)
            if r.get("series_id")==series_id: followups[p.name]=r
        except Exception:
            pass

    candidates=[]
    for p in (ROOT/"paper_decisions").glob("*.json") if (ROOT/"paper_decisions").exists() else []:
        try: d=load(p)
        except Exception: continue
        if d.get("series_id")!=series_id: continue
        terminal=(revals.get(p.name) or d)
        candidates.append({
            "candidate_id":d["candidate_id"],
            "series_id":series_id,
            "pair":d["pair"],
            "decision":terminal.get("decision",{}).get("decision",d["decision"]["decision"]),
            "evaluated_at":d["evaluated_at_utc"],
            "followup":followups.get(p.name),
            "payload":{"decision":d,"revalidation":revals.get(p.name)},
        })

    trades=[]
    for p in (ROOT/"paper_positions").glob("*.json") if (ROOT/"paper_positions").exists() else []:
        try: s=load(p)
        except Exception: continue
        if s.get("series_id")!=series_id: continue
        exit_=s.get("exit") or {}
        trades.append({
            "candidate_id":s["candidate_id"],
            "series_id":series_id,
            "pair":s["pair"],
            "status":s["status"],
            "opened_at":s["opened_at_utc"],
            "closed_at":exit_.get("closed_at_utc"),
            "net_pnl_eur":exit_.get("net_pnl_eur"),
            "net_return_pct":exit_.get("net_return_pct"),
            "payload":s,
        })

    post_rows(url,key,"paper_series",series,"series_id")
    post_rows(url,key,"paper_candidate_outcomes",candidates,"candidate_id")
    post_rows(url,key,"paper_trade_results",trades,"candidate_id")
    print(json.dumps({"series_id":series_id,"candidates":len(candidates),"trades":len(trades)},sort_keys=True))

if __name__=="__main__":
    main()
