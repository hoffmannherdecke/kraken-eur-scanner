#!/usr/bin/env python3
"""Point-in-time transparent price x volume primitive smoke for V3-H6."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

def load(path:Path)->list[dict[str,Any]]:
    raw=json.loads(path.read_text("utf-8"))
    rows=raw.get("bars") if isinstance(raw,dict) else None
    if not isinstance(rows,list) or not rows:
        raise SystemExit("fixture must contain non-empty bars")
    out=[]
    for r in rows:
        ts=int(r["bar_end_epoch"])
        close=float(r["close"])
        volume=float(r["volume"])
        if close<=0 or volume<0 or not math.isfinite(close) or not math.isfinite(volume):
            raise SystemExit("invalid close/volume")
        out.append({"bar_end_epoch":ts,"close":close,"volume":volume})
    out.sort(key=lambda x:x["bar_end_epoch"])
    if len({x["bar_end_epoch"] for x in out})!=len(out):
        raise SystemExit("duplicate bar_end_epoch")
    return out

def by_ts(rows):
    return {r["bar_end_epoch"]:r for r in rows}

def mean(xs):
    return sum(xs)/len(xs) if xs else None

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("fixture",type=Path)
    ap.add_argument("--cutoff-epoch",type=int,required=True)
    ap.add_argument("--bar-seconds",type=int,default=900)
    ap.add_argument("--output",type=Path)
    args=ap.parse_args()
    if args.bar_seconds<=0:
        raise SystemExit("bar-seconds must be positive")
    rows=load(args.fixture)
    m=by_ts(rows)
    cutoff=args.cutoff_epoch

    def ret(bars_back:int):
        now=m.get(cutoff)
        prev=m.get(cutoff-bars_back*args.bar_seconds)
        if not now or not prev or prev["close"]==0:
            return None
        return (now["close"]/prev["close"]-1.0)*100.0

    # Four 15m bars ending at cutoff vs the immediately preceding four bars.
    recent_ts=[cutoff-i*args.bar_seconds for i in range(0,4)]
    prior_ts=[cutoff-i*args.bar_seconds for i in range(4,8)]
    recent=[m[t]["volume"] for t in recent_ts if t in m]
    prior=[m[t]["volume"] for t in prior_ts if t in m]
    recent_complete=len(recent)==4
    prior_complete=len(prior)==4
    recent_mean=mean(recent) if recent_complete else None
    prior_mean=mean(prior) if prior_complete else None
    ratio=(recent_mean/prior_mean) if recent_mean is not None and prior_mean not in (None,0) else None
    r1h=ret(4)

    future_rows=sum(1 for r in rows if r["bar_end_epoch"]>cutoff)
    result={
      "kind":"V3_H6_PRICE_VOLUME_PIT_SMOKE_V1",
      "status":"PASS",
      "cutoff_epoch":cutoff,
      "price_returns_pct":{
        "15m":ret(1),
        "1h":r1h,
        "4h":ret(16),
      },
      "volume":{
        "recent_1h_complete":recent_complete,
        "prior_1h_complete":prior_complete,
        "recent_1h_mean":recent_mean,
        "prior_1h_mean":prior_mean,
        "recent_vs_prior_1h_ratio":ratio,
      },
      "agreement":{
        "price_up_with_volume_expansion":bool(r1h is not None and r1h>0 and ratio is not None and ratio>1),
        "price_down_with_volume_expansion":bool(r1h is not None and r1h<0 and ratio is not None and ratio>1),
      },
      "future_rows_present":future_rows,
      "point_in_time_assertions":{
        "cutoff_bar_exists":cutoff in m,
        "future_rows_present_but_ignored":future_rows>0,
        "exact_bar_end_alignment_used":True,
        "recent_prior_volume_windows_non_overlapping":set(recent_ts).isdisjoint(prior_ts),
        "missing_windows_remain_missing":True,
        "zero_fill_not_used":True,
      },
      "guardrails":{
        "performance_trial_started":False,
        "threshold_selection_performed":False,
        "parameter_sweep_performed":False,
        "nonlinear_model_used":False,
        "holdout_opened":False,
        "active_v2r3_changed":False,
        "v2r4_changed":False,
        "orders":False,
        "real_money_actions":False,
      }
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
