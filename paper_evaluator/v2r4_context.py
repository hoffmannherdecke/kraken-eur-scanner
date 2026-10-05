#!/usr/bin/env python3
"""V2R4 assessment context using the canonical shared Kraken market-data layer.

Only supplemental non-Kraken research context is inherited from paper_context.
Kraken ticker/OHLC/AssetPairs semantics come from market_data.
No account/order API exists here.
"""
from __future__ import annotations

from datetime import datetime, timezone

from market_data.rest import kraken_public, rest_market_context
from paper_context import derivatives_context, official_headlines


def _ret(candles, bars: int):
    if len(candles) <= bars:
        return None
    a=float(candles[-1-bars]["close"])
    b=float(candles[-1]["close"])
    return ((b/a)-1.0)*100.0 if a else None


def kraken_pair_metadata(altname: str):
    out={"source":"market_data.rest.kraken_public/AssetPairs","available":False}
    try:
        result=kraken_public("/0/public/AssetPairs",{"pair":altname})
        row=next(iter(result.values()))
        out.update({
            "available":True,
            "status":row.get("status"),
            "ordermin":row.get("ordermin"),
            "costmin":row.get("costmin"),
            "pair_decimals":row.get("pair_decimals"),
            "lot_decimals":row.get("lot_decimals"),
            "fees":row.get("fees"),
            "wsname":row.get("wsname"),
            "altname":row.get("altname"),
        })
    except Exception as exc:
        out.update({"error":type(exc).__name__,"detail":str(exc)[:120]})
    return out


def major_market_regime():
    assets={}
    pos1=pos3=available=0
    for symbol,altname in (("BTC/EUR","XBTEUR"),("ETH/EUR","ETHEUR"),("SOL/EUR","SOLEUR")):
        try:
            ctx=rest_market_context(symbol,altname)
            candles=ctx["candles"]["15m"]
            r1=_ret(candles,4)
            r3=_ret(candles,12)
            assets[symbol]={
                "available":True,
                "ret1h_pct":r1,
                "ret3h_pct":r3,
                "source":"market_data.rest",
            }
            available+=1
            if r1 is not None and r1>0: pos1+=1
            if r3 is not None and r3>0: pos3+=1
        except Exception as exc:
            assets[symbol]={"available":False,"error":type(exc).__name__}
    return {
        "source":"market_data.rest",
        "assets":assets,
        "available_assets":available,
        "positive_1h_count":pos1,
        "positive_3h_count":pos3,
        "note":"Canonical shared Kraken REST semantics; breadth is context, not an automatic veto.",
    }


def build_context(candidate, current_ticker):
    symbol=candidate["pair"]
    altname=candidate["altname"]
    canonical=None
    canonical_error=None
    try:
        canonical=rest_market_context(symbol,altname)
    except Exception as exc:
        canonical_error={"type":type(exc).__name__,"detail":str(exc)[:120]}

    return {
        "schema_version":2,
        "retrieved_at_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "market_data_semantics":"CANONICAL_SHARED_LAYER_V1",
        "kraken_public_pair_verified":True,
        "kraken_execution_ticker":current_ticker,
        "kraken_pair_metadata":kraken_pair_metadata(altname),
        "kraken_market_context":canonical,
        "kraken_market_context_error":canonical_error,
        "major_market_regime":major_market_regime(),
        "derivatives":derivatives_context(symbol),
        "official_headlines":official_headlines(),
        "onchain":{"available":False,"reason":"No reliable free account-independent on-chain source integrated in this revision."},
        "account_specific_tradability":{"available":False,"reason":"No private Kraken trading credential is used by paper infrastructure."},
    }
