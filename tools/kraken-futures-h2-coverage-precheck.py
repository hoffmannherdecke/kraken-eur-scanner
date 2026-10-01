#!/usr/bin/env python3
"""Bounded public Kraken Futures coverage/semantics precheck for V3-H2.

Public/read-only only:
- current Kraken Spot AssetPairs (live EUR universe metadata)
- current Kraken Futures tickers
- bounded Market Analytics probes for open-interest/funding/future-basis

The tool measures source coverage and timestamp semantics only. It does not
evaluate strategy performance, open a holdout, access an account, place orders,
or change V2R3/V2R4 runtime state.
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UA="kraken-eur-scanner-v3-h2-public-precheck/1.0"

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def get_json(url: str, timeout: float=20.0) -> Any:
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        raw=r.read().decode("utf-8")
        if not 200 <= r.status < 300:
            raise RuntimeError(f"HTTP {r.status}: {raw[:200]}")
        return json.loads(raw)

def spot_eur_bases() -> set[str]:
    data=get_json("https://api.kraken.com/0/public/AssetPairs")
    if data.get("error"):
        raise RuntimeError(f"Kraken AssetPairs errors: {data['error']}")
    bases=set()
    for _,row in (data.get("result") or {}).items():
        if not isinstance(row,dict):
            continue
        status=str(row.get("status") or "").lower()
        ws=str(row.get("wsname") or "")
        alt=str(row.get("altname") or "")
        quote=str(row.get("quote") or "")
        if status != "online":
            continue
        if ws.endswith("/EUR"):
            base=ws.split("/",1)[0]
        elif alt.endswith("EUR"):
            base=alt[:-3]
        elif quote in {"ZEUR","EUR"}:
            base=str(row.get("base") or "")
            base=re.sub(r"^[XZ]","",base)
        else:
            continue
        base=base.upper()
        aliases={"BTC":"XBT","XDG":"DOGE"}
        base=aliases.get(base,base)
        if base:
            bases.add(base)
    return bases

def futures_tickers() -> list[dict[str,Any]]:
    data=get_json("https://futures.kraken.com/derivatives/api/v3/tickers")
    rows=data.get("tickers") if isinstance(data,dict) else None
    if rows is None and isinstance(data,dict):
        result=data.get("result")
        if isinstance(result,dict):
            rows=result.get("tickers")
        elif isinstance(result,list):
            rows=result
    if not isinstance(rows,list):
        raise RuntimeError(f"unexpected tickers shape keys={list(data) if isinstance(data,dict) else type(data).__name__}")
    return [x for x in rows if isinstance(x,dict)]

def symbol_of(row: dict[str,Any]) -> str:
    return str(row.get("symbol") or row.get("product_id") or row.get("instrument") or "").upper()

def base_guess(row: dict[str,Any]) -> str | None:
    # Prefer explicit pair/base-like metadata where exposed.
    for key in ("base","baseCurrency","underlying","underlyingAsset"):
        v=row.get(key)
        if isinstance(v,str) and v.strip():
            x=v.upper().replace("BTC","XBT").replace("XDG","DOGE")
            return re.sub(r"[^A-Z0-9]","",x)
    pair=row.get("pair")
    if isinstance(pair,str) and pair.strip():
        x=re.split(r"[/:_-]",pair.upper())[0]
        x={"BTC":"XBT","XDG":"DOGE"}.get(x,x)
        if x:
            return x
    sym=symbol_of(row)
    if not sym:
        return None
    # Common Kraken Futures prefixes PI_/PF_ and quote suffixes.
    x=re.sub(r"^(PI|PF|FI|FF|IN)_","",sym)
    for suffix in ("USDT","USD","EUR"):
        if x.endswith(suffix) and len(x)>len(suffix):
            x=x[:-len(suffix)]
            break
    x={"BTC":"XBT","XDG":"DOGE"}.get(x,x)
    return x or None

def is_perpetual(row: dict[str,Any]) -> bool:
    text=" ".join(str(row.get(k) or "") for k in ("symbol","tag","type","contractType","product_type","productType")).lower()
    sym=symbol_of(row)
    return ("perpet" in text or sym.startswith("PI_") or sym.startswith("PF_"))

def analytics_probe(symbol: str, metric: str, since: int, interval: int, timeout: float) -> dict[str,Any]:
    path=f"https://futures.kraken.com/api/charts/v1/analytics/{urllib.parse.quote(symbol,safe='')}/{metric}"
    url=path+"?"+urllib.parse.urlencode({"since":since,"interval":interval})
    out={"symbol":symbol,"metric":metric,"ok":False}
    try:
        data=get_json(url,timeout=timeout)
        result=(data or {}).get("result") if isinstance(data,dict) else None
        if not isinstance(result,dict):
            raise RuntimeError("missing result object")
        timestamps=result.get("timestamp") or []
        if not isinstance(timestamps,list):
            raise RuntimeError("timestamp is not a list")
        out.update({
            "ok":True,
            "row_count":len(timestamps),
            "first_timestamp":timestamps[0] if timestamps else None,
            "last_timestamp":timestamps[-1] if timestamps else None,
            "more":bool(result.get("more",False)),
            "data_keys":sorted((result.get("data") or {}).keys()) if isinstance(result.get("data"),dict) else [],
        })
    except Exception as exc:
        out.update({"error":type(exc).__name__,"detail":str(exc)[:240]})
    return out

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--max-symbols",type=int,default=5)
    ap.add_argument("--lookback-seconds",type=int,default=3600)
    ap.add_argument("--interval",type=int,default=300,choices=(60,300,900,1800,3600,14400,43200,86400,604800))
    ap.add_argument("--timeout-seconds",type=float,default=20.0)
    ap.add_argument("--output",type=Path)
    args=ap.parse_args()
    if not 1 <= args.max_symbols <= 10:
        raise SystemExit("--max-symbols must be 1..10")
    if args.lookback_seconds <= 0:
        raise SystemExit("--lookback-seconds must be positive")

    spot=spot_eur_bases()
    tickers=futures_tickers()
    perps=[r for r in tickers if is_perpetual(r)]
    mapped=[]
    for r in perps:
        base=base_guess(r)
        sym=symbol_of(r)
        if base and sym and base in spot:
            mapped.append({"base":base,"symbol":sym})
    # Deterministic one symbol per base, with majors first.
    uniq={}
    for r in sorted(mapped,key=lambda x:(x["base"],x["symbol"])):
        uniq.setdefault(r["base"],r["symbol"])
    priority=["XBT","ETH","SOL","XRP","ADA"]
    ordered=[]
    for b in priority+sorted(set(uniq)-set(priority)):
        if b in uniq:
            ordered.append({"base":b,"symbol":uniq[b]})
    selected=ordered[:args.max_symbols]

    now=int(time.time())
    since=now-args.lookback_seconds
    probes=[]
    for item in selected:
        for metric in ("open-interest","funding","future-basis"):
            probes.append(analytics_probe(item["symbol"],metric,since,args.interval,args.timeout_seconds))

    ok=sum(1 for p in probes if p["ok"])
    data_ok=sum(1 for p in probes if p["ok"] and p.get("row_count",0)>0)
    status="PASS" if selected and ok>0 else "FAIL"
    result={
        "schema_version":1,
        "kind":"KRAKEN_FUTURES_H2_COVERAGE_PRECHECK_V1",
        "checked_at_utc":utcnow(),
        "status":status,
        "spot_online_eur_base_count":len(spot),
        "futures_ticker_count":len(tickers),
        "futures_perpetual_count":len(perps),
        "spot_eur_bases_with_mapped_perpetual_count":len(uniq),
        "coverage_pct_of_spot_eur_bases":round(100.0*len(uniq)/len(spot),2) if spot else None,
        "selected_symbols":selected,
        "analytics_probe_count":len(probes),
        "analytics_probe_ok":ok,
        "analytics_probe_with_data":data_ok,
        "analytics_probes":probes,
        "ticker_field_sample":sorted(set().union(*(r.keys() for r in tickers[:5]))) if tickers else [],
        "interpretation":{
            "coverage_only":True,
            "performance_conclusion_allowed":False,
            "missing_derivatives_coverage_is_valid_missing_state":True,
            "binance_may_fill_context_gap_only_as_separately_proven_supplementary_source":True,
            "kraken_spot_eur_remains_execution_truth":True
        },
        "guardrails":{
            "public_endpoints_only":True,
            "api_key_used":False,
            "account_endpoint_used":False,
            "private_data_accessed":False,
            "bulk_history_downloaded":False,
            "holdout_opened":False,
            "performance_selection_performed":False,
            "active_v2r3_changed":False,
            "v2r4_activated":False,
            "orders":False,
            "leverage_action":False,
            "real_money_actions":False
        }
    }
    raw=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(raw,"utf-8")
    print(raw,end="")
    return 0 if status=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
