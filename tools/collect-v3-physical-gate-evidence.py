#!/usr/bin/env python3
"""Collect compact evidence from the already-completed V3 physical gate bundle.

Local files only. No network, no APIs, no strategy mutation, no evaluator,
no orders and no re-execution of H1/H6/H3/H9/Binance tests.
"""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def utcnow()->str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def load(path:Path)->dict[str,Any]:
    obj=json.loads(path.read_text("utf-8"))
    if not isinstance(obj,dict): raise RuntimeError(f"{path}: root not object")
    return obj

def latest(root:Path,pattern:str)->Path:
    xs=sorted(root.glob(pattern),key=lambda p:p.stat().st_mtime,reverse=True)
    if not xs: raise RuntimeError(f"no file for {pattern} under {root}")
    return xs[0]

def require_false(d:dict[str,Any],keys:list[str],label:str)->None:
    for k in keys:
        if d.get(k) is not False:
            raise RuntimeError(f"{label}: guardrail {k} is not false")

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--trading-root",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    hist=a.trading_root/"Historical"/"reports"
    logs=a.trading_root/"Logs"
    paths={
      "h6":latest(hist,"v3-h6-feature-integrity-*.json"),
      "h1":latest(hist,"v3-h1-breadth-feature-integrity-*.json"),
      "h3":latest(logs,"v3-h3-ws-book-smoke-*.json"),
      "h9":latest(logs,"v3-h9-book-trade-clock-*.json"),
      "binance":logs/"minipc-binance-public-access-latest.json",
    }
    for p in paths.values():
        if not p.exists(): raise RuntimeError(f"missing report: {p}")
    j={k:load(v) for k,v in paths.items()}

    # Fail closed on exact completed-gate invariants.
    assert j["h6"]["kind"]=="V3_H6_EUR15_FEATURE_INTEGRITY_RESULT_V1"
    assert j["h6"]["status"]=="PASS"
    assert j["h6"]["guardrails"]["holdout_opened"] is False
    assert j["h6"]["guardrails"]["active_v2r3_changed"] is False
    assert j["h6"]["guardrails"]["v2r4_changed"] is False
    assert j["h6"]["guardrails"]["orders"] is False
    assert j["h6"]["guardrails"]["real_money_actions"] is False

    assert j["h1"]["kind"]=="V3_H1_EUR15_BREADTH_FEATURE_INTEGRITY_RESULT_V1"
    assert j["h1"]["status"]=="PASS"
    assert j["h1"]["guardrails"]["holdout_opened"] is False
    assert j["h1"]["guardrails"]["active_v2r3_changed"] is False
    assert j["h1"]["guardrails"]["v2r4_changed"] is False
    assert j["h1"]["guardrails"]["orders"] is False
    assert j["h1"]["guardrails"]["real_money_actions"] is False

    assert j["h3"]["kind"]=="V3_H3_KRAKEN_SPOT_WS_BOOK_RECONCILIATION_SMOKE_V1"
    assert j["h3"]["status"]=="PASS"
    assert j["h3"]["totals"]["checksum_fail"]==0
    assert j["h3"]["interpretation"]["bounded_reconnect_resubscribe_proven"] is True
    assert j["h3"]["interpretation"]["queue_position_proven"] is False
    assert j["h3"]["interpretation"]["maker_fill_probability_proven"] is False
    assert j["h3"]["guardrails"]["orders"] is False
    assert j["h3"]["guardrails"]["real_money_actions"] is False

    assert j["h9"]["kind"]=="V3_H9_PUBLIC_BOOK_TRADE_CLOCK_SMOKE_V1"
    assert j["h9"]["status"]=="PASS"
    assert j["h9"]["totals"]["trades"]>0
    assert j["h9"]["totals"]["aligned_preceding_book_trades"]>0
    assert j["h9"]["interpretation"]["queue_position_proven"] is False
    assert j["h9"]["interpretation"]["maker_fill_probability_proven"] is False
    assert j["h9"]["interpretation"]["routing_decision_allowed"] is False
    assert j["h9"]["guardrails"]["orders"] is False
    assert j["h9"]["guardrails"]["real_money_actions"] is False

    assert j["binance"]["kind"]=="MINIPC_BINANCE_PUBLIC_ACCESS_SMOKE_V1"
    assert j["binance"]["status"]=="HEALTHY"
    assert all(x["ok"] for x in j["binance"]["checks"])
    assert j["binance"]["guardrails"]["orders"] is False
    assert j["binance"]["guardrails"]["real_money_actions"] is False

    out={
      "schema_version":1,
      "kind":"V3_PHYSICAL_GATE_BUNDLE_EVIDENCE_V1",
      "collected_at_utc":utcnow(),
      "status":"PASS",
      "source_reports":{k:{
          "path":str(paths[k]),
          "sha256":sha256(paths[k]),
          "bytes":paths[k].stat().st_size
      } for k in paths},
      "h6":{
        "trial_id":j["h6"]["trial_id"],
        "file_count":j["h6"]["dataset"]["file_count"],
        "rows_processed_before_holdout":j["h6"]["dataset"]["rows_processed_before_holdout"],
        "pairs_with_any_eligible_cutoff":j["h6"]["coverage"]["pairs_with_any_eligible_cutoff"],
        "deterministic_summary_sha256":j["h6"]["deterministic_summary_sha256"],
      },
      "h1":{
        "trial_id":j["h1"]["trial_id"],
        "file_count":j["h1"]["dataset"]["file_count"],
        "feature_rows_processed_before_holdout":j["h1"]["dataset"]["feature_rows_processed_before_holdout"],
        "cutoffs_processed":j["h1"]["cutoffs_processed"],
        "leader_cutoffs":j["h1"]["leader_contract"]["cutoffs_with_at_least_one_leader_1h"],
        "deterministic_summary_sha256":j["h1"]["deterministic_summary_sha256"],
      },
      "h3":{
        "checked_at_utc":j["h3"]["checked_at_utc"],
        "symbols":j["h3"]["symbols"],
        "cycles_completed":j["h3"]["cycles_completed"],
        "updates":j["h3"]["totals"]["updates"],
        "checksum_pass":j["h3"]["totals"]["checksum_pass"],
        "checksum_fail":j["h3"]["totals"]["checksum_fail"],
        "max_source_age_ms_by_symbol":{
          s:max((c["symbols"][s]["max_source_age_ms"] or 0) for c in j["h3"]["cycles"])
          for s in j["h3"]["symbols"]
        }
      },
      "h9":{
        "checked_at_utc":j["h9"]["checked_at_utc"],
        "symbols":j["h9"]["symbols"],
        "trades":j["h9"]["totals"]["trades"],
        "aligned_preceding_book_trades":j["h9"]["totals"]["aligned_preceding_book_trades"],
        "per_symbol":{
          s:{
            "trades":r["trades"],
            "book_checksum_fail":r["book"]["checksum_fail"],
            "trade_id_duplicates":r["trade_id_sequence"]["duplicates"],
            "trade_id_out_of_order":r["trade_id_sequence"]["out_of_order"],
            "no_book_yet":r["clock_join"]["no_book_yet"]
          } for s,r in j["h9"]["per_symbol"].items()
        }
      },
      "binance":{
        "checked_at_utc":j["binance"]["checked_at_utc"],
        "status":j["binance"]["status"],
        "checks":[{
          "name":x["name"],"ok":x["ok"],"latency_ms":x.get("latency_ms"),
          "url_host":x.get("url_host")
        } for x in j["binance"]["checks"]]
      },
      "global_guardrails":{
        "holdout_opened":False,
        "active_v2r3_changed":False,
        "v2r4_changed":False,
        "private_api_used":False,
        "orders":False,
        "leverage_action":False,
        "real_money_actions":False,
        "reports_reexecuted":False,
        "network_used_by_collector":False
      }
    }
    raw=json.dumps(out,indent=2,sort_keys=True)+"\n"
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(raw,"utf-8")
    print("V3_PHYSICAL_GATE_EVIDENCE PASS")
    print(raw,end="")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
