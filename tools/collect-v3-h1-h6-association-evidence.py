#!/usr/bin/env python3
"""Collect compact evidence from completed V3-H1/H6 association trials.

Local reports + immutable local trial ledger only. Does not re-run trials,
read holdout data, use network, tune thresholds, select winners, or mutate
strategy/runtime state.
"""
from __future__ import annotations
import argparse,hashlib,json,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from typing import Any

def utcnow()->str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()
def load(path:Path)->dict[str,Any]:
    j=json.loads(path.read_text("utf-8"))
    if not isinstance(j,dict):raise RuntimeError(f"{path}: root not object")
    return j
def latest(root:Path,pattern:str)->Path:
    xs=sorted(root.glob(pattern),key=lambda p:p.stat().st_mtime,reverse=True)
    if not xs:raise RuntimeError(f"no report matching {pattern}")
    return xs[0]
def ledger_rows(db:Path,ids:list[str])->tuple[dict[str,Any],dict[str,Any]]:
    con=sqlite3.connect(db)
    try:
        rows=con.execute("select trial_id,payload_sha256,payload_json from trials where trial_id in (?,?) order by trial_id",ids).fetchall()
        allrows=con.execute("select trial_id,payload_sha256,payload_json from trials order by trial_id").fetchall()
    finally:con.close()
    corrupt=[]
    for tid,expected,payload_json in allrows:
        obj=json.loads(payload_json)
        canonical=json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False)
        actual=hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if actual!=expected:corrupt.append(tid)
    selected={}
    for tid,digest,payload_json in rows:
        p=json.loads(payload_json)
        selected[tid]={
          "payload_sha256":digest,
          "created_at_utc":p["created_at_utc"],
          "parent_hypothesis":p["parent_hypothesis"],
          "strategy_revision":p["strategy_revision"],
          "code_fingerprint":p["code_fingerprint"],
          "dataset_snapshot":p["dataset_snapshot"],
          "dataset_sha256":p["dataset_sha256"],
          "influenced_later_design":p["influenced_later_design"]
        }
    return {"status":"PASS" if not corrupt else "FAIL","trial_count":len(allrows),"corrupt_trial_ids":corrupt},selected

def validate_report(j:dict[str,Any],kind:str,trial_id:str)->None:
    assert j["kind"]==kind and j["status"]=="PASS" and j["trial_id"]==trial_id
    assert j["dataset"]["holdout_status"]=="LOCKED_DO_NOT_READ_OR_LABEL"
    assert j["interpretation"]["descriptive_association_only"] is True
    assert j["interpretation"]["automatic_winner_selected"] is False
    assert j["interpretation"]["promotion_allowed"] is False
    g=j["guardrails"]
    for k in ("network_used","trade_returns","fee_adjusted_returns","threshold_search","pair_subset_search",
              "month_subset_search","horizon_search","p_value_feature_selection","holdout_opened",
              "holdout_labels_generated","active_v2r3_changed","v2r4_changed","orders","leverage","real_money_actions"):
        assert g[k] is False

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--trading-root",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    reports=a.trading_root/"Historical"/"reports"
    db=a.trading_root/"Historical"/"trials"/"trial-ledger.sqlite3"
    h1p=latest(reports,"v3-h1-association-001-*.json")
    h6p=latest(reports,"v3-h6-association-001-*.json")
    h1=load(h1p);h6=load(h6p)
    validate_report(h1,"V3_H1_BREADTH_ASSOCIATION_RESULT_V1","V3-H1-ASSOC-001")
    validate_report(h6,"V3_H6_PRICE_VOLUME_ASSOCIATION_RESULT_V1","V3-H6-ASSOC-001")
    verify,selected=ledger_rows(db,["V3-H1-ASSOC-001","V3-H6-ASSOC-001"])
    assert verify["status"]=="PASS"
    assert set(selected)=={"V3-H1-ASSOC-001","V3-H6-ASSOC-001"}
    assert selected["V3-H1-ASSOC-001"]["influenced_later_design"] is False
    assert selected["V3-H6-ASSOC-001"]["influenced_later_design"] is False

    out={
      "schema_version":1,
      "kind":"V3_H1_H6_ASSOCIATION_EVIDENCE_V1",
      "collected_at_utc":utcnow(),
      "status":"PASS",
      "source_reports":{
        "h1":{"path":str(h1p),"sha256":sha256(h1p),"bytes":h1p.stat().st_size,"deterministic_summary_sha256":h1["deterministic_summary_sha256"]},
        "h6":{"path":str(h6p),"sha256":sha256(h6p),"bytes":h6p.stat().st_size,"deterministic_summary_sha256":h6["deterministic_summary_sha256"]}
      },
      "trial_ledger":{"db_path":str(db),"verify":verify,"selected_trials":selected},
      "h1":{
        "trial_id":h1["trial_id"],"spec_sha256":h1["spec_sha256"],"dataset":h1["dataset"],
        "splits":h1["splits"],"interpretation":h1["interpretation"],"guardrails":h1["guardrails"]
      },
      "h6":{
        "trial_id":h6["trial_id"],"spec_sha256":h6["spec_sha256"],"dataset":h6["dataset"],
        "splits":h6["splits"],"interpretation":h6["interpretation"],"guardrails":h6["guardrails"]
      },
      "collector_guardrails":{
        "reports_reexecuted":False,"network_used":False,"holdout_opened":False,
        "threshold_search":False,"winner_selected":False,"strategy_mutation":False,
        "orders":False,"real_money_actions":False
      }
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n","utf-8")
    print("V3_H1_H6_ASSOC_EVIDENCE PASS")
    print(json.dumps({
      "h1_report":str(h1p),"h1_summary_sha":h1["deterministic_summary_sha256"],
      "h6_report":str(h6p),"h6_summary_sha":h6["deterministic_summary_sha256"],
      "trial_count":verify["trial_count"],"ledger_corrupt":verify["corrupt_trial_ids"]
    },sort_keys=True))
    return 0
if __name__=="__main__":raise SystemExit(main())
