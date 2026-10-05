"""Canonical Kraken Spot-EUR universe and ticker normalization primitives.

Read-only/data-only module. It contains no strategy, account or order behavior.
All future runtime consumers should reuse these functions instead of maintaining
parallel AssetPairs/symbol/ticker normalization rules.
"""
from __future__ import annotations
from typing import Any

SYMBOL_ALIASES={"XBT":"BTC","XDG":"DOGE"}

def ws_v2_symbol(wsname:str)->str|None:
    parts=str(wsname or "").split("/")
    if len(parts)!=2:
        return None
    base,quote=(part.strip().upper() for part in parts)
    base=SYMBOL_ALIASES.get(base,base)
    quote=SYMBOL_ALIASES.get(quote,quote)
    if not base or quote!="EUR":
        return None
    return f"{base}/EUR"

def online_eur_universe(result:dict[str,Any])->list[dict[str,str]]:
    rows=[]
    seen=set()
    for pair_key,info in result.items():
        if not isinstance(info,dict):
            continue
        if str(info.get("status") or "").lower()!="online":
            continue
        wsname=str(info.get("wsname") or "")
        quote=str(info.get("quote") or "")
        if not (wsname.endswith("/EUR") or quote in {"ZEUR","EUR"}):
            continue
        symbol=ws_v2_symbol(wsname)
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        rows.append({
            "symbol":symbol,
            "pair_key":str(pair_key),
            "altname":str(info.get("altname") or pair_key),
            "rest_wsname":wsname,
            "status":"online",
        })
    rows.sort(key=lambda row:row["symbol"])
    return rows

def ticker_record(row:dict[str,Any],received_at:str)->dict[str,Any]:
    def num(key:str)->float|None:
        value=row.get(key)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError,ValueError):
            return None
    bid=num("bid"); ask=num("ask"); last=num("last")
    volume=num("volume"); vwap=num("vwap")
    spread_pct=None
    if bid is not None and ask is not None and bid>0 and ask>=bid:
        mid=(bid+ask)/2.0
        if mid>0:
            spread_pct=100.0*(ask-bid)/mid
    turnover=None
    if volume is not None:
        ref=vwap if vwap and vwap>0 else last
        if ref is not None:
            turnover=volume*ref
    return {
        "symbol":str(row.get("symbol") or ""),
        "exchange_at_utc":row.get("timestamp"),
        "received_at_utc":received_at,
        "bid_eur":bid,"ask_eur":ask,"last_eur":last,
        "spread_pct":spread_pct,
        "volume24_base":volume,"vwap24_eur":vwap,
        "turnover24_est_eur":turnover,
        "change24_eur":num("change"),
        "change24_pct":num("change_pct"),
        "high24_eur":num("high"),
        "low24_eur":num("low"),
    }
