#!/usr/bin/env python3
"""Bounded public Kraken Spot WS-v2 L2 book reconciliation smoke for V3-H3.

Research/infrastructure only:
- public wss://ws.kraken.com/v2, channel=book, depth=10;
- preserves decimal text via Decimal parsing;
- applies snapshot + all update levels, trims to subscribed depth;
- validates Kraken CRC32 top-10 checksum;
- reconnects in bounded independent cycles;
- persists compact evidence only, never raw endless book traffic;
- no account, private API, evaluator, orders, leverage or real-money action.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

WS_URL="wss://ws.kraken.com/v2"

def utcnow()->str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def parse_utc(value:str)->datetime:
    return datetime.fromisoformat(value.replace("Z","+00:00")).astimezone(timezone.utc)

def checksum_piece(v:Decimal)->str:
    s=format(v,"f").replace(".","").lstrip("0")
    return s or "0"

@dataclass
class Book:
    depth:int
    bids:dict[Decimal,Decimal]=field(default_factory=dict)
    asks:dict[Decimal,Decimal]=field(default_factory=dict)
    snapshots:int=0
    updates:int=0
    checksum_pass:int=0
    checksum_fail:int=0
    last_exchange_at_utc:str|None=None
    last_received_at_utc:str|None=None
    max_source_age_ms:float|None=None

    def trim(self)->None:
        self.bids=dict(sorted(self.bids.items(),key=lambda kv:kv[0],reverse=True)[:self.depth])
        self.asks=dict(sorted(self.asks.items(),key=lambda kv:kv[0])[:self.depth])

    def apply_levels(self,side:str,levels:list[dict[str,Any]])->None:
        book=self.bids if side=="bids" else self.asks
        for row in levels:
            if not isinstance(row,dict):
                raise RuntimeError(f"{side}: non-object level")
            price=row.get("price"); qty=row.get("qty")
            if not isinstance(price,Decimal) or not isinstance(qty,Decimal):
                raise RuntimeError(f"{side}: price/qty must be Decimal")
            if price<=0 or qty<0:
                raise RuntimeError(f"{side}: invalid price/qty")
            if qty==0:
                book.pop(price,None)
            else:
                book[price]=qty

    def crc32(self)->int:
        chunks=[]
        for price,qty in sorted(self.asks.items(),key=lambda kv:kv[0])[:10]:
            chunks.append(checksum_piece(price)); chunks.append(checksum_piece(qty))
        for price,qty in sorted(self.bids.items(),key=lambda kv:kv[0],reverse=True)[:10]:
            chunks.append(checksum_piece(price)); chunks.append(checksum_piece(qty))
        return zlib.crc32("".join(chunks).encode("ascii")) & 0xffffffff

    def process(self,msg_type:str,row:dict[str,Any],received_at:str)->None:
        if msg_type=="snapshot":
            self.bids.clear(); self.asks.clear()
        bids=row.get("bids") or []; asks=row.get("asks") or []
        if not isinstance(bids,list) or not isinstance(asks,list):
            raise RuntimeError("bids/asks must be arrays")
        self.apply_levels("bids",bids); self.apply_levels("asks",asks)
        self.trim()
        if not self.bids or not self.asks:
            raise RuntimeError("book side empty after reconciliation")
        expected=int(row["checksum"])
        actual=self.crc32()
        if expected!=actual:
            self.checksum_fail+=1
            raise RuntimeError(f"checksum mismatch expected={expected} actual={actual}")
        self.checksum_pass+=1
        if msg_type=="snapshot": self.snapshots+=1
        elif msg_type=="update": self.updates+=1
        self.last_exchange_at_utc=str(row.get("timestamp") or "")
        self.last_received_at_utc=received_at
        if self.last_exchange_at_utc:
            age=(parse_utc(received_at)-parse_utc(self.last_exchange_at_utc)).total_seconds()*1000.0
            self.max_source_age_ms=age if self.max_source_age_ms is None else max(self.max_source_age_ms,age)

async def one_cycle(symbols:list[str],depth:int,seconds:float,cycle:int)->dict[str,Any]:
    from websockets.asyncio.client import connect

    books={s:Book(depth=depth) for s in symbols}
    started=utcnow(); started_mono=time.monotonic()
    wire=0; acks=0; book_msgs=0; errors=[]

    async with connect(
        WS_URL,open_timeout=15,ping_interval=10,ping_timeout=10,max_size=8*1024*1024
    ) as ws:
        await ws.send(json.dumps({
            "method":"subscribe",
            "params":{"channel":"book","symbol":symbols,"depth":depth,"snapshot":True},
            "req_id":cycle,
        }))
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            timeout=max(0.05,min(1.0,deadline-time.monotonic()))
            try:
                raw=await asyncio.wait_for(ws.recv(),timeout=timeout)
            except asyncio.TimeoutError:
                continue
            wire+=1
            received=utcnow()
            msg=json.loads(raw,parse_float=Decimal)
            if not isinstance(msg,dict):
                continue
            if msg.get("method")=="subscribe":
                if msg.get("success") is not True:
                    errors.append("subscription_failed:"+str(msg.get("error") or "unknown"))
                else:
                    acks+=1
                continue
            if msg.get("channel")!="book":
                continue
            msg_type=str(msg.get("type") or "")
            if msg_type not in {"snapshot","update"}:
                continue
            data=msg.get("data") or []
            if not isinstance(data,list):
                errors.append("book_data_not_list")
                continue
            book_msgs+=1
            for row in data:
                if not isinstance(row,dict):
                    errors.append("book_row_not_object"); continue
                symbol=str(row.get("symbol") or "")
                if symbol not in books:
                    errors.append("unexpected_symbol:"+symbol); continue
                try:
                    books[symbol].process(msg_type,row,received)
                except Exception as exc:
                    errors.append(f"{symbol}:{type(exc).__name__}:{str(exc)[:180]}")
                    break
            if errors:
                break

    elapsed=round(time.monotonic()-started_mono,3)
    per_symbol={}
    for s,b in books.items():
        best_bid=max(b.bids) if b.bids else None
        best_ask=min(b.asks) if b.asks else None
        spread_bps=None
        if best_bid is not None and best_ask is not None and best_ask>best_bid:
            mid=(best_bid+best_ask)/Decimal(2)
            spread_bps=float((best_ask-best_bid)/mid*Decimal(10000))
        per_symbol[s]={
            "snapshots":b.snapshots,"updates":b.updates,
            "checksum_pass":b.checksum_pass,"checksum_fail":b.checksum_fail,
            "bid_levels":len(b.bids),"ask_levels":len(b.asks),
            "spread_bps_last":round(spread_bps,6) if spread_bps is not None else None,
            "last_exchange_at_utc":b.last_exchange_at_utc,
            "last_received_at_utc":b.last_received_at_utc,
            "max_source_age_ms":round(b.max_source_age_ms,3) if b.max_source_age_ms is not None else None,
        }
    complete=(
        not errors
        and all(x["snapshots"]>=1 for x in per_symbol.values())
        and all(x["checksum_pass"]>=1 for x in per_symbol.values())
        and all(x["checksum_fail"]==0 for x in per_symbol.values())
    )
    return {
        "cycle":cycle,"started_at_utc":started,"elapsed_seconds":elapsed,
        "wire_messages":wire,"subscription_acks":acks,"book_messages":book_msgs,
        "symbols":per_symbol,"errors":errors,"complete":complete,
    }

async def run(args)->dict[str,Any]:
    cycles=[]
    for n in range(1,args.cycles+1):
        cycles.append(await one_cycle(args.symbols,args.depth,args.seconds_per_cycle,n))
        if not cycles[-1]["complete"]:
            break
        if n<args.cycles:
            await asyncio.sleep(args.reconnect_pause_seconds)
    all_complete=len(cycles)==args.cycles and all(c["complete"] for c in cycles)
    update_total=sum(
        s["updates"] for c in cycles for s in c["symbols"].values()
    )
    checksum_pass_total=sum(
        s["checksum_pass"] for c in cycles for s in c["symbols"].values()
    )
    checksum_fail_total=sum(
        s["checksum_fail"] for c in cycles for s in c["symbols"].values()
    )
    return {
        "schema_version":1,
        "kind":"V3_H3_KRAKEN_SPOT_WS_BOOK_RECONCILIATION_SMOKE_V1",
        "checked_at_utc":utcnow(),
        "status":"PASS" if all_complete and update_total>0 and checksum_fail_total==0 else "FAIL",
        "endpoint":WS_URL,
        "channel":"book",
        "depth":args.depth,
        "symbols":args.symbols,
        "cycles_requested":args.cycles,
        "cycles_completed":len(cycles),
        "seconds_per_cycle":args.seconds_per_cycle,
        "reconnect_pause_seconds":args.reconnect_pause_seconds,
        "cycles":cycles,
        "totals":{
            "updates":update_total,
            "checksum_pass":checksum_pass_total,
            "checksum_fail":checksum_fail_total,
        },
        "interpretation":{
            "l2_snapshot_and_delta_reconciliation_proven":all_complete,
            "crc32_top10_validation_used":True,
            "bounded_reconnect_resubscribe_proven":all_complete and args.cycles>=2,
            "explicit_sequence_number_observed":False,
            "checksum_used_as_synchronization_guard":True,
            "queue_position_proven":False,
            "maker_fill_probability_proven":False,
            "performance_conclusion_allowed":False,
        },
        "retention":"compact_summary_only_no_raw_book_archive",
        "guardrails":{
            "public_endpoint_only":True,
            "api_key_used":False,
            "private_data_accessed":False,
            "active_v2r3_changed":False,
            "v2r4_changed":False,
            "evaluator_invoked":False,
            "threshold_selection_performed":False,
            "holdout_opened":False,
            "orders":False,
            "leverage_action":False,
            "real_money_actions":False,
        },
    }

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--symbols",default="BTC/EUR,ETH/EUR,SOL/EUR")
    ap.add_argument("--depth",type=int,default=10,choices=(10,25,100,500,1000))
    ap.add_argument("--cycles",type=int,default=2)
    ap.add_argument("--seconds-per-cycle",type=float,default=12.0)
    ap.add_argument("--reconnect-pause-seconds",type=float,default=1.0)
    ap.add_argument("--output",type=Path)
    a=ap.parse_args()
    a.symbols=[x.strip().upper() for x in a.symbols.split(",") if x.strip()]
    if not 1<=len(a.symbols)<=5: raise SystemExit("symbols must contain 1..5 pairs")
    if not 1<=a.cycles<=3: raise SystemExit("cycles must be 1..3")
    if not 5<=a.seconds_per_cycle<=30: raise SystemExit("seconds-per-cycle must be 5..30")
    result=asyncio.run(run(a))
    raw=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(raw,"utf-8")
    print(raw,end="")
    return 0 if result["status"]=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
