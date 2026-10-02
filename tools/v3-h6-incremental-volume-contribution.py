#!/usr/bin/env python3
"""Frozen V3-H6-INCR-001 runner: incremental volume contribution only."""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,math,statistics,sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_SPEC=ROOT/"research/v3/h6-incremental-volume-contribution-trial-v1.json"
BASE_PATH=ROOT/"tools/v3-h6-association-trial.py"

def load_base():
    s=importlib.util.spec_from_file_location("v3_h6_assoc_base",BASE_PATH)
    if s is None or s.loader is None: raise RuntimeError("cannot load H6 association base")
    m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
B=load_base()

def sha_text(p:Path)->str:
    return hashlib.sha256(p.read_text("utf-8").replace("\r\n","\n").encode()).hexdigest()

@dataclass
class Corr3:
    n:int=0;sx:float=0.;sz:float=0.;sy:float=0.;sxx:float=0.;szz:float=0.;syy:float=0.;sxz:float=0.;sxy:float=0.;szy:float=0.
    def add(self,x:float,z:float,y:float)->None:
        if not all(math.isfinite(v) for v in (x,z,y)): return
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
        return {"n":self.n,"r_y_volume":ryz,"r_y_price":ryx,"r_volume_price":rzx,"partial_r_y_volume_given_price":p}

@dataclass
class Effect:
    nt:int=0;st:float=0.;nf:int=0;sf:float=0.
    def add(self,flag:bool,y:float)->None:
        if flag:self.nt+=1;self.st+=y
        else:self.nf+=1;self.sf+=y
    def out(self):
        mt=self.st/self.nt if self.nt else None;mf=self.sf/self.nf if self.nf else None
        return {"n_true":self.nt,"n_false":self.nf,"mean_true":mt,"mean_false":mf,
                "true_minus_false_mean":(mt-mf) if mt is not None and mf is not None else None}

def med(xs):return statistics.median(xs) if xs else None

def execute(normalized:Path,spec_path:Path,catalog:Path|None):
    spec=json.loads(spec_path.read_text("utf-8"))
    if spec.get("kind")!="V3_H6_INCREMENTAL_VOLUME_CONTRIBUTION_TRIAL_V1" or spec.get("status")!="FROZEN_PREREGISTERED_NOT_EXECUTED":
        raise RuntimeError("unexpected H6 incremental spec")
    files=sorted(normalized.glob("*EUR_15.normalized.csv.gz"),key=lambda p:p.name.upper())
    if len(files)!=int(spec["dataset"]["expected_normalized_pair_files"]):raise RuntimeError("file-count mismatch")
    catalog_sha=None
    if catalog:
        cat=json.loads(catalog.read_text("utf-8"))
        if cat.get("status")!="PASS" or int(cat.get("file_count",-1))!=len(files):raise RuntimeError("catalog mismatch")
        if cat.get("source_archive_sha256")!=spec["dataset"]["raw_archive_sha256"]:raise RuntimeError("archive hash mismatch")
        catalog_sha=hashlib.sha256(catalog.read_bytes()).hexdigest()
    w=B.split_windows(spec);splits=list(w);strata=("down","up")
    glob={(s,q):Corr3() for s in splits for q in strata};effects={(s,q):Effect() for s in splits for q in strata}
    pairvals={(s,q):[] for s in splits for q in strata}
    coverage={s:{q:{"complete_cases":0,"volume_expansion_true":0,"volume_expansion_false":0} for q in strata} for s in splits}
    end=B.iso_epoch(spec["dataset"]["development_end_utc_exclusive"])
    for idx,p in enumerate(files,1):
        ts,cl,vol=B.load_rows(p,end);back,fwd=B.continuity(ts);local={(s,q):Corr3() for s in splits for q in strata}
        for i,t in enumerate(ts):
            sp=B.classify(t,w)
            if sp is None or back[i]<8 or fwd[i]<5:continue
            r1=cl[i]/cl[i-4]-1.0
            if r1==0:continue
            prior=sum(vol[i-7:i-3])/4.0
            if prior<=0:continue
            ratio=(sum(vol[i-3:i+1])/4.0)/prior;y=cl[i+4]/cl[i]-1.0
            q="up" if r1>0 else "down";flag=ratio>1.0;z=1.0 if flag else 0.0
            glob[(sp,q)].add(r1,z,y);local[(sp,q)].add(r1,z,y);effects[(sp,q)].add(flag,y)
            coverage[sp][q]["complete_cases"]+=1;coverage[sp][q]["volume_expansion_true" if flag else "volume_expansion_false"]+=1
        for key,c in local.items():
            v=c.result()["partial_r_y_volume_given_price"]
            if v is not None:pairvals[key].append(v)
        if idx%50==0 or idx==len(files):print(f"V3_H6_INCR progress={idx}/{len(files)}",flush=True)
    splits_out={sp:{q:{
        "coverage":coverage[sp][q],
        "simple_effect":effects[(sp,q)].out(),
        "observation_weighted":glob[(sp,q)].result(),
        "equal_pair_weighted":{"eligible_pair_count":len(pairvals[(sp,q)]),"median_pair_partial_r":med(pairvals[(sp,q)])}
      } for q in strata} for sp in splits}
    out={"schema_version":1,"kind":"V3_H6_INCREMENTAL_VOLUME_CONTRIBUTION_RESULT_V1","status":"PASS","trial_id":spec["trial_id"],
      "spec_sha256":sha_text(spec_path),"dataset":{"file_count":len(files),"catalog_sha256":catalog_sha,
      "development_end_utc_exclusive":spec["dataset"]["development_end_utc_exclusive"],"holdout_status":spec["topology"]["sealed_holdout"]["status"]},
      "splits":splits_out,"interpretation":{"incremental_association_only":True,"threshold_tuned":False,"automatic_winner_selected":False,"promotion_allowed":False},
      "guardrails":{"network_used":False,"trade_returns":False,"fee_adjusted_returns":False,"threshold_search":False,"volume_transform_search":False,
      "pair_subset_search":False,"month_subset_search":False,"p_value_feature_selection":False,"holdout_opened":False,"holdout_labels_generated":False,
      "active_v2r3_changed":False,"v2r4_changed":False,"orders":False,"leverage":False,"real_money_actions":False}}
    raw=json.dumps(out,sort_keys=True,separators=(",",":"));out["deterministic_summary_sha256"]=hashlib.sha256(raw.encode()).hexdigest();return out

def self_test()->int:
    c=Corr3();xs=[-2,-1,0,0,1,2];zs=[0,1,0,1,0,1]
    for x,z in zip(xs,zs):c.add(float(x),float(z),0.5*x+2*z)
    assert c.result()["partial_r_y_volume_given_price"]>0.999999
    e=Effect();e.add(True,2);e.add(True,4);e.add(False,1);e.add(False,1);assert abs(e.out()["true_minus_false_mean"]-2)<1e-12
    ts=[900,1800,2700,3600,4500,6300,7200];back,fwd=B.continuity(ts);assert back[4]==5 and fwd[4]==1 and back[5]==1
    print("V3_H6_INCR_SELFTEST PASS partial-corr/effect/contiguity");return 0

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("normalized_dir",type=Path,nargs="?");ap.add_argument("--spec",type=Path,default=DEFAULT_SPEC);ap.add_argument("--catalog",type=Path);ap.add_argument("--output",type=Path);ap.add_argument("--self-test",action="store_true");a=ap.parse_args()
    if a.self_test:return self_test()
    if not a.normalized_dir or not a.output:raise SystemExit("normalized_dir and --output required")
    out=execute(a.normalized_dir,a.spec,a.catalog);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n","utf-8")
    print("V3_H6_INCR_RESULT "+json.dumps({"status":out["status"],"trial_id":out["trial_id"],"summary_sha256":out["deterministic_summary_sha256"],"holdout_opened":out["guardrails"]["holdout_opened"]},sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
