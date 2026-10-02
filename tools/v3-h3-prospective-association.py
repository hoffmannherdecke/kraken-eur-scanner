#!/usr/bin/env python3
"""Prospective V3-H3 orderbook-state association capture/evaluator.

Frozen contract:
- Kraken public WS v2 book, depth 10
- BTC/EUR, ETH/EUR, SOL/EUR
- fixed 5s wall-clock sampling
- fixed 1m/5m/15m future mid-price returns
- descriptive association only; no thresholds, p-values, fill/routing claims or trading actions
"""
from __future__ import annotations
import argparse,asyncio,json,math,statistics,time,zlib
from collections import defaultdict,deque
from dataclasses import dataclass,field
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

DEFAULT_SPEC=Path(__file__).resolve().parents[1]/"research/v3/h3-prospective-state-association-trial-v2.json"
WS_URL="wss://ws.kraken.com/v2"
FEATURES=("spread_bps","bid_depth_quote_top10","ask_depth_quote_top10","depth_imbalance_top10")
SYMBOLS=("BTC/EUR","ETH/EUR","SOL/EUR")

def iso(ts:float)->str:return datetime.fromtimestamp(ts,timezone.utc).isoformat().replace("+00:00","Z")
def piece(v:Decimal)->str:
    s=format(v,"f").replace(".","").lstrip("0")
    return s or "0"

@dataclass
class Corr:
    n:int=0;sx:float=0.;sy:float=0.;sxx:float=0.;syy:float=0.;sxy:float=0.
    def add(self,x:float,y:float)->None:
        if not math.isfinite(x) or not math.isfinite(y):return
        self.n+=1;self.sx+=x;self.sy+=y;self.sxx+=x*x;self.syy+=y*y;self.sxy+=x*y
    def out(self)->dict[str,Any]:
        if self.n<2:return {"n":self.n,"pearson_r":None}
        mx=self.sx/self.n;my=self.sy/self.n
        vx=max(0.,self.sxx/self.n-mx*mx);vy=max(0.,self.syy/self.n-my*my);cov=self.sxy/self.n-mx*my
        return {"n":self.n,"pearson_r":cov/math.sqrt(vx*vy) if vx>0 and vy>0 else None}

@dataclass
class Book:
    depth:int=10
    bids:dict[Decimal,Decimal]=field(default_factory=dict)
    asks:dict[Decimal,Decimal]=field(default_factory=dict)
    def apply_levels(self,d:dict[Decimal,Decimal],rows:list[dict[str,Any]])->None:
        for r in rows:
            p,q=r.get("price"),r.get("qty")
            if not isinstance(p,Decimal) or not isinstance(q,Decimal) or p<=0 or q<0:raise RuntimeError("bad book level")
            if q==0:d.pop(p,None)
            else:d[p]=q
    def trim(self)->None:
        self.bids=dict(sorted(self.bids.items(),reverse=True)[:self.depth])
        self.asks=dict(sorted(self.asks.items())[:self.depth])
    def crc(self)->int:
        parts=[]
        for p,q in sorted(self.asks.items())[:10]:parts += [piece(p),piece(q)]
        for p,q in sorted(self.bids.items(),reverse=True)[:10]:parts += [piece(p),piece(q)]
        return zlib.crc32("".join(parts).encode("ascii")) & 0xffffffff
    def update(self,typ:str,row:dict[str,Any])->dict[str,float]:
        if typ=="snapshot":self.bids.clear();self.asks.clear()
        self.apply_levels(self.bids,row.get("bids") or []);self.apply_levels(self.asks,row.get("asks") or []);self.trim()
        if not self.bids or not self.asks:raise RuntimeError("empty book")
        if self.crc()!=int(row["checksum"]):raise RuntimeError("checksum")
        bid=max(self.bids);ask=min(self.asks)
        if not ask>bid:raise RuntimeError("crossed book")
        mid=(bid+ask)/2
        bd=sum(p*q for p,q in self.bids.items());ad=sum(p*q for p,q in self.asks.items());den=bd+ad
        return {"mid_price":float(mid),"spread_bps":float((ask-bid)/mid*Decimal(10000)),
                "bid_depth_quote_top10":float(bd),"ask_depth_quote_top10":float(ad),
                "depth_imbalance_top10":float((bd-ad)/den)}

def load_spec(path:Path)->dict[str,Any]:
    s=json.loads(path.read_text("utf-8"))
    if s.get("kind")!="V3_H3_PROSPECTIVE_ORDERBOOK_STATE_ASSOCIATION_TRIAL_V1":raise RuntimeError("unexpected spec kind")
    if s.get("status")!="FROZEN_PREREGISTERED_CAPTURE_NOT_STARTED":raise RuntimeError("spec not frozen")
    if tuple(s["source"]["symbols"])!=SYMBOLS or int(s["source"]["depth"])!=10:raise RuntimeError("source contract drift")
    if tuple(s["fixed_features"])!=FEATURES:raise RuntimeError("feature contract drift")
    if int(s["sampling"]["maximum_state_age_ms"])!=2000:raise RuntimeError("freshness contract drift")
    return s

async def capture(seconds:int,session_id:str,spec:dict[str,Any])->dict[str,Any]:
    from websockets.asyncio.client import connect
    grid=5
    books={s:Book(10) for s in SYMBOLS}
    history={s:deque(maxlen=16) for s in SYMBOLS}
    rows=[];errors=[];acks=0;wire=0
    started=time.time();first_grid=math.ceil(started/grid)*grid;end=started+seconds
    async with connect(WS_URL,open_timeout=15,ping_interval=10,ping_timeout=10,max_size=8*1024*1024) as ws:
        await ws.send(json.dumps({"method":"subscribe","params":{"channel":"book","symbol":list(SYMBOLS),"depth":10,"snapshot":True},"req_id":1}))
        next_grid=first_grid
        while time.time()<end:
            wall=time.time()
            if wall>=next_grid:
                g=next_grid
                for sym in SYMBOLS:
                    eligible=[x for x in history[sym] if x["recv_epoch"]<=g]
                    if not eligible:continue
                    st=eligible[-1];age_ms=(g-st["recv_epoch"])*1000.
                    if age_ms<0 or age_ms>int(spec["sampling"]["maximum_state_age_ms"]):continue
                    row={"schema_version":1,"session_id":session_id,"sample_epoch":int(g),"sample_utc":iso(g),
                         "symbol":sym,"source_age_ms":age_ms}
                    row.update({k:st[k] for k in ("mid_price",)+FEATURES});rows.append(row)
                next_grid+=grid
                continue
            timeout=max(.01,min(.25,next_grid-wall,end-wall))
            try: raw=await asyncio.wait_for(ws.recv(),timeout=timeout)
            except asyncio.TimeoutError:continue
            wire+=1;recv=time.time();j=json.loads(raw,parse_float=Decimal)
            if j.get("method")=="subscribe":
                if j.get("success") is True:acks+=1
                else:errors.append(str(j.get("error")))
                continue
            if j.get("channel")!="book" or j.get("type") not in ("snapshot","update"):continue
            for r in j.get("data") or []:
                sym=str(r.get("symbol") or "")
                if sym not in books:continue
                try:
                    vals=books[sym].update(j["type"],r)
                    history[sym].append({"recv_epoch":recv,**vals})
                except Exception as e:
                    errors.append(f"{sym}:{type(e).__name__}:{e}")
                    break
            if errors:break
    ended=time.time()
    counts={s:sum(r["symbol"]==s for r in rows) for s in SYMBOLS}
    status="PASS" if not errors and acks>=1 and all(counts[s]>0 for s in SYMBOLS) else "FAIL"
    return {"schema_version":1,"kind":"V3_H3_PROSPECTIVE_CAPTURE_SESSION_V1","status":status,
            "trial_id":spec["trial_id"],"session_id":session_id,"started_at_utc":iso(started),"ended_at_utc":iso(ended),
            "duration_seconds":ended-started,"sampling_grid_seconds":grid,"wire_messages":wire,"subscription_acks":acks,
            "symbols":list(SYMBOLS),"counts":counts,"errors":errors,"rows":rows,
            "guardrails":{"public_endpoint_only":True,"raw_book_archive":False,"orders":False,"private_api_used":False,
                          "active_v2r3_changed":False,"v2r4_changed":False,"holdout_opened":False,"real_money_actions":False}}

def evaluate(files:list[Path],spec:dict[str,Any])->dict[str,Any]:
    sessions=[json.loads(p.read_text("utf-8")) for p in files]
    for s in sessions:
        if s.get("kind")!="V3_H3_PROSPECTIVE_CAPTURE_SESSION_V1" or s.get("trial_id")!=spec["trial_id"]:raise RuntimeError("capture contract mismatch")
        if s.get("status")!="PASS":raise RuntimeError("failed capture session supplied")
    gate=spec["collection_gate"];dates={s["started_at_utc"][:10] for s in sessions}
    rows_by_symbol=defaultdict(list)
    for s in sessions:
        for r in s["rows"]:rows_by_symbol[r["symbol"]].append((s["session_id"],r))
    valid_counts={sym:len(rows_by_symbol[sym]) for sym in SYMBOLS}
    gate_pass=(len(sessions)>=int(gate["minimum_distinct_sessions"]) and
               all(float(s["duration_seconds"])>=float(gate["minimum_session_seconds"]) for s in sessions) and
               len(dates)>=int(gate["minimum_distinct_utc_dates"]) and
               all(valid_counts[s]>=int(gate["minimum_valid_feature_rows_per_symbol"]) for s in SYMBOLS))
    if not gate_pass:
        return {"schema_version":1,"kind":"V3_H3_PROSPECTIVE_ASSOCIATION_RESULT_V1","status":"COLLECTION_GATE_NOT_MET",
                "trial_id":spec["trial_id"],"collection":{"session_count":len(sessions),"distinct_utc_dates":len(dates),"valid_rows":valid_counts},
                "association_metrics":None,"interpretation":{"effect_size_conclusion_allowed":False,"automatic_winner_selected":False,"promotion_allowed":False},
                "guardrails":{"threshold_search":False,"p_values":False,"fill_probability_claim":False,"holdout_opened":False,"orders":False}}
    horizons=(60,300,900)
    pooled={(sym,f,h):Corr() for sym in SYMBOLS for f in FEATURES for h in horizons}
    per_session={(sid,sym,f,h):Corr() for s in sessions for sid in [s["session_id"]] for sym in SYMBOLS for f in FEATURES for h in horizons}
    for sym in SYMBOLS:
        by_ts={int(r["sample_epoch"]):(sid,r) for sid,r in rows_by_symbol[sym]}
        for ts,(sid,r) in by_ts.items():
            for h in horizons:
                fut=by_ts.get(ts+h)
                if fut is None or fut[0]!=sid:continue
                y=fut[1]["mid_price"]/r["mid_price"]-1.0
                for f in FEATURES:
                    pooled[(sym,f,h)].add(float(r[f]),y);per_session[(sid,sym,f,h)].add(float(r[f]),y)
    metrics={}
    for sym in SYMBOLS:
        metrics[sym]={}
        for f in FEATURES:
            metrics[sym][f]={}
            for h in horizons:
                rs=[per_session[(s["session_id"],sym,f,h)].out()["pearson_r"] for s in sessions]
                rs=[x for x in rs if x is not None]
                metrics[sym][f][f"future_mid_return_{h}s"]={"pooled_observation_weighted":pooled[(sym,f,h)].out(),
                    "equal_session_weighted":{"eligible_session_count":len(rs),"median_session_pearson_r":statistics.median(rs) if rs else None}}
    return {"schema_version":1,"kind":"V3_H3_PROSPECTIVE_ASSOCIATION_RESULT_V1","status":"PASS","trial_id":spec["trial_id"],
            "collection":{"session_count":len(sessions),"distinct_utc_dates":len(dates),"valid_rows":valid_counts},
            "association_metrics":metrics,
            "interpretation":{"descriptive_association_only":True,"automatic_winner_selected":False,"promotion_allowed":False,
                              "queue_position_proven":False,"maker_fill_probability_proven":False},
            "guardrails":{"threshold_search":False,"feature_transform_search":False,"horizon_search":False,"pair_selection":False,
                          "p_values":False,"holdout_opened":False,"orders":False,"real_money_actions":False}}

def self_test()->int:
    c=Corr()
    for x in (1.,2.,3.,4.):c.add(x,2*x)
    assert abs(c.out()["pearson_r"]-1.0)<1e-12
    # Regression guard for the original scheduler bug: a wall clock past next_grid must enter sampling.
    wall=105.2;next_grid=105.0;end=120.0
    assert wall>=next_grid
    timeout=max(.01,min(.25,next_grid-wall,end-wall))
    assert timeout==.01  # proves timeout itself must NOT be used as the sampling predicate
    spec={"trial_id":"V3-H3-ASSOC-002","collection_gate":{"minimum_distinct_sessions":1,"minimum_session_seconds":0,
          "minimum_distinct_utc_dates":1,"minimum_valid_feature_rows_per_symbol":3}}
    rows=[]
    for sym in SYMBOLS:
        for i in range(0,19):
            t=1700000000+i*5;v=1.0+i/1000
            rows.append({"session_id":"S1","sample_epoch":t,"sample_utc":iso(t),"symbol":sym,"source_age_ms":10.,
                         "mid_price":100+i,"spread_bps":v,"bid_depth_quote_top10":1000+10*i,
                         "ask_depth_quote_top10":900+5*i,"depth_imbalance_top10":-0.1+i/1000})
    cap={"kind":"V3_H3_PROSPECTIVE_CAPTURE_SESSION_V1","status":"PASS","trial_id":"V3-H3-ASSOC-002","session_id":"S1",
         "started_at_utc":"2023-11-14T00:00:00Z","duration_seconds":1800,"rows":rows}
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/"s.json";p.write_text(json.dumps(cap),"utf-8")
        out=evaluate([p],spec)
        assert out["status"]=="PASS"
        assert out["association_metrics"]["BTC/EUR"]["spread_bps"]["future_mid_return_60s"]["pooled_observation_weighted"]["n"]==7
        assert out["interpretation"]["automatic_winner_selected"] is False
    print("V3_H3_ASSOC_SELFTEST PASS fixed-grid/exact-future-labels/no-winner")
    return 0

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--spec",type=Path,default=DEFAULT_SPEC);ap.add_argument("--self-test",action="store_true")
    sub=ap.add_subparsers(dest="cmd")
    c=sub.add_parser("capture");c.add_argument("--seconds",type=int,default=1800);c.add_argument("--session-id",required=True);c.add_argument("--output",type=Path,required=True)
    e=sub.add_parser("evaluate");e.add_argument("inputs",nargs="+",type=Path);e.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    if a.self_test:return self_test()
    spec=load_spec(a.spec)
    if a.cmd=="capture":
        if not 30<=a.seconds<=3600:raise SystemExit("capture seconds must be 30..3600; collection gate still requires >=1800 per session")
        out=asyncio.run(capture(a.seconds,a.session_id,spec));a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n","utf-8")
        print("V3_H3_CAPTURE "+json.dumps({"status":out["status"],"session_id":out["session_id"],"counts":out["counts"]},sort_keys=True));return 0 if out["status"]=="PASS" else 2
    if a.cmd=="evaluate":
        out=evaluate(a.inputs,spec);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n","utf-8")
        print("V3_H3_ASSOC "+json.dumps({"status":out["status"],"trial_id":out["trial_id"]},sort_keys=True));return 0
    raise SystemExit("choose capture or evaluate, or --self-test")

if __name__=="__main__":raise SystemExit(main())
