#!/usr/bin/env python3
"""Isolated prospective Kraken Futures state capture for a single V3-H2 candidate.

Research-only CLI. Not wired to the scanner, handoff queue, scheduler, orders,
paper decisions, or any private API. Four-element analytics payloads remain
opaque until separately proven semantic mapping exists.
"""
from __future__ import annotations
import argparse,json,re,time,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from typing import Any

UA="kraken-eur-scanner-v3-h2-candidate-capture/1.0"
TICKERS="https://futures.kraken.com/derivatives/api/v3/tickers"
ANALYTICS="https://futures.kraken.com/api/charts/v1/analytics"
METRICS=("open-interest","funding","future-basis")

def dt_parse(s:str)->datetime:
    return datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(timezone.utc)
def iso(d:datetime)->str:
    return d.astimezone(timezone.utc).isoformat().replace("+00:00","Z")
def now()->datetime:
    return datetime.now(timezone.utc)
def get_json(url:str,timeout:float)->Any:
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        raw=r.read().decode("utf-8")
        if not 200<=r.status<300: raise RuntimeError(f"HTTP {r.status}: {raw[:200]}")
        return json.loads(raw)
def symbol_of(row:dict[str,Any])->str:
    return str(row.get("symbol") or row.get("product_id") or row.get("instrument") or "").upper()
def base_guess(row:dict[str,Any])->str|None:
    for key in ("base","baseCurrency","underlying","underlyingAsset"):
        v=row.get(key)
        if isinstance(v,str) and v.strip():
            x=v.upper().replace("BTC","XBT").replace("XDG","DOGE")
            return re.sub(r"[^A-Z0-9]","",x)
    pair=row.get("pair")
    if isinstance(pair,str) and pair.strip():
        x=re.split(r"[/:_-]",pair.upper())[0]
        return {"BTC":"XBT","XDG":"DOGE"}.get(x,x)
    sym=symbol_of(row)
    x=re.sub(r"^(PI|PF|FI|FF|IN)_","",sym)
    for suffix in ("USDT","USD","EUR"):
        if x.endswith(suffix) and len(x)>len(suffix):
            x=x[:-len(suffix)]; break
    x={"BTC":"XBT","XDG":"DOGE"}.get(x,x)
    return x or None
def is_perp(row:dict[str,Any])->bool:
    text=" ".join(str(row.get(k) or "") for k in ("symbol","tag","type","contractType","product_type","productType")).lower()
    sym=symbol_of(row)
    return "perpet" in text or sym.startswith("PI_") or sym.startswith("PF_")
def map_perp(base:str,timeout:float)->tuple[str|None,str]:
    data=get_json(TICKERS,timeout)
    rows=data.get("tickers") if isinstance(data,dict) else None
    if rows is None and isinstance(data,dict):
        res=data.get("result")
        rows=res.get("tickers") if isinstance(res,dict) else res if isinstance(res,list) else None
    if not isinstance(rows,list): raise RuntimeError("unexpected tickers shape")
    choices=sorted({symbol_of(r) for r in rows if isinstance(r,dict) and is_perp(r) and base_guess(r)==base and symbol_of(r)})
    return (choices[0] if choices else None, iso(now()))
def normalize_ts(raw:Any,metric:str)->float:
    x=float(raw)
    if metric=="funding":
        if x<10_000_000_000: raise RuntimeError("funding timestamp expected milliseconds")
        return x/1000.0
    if x>10_000_000_000: raise RuntimeError(f"{metric} timestamp expected seconds")
    return x
def payload_at(data:Any,metric:str,index:int,count:int)->Any:
    if metric=="open-interest":
        if not isinstance(data,list) or len(data)!=count: raise RuntimeError("open-interest shape mismatch")
        payload=data[index]
        if not isinstance(payload,list) or len(payload)!=4 or not all(isinstance(x,str) for x in payload):
            raise RuntimeError("open-interest opaque 4-string payload mismatch")
        return payload
    if metric=="funding":
        if not isinstance(data,dict) or sorted(data.keys())!=["rate","relativeRate"]:
            raise RuntimeError("funding object keys mismatch")
        out={}
        for key in ("rate","relativeRate"):
            arr=data[key]
            if not isinstance(arr,list) or len(arr)!=count: raise RuntimeError(f"funding {key} length mismatch")
            payload=arr[index]
            if not isinstance(payload,list) or len(payload)!=4 or not all(isinstance(x,str) for x in payload):
                raise RuntimeError(f"funding {key} opaque 4-string payload mismatch")
            out[key]=payload
        return out
    if metric=="future-basis":
        if not isinstance(data,dict) or sorted(data.keys())!=["basis"]:
            raise RuntimeError("future-basis object keys mismatch")
        arr=data["basis"]
        if not isinstance(arr,list) or len(arr)!=count or not isinstance(arr[index],str):
            raise RuntimeError("future-basis shape mismatch")
        return {"basis":arr[index]}
    raise RuntimeError("unsupported metric")
def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--candidate-id",required=True)
    ap.add_argument("--base",required=True)
    ap.add_argument("--event-utc",required=True)
    ap.add_argument("--lookback-seconds",type=int,default=3600)
    ap.add_argument("--interval",type=int,default=300)
    ap.add_argument("--max-mapping-lag-seconds",type=int,default=120)
    ap.add_argument("--timeout-seconds",type=float,default=20.0)
    ap.add_argument("--output",type=Path)
    a=ap.parse_args()
    base={"BTC":"XBT","XDG":"DOGE"}.get(a.base.upper(),a.base.upper())
    event=dt_parse(a.event_utc)
    event_s=int(event.timestamp())
    wall=now()
    if event > wall:
        raise SystemExit("candidate event is in the future")
    if (wall-event).total_seconds()>a.max_mapping_lag_seconds:
        raise SystemExit("this prospective mapper is not allowed for stale/historical candidates")
    symbol,mapping_at=map_perp(base,a.timeout_seconds)
    mapping_lag=(dt_parse(mapping_at)-event).total_seconds()
    states=[]
    if symbol is None:
        for metric in METRICS:
            states.append({"analytics_type":metric,"status":"MISSING","missing_reason":"NO_CURRENT_PROSPECTIVE_PERPETUAL_MAPPING"})
    else:
        since=event_s-a.lookback_seconds
        for metric in METRICS:
            url=f"{ANALYTICS}/{urllib.parse.quote(symbol,safe='')}/{metric}?"+urllib.parse.urlencode({
                "since":since,"to":event_s,"interval":a.interval})
            retrieved=now()
            try:
                raw=get_json(url,a.timeout_seconds)
                result=raw.get("result") if isinstance(raw,dict) else None
                if not isinstance(result,dict): raise RuntimeError("missing result")
                ts=result.get("timestamp") or []
                if not isinstance(ts,list) or not ts:
                    states.append({"analytics_type":metric,"status":"MISSING","missing_reason":"NO_BUCKET_AT_OR_BEFORE_EVENT",
                      "retrieved_at_utc":iso(now())})
                    continue
                norm=[normalize_ts(x,metric) for x in ts]
                valid=[i for i,x in enumerate(norm) if x<=event_s]
                if not valid:
                    states.append({"analytics_type":metric,"status":"MISSING","missing_reason":"NO_TIMESTAMP_AT_OR_BEFORE_EVENT",
                      "retrieved_at_utc":iso(now())})
                    continue
                idx=valid[-1]
                if any(x>event_s for x in norm[:idx+1]): raise RuntimeError("future row before chosen index")
                payload=payload_at(result.get("data"),metric,idx,len(ts))
                states.append({
                    "analytics_type":metric,"status":"CAPTURED",
                    "source_timestamp_raw":ts[idx],
                    "source_timestamp_seconds":norm[idx],
                    "metric_age_seconds":event_s-norm[idx],
                    "bucket_payload_opaque":payload,
                    "retrieved_at_utc":iso(now()),
                    "more":bool(result.get("more",False))
                })
            except Exception as exc:
                states.append({"analytics_type":metric,"status":"ERROR_FAIL_CLOSED",
                  "error":type(exc).__name__,"detail":str(exc)[:240],"retrieved_at_utc":iso(now())})
    out={
      "schema_version":1,"kind":"V3_H2_PROSPECTIVE_CANDIDATE_DERIVATIVES_CAPTURE_V1",
      "status":"PASS" if all(s["status"] in {"CAPTURED","MISSING"} for s in states) else "FAIL",
      "candidate":{"candidate_id":a.candidate_id,"event_utc":iso(event),"event_epoch_seconds":event_s,"spot_eur_base":base},
      "mapping":{"kraken_futures_symbol":symbol,"mapping_retrieved_at_utc":mapping_at,
        "mapping_lag_seconds":mapping_lag,"prospective_only":True},
      "request_contract":{"analytics_types":list(METRICS),"lookback_seconds":a.lookback_seconds,
        "interval_seconds":a.interval,"explicit_to_epoch_seconds":event_s},
      "states":states,
      "interpretation":{"opaque_4tuple_semantics_resolved":False,"derived_scalar_created":False,
        "candidate_decision_mutated":False,"missing_state_keeps_candidate":True,
        "performance_conclusion_allowed":False},
      "guardrails":{"public_endpoints_only":True,"api_key_used":False,"private_data_accessed":False,
        "historical_candidate_use_allowed":False,"outcome_label_joined":False,"threshold_selection_performed":False,
        "holdout_opened":False,"active_v2r3_changed":False,"v2r4_changed":False,"paper_decision_changed":False,
        "orders":False,"leverage_action":False,"real_money_actions":False}
    }
    raw=json.dumps(out,indent=2,sort_keys=True)+"\n"
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(raw,"utf-8")
    print(raw,end="")
    return 0 if out["status"]=="PASS" else 2
if __name__=="__main__":
    raise SystemExit(main())
