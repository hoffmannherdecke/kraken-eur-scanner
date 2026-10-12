"""V3 future PAPER owner-source bridge, PURE and fail-closed.

The currently deployed H10 Edge returns only descriptive context; today's
H11 source captures five unrelated market books without a coin-positive
probability DELTA; H5 scheduled macro calendar is NOT a verified government
coin-beneficiary announcement. Those three research shapes are NEVER silently
promoted to a positive independent BUY-review candidate.

The existing source steward can later pass original, independently verified
coin-specific event packets from its authorized owner, with an exact
content digest. The digest protects payload integrity, NOT source identity:
the caller remains responsible for authenticating the owner (Cloud permission
or reviewed registry). This module is NEVER a source authenticator.

No network, local IO, AI, scheduler, paper writer, real-world orders or
side-effectful source registration in this module.
"""
from __future__ import annotations
import hashlib,json
from typing import Any
from paper_evaluator.v3_paper_positive_source_entry_v1 import (
    STREAMS,assess_positive_source,ELIGIBLE,
)

KIND="V3_EXISTING_SOURCE_OWNER_PROOF_BRIDGE_V1"
def fingerprint(snapshot:dict[str,Any])->str:
    return hashlib.sha256(json.dumps(snapshot,sort_keys=True,
                          separators=(",",":"),ensure_ascii=False,
                          allow_nan=False).encode("utf-8")).hexdigest()

def join_owner_sources(*,h10_context:dict[str,Any]|None,
                       h11_market_capture:dict[str,Any]|None,
                       h5_macro_calendar:dict[str,Any]|None,
                       owner_event_packets:list[dict[str,Any]],
                       authenticated_owner_ids:dict[str,list[str]],
                       decision_at_utc:str)->dict[str,Any]:
    """Future owner must authenticate sender OUTSIDE this pure code."""
    if (not isinstance(owner_event_packets,list) or len(owner_event_packets)>60
            or not isinstance(authenticated_owner_ids,dict)
            or set(authenticated_owner_ids)!=set(STREAMS)
            or any(not isinstance(v,list) or len(v)>20 for v in authenticated_owner_ids.values())):
        raise ValueError("bounded authenticated-source-owner bridge contract required")
    diagnostics={}
    if h10_context is None:
        diagnostics["smart_money_h10"]="NOT_AVAILABLE"
    elif not isinstance(h10_context,dict):
        raise ValueError("invalid original H10 context")
    elif h10_context.get("status") not in (
            "H10_PIT_CONTEXT_ONLY","NOT_AVAILABLE_OR_STALE",
            "NOT_EVALUABLE_SOURCE_COUNTS"):
        diagnostics["smart_money_h10"]="H10_UNRECOGNIZED_SOURCE_NO_CATALYST"
    else:
        diagnostics["smart_money_h10"]="H10_RESEARCH_CONTEXT_NOT_CONFIRMED_INDEPENDENT_FILLS"
    if h11_market_capture is None:
        diagnostics["polymarket_h11"]="NOT_AVAILABLE"
    elif not isinstance(h11_market_capture,dict):
        raise ValueError("invalid original H11 capture")
    elif h11_market_capture.get("kind")=="V3_H11_POLYMARKET_PROSPECTIVE_STATE_CAPTURE_V1":
        diagnostics["polymarket_h11"]="H11_RAW_MARKET_BOOK_ONLY_NO_PAIR_IMPACT_OR_PROBABILITY_DELTA"
    else:
        diagnostics["polymarket_h11"]="H11_UNRECOGNIZED_CAPTURE_NO_CATALYST"
    if h5_macro_calendar is None:
        diagnostics["news_sentiment"]="NOT_AVAILABLE"
    elif not isinstance(h5_macro_calendar,dict):
        raise ValueError("invalid H5 calendar")
    else:
        diagnostics["news_sentiment"]="H5_MACRO_CALENDAR_NOT_VERIFIED_OFFICIAL_COIN_NEWS"
    accepted=[];denied={}
    for packet in owner_event_packets:
        def fail(key:str):
            denied[key]=denied.get(key,0)+1
        if not isinstance(packet,dict):
            fail("UNVERIFIED_OWNER_PACKET");continue
        name,pair,altname,snap,proof=(packet.get(k) for k in
           ("source_name","pair","altname","snapshot","owner_integrity"))
        if (name not in STREAMS or not isinstance(pair,str)
                or not pair.endswith("/EUR") or not isinstance(altname,str)
                or not altname.isalnum() or not isinstance(snap,dict)
                or not isinstance(proof,dict)):
            fail("NO_CANONICAL_COIN_OR_OWNER_PROVENANCE");continue
        owner=snap.get("source_owner")
        if (not isinstance(owner,str) or owner not in authenticated_owner_ids[name]
                or proof.get("authenticated_owner_id")!=owner
                or proof.get("authentication_checked_by_trusted_caller") is not True):
            fail("OWNER_NOT_AUTHENTICATED_BY_EXISTING_TRUST_BOUNDARY");continue
        try:
            valid_digest=fingerprint(snap)
        except (TypeError,ValueError,OverflowError):
            fail("BAD_SOURCE_PAYLOAD");continue
        if proof.get("canonical_payload_sha256")!=valid_digest:
            fail("SOURCE_EVENT_CONTENT_DIGEST_MISMATCH");continue
        result=assess_positive_source(
            pair=pair,source_name=name,snapshot=snap,
            decision_at_utc=decision_at_utc,
            market_move=packet.get("market_move"))
        if result["status"]!=ELIGIBLE:
            fail("SOURCE_NOT_DIRECT_POSITIVE_OR_POINT_IN_TIME_QUALIFIED");continue
        # Reuse the EXACT already authorized source packet; do not alter its
        # original publication/known_at clock or backdate the owner receipt.
        accepted.append({"source_name":name,"pair":pair,"altname":altname,
                         "snapshot":snap,"market_move":packet.get("market_move")})
    return {
        "kind":KIND,"status":"VERIFIED_OWNER_POSITIVE_EVENTS_PRESENT"
                 if accepted else "NO_AUTHENTICATED_POSITIVE_OWNER_EVENTS",
        "owner_source_events":accepted,
        "raw_source_dispositions":diagnostics,
        "source_event_rejections":denied,
        "owner_authentication_external_not_proven_by_hash":True,
        "source_eligibility_not_a_model_budget":True,
        "model_http_authorized":False,"model_calls":0,
        "paper_writer_active":False,"orders":False,"real_money_actions":False,
        "v2r4_changed":False,"new_scheduler":False,
    }
