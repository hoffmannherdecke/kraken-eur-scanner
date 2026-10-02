#!/usr/bin/env python3
from __future__ import annotations
import argparse,asyncio,json,math,time,zlib
from dataclasses import dataclass,field
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
WS_URL="wss://ws.kraken.com/v2"
def now(): return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def dt(s): return datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(timezone.utc)
def piece(v):
    s=format(v,"f").replace(".","").lstrip("0"); return s or "0"
@dataclass
class M:
    n:int=0; s:float=0.; s2:float=0.; lo:float|None=None; hi:float|None=None
    def add(self,x):
        if not math.isfinite(x): raise RuntimeError("nonfinite")
        self.n+=1;self.s+=x;self.s2+=x*x;self.lo=x if self.lo is None else min(self.lo,x);self.hi=x if self.hi is None else max(self.hi,x)
    def out(self):
        if not self.n:return {"n":0,"mean":None,"std_population":None,"min":None,"max":None}
        m=self.s/self.n
        return {"n":self.n,"mean":m,"std_population":math.sqrt(max(0.,self.s2/self.n-m*m)),"min":self.lo,"max":self.hi}
@dataclass
class B:
    depth:int
    bids:dict=field(default_factory=dict);asks:dict=field(default_factory=dict)
    snaps:int=0;updates:int=0;ok:int=0;bad:int=0;max_age:float|None=None
    ms:dict=field(default_factory=lambda:{k:M() for k in ("spread_bps","bid_depth_quote_top10","ask_depth_quote_top10","depth_imbalance_top10")})
    def apply(self,d,rows):
        for r in rows:
            p,q=r.get("price"),r.get("qty")
            if not isinstance(p,Decimal) or not isinstance(q,Decimal) or p<=0 or q<0: raise RuntimeError("bad level")
            if q==0:d.pop(p,None)
            else:d[p]=q
    def trim(self):
        self.bids=dict(sorted(self.bids.items(),reverse=True)[:self.depth]);self.asks=dict(sorted(self.asks.items())[:self.depth])
    def crc(self):
        x=[]
        for p,q in sorted(self.asks.items())[:10]:x += [piece(p),piece(q)]
        for p,q in sorted(self.bids.items(),reverse=True)[:10]:x += [piece(p),piece(q)]
        return zlib.crc32("".join(x).encode("ascii")) & 0xffffffff
    def process(self,typ,r,recv):
        if typ=="snapshot":self.bids.clear();self.asks.clear()
        self.apply(self.bids,r.get("bids") or []);self.apply(self.asks,r.get("asks") or []);self.trim()
        if not self.bids or not self.asks:raise RuntimeError("empty book")
        if self.crc()!=int(r["checksum"]):self.bad+=1;raise RuntimeError("checksum")
        self.ok+=1;self.snaps+=typ=="snapshot";self.updates+=typ=="update"
        bid=max(self.bids);ask=min(self.asks);mid=(bid+ask)/2
        if not ask>bid:raise RuntimeError("crossed")
        bd=sum(p*q for p,q in self.bids.items());ad=sum(p*q for p,q in self.asks.items());den=bd+ad
        vals={"spread_bps":float((ask-bid)/mid*Decimal(10000)),"bid_depth_quote_top10":float(bd),
              "ask_depth_quote_top10":float(ad),"depth_imbalance_top10":float((bd-ad)/den)}
        for k,v in vals.items():self.ms[k].add(v)
        if r.get("timestamp"):
            age=(dt(recv)-dt(str(r["timestamp"]))).total_seconds()*1000
            self.max_age=age if self.max_age is None else max(self.max_age,age)
async def run(symbols,seconds):
    from websockets.asyncio.client import connect
    books={s:B(10) for s in symbols};errs=[];acks=0;wire=0
    async with connect(WS_URL,open_timeout=15,ping_interval=10,ping_timeout=10,max_size=8*1024*1024) as ws:
        await ws.send(json.dumps({"method":"subscribe","params":{"channel":"book","symbol":symbols,"depth":10,"snapshot":True},"req_id":1}))
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            try: raw=await asyncio.wait_for(ws.recv(),timeout=max(.05,min(1.,end-time.monotonic())))
            except asyncio.TimeoutError:continue
            wire+=1;recv=now();j=json.loads(raw,parse_float=Decimal)
            if j.get("method")=="subscribe":
                acks+=j.get("success") is True
                if j.get("success") is not True:errs.append(str(j.get("error")))
                continue
            if j.get("channel")!="book" or j.get("type") not in ("snapshot","update"):continue
            for r in j.get("data") or []:
                s=str(r.get("symbol") or "")
                try: books[s].process(j["type"],r,recv)
                except Exception as e:errs.append(f"{s}:{type(e).__name__}:{e}");break
            if errs:break
    per={s:{"snapshots":b.snaps,"updates":b.updates,"checksum_pass":b.ok,"checksum_fail":b.bad,
            "max_source_age_ms":round(b.max_age,3) if b.max_age is not None else None,
            "features":{k:v.out() for k,v in b.ms.items()}} for s,b in books.items()}
    ok=not errs and all(r["snapshots"]>=1 and r["checksum_pass"]>=1 and r["checksum_fail"]==0 for r in per.values())
    return {"schema_version":1,"kind":"V3_H3_ORDERBOOK_STATE_CAPTURE_V1","status":"PASS" if ok else "FAIL","symbols":symbols,"depth":10,
            "seconds":seconds,"wire_messages":wire,"subscription_acks":acks,"per_symbol":per,"errors":errs,
            "interpretation":{"state_descriptive_only":True,"future_outcomes_joined":False,"thresholds_selected":False,
              "directional_signal_created":False,"queue_position_proven":False,"maker_fill_probability_proven":False},
            "guardrails":{"public_endpoint_only":True,"raw_book_archive":False,"automatic_schedule_enabled":False,
              "active_v2r3_changed":False,"v2r4_changed":False,"private_api_used":False,"holdout_opened":False,"orders":False,"real_money_actions":False}}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--seconds",type=float,default=12);ap.add_argument("--output",type=Path,required=True);a=ap.parse_args()
    syms=["BTC/EUR","ETH/EUR","SOL/EUR"]
    if not 5<=a.seconds<=30:raise SystemExit("seconds 5..30")
    o=asyncio.run(run(syms,a.seconds));a.output.write_text(json.dumps(o,indent=2,sort_keys=True)+"\n","utf-8")
    print("V3_H3_ORDERBOOK_STATE "+json.dumps({"status":o["status"],"errors":o["errors"]},sort_keys=True));return 0 if o["status"]=="PASS" else 2
if __name__=="__main__":raise SystemExit(main())
