#!/usr/bin/env python3
"""Execute the preregistered V3-H1 EUR15 breadth feature-integrity trial.

Multiway-merges local normalized pair streams by exact bar-end time so breadth,
leader and peer-relative features are computed point-in-time without loading the
full 20M-row dataset into memory. Development-data feature integrity only:
no future labels, trade returns, edge metrics, rankings, holdout or network.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,heapq,json,math,statistics,tempfile
from collections import deque
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
from typing import Any,Iterator

DEFAULT_SPEC=Path(__file__).resolve().parents[1]/"research/v3/h1-eur15-development-feature-trial-v1.json"

def sha_text(path:Path)->str:
    return hashlib.sha256(path.read_text("utf-8").replace("\r\n","\n").encode()).hexdigest()
def parse_utc(s:str)->datetime:
    return datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(timezone.utc)

@dataclass
class Stats:
    n:int=0; total:float=0.0; total_sq:float=0.0; min_v:float|None=None; max_v:float|None=None
    def add(self,x:float|None)->None:
        if x is None or not math.isfinite(x): return
        self.n+=1; self.total+=x; self.total_sq+=x*x
        self.min_v=x if self.min_v is None else min(self.min_v,x)
        self.max_v=x if self.max_v is None else max(self.max_v,x)
    def out(self)->dict[str,Any]:
        if not self.n:return {"n":0,"mean":None,"std_population":None,"min":None,"max":None}
        mean=self.total/self.n; var=max(0.0,self.total_sq/self.n-mean*mean)
        return {"n":self.n,"mean":mean,"std_population":math.sqrt(var),"min":self.min_v,"max":self.max_v}

def pair_name(path:Path)->str:
    suffix="_15.normalized.csv.gz"
    if not path.name.endswith(suffix): raise RuntimeError("unexpected filename "+path.name)
    return path.name[:-len(suffix)].upper()

def feature_iter(path:Path,end_epoch:int)->Iterator[tuple[int,str,dict[str,float|None]]]:
    pair=pair_name(path); hist:dict[int,float]={}; order:deque[int]=deque()
    with gzip.open(path,"rt",encoding="utf-8",newline="") as fh:
        rd=csv.DictReader(fh)
        if not {"bar_end_epoch","close"}.issubset(set(rd.fieldnames or [])):
            raise RuntimeError(f"{path.name}: missing normalized fields")
        for row in rd:
            ts=int(row["bar_end_epoch"])
            if ts>=end_epoch: break
            close=float(row["close"])
            if close<=0 or not math.isfinite(close): raise RuntimeError(f"{path.name}: invalid close")
            def ret(sec:int)->float|None:
                prev=hist.get(ts-sec)
                return (close/prev-1.0) if prev and prev>0 else None
            vals={"15m":ret(900),"1h":ret(3600),"4h":ret(14400)}
            yield ts,pair,vals
            hist[ts]=close; order.append(ts)
            cutoff=ts-14400
            while order and order[0]<cutoff:
                old=order.popleft(); hist.pop(old,None)

def median_without(sorted_items:list[tuple[float,str]],idx:int)->float|None:
    n=len(sorted_items); m=n-1
    if m<=0:return None
    def original_index(reduced_idx:int)->int:
        return reduced_idx if reduced_idx<idx else reduced_idx+1
    if m%2:
        return sorted_items[original_index(m//2)][0]
    a=sorted_items[original_index(m//2-1)][0]
    b=sorted_items[original_index(m//2)][0]
    return (a+b)/2.0

def execute(normalized_dir:Path,spec_path:Path,catalog_path:Path|None)->dict[str,Any]:
    spec=json.loads(spec_path.read_text("utf-8"))
    if spec.get("kind")!="V3_H1_EUR15_DEVELOPMENT_FEATURE_TRIAL_V1" or spec.get("status")!="FROZEN_PREREGISTERED_NOT_EXECUTED":
        raise RuntimeError("unexpected H1 frozen spec")
    ds=spec["dataset"]; end_epoch=int(parse_utc(ds["development_window"]["end_utc_exclusive"]).timestamp())
    files=sorted(normalized_dir.glob("*EUR_15.normalized.csv.gz"),key=lambda p:p.name.upper())
    if len(files)!=int(ds["expected_normalized_pair_files"]):
        raise RuntimeError(f"normalized file count mismatch expected={ds['expected_normalized_pair_files']} got={len(files)}")
    catalog_sha=None
    if catalog_path:
        cat=json.loads(catalog_path.read_text("utf-8"))
        if cat.get("status")!="PASS" or int(cat.get("file_count",-1))!=len(files): raise RuntimeError("catalog status/count mismatch")
        if int(cat.get("total_rows",-1))!=int(ds["expected_total_normalized_rows"]): raise RuntimeError("catalog total_rows mismatch")
        if cat.get("source_archive_sha256")!=ds["raw_archive_sha256"]: raise RuntimeError("catalog archive hash mismatch")
        catalog_sha=hashlib.sha256(catalog_path.read_bytes()).hexdigest()

    iters=[]; heap=[]; seq=0
    for p in files:
        it=feature_iter(p,end_epoch); iters.append(it)
        try: item=next(it)
        except StopIteration: continue
        heapq.heappush(heap,(item[0],seq,item,it)); seq+=1

    horizons=("15m","1h","4h")
    eligible_stats={h:Stats() for h in horizons}; missing_stats={h:Stats() for h in horizons}
    breadth_stats={h:Stats() for h in horizons}; median_stats={h:Stats() for h in horizons}; disp_stats={h:Stats() for h in horizons}
    leader_minus_target=Stats(); target_minus_peer=Stats()
    cutoffs=0; rows_seen=0; leader_available_cutoffs=0
    total_pairs=len(files)
    while heap:
        ts=heap[0][0]; group=[]
        while heap and heap[0][0]==ts:
            _,_,item,it=heapq.heappop(heap); group.append(item); rows_seen+=1
            try:
                nxt=next(it); heapq.heappush(heap,(nxt[0],seq,nxt,it)); seq+=1
            except StopIteration: pass
        cutoffs+=1
        by_pair={pair:vals for _,pair,vals in group}
        for h in horizons:
            items=sorted((v[h],p) for p,v in by_pair.items() if v[h] is not None)
            vals=[x[0] for x in items]; n=len(vals)
            eligible_stats[h].add(float(n)); missing_stats[h].add(float(total_pairs-n))
            if vals:
                breadth_stats[h].add(sum(1 for x in vals if x>0)/n)
                median_stats[h].add(statistics.median(vals))
                disp_stats[h].add(statistics.pstdev(vals) if n>=2 else 0.0)
        one=sorted((v["1h"],p) for p,v in by_pair.items() if v["1h"] is not None)
        one_map={p:x for x,p in one}
        leaders=[one_map[p] for p in ("XBTEUR","ETHEUR") if p in one_map]
        if leaders:
            leader_available_cutoffs+=1
            lm=statistics.median(leaders)
            for value,_pair in one: leader_minus_target.add(lm-value)
        for idx,(value,_pair) in enumerate(one):
            peer=median_without(one,idx)
            if peer is not None: target_minus_peer.add(value-peer)
        if cutoffs%50000==0:
            print(f"V3_H1_FEATURE cutoffs={cutoffs} rows={rows_seen}",flush=True)

    out={
      "schema_version":1,"kind":"V3_H1_EUR15_BREADTH_FEATURE_INTEGRITY_RESULT_V1","status":"PASS",
      "trial_id":spec["trial_id"],"spec_sha256":sha_text(spec_path),
      "dataset":{"normalized_dir":str(normalized_dir),"file_count":len(files),"catalog_sha256":catalog_sha,
        "development_end_exclusive":ds["development_window"]["end_utc_exclusive"],
        "holdout_status":ds["sealed_holdout"]["status"],"feature_rows_processed_before_holdout":rows_seen},
      "cutoffs_processed":cutoffs,
      "horizons":{h:{
          "eligible_pair_count_distribution":eligible_stats[h].out(),
          "missing_pair_count_distribution":missing_stats[h].out(),
          "breadth_positive_share_distribution":breadth_stats[h].out(),
          "cross_sectional_median_return_distribution":median_stats[h].out(),
          "cross_sectional_dispersion_distribution":disp_stats[h].out()
        } for h in horizons},
      "leader_contract":{"leaders":["XBTEUR","ETHEUR"],"cutoffs_with_at_least_one_leader_1h":leader_available_cutoffs,
        "leader_minus_target_1h_distribution":leader_minus_target.out()},
      "peer_contract":{"target_minus_peer_median_1h_distribution":target_minus_peer.out()},
      "guardrails":{"network_used":False,"future_return_labels":False,"trade_returns":False,"edge_metrics":False,
        "threshold_ranking":False,"pair_ranking_by_performance":False,"month_ranking":False,"holdout_opened":False,
        "active_v2r3_changed":False,"v2r4_changed":False,"orders":False,"leverage":False,"real_money_actions":False}
    }
    canonical=json.dumps(out,sort_keys=True,separators=(",",":"))
    out["deterministic_summary_sha256"]=hashlib.sha256(canonical.encode()).hexdigest()
    return out

def self_test()->int:
    with tempfile.TemporaryDirectory() as td:
        d=Path(td)
        for pair,shift in (("XBTEUR",0.0),("ETHEUR",1.0),("SOLEUR",2.0)):
            p=d/f"{pair}_15.normalized.csv.gz"
            with gzip.open(p,"wt",encoding="utf-8",newline="") as fh:
                wr=csv.writer(fh); wr.writerow(["bar_start_epoch","bar_end_epoch","bar_start_utc","bar_end_utc","open","high","low","close","volume","trades"])
                for i in range(1,25):
                    end=i*900; start=end-900; close=100+shift+i
                    wr.writerow([start,end,"x","x",close,close,close,close,10,1])
        # Directly test merge helpers without frozen 648-file spec.
        streams=[feature_iter(p,9999999999) for p in sorted(d.glob("*.gz"))]
        rows=[list(it) for it in streams]
        assert all(len(x)==24 for x in rows)
        assert all(x[-1][2]["4h"] is not None for x in rows)
        items=sorted((1.0,"A"),(2.0,"B")) if False else [(1.0,"A"),(2.0,"B"),(3.0,"C")]
        assert median_without(items,0)==2.5
        assert median_without(items,1)==2.0
        assert median_without(items,2)==1.5
        print("V3_H1_FEATURE_SELFTEST PASS exact-lookbacks/multiway-primitives/peer-median")
    return 0

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("normalized_dir",type=Path,nargs="?")
    ap.add_argument("--spec",type=Path,default=DEFAULT_SPEC)
    ap.add_argument("--catalog",type=Path)
    ap.add_argument("--output",type=Path)
    ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test:return self_test()
    if not a.normalized_dir or not a.output:raise SystemExit("normalized_dir and --output required")
    out=execute(a.normalized_dir,a.spec,a.catalog)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n","utf-8")
    print("V3_H1_FEATURE_RESULT "+json.dumps({
      "status":out["status"],"file_count":out["dataset"]["file_count"],"rows":out["dataset"]["feature_rows_processed_before_holdout"],
      "cutoffs":out["cutoffs_processed"],"summary_sha256":out["deterministic_summary_sha256"],
      "holdout_opened":out["guardrails"]["holdout_opened"]},sort_keys=True))
    return 0
if __name__=="__main__":raise SystemExit(main())
