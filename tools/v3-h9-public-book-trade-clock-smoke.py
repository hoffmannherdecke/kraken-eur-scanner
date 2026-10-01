#!/usr/bin/env python3
"""Bounded same-connection Kraken Spot WS-v2 book+trade clock smoke for V3-H9.

Public research-only protocol evidence:
- book depth=10 is maintained and CRC32 validated;
- trade updates are captured on the same websocket connection;
- each trade is compared only to the latest locally reconciled book state;
- exchange timestamps and arrival timestamps are preserved;
- no queue inference, maker-fill estimate, routing decision, threshold or order path.
"""
from __future__ import annotations
import argparse,asyncio,json,math,time,zlib
from dataclasses import dataclass,field
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

WS_URL="wss://ws.kraken.com/v2"

def utcnow()->str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def parse_utc(v:str)->datetime:
    return datetime.fromisoformat(v.replace("Z","+00:00")).astimezone(timezone.utc)
def piece(v:Decimal)->str:
    s=format(v,"f").replace(".","").lstrip("0"); return s or "0"

@dataclass
class Book:
    depth:int
    bids:dict[Decimal,Decimal]=field(default_factory=dict)
    asks:dict[Decimal,Decimal]=field(default_factory=dict)
    last_exchange_at_utc:str|None=None
    last_received_at_utc:str|None=None
    checksum_pass:int=0
    checksum_fail:int=0
    snapshots:int=0
    updates:int=0
    def trim(self):
        self.bids=dict(sorted(self.bids.items(),key=lambda kv:kv[0],reverse=True)[:self.depth])
        self.asks=dict(sorted(self.asks.items(),key=lambda kv:kv[0])[:self.depth])
    def apply(self,side:str,rows:list[dict[str,Any]]):
        d=self.bids if side=="bids" else self.asks
        for r in rows:
            p=r.get("price");q=r.get("qty")
            if not isinstance(p,Decimal) or not isinstance(q,Decimal): raise RuntimeError("book decimal parse failure")
            if p<=0 or q<0: raise RuntimeError("invalid book level")
            if q==0:d.pop(p,None)
            else:d[p]=q
    def crc(self)->int:
        parts=[]
        for p,q in sorted(self.asks.items(),key=lambda kv:kv[0])[:10]:parts += [piece(p),piece(q)]
        for p,q in sorted(self.bids.items(),key=lambda kv:kv[0],reverse=True)[:10]:parts += [piece(p),piece(q)]
        return zlib.crc32("".join(parts).encode("ascii")) & 0xffffffff
    def process(self,typ:str,row:dict[str,Any],received:str):
        if typ=="snapshot":self.bids.clear();self.asks.clear()
        bids=row.get("bids") or [];asks=row.get("asks") or []
        if not isinstance(bids,list) or not isinstance(asks,list):raise RuntimeError("book arrays invalid")
        self.apply("bids",bids);self.apply("asks",asks);self.trim()
        if not self.bids or not self.asks:raise RuntimeError("book empty")
        if self.crc()!=int(row["checksum"]):
            self.checksum_fail+=1;raise RuntimeError("checksum mismatch")
        self.checksum_pass+=1
        if typ=="snapshot":self.snapshots+=1
        else:self.updates+=1
        self.last_exchange_at_utc=str(row.get("timestamp") or "")
        self.last_received_at_utc=received
    def top(self)->tuple[Decimal,Decimal]:
        return max(self.bids),min(self.asks)

async def capture(symbols:list[str],seconds:float,depth:int)->dict[str,Any]:
    from websockets.asyncio.client import connect
    books={s:Book(depth) for s in symbols}
    trade_ids={s:[] for s in symbols}
    counts={s:0 for s in symbols}
    aligned={s:0 for s in symbols}
    book_ahead={s:0 for s in symbols}
    no_book={s:0 for s in symbols}
    lag_ms={s:[] for s in symbols}
    recv_lag_ms={s:[] for s in symbols}
    trade_exchange_age_ms={s:[] for s in symbols}
    errors=[];wire=0;acks=0
    started=utcnow()
    async with connect(WS_URL,open_timeout=15,ping_interval=10,ping_timeout=10,max_size=8*1024*1024) as ws:
        await ws.send(json.dumps({"method":"subscribe","params":{"channel":"book","symbol":symbols,"depth":depth,"snapshot":True},"req_id":1}))
        await ws.send(json.dumps({"method":"subscribe","params":{"channel":"trade","symbol":symbols,"snapshot":False},"req_id":2}))
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            try:raw=await asyncio.wait_for(ws.recv(),timeout=max(0.05,min(1.0,deadline-time.monotonic())))
            except asyncio.TimeoutError:continue
            wire+=1;received=utcnow()
            msg=json.loads(raw,parse_float=Decimal)
            if not isinstance(msg,dict):continue
            if msg.get("method")=="subscribe":
                if msg.get("success") is not True:errors.append("subscription:"+str(msg.get("error")))
                else:acks+=1
                continue
            ch=msg.get("channel");typ=str(msg.get("type") or "")
            data=msg.get("data") or []
            if not isinstance(data,list):errors.append("data_not_list");break
            if ch=="book" and typ in {"snapshot","update"}:
                for row in data:
                    if not isinstance(row,dict):continue
                    s=str(row.get("symbol") or "")
                    if s not in books:continue
                    try:books[s].process(typ,row,received)
                    except Exception as exc:errors.append(f"{s}:{type(exc).__name__}:{str(exc)}");break
                if errors:break
            elif ch=="trade" and typ=="update":
                for tr in data:
                    if not isinstance(tr,dict):continue
                    s=str(tr.get("symbol") or "")
                    if s not in books:continue
                    counts[s]+=1
                    tid=int(tr["trade_id"]);trade_ids[s].append(tid)
                    tex=str(tr["timestamp"]);tdt=parse_utc(tex);rdt=parse_utc(received)
                    trade_exchange_age_ms[s].append((rdt-tdt).total_seconds()*1000.0)
                    b=books[s]
                    if not b.last_exchange_at_utc:
                        no_book[s]+=1;continue
                    bdt=parse_utc(b.last_exchange_at_utc)
                    if bdt<=tdt:
                        aligned[s]+=1
                        lag_ms[s].append((tdt-bdt).total_seconds()*1000.0)
                    else:
                        book_ahead[s]+=1
                    if b.last_received_at_utc:
                        recv_lag_ms[s].append((rdt-parse_utc(b.last_received_at_utc)).total_seconds()*1000.0)
                    # Price is intentionally not interpreted against the book here.
                    _=tr.get("price");_=tr.get("side");_=tr.get("qty");_=tr.get("ord_type")
            if errors:break
    def stats(xs:list[float])->dict[str,Any]:
        ys=sorted(x for x in xs if math.isfinite(x))
        if not ys:return {"n":0,"mean":None,"median":None,"p90":None,"max":None}
        idx=min(len(ys)-1,max(0,math.ceil(0.9*len(ys))-1))
        return {"n":len(ys),"mean":sum(ys)/len(ys),"median":statistics_median(ys),"p90":ys[idx],"max":ys[-1]}
    def seq(ids:list[int])->dict[str,Any]:
        if not ids:return {"n":0,"duplicates":0,"out_of_order":0,"gaps":0}
        dup=len(ids)-len(set(ids));ooo=sum(1 for a,b in zip(ids,ids[1:]) if b<a);gaps=sum(max(0,b-a-1) for a,b in zip(ids,ids[1:]) if b>a)
        return {"n":len(ids),"duplicates":dup,"out_of_order":ooo,"gaps":gaps,"min":min(ids),"max":max(ids)}
    per={}
    for s in symbols:
        b=books[s]
        per[s]={
          "book":{"snapshots":b.snapshots,"updates":b.updates,"checksum_pass":b.checksum_pass,"checksum_fail":b.checksum_fail},
          "trades":counts[s],"trade_id_sequence":seq(trade_ids[s]),
          "clock_join":{"book_at_or_before_trade":aligned[s],"book_clock_ahead_of_trade":book_ahead[s],"no_book_yet":no_book[s],
            "trade_minus_preceding_book_exchange_ms":stats(lag_ms[s]),
            "trade_receive_minus_latest_book_receive_ms":stats(recv_lag_ms[s]),
            "trade_exchange_to_receive_ms":stats(trade_exchange_age_ms[s])}
        }
    total_trades=sum(counts.values());total_aligned=sum(aligned.values())
    complete=(not errors and all(books[s].snapshots>=1 and books[s].checksum_fail==0 for s in symbols) and total_trades>0 and total_aligned>0)
    return {
      "schema_version":1,"kind":"V3_H9_PUBLIC_BOOK_TRADE_CLOCK_SMOKE_V1","checked_at_utc":utcnow(),
      "started_at_utc":started,"status":"PASS" if complete else "FAIL","endpoint":WS_URL,
      "symbols":symbols,"depth":depth,"seconds":seconds,"wire_messages":wire,"subscription_acks":acks,
      "per_symbol":per,"totals":{"trades":total_trades,"aligned_preceding_book_trades":total_aligned},"errors":errors,
      "interpretation":{
        "same_websocket_connection":True,"book_crc_reconciliation_used":True,
        "trade_id_is_public_per_book_sequence":True,"book_and_trade_exchange_clocks_observed":True,
        "arrival_order_and_exchange_time_both_preserved":True,
        "queue_position_proven":False,"maker_fill_probability_proven":False,
        "fill_before_deadline_probability_proven":False,"cancel_fill_race_proven":False,
        "adverse_selection_modelled":False,"routing_decision_allowed":False},
      "retention":"compact_clock_and_sequence_summary_only_no_raw_archive",
      "guardrails":{"public_endpoint_only":True,"api_key_used":False,"private_data_accessed":False,
        "threshold_selection_performed":False,"performance_trial_started":False,"holdout_opened":False,
        "active_v2r3_changed":False,"v2r4_changed":False,"live_order_routing_changed":False,
        "orders":False,"leverage_action":False,"real_money_actions":False}
    }

def statistics_median(xs:list[float])->float:
    n=len(xs);m=n//2
    return xs[m] if n%2 else (xs[m-1]+xs[m])/2.0

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--symbols",default="BTC/EUR,ETH/EUR,SOL/EUR")
    ap.add_argument("--seconds",type=float,default=15.0)
    ap.add_argument("--depth",type=int,default=10,choices=(10,25,100,500,1000))
    ap.add_argument("--output",type=Path)
    a=ap.parse_args();symbols=[x.strip().upper() for x in a.symbols.split(",") if x.strip()]
    if not 1<=len(symbols)<=5:raise SystemExit("symbols must contain 1..5")
    if not 5<=a.seconds<=30:raise SystemExit("seconds must be 5..30")
    out=asyncio.run(capture(symbols,a.seconds,a.depth))
    raw=json.dumps(out,indent=2,sort_keys=True)+"\n"
    if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(raw,"utf-8")
    print(raw,end="");return 0 if out["status"]=="PASS" else 2
if __name__=="__main__":raise SystemExit(main())
