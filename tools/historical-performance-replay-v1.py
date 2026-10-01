#!/usr/bin/env python3
"""Execute frozen EUR15 price-volume continuation event-study V1.

Guardrails:
- uses only the frozen spec passed on CLI;
- scans normalized Kraken EUR 15m files locally/offline;
- never uses current live Kraken membership;
- requires exact 15m contiguous history and future windows;
- sealed 2026H1 holdout is not used for features, labels, selection or metrics;
- fixed thresholds/horizon/costs; no optimization or ranking;
- event-level study only, no portfolio equity-curve claim.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import os
import statistics
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

INTERVAL_SECONDS = 900
EXPECTED_HEADER = [
    "bar_start_epoch","bar_end_epoch","bar_start_utc","bar_end_utc",
    "open","high","low","close","volume","trades",
]

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk=fh.read(8*1024*1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def normalized_text_sha256(path: Path) -> str:
    text=path.read_text("utf-8")
    text=text.replace("\r\n","\n").replace("\r","\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def iso_epoch(s: str) -> int:
    return int(datetime.fromisoformat(s.replace("Z","+00:00")).timestamp())

def load_spec(path: Path) -> dict[str,Any]:
    s=json.loads(path.read_text("utf-8"))
    if s.get("kind")!="KRAKEN_EUR15_PERFORMANCE_REPLAY_SPEC_V1":
        raise ValueError("unexpected performance replay spec kind")
    if s.get("status")!="FROZEN_PRE_REGISTERED_NOT_YET_EXECUTED":
        raise ValueError("performance replay spec is not frozen pre-registered V1")
    if s["validation_topology"]["sealed_holdout"]["status"]!="LOCKED_DO_NOT_READ_IN_V1_SELECTION":
        raise ValueError("sealed holdout is not locked")
    return s

def pct(a: float,b: float) -> float:
    return 100.0*(a/b-1.0)

def contiguous(starts: list[int]) -> bool:
    return all((b-a)==INTERVAL_SECONDS for a,b in zip(starts,starts[1:]))

def summary(values: list[float]) -> dict[str,Any]:
    if not values:
        return {"count":0,"mean":None,"median":None,"positive_rate":None,"p10":None,"p90":None}
    ordered=sorted(values)
    def q(p: float) -> float:
        if len(ordered)==1:
            return ordered[0]
        pos=(len(ordered)-1)*p
        lo=math.floor(pos); hi=math.ceil(pos)
        if lo==hi:
            return ordered[lo]
        return ordered[lo]*(hi-pos)+ordered[hi]*(pos-lo)
    return {
        "count":len(values),
        "mean":round(statistics.fmean(values),12),
        "median":round(statistics.median(values),12),
        "positive_rate":round(sum(1 for v in values if v>0)/len(values),12),
        "p10":round(q(0.10),12),
        "p90":round(q(0.90),12),
    }

def read_pair(path: Path, holdout_start_epoch: int) -> tuple[list[dict[str,Any]],dict[str,Any]]:
    rows=[]
    stopped_at_holdout=False
    with gzip.open(path,"rt",encoding="utf-8",newline="") as fh:
        reader=csv.DictReader(fh)
        if reader.fieldnames!=EXPECTED_HEADER:
            raise ValueError(f"{path.name}: unexpected normalized header")
        prev=None
        for line_no,row in enumerate(reader,2):
            start=int(row["bar_start_epoch"])
            if start>=holdout_start_epoch:
                stopped_at_holdout=True
                break
            end=int(row["bar_end_epoch"])
            if end-start!=INTERVAL_SECONDS:
                raise ValueError(f"{path.name}:{line_no}: invalid bar duration")
            if prev is not None and start<=prev:
                raise ValueError(f"{path.name}:{line_no}: non-monotonic timestamp")
            prev=start
            rows.append({
                "start":start,"end":end,
                "start_utc":row["bar_start_utc"],"end_utc":row["bar_end_utc"],
                "open":float(row["open"]),"high":float(row["high"]),
                "low":float(row["low"]),"close":float(row["close"]),
                "volume":float(row["volume"]),"trades":int(row["trades"]),
            })
    return rows,{"stopped_at_holdout":stopped_at_holdout,"pre_holdout_rows":len(rows)}

def split_for(decision_epoch: int, topo: dict[str,Any]) -> str|None:
    for name in ("research_train","calibration","validation"):
        w=topo[name]
        if iso_epoch(w["start_utc"])<=decision_epoch<iso_epoch(w["end_utc_exclusive"]):
            return name
    return None

def same_split_horizon(split: str, last_future_end: int, topo: dict[str,Any]) -> bool:
    return last_future_end<=iso_epoch(topo[split]["end_utc_exclusive"])

def event_metrics(events: list[dict[str,Any]], costs: list[float]) -> dict[str,Any]:
    out={}
    gross=[e["gross_return_pct"] for e in events]
    out["gross"]=summary(gross)
    out["mfe"]=summary([e["mfe_pct"] for e in events])
    out["mae"]=summary([e["mae_pct"] for e in events])
    out["net_by_round_trip_cost_pct"]={
        f"{cost:.2f}":summary([e["gross_return_pct"]-cost for e in events])
        for cost in costs
    }
    pair_counts=Counter(e["pair"] for e in events)
    month_counts=Counter(e["decision_time_utc"][:7] for e in events)
    top10=sum(v for _,v in pair_counts.most_common(10))
    out["pair_concentration_share_top10"]=round(top10/len(events),12) if events else None
    out["events_by_pair"]=dict(sorted(pair_counts.items()))
    out["events_by_calendar_month"]=dict(sorted(month_counts.items()))
    return out

def deterministic_gzip_jsonl(path: Path, rows: list[dict[str,Any]]) -> str:
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmpname=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent)
    os.close(fd)
    tmp=Path(tmpname)
    try:
        with tmp.open("wb") as raw:
            with gzip.GzipFile(fileobj=raw,mode="wb",mtime=0,filename="") as gz:
                with io.TextIOWrapper(gz,encoding="utf-8",newline="") as out:
                    for row in rows:
                        out.write(json.dumps(row,sort_keys=True,separators=(",",":"))+"\n")
        digest=sha256_file(tmp)
        os.replace(tmp,path)
        return digest
    finally:
        tmp.unlink(missing_ok=True)

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("normalized_dir",type=Path)
    ap.add_argument("--spec",type=Path,required=True)
    ap.add_argument("--normalization-catalog",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--events-output",type=Path,required=True)
    ap.add_argument("--expected-count",type=int,default=648)
    args=ap.parse_args()

    spec=load_spec(args.spec)
    spec_sha=normalized_text_sha256(args.spec)
    norm=json.loads(args.normalization_catalog.read_text("utf-8"))
    if norm.get("status")!="PASS":
        raise SystemExit("normalization catalog status is not PASS")
    if int(norm.get("file_count",-1))!=args.expected_count:
        raise SystemExit("normalization catalog file_count mismatch")

    files=sorted(args.normalized_dir.glob("*EUR_15.normalized.csv.gz"),key=lambda p:p.name.upper())
    if len(files)!=args.expected_count:
        raise SystemExit(f"normalized file count mismatch: expected {args.expected_count}, got {len(files)}")

    topo=spec["validation_topology"]
    holdout_start=iso_epoch(topo["sealed_holdout"]["start_utc"])
    history=int(spec["eligibility"]["required_contiguous_history_bars"])
    future=int(spec["eligibility"]["required_contiguous_future_bars"])
    cooldown=int(spec["eligibility"]["same_pair_cooldown_bars_after_signal"])
    min_trades=int(spec["eligibility"]["min_trades_last_15m"])
    cond={c["feature"]:float(c["value"]) for c in spec["signal"]["all_conditions_required"]}
    costs=[float(x) for x in spec["cost_model"]["cost_sensitivity_report_pct_round_trip"]]

    events=[]
    file_stats=[]
    for file_index,path in enumerate(files,1):
        rows,meta=read_pair(path,holdout_start)
        pair=path.name.split("_15.normalized.csv.gz")[0].upper()
        signals=0
        last_signal_idx=-10**12

        for idx in range(max(history-1,12),len(rows)-future):
            if idx<=last_signal_idx+cooldown:
                continue

            hist=rows[idx-(history-1):idx+1]
            fut=rows[idx+1:idx+1+future]
            if len(hist)!=history or len(fut)!=future:
                continue
            starts=[r["start"] for r in hist]
            if not contiguous(starts):
                continue
            if rows[idx+1]["start"]!=rows[idx]["end"]:
                continue
            if not contiguous([rows[idx]["start"]]+[r["start"] for r in fut]):
                continue

            decision=rows[idx]
            split=split_for(decision["end"],topo)
            if split is None:
                continue
            if not same_split_horizon(split,fut[-1]["end"],topo):
                continue
            if decision["trades"]<min_trades:
                continue

            mean_vol=statistics.fmean(r["volume"] for r in hist)
            mean_trades=statistics.fmean(r["trades"] for r in hist)
            if mean_vol<=0 or mean_trades<=0:
                continue

            features={
                "return_1h_pct":pct(decision["close"],rows[idx-4]["close"]),
                "return_3h_pct":pct(decision["close"],rows[idx-12]["close"]),
                "volume_ratio_15m_vs_20":decision["volume"]/mean_vol,
                "trades_ratio_15m_vs_20":decision["trades"]/mean_trades,
            }
            if not (
                features["return_1h_pct"]>=cond["return_1h_pct"]
                and features["return_3h_pct"]>=cond["return_3h_pct"]
                and features["volume_ratio_15m_vs_20"]>=cond["volume_ratio_15m_vs_20"]
                and features["trades_ratio_15m_vs_20"]>=cond["trades_ratio_15m_vs_20"]
            ):
                continue

            entry=fut[0]["open"]
            exit_price=fut[-1]["close"]
            if entry<=0 or exit_price<=0:
                continue
            gross=pct(exit_price,entry)
            mfe=pct(max(r["high"] for r in fut),entry)
            mae=pct(min(r["low"] for r in fut),entry)
            event={
                "pair":pair,
                "split":split,
                "decision_time_utc":decision["end_utc"],
                "decision_epoch":decision["end"],
                "entry_time_utc":fut[0]["start_utc"],
                "exit_time_utc":fut[-1]["end_utc"],
                "entry_open":entry,
                "exit_close":exit_price,
                "gross_return_pct":round(gross,12),
                "mfe_pct":round(mfe,12),
                "mae_pct":round(mae,12),
                "features":{k:round(v,12) for k,v in features.items()},
            }
            events.append(event)
            signals+=1
            last_signal_idx=idx

        file_stats.append({
            "pair":pair,
            "pre_holdout_rows":meta["pre_holdout_rows"],
            "stopped_at_holdout_boundary":meta["stopped_at_holdout"],
            "signals":signals,
        })
        if file_index%25==0 or file_index==len(files):
            print(
                f"PERF_V1_SCAN progress={file_index}/{len(files)} events={len(events)}",
                flush=True,
            )

    split_events={
        name:[e for e in events if e["split"]==name]
        for name in ("research_train","calibration","validation")
    }
    split_metrics={name:event_metrics(es,costs) for name,es in split_events.items()}
    primary_cost=float(spec["cost_model"]["primary_cost_for_trial_selection_pct_round_trip"])
    validation_net=[e["gross_return_pct"]-primary_cost for e in split_events["validation"]]

    events_sha=deterministic_gzip_jsonl(args.events_output,events)
    holdout_event_count=sum(1 for e in events if e["decision_epoch"]>=holdout_start)
    if holdout_event_count:
        raise AssertionError("sealed holdout event leaked into V1 output")

    result={
        "kind":"KRAKEN_EUR15_PERFORMANCE_REPLAY_V1_RESULT",
        "status":"PASS",
        "spec":str(args.spec),
        "spec_sha256":spec_sha,
        "normalization_catalog":str(args.normalization_catalog),
        "normalization_catalog_sha256":sha256_file(args.normalization_catalog),
        "normalized_file_count":len(files),
        "total_event_count":len(events),
        "split_event_counts":{k:len(v) for k,v in split_events.items()},
        "metrics_by_split":split_metrics,
        "primary_validation_metrics":{
            "round_trip_cost_pct":primary_cost,
            "validation_event_count":len(validation_net),
            "validation_mean_net_return_pct":round(statistics.fmean(validation_net),12) if validation_net else None,
            "validation_median_net_return_pct":round(statistics.median(validation_net),12) if validation_net else None,
            "validation_positive_net_rate":round(sum(1 for v in validation_net if v>0)/len(validation_net),12) if validation_net else None,
        },
        "events_output":str(args.events_output),
        "events_output_sha256":events_sha,
        "file_stats":file_stats,
        "holdout_guard":{
            "holdout_start_utc":topo["sealed_holdout"]["start_utc"],
            "holdout_status":topo["sealed_holdout"]["status"],
            "holdout_events_generated":holdout_event_count,
            "holdout_metrics_computed":False,
            "holdout_used_for_threshold_selection":False,
        },
        "execution_semantics":{
            "entry":"next contiguous 15m bar open",
            "exit":"16th contiguous future 15m bar close",
            "cost_application":"event gross return percentage minus frozen total round-trip cost percentage",
            "portfolio_equity_curve_computed":False,
        },
        "guardrails":{
            "network_used":False,
            "active_strategy_changed":False,
            "paper_shadow_runtime_changed":False,
            "real_money_action":False,
            "threshold_optimization_performed":False,
            "cross_pair_ranking_performed":False,
        },
        "interpretation_guardrail":spec["interpretation_guardrail"],
        "next_gate":spec["next_gate_after_v1_validation"],
    }

    args.output.parent.mkdir(parents=True,exist_ok=True)
    tmp=args.output.with_suffix(args.output.suffix+".tmp")
    tmp.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n","utf-8")
    os.replace(tmp,args.output)

    compact={
        "kind":result["kind"],"status":result["status"],
        "spec_sha256":spec_sha,
        "total_event_count":result["total_event_count"],
        "split_event_counts":result["split_event_counts"],
        "primary_validation_metrics":result["primary_validation_metrics"],
        "holdout_guard":result["holdout_guard"],
        "events_output_sha256":events_sha,
        "guardrails":result["guardrails"],
        "next_gate":result["next_gate"],
    }
    print("KRAKEN_EUR15_PERFORMANCE_REPLAY_V1 "+json.dumps(compact,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
