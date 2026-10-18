"""Real-time V3 PAPER WAIT observer with zero model calls or order authority.

A WAIT is not a BUY. Only observations ACTUALLY collected and known during
the model-specified TTL can match conditions. An absent/late observation is
UNKNOWN, never reconstructed as an early real purchase. Tick is intended for
the ONE existing Mini-PC supervisor, not a new scheduled task.
"""
from __future__ import annotations
import json,math
from datetime import timedelta
from pathlib import Path
from typing import Any
from paper_evaluator.v3_experimental_paper_journal_v1 import (
    make_receipt,store_receipt_explicitly,clock,
)
from paper_evaluator.v3_paper_minipc_one_candidate_v1 import REVISION

FIELDS={
    "last_eur","bid_eur","ask_eur","spread_pct",
    "closed_1m_close_eur","closed_1m_volume_ratio_5",
    "closed_5m_close_eur","closed_5m_volume_ratio_5",
    "closed_15m_close_eur","closed_15m_volume_ratio_4",
}
NONNEGATIVE={"spread_pct","closed_1m_volume_ratio_5",
             "closed_5m_volume_ratio_5","closed_15m_volume_ratio_4"}
OPS={">":lambda a,b:a>b,">=":lambda a,b:a>=b,
     "<":lambda a,b:a<b,"<=":lambda a,b:a<=b}

def candidate_receipts(journal:Path,series_id:str,candidate_id:str)->list[dict]:
    if not journal.is_dir() or journal.is_symlink():
        raise ValueError("isolated existing V3 journal required")
    rows=[]
    for p in journal.glob("*.json"):
        row=json.loads(p.read_text("utf-8"))
        if row.get("series_id")==series_id and row.get("candidate_id")==candidate_id:
            if row.get("revision")!=REVISION:raise ValueError("mixed revision")
            rows.append(row)
    return rows

def _wait_setup(rows:list[dict])->tuple[dict,dict,dict,int,Any]:
    origin=next((r for r in rows if r["phase"] in (
        "SCANNER_CAPTURE","P1_CHILD_ENROLLMENT")),None)
    p4=next((r for r in rows if r["phase"]=="P4_VALIDATION"),None)
    watch=next((r for r in rows if r["phase"]=="WAIT_WATCH" and r["result"]=="WAIT"),None)
    model=next((r for r in rows if r["phase"]=="MODEL_RESPONSE"),None)
    if (not origin or not p4 or p4["result"]!="WAIT" or
            not watch or not model or model["data"].get("raw_model_decision")!="WAIT"):
        raise ValueError("model P4 WAIT + original watch required; no source-only BUY")
    ttl=watch["data"].get("raw_wait_ttl_minutes")
    if type(ttl) is not int or not 1<=ttl<=60:raise ValueError("invalid model watch TTL")
    conditions=watch["data"].get("raw_watch_conditions")
    if not isinstance(conditions,list) or not 1<=len(conditions)<=6:
        raise ValueError("missing validated watch conditions")
    for c in conditions:
        if (not isinstance(c,dict) or c.get("metric") not in FIELDS
                or c.get("op") not in OPS
                or type(c.get("value")) not in (int,float)
                or not math.isfinite(c["value"])):
            raise ValueError("untrusted model WATCH comparison")
    decision=clock(model["data"]["model_response_at_utc"])
    if abs((decision-clock(watch["known_at_utc"])).total_seconds())>10:
        raise ValueError("mismatched model-watch lineage")
    return origin,p4,watch,ttl,decision

def observe_wait(*,journal:Path,series_id:str,candidate_id:str,
                 snapshot:dict[str,Any],now_at_utc:str)->dict[str,Any]:
    """Examine ONE current 5m closed candle/ask; never authorize more AI calls.

    snapshot must come from a live/known source and never be backfilled.
    """
    rows=candidate_receipts(journal,series_id,candidate_id)
    origin,p4,watch,ttl,decision=_wait_setup(rows)
    deadline=decision+timedelta(minutes=ttl)
    now=clock(now_at_utc)
    if now>deadline:
        return finish_wait(journal=journal,series_id=series_id,
                           candidate_id=candidate_id,now_at_utc=now_at_utc)
    if any(r["phase"]=="WAIT_EXPIRY" for r in rows):
        return {"status":"WAIT_ALREADY_EXPIRED","authorized_buy":False}
    if any(r["phase"]=="WAIT_RECHECK" and r["result"]=="PASS" for r in rows):
        return {"status":"WAIT_TRIGGER_ALREADY_RECORDED_REQUIRES_NEW_MODEL_AUTH",
                "authorized_buy":False}
    if not isinstance(snapshot,dict) or snapshot.get("pair")!=origin["pair"]:
        return {"status":"WAIT_NO_SAME_PAIR_SOURCE","authorized_buy":False}
    try:
        observed=clock(snapshot["observed_at_utc"])
        known=clock(snapshot["known_at_utc"])
        candle_end=clock(snapshot["closed_5m_end_utc"])
        values=snapshot["values"]
        if (not isinstance(values,dict) or not (decision<=observed<=known<=now<=deadline)
                or not decision<candle_end<=observed
                or (observed-candle_end).total_seconds()>450
                or (known-observed).total_seconds()>120):
            return {"status":"WAIT_NO_VALID_PIT_SOURCE_IN_TTL","authorized_buy":False}
        checks=[]
        for condition in watch["data"]["raw_watch_conditions"]:
            metric=condition["metric"]
            v=values.get(metric)
            if (type(v) not in (int,float) or not math.isfinite(v)
                    or (v<0 if metric in NONNEGATIVE else v<=0)):
                return {"status":"WAIT_SOURCE_METRIC_UNKNOWN","authorized_buy":False}
            checks.append(OPS[condition["op"]](v,condition["value"]))
        if any(r["phase"]=="WAIT_RECHECK" and
               r["event_key"]=="C"+candle_end.strftime("%Y%m%dT%H%M%SZ") for r in rows):
            return {"status":"WAIT_SAME_CLOSED_5M_ALREADY_EVALUATED","authorized_buy":False}
    except (KeyError,ValueError,TypeError,OverflowError):
        return {"status":"WAIT_SOURCE_INVALID_NO_ACTION","authorized_buy":False}
    matched=all(checks)
    receipt=make_receipt(
        series_id=series_id,revision=REVISION,
        candidate_id=candidate_id,pair=origin["pair"],
        event_time_utc=origin["event_time_utc"],
        known_at_utc=snapshot["known_at_utc"],
        phase="WAIT_RECHECK",result="PASS" if matched else "WAIT",
        event_key="C"+candle_end.strftime("%Y%m%dT%H%M%SZ"),
        data={
            "review_family":p4["data"].get("review_family") or "INITIAL_WAIT",
            "wait_recheck_at_utc":snapshot["known_at_utc"],
            "watch_closed_5m_end_utc":snapshot["closed_5m_end_utc"],
            "watch_evaluated_conditions":len(checks),
            "watch_conditions_met":matched,
            "watch_snapshot_values":{k:round(float(v),8) for k,v in values.items() if k in FIELDS and type(v) in (int,float) and math.isfinite(v)},
            "source_status":"PROSPECTIVELY_OBSERVED_NO_TRADE_AUTHORITY",
            "phase_failure_stage":"MODEL_BUDGET_EXHAUSTED_NO_AUTO_REVIEW" if matched
                                  else "WAIT_CONDITIONS_NOT_YET_ALL_MET",
        })
    store_receipt_explicitly(journal,receipt)
    return {"status":"WAIT_CONDITIONS_MATCHED_REQUIRES_NEW_MODEL_P4_AUTH"
            if matched else "WAIT_VALID_5M_TICK_NOT_YET_MATCHED",
            "authorized_buy":False,"model_calls":0,
            "condition_count":len(checks),"observed_at_utc":snapshot["known_at_utc"]}

def finish_wait(*,journal:Path,series_id:str,candidate_id:str,
                now_at_utc:str)->dict[str,Any]:
    rows=candidate_receipts(journal,series_id,candidate_id)
    origin,_,watch,ttl,decision=_wait_setup(rows)
    now=clock(now_at_utc)
    if now<decision+timedelta(minutes=ttl):
        return {"status":"WAIT_TTL_NOT_EXPIRED","authorized_buy":False}
    if any(r["phase"]=="WAIT_EXPIRY" for r in rows):
        return {"status":"WAIT_EXPIRY_ALREADY_FINAL","authorized_buy":False}
    matched=any(r["phase"]=="WAIT_RECHECK" and r["result"]=="PASS" for r in rows)
    # Critical honesty: no complete sequence of tick observations -> UNKNOWN
    # about what happened in real time. An observed trigger is still NOT BUY.
    receipt=make_receipt(
        series_id=series_id,revision=REVISION,
        candidate_id=candidate_id,pair=origin["pair"],
        event_time_utc=origin["event_time_utc"],
        known_at_utc=now_at_utc,
        phase="WAIT_EXPIRY",result="CLOSED" if matched else "UNKNOWN",
        data={
            "raw_wait_ttl_minutes":ttl,
            "watch_conditions_met":matched,
            "watch_valid_snapshot_count":sum(
                1 for x in rows if x["phase"]=="WAIT_RECHECK"),
            "source_status":"MATCHED_WITHIN_TTL_BUT_NO_NEW_BUY_AUTHORITY" if matched
                else "UNKNOWN_DID_NOT_CAPTURE_COMPLETE_TTL_NO_NEGATIVE_INFERENCE",
            "watch_did_not_prove_no_trigger":not matched,
            "phase_failure_stage":"MODEL_REVIEW_AUTHORITY_EXHAUSTED" if matched
                                   else "HISTORICAL_WAIT_TTL_OBSERVATION_INCOMPLETE",
        })
    store_receipt_explicitly(journal,receipt)
    return {"status":"WAIT_EXPIRED_AFTER_MATCH_NO_BUY" if matched
                    else "WAIT_EXPIRED_UNKNOWN_WITH_UNPROVEN_MISSED_OPPORTUNITY",
            "authorized_buy":False,"model_calls":0,"historical_trigger_proven":matched}
