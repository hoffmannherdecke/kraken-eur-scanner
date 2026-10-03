#!/usr/bin/env python3
"""Build isolated V3-H1 same-scan relative-context sidecars.

Reads the scanner's candidates.jsonl, derives the fixed H1 relative-context
features from the full same-scan row set, and writes one sidecar per canonical
candidate. It never mutates the canonical handoff payload, paper decision, active
V2R3 runtime, orders, or any private account state.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any

LEADERS=("XBT/EUR","ETH/EUR")

def _num(v:Any)->float|None:
    try:
        x=float(v)
    except (TypeError,ValueError):
        return None
    return x if math.isfinite(x) else None

def derive(candidate:dict[str,Any], row_features:dict[str,dict[str,Any]])->dict[str,Any]:
    pair=str(candidate["pair"])
    target=_num((row_features.get(pair) or {}).get("ret1h"))
    leader_vals=[x for p in LEADERS if (x:=_num((row_features.get(p) or {}).get("ret1h"))) is not None]
    peer_vals=[]
    for p,row in row_features.items():
        if p==pair:
            continue
        x=_num((row or {}).get("ret1h"))
        if x is not None:
            peer_vals.append(x)
    leader_median=statistics.median(leader_vals) if leader_vals else None
    peer_median=statistics.median(peer_vals) if peer_vals else None
    leader_minus=(leader_median-target) if leader_median is not None and target is not None else None
    target_minus=(target-peer_median) if target is not None and peer_median is not None else None
    status="PASS" if leader_minus is not None and target_minus is not None else "MISSING_FAIL_CLOSED"
    return {
      "schema_version":1,
      "kind":"V3_H1_SHADOW_CONTEXT_SIDECAR_V1",
      "status":status,
      "shadow_candidate_id":"V3-H1-SHADOW-001",
      "candidate_id":candidate["candidate_id"],
      "queue_id":candidate["queue_id"],
      "pair":pair,
      "event_time_utc":candidate["event_time_utc"],
      "source_scanner_run_id":candidate["source_scanner_run_id"],
      "source":"SAME_SCANNER_RUN_FULL_ROW_SET",
      "leader_pairs":list(LEADERS),
      "features":{
        "target_return_1h_pct":target,
        "leader_median_return_1h_pct":leader_median,
        "leader_minus_target_return_1h_pct":leader_minus,
        "peer_median_return_1h_pct":peer_median,
        "target_minus_peer_median_return_1h_pct":target_minus,
        "eligible_peer_count":len(peer_vals),
        "available_leader_count":len(leader_vals)
      },
      "guardrails":{
        "canonical_handoff_mutated":False,
        "active_v2r3_changed":False,
        "threshold_search":False,
        "feature_transform_search":False,
        "orders":False,
        "real_money_actions":False
      }
    }

def self_test()->int:
    cand={"candidate_id":"C","queue_id":"Q","pair":"ALT/EUR","event_time_utc":"2026-01-01T00:00:00Z","source_scanner_run_id":1}
    rows={
      "XBT/EUR":{"ret1h":2.0},
      "ETH/EUR":{"ret1h":4.0},
      "ALT/EUR":{"ret1h":1.0},
      "A/EUR":{"ret1h":-1.0},
      "B/EUR":{"ret1h":3.0},
    }
    out=derive(cand,rows)
    assert out["status"]=="PASS"
    assert out["features"]["leader_median_return_1h_pct"]==3.0
    assert out["features"]["leader_minus_target_return_1h_pct"]==2.0
    assert out["features"]["peer_median_return_1h_pct"]==2.5
    assert out["features"]["target_minus_peer_median_return_1h_pct"]==-1.5
    assert out["features"]["eligible_peer_count"]==4
    print("V3_H1_SHADOW_CONTEXT_SELFTEST PASS same-scan/fixed-features/no-baseline-mutation")
    return 0

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--handoff-jsonl",type=Path)
    ap.add_argument("--candidate-manifest",type=Path)
    ap.add_argument("--output-dir",type=Path)
    ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.handoff_jsonl or not a.candidate_manifest or not a.output_dir:
        raise SystemExit("--handoff-jsonl, --candidate-manifest and --output-dir are required")
    rows=[json.loads(line) for line in a.handoff_jsonl.read_text("utf-8").splitlines() if line.strip()]
    row_features={r["pair"]:r["features"] for r in rows if (r.get("kind")=="row" or r.get("type")=="row") and r.get("pair") and isinstance(r.get("features"),dict)}
    manifest=json.loads(a.candidate_manifest.read_text("utf-8"))
    a.output_dir.mkdir(parents=True,exist_ok=True)
    written=[]
    for raw in manifest.get("candidate_files",[]):
        p=Path(raw)
        c=json.loads(p.read_text("utf-8"))
        out=derive(c,row_features)
        target=a.output_dir/(c["candidate_id"]+".json")
        encoded=json.dumps(out,indent=2,sort_keys=True)+"\n"
        if target.exists() and target.read_text("utf-8")!=encoded:
            raise SystemExit(f"H1 sidecar collision with different content: {target}")
        target.write_text(encoded,"utf-8")
        written.append({"candidate_id":c["candidate_id"],"status":out["status"],"path":str(target)})
    print("V3_H1_SHADOW_CONTEXT_WRITTEN "+json.dumps({"count":len(written),"items":written},sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
