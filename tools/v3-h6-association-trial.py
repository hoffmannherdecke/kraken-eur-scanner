#!/usr/bin/env python3
"""Execute frozen V3-H6 development-only association trial.

Local normalized Kraken EUR 15m files only. Generates fixed 1h/4h future
labels after feature cutoff, applies frozen chronological split/purge/embargo,
and reports descriptive effect sizes only. No threshold search, p-value
selection, trade/net returns, holdout labels, network, orders, or strategy
mutation.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,math,statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_SPEC=Path(__file__).resolve().parents[1]/"research/v3/h6-price-volume-association-trial-v1.json"

def sha_text(path:Path)->str:
    return hashlib.sha256(path.read_text("utf-8").replace("\r\n","\n").encode()).hexdigest()

def iso_epoch(s:str)->int:
    from datetime import datetime, timezone
    return int(datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(timezone.utc).timestamp())

@dataclass
class Corr:
    n:int=0; sx:float=0.0; sy:float=0.0; sxx:float=0.0; syy:float=0.0; sxy:float=0.0
    def add(self,x:float|None,y:float|None)->None:
        if x is None or y is None or not math.isfinite(x) or not math.isfinite(y): return
        self.n+=1; self.sx+=x; self.sy+=y; self.sxx+=x*x; self.syy+=y*y; self.sxy+=x*y
    def result(self)->dict[str,Any]:
        if self.n<2:return {"n":self.n,"mean_x":None,"mean_y":None,"cov_population":None,"pearson_r":None}
        mx=self.sx/self.n; my=self.sy/self.n
        vx=max(0.0,self.sxx/self.n-mx*mx); vy=max(0.0,self.syy/self.n-my*my)
        cov=self.sxy/self.n-mx*my
        r=(cov/math.sqrt(vx*vy)) if vx>0 and vy>0 else None
        return {"n":self.n,"mean_x":mx,"mean_y":my,"cov_population":cov,"pearson_r":r}

@dataclass
class BoolEffect:
    n_true:int=0; sum_true:float=0.0; n_false:int=0; sum_false:float=0.0
    def add(self,flag:bool|None,y:float|None)->None:
        if flag is None or y is None or not math.isfinite(y): return
        if flag:self.n_true+=1;self.sum_true+=y
        else:self.n_false+=1;self.sum_false+=y
    def result(self)->dict[str,Any]:
        mt=self.sum_true/self.n_true if self.n_true else None
        mf=self.sum_false/self.n_false if self.n_false else None
        return {"n_true":self.n_true,"n_false":self.n_false,"mean_true":mt,"mean_false":mf,
                "true_minus_false_mean":(mt-mf) if mt is not None and mf is not None else None}

def split_windows(spec:dict[str,Any])->dict[str,tuple[int,int]]:
    t=spec["topology"]
    return {
      "research_train":(iso_epoch(t["research_train"]["nominal_start_utc"]),iso_epoch(t["research_train"]["effective_cutoff_end_utc_exclusive"])),
      "calibration":(iso_epoch(t["calibration"]["effective_cutoff_start_utc"]),iso_epoch(t["calibration"]["effective_cutoff_end_utc_exclusive"])),
      "validation":(iso_epoch(t["validation"]["effective_cutoff_start_utc"]),iso_epoch(t["validation"]["effective_cutoff_end_utc_exclusive"])),
    }

def classify(ts:int,windows:dict[str,tuple[int,int]])->str|None:
    for name,(start,end) in windows.items():
        if start<=ts<end:return name
    return None

def pair_name(path:Path)->str:
    suffix="_15.normalized.csv.gz"
    if not path.name.endswith(suffix):raise RuntimeError("unexpected filename "+path.name)
    return path.name[:-len(suffix)].upper()

def load_rows(path:Path,end_epoch:int)->tuple[list[int],list[float],list[float]]:
    ts=[];close=[];vol=[];last=None
    with gzip.open(path,"rt",encoding="utf-8",newline="") as fh:
        rd=csv.DictReader(fh)
        if not {"bar_end_epoch","close","volume"}.issubset(set(rd.fieldnames or [])):raise RuntimeError(f"{path.name}: missing normalized fields")
        for row in rd:
            t=int(row["bar_end_epoch"])
            if t>=end_epoch:break
            c=float(row["close"]);v=float(row["volume"])
            if c<=0 or v<0 or not math.isfinite(c) or not math.isfinite(v):raise RuntimeError(f"{path.name}: invalid row")
            if last is not None and t<=last:raise RuntimeError(f"{path.name}: non-increasing bar_end_epoch")
            ts.append(t);close.append(c);vol.append(v);last=t
    return ts,close,vol

def continuity(ts:list[int])->tuple[list[int],list[int]]:
    n=len(ts);back=[1]*n;fwd=[1]*n
    for i in range(1,n):
        if ts[i]-ts[i-1]==900:back[i]=back[i-1]+1
    for i in range(n-2,-1,-1):
        if ts[i+1]-ts[i]==900:fwd[i]=fwd[i+1]+1
    return back,fwd

def analyze_pair(path:Path,spec:dict[str,Any],global_corr,global_bool,pair_r_values,pair_bool_values,split_counts)->None:
    end_epoch=iso_epoch(spec["dataset"]["development_end_utc_exclusive"]);windows=split_windows(spec)
    ts,close,vol=load_rows(path,end_epoch);back,fwd=continuity(ts)
    labels=("future_return_1h","future_return_4h")
    local_corr={(sp,f,l):Corr() for sp in windows for f in spec["fixed_numeric_features"] for l in labels}
    local_bool={(sp,f,l):BoolEffect() for sp in windows for f in spec["fixed_boolean_features"] for l in labels}
    for i,t in enumerate(ts):
        sp=classify(t,windows)
        if sp is None:continue
        split_counts[sp]["cutoffs_seen"]+=1
        r1=(close[i]/close[i-4]-1.0) if back[i]>=5 else None
        r4=(close[i]/close[i-16]-1.0) if back[i]>=17 else None
        ratio=None
        if back[i]>=8:
            recent=sum(vol[i-3:i+1])/4.0;prior=sum(vol[i-7:i-3])/4.0
            ratio=(recent/prior) if prior!=0 else None
        up=(r1>0 and ratio>1) if r1 is not None and ratio is not None else None
        down=(r1<0 and ratio>1) if r1 is not None and ratio is not None else None
        y1=(close[i+4]/close[i]-1.0) if fwd[i]>=5 else None
        y4=(close[i+16]/close[i]-1.0) if fwd[i]>=17 else None
        if y1 is not None:split_counts[sp]["future_return_1h_non_null"]+=1
        if y4 is not None:split_counts[sp]["future_return_4h_non_null"]+=1
        features={"price_return_1h":r1,"price_return_4h":r4,"volume_ratio_recent_vs_prior_1h":ratio}
        bools={"price_up_with_volume_expansion":up,"price_down_with_volume_expansion":down}
        ys={"future_return_1h":y1,"future_return_4h":y4}
        for f,x in features.items():
            for l,y in ys.items():global_corr[(sp,f,l)].add(x,y);local_corr[(sp,f,l)].add(x,y)
        for f,flag in bools.items():
            for l,y in ys.items():global_bool[(sp,f,l)].add(flag,y);local_bool[(sp,f,l)].add(flag,y)
    for key,c in local_corr.items():
        r=c.result()["pearson_r"]
        if r is not None:pair_r_values[key].append(r)
    for key,b in local_bool.items():
        d=b.result()["true_minus_false_mean"]
        if d is not None:pair_bool_values[key].append(d)

def med(xs:list[float])->float|None:return statistics.median(xs) if xs else None

def execute(normalized_dir:Path,spec_path:Path,catalog_path:Path|None)->dict[str,Any]:
    spec=json.loads(spec_path.read_text("utf-8"))
    if spec.get("kind")!="V3_H6_PRICE_VOLUME_ASSOCIATION_TRIAL_V1" or spec.get("status")!="FROZEN_PREREGISTERED_NOT_EXECUTED":raise RuntimeError("unexpected H6 association spec")
    files=sorted(normalized_dir.glob("*EUR_15.normalized.csv.gz"),key=lambda p:p.name.upper())
    if len(files)!=int(spec["dataset"]["expected_normalized_pair_files"]):raise RuntimeError(f"file count mismatch expected={spec['dataset']['expected_normalized_pair_files']} got={len(files)}")
    catalog_sha=None
    if catalog_path:
        cat=json.loads(catalog_path.read_text("utf-8"))
        if cat.get("status")!="PASS" or int(cat.get("file_count",-1))!=len(files):raise RuntimeError("catalog status/count mismatch")
        if cat.get("source_archive_sha256")!=spec["dataset"]["raw_archive_sha256"]:raise RuntimeError("catalog archive hash mismatch")
        catalog_sha=hashlib.sha256(catalog_path.read_bytes()).hexdigest()
    windows=split_windows(spec);numeric=spec["fixed_numeric_features"];boolean=spec["fixed_boolean_features"];labels=("future_return_1h","future_return_4h")
    global_corr={(sp,f,l):Corr() for sp in windows for f in numeric for l in labels}
    global_bool={(sp,f,l):BoolEffect() for sp in windows for f in boolean for l in labels}
    pair_r_values={(sp,f,l):[] for sp in windows for f in numeric for l in labels}
    pair_bool_values={(sp,f,l):[] for sp in windows for f in boolean for l in labels}
    split_counts={sp:{"cutoffs_seen":0,"future_return_1h_non_null":0,"future_return_4h_non_null":0} for sp in windows}
    for idx,p in enumerate(files,1):
        analyze_pair(p,spec,global_corr,global_bool,pair_r_values,pair_bool_values,split_counts)
        if idx%50==0 or idx==len(files):print(f"V3_H6_ASSOC progress={idx}/{len(files)}",flush=True)
    splits={}
    for sp in windows:
        splits[sp]={
          "coverage":split_counts[sp],
          "numeric":{f:{l:{"observation_weighted":global_corr[(sp,f,l)].result(),
                           "equal_pair_weighted":{"eligible_pair_count":len(pair_r_values[(sp,f,l)]),"median_pair_pearson_r":med(pair_r_values[(sp,f,l)])}}
                        for l in labels} for f in numeric},
          "boolean":{f:{l:{"observation_weighted":global_bool[(sp,f,l)].result(),
                           "equal_pair_weighted":{"eligible_pair_count":len(pair_bool_values[(sp,f,l)]),"median_pair_true_minus_false_mean":med(pair_bool_values[(sp,f,l)])}}
                        for l in labels} for f in boolean}}
    out={"schema_version":1,"kind":"V3_H6_PRICE_VOLUME_ASSOCIATION_RESULT_V1","status":"PASS","trial_id":spec["trial_id"],"spec_sha256":sha_text(spec_path),
      "dataset":{"file_count":len(files),"catalog_sha256":catalog_sha,"development_end_utc_exclusive":spec["dataset"]["development_end_utc_exclusive"],"holdout_status":spec["topology"]["sealed_holdout"]["status"]},
      "splits":splits,"interpretation":{"descriptive_association_only":True,"automatic_winner_selected":False,"promotion_allowed":False},
      "guardrails":{"network_used":False,"trade_returns":False,"fee_adjusted_returns":False,"threshold_search":False,"pair_subset_search":False,"month_subset_search":False,"horizon_search":False,"p_value_feature_selection":False,"holdout_opened":False,"holdout_labels_generated":False,"active_v2r3_changed":False,"v2r4_changed":False,"orders":False,"leverage":False,"real_money_actions":False}}
    canonical=json.dumps(out,sort_keys=True,separators=(",",":"));out["deterministic_summary_sha256"]=hashlib.sha256(canonical.encode()).hexdigest();return out

def self_test()->int:
    c=Corr()
    for x in (1.0,2.0,3.0,4.0):c.add(x,2*x)
    assert abs(c.result()["pearson_r"]-1.0)<1e-12
    b=BoolEffect();b.add(True,2);b.add(True,4);b.add(False,1);b.add(False,1)
    assert abs(b.result()["true_minus_false_mean"]-2.0)<1e-12
    ts=[900,1800,2700,3600,4500,6300,7200];back,fwd=continuity(ts)
    assert back[4]==5 and fwd[4]==1 and back[5]==1
    fake={"topology":{"research_train":{"nominal_start_utc":"1970-01-01T00:00:00Z","effective_cutoff_end_utc_exclusive":"1970-01-02T20:00:00Z"},"calibration":{"effective_cutoff_start_utc":"1970-01-03T04:00:00Z","effective_cutoff_end_utc_exclusive":"1970-01-04T20:00:00Z"},"validation":{"effective_cutoff_start_utc":"1970-01-05T04:00:00Z","effective_cutoff_end_utc_exclusive":"1970-01-06T20:00:00Z"}}}
    w=split_windows(fake);assert classify(iso_epoch("1970-01-03T02:00:00Z"),w) is None;assert classify(iso_epoch("1970-01-03T05:00:00Z"),w)=="calibration"
    print("V3_H6_ASSOC_SELFTEST PASS corr/effect/contiguity/purge-embargo");return 0

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("normalized_dir",type=Path,nargs="?");ap.add_argument("--spec",type=Path,default=DEFAULT_SPEC);ap.add_argument("--catalog",type=Path);ap.add_argument("--output",type=Path);ap.add_argument("--self-test",action="store_true");a=ap.parse_args()
    if a.self_test:return self_test()
    if not a.normalized_dir or not a.output:raise SystemExit("normalized_dir and --output required")
    out=execute(a.normalized_dir,a.spec,a.catalog);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n","utf-8")
    print("V3_H6_ASSOC_RESULT "+json.dumps({"status":out["status"],"trial_id":out["trial_id"],"summary_sha256":out["deterministic_summary_sha256"],"holdout_opened":out["guardrails"]["holdout_opened"],"winner_selected":out["interpretation"]["automatic_winner_selected"]},sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
