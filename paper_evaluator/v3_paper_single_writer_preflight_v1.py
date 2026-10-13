"""One future V3 PAPER single-writer *preflight* seam, not the writer.

Combines EXISTING immutable scanner originals, authenticated owner-supplied
positive events (H5 official news, H10 proven fills, H11 true coin-positive
event), and the existing V3 fresh-PIT/ATR/stop/ask review gate.
No program in this module collects prices or source news, schedules tasks,
spends a model budget, writes a receipt or starts a PAPER trading series.
The actual single writer must separately hold a user-approved budget, call
the real Kraken consumer/model/P4 and journal before cloud sync.
"""
from __future__ import annotations
from datetime import timedelta
from typing import Any
from paper_evaluator.v3_paper_existing_owner_source_bridge_v1 import join_owner_sources
from paper_evaluator.v3_paper_positive_source_entry_v1 import utc
from paper_evaluator.v3_paper_shared_candidate_intake_plan_v1 import plan_intake
from paper_evaluator.v3_experimental_paper_initial_review_v1 import (
    propose_initial_full_review, ELIGIBLE,
)

KIND="V3_FUTURE_SINGLE_PAPER_WRITER_PRE_FLIGHT_PLAN_V1"

def plan_writer_preflight(*,scanner_events:list[dict[str,Any]],
        owner_event_packets:list[dict[str,Any]],
        h10_context:dict[str,Any]|None,
        h11_market_capture:dict[str,Any]|None,
        h5_macro_calendar:dict[str,Any]|None,
        authenticated_owner_ids:dict[str,list[str]],
        journal_receipts:list[dict[str,Any]],
        known_pairs:dict[str,dict[str,Any]],
        market_observations:dict[str,dict[str,Any]],
        series_id:str,decision_at_utc:str,max_reviews:int=3,
        trusted_owner_hmac_keys:dict[str,dict[str,bytes]]|None=None)->dict[str,Any]:
    if not isinstance(market_observations,dict):
        raise ValueError("bounded exact Kraken market observation mapping required")
    source=join_owner_sources(
        h10_context=h10_context,h11_market_capture=h11_market_capture,
        h5_macro_calendar=h5_macro_calendar,
        owner_event_packets=owner_event_packets,
        authenticated_owner_ids=authenticated_owner_ids,
        decision_at_utc=decision_at_utc,
        trusted_owner_hmac_keys=trusted_owner_hmac_keys)
    intake=plan_intake(
        scanner_events=scanner_events,
        source_events=source["owner_source_events"],
        known_pairs=known_pairs,journal_receipts=journal_receipts,
        series_id=series_id,decision_at_utc=decision_at_utc,
        max_reviews=max_reviews)
    # Source-owner packets denied BEFORE the shared router are original
    # inputs too. Preserve their identities safely in the SAME immutable
    # research journal, never silently collapse them to aggregate counts.
    owner_rejects=source["source_event_rejected_originals"]
    if sum(source["source_event_rejections"].values())!=len(owner_rejects):
        raise ValueError("owner rejection individual audit accounting mismatch")
    counts=dict(intake["counts"])
    counts["suppressed_or_deferred"]+=len(owner_rejects)
    reasons=dict(intake["dispositions"])
    for key,num in source["source_event_rejections"].items():
        reasons[key]=reasons.get(key,0)+num
    # Prospective path enrollment must begin promptly with the ORIGINAL
    # candidate clock; a healthy future 5m observer is not evidence that the
    # first post-event closed minute was actually witnessed within 15 min.
    # This is a pure deadline plan for the SAME eventual single writer.
    at=utc(decision_at_utc)
    capture_enrollment=[]
    for status,rows in (
            ("SELECTED_FOR_MODEL_REVIEW",intake["candidates"]),
            ("CAPACITY_DEFERRED_NEEDS_OWNER_RETRY",intake["capacity_deferred_originals"])):
        for item in rows:
            original=utc(item["event_time_utc"])
            first=original.replace(second=0,microsecond=0)
            if first<original:
                first+=timedelta(minutes=1)
            first_close=first+timedelta(minutes=1)
            last_witness=first_close+timedelta(minutes=15)
            capture_enrollment.append({
                "candidate_id":item["candidate_id"],"pair":item["pair"],
                "ingress_disposition":status,
                "original_at_utc":original.isoformat(),
                "first_expected_closed_1m_start_utc":first.isoformat(),
                "latest_first_bar_live_witness_utc":last_witness.isoformat(),
                "new_capture_window_still_open_as_of_preflight":at<=last_witness,
                "first_bar_physically_witnessed_by_this_preflight":False,
                "new_kraken_requests":0,
            })
    # Urgency is for data preservation only. Keep the authorized intake/model
    # ranking intact; an early SOURCE monitor is never an independent BUY.
    capture_enrollment.sort(
        key=lambda r:(r["latest_first_bar_live_witness_utc"],
                      r["candidate_id"]))
    decisions=[]
    for c in intake["candidates"]:
        snap=market_observations.get(c["pair"])
        if not isinstance(snap,dict):
            decisions.append({
                "candidate_id":c["candidate_id"],"pair":c["pair"],
                "origin":c.get("entry_origin"),
                "status":"UNKNOWN_NO_FRESH_COIN_KRAKEN_CONSUMER_INPUT",
                "model_review_authorized":False})
            continue
        quote,frame,metadata=(snap.get(k) for k in
                              ("ticker","entry_evidence","pair_metadata"))
        if not all(isinstance(x,dict) for x in (quote,frame,metadata)):
            decisions.append({
                "candidate_id":c["candidate_id"],"pair":c["pair"],
                "origin":c.get("entry_origin"),
                "status":"UNKNOWN_PARTIAL_COIN_KRAKEN_PROVENANCE",
                "model_review_authorized":False})
            continue
        review=propose_initial_full_review(
            c,frame,quote,metadata,decision_at_utc=decision_at_utc)
        decisions.append({
            "candidate_id":c["candidate_id"],"pair":c["pair"],
            "origin":c.get("entry_origin"),
            "review_family":("SOURCE_CATALYST_INDEPENDENT"
                         if c.get("entry_origin")=="VERIFIED_POSITIVE_SOURCE_CATALYST"
                         else "FIRST_SCANNER_EARLY_REVIEW"),
            "status":review["status"],
            "checks":review.get("checks",{}),
            "eligible_for_full_model_review":review["status"]==ELIGIBLE,
            "model_review_authorized":False,
            "paper_buy_authorized":False})
    return {
        "kind":KIND,"series_id":series_id,"at_utc":decision_at_utc,
        "status":"REAL_PIT_REVIEW_ELIGIBLE_BUT_MODEL_SPEND_UNAUTHORIZED"
                 if any(x.get("eligible_for_full_model_review") for x in decisions)
                 else "NO_COMPLETE_PIT_MODEL_REVIEW_ELIGIBILITY",
        "source_provenance":source,
        "ingress":{"status":intake["status"],
                   "counts":counts,
                   "dispositions":reasons,
                   "owner_pre_router_rejection_count":len(owner_rejects),
                   "capacity_deferred_originals":intake["capacity_deferred_originals"],
                   "same_pair_coalesced_originals":intake["same_pair_coalesced_originals"],
                   "rejected_originals":intake["rejected_originals"]+owner_rejects,
                   "rejected_originals_audit_only_no_model_authority":True,
                   "overflow_requires_durable_owner_queue_before_runtime":intake["overflow_requires_durable_owner_queue_before_runtime"],
                   "rejected_originals_not_yet_journaled":True},
        "selected_candidates":intake["candidates"],
        "prospective_first_1m_capture_enrollment":capture_enrollment,
        "capture_enrollment_is_deadline_plan_not_live_proof":True,
        "capacity_deferred_origins_need_durable_same_owner_retry":bool(
            intake["capacity_deferred_originals"]),
        "review_preflights":decisions,
        "real_consumer_requires_separate_actual_kraken_and_p4_recheck":True,
        "independently_authenticated_source_owner_runtime_proven":False,
        "model_http_authorized":False,"model_calls":0,
        "paper_writer_active":False,"paper_buy_authorized":False,
        "orders":False,"real_money_actions":False,
        "old_v2r4_intake_stopped":False,"cloud_active_series_changed":False,
        "new_schedules":0,"v2r4_changed":False,
    }
