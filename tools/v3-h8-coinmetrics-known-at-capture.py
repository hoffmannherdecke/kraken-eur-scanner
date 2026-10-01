#!/usr/bin/env python3
"""Prospective compact Coin Metrics known-at capture for V3-H8."""
from __future__ import annotations
import argparse,json,math,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from typing import Any

BASE="https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
UA="kraken-eur-scanner-v3-h8-known-at-capture/1.0"
DEFAULT_METRICS=["AdrActCnt","TxCnt","CapMVRVCur","FlowInExUSD","FlowOutExUSD","AssetEODCompletionTime"]

def now()->datetime: return datetime.now(timezone.utc)
def iso(d:datetime)->str: return d.astimezone(timezone.utc).isoformat().replace("+00:00","Z")
def parse(s:str)->datetime: return datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(timezone.utc)
def epoch_iso(v:Any)->str|None:
    if v in (None,""): return None
    try: x=float(v)
    except (TypeError,ValueError): return None
    if not math.isfinite(x) or x<=0: return None
    return iso(datetime.fromtimestamp(x,tz=timezone.utc))
def get_json(url:str,timeout:float)->Any:
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        raw=r.read().decode("utf-8")
        if not 200<=r.status<300: raise RuntimeError(f"HTTP {r.status}: {raw[:200]}")
        return json.loads(raw)

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--assets",default="btc,eth,sol,xrp,ada")
    ap.add_argument("--metrics",default=",".join(DEFAULT_METRICS))
    ap.add_argument("--timeout-seconds",type=float,default=20.0)
    ap.add_argument("--output",type=Path)
    a=ap.parse_args()
    assets=[x.strip().lower() for x in a.assets.split(",") if x.strip()]
    metrics=[x.strip() for x in a.metrics.split(",") if x.strip()]
    if not 1<=len(assets)<=20 or not 1<=len(metrics)<=20: raise SystemExit("invalid bounded scope")
    started=now(); rows=[]; errors=[]
    for asset in assets:
        q=urllib.parse.urlencode({
            "assets":asset,"metrics":",".join(metrics),"frequency":"1d",
            "limit_per_asset":"3","paging_from":"end","sort":"time",
            "ignore_unsupported_errors":"true","ignore_forbidden_errors":"true","pretty":"false"})
        try:
            data=get_json(BASE+"?"+q,a.timeout_seconds)
            vals=data.get("data") if isinstance(data,dict) else None
            if not isinstance(vals,list): raise RuntimeError("unexpected timeseries response")
            vals=[x for x in vals if isinstance(x,dict) and str(x.get("asset") or "").lower()==asset]
            vals.sort(key=lambda x:str(x.get("time") or ""))
            latest=vals[-1] if vals else None
            retrieved=now()
            if latest is None:
                rows.append({"asset":asset,"status":"NO_ROW","retrieved_at_utc":iso(retrieved),
                    "observation_time_utc":None,"metrics":{},"provider_asset_eod_completion_utc":None,
                    "safe_known_at_upper_bound_utc":iso(retrieved)})
                continue
            obs=parse(str(latest["time"]))
            returned={}; status_times={}
            for metric in metrics:
                if metric=="AssetEODCompletionTime": continue
                if metric in latest: returned[metric]=latest.get(metric)
                sk=metric+"-status-time"
                if sk in latest: status_times[metric]=latest.get(sk)
            pc_iso=epoch_iso(latest.get("AssetEODCompletionTime"))
            pc_lag=None; pc_before=None
            if pc_iso:
                pc=parse(pc_iso); pc_lag=(pc-obs).total_seconds(); pc_before=pc<=retrieved
            rows.append({"asset":asset,"status":"ROW_RETURNED","retrieved_at_utc":iso(retrieved),
                "observation_time_utc":iso(obs),"observation_age_at_retrieval_seconds":(retrieved-obs).total_seconds(),
                "metrics":returned,"metric_status_times_if_returned":status_times,
                "provider_asset_eod_completion_utc":pc_iso,
                "provider_completion_lag_from_observation_seconds":pc_lag,
                "provider_completion_at_or_before_retrieval":pc_before,
                "safe_known_at_upper_bound_utc":iso(retrieved)})
        except Exception as exc:
            errors.append({"asset":asset,"error":f"{type(exc).__name__}: {exc}"})
    finished=now(); n=sum(1 for x in rows if x["status"]=="ROW_RETURNED")
    out={"schema_version":1,"kind":"V3_H8_COINMETRICS_PROSPECTIVE_KNOWN_AT_CAPTURE_V1",
      "status":"PASS" if n>0 and not errors else "FAIL","source":"coinmetrics_community_network_data",
      "endpoint":"timeseries/asset-metrics","request_started_at_utc":iso(started),"request_finished_at_utc":iso(finished),
      "requested_assets":assets,"requested_metrics":metrics,"returned_asset_count":n,"rows":rows,"errors":errors,
      "known_at_interpretation":{"observation_time_is_publication_time":False,
        "retrieved_at_is_safe_known_at_upper_bound":True,
        "asset_eod_completion_is_exact_per_metric_publication_time":False,
        "single_capture_proves_historical_known_at":False,
        "repeated_prospective_capture_required_for_first_seen_lag":True},
      "guardrails":{"public_endpoint_only":True,"api_key_used":False,"private_data_accessed":False,
        "historical_backfill_performed":False,"performance_trial_started":False,"threshold_selection_performed":False,
        "holdout_opened":False,"active_v2r3_changed":False,"v2r4_changed":False,"paper_runtime_changed":False,
        "orders":False,"real_money_actions":False}}
    raw=json.dumps(out,indent=2,sort_keys=True)+"\n"
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(raw,"utf-8")
    print(raw,end=""); return 0 if out["status"]=="PASS" else 2
if __name__=="__main__": raise SystemExit(main())
