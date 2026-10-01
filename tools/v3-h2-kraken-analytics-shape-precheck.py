#!/usr/bin/env python3
"""Bounded live response-shape audit for Kraken Futures V3-H2 analytics.

Inspects structure/timestamp units only. It does not evaluate metric values,
strategy performance, thresholds, candidate outcomes, or trading behavior.
"""
from __future__ import annotations
import argparse,json,time,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from typing import Any

BASE="https://futures.kraken.com/api/charts/v1/analytics"
UA="kraken-eur-scanner-v3-h2-shape-precheck/1.0"
METRICS=("open-interest","funding","future-basis")

def utcnow()->str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def get_json(url:str,timeout:float)->Any:
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        raw=r.read().decode("utf-8")
        if not 200<=r.status<300:
            raise RuntimeError(f"HTTP {r.status}: {raw[:200]}")
        return json.loads(raw)

def scalar_type(x:Any)->str:
    if x is None: return "null"
    if isinstance(x,bool): return "bool"
    if isinstance(x,str): return "string"
    if isinstance(x,(int,float)): return "number"
    if isinstance(x,list): return "array"
    if isinstance(x,dict): return "object"
    return type(x).__name__

def value_shape(x:Any)->dict[str,Any]:
    if isinstance(x,dict):
        return {
            "kind":"object",
            "keys":sorted(x.keys()),
            "fields":{str(k):value_shape(v) for k,v in sorted(x.items())},
        }
    if isinstance(x,list):
        sample=x[:3]
        return {
            "kind":"array",
            "length":len(x),
            "element_types":sorted({scalar_type(v) for v in sample}),
            "sample_element_shapes":[value_shape(v) for v in sample[:1]],
        }
    return {"kind":scalar_type(x)}

def normalize_epoch(raw:Any)->float|None:
    try: x=float(raw)
    except (TypeError,ValueError): return None
    return x/1000.0 if x>10_000_000_000 else x

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--symbol",default="PF_XBTUSD")
    ap.add_argument("--lookback-seconds",type=int,default=3600)
    ap.add_argument("--interval",type=int,default=300)
    ap.add_argument("--timeout-seconds",type=float,default=20.0)
    ap.add_argument("--output",type=Path)
    a=ap.parse_args()
    if a.lookback_seconds<=0: raise SystemExit("lookback must be positive")
    now=int(time.time())
    since=now-a.lookback_seconds
    probes=[]
    for metric in METRICS:
        url=f"{BASE}/{urllib.parse.quote(a.symbol,safe='')}/{metric}?"+urllib.parse.urlencode({
            "since":since,"to":now,"interval":a.interval})
        try:
            raw=get_json(url,a.timeout_seconds)
            result=raw.get("result") if isinstance(raw,dict) else None
            if not isinstance(result,dict): raise RuntimeError("missing result object")
            ts=result.get("timestamp") or []
            if not isinstance(ts,list): raise RuntimeError("timestamp not list")
            normalized=[normalize_epoch(x) for x in ts]
            normalized=[x for x in normalized if x is not None]
            unit="milliseconds" if ts and float(ts[-1])>10_000_000_000 else "seconds"
            probes.append({
                "metric":metric,"ok":True,"timestamp_count":len(ts),
                "timestamp_unit":unit,"first_timestamp_raw":ts[0] if ts else None,
                "last_timestamp_raw":ts[-1] if ts else None,
                "last_timestamp_normalized_seconds":normalized[-1] if normalized else None,
                "last_timestamp_at_or_before_to":(normalized[-1] <= now) if normalized else None,
                "data_shape":value_shape(result.get("data")),
                "more":bool(result.get("more",False)),
            })
        except Exception as exc:
            probes.append({"metric":metric,"ok":False,"error":type(exc).__name__,"detail":str(exc)[:240]})
    ok=sum(1 for p in probes if p["ok"])
    status="PASS" if ok==len(METRICS) else "FAIL"
    out={
        "schema_version":1,"kind":"V3_H2_KRAKEN_ANALYTICS_RESPONSE_SHAPE_V1",
        "checked_at_utc":utcnow(),"status":status,"symbol":a.symbol,
        "request_window":{"since_epoch_seconds":since,"to_epoch_seconds":now,"interval_seconds":a.interval},
        "probes":probes,
        "interpretation":{
            "shape_only":True,"metric_values_evaluated":False,
            "timestamp_units_must_be_normalized_per_metric":True,
            "parser_contract_not_implied_until_shape_is_persisted":True,
        },
        "guardrails":{
            "public_endpoint_only":True,"api_key_used":False,"private_data_accessed":False,
            "performance_trial_started":False,"threshold_selection_performed":False,
            "holdout_opened":False,"active_v2r3_changed":False,"v2r4_changed":False,
            "orders":False,"real_money_actions":False,
        }
    }
    text=json.dumps(out,indent=2,sort_keys=True)+"\n"
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(text,"utf-8")
    print(text,end="")
    return 0 if status=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
