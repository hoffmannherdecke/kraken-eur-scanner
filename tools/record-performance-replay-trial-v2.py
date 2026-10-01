#!/usr/bin/env python3
"""Record frozen Performance Replay V2 development result in immutable trial ledger."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


def normalized_text_sha256(path: Path) -> str:
    text=path.read_text("utf-8").replace("\r\n","\n").replace("\r","\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str,Any]:
    obj=json.loads(path.read_text("utf-8"))
    if not isinstance(obj,dict):
        raise ValueError(f"JSON object required: {path}")
    return obj


def import_ledger(repo_root: Path):
    path=repo_root/"tools"/"historical-trial-ledger.py"
    spec=importlib.util.spec_from_file_location("historical_trial_ledger",path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to import historical-trial-ledger.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def code_fingerprint(repo_root: Path) -> str:
    rels=(
        "research/historical/performance-replay-spec-v2.json",
        "research/historical/performance-replay-spec-v2.lock.json",
        "tools/validate-performance-replay-spec-v2.py",
        "tools/historical-performance-replay-v2.py",
        "tools/record-performance-replay-trial-v2.py",
    )
    h=hashlib.sha256()
    for rel in rels:
        p=repo_root/rel
        h.update(rel.encode("utf-8")+b"\0")
        h.update(p.read_bytes()+b"\0")
    return "sha256:"+h.hexdigest()


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--spec",type=Path,required=True)
    ap.add_argument("--lock",type=Path,required=True)
    ap.add_argument("--result",type=Path,required=True)
    ap.add_argument("--db",type=Path,required=True)
    ap.add_argument("--schema",type=Path,required=True)
    ap.add_argument("--output-record",type=Path,required=True)
    ap.add_argument("--repo-root",type=Path,required=True)
    args=ap.parse_args()

    spec_obj=load_json(args.spec)
    lock_obj=load_json(args.lock)
    result=load_json(args.result)
    schema=load_json(args.schema)

    spec_sha=normalized_text_sha256(args.spec)
    if lock_obj.get("status")!="LOCKED":
        raise SystemExit("V2 spec lock is not LOCKED")
    if lock_obj.get("spec_sha256")!=spec_sha:
        raise SystemExit("V2 spec checksum does not match lock")
    if result.get("status")!="PASS":
        raise SystemExit("V2 result status is not PASS")
    if result.get("spec_sha256")!=spec_sha:
        raise SystemExit("V2 result spec checksum mismatch")
    holdout=result.get("holdout_guard",{})
    if holdout.get("holdout_metrics_computed") is not False:
        raise SystemExit("V2 holdout metrics were computed")
    if int(holdout.get("holdout_events_generated",-1))!=0:
        raise SystemExit("V2 holdout events were generated")
    if holdout.get("holdout_used_for_rule_selection") is not False:
        raise SystemExit("V2 holdout used for rule selection")

    ledger=import_ledger(args.repo_root)
    trial_id="PERF-EUR15-V2-"+spec_sha[:12].upper()
    record={
        "trial_id":trial_id,
        "created_at_utc":spec_obj["frozen_date"]+"T00:00:00Z",
        "parent_hypothesis":spec_obj["parent_hypothesis"],
        "strategy_revision":"EUR15_SECOND_LEG_CONFIRMATION_V2",
        "code_fingerprint":code_fingerprint(args.repo_root),
        "feature_schema_version":"EUR15_SECOND_LEG_CONFIRMATION_FEATURES_V2",
        "dataset_snapshot":{
            "kind":"KRAKEN_EUR15_NORMALIZED_DATASET_V1",
            "raw_archive_sha256":spec_obj["dataset"]["raw_archive_sha256"],
            "spec_sha256":spec_sha,
            "events_output_sha256":result["events_output_sha256"],
            "normalized_file_count":result["normalized_file_count"],
            "holdout_status":holdout["holdout_status"],
            "influenced_by_v1_validation":True,
        },
        "dataset_sha256":spec_obj["dataset"]["raw_archive_sha256"],
        "universe_method":spec_obj["dataset"]["survivorship_rule"],
        "train_window":spec_obj["evaluation_topology"]["development_seen"],
        "calibration_window":{
            "role":"not_separate_v2_all_pre2026_seen_development"
        },
        "validation_window":{
            "role":"not_clean_for_v2_due_to_v1_influence"
        },
        "holdout_window":None,
        "purge_seconds":0,
        "embargo_seconds":0,
        "fee_model":{
            "kind":"FROZEN_V2",
            "taker_pct_per_side":spec_obj["cost_model"]["taker_fee_pct_per_side"],
            "total_round_trip_primary_pct":spec_obj["cost_model"]["primary_cost_pct_round_trip"],
        },
        "spread_model":{
            "kind":spec_obj["cost_model"]["spread_model"],
            "separately_observed":False,
        },
        "slippage_model":{
            "kind":"FROZEN_FIXED_PROXY_V2",
            "pct_per_side":spec_obj["cost_model"]["slippage_pct_per_side"],
        },
        "fill_ordering_policy":"CONFIRM_CLOSE_THEN_NEXT_CONTIGUOUS_BAR_OPEN",
        "stop_policy":{
            "kind":"NO_STOP_V2",
            "stop_loss":spec_obj["execution"]["stop_loss"],
            "take_profit":spec_obj["execution"]["take_profit"],
        },
        "ttl_policy":{
            "kind":"CONFIRM_WITHIN_4_BARS_THEN_HOLD_16_BARS",
            "confirmation_max_wait_bars":spec_obj["confirmation"]["max_wait_bars"],
            "holding_period_minutes":spec_obj["execution"]["holding_period_minutes"],
        },
        "sizing_policy":{
            "kind":"EVENT_STUDY_NO_PORTFOLIO_SIZING",
            "portfolio_capital_simulation":False,
        },
        "parameters":{
            "initial_signal":spec_obj["initial_signal"],
            "confirmation":spec_obj["confirmation"],
            "execution":spec_obj["execution"],
            "cost_model":spec_obj["cost_model"],
            "development_gate_before_holdout":spec_obj["development_gate_before_holdout"],
            "provenance":spec_obj["provenance"],
        },
        "metrics":{
            "kind":result["kind"],
            "status":result["status"],
            "initial_signal_count":result["initial_signal_count"],
            "confirmed_event_count":result["confirmed_event_count"],
            "confirmation_rate":result["confirmation_rate"],
            "development_metrics":result["development_metrics"],
            "preregistered_development_gate":result["preregistered_development_gate"],
            "holdout_guard":result["holdout_guard"],
            "events_output_sha256":result["events_output_sha256"],
            "interpretation_guardrail":result["interpretation_guardrail"],
        },
        "influenced_later_design":False,
    }

    ledger.validate_record(record,schema)
    args.output_record.parent.mkdir(parents=True,exist_ok=True)
    args.output_record.write_text(json.dumps(record,indent=2,sort_keys=True)+"\n","utf-8")

    con=ledger.connect(args.db)
    try:
        ledger.init_db(con)
        existing=con.execute(
            "select payload_sha256,payload_json from trials where trial_id=?",
            (trial_id,)
        ).fetchone()
        digest=ledger.payload_sha256(record)
        if existing is None:
            digest=ledger.append_record(con,record,schema)
            status="PASS_RECORDED"
        else:
            existing_digest,existing_json=existing
            existing_obj=json.loads(existing_json)
            if existing_digest!=digest or ledger.payload_sha256(existing_obj)!=digest:
                raise SystemExit("immutable V2 trial conflict")
            status="ALREADY_RECORDED_IDENTICAL"
        verification=ledger.verify(con)
    finally:
        con.close()

    if verification["status"]!="PASS":
        raise SystemExit("trial ledger verification failed")

    out={
        "kind":"PERFORMANCE_REPLAY_TRIAL_RECORD_V2",
        "status":status,
        "trial_id":trial_id,
        "payload_sha256":digest,
        "spec_sha256":spec_sha,
        "ledger_trial_count":verification["trial_count"],
        "corrupt_trial_ids":verification["corrupt_trial_ids"],
        "development_gate_pass":result["preregistered_development_gate"]["pass"],
        "development_gate_action":result["preregistered_development_gate"]["action"],
        "holdout_opened":False,
        "guardrails":{
            "network_used":False,
            "active_strategy_changed":False,
            "paper_shadow_runtime_changed":False,
            "real_money_action":False,
        },
        "next_gate":"apply_v2_gate_without_opening_holdout",
    }
    print("PERFORMANCE_REPLAY_TRIAL_RECORD_V2 "+json.dumps(out,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
