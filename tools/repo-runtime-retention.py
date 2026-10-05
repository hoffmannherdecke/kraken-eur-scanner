#!/usr/bin/env python3
"""Bounded runtime-file retention for the source repository.

Git is code/config/release evidence. Supabase is the durable runtime/research archive.
During the frozen V2R3 compatibility window, active-series files remain in Git.
Closed/non-active files are removed only when their IDs are verified in Supabase.
"""
from __future__ import annotations
import argparse, json, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PAPER_DIRS=("paper_decisions","paper_revalidations","paper_positions","paper_followups")
H1_DIRS=("research/v3/shadow-runtime/h1-context","research/v3/shadow-runtime/h1-decisions")
FRESH_QUEUE_SECONDS=3*3600

def read_json(path:Path):
    try: return json.loads(path.read_text("utf-8"))
    except Exception: return None

def cid_of(path:Path,d):
    return str((d or {}).get("candidate_id") or path.stem)

def plan(root:Path, manifest:dict):
    control=read_json(root/"paper_runtime_control.json") or {}
    active=str(control.get("series_id") or "")
    archived=set(manifest.get("paper_candidate_ids") or [])
    retire=bool(manifest.get("retire_active_paper"))
    expected=int(manifest.get("active_candidate_outcomes") or 0)

    remove=[]
    kept_active=set()
    active_decisions=0
    old_ids=set()

    for dirname in PAPER_DIRS:
        droot=root/dirname
        if not droot.exists(): continue
        for path in sorted(droot.glob("*.json")):
            d=read_json(path)
            if not isinstance(d,dict):
                continue
            sid=str(d.get("series_id") or "")
            cid=cid_of(path,d)
            if sid==active and not retire:
                kept_active.add(cid)
                if dirname=="paper_decisions": active_decisions+=1
                continue
            if sid==active and retire:
                if cid not in archived:
                    raise SystemExit(f"refuse retire: active candidate not archived: {cid}")
                remove.append(path); continue
            if sid and sid!=active:
                if cid not in archived:
                    raise SystemExit(f"refuse cleanup: non-active candidate not archived: {cid}")
                old_ids.add(cid); remove.append(path)

    if retire and expected and active_decisions and active_decisions!=expected:
        raise SystemExit(f"refuse retire: local active decisions={active_decisions} expected={expected}")

    qroot=root/"handoff_queue"
    now=int(time.time())
    if qroot.exists():
        for path in sorted(qroot.glob("*.json")):
            d=read_json(path)
            if not isinstance(d,dict): continue
            cid=cid_of(path,d)
            ts=int(d.get("event_ts") or 0)
            fresh=bool(ts and 0 <= now-ts <= FRESH_QUEUE_SECONDS)
            if retire:
                if cid in archived or not fresh:
                    remove.append(path)
            elif cid in old_ids and cid in archived and not fresh:
                remove.append(path)

    h1_control=read_json(root/"research/v3/shadow-runtime/h1-control.json") or {}
    h1_status=read_json(root/"research/v3/shadow-runtime/h1-status.json") or {}
    h1_archive_ok=(
        h1_control.get("enabled") is False
        and h1_status.get("minimum_gate_met") is True
        and int(manifest.get("h1_evidence_rows") or 0) >= int(h1_status.get("shadow_records") or 0) >= 200
    )
    if h1_archive_ok:
        for dirname in H1_DIRS:
            droot=root/dirname
            if droot.exists():
                remove.extend(sorted(droot.glob("*.json")))

    # Alert receipts are operational audit noise after 30 days.
    aroot=root/"paper_alerts"
    cutoff=time.time()-30*86400
    if aroot.exists():
        for p in aroot.glob("*.json"):
            try:
                if p.stat().st_mtime < cutoff: remove.append(p)
            except OSError: pass

    # Deduplicate paths.
    unique=sorted(set(remove))
    return {
        "active_series_id":active,
        "retire_active_paper":retire,
        "active_decisions":active_decisions,
        "expected_active_candidate_outcomes":expected,
        "h1_archive_ok":h1_archive_ok,
        "remove":[str(p.relative_to(root)) for p in unique],
    }

def self_test():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        r=Path(td)
        for d in PAPER_DIRS+( "handoff_queue",):
            (r/d).mkdir(parents=True,exist_ok=True)
        (r/"research/v3/shadow-runtime/h1-context").mkdir(parents=True)
        (r/"research/v3/shadow-runtime/h1-decisions").mkdir(parents=True)
        (r/"paper_runtime_control.json").write_text(json.dumps({"series_id":"ACTIVE"}))
        (r/"paper_decisions/a.json").write_text(json.dumps({"series_id":"ACTIVE","candidate_id":"a"}))
        (r/"paper_decisions/b.json").write_text(json.dumps({"series_id":"OLD","candidate_id":"b"}))
        (r/"handoff_queue/b.json").write_text(json.dumps({"candidate_id":"b","event_ts":1}))
        (r/"research/v3/shadow-runtime/h1-control.json").write_text(json.dumps({"enabled":False}))
        (r/"research/v3/shadow-runtime/h1-status.json").write_text(json.dumps({"minimum_gate_met":True,"shadow_records":200}))
        (r/"research/v3/shadow-runtime/h1-context/x.json").write_text("{}")
        p=plan(r,{"paper_candidate_ids":["b"],"h1_evidence_rows":200})
        assert "paper_decisions/b.json" in p["remove"]
        assert "handoff_queue/b.json" in p["remove"]
        assert "paper_decisions/a.json" not in p["remove"]
        assert p["h1_archive_ok"] is True
    print("REPO_RUNTIME_RETENTION_SELF_TEST_PASS")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=Path,default=ROOT)
    ap.add_argument("--manifest",type=Path)
    ap.add_argument("--apply",action="store_true")
    ap.add_argument("--self-test",action="store_true")
    args=ap.parse_args()
    if args.self_test:
        self_test(); return 0
    if not args.manifest:
        raise SystemExit("--manifest required")
    manifest=json.loads(args.manifest.read_text("utf-8"))
    result=plan(args.root,manifest)
    print("RUNTIME_RETENTION_PLAN "+json.dumps({k:v for k,v in result.items() if k!="remove"},sort_keys=True))
    print("RUNTIME_RETENTION_REMOVE_COUNT",len(result["remove"]))
    if args.apply:
        for rel in result["remove"]:
            p=args.root/rel
            if p.exists(): p.unlink()
        print("RUNTIME_RETENTION_APPLIED",len(result["remove"]))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
