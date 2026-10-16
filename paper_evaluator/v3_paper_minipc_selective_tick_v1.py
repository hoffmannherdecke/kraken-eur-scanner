#!/usr/bin/env python3
"""A SINGLE selective V3-PAPER observation tick, suitable for existing supervisor.

Not a separate daemon or an activation. Reads ONE original candidate, fetches
public Kraken closed 1m, journals a TRUE prospective WAIT checkpoint only if
within TTL, and matures due 6/24/72h followups from archived observations.
Never calls any AI/model/private exchange API, creates orders, changes
paper_series, touches V2R4 or creates schedules. Supabase ACK is a separate
existing explicitly authorized receipt-sync operation.
"""
from __future__ import annotations
import argparse,json
from datetime import datetime,timedelta,timezone
from pathlib import Path
from typing import Any,Callable
from paper_evaluator import evaluate
from paper_evaluator.successor_coin_entry_evidence_v1 import fetch_public_entry_evidence
from paper_evaluator.v3_paper_minipc_closed_1m_capture_v1 import (
    capture_public_1m,assemble,early_path_coverage,
)
from paper_evaluator.v3_paper_minipc_followup_v1 import record_horizon
from paper_evaluator.v3_paper_missed_opportunity_followup_v1 import followup_no_buy
from paper_evaluator.v3_paper_wait_observer_v1 import (
    candidate_receipts,observe_wait,finish_wait,
)
from paper_evaluator.v3_experimental_paper_journal_v1 import clock

def utc_now()->str:
    return datetime.now(timezone.utc).isoformat()

def tick_once(*,candidate:dict[str,Any],series_id:str,journal:Path,
              capture_dir:Path,clock_now:Callable[[],str]=utc_now,
              capture:Callable=capture_public_1m,
              fetch:Callable=fetch_public_entry_evidence,
              ticker:Callable=evaluate.kraken_ticker)->dict[str,Any]:
    if not series_id.startswith("PAPER-V3-CANARY-"):
        raise ValueError("research CANARY only until independent single writer released")
    if not isinstance(candidate,dict):
        raise ValueError("original candidate object missing")
    cid=candidate.get("candidate_id")
    pair=candidate.get("pair")
    altname=candidate.get("altname")
    if (not isinstance(cid,str) or not cid
            or not isinstance(pair,str) or not pair.endswith("/EUR")
            or not isinstance(altname,str) or not altname.isalnum()):
        raise ValueError("valid source Kraken EUR candidate and altname required")
    source_time=clock(candidate["event_time_utc"])
    rows=candidate_receipts(journal,series_id,cid)
    origin=next((r for r in rows if r["phase"]=="SCANNER_CAPTURE"),None)
    if not origin or origin["pair"]!=pair or clock(origin["event_time_utc"])!=source_time:
        raise ValueError("candidate not previously journaled at true original PIT clock")
    results={"kind":"V3_PAPER_EXISTING_SUPERVISOR_SELECTIVE_TICK_V1",
             "series_id":series_id,"candidate_id":cid,"pair":pair,
             "paper_only":True,"model_called":False,"model_attempts":0,
             "orders":False,"real_money_actions":False,
             "v2r4_changed":False,"new_schedules":0}
    # No endless data accumulation after ALL three original followup
    # horizons have individually durable final outcomes. PENDING does not
    # count as final; the original six/24/72h facts remain immutable.
    finals={r["phase"] for r in rows
            if r["phase"] in ("FOLLOWUP_6H","FOLLOWUP_24H","FOLLOWUP_72H")
            and r["result"] in ("MATURE_COMPLETE","CENSORED")}
    if finals=={"FOLLOWUP_6H","FOLLOWUP_24H","FOLLOWUP_72H"}:
        results["status"]="ALL_FOLLOWUP_HORIZONS_FINAL_NO_NEW_PUBLIC_KRAKEN_REQUEST"
        results["source_capture"]="SKIPPED_COMPLETE_IMMUTABLE_6H24H72H"
        results["prospective_1m_bars"]=0
        results["horizons"]={}
        return results
    # The existing Kraken rate-limited client is called ONCE for this
    # tracked candidate, not a second scanner of all 500+ assets.
    snapshot=capture(pair=pair,altname=altname,outdir=capture_dir)
    if snapshot.get("status")!="CLOSED_KRAKEN_1M_SNAPSHOT_SAVED":
        raise ValueError("no actual Kraken source capture acknowledgement")
    results["source_capture"]=snapshot["status"]
    results["source_closed_1m_count"]=snapshot["count"]
    watch=next((r for r in rows if r["phase"]=="WAIT_WATCH" and r["result"]=="WAIT"),None)
    p4=next((r for r in rows if r["phase"]=="P4_VALIDATION"),None)
    if watch and p4 and p4["result"]=="WAIT":
        old=next((r for r in rows if r["phase"]=="MODEL_RESPONSE"),None)
        if old and isinstance(old["data"].get("model_response_at_utc"),str):
            start=clock(old["data"]["model_response_at_utc"])
            ttl=watch["data"].get("raw_wait_ttl_minutes")
            now=clock(clock_now())
            if type(ttl) is int and now>=start+timedelta(minutes=ttl):
                results["wait"]=finish_wait(journal=journal,series_id=series_id,
                                              candidate_id=cid,now_at_utc=clock_now())
            elif type(ttl) is int and 1<=ttl<=60:
                # Real closed source is requested only while the window is live.
                coin=fetch(altname,pair)
                q=ticker(altname)
                frames=coin.get("frames") or {}
                frame=frames.get("5") or {}
                frame1=frames.get("1") or {}
                frame15=frames.get("15") or {}
                now_at=clock_now()
                evidence={
                    "pair":pair,"observed_at_utc":coin.get("observed_at_utc"),
                    "known_at_utc":now_at,
                    "closed_5m_end_utc":frame.get("last_closed_bar_end_utc"),
                    "values":{
                        "last_eur":q.get("last"),
                        "bid_eur":q.get("bid"),
                        "ask_eur":q.get("ask"),
                        "spread_pct":q.get("spread_pct"),
                        "closed_1m_close_eur":frame1.get("closed_close_eur"),
                        "closed_1m_volume_ratio_5":frame1.get("volume_ratio_prior_5"),
                        "closed_5m_close_eur":frame.get("closed_close_eur"),
                        "closed_5m_volume_ratio_5":frame.get("volume_ratio_prior_5"),
                        "closed_15m_close_eur":frame15.get("closed_close_eur"),
                        "closed_15m_volume_ratio_4":frame15.get("volume_ratio_prior_4"),
                    },
                }
                if frame.get("status")!="VALID" or coin.get("pair")!=pair:
                    results["wait"]={"status":"WAIT_5M_SOURCE_UNVERIFIED_NO_ACTION",
                                     "authorized_buy":False}
                else:
                    results["wait"]=observe_wait(journal=journal,series_id=series_id,
                        candidate_id=cid,snapshot=evidence,now_at_utc=now_at)
    now=clock(clock_now())
    # The original model decision is final if no BUY: followup even SKIP/WAIT/
    # source-UNKNOWN cases, never reclassify ex-post MFE as earned trades.
    capture_path=assemble(snapshots=capture_dir,pair=pair,
        entry_at_utc=origin["event_time_utc"],observed_at_utc=clock_now(),
        max_live_capture_lag_minutes=15)
    results["prospective_1m_bars"]=len(capture_path["closed_bars"])
    # Zero extra Kraken requests, receipts, or tasks: signal a missing
    # first minute while the event is still fresh instead of pretending
    # a later historic OHLC download was a live witnessed source path.
    results["early_1m_coverage"]=early_path_coverage(
        assembled=capture_path,entry_at_utc=origin["event_time_utc"],
        observed_at_utc=capture_path["captured_at_utc"])
    results["horizons"]={}
    buys=any(r["phase"]=="PAPER_FILL" and r["result"]=="PAPER_FILLED" for r in rows)
    for hrs in (6,24,72):
        if now<source_time+timedelta(hours=hrs):
            continue
        if buys:
            a=record_horizon(journal=journal,series_id=series_id,
                             candidate_id=cid,captured_1m=capture_path,
                             horizon_hours=hrs)
        else:
            a=followup_no_buy(journal=journal,series_id=series_id,
                              candidate_id=cid,captured_1m=capture_path,hours=hrs)
        results["horizons"][f"{hrs}h"]=a["status"]
    return results



def first_enrolled_canary_tick_once(*, preflight:dict[str,Any],
                                    candidate:dict[str,Any], series_id:str,
                                    journal:Path, capture_dir:Path,
                                    clock_now:Callable[[],str],
                                    capture:Callable,
                                    fetch:Callable=fetch_public_entry_evidence,
                                    ticker:Callable=evaluate.kraken_ticker)->dict[str,Any]:
    """One existing-owner research intake→witness→observation handoff.

    This is NOT a new service, scheduler, model executor, writer or V3
    Paper release. The ONLY eligible series is the existing CANARY namespace;
    an actual V3 PAPER series remains blocked until independent cutover.
    Original immutable intake precedes any public source request. If the
    first minute is witnessed, the existing tick must reuse that SAME source
    instead of fetching Kraken a second time within this one owner cycle.
    """
    from paper_evaluator.v3_paper_intake_receipt_stage_v1 import (
        stage_and_witness_first_minute,
    )
    if (not series_id.startswith("PAPER-V3-CANARY-")
            or preflight.get("series_id") != series_id
            or not callable(capture) or not callable(clock_now)):
        raise ValueError("isolated original CANARY source owner only")
    selected=preflight.get("selected_candidates")
    if (not isinstance(selected,list) or len(selected)!=1
            or not isinstance(candidate,dict) or selected[0]!=candidate
            or candidate.get("entry_origin")!="SCANNER"):
        raise ValueError("exact one original scanner candidate required")
    observed_at_utc=clock_now()
    stage=stage_and_witness_first_minute(
        preflight=preflight,journal_directory=journal,
        capture_directory=capture_dir,observed_at_utc=observed_at_utc,
        capture=capture)
    if len(stage["enrollment"])!=1:
        raise ValueError("one source enrollment receipt required")
    witness=stage["enrollment"][0]
    good=("FIRST_CLOSED_MINUTE_WITNESSED_RESEARCH_ONLY",
          "FIRST_MINUTE_ALREADY_ARCHIVED_NO_DUPLICATE_GET",
          "FIRST_MINUTE_MISSING_NO_ECONOMIC_CLAIM")
    out={"kind":"V3_EXISTING_CANARY_SINGLE_OWNER_FIRST_TICK_V1",
         "series_id":series_id,"candidate_id":candidate["candidate_id"],
         "source_enrollment":witness,
         "source_capture_calls":stage["source_capture_calls"],
         "paper_writer_active":False,"model_http_calls":0,
         "cloud_ack_verified":False,"new_schedules":0,
         "v2r4_changed":False,"orders":False,
         "real_money_actions":False}
    if witness["status"] not in good:
        out["status"]="SOURCE_FIRST_MINUTE_NOT_READY_NO_OBSERVATION"
        out["tick_called"]=False
        return out
    # Existing owner has already authenticated the closed Kraken first-bar
    # via original capture SHA and prospective assemble. Reuse the persisted
    # snapshot within THIS invocation; future ordinary ticks still poll
    # once each to grow the 6/24/72h path prospectively.
    def already_captured(*,pair:str,altname:str,outdir:Path)->dict[str,Any]:
        if (pair!=candidate["pair"] or altname!=candidate["altname"]
                or outdir.resolve()!=capture_dir.resolve()):
            raise ValueError("source owner identity mismatch after capture")
        return {"status":"CLOSED_KRAKEN_1M_SNAPSHOT_SAVED",
                "count":1}
    observation=tick_once(
        candidate=candidate,series_id=series_id,journal=journal,
        capture_dir=capture_dir,clock_now=clock_now,
        capture=already_captured,fetch=fetch,ticker=ticker)
    out["tick_called"]=True
    out["status"]="SAME_OWNER_FIRST_SOURCE_AND_FOLLOWUP_TICK_NO_SECOND_GET"
    out["observation"]=observation
    return out

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--original-candidate-file",type=Path,required=True)
    p.add_argument("--series",required=True)
    p.add_argument("--journal",type=Path,required=True)
    p.add_argument("--capture-dir",type=Path,required=True)
    p.add_argument("--execute-public-kraken-tick",action="store_true")
    args=p.parse_args()
    if not args.execute_public_kraken_tick:
        print(json.dumps({"status":"PLAN_ONLY_NO_NETWORK_MODEL_OR_JOURNAL_CHANGE",
                          "orders":False,"model_calls":0}))
        return 0
    candidate=json.loads(args.original_candidate_file.read_text("utf-8"))
    result=tick_once(candidate=candidate,series_id=args.series,
         journal=args.journal,capture_dir=args.capture_dir)
    print(json.dumps(result,sort_keys=True))
    return 0
if __name__=="__main__":raise SystemExit(main())
