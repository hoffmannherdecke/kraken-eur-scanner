#!/usr/bin/env python3
"""Fail-closed compaction of repository runtime evidence already archived elsewhere.

Active V2R3 files are never touched. Closed series files are removed from the
current working tree only when their candidate IDs exist in Supabase. Historical
Git objects remain available through the pre-compaction archive ref.
"""
from __future__ import annotations
import argparse, json, os, urllib.parse, urllib.request
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"research/archive/runtime-compaction-20261005.json"
ARCHIVE_REF="archive/runtime-pre-compaction-20261005"

def request(path):
    base=os.environ["SUPABASE_URL"].rstrip("/")
    key=(os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not key:
        raise RuntimeError("Supabase backend credential missing")
    headers={"apikey":key}
    if not key.startswith("sb_secret_"):
        headers["Authorization"]="Bearer "+key
    req=urllib.request.Request(base+path,headers=headers)
    with urllib.request.urlopen(req,timeout=30) as resp:
        raw=resp.read().decode("utf-8","replace")
        return json.loads(raw) if raw else None

def archived_candidates():
    rows=[]; offset=0
    while True:
        batch=request(f"/rest/v1/paper_candidate_outcomes?select=candidate_id,series_id&limit=1000&offset={offset}") or []
        rows.extend(batch)
        if len(batch)<1000:
            break
        offset+=1000
    return {(r["series_id"],r["candidate_id"]) for r in rows}

def load_json(p):
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"invalid JSON blocks compaction: {p}: {exc}")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--apply",action="store_true")
    args=ap.parse_args()

    control=load_json(ROOT/"paper_runtime_control.json")
    active=control["series_id"]
    start=datetime.fromisoformat(control["series_started_at_utc"].replace("Z","+00:00")).timestamp()
    archived=archived_candidates()
    deletes=[]
    blocked=[]

    for dirname in ("paper_decisions","paper_revalidations","paper_followups","paper_positions"):
        d=ROOT/dirname
        if not d.exists(): continue
        for p in d.glob("*.json"):
            row=load_json(p)
            sid=row.get("series_id")
            cid=row.get("candidate_id")
            if sid==active:
                continue
            if not sid:
                # Legacy pre-series V1 evidence is small and retained in-tree.
                continue
            if not cid or (sid,cid) not in archived:
                blocked.append({"path":str(p.relative_to(ROOT)),"reason":"closed-series record not verified in Supabase"})
                continue
            deletes.append(p)

    # Canonical handoff queue is only a transient execution input. Pre-active
    # candidates remain available through Git history/archive ref and are not
    # needed by the frozen active-series evaluator.
    handoff=ROOT/"handoff_queue"
    if handoff.exists():
        for p in handoff.glob("*.json"):
            row=load_json(p)
            ts=row.get("event_ts")
            if ts is not None and float(ts)<start:
                deletes.append(p)

    # H1 pilot is complete and archived as full immutable decision payloads.
    summary=request("/rest/v1/v3_h1_shadow_summary?select=*&shadow_candidate_id=eq.V3-H1-SHADOW-001") or []
    status=load_json(ROOT/"research/v3/shadow-runtime/h1-status.json")
    h1_ok=(summary and int(summary[0].get("shadow_records",0))==200
           and int(summary[0].get("pass_records",0))==200
           and status.get("minimum_gate_met") is True)
    if not h1_ok:
        blocked.append({"path":"research/v3/shadow-runtime/h1-*","reason":"H1 Supabase archive not verified 200/200"})
    else:
        for dirname in ("research/v3/shadow-runtime/h1-context","research/v3/shadow-runtime/h1-decisions"):
            d=ROOT/dirname
            if d.exists():
                deletes.extend(d.glob("*.json"))

    # Never touch the active-series payloads.
    active_paths=[]
    for p in deletes:
        if p.parts[-2] in {"paper_decisions","paper_revalidations","paper_followups","paper_positions"}:
            row=load_json(p)
            if row.get("series_id")==active:
                active_paths.append(str(p.relative_to(ROOT)))
    if active_paths:
        blocked.append({"path":active_paths[:5],"reason":"active-series deletion candidate"})
    if blocked:
        print(json.dumps({"status":"BLOCKED","blocked":blocked[:20]},sort_keys=True))
        raise SystemExit(2)

    unique=sorted(set(deletes))
    by_dir={}
    bytes_removed=0
    for p in unique:
        rel=str(p.relative_to(ROOT))
        top="/".join(rel.split("/")[:4]) if rel.startswith("research/v3/shadow-runtime/") else rel.split("/")[0]
        by_dir[top]=by_dir.get(top,0)+1
        bytes_removed+=p.stat().st_size

    report={
        "schema_version":1,
        "kind":"REPOSITORY_RUNTIME_COMPACTION_V1",
        "generated_at_utc":datetime.utcnow().isoformat()+"Z",
        "active_series_preserved":active,
        "archive_ref":ARCHIVE_REF,
        "apply":bool(args.apply),
        "files_selected":len(unique),
        "bytes_selected":bytes_removed,
        "by_scope":by_dir,
        "closed_series_archive_verified":True,
        "h1_archive_verified":bool(h1_ok),
        "active_series_deleted":False,
        "strategy_changed":False,
        "real_money_actions":False,
    }
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n","utf-8")
    if args.apply:
        for p in unique:
            p.unlink()
    print("RUNTIME_COMPACTION "+json.dumps(report,sort_keys=True))
if __name__=="__main__":
    main()
