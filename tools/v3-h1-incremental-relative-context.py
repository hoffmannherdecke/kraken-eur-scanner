#!/usr/bin/env python3
"""Frozen V3-H1-INCR-001 runner: incremental relative-context value only."""
from __future__ import annotations
import argparse,hashlib,heapq,importlib.util,json,math,statistics,sys,tempfile,csv,gzip
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_SPEC=ROOT/"research/v3/h1-incremental-relative-context-trial-v1.json"
BASE_PATH=ROOT/"tools/v3-h1-association-trial.py"

def load_base():
    s=importlib.util.spec_from_file_location("v3_h1_assoc_base",BASE_PATH)
    if s is None or s.loader is None:raise RuntimeError("cannot load H1 association base")
    m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
B=load_base()

def sha_text(p:Path)->str:
    return hashlib.sha256(p.read_text("utf-8").replace("\r\n","\n").encode()).hexdigest()

@dataclass
class Corr3:
    n:int=0;sx:float=0.;sz:float=0.;sy:float=0.;sxx:float=0.;szz:float=0.;syy:float=0.;sxz:float=0.;sxy:float=0.;szy:float=0.
    def add(self,x:float,z:float,y:float)->None:
        if not all(math.isfinite(v) for v in (x,z,y)):return
        self.n+=1;self.sx+=x;self.sz+=z;self.sy+=y
        self.sxx+=x*x;self.szz+=z*z;self.syy+=y*y;self.sxz+=x*z;self.sxy+=x*y;self.szy+=z*y
    @staticmethod
    def corr(n,sa,sb,saa,sbb,sab):
        if n<2:return None
        ma=sa/n;mb=sb/n;va=max(0.,saa/n-ma*ma);vb=max(0.,sbb/n-mb*mb)
        if va<=0 or vb<=0:return None
        return (sab/n-ma*mb)/math.sqrt(va*vb)
    def result(self)->dict[str,Any]:
        ryz=self.corr(self.n,self.sy,self.sz,self.syy,self.szz,self.szy)
        ryx=self.corr(self.n,self.sy,self.sx,self.syy,self.sxx,self.sxy)
        rzx=self.corr(self.n,self.sz,self.sx,self.szz,self.sxx,self.sxz)
        p=None
        if None not in (ryz,ryx,rzx):
            den=(1-ryx*ryx)*(1-rzx*rzx)
            if den>0:p=(ryz-ryx*rzx)/math.sqrt(den)
        return {"n":self.n,"r_y_incremental":ryz,"r_y_control":ryx,"r_incremental_control":rzx,"partial_r_y_incremental_given_control":p}

def med(xs):return statistics.median(xs) if xs else None

def execute(normalized:Path,spec_path:Path,catalog:Path|None):
    spec=json.loads(spec_path.read_text("utf-8"))
    if spec.get("kind")!="V3_H1_INCREMENTAL_RELATIVE_CONTEXT_TRIAL_V1" or spec.get("status")!="FROZEN_PREREGISTERED_NOT_EXECUTED":
        raise RuntimeError("unexpected H1 incremental spec")
    files=sorted(normalized.glob("*EUR_15.normalized.csv.gz"),key=lambda p:p.name.upper())
    if len(files)!=int(spec["dataset"]["expected_normalized_pair_files"]):raise RuntimeError("file-count mismatch")
    catalog_sha=None
    if catalog:
        cat=json.loads(catalog.read_text("utf-8"))
        if cat.get("status")!="PASS" or int(cat.get("file_count",-1))!=len(files):raise RuntimeError("catalog mismatch")
        if cat.get("source_archive_sha256")!=spec["dataset"]["raw_archive_sha256"]:raise RuntimeError("archive hash mismatch")
        catalog_sha=hashlib.sha256(catalog.read_bytes()).hexdigest()
    w=B.split_windows(spec);splits=list(w);features=spec["fixed_incremental_features"]
    glob={(s,f):Corr3() for s in splits for f in features};pair={};pairvals={(s,f):[] for s in splits for f in features}
    coverage={s:{f:0 for f in features} for s in splits}
    heap=[];seq=0
    for p in files:
        it=B.labeled_iter(p,spec)
        try:item=next(it)
        except StopIteration:continue
        heapq.heappush(heap,(item["ts"],seq,item,it));seq+=1
    cutoffs=0
    while heap:
        ts=heap[0][0];group=[]
        while heap and heap[0][0]==ts:
            _,_,item,it=heapq.heappop(heap);group.append(item)
            try:nxt=next(it);heapq.heappush(heap,(nxt["ts"],seq,nxt,it));seq+=1
            except StopIteration:pass
        sp=group[0]["split"]
        if sp is None or any(x["split"]!=sp for x in group):raise RuntimeError("split mismatch")
        cutoffs+=1
        one=sorted((x["target_return_1h"],x["pair"],x) for x in group if x["target_return_1h"] is not None)
        if not one:continue
        mp={p:v for v,p,_ in one};leaders=[mp[p] for p in spec["fixed_leaders"] if p in mp];leader=statistics.median(leaders) if leaders else None
        for idx,(x,pairname,rec) in enumerate(one):
            y=rec["future_return_1h"]
            if y is None:continue
            peer=B.median_without(one,idx)
            zs={
              "leader_minus_target_return_1h":(leader-x) if leader is not None else None,
              "target_minus_peer_median_return_1h":(x-peer) if peer is not None else None}
            for f,z in zs.items():
                if z is None:continue
                glob[(sp,f)].add(x,z,y);coverage[sp][f]+=1
                key=(sp,f,pairname);c=pair.get(key)
                if c is None:c=pair[key]=Corr3()
                c.add(x,z,y)
        if cutoffs%50000==0:print(f"V3_H1_INCR cutoffs={cutoffs}",flush=True)
    for (sp,f,pn),c in pair.items():
        v=c.result()["partial_r_y_incremental_given_control"]
        if v is not None:pairvals[(sp,f)].append(v)
    splits_out={sp:{f:{
      "complete_cases":coverage[sp][f],
      "observation_weighted":glob[(sp,f)].result(),
      "equal_pair_weighted":{"eligible_pair_count":len(pairvals[(sp,f)]),"median_pair_partial_r":med(pairvals[(sp,f)])}
      } for f in features} for sp in splits}
    out={"schema_version":1,"kind":"V3_H1_INCREMENTAL_RELATIVE_CONTEXT_RESULT_V1","status":"PASS","trial_id":spec["trial_id"],
      "spec_sha256":sha_text(spec_path),"dataset":{"file_count":len(files),"catalog_sha256":catalog_sha,
      "development_end_utc_exclusive":spec["dataset"]["development_end_utc_exclusive"],"holdout_status":spec["topology"]["sealed_holdout"]["status"]},
      "cutoffs_processed":cutoffs,"splits":splits_out,
      "interpretation":{"incremental_association_only":True,"automatic_winner_selected":False,"promotion_allowed":False},
      "guardrails":{"network_used":False,"trade_returns":False,"fee_adjusted_returns":False,"threshold_search":False,"pair_subset_search":False,
      "month_subset_search":False,"p_value_feature_selection":False,"holdout_opened":False,"holdout_labels_generated":False,
      "active_v2r3_changed":False,"v2r4_changed":False,"orders":False,"leverage":False,"real_money_actions":False}}
    raw=json.dumps(out,sort_keys=True,separators=(",",":"));out["deterministic_summary_sha256"]=hashlib.sha256(raw.encode()).hexdigest();return out

def self_test()->int:
    c=Corr3();xs=[-2,-1,0,0,1,2];zs=[0,1,0,1,0,1]
    for x,z in zip(xs,zs):c.add(float(x),float(z),0.5*x+2*z)
    assert c.result()["partial_r_y_incremental_given_control"]>0.999999
    items=[(1.0,"A",{}),(2.0,"B",{}),(3.0,"C",{})]
    assert B.median_without(items,0)==2.5 and B.median_without(items,1)==2.0 and B.median_without(items,2)==1.5
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/"XBTEUR_15.normalized.csv.gz"
        with gzip.open(p,"wt",encoding="utf-8",newline="") as fh:
            wr=csv.writer(fh);wr.writerow(["bar_start_epoch","bar_end_epoch","bar_start_utc","bar_end_utc","open","high","low","close","volume","trades"])
            for i in range(1,20):
                e=i*900;cl=100+i;wr.writerow([e-900,e,"x","x",cl,cl,cl,cl,10,1])
        fake={"dataset":{"development_end_utc_exclusive":"2100-01-01T00:00:00Z"},"topology":{"research_train":{"nominal_start_utc":"1970-01-01T00:00:00Z","effective_cutoff_end_utc_exclusive":"2100-01-01T00:00:00Z"},"calibration":{"effective_cutoff_start_utc":"2100-01-01T00:00:00Z","effective_cutoff_end_utc_exclusive":"2100-01-01T00:00:00Z"},"validation":{"effective_cutoff_start_utc":"2100-01-01T00:00:00Z","effective_cutoff_end_utc_exclusive":"2100-01-01T00:00:00Z"}}}
        rows=list(B.labeled_iter(p,fake))
        assert rows[4]["target_return_1h"] is not None and rows[0]["future_return_1h"] is not None and rows[-1]["future_return_1h"] is None
    print("V3_H1_INCR_SELFTEST PASS partial-corr/peer/exact-future-labels");return 0

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("normalized_dir",type=Path,nargs="?");ap.add_argument("--spec",type=Path,default=DEFAULT_SPEC);ap.add_argument("--catalog",type=Path);ap.add_argument("--output",type=Path);ap.add_argument("--self-test",action="store_true");a=ap.parse_args()
    if a.self_test:return self_test()
    if not a.normalized_dir or not a.output:raise SystemExit("normalized_dir and --output required")
    out=execute(a.normalized_dir,a.spec,a.catalog);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n","utf-8")
    print("V3_H1_INCR_RESULT "+json.dumps({"status":out["status"],"trial_id":out["trial_id"],"summary_sha256":out["deterministic_summary_sha256"],"holdout_opened":out["guardrails"]["holdout_opened"]},sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
