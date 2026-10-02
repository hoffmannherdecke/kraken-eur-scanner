#!/usr/bin/env python3
"""Execute frozen V3-H1 development-only breadth association trial.

Streams normalized Kraken EUR 15m pairs, freezes target and cross-sectional
features at each cutoff, generates exact-contiguous 1h/4h labels only after
the cutoff, and reports descriptive associations only.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,heapq,json,math,statistics,tempfile
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any,Iterator

DEFAULT_SPEC=Path(__file__).resolve().parents[1]/"research/v3/h1-breadth-association-trial-v1.json"

def sha_text(path:Path)->str:return hashlib.sha256(path.read_text("utf-8").replace("\r\n","\n").encode()).hexdigest()
def iso_epoch(s:str)->int:
    from datetime import datetime, timezone
    return int(datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(timezone.utc).timestamp())

@dataclass
class Corr:
    n:int=0;sx:float=0.0;sy:float=0.0;sxx:float=0.0;syy:float=0.0;sxy:float=0.0
    def add(self,x:float|None,y:float|None)->None:
        if x is None or y is None or not math.isfinite(x) or not math.isfinite(y):return
        self.n+=1;self.sx+=x;self.sy+=y;self.sxx+=x*x;self.syy+=y*y;self.sxy+=x*y
    def result(self)->dict[str,Any]:
        if self.n<2:return {"n":self.n,"mean_x":None,"mean_y":None,"cov_population":None,"pearson_r":None}
        mx=self.sx/self.n;my=self.sy/self.n;vx=max(0.0,self.sxx/self.n-mx*mx);vy=max(0.0,self.syy/self.n-my*my);cov=self.sxy/self.n-mx*my
        return {"n":self.n,"mean_x":mx,"mean_y":my,"cov_population":cov,"pearson_r":(cov/math.sqrt(vx*vy)) if vx>0 and vy>0 else None}

def split_windows(spec:dict[str,Any])->dict[str,tuple[int,int]]:
    t=spec["topology"];return {"research_train":(iso_epoch(t["research_train"]["nominal_start_utc"]),iso_epoch(t["research_train"]["effective_cutoff_end_utc_exclusive"])),"calibration":(iso_epoch(t["calibration"]["effective_cutoff_start_utc"]),iso_epoch(t["calibration"]["effective_cutoff_end_utc_exclusive"])),"validation":(iso_epoch(t["validation"]["effective_cutoff_start_utc"]),iso_epoch(t["validation"]["effective_cutoff_end_utc_exclusive"]))}
def classify(ts:int,w:dict[str,tuple[int,int]])->str|None:
    for n,(a,b) in w.items():
        if a<=ts<b:return n
    return None
def pair_name(path:Path)->str:
    s="_15.normalized.csv.gz"
    if not path.name.endswith(s):raise RuntimeError("unexpected filename "+path.name)
    return path.name[:-len(s)].upper()
def median_without(items:list[tuple[float,str,dict[str,Any]]],idx:int)->float|None:
    m=len(items)-1
    if m<=0:return None
    def oi(j:int)->int:return j if j<idx else j+1
    return items[oi(m//2)][0] if m%2 else (items[oi(m//2-1)][0]+items[oi(m//2)][0])/2.0

def labeled_iter(path:Path,spec:dict[str,Any])->Iterator[dict[str,Any]]:
    pair=pair_name(path);end_epoch=iso_epoch(spec["dataset"]["development_end_utc_exclusive"]);windows=split_windows(spec)
    hist={};order=deque();rows=deque();last=None;back=0
    with gzip.open(path,"rt",encoding="utf-8",newline="") as fh:
        rd=csv.DictReader(fh)
        if not {"bar_end_epoch","close"}.issubset(set(rd.fieldnames or [])):raise RuntimeError(f"{path.name}: missing normalized fields")
        for raw in rd:
            ts=int(raw["bar_end_epoch"])
            if ts>=end_epoch:break
            close=float(raw["close"])
            if close<=0 or not math.isfinite(close):raise RuntimeError(f"{path.name}: invalid close")
            if last is not None and ts<=last:raise RuntimeError(f"{path.name}: non-increasing bar_end_epoch")
            back=(back+1) if last is not None and ts-last==900 else 1
            prev=hist.get(ts-3600);r1=(close/prev-1.0) if prev and prev>0 else None
            rec={"ts":ts,"pair":pair,"split":classify(ts,windows),"target_return_1h":r1,"close":close,"future_return_1h":None,"future_return_4h":None};rows.append(rec)
            if back>=5 and len(rows)>=5:
                c=list(rows)[-5];c["future_return_1h"]=close/c["close"]-1.0
            if back>=17 and len(rows)>=17:
                c=list(rows)[-17];c["future_return_4h"]=close/c["close"]-1.0
            if len(rows)>17:
                out=rows.popleft()
                if out["split"] is not None:yield out
            hist[ts]=close;order.append(ts);cutoff=ts-3600
            while order and order[0]<cutoff:
                old=order.popleft();hist.pop(old,None)
            last=ts
    while rows:
        out=rows.popleft()
        if out["split"] is not None:yield out

def med(xs:list[float])->float|None:return statistics.median(xs) if xs else None

def execute(normalized_dir:Path,spec_path:Path,catalog_path:Path|None)->dict[str,Any]:
    spec=json.loads(spec_path.read_text("utf-8"))
    if spec.get("kind")!="V3_H1_BREADTH_ASSOCIATION_TRIAL_V1" or spec.get("status")!="FROZEN_PREREGISTERED_NOT_EXECUTED":raise RuntimeError("unexpected H1 association spec")
    files=sorted(normalized_dir.glob("*EUR_15.normalized.csv.gz"),key=lambda p:p.name.upper())
    if len(files)!=int(spec["dataset"]["expected_normalized_pair_files"]):raise RuntimeError(f"file count mismatch expected={spec['dataset']['expected_normalized_pair_files']} got={len(files)}")
    catalog_sha=None
    if catalog_path:
        cat=json.loads(catalog_path.read_text("utf-8"))
        if cat.get("status")!="PASS" or int(cat.get("file_count",-1))!=len(files):raise RuntimeError("catalog status/count mismatch")
        if cat.get("source_archive_sha256")!=spec["dataset"]["raw_archive_sha256"]:raise RuntimeError("catalog archive hash mismatch")
        catalog_sha=hashlib.sha256(catalog_path.read_bytes()).hexdigest()
    windows=split_windows(spec);features=spec["fixed_features"];labels=("future_return_1h","future_return_4h")
    global_corr={(sp,f,l):Corr() for sp in windows for f in features for l in labels};pair_corr={};pair_r={(sp,f,l):[] for sp in windows for f in features for l in labels}
    coverage={sp:{"cutoffs":0,"target_rows":0,"future_return_1h_non_null":0,"future_return_4h_non_null":0,"cutoffs_with_at_least_one_leader":0} for sp in windows}
    heap=[];seq=0
    for p in files:
        it=labeled_iter(p,spec)
        try:item=next(it)
        except StopIteration:continue
        heapq.heappush(heap,(item["ts"],seq,item,it));seq+=1
    total_cutoffs=0
    while heap:
        ts=heap[0][0];group=[]
        while heap and heap[0][0]==ts:
            _,_,item,it=heapq.heappop(heap);group.append(item)
            try:nxt=next(it);heapq.heappush(heap,(nxt["ts"],seq,nxt,it));seq+=1
            except StopIteration:pass
        sp=group[0]["split"]
        if sp is None or any(x["split"]!=sp for x in group):raise RuntimeError("split mismatch at shared cutoff")
        coverage[sp]["cutoffs"]+=1;coverage[sp]["target_rows"]+=len(group);total_cutoffs+=1
        coverage[sp]["future_return_1h_non_null"]+=sum(x["future_return_1h"] is not None for x in group);coverage[sp]["future_return_4h_non_null"]+=sum(x["future_return_4h"] is not None for x in group)
        one=sorted((x["target_return_1h"],x["pair"],x) for x in group if x["target_return_1h"] is not None)
        if not one:continue
        vals=[x[0] for x in one];breadth=sum(v>0 for v in vals)/len(vals);cross_median=statistics.median(vals);one_map={p:v for v,p,_ in one};leaders=[one_map[p] for p in spec["fixed_leaders"] if p in one_map];leader_median=statistics.median(leaders) if leaders else None
        if leaders:coverage[sp]["cutoffs_with_at_least_one_leader"]+=1
        for idx,(r1,pair,rec) in enumerate(one):
            peer=median_without(one,idx);fs={"target_return_1h":r1,"breadth_positive_share_1h":breadth,"cross_sectional_median_return_1h":cross_median,"leader_minus_target_return_1h":(leader_median-r1) if leader_median is not None else None,"target_minus_peer_median_return_1h":(r1-peer) if peer is not None else None};ys={"future_return_1h":rec["future_return_1h"],"future_return_4h":rec["future_return_4h"]}
            for f,x in fs.items():
                for l,y in ys.items():
                    global_corr[(sp,f,l)].add(x,y);key=(sp,f,l,pair);c=pair_corr.get(key)
                    if c is None:c=pair_corr[key]=Corr()
                    c.add(x,y)
        if total_cutoffs%50000==0:print(f"V3_H1_ASSOC cutoffs={total_cutoffs}",flush=True)
    for (sp,f,l,pair),c in pair_corr.items():
        r=c.result()["pearson_r"]
        if r is not None:pair_r[(sp,f,l)].append(r)
    splits={sp:{"coverage":coverage[sp],"features":{f:{l:{"observation_weighted":global_corr[(sp,f,l)].result(),"equal_pair_weighted":{"eligible_pair_count":len(pair_r[(sp,f,l)]),"median_pair_pearson_r":med(pair_r[(sp,f,l)])}} for l in labels} for f in features}} for sp in windows}
    out={"schema_version":1,"kind":"V3_H1_BREADTH_ASSOCIATION_RESULT_V1","status":"PASS","trial_id":spec["trial_id"],"spec_sha256":sha_text(spec_path),"dataset":{"file_count":len(files),"catalog_sha256":catalog_sha,"development_end_utc_exclusive":spec["dataset"]["development_end_utc_exclusive"],"holdout_status":spec["topology"]["sealed_holdout"]["status"]},"splits":splits,"interpretation":{"descriptive_association_only":True,"automatic_winner_selected":False,"promotion_allowed":False},"guardrails":{"network_used":False,"trade_returns":False,"fee_adjusted_returns":False,"threshold_search":False,"pair_subset_search":False,"month_subset_search":False,"horizon_search":False,"p_value_feature_selection":False,"holdout_opened":False,"holdout_labels_generated":False,"active_v2r3_changed":False,"v2r4_changed":False,"orders":False,"leverage":False,"real_money_actions":False}}
    canonical=json.dumps(out,sort_keys=True,separators=(",",":"));out["deterministic_summary_sha256"]=hashlib.sha256(canonical.encode()).hexdigest();return out

def self_test()->int:
    c=Corr()
    for x in (1.0,2.0,3.0,4.0):c.add(x,3*x)
    assert abs(c.result()["pearson_r"]-1.0)<1e-12
    items=[(1.0,"A",{}),(2.0,"B",{}),(3.0,"C",{})];assert median_without(items,0)==2.5 and median_without(items,1)==2.0 and median_without(items,2)==1.5
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/"XBTEUR_15.normalized.csv.gz"
        with gzip.open(p,"wt",encoding="utf-8",newline="") as fh:
            wr=csv.writer(fh);wr.writerow(["bar_start_epoch","bar_end_epoch","bar_start_utc","bar_end_utc","open","high","low","close","volume","trades"])
            for i in range(1,41):
                end=i*900;cl=100+i;wr.writerow([end-900,end,"x","x",cl,cl,cl,cl,10,1])
        fake={"dataset":{"development_end_utc_exclusive":"2100-01-01T00:00:00Z"},"topology":{"research_train":{"nominal_start_utc":"1970-01-01T00:00:00Z","effective_cutoff_end_utc_exclusive":"2100-01-01T00:00:00Z"},"calibration":{"effective_cutoff_start_utc":"2100-01-01T00:00:00Z","effective_cutoff_end_utc_exclusive":"2100-01-01T00:00:00Z"},"validation":{"effective_cutoff_start_utc":"2100-01-01T00:00:00Z","effective_cutoff_end_utc_exclusive":"2100-01-01T00:00:00Z"}}}
        rows=list(labeled_iter(p,fake));assert len(rows)==40;assert rows[4]["target_return_1h"] is not None;assert rows[0]["future_return_1h"] is not None;assert rows[0]["future_return_4h"] is not None;assert rows[-1]["future_return_1h"] is None and rows[-1]["future_return_4h"] is None
    print("V3_H1_ASSOC_SELFTEST PASS corr/peer/exact-future-labels/no-lookahead");return 0

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("normalized_dir",type=Path,nargs="?");ap.add_argument("--spec",type=Path,default=DEFAULT_SPEC);ap.add_argument("--catalog",type=Path);ap.add_argument("--output",type=Path);ap.add_argument("--self-test",action="store_true");a=ap.parse_args()
    if a.self_test:return self_test()
    if not a.normalized_dir or not a.output:raise SystemExit("normalized_dir and --output required")
    out=execute(a.normalized_dir,a.spec,a.catalog);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n","utf-8")
    print("V3_H1_ASSOC_RESULT "+json.dumps({"status":out["status"],"trial_id":out["trial_id"],"summary_sha256":out["deterministic_summary_sha256"],"holdout_opened":out["guardrails"]["holdout_opened"],"winner_selected":out["interpretation"]["automatic_winner_selected"]},sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
