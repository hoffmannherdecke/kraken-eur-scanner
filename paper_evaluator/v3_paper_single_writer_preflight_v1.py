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
from typing import Any
from paper_evaluator.v3_paper_existing_owner_source_bridge_v1 import join_owner_sources
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
        "review_preflights":decisions,
        "real_consumer_requires_separate_actual_kraken_and_p4_recheck":True,
        "independently_authenticated_source_owner_runtime_proven":False,
        "model_http_authorized":False,"model_calls":0,
        "paper_writer_active":False,"paper_buy_authorized":False,
        "orders":False,"real_money_actions":False,
        "old_v2r4_intake_stopped":False,"cloud_active_series_changed":False,
        "new_schedules":0,"v2r4_changed":False,
    }
