#!/usr/bin/env python3
"""Bounded public Coin Metrics Community coverage audit for V3-H8.

No API key, account, orders, strategy mutation, holdout access, or performance
selection. This tool inspects catalog coverage only and does not claim historical
point-in-time usability from metric interval timestamps.
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE="https://community-api.coinmetrics.io/v4"
UA="kraken-eur-scanner-v3-h8-onchain-precheck/1.0"

TARGET_GROUPS={
    "active_addresses": [re.compile(r"^AdrAct(?:Cnt|7dCnt|30dCnt)$",re.I)],
    "new_addresses": [re.compile(r"^AdrNew(?:Cnt|Bal)$",re.I)],
    "transaction_count": [re.compile(r"^TxCnt$",re.I)],
    "mvrv": [re.compile(r"MVRV",re.I)],
    "flow_like": [re.compile(r"^Flow(?:In|Out|Net)",re.I)],
}

def utcnow()->str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def get_json(url:str,timeout:float)->Any:
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as resp:
        raw=resp.read().decode("utf-8")
        if not 200 <= resp.status < 300:
            raise RuntimeError(f"HTTP {resp.status}: {raw[:200]}")
        return json.loads(raw)

def match_groups(metric:str)->list[str]:
    out=[]
    for group,patterns in TARGET_GROUPS.items():
        if any(p.search(metric) for p in patterns):
            out.append(group)
    return out

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--assets",default="btc,eth,sol,xrp,ada")
    ap.add_argument("--timeout-seconds",type=float,default=20.0)
    ap.add_argument("--output",type=Path)
    args=ap.parse_args()

    assets=[x.strip().lower() for x in args.assets.split(",") if x.strip()]
    if not assets or len(assets)>20:
        raise SystemExit("assets must contain 1..20 comma-separated asset ids")

    url=BASE+"/catalog-v2/asset-metrics?"+urllib.parse.urlencode({
        "assets":",".join(assets),
        "pretty":"false"
    })
    data=get_json(url,args.timeout_seconds)
    rows=data.get("data") if isinstance(data,dict) else None
    if not isinstance(rows,list):
        raise SystemExit("unexpected Coin Metrics catalog response")

    by_asset={}
    for row in rows:
        if not isinstance(row,dict):
            continue
        asset=str(row.get("asset") or "").lower()
        if not asset:
            continue
        metrics=row.get("metrics") or []
        metric_map={}
        groups={k:[] for k in TARGET_GROUPS}
        for m in metrics:
            if not isinstance(m,dict):
                continue
            mid=str(m.get("metric") or "")
            if not mid:
                continue
            freqs=[]
            for f in m.get("frequencies") or []:
                if not isinstance(f,dict):
                    continue
                freqs.append({
                    "frequency":f.get("frequency"),
                    "min_time":f.get("min_time"),
                    "max_time":f.get("max_time")
                })
            metric_map[mid]=freqs
            for group in match_groups(mid):
                groups[group].append(mid)
        by_asset[asset]={
            "metric_count":len(metric_map),
            "groups":{k:sorted(v) for k,v in groups.items()},
            "target_metric_frequencies":{
                mid:freqs for mid,freqs in sorted(metric_map.items())
                if match_groups(mid)
            }
        }

    requested=set(assets)
    returned=set(by_asset)
    summary={}
    for group in TARGET_GROUPS:
        covered=sorted(a for a,v in by_asset.items() if v["groups"][group])
        summary[group]={
            "assets_with_coverage":covered,
            "count":len(covered),
            "coverage_pct_of_requested":round(100.0*len(covered)/len(assets),2)
        }

    status="PASS" if returned and (
        summary["active_addresses"]["count"]>0
        or summary["transaction_count"]["count"]>0
    ) else "FAIL"

    result={
        "schema_version":1,
        "kind":"V3_H8_COINMETRICS_COMMUNITY_COVERAGE_V1",
        "checked_at_utc":utcnow(),
        "status":status,
        "source":"coinmetrics_community_network_data",
        "endpoint":"catalog-v2/asset-metrics",
        "requested_assets":assets,
        "returned_assets":sorted(returned),
        "missing_requested_assets":sorted(requested-returned),
        "coverage":summary,
        "assets":by_asset,
        "point_in_time_interpretation":{
            "catalog_proves_metric_availability_not_historical_known_at":True,
            "metric_interval_time_must_not_be_treated_as_publication_time":True,
            "historical_performance_trial_allowed":False,
            "prospective_capture_allowed_after_separate_gate":True,
            "missing_coverage_remains_missing":True
        },
        "guardrails":{
            "public_endpoint_only":True,
            "api_key_used":False,
            "private_data_accessed":False,
            "raw_history_downloaded":False,
            "performance_trial_started":False,
            "threshold_selection_performed":False,
            "holdout_opened":False,
            "active_v2r3_changed":False,
            "v2r4_changed":False,
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
