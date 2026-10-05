#!/usr/bin/env python3
"""Archive completed V3-H1 shadow pilot evidence to backend-only Supabase."""
from __future__ import annotations
import json, os, urllib.parse, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DECISIONS=ROOT/"research/v3/shadow-runtime/h1-decisions"
STATUS=ROOT/"research/v3/shadow-runtime/h1-status.json"
CONTROL=ROOT/"research/v3/shadow-runtime/h1-control.json"

def request(method,path,body=None,prefer=None):
    base=os.environ["SUPABASE_URL"].rstrip("/")
    key=(os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not key:
        raise RuntimeError("Supabase backend credential missing")
    headers={"apikey":key,"Content-Type":"application/json"}
    if not key.startswith("sb_secret_"):
        headers["Authorization"]="Bearer "+key
    if prefer:
        headers["Prefer"]=prefer
    data=None if body is None else json.dumps(body,separators=(",",":")).encode()
    req=urllib.request.Request(base+path,data=data,method=method,headers=headers)
    with urllib.request.urlopen(req,timeout=30) as resp:
        raw=resp.read().decode("utf-8","replace")
        return resp.status,(json.loads(raw) if raw else None)

def main():
    control=json.loads(CONTROL.read_text("utf-8"))
    status=json.loads(STATUS.read_text("utf-8"))
    if status.get("minimum_gate_met") is not True or int(status.get("shadow_records",0))!=200:
        raise SystemExit("H1 pilot is not at frozen 200-record completion gate")
    rows=[]
    for p in sorted(DECISIONS.glob("*.json")):
        d=json.loads(p.read_text("utf-8"))
        if d.get("shadow_candidate_id")!=control["shadow_candidate_id"]:
            raise SystemExit(f"unexpected shadow candidate in {p}")
        cid=d.get("candidate_id")
        if not cid:
            raise SystemExit(f"missing candidate id in {p}")
        rows.append({
            "candidate_id":cid,
            "shadow_candidate_id":d["shadow_candidate_id"],
            "baseline_series_id":d.get("series_id") or control["baseline_series_id"],
            "pair":d.get("pair"),
            "candidate_event_time":d.get("candidate_event_time_utc"),
            "status":d.get("status") or "UNKNOWN",
            "decision_diverged":bool(d.get("decision_diverged")),
            "payload":d,
            "source_commit":os.getenv("GITHUB_SHA"),
        })
    if len(rows)!=200:
        raise SystemExit(f"expected exactly 200 H1 decision records, found {len(rows)}")
    for i in range(0,len(rows),50):
        request("POST","/rest/v1/v3_h1_shadow_evidence?on_conflict=candidate_id",rows[i:i+50],
                "resolution=merge-duplicates,return=minimal")
    request("POST","/rest/v1/v3_h1_shadow_status?on_conflict=shadow_candidate_id",[{
        "shadow_candidate_id":status["shadow_candidate_id"],
        "generated_at":status["generated_at_utc"],
        "payload":status,
        "source_commit":os.getenv("GITHUB_SHA"),
    }],"resolution=merge-duplicates,return=minimal")
    _,summary=request("GET","/rest/v1/v3_h1_shadow_summary?select=*&shadow_candidate_id=eq."+
                      urllib.parse.quote(status["shadow_candidate_id"],safe=""))
    if not summary or int(summary[0]["shadow_records"])!=200 or int(summary[0]["pass_records"])!=200:
        raise SystemExit("Supabase H1 archive verification failed")
    print("V3_H1_ARCHIVE_PASS "+json.dumps(summary[0],sort_keys=True))
if __name__=="__main__":
    main()
