"""Real positive H5 news/H10 money/H11 probability as a V3 PAPER ENTRY origin.

Unlike the old context-only adapter, a time-verified materially positive
source can create an INDEPENDENT fresh candidate BEFORE scanner recognition.
Positive source --> full model review, NEVER source --> automatic BUY.
All sources require actual coin attribution, original timestamp, curator
verification and cause/effect. Missing/stale sources never block technical
entry. Pure code, no web, model, cloud, scheduling, or trade action.
"""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
from typing import Any
from urllib.parse import urlparse
import math,re

KIND="V3_PAPER_POSITIVE_SOURCE_TRIGGER_V1"
ELIGIBLE="SOURCE_CATALYST_READY_FOR_FULL_MODEL_REVIEW_ONLY"
STREAMS=("news_sentiment","smart_money_h10","polymarket_h11")
MAX_AGE_SECONDS={"news_sentiment":3600,"smart_money_h10":900,"polymarket_h11":900}
_ALLOWED_H10={"LONG","NET_BUY"}
_ALLOWED_MOVE={"EARLY_ACCELERATION","BREAKOUT_INITIATION","POSITIVE_VELOCITY"}

def utc(v:str)->datetime:
    if not isinstance(v,str):raise ValueError("time required")
    d=datetime.fromisoformat(v.replace("Z","+00:00"))
    if d.tzinfo is None or d.utcoffset() is None:raise ValueError("timezone required")
    return d.astimezone(timezone.utc)

def _bounded(v:Any,minimum:float,maximum:float)->bool:
    return type(v) in (int,float) and math.isfinite(v) and minimum<=v<=maximum

def assess_positive_source(*,pair:str,source_name:str,snapshot:dict[str,Any],
                           decision_at_utc:str,market_move:dict[str,Any]|None=None)->dict[str,Any]:
    """Return explicit qualification + reasons, preserving source attribution."""
    result={"kind":KIND,"pair":pair,"source_name":source_name,"status":"NOT_ELIGIBLE",
            "model_review_only":False,"approval_to_call_model":False,
            "buy_authorized":False,"orders":False,"real_money_actions":False,
            "is_technical_signal_hard_gate":False,
            "no_source_means_no_veto":True,"review_requires_real_kraken_and_p4":True}
    def reject(code:str):
        return {**result,"status":code}
    if not isinstance(pair,str) or not pair.endswith("/EUR") or source_name not in STREAMS:
        return reject("INVALID_SOURCE_OR_PAIR")
    if not isinstance(snapshot,dict) or snapshot.get("pair")!=pair:
        return reject("NOT_COIN_SPECIFIC")
    if snapshot.get("source_verified") is not True or snapshot.get("coin_relevance_verified") is not True:
        return reject("UNVERIFIED_SOURCE_OR_COIN_IMPACT")
    source_id=snapshot.get("source_id")
    owner=snapshot.get("source_owner")
    event_id=snapshot.get("event_id")
    if not all(isinstance(v,str) and 5<=len(v)<=150 and re.fullmatch(r"[A-Za-z0-9_.:/-]+",v)
               for v in (source_id,owner,event_id)):
        return reject("MISSING_CANONICAL_SOURCE_EVENT_ID")
    try:
        at=utc(decision_at_utc)
        observed=utc(snapshot["observed_at_utc"])
        known=utc(snapshot["known_at_utc"])
        if not observed<=known<=at:
            return reject("FUTURE_OR_REVERSED_SOURCE_CLOCK")
        if not 0<=(at-known).total_seconds()<=MAX_AGE_SECONDS[source_name]:
            return reject("STALE_SOURCE_EVENT")
    except (ValueError,TypeError,KeyError,OverflowError):
        return reject("INVALID_SOURCE_PROVENANCE")
    relevance=snapshot.get("impact_mechanism")
    if not isinstance(relevance,str) or not 12<=len(relevance)<=160:
        return reject("MISSING_COIN_SPECIFIC_CAUSAL_MECHANISM")
    reason=None
    if source_name=="news_sentiment":
        # A claim ABOUT a U.S. authority is not an authentic government act.
        # Only an original verified official .gov link (plus curatorial
        # direct-beneficiary check) qualifies for this strong variant.
        link=snapshot.get("official_primary_url")
        if not isinstance(link,str):return reject("OFFICIAL_PRIMARY_EVIDENCE_MISSING")
        uri=urlparse(link)
        host=(uri.hostname or "").lower()
        if (uri.scheme!="https" or not (host=="gov" or host.endswith(".gov"))
                or uri.username is not None or uri.password is not None):
            return reject("OFFICIAL_SOURCE_NOT_AUTHENTICATED")
        if (snapshot.get("official_confirmation") is not True
                or snapshot.get("direct_pair_beneficiary") is not True
                or snapshot.get("sentiment")!="POSITIVE"
                or snapshot.get("news_category") not in
                   ("OFFICIAL_APPROVAL","DIRECT_REGULATORY_BENEFIT",
                    "DIRECT_PUBLIC_FUNDING","OFFICIAL_ADOPTION")):
            return reject("UNCONFIRMED_OR_AMBIGUOUS_OFFICIAL_IMPACT")
        reason="DIRECT_VERIFIED_OFFICIAL_POSITIVE_EVENT"
    elif source_name=="smart_money_h10":
        if (snapshot.get("consensus_direction") not in _ALLOWED_H10
                or not _bounded(snapshot.get("independent_wallet_count"),3,100000)
                or not _bounded(snapshot.get("confirmed_net_buy_usd"),10000,10**12)
                or snapshot.get("onchain_fills_confirmed") is not True
                or snapshot.get("not_self_dealing_checked") is not True):
            return reject("SMART_MONEY_UNCORROBORATED_OR_NO_REAL_FILLS")
        reason="MULTIPLE_INDEPENDENT_CONFIRMED_NET_BUYS"
    else:
        # Probabilities on Polymarket are outcomes of binary questions,
        # NOT automatically directional Kraken coin signals.
        if (snapshot.get("direct_positive_outcome_for_pair") is not True
                or not _bounded(snapshot.get("yes_midpoint"),0,1)
                or not _bounded(snapshot.get("observed_probability_delta"),.10,1)
                or not _bounded(snapshot.get("market_liquidity_usd"),10000,10**12)
                or snapshot.get("market_resolved") is not False):
            return reject("POLYMARKET_NOT_DIRECTLY_POSITIVE_OR_RELIABLE")
        if not isinstance(market_move,dict) or market_move.get("pair")!=pair:
            return reject("POLYMARKET_NEEDS_SAME_COIN_DYNAMIC_MOVEMENT")
        if (market_move.get("source_verified") is not True
                or market_move.get("movement_phase") not in _ALLOWED_MOVE):
            return reject("POLYMARKET_DYNAMIC_MOVEMENT_UNCONFIRMED")
        try:
            mv_at=utc(market_move["known_at_utc"])
            if not 0<=(at-mv_at).total_seconds()<=900:
                return reject("POLYMARKET_DYNAMIC_MOVEMENT_STALE_OR_FUTURE")
        except (ValueError,KeyError,TypeError):
            return reject("POLYMARKET_DYNAMIC_MOVEMENT_CLOCK_UNKNOWN")
        reason="DIRECT_POLYMARKET_EVENT_AND_COIN_EARLY_MOVE"
    return {**result,"status":ELIGIBLE,"model_review_only":True,
            "source_event_id":event_id,"source_owner":owner,"source_id":source_id,
            "source_known_at_utc":snapshot["known_at_utc"],
            "source_observed_at_utc":snapshot["observed_at_utc"],
            "impact_mechanism":relevance,"positive_reason":reason,
            "attribution_family":"SOURCE_CATALYST",
            "same_hard_execution_risk_gates_required":True}

def make_source_candidate(*,pair:str,kraken_altname:str,source_name:str,
                          snapshot:dict[str,Any],decision_at_utc:str,
                          market_move:dict[str,Any]|None=None)->dict[str,Any]:
    """Build an actual independent model-input candidate from a real source."""
    x=assess_positive_source(pair=pair,source_name=source_name,snapshot=snapshot,
                             decision_at_utc=decision_at_utc,market_move=market_move)
    if x["status"]!=ELIGIBLE:raise ValueError("positive catalyst not qualified: "+x["status"])
    if not isinstance(kraken_altname,str) or not kraken_altname.isalnum():
        raise ValueError("independent verified Kraken altname mapping required")
    # Event-known time is the earliest lawful detection. Do not backdate the
    # original source publication into a fabricated early scanner timestamp.
    ident=sha256("|".join((pair,source_name,x["source_event_id"],
                           x["source_known_at_utc"])).encode()).hexdigest()[:24]
    return {"kind":"V3_POSITIVE_SOURCE_CANONICAL_PAPER_CANDIDATE_V1",
            "candidate_id":"V3-SRC-"+ident,"pair":pair,"altname":kraken_altname,
            "event_time_utc":x["source_known_at_utc"],
            "entry_origin":"VERIFIED_POSITIVE_SOURCE_CATALYST",
            "positive_source_name":source_name,
            "positive_source_event_id":x["source_event_id"],
            "positive_source_status":ELIGIBLE,
            "paper_only":True,"real_money_actions":False,"orders":False}
