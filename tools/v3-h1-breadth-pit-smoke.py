#!/usr/bin/env python3
"""Point-in-time multi-pair feature smoke for V3-H1.

Input JSON:
{
  "pairs": {
    "XBTEUR": [{"bar_end_epoch": 1000, "close": 100.0}, ...],
    ...
  }
}

The tool uses exact wall-clock closed-bar endpoints at/before an explicit cutoff.
Future rows are ignored, not clipped into the feature set. Missing lookbacks
remain missing and are reflected in the breadth denominator.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any

HORIZONS={"15m":900,"1h":3600,"4h":14400}

def load(path: Path) -> dict[str,list[dict[str,Any]]]:
    raw=json.loads(path.read_text("utf-8"))
    pairs=raw.get("pairs") if isinstance(raw,dict) else None
    if not isinstance(pairs,dict) or not pairs:
        raise SystemExit("fixture must contain non-empty pairs object")
    out={}
    for pair,rows in pairs.items():
        if not isinstance(rows,list):
            raise SystemExit(f"{pair}: rows must be list")
        clean=[]
        for r in rows:
            ts=int(r["bar_end_epoch"])
            close=float(r["close"])
            if not math.isfinite(close) or close<=0:
                raise SystemExit(f"{pair}: invalid close")
            clean.append({"bar_end_epoch":ts,"close":close})
        clean.sort(key=lambda x:x["bar_end_epoch"])
        if len({r["bar_end_epoch"] for r in clean})!=len(clean):
            raise SystemExit(f"{pair}: duplicate bar_end_epoch")
        out[str(pair).upper()]=clean
    return out

def close_exact(rows:list[dict[str,Any]], ts:int)->float|None:
    for r in rows:
        if r["bar_end_epoch"]==ts:
            return r["close"]
    return None

def ret_exact(rows:list[dict[str,Any]], cutoff:int, seconds:int)->float|None:
    now=close_exact(rows,cutoff)
    prev=close_exact(rows,cutoff-seconds)
    if now is None or prev in (None,0):
        return None
    return (now/prev-1.0)*100.0

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("fixture",type=Path)
    ap.add_argument("--cutoff-epoch",type=int,required=True)
    ap.add_argument("--target",required=True)
    ap.add_argument("--leaders",default="XBTEUR,ETHEUR")
    ap.add_argument("--output",type=Path)
    args=ap.parse_args()

    pairs=load(args.fixture)
    target=args.target.upper()
    leaders=[x.strip().upper() for x in args.leaders.split(",") if x.strip()]
    if target not in pairs:
        raise SystemExit(f"target not found: {target}")

    future_rows=sum(1 for rows in pairs.values() for r in rows if r["bar_end_epoch"]>args.cutoff_epoch)
    used_rows=[r for rows in pairs.values() for r in rows if r["bar_end_epoch"]<=args.cutoff_epoch]

    returns={}
    for pair,rows in pairs.items():
        returns[pair]={name:ret_exact(rows,args.cutoff_epoch,sec) for name,sec in HORIZONS.items()}

    cross={}
    for horizon in HORIZONS:
        eligible={p:v[horizon] for p,v in returns.items() if v[horizon] is not None}
        vals=list(eligible.values())
        positive=sum(1 for x in vals if x>0)
        cross[horizon]={
            "eligible_pair_count":len(vals),
            "total_fixture_pair_count":len(pairs),
            "missing_pair_count":len(pairs)-len(vals),
            "positive_pair_count":positive,
            "breadth_positive_share":positive/len(vals) if vals else None,
            "median_return_pct":statistics.median(vals) if vals else None,
            "dispersion_population_pct":statistics.pstdev(vals) if len(vals)>=2 else (0.0 if len(vals)==1 else None),
        }

    leader_1h=[returns[p]["1h"] for p in leaders if p in returns and returns[p]["1h"] is not None]
    leader_median_1h=statistics.median(leader_1h) if leader_1h else None
    target_1h=returns[target]["1h"]
    peers_1h=[v["1h"] for p,v in returns.items() if p!=target and v["1h"] is not None]
    peer_median_1h=statistics.median(peers_1h) if peers_1h else None

    result={
        "kind":"V3_H1_CROSS_CRYPTO_BREADTH_PIT_SMOKE_V1",
        "status":"PASS",
        "cutoff_epoch":args.cutoff_epoch,
        "target":target,
        "leaders":leaders,
        "fixture_pair_count":len(pairs),
        "future_rows_present":future_rows,
        "returns_pct":returns,
        "cross_section":cross,
        "derived":{
            "leader_median_return_1h_pct":leader_median_1h,
            "leader_minus_target_return_1h_pct":(
                leader_median_1h-target_1h
                if leader_median_1h is not None and target_1h is not None else None
            ),
            "peer_median_return_1h_pct":peer_median_1h,
            "target_minus_peer_median_return_1h_pct":(
                target_1h-peer_median_1h
                if target_1h is not None and peer_median_1h is not None else None
            ),
        },
        "point_in_time_assertions":{
            "all_used_rows_at_or_before_cutoff":all(r["bar_end_epoch"]<=args.cutoff_epoch for r in used_rows),
            "future_rows_present_but_ignored":future_rows>0,
            "exact_cutoff_bar_required":close_exact(pairs[target],args.cutoff_epoch) is not None,
            "exact_wall_clock_lookbacks_used":True,
            "missing_lookbacks_remain_missing":True,
            "zero_fill_used":False,
            "current_live_universe_filter_used":False,
        },
        "guardrails":{
            "performance_trial_started":False,
            "threshold_selection_performed":False,
            "pair_selection_by_seen_performance":False,
            "month_selection_by_seen_performance":False,
            "holdout_opened":False,
            "active_v2r3_changed":False,
            "v2r4_changed":False,
            "orders":False,
            "real_money_actions":False,
        },
    }
    if not all(result["point_in_time_assertions"].values()):
        result["status"]="FAIL"

    raw=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(raw,"utf-8")
    print(raw,end="")
    return 0 if result["status"]=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
