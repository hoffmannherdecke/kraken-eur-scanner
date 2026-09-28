#!/usr/bin/env python3
"""Compact public context enrichment for the paper evaluator.

All sources are public/read-only. Failures are represented as unavailable; nothing is invented.
"""
from __future__ import annotations
import json, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

UA="kraken-paper-context/2.0"

def _json(url, timeout=12):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode())

def _text(url, timeout=12, user_agent=UA):
    req=urllib.request.Request(url,headers={"User-Agent":user_agent,"Accept":"application/rss+xml,application/xml,text/xml,*/*"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return r.read().decode("utf-8","replace")

def _kraken_ohlc(pair, interval=15):
    q=urllib.parse.urlencode({"pair":pair,"interval":interval})
    d=_json("https://api.kraken.com/0/public/OHLC?"+q)
    if d.get("error"):
        raise RuntimeError(repr(d["error"]))
    rows=next(v for k,v in d["result"].items() if k!="last")
    return rows[:-1] if len(rows)>1 else rows

def _ret(rows, bars):
    if len(rows)<bars+1:
        return None
    a=float(rows[-bars-1][4]); b=float(rows[-1][4])
    return ((b/a)-1.0)*100.0 if a else None

def kraken_regime():
    pairs={"BTC/EUR":"XBTEUR","ETH/EUR":"ETHEUR","SOL/EUR":"SOLEUR"}
    assets={}
    pos1=pos3=0
    available=0
    for label,pair in pairs.items():
        try:
            rows=_kraken_ohlc(pair,15)
            r1=_ret(rows,4); r3=_ret(rows,12)
            assets[label]={"available":True,"ret1h_pct":r1,"ret3h_pct":r3}
            available+=1
            if r1 is not None and r1>0: pos1+=1
            if r3 is not None and r3>0: pos3+=1
        except Exception as exc:
            assets[label]={"available":False,"error":type(exc).__name__}
    return {
        "source":"kraken_public_ohlc",
        "assets":assets,
        "available_assets":available,
        "positive_1h_count":pos1,
        "positive_3h_count":pos3,
        "note":"Raw breadth proxy only; evaluator must not infer unavailable global market data."
    }

def binance_derivatives(pair):
    base=pair.split("/")[0].upper().replace("XBT","BTC").replace("XDG","DOGE")
    symbol=base+"USDT"
    out={"source":"binance_public_futures","symbol":symbol,"available":False}
    try:
        premium=_json("https://fapi.binance.com/fapi/v1/premiumIndex?"+urllib.parse.urlencode({"symbol":symbol}))
        oi=_json("https://fapi.binance.com/fapi/v1/openInterest?"+urllib.parse.urlencode({"symbol":symbol}))
        out.update({
            "available":True,
            "mark_price":float(premium["markPrice"]),
            "index_price":float(premium["indexPrice"]),
            "last_funding_rate":float(premium["lastFundingRate"]),
            "next_funding_time":int(premium["nextFundingTime"]),
            "open_interest_base":float(oi["openInterest"]),
            "retrieved_ms":int(time.time()*1000),
            "note":"Cross-market context only; never used as Kraken EUR execution price."
        })
    except Exception as exc:
        out.update({"error":type(exc).__name__,"detail":str(exc)[:120]})
    return out

def kraken_pair_metadata(altname):
    out={"source":"kraken_public_assetpairs","available":False}
    try:
        q=urllib.parse.urlencode({"pair":altname})
        d=_json("https://api.kraken.com/0/public/AssetPairs?"+q)
        if d.get("error"):
            raise RuntimeError(repr(d["error"]))
        row=next(iter(d.get("result",{}).values()))
        out.update({
            "available":True,
            "status":row.get("status"),
            "ordermin":row.get("ordermin"),
            "costmin":row.get("costmin"),
            "pair_decimals":row.get("pair_decimals"),
            "lot_decimals":row.get("lot_decimals"),
            "fees":row.get("fees"),
        })
    except Exception as exc:
        out.update({"error":type(exc).__name__,"detail":str(exc)[:120]})
    return out

def kraken_futures_derivatives(pair):
    base=pair.split("/")[0].upper().replace("BTC","XBT").replace("DOGE","XDG")
    desired={f"PF_{base}USD",f"PI_{base}USD"}
    out={"source":"kraken_futures_public","available":False,"requested_symbols":sorted(desired)}
    try:
        d=_json("https://futures.kraken.com/derivatives/api/v3/tickers")
        rows=d.get("tickers") or d.get("result") or []
        if isinstance(rows,dict):
            rows=list(rows.values())
        row=next((x for x in rows if str(x.get("symbol","")).upper() in desired),None)
        if row is None:
            row=next((x for x in rows if base in str(x.get("symbol","")).upper()
                      and str(x.get("symbol","")).upper().endswith("USD")),None)
        if row is None:
            out["detail"]="No matching Kraken Futures USD contract"
            return out

        def pick(*keys):
            for k in keys:
                if row.get(k) is not None:
                    return row.get(k)
            return None

        out.update({
            "available":True,
            "symbol":row.get("symbol"),
            "last":pick("last","lastPrice"),
            "mark_price":pick("markPrice","mark_price"),
            "index_price":pick("indexPrice","index_price"),
            "funding_rate":pick("fundingRate","funding_rate","fundingRatePrediction"),
            "open_interest":pick("openInterest","open_interest","openInterestUsd"),
            "volume24h":pick("vol24h","volume24h","volume"),
            "note":"Kraken Futures public cross-market context only; never used as Kraken Spot EUR execution price."
        })
    except Exception as exc:
        out.update({"error":type(exc).__name__,"detail":str(exc)[:120]})
    return out

def derivatives_context(pair):
    primary=kraken_futures_derivatives(pair)
    secondary=binance_derivatives(pair)
    return {
        "available":bool(primary.get("available") or secondary.get("available")),
        "kraken_futures":primary,
        "binance_futures":secondary,
        "preferred_source":"kraken_futures" if primary.get("available") else ("binance_futures" if secondary.get("available") else None),
        "note":"Derivatives are supplementary context only; Kraken Spot EUR controls execution."
    }

def _recent_rss(url, source, user_agent=UA, hours=24, limit=5):
    out={"source":source,"available":False,"items":[]}
    try:
        root=ET.fromstring(_text(url,user_agent=user_agent))
        now=datetime.now(timezone.utc)
        items=[]
        for item in root.findall(".//item"):
            title=(item.findtext("title") or "").strip()
            raw=(item.findtext("pubDate") or item.findtext("date") or "").strip()
            if not title:
                continue
            published=None
            if raw:
                try:
                    published=parsedate_to_datetime(raw)
                    if published.tzinfo is None:
                        published=published.replace(tzinfo=timezone.utc)
                except Exception:
                    published=None
            if published is not None and (now-published).total_seconds()>hours*3600:
                continue
            items.append({"title":title[:180],"published_at":published.isoformat() if published else None})
            if len(items)>=limit:
                break
        out.update({"available":True,"items":items})
    except Exception as exc:
        out.update({"error":type(exc).__name__,"detail":str(exc)[:120]})
    return out

def official_headlines():
    return {
        "federal_reserve":_recent_rss(
            "https://www.federalreserve.gov/feeds/press_all.xml",
            "Federal Reserve official RSS"
        ),
        "sec":_recent_rss(
            "https://www.sec.gov/news/pressreleases.rss",
            "SEC official press releases",
            user_agent="paper-research contact=github-actions@example.invalid"
        ),
        "scope_note":"Official headline context only; absence of a headline is not evidence that no catalyst exists."
    }

def build_context(candidate, current_ticker):
    return {
        "schema_version":1,
        "retrieved_at_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "kraken_public_pair_verified":True,
        "kraken_execution_ticker":current_ticker,
        "kraken_pair_metadata":kraken_pair_metadata(candidate["altname"]),
        "major_market_regime":kraken_regime(),
        "derivatives":derivatives_context(candidate["pair"]),
        "official_headlines":official_headlines(),
        "onchain":{"available":False,"reason":"No reliable free account-independent on-chain source integrated in this revision."},
        "account_specific_tradability":{"available":False,"reason":"No private Kraken trading credential is used by paper infrastructure."}
    }
