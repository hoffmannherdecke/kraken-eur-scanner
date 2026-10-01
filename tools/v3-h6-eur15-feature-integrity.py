#!/usr/bin/env python3
"""Execute the preregistered V3-H6 EUR15 feature-integrity trial.

Reads local normalized Kraken EUR 15m gzip CSVs only through the development
boundary. Produces coverage/missingness/descriptive feature summaries only.
No labels, trade returns, thresholds, ranking, network, holdout metrics,
strategy mutation, evaluator, orders, leverage, or real-money action.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,math,tempfile
from collections import deque
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
from typing import Any

DEFAULT_SPEC=Path(__file__).resolve().parents[1]/"research/v3/h6-eur15-development-feature-trial-v1.json"

def sha_text(path:Path)->str:
    return hashlib.sha256(path.read_text("utf-8").replace("\r\n","\n").encode()).hexdigest()

def parse_utc(s:str)->datetime:
    return datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(timezone.utc)

@dataclass
class Stats:
    n:int=0
    total:float=0.0
    total_sq:float=0.0
    min_v:float|None=None
    max_v:float|None=None
    def add(self,x:float|None)->None:
        if x is None or not math.isfinite(x): return
        self.n+=1; self.total+=x; self.total_sq+=x*x
        self.min_v=x if self.min_v is None else min(self.min_v,x)
        self.max_v=x if self.max_v is None else max(self.max_v,x)
    def out(self)->dict[str,Any]:
        if not self.n: return {"n":0,"mean":None,"std_population":None,"min":None,"max":None}
        mean=self.total/self.n
        var=max(0.0,self.total_sq/self.n-mean*mean)
        return {"n":self.n,"mean":mean,"std_population":math.sqrt(var),"min":self.min_v,"max":self.max_v}

def analyze_pair(path:Path,end_epoch:int)->dict[str,Any]:
    hist:dict[int,tuple[float,float]]={}
    order:deque[int]=deque()
    eligible=0
    non_null={k:0 for k in (
        "price_return_15m","price_return_1h","price_return_4h",
        "recent_1h_mean_volume","prior_1h_mean_volume",
        "volume_ratio_recent_vs_prior_1h","price_up_with_volume_expansion",
        "price_down_with_volume_expansion")}
    missing={k:0 for k in (
        "price_return_15m","price_return_1h","price_return_4h",
        "recent_1h_mean_volume","prior_1h_mean_volume","volume_ratio_recent_vs_prior_1h")}
    dist={k:Stats() for k in ("price_return_15m","price_return_1h","price_return_4h","volume_ratio_recent_vs_prior_1h")}
    rows=0
    with gzip.open(path,"rt",encoding="utf-8",newline="") as fh:
        rd=csv.DictReader(fh)
        need={"bar_end_epoch","close","volume"}
        if not need.issubset(set(rd.fieldnames or [])):
            raise RuntimeError(f"{path.name}: missing normalized fields")
        for row in rd:
            ts=int(row["bar_end_epoch"])
            if ts>=end_epoch: break
            close=float(row["close"]); vol=float(row["volume"])
            if close<=0 or vol<0 or not math.isfinite(close) or not math.isfinite(vol):
                raise RuntimeError(f"{path.name}: invalid close/volume")
            rows+=1
            def ret(sec:int)->float|None:
                prev=hist.get(ts-sec)
                return (close/prev[0]-1.0) if prev and prev[0]>0 else None
            r15=ret(900); r1=ret(3600); r4=ret(14400)
            recent_ts=[ts-i*900 for i in range(0,4)]
            prior_ts=[ts-i*900 for i in range(4,8)]
            recent_vals=[vol if t==ts else hist[t][1] for t in recent_ts if t==ts or t in hist]
            prior_vals=[hist[t][1] for t in prior_ts if t in hist]
            recent=sum(recent_vals)/4.0 if len(recent_vals)==4 else None
            prior=sum(prior_vals)/4.0 if len(prior_vals)==4 else None
            ratio=(recent/prior) if recent is not None and prior not in (None,0) else None
            vals={
                "price_return_15m":r15,"price_return_1h":r1,"price_return_4h":r4,
                "recent_1h_mean_volume":recent,"prior_1h_mean_volume":prior,
                "volume_ratio_recent_vs_prior_1h":ratio
            }
            for k,v in vals.items():
                if v is None: missing[k]+=1
                else: non_null[k]+=1
            up=(r1 is not None and r1>0 and ratio is not None and ratio>1)
            down=(r1 is not None and r1<0 and ratio is not None and ratio>1)
            if r1 is not None and ratio is not None:
                non_null["price_up_with_volume_expansion"]+=1
                non_null["price_down_with_volume_expansion"]+=1
                eligible+=1
            for k,v in (("price_return_15m",r15),("price_return_1h",r1),("price_return_4h",r4),("volume_ratio_recent_vs_prior_1h",ratio)):
                dist[k].add(v)
            hist[ts]=(close,vol); order.append(ts)
            cutoff=ts-14400
            while order and order[0]<cutoff:
                old=order.popleft(); hist.pop(old,None)
    return {
        "rows_before_holdout":rows,
        "eligible_price1h_and_volume_ratio_cutoffs":eligible,
        "non_null_counts":non_null,
        "missing_counts":missing,
        "distributions":{k:v.out() for k,v in dist.items()},
    }

def execute(normalized_dir:Path,spec_path:Path,catalog_path:Path|None)->dict[str,Any]:
    spec=json.loads(spec_path.read_text("utf-8"))
    if spec.get("kind")!="V3_H6_EUR15_DEVELOPMENT_FEATURE_TRIAL_V1" or spec.get("status")!="FROZEN_PREREGISTERED_NOT_EXECUTED":
        raise RuntimeError("unexpected H6 frozen spec")
    ds=spec["dataset"]; end_epoch=int(parse_utc(ds["development_window"]["end_utc_exclusive"]).timestamp())
    files=sorted(normalized_dir.glob("*EUR_15.normalized.csv.gz"),key=lambda p:p.name.upper())
    if len(files)!=int(ds["expected_normalized_pair_files"]):
        raise RuntimeError(f"normalized file count mismatch expected={ds['expected_normalized_pair_files']} got={len(files)}")
    catalog_sha=None
    if catalog_path:
        cat=json.loads(catalog_path.read_text("utf-8"))
        if cat.get("status")!="PASS" or int(cat.get("file_count",-1))!=len(files):
            raise RuntimeError("normalization catalog status/count mismatch")
        if int(cat.get("total_rows",-1))!=int(ds["expected_total_normalized_rows"]):
            raise RuntimeError("normalization catalog total_rows mismatch")
        if cat.get("source_archive_sha256")!=ds["raw_archive_sha256"]:
            raise RuntimeError("normalization catalog archive hash mismatch")
        catalog_sha=hashlib.sha256(catalog_path.read_bytes()).hexdigest()
    agg_non={}; agg_missing={}; agg_dist={k:Stats() for k in ("price_return_15m","price_return_1h","price_return_4h","volume_ratio_recent_vs_prior_1h")}
    pair_counts=[]; total_rows=0
    for idx,path in enumerate(files,1):
        r=analyze_pair(path,end_epoch); total_rows+=r["rows_before_holdout"]
        pair_counts.append(r["eligible_price1h_and_volume_ratio_cutoffs"])
        for k,v in r["non_null_counts"].items(): agg_non[k]=agg_non.get(k,0)+int(v)
        for k,v in r["missing_counts"].items(): agg_missing[k]=agg_missing.get(k,0)+int(v)
        # Merge exact raw moments from pair summaries.
        for k,s in r["distributions"].items():
            n=int(s["n"])
            if n:
                # Pair summary lacks sum/sumsq, so distributions are recomputed below only
                # as pair-level mean distribution; raw primitive counts remain exact.
                agg_dist[k].add(float(s["mean"]))
        if idx%50==0 or idx==len(files):
            print(f"V3_H6_FEATURE progress={idx}/{len(files)}",flush=True)
    pair_stat=Stats()
    for x in pair_counts: pair_stat.add(float(x))
    base={
        "schema_version":1,"kind":"V3_H6_EUR15_FEATURE_INTEGRITY_RESULT_V1","status":"PASS",
        "trial_id":spec["trial_id"],"spec_sha256":sha_text(spec_path),
        "dataset":{"normalized_dir":str(normalized_dir),"file_count":len(files),
          "catalog_sha256":catalog_sha,"development_end_exclusive":ds["development_window"]["end_utc_exclusive"],
          "holdout_status":ds["sealed_holdout"]["status"],"rows_processed_before_holdout":total_rows},
        "coverage":{"eligible_cutoffs_per_pair":pair_stat.out(),"pairs_with_any_eligible_cutoff":sum(1 for x in pair_counts if x>0)},
        "primitive_non_null_counts":agg_non,"primitive_missing_counts":agg_missing,
        "compact_distributions":{"pair_mean_"+k:v.out() for k,v in agg_dist.items()},
        "guardrails":{"network_used":False,"future_return_labels":False,"trade_returns":False,
          "edge_metrics":False,"threshold_selection":False,"pair_ranking":False,"month_ranking":False,
          "holdout_opened":False,"active_v2r3_changed":False,"v2r4_changed":False,"orders":False,
          "leverage":False,"real_money_actions":False}
    }
    canonical=json.dumps({k:v for k,v in base.items() if k!="deterministic_summary_sha256"},sort_keys=True,separators=(",",":"))
    base["deterministic_summary_sha256"]=hashlib.sha256(canonical.encode()).hexdigest()
    return base

def self_test()->int:
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/"TESTEUR_15.normalized.csv.gz"
        with gzip.open(p,"wt",encoding="utf-8",newline="") as fh:
            wr=csv.writer(fh); wr.writerow(["bar_start_epoch","bar_end_epoch","bar_start_utc","bar_end_utc","open","high","low","close","volume","trades"])
            for i in range(1,25):
                end=i*900; start=end-900
                wr.writerow([start,end,"x","x",100,101,99,100+i,10+i,1])
        r=analyze_pair(p,9999999999)
        assert r["rows_before_holdout"]==24
        assert r["non_null_counts"]["price_return_15m"]==23
        assert r["non_null_counts"]["price_return_1h"]==20
        assert r["non_null_counts"]["price_return_4h"]==8
        assert r["non_null_counts"]["volume_ratio_recent_vs_prior_1h"]==17
        print("V3_H6_FEATURE_SELFTEST PASS exact-lookbacks/no-zero-fill")
    return 0

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("normalized_dir",type=Path,nargs="?")
    ap.add_argument("--spec",type=Path,default=DEFAULT_SPEC)
    ap.add_argument("--catalog",type=Path)
    ap.add_argument("--output",type=Path)
    ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test: return self_test()
    if not a.normalized_dir or not a.output: raise SystemExit("normalized_dir and --output required")
    out=execute(a.normalized_dir,a.spec,a.catalog)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n","utf-8")
    print("V3_H6_FEATURE_RESULT "+json.dumps({
        "status":out["status"],"file_count":out["dataset"]["file_count"],
        "rows":out["dataset"]["rows_processed_before_holdout"],
        "pairs_with_eligible":out["coverage"]["pairs_with_any_eligible_cutoff"],
        "summary_sha256":out["deterministic_summary_sha256"],
        "holdout_opened":out["guardrails"]["holdout_opened"]},sort_keys=True))
    return 0

if __name__=="__main__": raise SystemExit(main())
