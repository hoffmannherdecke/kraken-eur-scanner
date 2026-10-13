#!/usr/bin/env python3
"""V3 Mini-PC Paper 6/24/72h followup, source-bounded and rotation-safe.

Uses EXISTING captured closed Kraken 1m path snapshots, never fabricates
missing bars. Every mature horizon and censored missingness is a NEW immutable
event; pending original is retained across series closures. No model/HTTP/SQL.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from typing import Any
from paper_evaluator.v3_experimental_paper_pathwise_economics_v1 import estimate_closed_1m_paper_path
from paper_evaluator.v3_paper_minipc_closed_1m_capture_v1 import require_prospective_assembled_path
from paper_evaluator.v3_experimental_paper_journal_v1 import (
    make_receipt,store_receipt_explicitly,clock,
)
from paper_evaluator.v3_paper_minipc_one_candidate_v1 import REVISION

def record_horizon(*,journal:Path,series_id:str,candidate_id:str,
                   captured_1m:dict[str,Any],horizon_hours:int)->dict:
    if horizon_hours not in (6,24,72):
        raise ValueError("known horizon only")
    rows=[]
    for p in journal.glob("*.json"):
        obj=json.loads(p.read_text("utf-8"))
        if obj.get("series_id")==series_id and obj.get("candidate_id")==candidate_id:
            rows.append(obj)
    if not rows:raise ValueError("original immutable candidate receipt missing")
    initial=next((r for r in rows if r["phase"]=="SCANNER_CAPTURE"),None)
    fill=next((r for r in rows if r["phase"]=="PAPER_FILL"),None)
    if initial is None:raise ValueError("no original V3 scanner event")
    phase=f"FOLLOWUP_{horizon_hours}H"
    # A corrected old result cannot be silently rewritten. Manual source
    # amendments must use a separately audited lineage, never this endpoint.
    if any(r["phase"]==phase and r["result"] in ("MATURE_COMPLETE","CENSORED") for r in rows):
        return {"status":"FOLLOWUP_ALREADY_FINAL_IMMUTABLE","horizon_hours":horizon_hours}
    now_at=captured_1m.get("captured_at_utc")
    if now_at is None or clock(now_at)<clock(initial["event_time_utc"]):
        raise ValueError("no prospective capture time")
    if fill is None:
        raise ValueError("no economic buy; use separate no-BUY opportunity observer")
    require_prospective_assembled_path(assembled=captured_1m,pair=fill["pair"])
    f=fill["data"]
    if (captured_1m.get("kind")!="KRAKEN_CLOSED_1M_PATH_CAPTURE_V1"
            or captured_1m.get("pair")!=fill["pair"]
            or captured_1m.get("source")!="KRAKEN_SPOT_EUR_PUBLIC"
            or not isinstance(captured_1m.get("closed_bars"),list)):
        raise ValueError("no actual Kraken closed 1m provenance")
    data=estimate_closed_1m_paper_path(
        candidate_id=candidate_id,pair=fill["pair"],
        entry_at_utc=fill["known_at_utc"],
        observed_at_utc=now_at,entry_ask_eur=f["paper_entry_ask_eur"],
        stop_eur=f["validated_stop_eur"],
        stage2_trigger_eur=f["validated_stage2_eur"],
        stage2_ttl_minutes=f["stage2_ttl_minutes"],
        closed_1m_bars=captured_1m["closed_bars"],
        horizon_minutes=horizon_hours*60,
    )
    status=data["status"]
    if status=="CENSORED_HORIZON_NOT_YET_MATURE":
        return {"status":"HORIZON_NOT_MATURE_NO_PREMATURE_FINAL",
                "horizon_hours":horizon_hours}
    mature=status=="MATURE_ESTIMATED_PAPER_NET_NOT_VERIFIED_FILL"
    # Allow normal source recovery time before final CENSORED: a temporary
    # missing scan cannot become an irreversible data-loss verdict.
    from datetime import timedelta
    deadline=clock(fill["known_at_utc"])+timedelta(hours=horizon_hours,minutes=60)
    if not mature and clock(now_at)<deadline:
        return {"status":"FOLLOWUP_DATA_GAP_PENDING_BOUNDED_RECOVERY",
                "horizon_hours":horizon_hours,
                "source_status":status}
    outcome_data={
        "followup_source":"KRAKEN_CLOSED_1M_PATH_CAPTURE_V1",
        "path_contiguous_1m_verified":mature,
        "position_net_pnl_eur":data["net_pnl_eur"],
        "position_net_return_pct":data["net_return_pct"],
        "mfe_pct":data.get("gross_mfe_from_entry_ask_pct"),
        "mae_pct":data.get("gross_mae_from_entry_ask_pct"),
        "paper_exit_reason":data.get("exit_reason"),
        "paper_exit_bid_eur":data.get("exit_synthetic_bid_eur"),
        "stop_before_profit_ordering":(
            "STOP_FIRST_IF_AMBIGUOUS" if data.get("stop_first_when_bar_ambiguous")
            else "CONSERVATIVE_1M_PATH_NO_INTRABAR_ORDER_PROVEN"),
    }
    if not mature:
        outcome_data["censor_reason"]=status
    receipt=make_receipt(
        series_id=series_id,revision=REVISION,candidate_id=candidate_id,
        pair=fill["pair"],event_time_utc=initial["event_time_utc"],
        known_at_utc=now_at,phase=phase,
        result="MATURE_COMPLETE" if mature else "CENSORED",
        data=outcome_data,event_key=f"FINAL{horizon_hours}H")
    state,p=store_receipt_explicitly(journal,receipt)
    return {"status":state,"horizon_hours":horizon_hours,
            "economic_estimate_status":status,
            "net_estimate_eur":data["net_pnl_eur"],
            "source_is_true_exchange_fill":False,
            "receipt":p.name}

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--journal",required=True,type=Path)
    p.add_argument("--series",required=True)
    p.add_argument("--candidate-id",required=True)
    p.add_argument("--captured-closed-1m",required=True,type=Path)
    p.add_argument("--hours",required=True,type=int,choices=(6,24,72))
    a=p.parse_args()
    cap=json.loads(a.captured_closed_1m.read_text("utf-8"))
    print(json.dumps(record_horizon(journal=a.journal,series_id=a.series,
                                    candidate_id=a.candidate_id,captured_1m=cap,
                                    horizon_hours=a.hours),sort_keys=True))
    return 0

if __name__=="__main__":raise SystemExit(main())
