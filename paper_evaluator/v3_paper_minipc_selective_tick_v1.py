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
import argparse,hashlib,json,math,re
from datetime import datetime,timedelta,timezone
from pathlib import Path
from typing import Any,Callable
from contextlib import contextmanager
import os
from paper_evaluator import evaluate
from paper_evaluator.v3_paper_minipc_one_candidate_v1 import (
    REVISION,one_candidate,preflight_budget,_RELEASED_MODEL_NATIVE_OWNER,
)
from paper_evaluator.successor_coin_entry_evidence_v1 import fetch_public_entry_evidence
from paper_evaluator.v3_paper_minipc_closed_1m_capture_v1 import (
    capture_public_1m,assemble,early_path_coverage,
)
from paper_evaluator.v3_paper_minipc_followup_v1 import record_horizon
from paper_evaluator.v3_paper_missed_opportunity_followup_v1 import followup_no_buy
from paper_evaluator.v3_paper_wait_observer_v1 import (
    candidate_receipts,observe_wait,finish_wait,
)
from paper_evaluator.v3_experimental_paper_journal_v1 import (
    clock,make_receipt,store_receipt_explicitly,
)
from paper_evaluator.v3_extended_reentry_review_v1 import (
    extended_reentry_review,MAX_ORIGINAL_TO_LATER_REVIEW_SECONDS,
)
from paper_evaluator.v3_second_leg_policy_candidate_v1 import (
    witnessed_15m_from_existing_1m_path,propose_second_leg_review,
    canonical_second_leg_episode,prepare_original_owner_reentry_child,
)
from paper_evaluator.v3_paper_cloud_receipt_sync_v1 import (
    sync_once, _RELEASED_CLOUD_SYNC_NATIVE_OWNER,
)

def utc_now()->str:
    return datetime.now(timezone.utc).isoformat()

def _journal_extended_second_leg(*,candidate:dict[str,Any],series_id:str,
        journal:Path,rows:list[dict],p4:dict,coin:dict,quote:dict,
        assembled_1m:dict,now_at_utc:str)->dict[str,Any]:
    """One observed reentry on the EXISTING owner and immutable receipt path.

    Never authorizes a model call, Paper fill or trader action. Historical
    model/P4 decisions are not fresh trade signals. Only the new witnessed
    closed Kraken 5m candle can request a separately funded FULL review.
    """
    frame=(coin.get("frames") or {}).get("15") or {}
    closed=frame.get("last_closed_bar_end_utc")
    now=clock(now_at_utc)
    # Missing time => explicit technical UNKNOWN, not negative market vote.
    try:
        bar=clock(closed)
        if not clock(p4["known_at_utc"])<bar<=now:
            raise ValueError("no independently later bar")
        event_key="C"+bar.strftime("%Y%m%dT%H%M%SZ")
    except (ValueError,TypeError,KeyError,AttributeError):
        event_key="T"+now.strftime("%Y%m%dT%H%M%SZ")
        closed=None
    if any(r["phase"]=="FRESH_SECOND_LEG" and
           r["event_key"]==event_key for r in rows):
        return {"status":"EXTENDED_BAR_ALREADY_REVIEWED_NO_DUPLICATE",
                "model_calls":0,"paper_fills":0}
    safe_source=(coin.get("status")=="COMPLETE"
                 and coin.get("pair")==candidate["pair"]
                 and isinstance(quote,dict)
                 and isinstance(closed,str)
                 and (quote.get("pair") in (None,candidate["pair"])))
    review={"state":"UNKNOWN_NO_COMPLETE_PROSPECTIVE_KRAKEN_SOURCE"}
    policy={"status":"UNKNOWN_NO_WITNESSED_CLOSED_15M_BASE"}
    if safe_source:
        stage="PIT_CLOCK_REVIEW"
        try:
            # The earlier 5m proximity test is NOT proof of a 1-3h base.
            # Require the independently archived, time-witnessed 1m path,
            # then use the existing canonical P1 second-leg policy only.
            review=extended_reentry_review(
                candidate,{"setup_lane":"EXTENDED","decision":p4["result"],
                           "known_at_utc":p4["known_at_utc"]},
                coin,quote,decision_at_utc=now_at_utc)
            stage="PROSPECTIVE_1M_TO_15M_RECONSTRUCTION"
            bars=witnessed_15m_from_existing_1m_path(
                assembled_1m,pair=candidate["pair"],
                observed_at_utc=now_at_utc)
            stage="P1_SECOND_LEG_STRUCTURE_REVIEW"
            policy=propose_second_leg_review(
                candidate,{"setup_lane":"EXTENDED","decision":p4["result"]},
                coin,quote,bars,decision_at_utc=now_at_utc)
        except (OSError,KeyError,ValueError,TypeError,OverflowError) as exc:
            policy={"status":"UNKNOWN_PROSPECTIVE_15M_BASE_SOURCE_INVALID",
                    "technical_failure_stage":stage,
                    "technical_failure_class":type(exc).__name__}
    # A complete five-minute ticker is necessary but never sufficient.
    clock_safe=not review["state"].startswith("UNKNOWN")
    state=policy["status"] if clock_safe else review["state"]
    eligible=(clock_safe and
              policy.get("status")=="SECOND_LEG_STRUCTURE_SUPPORTS_NEW_FULL_REVIEW_ONLY"
              and policy.get("request_model_recheck_only") is True
              and closed is not None)
    missing=(state.startswith("UNKNOWN") or state.startswith("MISSING")
             or state in ("NONCONTIGUOUS_BASE_HISTORY",
                          "CANDLE_EVIDENCE_CLOCK_MISMATCH"))
    status=("PASS" if eligible else "UNKNOWN" if missing else "SKIP")
    episode={}
    if eligible:
        try:
            episode=canonical_second_leg_episode(
                series_id=series_id,original_candidate=candidate,
                closed_15m_end_utc=closed,
                signal_known_at_utc=now_at_utc)
        except (ValueError,TypeError,KeyError,OverflowError):
            eligible=False
            state="UNKNOWN_INVALID_PROSPECTIVE_EPISODE_CLOCK_OR_ID"
            status="UNKNOWN"
    rec=make_receipt(
        series_id=series_id,revision=REVISION,
        candidate_id=candidate["candidate_id"],pair=candidate["pair"],
        event_time_utc=candidate["event_time_utc"],
        known_at_utc=now_at_utc,phase="FRESH_SECOND_LEG",result=status,
        event_key=event_key,
        data={"review_family":"EXTENDED_PROSPECTIVE_15M_BASE_SECOND_LEG",
              "review_status":state,
              "review_checks":{"p1":policy.get("checks") or {},
                               "source_timing":review.get("checks") or {},
                               "closed_15m_base_source":"WITNESSED_PRIOR_1M_ONLY"},
              "source_status":coin.get("status") or "UNKNOWN",
              "phase_failure_stage":None if eligible else
                    "EXTENDED_REENTRY_SOURCE_OR_CONFIRMATION_INCOMPLETE",
              **episode})
    store_receipt_explicitly(journal,rec)
    handoff=None
    if eligible:
        # Re-read the persisted parent history in THIS existing owner
        # immediately, avoiding a second scheduler or a stale next-cycle
        # opportunity. This produces no model budget or Paper fill authority.
        try:
            handoff=prepare_original_owner_reentry_child(
                journal=journal,series_id=series_id,
                original_candidate=candidate,parent_event_key=event_key,
                now_at_utc=now_at_utc)
        except (OSError,KeyError,ValueError,TypeError,OverflowError):
            handoff={"status":"P1_CHILD_PARENT_PROVENANCE_HOLD_NO_MODEL",
                     "approval_to_call_model":False,"model_calls":0,
                     "orders":False}
    handoff_ready=bool(handoff and
        handoff.get("status")=="P1_CHILD_PREPARED_MODEL_AND_PAPER_STILL_GATED")
    return {"status":(
                "EXTENDED_CHILD_PREPARED_FOR_SEPARATE_GATED_MODEL_P4_NO_AUTH"
                if handoff_ready else
                "EXTENDED_P1_PARENT_CHILD_RECONCILIATION_HOLD_NO_AUTH"
                if eligible else state),
            **episode,
            "reentry_child_handoff":handoff,
            "technical_failure_stage":policy.get("technical_failure_stage"),
            "technical_failure_class":policy.get("technical_failure_class"),
            "full_model_review_candidate":eligible,
            "model_calls":0,"paper_fills":0,"orders":False,
            "requires_separate_model_budget":True,
            "new_paper_writer_started":False}


def tick_once(*,candidate:dict[str,Any],series_id:str,journal:Path,
              capture_dir:Path,clock_now:Callable[[],str]=utc_now,
              capture:Callable=capture_public_1m,
              fetch:Callable=fetch_public_entry_evidence,
              ticker:Callable=evaluate.kraken_ticker,
              _released_tick_capability:object=None)->dict[str,Any]:
    if not series_id.startswith("PAPER-V3-CANARY-"):
        if _released_tick_capability is not _RELEASED_TICK_AFTER_LIVE_CLOUD_LOCK:
            raise ValueError("non-CANARY V3 tick requires locked external active Paper readback")
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
    origin=next((r for r in rows if r["phase"] in (
        "SCANNER_CAPTURE","P1_CHILD_ENROLLMENT")),None)
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
    reentry_coin=None
    reentry_quote=None
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
                reentry_coin=coin
                # The existing Kraken public ticker client does not carry an
                # exchange observation timestamp. Its real local completion
                # time is known only AFTER the quote was acquired.
                reentry_quote=dict(q,observed_at_utc=(
                    q.get("observed_at_utc") or clock_now()))
                reentry_quote.setdefault("pair",pair)
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
    # Build verified archive ONCE for both original lifecycle and the later
    # P1 structural base. A new bar cannot be inferred from a late download.
    capture_path=assemble(snapshots=capture_dir,pair=pair,
        entry_at_utc=origin["event_time_utc"],observed_at_utc=clock_now(),
        max_live_capture_lag_minutes=15)
    # Existing original MODEL_RESPONSE is authoritative for setup lane.
    # Neither caller-created candidate.setup_lane nor keyword reason codes
    # are acceptable evidence that the original model decided EXTENDED.
    original_model=next((r for r in rows
        if r["phase"]=="MODEL_RESPONSE" and r["result"]=="PASS"),None)
    is_extended=bool(original_model and
        original_model["data"].get("raw_setup_lane")=="EXTENDED")
    age=(clock(clock_now())-source_time).total_seconds()
    if (p4 and p4["result"] in ("WAIT","REJECT") and is_extended
            and candidate.get("entry_origin","SCANNER")=="SCANNER"
            and original_model is not None
            and 0<=age<=MAX_ORIGINAL_TO_LATER_REVIEW_SECONDS):
        now_at_utc=clock_now()
        if reentry_coin is None:
            try:
                reentry_coin=fetch(altname,pair)
                raw_quote=ticker(altname)
                reentry_quote=dict(raw_quote,observed_at_utc=(
                    raw_quote.get("observed_at_utc") or clock_now()))
                reentry_quote.setdefault("pair",pair)
            except (OSError,ValueError,KeyError,TypeError) as exc:
                reentry_coin={"pair":pair,
                    "status":"UNKNOWN_KRAKEN_SECOND_LEG_SOURCE_"+type(exc).__name__.upper()}
                reentry_quote={}
        results["extended_reentry"]=_journal_extended_second_leg(
            candidate=candidate,series_id=series_id,journal=journal,
            rows=rows,p4=p4,coin=reentry_coin,quote=reentry_quote,
            assembled_1m=capture_path,now_at_utc=now_at_utc)
    # Shadow-only offensive CONTINUITY comparison on the EXISTING selective
    # tick: same witnessed 1m archive, same closed Kraken PIT, one ticker,
    # same clock and original model lane. Never mint a new candidate, model
    # approval, Paper fill or new scheduler from research eligibility.
    if (p4 and p4["result"] in ("WAIT","REJECT")
            and original_model is not None
            and original_model["data"].get("raw_setup_lane")=="CONTINUITY"
            and candidate.get("entry_origin","SCANNER")=="SCANNER"
            and 0<=(clock(clock_now())-source_time).total_seconds()<=900):
        try:
            from paper_evaluator.v3_p3_early_5m_continuity_research_v1 import (
                propose_early_5m_continuity_review,
            )
            from paper_evaluator.v3_experimental_continuity_volume_review_v1 import (
                propose_experimental_continuity_review,
            )
            from paper_evaluator.v3_continuity_fresh_review_candidate_v1 import (
                propose_continuity_fresh_review,
            )
            from paper_evaluator.v3_first_pit_presignal_15m_v1 import (
                read_first_pit_base,
            )
            observed=clock_now()
            # Check disk-only pre-signal source before any optional extra Kraken
            # entry/quote call. Missing history must be a zero-request hold.
            history_start=(source_time-timedelta(minutes=45)).isoformat()
            research_path=assemble(
                snapshots=capture_dir,pair=pair,
                entry_at_utc=history_start,observed_at_utc=observed,
                max_live_capture_lag_minutes=15)
            witnessed=witnessed_15m_from_existing_1m_path(
                research_path,pair=pair,observed_at_utc=observed)
            prior_closed=[bar for bar in witnessed
                          if clock(datetime.fromtimestamp(
                              bar["start_utc"]+900,timezone.utc).isoformat())
                          <=source_time]
            # The original P0 already fetched Kraken 15m candles BEFORE this
            # optional new 5m research read. Its immutable SOURCE_INPUT may
            # retain the actual two pre-signal OHLC bars with the FIRST
            # OBSERVATION clock. This is not a historical 1m witness.
            first_base=None
            if len(prior_closed)<2:
                first_source=next((r for r in rows
                    if r["phase"]=="SOURCE_INPUT" and r["result"]=="PASS"
                    and r["data"].get("initial_pit_15m_base") is not None),None)
                if first_source is not None:
                    first_base=read_first_pit_base(
                        candidate,first_source,decision_at_utc=observed)
                if first_base is not None:
                    prior_closed=first_base["bars"]
            if len(prior_closed)<2:
                results["continuity_offensive_shadow"]={
                    "status":"PRE_SIGNAL_15M_PROSPECTIVE_HISTORY_MISSING",
                    "pre_signal_closed_15m_witnessed":len(prior_closed),
                    "model_called":False,"model_http_attempts_reserved":0,
                    "paper_writer_started":False,"orders":False,
                    "real_money_actions":False,"release_evidence":False}
            else:
                if reentry_coin is None:
                    reentry_coin=fetch(altname,pair)
                    raw_quote=ticker(altname)
                    reentry_quote=dict(raw_quote,observed_at_utc=(
                        raw_quote.get("observed_at_utc") or clock_now()))
                    reentry_quote.setdefault("pair",pair)
                observed=clock_now()
                baseline={"setup_lane":"CONTINUITY","decision":p4["result"]}
                # Early-5m MUST see the two original pre-detection bars,
                # never the latest bars assembled after the candidate.
                # Standard/soft-volume retain the same complete witnessed
                # history as their own strategy contracts require.
                standard=propose_continuity_fresh_review(
                    candidate,baseline,reentry_coin,reentry_quote,witnessed,
                    decision_at_utc=observed)
                # A 5m confirmation that CLOSED before the original P0
                # was even observed cannot be a new post-P0 opportunity.
                # Require first-source knowledge at/before the newly closed
                # 5m candle, otherwise record an explicit no-review hold.
                fresh5=(reentry_coin.get("frames") or {}).get("5") or {}
                close5_at=fresh5.get("last_closed_bar_end_utc")
                if (first_base is not None and (
                        not isinstance(close5_at,str)
                        or clock(close5_at)<clock(first_base["first_known_at_utc"])
                        or clock(close5_at)<clock(p4["known_at_utc"]))):
                    early={"status":"ORIGINAL_PIT_OR_P4_KNOWN_AFTER_5M_CLOSE_NO_REVIEW",
                           "request_model_recheck_only":False}
                else:
                    early=propose_early_5m_continuity_review(
                        candidate,baseline,reentry_coin,reentry_quote,prior_closed,
                        decision_at_utc=observed)
                volume=propose_experimental_continuity_review(
                    candidate,baseline,reentry_coin,reentry_quote,witnessed,
                    decision_at_utc=observed)
                results["continuity_offensive_shadow"]={
                    "status":"SOURCE_CLOCKED_PIT_RESEARCH_ONLY",
                    "early_base_provenance":(
                        "ORIGINAL_P0_15M_FIRST_KNOWN_NOT_PRE_SIGNAL_WITNESS"
                        if first_base is not None else
                        "PROSPECTIVELY_SHA_WITNESSED_PRE_SIGNAL_1M"),
                    "early_base_first_known_at_utc":(
                        first_base["first_known_at_utc"] if first_base is not None
                        else None),
                    "standard_status":standard["status"],
                    "early_5m_status":early["status"],
                    "soft_volume_status":volume["status"],
                    "early_5m_review_only":early.get("request_model_recheck_only") is True,
                    "soft_volume_review_only":volume.get("request_model_recheck_only") is True,
                    "same_witnessed_archive":first_base is None,"model_called":False,
                    "model_http_attempts_reserved":0,"paper_writer_started":False,
                    "orders":False,"real_money_actions":False,
                    "release_evidence":False}
        except (OSError,ValueError,KeyError,TypeError,OverflowError,AttributeError) as exc:
            results["continuity_offensive_shadow"]={
                "status":"SOURCE_UNVERIFIED_RESEARCH_HOLD",
                "failure_class":type(exc).__name__,
                "model_called":False,"model_http_attempts_reserved":0,
                "paper_writer_started":False,"orders":False,
                "real_money_actions":False,"release_evidence":False}
    now=clock(clock_now())
    # The P1 child uses its new signal time for no-BUY opportunities, but a
    # positive Paper position starts each horizon at its ACTUAL durable fill.
    # Never mature a child position 6h after the original scanner clock.
    fills=[r for r in rows if r["phase"]=="PAPER_FILL" and
           r["result"]=="PAPER_FILLED"]
    horizon_start=clock(fills[0]["known_at_utc"]) if len(fills)==1 else source_time
    # The original model decision is final if no BUY: followup even SKIP/WAIT/
    # source-UNKNOWN cases, never reclassify ex-post MFE as earned trades.
    results["prospective_1m_bars"]=len(capture_path["closed_bars"])
    # Zero extra Kraken requests, receipts, or tasks: signal a missing
    # first minute while the event is still fresh instead of pretending
    # a later historic OHLC download was a live witnessed source path.
    results["early_1m_coverage"]=early_path_coverage(
        assembled=capture_path,entry_at_utc=origin["event_time_utc"],
        observed_at_utc=capture_path["captured_at_utc"])
    results["horizons"]={}
    buys=len(fills)==1
    if len(fills)>1:
        raise ValueError("multiple independent Paper fills on one child episode")
    for hrs in (6,24,72):
        if now<horizon_start+timedelta(hours=hrs):
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



# Identity-only accidental misuse fence, not an authentication secret.
# Only the existing post-CAS wrapper supplies this private sentinel while it
# owns the OS-native lock. Physical/Cloud release authority is EXTERNAL.
_RELEASED_TICK_AFTER_LIVE_CLOUD_LOCK=object()


def _require_released_paper_cloud(*,series_id:str,
        expected_repo_sha:str,expected_bundle_sha256:str,
        expected_strategy_sha256:str,
        read_active_series:Callable[[str],dict[str,Any]],
        clock_now:Callable[[],str])->None:
    """Shared source-only precondition; CALL ONLY from one native owner lock.

    A self-reported Cloud config is not independent physical proof of a
    Windows fence, signed six E2E proofs or actual deployment.
    """
    if (not isinstance(series_id,str)
            or re.fullmatch(r"PAPER-V3-[0-9]{8}T[0-9]{6}Z",series_id) is None
            or not all(isinstance(x,str) and re.fullmatch(pattern,x)
                       for x,pattern in (
                           (expected_repo_sha,r"[0-9a-f]{40}"),
                           (expected_bundle_sha256,r"[0-9a-f]{64}"),
                           (expected_strategy_sha256,r"[0-9a-f]{64}")))
            or not callable(read_active_series)):
        raise ValueError("exact release-pinned non-CANARY Paper identity required")

    original=read_active_series(series_id)
    if not isinstance(original,dict):
        raise ValueError("independent live Paper-series readback absent")
    try:
        observed=clock(original["observed_at_utc"])
        now=clock(clock_now())
        config=original["config"]
    except (KeyError,ValueError,TypeError,AttributeError) as exc:
        raise ValueError("invalid active Paper-series source/clock") from exc
    if (observed>now or (now-observed).total_seconds()>90
            or not isinstance(config,dict)
            or original.get("series_id")!=series_id
            or original.get("status")!="active"
            or original.get("strategy_revision")!=REVISION
            or config.get("series_id")!=series_id
            or config.get("strategy_revision")!=REVISION
            or config.get("release_repo_sha")!=expected_repo_sha
            or config.get("runtime_bundle_fingerprint_sha256")!=expected_bundle_sha256
            or config.get("strategy_fingerprint_sha256")!=expected_strategy_sha256
            or config.get("paper_only") is not True
            or config.get("real_money_actions_enabled") is not False
            or config.get("automatic_activation_allowed") is not False
            or config.get("physical_v2r4_writer_fence_verified") is not True
            or config.get("supervisor_old_intake_rearm_blocked") is not True
            or config.get("old_followup_owner_preserved") is not True
            or config.get("independent_six_e2e_proofs_verified") is not True):
        raise ValueError("non-CANARY Paper release source mismatch or stale")



def _verify_first_native_model_paper_journal(*,candidate:dict[str,Any],
        series_id:str,journal:Path,model_reservations:Path,
        approval:dict[str,Any])->dict[str,Any]:
    """Independent disk readback WHILE the existing native writer lock is held.

    A callback's successful P4 flag, test model, or synthetic receipt cannot
    prove a physical Paper deployment. This only verifies the already written
    local stage/model/P4/fill chain before the owner reports any local BUY.
    Cloud durability, real host pins and release proofs remain independent.
    """
    if (not isinstance(candidate,dict) or not isinstance(approval,dict)
            or not journal.is_dir() or journal.is_symlink()
            or not model_reservations.is_dir() or model_reservations.is_symlink()):
        raise ValueError("native paper audit roots or candidate absent")
    rows=[]
    for path in journal.glob("*.json"):
        if path.is_symlink() or not 0<path.stat().st_size<=16000:
            raise ValueError("noncanonical immutable V3 receipt file")
        raw=path.read_bytes()
        row=json.loads(raw)
        if (row.get("series_id"),row.get("candidate_id")) != (
                series_id,candidate["candidate_id"]):
            continue
        if (row.get("kind")!="V3_EXPERIMENTAL_PAPER_CANDIDATE_EVENT_V1"
                or row.get("revision")!=REVISION
                or row.get("pair")!=candidate["pair"]
                or clock(row["event_time_utc"])!=clock(candidate["event_time_utc"])
                or row.get("real_money_actions") is not False
                or row.get("orders") is not False):
            raise ValueError("foreign or altered Paper candidate lineage")
        digest=hashlib.sha256("|".join(str(row[k]) for k in
            ("series_id","candidate_id","phase","event_key")).encode()).hexdigest()
        if path.stem!=digest:
            raise ValueError("receipt disk name and event identity differ")
        rows.append((row,hashlib.sha256(raw).hexdigest()))
    if len({(r["phase"],r["event_key"]) for r,_ in rows})!=len(rows):
        raise ValueError("duplicate immutable event identity")
    child=candidate.get("entry_origin")=="P1_REENTRY_EPISODE"
    catalyst=candidate.get("entry_origin")=="VERIFIED_POSITIVE_SOURCE_CATALYST"
    key="FIRST" if child or catalyst else "FRESHRECHECK"
    def one(phase:str,receipt_key:str|None=None)->tuple[dict,str]:
        receipt_key=receipt_key or key
        found=[(row,sha) for row,sha in rows if
               row["phase"]==phase and row["event_key"]==receipt_key]
        if len(found)!=1:
            raise ValueError("missing or repeated original Paper phase: "+phase)
        return found[0]
    original,_=one("P1_CHILD_ENROLLMENT" if child else "SCANNER_CAPTURE","FIRST")
    if (original["result"]!="SEEN"
            or original["data"].get("candidate_origin")!=(
                "P1_REENTRY_EPISODE" if child else
                "VERIFIED_POSITIVE_SOURCE_CATALYST" if catalyst else "SCANNER")
            or (child and (
                original["data"].get("reentry_episode_id")!=candidate["candidate_id"]
                or original["data"].get("reentry_parent_candidate_id")!=
                    candidate.get("reentry_parent_candidate_id")
                or original["data"].get("reentry_episode_signal_at_utc")!=
                    candidate.get("event_time_utc")))):
        raise ValueError("unverified native Scanner or second-leg child original")
    if catalyst:
        source,_=one("SOURCE_CATALYST","FIRST")
        if (source["result"]!="PASS"
                or source["data"].get("positive_source_status")!=
                    "SOURCE_CATALYST_READY_FOR_FULL_MODEL_REVIEW_ONLY"
                or source["data"].get("positive_source_event_id")!=
                    candidate.get("positive_source_event_id")
                or source["data"].get("positive_source_name")!=
                    candidate.get("positive_source_name")):
            raise ValueError("positive original source provenance not journaled")
    if not child and not catalyst:
        one("FULL_REVIEW_ELIGIBILITY","FIRST")
    eligible,_=one("FULL_REVIEW_ELIGIBILITY")
    if eligible["result"]!="PASS":
        raise ValueError("full native model not review eligible")
    request,_=one("MODEL_REQUEST")
    response,_=one("MODEL_RESPONSE")
    p4,_=one("P4_VALIDATION")
    if (request["result"]!="PASS"
            or not isinstance(request["data"].get("input_fingerprint_sha256"),str)
            or not re.fullmatch("[0-9a-f]{64}",request["data"]["input_fingerprint_sha256"])
            or request["data"].get("model_http_attempts_reserved")!=1
            or response["result"]!="PASS"
            or not isinstance(response["data"].get("model_response_id"),str)
            or not response["data"]["model_response_id"]
            or not isinstance(response["data"].get("model_response_at_utc"),str)
            or p4["result"] not in ("BUY_SCOUT","WAIT","REJECT","UNKNOWN")
            or p4["data"].get("p4_decision")!=p4["result"]):
        raise ValueError("model budget, response or P4 original incomplete")
    reservations=[]
    for path in model_reservations.glob("*.reserved.json"):
        if path.is_symlink() or not 0<path.stat().st_size<=4096:
            raise ValueError("unverified native model reservation")
        item=json.loads(path.read_text("utf-8"))
        if (item.get("series_id"),item.get("candidate_id"))==(
                series_id,candidate["candidate_id"]):
            reservations.append(item)
    if (len(reservations)!=1
            or reservations[0].get("kind")!="V3_PAPER_MODEL_HTTP_RESERVED_BEFORE_NETWORK_V1"
            or reservations[0].get("unique_approval_id")!=approval.get("unique_approval_id")
            or reservations[0].get("no_automatic_retry") is not True):
        raise ValueError("missing or foreign one-shot model budget reservation")
    fills=[(row,sha) for row,sha in rows if row["phase"]=="PAPER_FILL"]
    if p4["result"]!="BUY_SCOUT":
        if fills:
            raise ValueError("non-BUY produced forbidden Paper fill")
        if p4["result"]=="WAIT":
            watch,_=one("WAIT_WATCH")
            if watch["result"]!="WAIT":
                raise ValueError("WAIT without actual watch phase")
        return {"p4_decision":p4["result"],
                "paper_entry_receipt_verified_local":False,
                "paper_entry_status":"NO_BUY_NO_PAPER_FILL_AS_EXPECTED",
                "paper_entry_receipt_sha256":None,
                "independent_cloud_paper_fill_ack":False}
    if (len(fills)!=1 or fills[0][0]["event_key"]!=key
            or fills[0][0]["result"]!="PAPER_FILLED"):
        raise ValueError("positive P4 without exact native Paper fill")
    fill,sha=fills[0]
    p=p4["data"];f=fill["data"]
    if (child or catalyst) and not (
            clock(candidate["event_time_utc"]) <= clock(p4["known_at_utc"])
            <= clock(fill["known_at_utc"])):
        raise ValueError("P1 Paper fill cannot predate new episode/P4")
    ask,stop,stage2=p.get("ask_eur"),p.get("validated_stop_eur"),p.get("validated_stage2_eur")
    if (p.get("p4_status")!="FULL_BUY_SCOUT_CONTRACT_VALIDATED_OFFLINE_NOT_RELEASE_EVIDENCE"
            or any(type(x) not in (int,float) or not math.isfinite(x)
                   for x in (ask,stop,stage2,f.get("paper_entry_ask_eur"),
                             f.get("paper_entry_qty"),f.get("paper_entry_fee_eur")))
            or not 0<stop<ask<stage2
            or not math.isclose(f["paper_entry_ask_eur"],ask,rel_tol=1e-7)
            or not math.isclose(f["paper_entry_qty"]*ask,50.0,rel_tol=1e-6,abs_tol=1e-5)
            or not math.isclose(f["paper_entry_fee_eur"],0.3,abs_tol=1e-8)
            or f.get("validated_stop_eur")!=stop
            or f.get("validated_stage2_eur")!=stage2
            or f.get("source_status")!="ASSUMED_VIRTUAL_PAPER_ASK_NOT_REAL_EXCHANGE_FILL"
            or type(f.get("stage2_ttl_minutes")) is not int
            or not 1<=f["stage2_ttl_minutes"]<=60
            or type(p.get("total_cost_pct")) not in (int,float)
            or p["total_cost_pct"]<1.2):
        raise ValueError("Paper 50 EUR scout/stop/stage2/fees contract mismatch")
    for hours in (6,24,72):
        follow,_=one(f"FOLLOWUP_{hours}H")
        if follow["result"]!="PENDING":
            raise ValueError("initial Paper entry missing pending future horizon")
    return {"p4_decision":"BUY_SCOUT",
            "paper_entry_receipt_verified_local":True,
            "paper_entry_status":"NATIVE_LOCAL_PAPER_SCOUT_DURABLE_PENDING_INDEPENDENT_CLOUD_ACK",
            "paper_entry_receipt_sha256":sha,
            "independent_cloud_paper_fill_ack":False}


def released_paper_first_scanner_model_once(*,preflight:dict[str,Any],
        candidate:dict[str,Any],series_id:str,journal:Path,
        capture_dir:Path,model_reservations:Path,
        expected_repo_sha:str,expected_bundle_sha256:str,
        expected_strategy_sha256:str,
        read_active_series:Callable[[str],dict[str,Any]],
        approval:dict[str,Any],model_key:str,
        clock_now:Callable[[],str]=utc_now,
        capture:Callable=capture_public_1m,
        acquire:Callable|None=None,model_client:Callable|None=None,
        existing_context:dict[str,Any]|None=None)->dict[str,Any]:
    """First *released* Scanner -> immutable PIT -> model/P4, one OS owner.

    Caller must independently establish the genuine mini-PC service identity
    and externally authorized model spend; CI-injected callbacks are NOT six
    physical E2E receipts or Cloud credentials. No Task, relay, CAS or orders.
    No automatic retry: any initial journal evidence blocks a repeated call.
    H5/H10/H11 independent positive-source entries require their separate
    signed OWNERAUTH path, not a forged Scanner label.
    """
    from paper_evaluator.v3_paper_intake_receipt_stage_v1 import (
        stage_and_witness_first_minute,
    )
    if (not isinstance(preflight,dict) or not isinstance(candidate,dict)
            or preflight.get("series_id")!=series_id
            or not isinstance(preflight.get("selected_candidates"),list)
            or preflight["selected_candidates"]!=[candidate]
            or candidate.get("entry_origin")!="SCANNER"
            or candidate.get("kind")!="CANONICAL_CANDIDATE_HANDOFF_V1"
            or candidate.get("action")!="REVIEW_ONLY_NOT_ORDER"
            or candidate.get("deferred_recheck") is True
            or not isinstance(preflight.get("ingress"),dict)
            or preflight["ingress"].get("capacity_deferred_originals")!=[]
            or len(preflight.get("prospective_first_1m_capture_enrollment",[]))!=1
            or len(preflight.get("review_preflights",[]))!=1
            or preflight["review_preflights"][0].get("candidate_id")!=candidate.get("candidate_id")
            or preflight["review_preflights"][0].get("eligible_for_full_model_review") is not True
            or preflight.get("paper_writer_active") is not False
            or preflight.get("model_http_authorized") is not False
            or not isinstance(model_key,str) or len(model_key)<20):
        raise ValueError("exact one original Scanner/PIT model candidate and permit required")
    # Budget must be genuinely new, individual, unexpired and <= exact fixed
    # spend cap. Reject BEFORE source/journal writes, not after network work.
    if not isinstance(approval,dict):
        raise ValueError("individual released model approval object required")
    preflight_budget(approval,series_id)
    if (not journal.is_dir() or journal.is_symlink()
            or not capture_dir.is_dir() or capture_dir.is_symlink()
            or not model_reservations.is_dir() or model_reservations.is_symlink()
            or len({journal.resolve(),capture_dir.resolve(),
                    model_reservations.resolve()})!=3):
        raise ValueError("separate preexisting V3 source/journal/reservation roots required")
    with _one_canary_owner(journal):
        _require_released_paper_cloud(
            series_id=series_id,expected_repo_sha=expected_repo_sha,
            expected_bundle_sha256=expected_bundle_sha256,
            expected_strategy_sha256=expected_strategy_sha256,
            read_active_series=read_active_series,clock_now=clock_now)
        if candidate_receipts(journal,series_id,candidate["candidate_id"]):
            return {"status":"FIRST_SCANNER_ALREADY_JOURNALED_NO_MODEL_RETRY",
                    "model_http_calls":0,"orders":False,
                    "paper_writer_active":False}
        enrollment=stage_and_witness_first_minute(
            preflight=preflight,journal_directory=journal,
            capture_directory=capture_dir,observed_at_utc=clock_now(),
            capture=capture)
        source=enrollment["enrollment"][0]
        # A not-yet-closed first minute is not a negative market finding.
        # Fresh original 1/5/15m P0 is separately re-acquired by one_candidate.
        result=one_candidate(
            candidate=candidate,series_id=series_id,
            local_receipts=journal,model_reservations=model_reservations,
            approval=approval,model_key=model_key,
            allow_model=True,admit_staged_scanner_one_approved_model=True,
            acquire=acquire,model_client=model_client,clock=clock_now,
            existing_context=existing_context,
            _released_model_capability=_RELEASED_MODEL_NATIVE_OWNER)
        proof={"paper_entry_receipt_verified_local":False,
               "paper_entry_status":"NO_VERIFIED_FINAL_P4_HOLD",
               "paper_entry_receipt_sha256":None,
               "independent_cloud_paper_fill_ack":False}
        if result.get("status")=="V3_CANARY_MODEL_P4_RECORDED_NO_PAPER_ACTIVATION":
            try:
                proof=_verify_first_native_model_paper_journal(
                    candidate=candidate,series_id=series_id,journal=journal,
                    model_reservations=model_reservations,approval=approval)
                if proof["p4_decision"]!=result.get("p4_decision"):
                    raise ValueError("worker result differs from immutable P4")
            except (OSError,ValueError,KeyError,TypeError,OverflowError):
                # The model's one-shot reservation remains spent even if a
                # local Paper fill crashed or the journal is malformed.
                # No model re-call, no inferred trade, no cloud ACK claim.
                return {"status":"FIRST_SCANNER_MODEL_OR_PAPER_LEDGER_INCOMPLETE_HOLD",
                        "series_id":series_id,"candidate_id":candidate["candidate_id"],
                        "model_result":result,"model_http_attempts_reserved":1,
                        "paper_entry_receipt_verified_local":False,
                        "independent_cloud_paper_fill_ack":False,
                        "requires_original_owner_reconciliation":True,
                        "paper_writer_active":False,"orders":False,
                        "real_money_actions":False,"v2r4_changed":False}
        return {
            "status":("FIRST_SCANNER_MODEL_P4_DURABLE_WAIT_FOR_FOLLOWUP"
                      if result.get("p4_decision") in
                         ("BUY_SCOUT","WAIT","REJECT","UNKNOWN")
                      else "FIRST_SCANNER_MODEL_OR_SOURCE_INCOMPLETE_HOLD"),
            "series_id":series_id,
            "candidate_id":candidate["candidate_id"],
            "model_result":result,
            "first_minute_witness_status":source["status"],
            "source_capture_calls":enrollment["source_capture_calls"],
            "model_http_attempts_reserved":result.get(
                "model_http_attempts_reserved",0),
            "cloud_ack_verified":False,"paper_writer_active":False,
            "orders":False,"real_money_actions":False,
            "new_schedules":0,"v2r4_changed":False,
            **proof,
        }



def released_paper_positive_catalyst_model_once(*,
        candidate:dict[str,Any],series_id:str,journal:Path,
        model_reservations:Path,expected_repo_sha:str,
        expected_bundle_sha256:str,expected_strategy_sha256:str,
        read_active_series:Callable[[str],dict[str,Any]],
        approval:dict[str,Any],model_key:str,
        existing_context:dict[str,Any],
        clock_now:Callable[[],str]=utc_now,
        acquire:Callable|None=None,model_client:Callable|None=None)->dict[str,Any]:
    """Existing locked V3 Paper owner: verified independent catalyst -> P4.

    This is NOT an autonomous positive-source poller or extra Paper writer.
    Caller must supply an original, authenticated source snapshot and a
    separate newly approved one-shot model budget. The six physical release
    gates and real protected-main SHA remain independent prerequisites.
    """
    from paper_evaluator.v3_paper_positive_source_entry_v1 import (
        assess_positive_source,make_source_candidate,ELIGIBLE as SOURCE_ELIGIBLE,
    )
    if (not isinstance(candidate,dict)
            or candidate.get("entry_origin")!="VERIFIED_POSITIVE_SOURCE_CATALYST"
            or candidate.get("kind")!="V3_POSITIVE_SOURCE_CANONICAL_PAPER_CANDIDATE_V1"
            or not isinstance(existing_context,dict)
            or not isinstance(model_key,str) or len(model_key)<20
            or not isinstance(approval,dict)):
        raise ValueError("canonical original positive source and separate model approval required")
    preflight_budget(approval,series_id)
    if (not journal.is_dir() or journal.is_symlink()
            or not model_reservations.is_dir() or model_reservations.is_symlink()
            or journal.resolve()==model_reservations.resolve()):
        raise ValueError("separate preexisting immutable V3 journal and model budget roots required")
    name=candidate.get("positive_source_name")
    snapshot=existing_context.get(name)
    now_at=clock_now()
    source=assess_positive_source(
        pair=candidate.get("pair"),source_name=name,snapshot=snapshot,
        decision_at_utc=now_at,
        market_move=existing_context.get("dynamic_move_radar"))
    if source["status"]!=SOURCE_ELIGIBLE:
        return {"status":"POSITIVE_SOURCE_NOT_CURRENT_NO_MODEL",
                "source_status":source["status"],"model_http_attempts_reserved":0,
                "orders":False,"real_money_actions":False}
    canonical=make_source_candidate(
        pair=candidate["pair"],kraken_altname=candidate["altname"],
        source_name=name,snapshot=snapshot,decision_at_utc=now_at,
        market_move=existing_context.get("dynamic_move_radar"))
    if canonical!=candidate:
        raise ValueError("positive event identity changed before original owner")
    with _one_canary_owner(journal):
        _require_released_paper_cloud(
            series_id=series_id,expected_repo_sha=expected_repo_sha,
            expected_bundle_sha256=expected_bundle_sha256,
            expected_strategy_sha256=expected_strategy_sha256,
            read_active_series=read_active_series,clock_now=clock_now)
        if candidate_receipts(journal,series_id,candidate["candidate_id"]):
            return {"status":"POSITIVE_SOURCE_ALREADY_JOURNALED_NO_MODEL_RETRY",
                    "model_http_attempts_reserved":0,"orders":False}
        result=one_candidate(
            candidate=candidate,series_id=series_id,
            local_receipts=journal,model_reservations=model_reservations,
            approval=approval,model_key=model_key,allow_model=True,
            existing_context=existing_context,acquire=acquire,
            model_client=model_client,clock=clock_now,
            _released_model_capability=_RELEASED_MODEL_NATIVE_OWNER)
        proof={"paper_entry_receipt_verified_local":False,
               "independent_cloud_paper_fill_ack":False}
        if result.get("status")=="V3_CANARY_MODEL_P4_RECORDED_NO_PAPER_ACTIVATION":
            try:
                proof=_verify_first_native_model_paper_journal(
                    candidate=candidate,series_id=series_id,journal=journal,
                    model_reservations=model_reservations,approval=approval)
                if proof["p4_decision"]!=result.get("p4_decision"):
                    raise ValueError("positive P4 differs from immutable original")
            except (OSError,ValueError,KeyError,TypeError,OverflowError):
                return {"status":"POSITIVE_SOURCE_MODEL_OR_LEDGER_INCOMPLETE_HOLD",
                        "model_result":result,"model_http_attempts_reserved":1,
                        "requires_original_owner_reconciliation":True,
                        "independent_cloud_paper_fill_ack":False,
                        "orders":False,"real_money_actions":False}
        return {"status":(
                    "POSITIVE_SOURCE_MODEL_P4_DURABLE_WAIT_FOR_FOLLOWUP"
                    if result.get("p4_decision") in
                    ("BUY_SCOUT","WAIT","REJECT","UNKNOWN")
                    else "POSITIVE_SOURCE_MODEL_OR_SOURCE_INCOMPLETE_HOLD"),
                "candidate_id":candidate["candidate_id"],"series_id":series_id,
                "model_result":result,
                "model_http_attempts_reserved":result.get(
                    "model_http_attempts_reserved",0),
                "cloud_ack_verified":False,"orders":False,
                "real_money_actions":False,"new_schedules":0,
                "v2r4_changed":False,**proof}


def released_paper_reentry_child_model_once(*,
        child:dict[str,Any],original_candidate:dict[str,Any],
        series_id:str,journal:Path,capture_dir:Path,
        model_reservations:Path,expected_repo_sha:str,
        expected_bundle_sha256:str,expected_strategy_sha256:str,
        read_active_series:Callable[[str],dict[str,Any]],
        approval:dict[str,Any],model_key:str,
        clock_now:Callable[[],str]=utc_now,
        acquire:Callable|None=None,model_client:Callable|None=None,
        existing_context:dict[str,Any]|None=None)->dict[str,Any]:
    """One original native-owner P1 child, same full model/P4/Paper writer.

    No activation, Cloud POST, new task, side process, Kraken order or retry.
    A real host must separately prove its Windows native OS owner and six
    release gates; this Python callback cannot certify physical identity.
    """
    if (not isinstance(child,dict)
            or child.get("entry_origin")!="P1_REENTRY_EPISODE"
            or child.get("action")!="REVIEW_ONLY_NOT_ORDER"
            or not isinstance(original_candidate,dict)
            or child.get("reentry_parent_candidate_id")!=
                original_candidate.get("candidate_id")
            or not isinstance(approval,dict)
            or not isinstance(model_key,str) or len(model_key)<20):
        raise ValueError("exact original P1 parent, child and one-shot budget required")
    # No spending, source GET or new journal entry before independent budget,
    # distinct directories and active Cloud release pin checks.
    preflight_budget(approval,series_id)
    if (not journal.is_dir() or journal.is_symlink()
            or not capture_dir.is_dir() or capture_dir.is_symlink()
            or not model_reservations.is_dir() or model_reservations.is_symlink()
            or len({journal.resolve(),capture_dir.resolve(),
                    model_reservations.resolve()})!=3):
        raise ValueError("separate original V3 journal/capture/budget roots required")
    with _one_canary_owner(journal):
        _require_released_paper_cloud(
            series_id=series_id,expected_repo_sha=expected_repo_sha,
            expected_bundle_sha256=expected_bundle_sha256,
            expected_strategy_sha256=expected_strategy_sha256,
            read_active_series=read_active_series,clock_now=clock_now)
        if candidate_receipts(journal,series_id,child["candidate_id"]):
            return {"status":"P1_CHILD_ALREADY_JOURNALED_NO_MODEL_RETRY",
                    "model_http_calls":0,"paper_entry_receipt_verified_local":False,
                    "orders":False,"real_money_actions":False,
                    "paper_writer_active":False}
        parent=prepare_original_owner_reentry_child(
            journal=journal,series_id=series_id,
            original_candidate=original_candidate,
            parent_event_key=child["reentry_parent_event_key"],
            now_at_utc=clock_now())
        if (parent.get("status")!="P1_CHILD_PREPARED_MODEL_AND_PAPER_STILL_GATED"
                or parent["child_candidate"]!=child):
            raise ValueError("P1 immutable parent/child handoff mismatch")
        # Reconstruct from ORIGINAL digest-verified witnessed 1m files,
        # never from a supplied historical OHLC or changed candidate clock.
        assembled=assemble(
            snapshots=capture_dir,pair=child["pair"],
            entry_at_utc=original_candidate["event_time_utc"],
            observed_at_utc=clock_now(),max_live_capture_lag_minutes=15)
        result=one_candidate(
            candidate=child,series_id=series_id,
            local_receipts=journal,model_reservations=model_reservations,
            approval=approval,model_key=model_key,allow_model=True,
            admit_reentry_child_one_approved_model=True,
            reentry_original_candidate=original_candidate,
            reentry_captured_1m=assembled,
            acquire=acquire,model_client=model_client,clock=clock_now,
            existing_context=existing_context,
            _released_model_capability=_RELEASED_MODEL_NATIVE_OWNER)
        proof={"paper_entry_receipt_verified_local":False,
               "paper_entry_status":"P1_MODEL_OR_SOURCE_NOT_COMPLETE_HOLD",
               "independent_cloud_paper_fill_ack":False}
        if result.get("status")=="V3_CANARY_MODEL_P4_RECORDED_NO_PAPER_ACTIVATION":
            try:
                proof=_verify_first_native_model_paper_journal(
                    candidate=child,series_id=series_id,journal=journal,
                    model_reservations=model_reservations,approval=approval)
                if proof["p4_decision"]!=result.get("p4_decision"):
                    raise ValueError("P1 P4 response not matching on-disk Paper")
            except (OSError,KeyError,ValueError,TypeError,OverflowError):
                return {"status":"P1_MODEL_OR_PAPER_LEDGER_INCOMPLETE_HOLD",
                        "candidate_id":child["candidate_id"],"series_id":series_id,
                        "model_http_attempts_reserved":1,
                        "requires_original_owner_reconciliation":True,
                        "paper_entry_receipt_verified_local":False,
                        "independent_cloud_paper_fill_ack":False,
                        "paper_writer_active":False,"orders":False,
                        "real_money_actions":False,"v2r4_changed":False}
        return {
            "status":("P1_CHILD_MODEL_P4_DURABLE_WAIT_FOR_FOLLOWUP"
                      if result.get("p4_decision") in (
                          "BUY_SCOUT","WAIT","REJECT","UNKNOWN")
                      else "P1_NEW_MARKET_SOURCE_NOT_VERIFIED_NO_MODEL"
                      if result.get("status")=="P1_NEW_MARKET_SOURCE_NOT_VERIFIED_NO_MODEL"
                      else "P1_CHILD_SOURCE_OR_MODEL_INCOMPLETE_HOLD"),
            "series_id":series_id,
            "candidate_id":child["candidate_id"],
            "reentry_parent_candidate_id":original_candidate["candidate_id"],
            "model_result":result,
            "model_http_attempts_reserved":result.get(
                "model_http_attempts_reserved",0),
            "paper_writer_active":False,"orders":False,
            "real_money_actions":False,"v2r4_changed":False,
            "cloud_ack_verified":False,"new_schedules":0,
            **proof,
        }


def released_paper_followup_tick_once(*,candidate:dict[str,Any],series_id:str,
        journal:Path,capture_dir:Path,model_reservations:Path,ack_file:Path,
        expected_repo_sha:str,expected_bundle_sha256:str,
        expected_strategy_sha256:str,
        read_active_series:Callable[[str],dict[str,Any]],
        clock_now:Callable[[],str]=utc_now,
        capture:Callable=capture_public_1m,
        fetch:Callable=fetch_public_entry_evidence,
        ticker:Callable=evaluate.kraken_ticker)->dict[str,Any]:
    """One *post-CAS* non-CANARY Paper followup using the SAME OS owner lock.

    The deploy-time owner must inject a trusted, fresh Supabase Cloud readback
    and physically verify that this exact SHA-pinned release owns the Windows
    Task, that old V2R4 intake is fenced, and that six E2E release proofs are
    authentic. A supplied callback alone cannot prove these facts. No CLI,
    daemon, scheduler, model, orders, Cloud POST or CAS is created here.

    Only previously immutable-journalled candidates with an actual MODEL/P4 and
    one valid O_EXCL HTTP reservation are eligible. Missing/ambiguous results
    stay on HOLD before any public Kraken request or journal mutation.
    """
    # Never permit a non-CANARY tick from the unguarded standalone CLI.
    with _one_canary_owner(journal):
        _require_released_paper_cloud(
            series_id=series_id,expected_repo_sha=expected_repo_sha,
            expected_bundle_sha256=expected_bundle_sha256,
            expected_strategy_sha256=expected_strategy_sha256,
            read_active_series=read_active_series,clock_now=clock_now)
        # Reuse the ORIGINAL strict restart/HTTP reservation + P4 + immutable
        # Cloud-ACK identity planner. No P4 after crash => NO source GET and
        # never classify a pending model as a final NO_BUY at 6h/24h/72h.
        resume=plan_canary_resume(
            candidate=candidate,series_id=series_id,journal=journal,
            model_reservations=model_reservations,ack_file=ack_file,
            _released_planner_capability=_RELEASED_TICK_AFTER_LIVE_CLOUD_LOCK)
        if resume.get("can_tick") is not True:
            return dict(resume,status="NONCANARY_FOLLOWUP_HOLD_"+resume["status"],
                        tick_called=False,source_capture_calls=0,
                        paper_writer_active=False,model_http_calls=0,
                        orders=False,real_money_actions=False)
        # Owner lock stays held THROUGH public source capture, journal and
        # outcome maturation. No concurrent second V3 followup can race.
        return tick_once(
            candidate=candidate,series_id=series_id,journal=journal,
            capture_dir=capture_dir,clock_now=clock_now,capture=capture,
            fetch=fetch,ticker=ticker,
            _released_tick_capability=_RELEASED_TICK_AFTER_LIVE_CLOUD_LOCK)



def released_paper_cloud_ack_once(*,series_id:str,journal:Path,ack_file:Path,
        token:str,expected_repo_sha:str,expected_bundle_sha256:str,
        expected_strategy_sha256:str,
        read_active_series:Callable[[str],dict[str,Any]],
        clock_now:Callable[[],str]=utc_now,
        cloud_post:Callable|None=None)->dict[str,Any]:
    """One released non-CANARY V3 Paper journal ACK through ONE native owner.

    This joins the original first-model and followup writer to the existing
    append-only Supabase relay, WITHOUT a new service/Task/monitor/schedule.
    The original caller must independently attest Windows Task/PID identity,
    native no-rearm old V2R4 intake, model budget and six physical/cloud
    release proofs. A faked Cloud callback cannot establish any of them.
    GitHub/CI invokes this only with stubbed Cloud transport, never live.
    """
    if (not isinstance(series_id,str)
            or re.fullmatch(r"PAPER-V3-[0-9]{8}T[0-9]{6}Z",series_id) is None
            or not isinstance(token,str) or not 24<=len(token)<=512
            or not isinstance(journal,Path) or not journal.is_dir()
            or journal.is_symlink()
            or not isinstance(ack_file,Path)
            or ack_file.is_symlink() or ack_file.parent.is_symlink()
            or not ack_file.parent.is_dir()
            or ack_file.parent.resolve()==journal.resolve()):
        raise ValueError("isolated native V3 Paper journal/ACK and relay credential required")
    # The SAME native lock as released Scanner/P4 and 6/24/72h followup,
    # including while authenticating Cloud and writing the Cloud ACK.
    with _one_canary_owner(journal):
        _require_released_paper_cloud(
            series_id=series_id,expected_repo_sha=expected_repo_sha,
            expected_bundle_sha256=expected_bundle_sha256,
            expected_strategy_sha256=expected_strategy_sha256,
            read_active_series=read_active_series,clock_now=clock_now)
        outcome=sync_once(
            journal=journal,series_id=series_id,ack_file=ack_file,
            token=token,post=cloud_post,
            _released_cloud_sync_capability=_RELEASED_CLOUD_SYNC_NATIVE_OWNER)
        return dict(outcome,
                    series_id=series_id,
                    cloud_cas_performed=False,
                    original_v2r4_changed=False,
                    paper_writer_active=False,
                    model_http_calls=0,
                    orders=False,real_money_actions=False,
                    technical_release_proofs_credited=0)




@contextmanager
def _one_canary_owner(journal:Path):
    if not journal.is_dir() or journal.is_symlink():
        raise ValueError("existing isolated CANARY journal required")
    lock_path=journal/".v3-existing-owner-cycle.lock"
    if lock_path.is_symlink():
        raise ValueError("owner lock must not be a symlink")
    fd=os.open(lock_path,os.O_CREAT|os.O_RDWR,0o600)
    locked=False
    try:
        if os.fstat(fd).st_size==0:
            os.write(fd,b"\0")
        os.lseek(fd,0,os.SEEK_SET)
        try:
            if os.name=="nt":
                import msvcrt
                msvcrt.locking(fd,msvcrt.LK_NBLCK,1)
            elif os.name=="posix":
                import fcntl
                fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            else:
                raise ValueError("unsupported Mini-PC OS owner fence")
            locked=True
        except (OSError,BlockingIOError) as exc:
            raise ValueError("ANOTHER_CANARY_OWNER_RUNNING_FAIL_CLOSED") from exc
        yield
    finally:
        if locked:
            os.lseek(fd,0,os.SEEK_SET)
            if os.name=="nt":
                msvcrt.locking(fd,msvcrt.LK_UNLCK,1)
            else:
                fcntl.flock(fd,fcntl.LOCK_UN)
        os.close(fd)

def first_enrolled_canary_tick_once(*, preflight:dict[str,Any],
                                    candidate:dict[str,Any],series_id:str,
                                    journal:Path,capture_dir:Path,
                                    clock_now:Callable[[],str],
                                    capture:Callable,
                                    fetch:Callable=fetch_public_entry_evidence,
                                    ticker:Callable=evaluate.kraken_ticker)->dict[str,Any]:
    """Serialize original intake + Kraken first witness + first tick.

    Use the SAME OS-native lock as CANARY restart/Cloud reconciliation;
    no second owner, parallel first fetch or duplicate immutable stage.
    This remains CANARY-only and is not a Paper release or Task.
    """
    if (not isinstance(series_id,str)
            or not series_id.startswith("PAPER-V3-CANARY-")
            or not isinstance(preflight,dict)
            or preflight.get("series_id")!=series_id
            or not callable(capture) or not callable(clock_now)):
        raise ValueError("isolated CANARY first-cycle owner only")
    with _one_canary_owner(journal):
        return _first_enrolled_canary_tick_once_unlocked(
            preflight=preflight,candidate=candidate,series_id=series_id,
            journal=journal,capture_dir=capture_dir,clock_now=clock_now,
            capture=capture,fetch=fetch,ticker=ticker)


def _first_enrolled_canary_tick_once_unlocked(*, preflight:dict[str,Any],
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
    # Only a genuinely witnessed ORIGINAL first closed minute may drive the
    # source-reuse observation. If Kraken returned other (earlier) closed
    # bars, the collector correctly records a missing first minute; treating
    # that missing response as an invented successful capture in tick_once
    # would conceal the source gap and permit unearned 6/24h conclusions.
    good=("FIRST_CLOSED_MINUTE_WITNESSED_RESEARCH_ONLY",
          "FIRST_MINUTE_ALREADY_ARCHIVED_NO_DUPLICATE_GET")
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



def plan_canary_resume(*,candidate:dict[str,Any],series_id:str,
                       journal:Path,model_reservations:Path,
                       ack_file:Path,
                       _released_planner_capability:object=None)->dict[str,Any]:
    """Read-only journal/reservation/ACK restart gate, never a model replay.

    An HTTP reservation may have spent money even with no model response.
    The response/P4 must be durably journalled before any selective source
    continuation. Do not infer a successful P4 from a partial model response.
    """
    import hashlib
    from paper_evaluator.v3_paper_cloud_receipt_sync_v1 import REVISION

    is_canary=(isinstance(series_id,str) and series_id.startswith("PAPER-V3-CANARY-"))
    is_released=(isinstance(series_id,str)
                 and re.fullmatch(r"PAPER-V3-[0-9]{8}T[0-9]{6}Z",series_id)
                 and _released_planner_capability is _RELEASED_TICK_AFTER_LIVE_CLOUD_LOCK)
    if (not (is_canary or is_released)
            or not isinstance(candidate,dict)
            or not isinstance(candidate.get("candidate_id"),str)
            or not isinstance(candidate.get("pair"),str)
            or not candidate["pair"].endswith("/EUR")
            or not isinstance(candidate.get("altname"),str)
            or not candidate["altname"].isalnum()):
        raise ValueError("CANARY-only original Scanner source required")
    roots=(journal,model_reservations,ack_file.parent)
    if any(not p.is_dir() or p.is_symlink() for p in roots):
        raise ValueError("existing independent owner roots required")
    if ack_file.is_symlink():
        raise ValueError("ACK identity cannot be symlink")
    if ack_file.exists():
        state=json.loads(ack_file.read_text("utf-8"))
        if (not isinstance(state,dict)
                or state.get("series_id")!=series_id
                or state.get("revision")!=REVISION
                or not isinstance(state.get("acked"),list)):
            raise ValueError("foreign or invalid cloud ACK identity")
    rows=[]
    for p in journal.glob("*.json"):
        if p.is_symlink() or p.stat().st_size>16000:
            raise ValueError("unverified immutable receipt path")
        row=json.loads(p.read_text("utf-8"))
        if (row.get("series_id"),row.get("candidate_id"))!=(
                series_id,candidate["candidate_id"]):
            continue
        if (row.get("revision")!=REVISION
                or row.get("kind")!="V3_EXPERIMENTAL_PAPER_CANDIDATE_EVENT_V1"
                or row.get("orders") is not False
                or row.get("real_money_actions") is not False
                or row.get("pair")!=candidate["pair"]
                or clock(row["event_time_utc"])!=clock(candidate["event_time_utc"])):
            raise ValueError("foreign/altered candidate original")
        eid=hashlib.sha256("|".join(str(row[x]) for x in
            ("series_id","candidate_id","phase","event_key")).encode()).hexdigest()
        if p.stem!=eid:
            raise ValueError("local journal filename is not canonical")
        rows.append(row)
    # A reservation without a journalled result is ambiguous after a crash.
    reserved=[]
    for p in model_reservations.glob("*.reserved.json"):
        if p.is_symlink() or p.stat().st_size>4096:
            raise ValueError("invalid model reservation")
        item=json.loads(p.read_text("utf-8"))
        if (item.get("series_id"),item.get("candidate_id"))==(
                series_id,candidate["candidate_id"]):
            if (item.get("kind")!="V3_PAPER_MODEL_HTTP_RESERVED_BEFORE_NETWORK_V1"
                    or item.get("no_automatic_retry") is not True):
                raise ValueError("model reservation provenance conflict")
            reserved.append(item)
    result={"kind":"V3_EXISTING_CANARY_RESTART_DISPOSITION_V1",
            "series_id":series_id,"candidate_id":candidate["candidate_id"],
            "paper_writer_active":False,"model_http_authorized":False,
            "model_http_calls":0,"orders":False,"real_money_actions":False,
            "cloud_ack_verified":False,"can_tick":False,"new_schedules":0}
    def block(status:str)->dict[str,Any]:
        return dict(result,status=status)
    if not rows:
        return block("NO_IMMUTABLE_ORIGINAL_NO_AUTOMATIC_RESTART")
    entries={(r["phase"],r["event_key"]) for r in rows}
    if len(entries)!=len(rows):
        raise ValueError("duplicate event identities")
    child=candidate.get("entry_origin")=="P1_REENTRY_EPISODE"
    origin_phase="P1_CHILD_ENROLLMENT" if child else "SCANNER_CAPTURE"
    origin_name="P1_REENTRY_EPISODE" if child else "SCANNER"
    origins=[r for r in rows if r["phase"]==origin_phase
             and r["result"]=="SEEN"
             and r["data"].get("candidate_origin")==origin_name]
    if len(origins)!=1 or origins[0]["event_key"]!="FIRST":
        return block("ORIGINAL_SCANNER_OR_CHILD_NOT_EXACT_NO_AUTOMATIC_RESTART")
    if child:
        d=origins[0]["data"]
        if (d.get("reentry_episode_id")!=candidate["candidate_id"]
                or d.get("reentry_parent_candidate_id")!=
                    candidate.get("reentry_parent_candidate_id")
                or d.get("reentry_episode_signal_at_utc")!=candidate["event_time_utc"]
                or d.get("reentry_original_event_time_utc")!=
                    candidate.get("reentry_original_event_time_utc")
                or d.get("reentry_parent_event_key")!=
                    candidate.get("reentry_parent_event_key")):
            return block("CHILD_EPISODE_PARENT_LINEAGE_QUARANTINE")
        # Re-validate parent PASS even after a Windows power failure.
        # An isolated new Paper child receipt is not sufficient authority
        # for a followup without its original, source-clock-bound P1 basis.
        parent=[]
        for path in journal.glob("*.json"):
            obj=json.loads(path.read_text("utf-8"))
            if (obj.get("series_id"),obj.get("candidate_id"))!=(
                    series_id,candidate.get("reentry_parent_candidate_id")):
                continue
            eid=hashlib.sha256("|".join(str(obj[k]) for k in
                ("series_id","candidate_id","phase","event_key")).encode()).hexdigest()
            if (path.is_symlink() or path.stem!=eid or
                    obj.get("kind")!="V3_EXPERIMENTAL_PAPER_CANDIDATE_EVENT_V1"
                    or obj.get("revision")!=REVISION or obj.get("orders") is not False
                    or obj.get("real_money_actions") is not False):
                return block("P1_PARENT_RECEIPT_INTEGRITY_QUARANTINE")
            parent.append(obj)
        from paper_evaluator.v3_full_entry_decision_candidate_v1 import SECOND_LEG_P1_CHECKS
        p1=[r for r in parent if r["phase"]=="FRESH_SECOND_LEG"
            and r["result"]=="PASS"
            and r["event_key"]==candidate.get("reentry_parent_event_key")]
        scan=[r for r in parent if r["phase"]=="SCANNER_CAPTURE" and r["result"]=="SEEN"]
        model=[r for r in parent if r["phase"]=="MODEL_RESPONSE" and r["result"]=="PASS"]
        old_p4=[r for r in parent if r["phase"]=="P4_VALIDATION"
                and r["result"] in ("WAIT","REJECT")]
        if (len(p1)!=1 or len(scan)!=1 or len(model)!=1 or len(old_p4)!=1
                or model[0]["data"].get("raw_setup_lane")!="EXTENDED"
                or clock(scan[0]["event_time_utc"])!=clock(
                    candidate["reentry_original_event_time_utc"])
                or any(r["phase"]=="PAPER_FILL" for r in parent)
                or p1[0]["data"].get("reentry_episode_id")!=candidate["candidate_id"]
                or clock(p1[0]["known_at_utc"])!=clock(candidate["event_time_utc"])
                or set((p1[0]["data"].get("review_checks") or {}).get("p1",{}))
                    !=SECOND_LEG_P1_CHECKS
                or any(v is not True for v in
                    (p1[0]["data"].get("review_checks") or {}).get("p1",{}).values())):
            return block("P1_PARENT_OR_BASIS_NOT_PROVEN_AFTER_RESTART")
    phases=lambda name:[r for r in rows if r["phase"]==name]
    requests=phases("MODEL_REQUEST")
    responses=phases("MODEL_RESPONSE")
    p4s=phases("P4_VALIDATION")
    errors=phases("MODEL_ERROR")
    if (len(requests)>1 or len(responses)>1 or len(p4s)>1
            or len(errors)>1 or len(reserved)>1):
        return block("CONFLICTING_MODEL_HISTORY_QUARANTINE")
    if errors or (reserved and not responses) or (
            requests and requests[0]["result"]=="PASS" and not responses):
        return block("MODEL_MAY_HAVE_SPENT_NO_RETRY_QUARANTINE")
    if responses and not p4s:
        return block("MODEL_RESPONSE_WITHOUT_FINAL_P4_QUARANTINE")
    if not p4s:
        return block("MODEL_NOT_FINAL_NO_AUTOMATIC_SPEND_OR_FOLLOWUP")
    p4=p4s[0]
    if (not requests or requests[0]["result"]!="PASS"
            or not responses or responses[0]["result"]!="PASS"
            or not reserved):
        return block("UNVERIFIED_MODEL_P4_PROVENANCE_QUARANTINE")
    if p4["result"]=="WAIT" and not any(r["phase"]=="WAIT_WATCH"
                                            and r["result"]=="WAIT" for r in rows):
        return block("WAIT_WITHOUT_WATCH_CONTRACT_QUARANTINE")
    if p4["result"]=="BUY_SCOUT" and not any(
            r["phase"]=="PAPER_FILL" and r["result"]=="PAPER_FILLED" for r in rows):
        return block("BUY_WITHOUT_DURABLE_PAPER_FILL_QUARANTINE")
    if p4["result"] not in ("WAIT","REJECT","BUY_SCOUT","UNKNOWN"):
        return block("UNKNOWN_P4_RESULT_QUARANTINE")
    finals={r["phase"] for r in rows if r["phase"] in (
        "FOLLOWUP_6H","FOLLOWUP_24H","FOLLOWUP_72H")
        and r["result"] in ("MATURE_COMPLETE","CENSORED")}
    if len(finals)==3:
        return block("ALL_FOLLOWUPS_FINAL_NO_NEW_SOURCE")
    return dict(result,status="FOLLOWUP_ONLY_SAFE_FOR_EXISTING_CANARY_TICK",
                can_tick=True)


def resume_canary_tick_once(*,candidate:dict[str,Any],series_id:str,
                            journal:Path,capture_dir:Path,
                            model_reservations:Path,ack_file:Path,
                            clock_now:Callable[[],str]=utc_now,
                            capture:Callable=capture_public_1m,
                            fetch:Callable=fetch_public_entry_evidence,
                            ticker:Callable=evaluate.kraken_ticker,
                            relay_token:str|None=None,
                            cloud_post:Callable|None=None,
                            cloud_sync_only:bool=False)->dict[str,Any]:
    """Single process-locked CANARY restart with optional injected Cloud ACK.

    The caller MUST inject a Cloud transport explicitly. There is NO default
    Supabase network request from this research-only helper; an uncertain
    Cloud result is never treated as a physical release proof.

    Never evict a live or suspicious lock or restart the old Paper runtime.
    OS process lock releases on crash; persistent immutable receipts and
    model reservation remain authoritative for the next attempt.
    """
    from paper_evaluator.v3_paper_cloud_receipt_sync_v1 import sync_once

    if (cloud_post is None) != (relay_token is None):
        raise ValueError("Cloud source-only callback/token must be explicitly paired")
    if cloud_post is not None and (
            not callable(cloud_post) or not isinstance(relay_token,str)
            or len(relay_token)<24):
        raise ValueError("explicit source-only Cloud transport/token required")
    if cloud_sync_only and cloud_post is None:
        raise ValueError("Cloud-only recovery requires explicit injected transport")

    with _one_canary_owner(journal):
        disposition=plan_canary_resume(
            candidate=candidate,series_id=series_id,journal=journal,
            model_reservations=model_reservations,ack_file=ack_file)
        # Cloud-only replay is useful after source/P4/followup journal
        # durability but before ACK. Never refetch Kraken or the model.
        # If every horizon is final, the final original receipts may still
        # be pending Cloud ACK. Ambiguous model/P4 states remain quarantined.
        if cloud_sync_only:
            if (not disposition["can_tick"] and disposition["status"]!=
                    "ALL_FOLLOWUPS_FINAL_NO_NEW_SOURCE"):
                return dict(disposition,tick_called=False,
                            cloud_post_accepted=False,
                            source_capture_calls=0)
            cloud=sync_once(journal=journal,series_id=series_id,
                            ack_file=ack_file,token=relay_token,
                            post=cloud_post)
            return dict(disposition,
                        status="CANARY_CLOUD_ONLY_RECONCILED_NO_SOURCE_OR_MODEL",
                        tick_called=False,source_capture_calls=0,
                        cloud_status=cloud["status"],
                        cloud_post_accepted=(cloud["status"]==
                                             "V3_RECEIPTS_CLOUD_ACK_VERIFIED"),
                        cloud_receipts_accepted=cloud["count"],
                        cloud_ack_verified=False,
                        full_physical_cloud_release_proof=False)
        if not disposition["can_tick"]:
            return dict(disposition,tick_called=False,
                        source_capture_calls=0)
        tick=tick_once(candidate=candidate,series_id=series_id,
                       journal=journal,capture_dir=capture_dir,
                       clock_now=clock_now,capture=capture,
                       fetch=fetch,ticker=ticker)
        cloud=(sync_once(journal=journal,series_id=series_id,
                         ack_file=ack_file,token=relay_token,post=cloud_post)
               if cloud_post is not None else None)
        return dict(disposition,status="SAFE_CANARY_FOLLOWUP_TICK_EXECUTED",
                    tick_called=True,tick=tick,
                    cloud_status=cloud["status"] if cloud else "NOT_REQUESTED",
                    cloud_post_accepted=bool(cloud and cloud["status"]==
                                           "V3_RECEIPTS_CLOUD_ACK_VERIFIED"),
                    cloud_receipts_accepted=cloud["count"] if cloud else 0,
                    cloud_ack_verified=False,full_physical_cloud_release_proof=False,
                    model_http_calls=0)

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
