#!/usr/bin/env python3
"""Bounded first real prospective V3-H2 candidate capture.

Attempts at most a few fresh candidates from one scanner handoff and stops
permanently once one useful mapped Kraken Futures capture exists. Research only:
no outcome join, thresholds, paper decision mutation, orders, or private API.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CAPTURE=ROOT/"tools/v3-h2-prospective-candidate-capture.py"

def useful(p:Path)->bool:
    try:
        d=json.loads(p.read_text("utf-8"))
    except Exception:
        return False
    return (
        d.get("status")=="PASS"
        and ((d.get("mapping") or {}).get("kraken_futures_symbol"))
        and any(s.get("status")=="CAPTURED" for s in d.get("states") or [])
        and ((d.get("guardrails") or {}).get("paper_decision_changed") is False)
        and ((d.get("guardrails") or {}).get("orders") is False)
        and ((d.get("guardrails") or {}).get("real_money_actions") is False)
    )

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--handoff-jsonl",type=Path,required=True)
    ap.add_argument("--source-run-id",required=True)
    ap.add_argument("--output-dir",type=Path,required=True)
    ap.add_argument("--max-attempts",type=int,default=3)
    a=ap.parse_args()
    a.output_dir.mkdir(parents=True,exist_ok=True)

    existing=[p for p in a.output_dir.glob("v3-h2-real-candidate-*.json") if useful(p)]
    if existing:
        print("V3_H2_FIRST_CAPTURE_ALREADY_COMPLETE "+str(sorted(existing)[0]))
        return 0

    rows=[json.loads(line) for line in a.handoff_jsonl.read_text("utf-8").splitlines() if line.strip()]
    snaps=[r for r in rows if r.get("kind")=="candidate_snapshot" and r.get("pair") and r.get("ts")]
    attempts=0
    for snap in snaps:
        if attempts>=max(1,a.max_attempts):
            break
        attempts+=1
        pair=str(snap["pair"])
        base=pair.split("/")[0]
        ts=int(snap["ts"])
        dt=datetime.fromtimestamp(ts,timezone.utc)
        pair_tag=pair.replace("/","-")
        cid=f"{dt.strftime('%Y%m%d-%H%M%S')}-{pair_tag}-r{int(a.source_run_id)}"
        tmp=a.output_dir/(".tmp-"+cid+".json")
        cmd=[
          sys.executable,str(CAPTURE),
          "--candidate-id",cid,
          "--base",base,
          "--event-utc",dt.isoformat().replace("+00:00","Z"),
          "--output",str(tmp)
        ]
        cp=subprocess.run(cmd,text=True,capture_output=True)
        if cp.returncode!=0:
            if tmp.exists(): tmp.unlink()
            print("V3_H2_FIRST_CAPTURE_ATTEMPT_FAIL "+json.dumps({"candidate_id":cid,"pair":pair,"detail":(cp.stderr or cp.stdout)[-240:]},sort_keys=True))
            continue
        if useful(tmp):
            target=a.output_dir/("v3-h2-real-candidate-"+cid+".json")
            tmp.replace(target)
            print("V3_H2_FIRST_CAPTURE_PASS "+json.dumps({"candidate_id":cid,"pair":pair,"path":str(target)},sort_keys=True))
            return 0
        try:
            d=json.loads(tmp.read_text("utf-8"))
            mapping=(d.get("mapping") or {}).get("kraken_futures_symbol")
        except Exception:
            mapping=None
        if tmp.exists(): tmp.unlink()
        print("V3_H2_FIRST_CAPTURE_NOT_USEFUL "+json.dumps({"candidate_id":cid,"pair":pair,"mapping":mapping},sort_keys=True))

    print("V3_H2_FIRST_CAPTURE_PENDING "+json.dumps({"attempts":attempts,"reason":"no fresh mapped candidate in this bounded scan"},sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
