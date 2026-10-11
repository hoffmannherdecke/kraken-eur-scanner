"""Tiny Mini-PC reuse of existing V3 immutable Paper journal: actionable learning.

No new scanner, scheduler, model, order or automatic strategy mutation.
Censor and unknown retained; missed-move labels are research, not gains.
"""
from __future__ import annotations
import json,statistics
from collections import Counter,defaultdict
from pathlib import Path
from typing import Any
from paper_evaluator.v3_experimental_paper_journal_v1 import clock,funnel_summary

def analyze_receipts(folder:Path,series_id:str)->dict[str,Any]:
    if not folder.is_dir():raise ValueError("V3 journal folder missing")
    events=[]
    for p in folder.glob("*.json"):
        row=json.loads(p.read_text("utf-8"))
        if row.get("series_id")==series_id:
            events.append(row)
    if not events:
        return {"kind":"V3_MINIPC_LEARNING_HEALTH_V1","status":"NO_V3_PAPER_EVIDENCE",
                "active_runtime_proven":False}
    by_candidate=defaultdict(list)
    for e in events:by_candidate[e["candidate_id"]].append(e)
    funnel=funnel_summary(events)
    lags=[];missed=[];horizon_censored=Counter()
    families=Counter();unknown_reasons=Counter()
    for cid,rows in by_candidate.items():
        capture=next((e for e in rows if e["phase"]=="SCANNER_CAPTURE"),None)
        response=next((e for e in rows if e["phase"]=="MODEL_RESPONSE"),None)
        if capture and response:
            lags.append(max(0,(clock(response["known_at_utc"])-
                               clock(capture["event_time_utc"])).total_seconds()))
        eligible=next((e for e in rows if e["phase"]=="FULL_REVIEW_ELIGIBILITY"),None)
        if eligible: families[eligible["data"].get("review_family","UNKNOWN")]+=1
        for e in rows:
            if e["result"] in ("UNKNOWN","ERROR","SKIP"):
                unknown_reasons[str(e["data"].get("phase_failure_stage") or
                                  e["data"].get("source_status") or e["phase"])]+=1
            if e["phase"] in ("FOLLOWUP_6H","FOLLOWUP_24H") and e["result"]=="CENSORED":
                horizon_censored[e["phase"]]+=1
            if e["phase"]=="FOLLOWUP_24H" and e["result"]=="MATURE_COMPLETE":
                data=e["data"]
                if data.get("source_status")=="NO_BUY_OPPORTUNITY_LABEL_NOT_EXECUTABLE_TRADED_PNL":
                    mfe=data.get("mfe_pct")
                    if type(mfe) in (float,int) and mfe>=5:
                        missed.append({"candidate_id":cid,
                            "mfe24_pct":mfe,"mae24_pct":data.get("mae_pct"),
                            "close24_pct":data.get("close_return_pct"),
                            "profit_claimed":False})
    missed.sort(key=lambda x:x["mfe24_pct"],reverse=True)
    return {
        "kind":"V3_MINIPC_LEARNING_HEALTH_V1","status":"READ_ONLY_JOURNAL_ANALYSIS",
        "series_id":series_id,"unique_candidates":len(by_candidate),
        "phase_conversion_counts":funnel["phase_result_counts"],
        "reasons_are_not_independent_vetoes":True,
        "unknown_and_skipped_causes":dict(unknown_reasons),
        "entry_family_counts":dict(families),
        "model_response_lag_seconds_p50":statistics.median(lags) if lags else None,
        "model_response_lag_seconds_max":max(lags) if lags else None,
        "horizon_censored":dict(horizon_censored),
        "mature_24h_no_buy_opportunity_count_mfe_ge_5pct":len(missed),
        "top_10_missed_move_for_causal_review_not_pnl":missed[:10],
        "economic_strategy_promotion":False,
        "model_calls":0,"new_kraken_reads":0,"cloud_writes":0,
        "orders":False,"real_money_actions":False,
        "next_gate":"COMPARE_SOURCE_PROVENANCE_FAMILY_AND_COST_NET_PAPER_ACTUAL_RECORDED_CASES"
    }
