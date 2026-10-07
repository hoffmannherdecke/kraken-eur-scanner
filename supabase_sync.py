#!/usr/bin/env python3
"""Optional secure Paper -> Supabase archive sync.

Requires SUPABASE_URL plus either SUPABASE_SECRET_KEY (preferred modern backend key)
or SUPABASE_SERVICE_ROLE_KEY (legacy JWT key) in the host environment.
Never commit either value. The script refuses publishable/anon-style keys.
"""
from __future__ import annotations
import json, os, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def load(path):
    return json.loads(path.read_text("utf-8"))

def _batches(rows, max_rows=50, max_bytes=900_000):
    batch=[]
    size=2
    for row in rows:
        encoded=json.dumps(row,separators=(",",":")).encode("utf-8")
        row_size=len(encoded)+(1 if batch else 0)
        if batch and (len(batch)>=max_rows or size+row_size>max_bytes):
            yield batch
            batch=[]
            size=2
        batch.append(row)
        size+=row_size
    if batch:
        yield batch

def post_rows(url,key,table,rows,on_conflict):
    if not rows:
        return
    endpoint=f"{url.rstrip('/')}/rest/v1/{table}?on_conflict={urllib.parse.quote(on_conflict)}"
    headers={
        "apikey":key,
        "Content-Type":"application/json",
        "Prefer":"resolution=merge-duplicates,return=minimal",
        "User-Agent":"kraken-paper-supabase-sync/1.2",
    }
    # Legacy service_role keys are JWTs and may be sent as Bearer tokens.
    # Modern sb_secret_ keys must be sent via apikey only.
    if not key.startswith("sb_secret_"):
        headers["Authorization"]="Bearer "+key

    total=0
    batches=0
    for batch in _batches(rows):
        payload=json.dumps(batch,separators=(",",":")).encode("utf-8")
        for attempt in range(3):
            req=urllib.request.Request(
                endpoint,
                data=payload,
                method="POST",
                headers=headers,
            )
            try:
                with urllib.request.urlopen(req,timeout=30) as resp:
                    if not 200<=resp.status<300:
                        raise RuntimeError(f"{table} HTTP {resp.status}")
                break
            except urllib.error.HTTPError as exc:
                # Retry only gateway/rate/transient server failures; schema/data
                # errors remain fail-fast so archive problems are visible.
                if exc.code not in (429,500,502,503,504) or attempt==2:
                    raise
                time.sleep(2**attempt)
            except (TimeoutError, urllib.error.URLError):
                if attempt==2:
                    raise
                time.sleep(2**attempt)
        total+=len(batch)
        batches+=1
    print(json.dumps({"archive_table":table,"rows":total,"batches":batches},sort_keys=True))

def main():
    url=os.environ.get("SUPABASE_URL","").strip()
    key=(
        os.environ.get("SUPABASE_SECRET_KEY","").strip()
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY","").strip()
    )
    if not url or not key:
        raise SystemExit("SUPABASE_URL / SUPABASE_SECRET_KEY (or legacy SUPABASE_SERVICE_ROLE_KEY) missing")
    low=key.lower()
    if low.startswith("sb_publishable_") or "anon" in low:
        raise SystemExit("Refusing non-secret Supabase key for archive writer")

    control=load(ROOT/"paper_runtime_control.json")
    if control.get("git_runtime_compatibility_mode")=="DISABLED_V2R4_LOCAL_SUPABASE_PRIMARY":
        print(json.dumps({"status":"SKIP_V2R4_LOCAL_RUNTIME_OWNS_ARCHIVE"},sort_keys=True))
        return
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
