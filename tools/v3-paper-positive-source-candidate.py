#!/usr/bin/env python3
"""Create actual V3 PAPER candidate only from a verified positive-source event.

Existing H5 news/H10 smart-money/H11 Polymarket curators supply a signed or
otherwise VERIFIED known-at event snapshot. This tool does not fetch websites
or start a recurring service. It prepares a real source-origin candidate to
the same Mini-PC V3 model+P4 pipeline, independently from scanner handoffs.
"""
from __future__ import annotations
import argparse,json,os
from pathlib import Path
from paper_evaluator.v3_paper_positive_source_entry_v1 import make_source_candidate
from paper_evaluator.v3_paper_minipc_one_candidate_v1 import now

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--existing-source-snapshot",type=Path,required=True)
    p.add_argument("--source",required=True,
                   choices=["news_sentiment","smart_money_h10","polymarket_h11"])
    p.add_argument("--pair",required=True)
    p.add_argument("--kraken-altname",required=True)
    p.add_argument("--output-candidate",type=Path,required=True)
    a=p.parse_args()
    source=json.loads(a.existing_source_snapshot.read_text("utf-8"))
    if not isinstance(source,dict):
        raise ValueError("source snapshots must be canonical JSON object")
    data=make_source_candidate(
        pair=a.pair,kraken_altname=a.kraken_altname,source_name=a.source,
        snapshot=source.get(a.source),
        decision_at_utc=now(),
        market_move=source.get("dynamic_move_radar"))
    output=a.output_candidate
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise ValueError("candidate directory must already be an isolated Paper host directory")
    fd=os.open(output,os.O_EXCL|os.O_CREAT|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as out:
        json.dump(data,out,sort_keys=True,allow_nan=False)
        out.write("\n");out.flush();os.fsync(out.fileno())
    print(json.dumps({"status":"REAL_VERIFIED_SOURCE_PAPER_CANDIDATE_CREATED",
                      "candidate_id":data["candidate_id"],
                      "source_name":a.source,"pair":data["pair"],
                      "next_action":"V3_MINIPC_ONE_CANDIDATE_WITH_SAME_VERIFIED_SOURCE_FILE",
                      "model_called":False,"orders":False}))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
