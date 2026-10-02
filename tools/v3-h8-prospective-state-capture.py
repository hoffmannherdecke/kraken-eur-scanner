#!/usr/bin/env python3
"""One bounded prospective H8 on-chain state capture.

Wraps the already validated public Coin Metrics capture tool and emits a
state-shaped compact artifact. No history/backfill, outcomes, thresholds,
scheduler, account/private API, orders, or strategy mutation.
"""
from __future__ import annotations
import argparse, json, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CAPTURE=ROOT/"tools"/"v3-h8-coinmetrics-known-at-capture.py"
CONTRACT=ROOT/"research"/"v3"/"h8-prospective-onchain-state-contract-v1.json"

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    c=json.loads(CONTRACT.read_text("utf-8"))
    assert c["kind"]=="V3_H8_PROSPECTIVE_ONCHAIN_STATE_CONTRACT_V1"
    assert c["status"]=="FROZEN_PREREGISTERED_NOT_SCHEDULED"
    with tempfile.TemporaryDirectory() as td:
        raw=Path(td)/"capture.json"
        cmd=[sys.executable,str(CAPTURE),"--assets",",".join(c["fixed_assets"]),
             "--metrics",",".join(c["fixed_metrics"]),"--output",str(raw)]
        cp=subprocess.run(cmd,check=False,capture_output=True,text=True)
        if cp.returncode!=0:
            sys.stderr.write(cp.stdout+cp.stderr)
            return cp.returncode or 2
        j=json.loads(raw.read_text("utf-8"))
    rows=[]
    for r in j["rows"]:
        rows.append({
          "asset":r["asset"],"status":r["status"],
          "observation_time_utc":r.get("observation_time_utc"),
          "retrieved_at_utc":r.get("retrieved_at_utc"),
          "safe_known_at_upper_bound_utc":r.get("safe_known_at_upper_bound_utc"),
          "provider_asset_eod_completion_utc":r.get("provider_asset_eod_completion_utc"),
          "metric_status_times_if_returned":r.get("metric_status_times_if_returned",{}),
          "metrics":r.get("metrics",{}),
          "observation_age_at_retrieval_seconds":r.get("observation_age_at_retrieval_seconds")
        })
    out={
      "schema_version":1,"kind":"V3_H8_PROSPECTIVE_ONCHAIN_STATE_CAPTURE_V1",
      "state_id":c["state_id"],"status":"PASS" if j["status"]=="PASS" else "FAIL",
      "request_started_at_utc":j["request_started_at_utc"],
      "request_finished_at_utc":j["request_finished_at_utc"],
      "rows":rows,
      "interpretation":{
        "retrieved_at_is_known_at_upper_bound":True,
        "historical_known_at_reconstruction_performed":False,
        "future_outcomes_joined":False,
        "thresholds_selected":False,
        "trade_rule_created":False
      },
      "guardrails":{
        "public_endpoint_only":True,"api_key_used":False,"automatic_schedule_enabled":False,
        "historical_backfill_performed":False,"holdout_opened":False,
        "active_v2r3_changed":False,"v2r4_changed":False,"paper_runtime_changed":False,
        "orders":False,"real_money_actions":False
      }
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n","utf-8")
    print("V3_H8_PROSPECTIVE_STATE "+json.dumps({
      "status":out["status"],"rows":len(rows),
      "returned":sum(x["status"]=="ROW_RETURNED" for x in rows),
      "missing":sum(x["status"]!="ROW_RETURNED" for x in rows)
    },sort_keys=True))
    return 0 if out["status"]=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
