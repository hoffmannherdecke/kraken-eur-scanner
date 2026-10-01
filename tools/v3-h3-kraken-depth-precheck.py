#!/usr/bin/env python3
"""Bounded public Kraken L2 snapshot precheck for V3-H3.

Public REST Depth only. No account, no orders, no strategy mutation, no holdout,
no persistent capture. This verifies snapshot semantics and simple depth math only.
"""
from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UA="kraken-eur-scanner-v3-h3-depth-precheck/1.0"

def utcnow()->str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def get_json(url:str,timeout:float)->Any:
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        raw=r.read().decode("utf-8")
        if not 200 <= r.status < 300:
            raise RuntimeError(f"HTTP {r.status}: {raw[:200]}")
        return json.loads(raw)

def parse_levels(levels:list[Any])->list[tuple[float,float,float]]:
    out=[]
    for row in levels:
        if not isinstance(row,list) or len(row)<2:
            continue
        price=float(row[0]); volume=float(row[1]); ts=float(row[2]) if len(row)>2 else 0.0
        if price<=0 or volume<=0:
            continue
        out.append((price,volume,ts))
    return out

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--pairs",default="XBTEUR,ETHEUR,SOLEUR")
    ap.add_argument("--count",type=int,default=10)
    ap.add_argument("--timeout-seconds",type=float,default=15.0)
    ap.add_argument("--output",type=Path)
    args=ap.parse_args()
    pairs=[x.strip().upper() for x in args.pairs.split(",") if x.strip()]
    if not pairs or len(pairs)>10:
        raise SystemExit("pairs must contain 1..10 values")
    if not 1 <= args.count <= 100:
        raise SystemExit("--count must be 1..100")

    rows=[]
    for pair in pairs:
        url="https://api.kraken.com/0/public/Depth?"+urllib.parse.urlencode({"pair":pair,"count":args.count})
        data=get_json(url,args.timeout_seconds)
        if data.get("error"):
            raise RuntimeError(f"{pair}: Kraken errors: {data['error']}")
        result=data.get("result") or {}
        if not result:
            raise RuntimeError(f"{pair}: empty result")
        key=next(iter(result.keys()))
        book=result[key]
        asks=parse_levels(book.get("asks") or [])
        bids=parse_levels(book.get("bids") or [])
        if not asks or not bids:
            raise RuntimeError(f"{pair}: missing bid/ask levels")
        best_ask=min(x[0] for x in asks)
        best_bid=max(x[0] for x in bids)
        if best_ask <= best_bid:
            raise RuntimeError(f"{pair}: crossed/non-positive spread")
        mid=(best_ask+best_bid)/2.0
        spread_bps=(best_ask-best_bid)/mid*10000.0
        bid_depth=sum(p*v for p,v,_ in bids[:args.count])
        ask_depth=sum(p*v for p,v,_ in asks[:args.count])
        rows.append({
            "requested_pair":pair,
            "response_pair_key":key,
            "bid_levels":len(bids),
            "ask_levels":len(asks),
            "best_bid":best_bid,
            "best_ask":best_ask,
            "mid":mid,
            "spread_bps":spread_bps,
            "bid_depth_quote_top_n":bid_depth,
            "ask_depth_quote_top_n":ask_depth
        })

    result={
      "schema_version":1,
      "kind":"V3_H3_KRAKEN_PUBLIC_DEPTH_PRECHECK_V1",
      "checked_at_utc":utcnow(),
      "status":"PASS",
      "pairs":rows,
      "interpretation":{
        "snapshot_semantics_only":True,
        "websocket_delta_sequence_proven":False,
        "queue_position_proven":False,
        "maker_fill_probability_proven":False,
        "performance_conclusion_allowed":False
      },
      "guardrails":{
        "public_endpoint_only":True,
        "api_key_used":False,
        "private_data_accessed":False,
        "persistent_capture_started":False,
        "performance_trial_started":False,
        "holdout_opened":False,
        "active_v2r3_changed":False,
        "v2r4_changed":False,
        "orders":False,
        "real_money_actions":False
      }
    }
    raw=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(raw,"utf-8")
    print(raw,end="")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
