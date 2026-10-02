#!/usr/bin/env python3
"""Bounded public read-only source smoke for V3 H10/H11.

No authentication, wallet, signer, private key, orders, strategy changes or schedules.
"""
from __future__ import annotations
import json,urllib.request,urllib.parse
from datetime import datetime,timezone
from typing import Any

UA="kraken-eur-scanner-v3-public-source-smoke/1.0"
ZERO="0x"+"0"*40

def now()->str:return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def request_json(url:str,method:str="GET",body:dict[str,Any]|None=None,timeout:float=20.0)->Any:
    data=None
    headers={"User-Agent":UA,"Accept":"application/json"}
    if body is not None:
        data=json.dumps(body,separators=(",",":")).encode()
        headers["Content-Type"]="application/json"
    req=urllib.request.Request(url,data=data,headers=headers,method=method)
    with urllib.request.urlopen(req,timeout=timeout) as r:
        raw=r.read().decode("utf-8")
        if not 200<=r.status<300:raise RuntimeError(f"HTTP {r.status} {url}")
        return json.loads(raw)

def hyperliquid()->dict[str,Any]:
    url="https://api.hyperliquid.xyz/info"
    mids=request_json(url,"POST",{"type":"allMids"})
    if not isinstance(mids,dict) or not mids:raise RuntimeError("Hyperliquid allMids unexpected shape")
    numeric=0
    for v in mids.values():
        try: float(v);numeric+=1
        except Exception: pass
    if numeric<1:raise RuntimeError("Hyperliquid allMids has no numeric values")
    open_orders=request_json(url,"POST",{"type":"openOrders","user":ZERO})
    fills=request_json(url,"POST",{"type":"userFills","user":ZERO})
    if not isinstance(open_orders,list):raise RuntimeError("Hyperliquid openOrders unexpected shape")
    if not isinstance(fills,list):raise RuntimeError("Hyperliquid userFills unexpected shape")
    return {
        "status":"PASS",
        "endpoint":url,
        "all_mids_count":len(mids),
        "all_mids_numeric_count":numeric,
        "public_zero_address_open_orders_shape":"LIST",
        "public_zero_address_user_fills_shape":"LIST",
        "address_selection_or_trader_quality_tested":False
    }

def token_ids(m:dict[str,Any])->list[str]:
    raw=m.get("clobTokenIds")
    if isinstance(raw,str):
        try: raw=json.loads(raw)
        except Exception:return []
    if isinstance(raw,list):return [str(x) for x in raw if str(x)]
    outs=m.get("outcomes")
    if isinstance(outs,dict):
        out=[]
        for k in ("yes","no"):
            v=outs.get(k)
            if isinstance(v,dict):
                t=v.get("tokenId") or v.get("token_id")
                if t:out.append(str(t))
        return out
    return []

def polymarket()->dict[str,Any]:
    events_url="https://gamma-api.polymarket.com/events/keyset?closed=false&limit=20"
    events=request_json(events_url)
    evs=(events.get("events") if isinstance(events,dict) else None) or (events.get("items") if isinstance(events,dict) else None)
    if not isinstance(evs,list) or not evs:raise RuntimeError("Polymarket events unexpected/empty shape")

    markets_url="https://gamma-api.polymarket.com/markets/keyset?closed=false&limit=20"
    markets=request_json(markets_url)
    ms=(markets.get("markets") if isinstance(markets,dict) else None) or (markets.get("items") if isinstance(markets,dict) else None)
    if not isinstance(ms,list) or not ms:raise RuntimeError("Polymarket markets unexpected/empty shape")

    selected=None
    attempts=0
    for x in ms[:12]:
        mid=str(x.get("id") or "") if isinstance(x,dict) else ""
        if not mid:continue
        attempts+=1
        try:
            m=request_json("https://gamma-api.polymarket.com/markets/"+urllib.parse.quote(mid,safe=""))
            toks=token_ids(m)
            for tok in toks[:2]:
                try:
                    q=urllib.parse.urlencode({"token_id":tok})
                    book=request_json("https://clob.polymarket.com/book?"+q)
                    if not isinstance(book,dict) or not isinstance(book.get("bids"),list) or not isinstance(book.get("asks"),list):
                        continue
                    midpoint=request_json("https://clob.polymarket.com/midpoint?"+q)
                    spread=request_json("https://clob.polymarket.com/spread?"+q)
                    if not isinstance(midpoint,dict) or "mid" not in midpoint and "midpoint" not in midpoint:
                        if "price" not in midpoint: raise RuntimeError("midpoint unexpected shape")
                    if not isinstance(spread,dict) or "spread" not in spread:
                        raise RuntimeError("spread unexpected shape")
                    selected={
                        "market_id":mid,
                        "token_id":tok,
                        "book_bids":len(book["bids"]),
                        "book_asks":len(book["asks"]),
                        "book_timestamp_present":book.get("timestamp") is not None,
                        "book_hash_present":book.get("hash") is not None,
                        "midpoint_shape_keys":sorted(midpoint.keys()),
                        "spread_shape_keys":sorted(spread.keys())
                    }
                    break
                except Exception:
                    continue
            if selected:break
        except Exception:
            continue
    if not selected:raise RuntimeError("No active Polymarket market with readable CLOB book found in bounded sample")
    return {
        "status":"PASS",
        "events_count":len(evs),
        "markets_count":len(ms),
        "markets_attempted":attempts,
        "selected_shape":selected,
        "authentication_used":False,
        "wallet_used":False,
        "orders":False
    }

def main()->int:
    out={
        "schema_version":1,
        "kind":"V3_H10_H11_PUBLIC_READONLY_SOURCE_SMOKE_V1",
        "checked_at_utc":now(),
        "hyperliquid":hyperliquid(),
        "polymarket":polymarket(),
        "guardrails":{
            "public_read_only":True,"authentication_used":False,"wallet_used":False,"private_key_used":False,
            "orders":False,"real_money_actions":False,"automatic_schedule_enabled":False,
            "active_v2r3_changed":False,"v2r4_changed":False,"signal_or_threshold_selected":False
        }
    }
    out["status"]="PASS"
    print("V3_H10_H11_PUBLIC_SOURCE_SMOKE "+json.dumps(out,sort_keys=True))
    return 0

if __name__=="__main__":raise SystemExit(main())
