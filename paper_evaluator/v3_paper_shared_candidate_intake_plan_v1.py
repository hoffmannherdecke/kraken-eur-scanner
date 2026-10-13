"""Pure shared V3 PAPER ingress plan: original Scanner + verified positive sources.

This is the MISSING bounded router for the FUTURE single V3 Paper writer.
It only SELECTS original events known at the decision clock. It cannot use
OpenAI, schedule processes, create local receipts, write to Cloud, make PAPER
fills or modify the sole active V2R4 series. Every review still needs fresh
Kraken Spot-EUR metadata, real coin 1m/5m/15m, model spend authorization,
a complete model response and the common P4/fee/stop/Stage2 validation.

Positive official news, verified independent Smart Money or a directly
coin-related Polymarket event may independently reach FULL_REVIEW; missing
optional signals never veto already-qualified Scanner handoffs.
"""
from __future__ import annotations
import hashlib,re
from datetime import datetime,timezone
from typing import Any
from paper_evaluator.v3_paper_positive_source_entry_v1 import (
    STREAMS,make_source_candidate,utc,
)

KIND="V3_SHARED_PAPER_CANDIDATE_INTAKE_PLAN_V1"
SCANNER_KIND="CANONICAL_CANDIDATE_HANDOFF_V1"
JOURNAL_KIND="V3_EXPERIMENTAL_PAPER_CANDIDATE_EVENT_V1"
FRESH_SECONDS=600
COALESCE_SECONDS=300
AUDIT_KIND="V3_ROUTER_REJECTED_ORIGINAL_AUDIT_V1"
_SAFE_ID=re.compile(r"^[A-Za-z0-9_.:-]{1,150}$")
_SAFE_PAIR=re.compile(r"^[A-Z0-9]{2,20}/EUR$")
_SAFE_SOURCE=re.compile(r"^[A-Za-z0-9_.:-]{1,150}$")

def _router_rejection_audit(raw:Any,*,origin:str,index:int,
                            reason:str,decision_at_utc:str)->dict[str,Any]:
    """Only fixed allowlisted metadata, never raw source payloads or secrets.

    Untrusted/noncanonical inputs receive a deterministic audit identity, NOT
    a candidate identity. They cannot enter the model/BUY or economic funnel.
    """
    original=raw if isinstance(raw,dict) else {}
    snapshot=original.get("snapshot")
    snap=snapshot if isinstance(snapshot,dict) else {}
    def safe(value:Any,pattern:re.Pattern[str])->str|None:
        return value if isinstance(value,str) and pattern.fullmatch(value) else None
    candidate_id=safe(original.get("candidate_id"),_SAFE_ID)
    pair=safe(original.get("pair"),_SAFE_PAIR)
    source_event_id=safe(snap.get("event_id"),_SAFE_SOURCE)
    untrusted_clock=original.get("event_time_utc")
    if untrusted_clock is None:
        untrusted_clock=snap.get("known_at_utc")
    clock_text=None
    if isinstance(untrusted_clock,str) and len(untrusted_clock)<=64:
        try: clock_text=utc(untrusted_clock).isoformat()
        except (ValueError,TypeError,OverflowError,AttributeError): pass
    if type(index) is not int or index<0:
        raise ValueError("invalid original input ordinal")
    audit_seed="|".join((origin,str(index),reason,decision_at_utc))
    audit_id="V3-INPUT-REJECT-"+hashlib.sha256(audit_seed.encode()).hexdigest()[:32]
    return {"kind":AUDIT_KIND,"audit_id":audit_id,
            "input_stream":origin,"input_index":index,"reason":reason,
            "original_candidate_id_if_safe":candidate_id,
            "original_pair_if_safe":pair,
            "original_event_time_if_parseable":clock_text,
            "original_source_event_id_if_safe":source_event_id,
            "original_untrusted_and_not_tradeable":True}


def _pair_meta(pair:str,altname:str,known_pairs:dict[str,Any])->bool:
    if (not isinstance(pair,str) or not pair.endswith("/EUR")
            or type(altname) is not str or not altname.isalnum()
            or not isinstance(known_pairs,dict)):
        return False
    meta=known_pairs.get(pair)
    return (isinstance(meta,dict) and meta.get("pair")==pair
            and meta.get("altname")==altname
            and meta.get("status")=="online"
            and meta.get("spot") is True and meta.get("quote")=="EUR")

def plan_intake(*,scanner_events:list[dict],source_events:list[dict],
                known_pairs:dict[str,dict],journal_receipts:list[dict],
                series_id:str,decision_at_utc:str,
                max_reviews:int=3)->dict[str,Any]:
    """No filesystem or HTTP side effects. Defer (not drop) overflow."""
    if (not isinstance(series_id,str) or not series_id.startswith("PAPER-V3-")
            or not all(isinstance(x,list) for x in
                       (scanner_events,source_events,journal_receipts))
            or type(max_reviews) is not int or not 1<=max_reviews<=5
            or len(scanner_events)>2000 or len(source_events)>2000
            or len(journal_receipts)>50000):
        raise ValueError("bounded isolated V3 paper planner input required")
    at=utc(decision_at_utc)
    if at.year<2026:raise ValueError("invalid decision clock")
    seen:dict[str,tuple[str,str]]={}
    prior_rows:dict[str,list[dict[str,Any]]]={}
    for row in journal_receipts:
        if not isinstance(row,dict) or row.get("kind")!=JOURNAL_KIND:
            raise ValueError("unverified immutable journal input")
        if row.get("series_id")!=series_id:continue
        cid,pair,event_time=row.get("candidate_id"),row.get("pair"),row.get("event_time_utc")
        if not isinstance(cid,str) or not isinstance(pair,str) or not isinstance(event_time,str):
            raise ValueError("invalid existing original V3 journal identity")
        old=seen.setdefault(cid,(pair,event_time))
        if old!=(pair,event_time):raise ValueError("conflicting immutable V3 candidate ID")
        prior_rows.setdefault(cid,[]).append(row)
    reasons:dict[str,int]={}
    rejected=[]
    rejected_originals=[]
    eligible=[]
    same_identity={}
    def exclude(reason:str,origin:str,raw:Any=None,index:int|None=None):
        reasons[reason]=reasons.get(reason,0)+1
        rejected.append({"origin":origin,"reason":reason})
        if index is not None:
            rejected_originals.append(_router_rejection_audit(
                raw,origin=origin,index=index,reason=reason,
                decision_at_utc=at.isoformat()))
    def add(candidate:dict[str,Any],origin:str,raw:Any,index:int):
        cid,pair,altname=(candidate.get(k) for k in ("candidate_id","pair","altname"))
        if not all(isinstance(x,str) and x for x in (cid,pair,altname)):
            exclude("MISSING_ORIGINAL_CANDIDATE_IDENTITY",origin,raw,index);return
        if not _pair_meta(pair,altname,known_pairs):
            exclude("PAIR_NOT_VERIFIED_AS_SPOT_EUR_METADATA_RECHECK_REQUIRED",origin,raw,index);return
        try:
            original=utc(candidate["event_time_utc"])
        except (ValueError,TypeError,KeyError,OverflowError,AttributeError):
            exclude("UNKNOWN_ORIGINAL_EVENT_CLOCK",origin,raw,index);return
        age=(at-original).total_seconds()
        if age<0:
            exclude("FUTURE_EVENT_NOT_YET_KNOWN",origin,raw,index);return
        if age>FRESH_SECONDS:
            exclude("EXPIRED_ORIGINAL_10M_WINDOW",origin,raw,index);return
        known=same_identity.get(cid)
        if known is not None:
            if known!=(pair,original.isoformat()):
                raise ValueError("two different events claim same candidate ID")
            exclude("EXACT_CANDIDATE_DUPLICATE_IN_INPUT",origin,raw,index);return
        same_identity[cid]=(pair,original.isoformat())
        if cid in seen:
            if seen[cid][0]!=pair or utc(seen[cid][1])!=original:
                raise ValueError("immutable candidate ID conflict with Cloud/journal")
            old_rows=prior_rows[cid]
            # The ONLY resumable receipt is one original SCANNER event that
            # was capacity-deferred (not rejected by the entry model). No
            # already processed, source-auth, or historically expired replay.
            deferred=(origin=="SCANNER" and len(old_rows)==1 and
                old_rows[0].get("phase")=="SCANNER_CAPTURE" and
                old_rows[0].get("event_key")=="FIRST" and
                old_rows[0].get("result")=="SKIP" and
                isinstance(old_rows[0].get("data"),dict) and
                old_rows[0]["data"].get("candidate_origin")=="SCANNER" and
                old_rows[0]["data"].get("source_status")==
                "CAPACITY_DEFERRED_NOT_A_NEGATIVE_MARKET_DECISION")
            if not deferred:
                exclude("ALREADY_JOURNALED_NO_REPEAT_NO_SPEND",origin,raw,index);return
            candidate=dict(candidate,deferred_recheck=True)
        eligible.append({"candidate":dict(candidate),
                         "origin":origin,"at":original})

    for idx,row in enumerate(scanner_events):
        if (not isinstance(row,dict)
                or row.get("kind")!=SCANNER_KIND
                or row.get("action")!="REVIEW_ONLY_NOT_ORDER"
                or row.get("entry_origin") not in (None,"SCANNER")):
            exclude("SCANNER_EVENT_NOT_AUTHORIZED_REVIEW_ONLY", "SCANNER",row,idx)
            continue
        # Nothing in this ingress logic is a liquidity/volume BUY VETO.
        add(dict(row,entry_origin="SCANNER"),"SCANNER",row,idx)

    for idx,row in enumerate(source_events):
        if not isinstance(row,dict):
            exclude("SOURCE_ENVELOPE_INVALID","SOURCE_CATALYST",row,idx)
            continue
        name,pair,altname=(row.get(k) for k in ("source_name","pair","altname"))
        if name not in STREAMS or not _pair_meta(pair,altname,known_pairs):
            exclude("SOURCE_NOT_VERIFIED_PAIR_MAPPING","SOURCE_CATALYST",row,idx)
            continue
        snapshot=row.get("snapshot")
        if not isinstance(snapshot,dict):
            exclude("SOURCE_SNAPSHOT_ABSENT","SOURCE_CATALYST",row,idx)
            continue
        try:
            candidate=make_source_candidate(
                pair=pair,kraken_altname=altname,source_name=name,
                snapshot=snapshot,decision_at_utc=decision_at_utc,
                market_move=row.get("market_move"))
        except (ValueError,TypeError,KeyError,OverflowError,AttributeError):
            exclude("SOURCE_CATALYST_NOT_INDEPENDENTLY_VERIFIED",
                    "SOURCE_CATALYST",row,idx)
            continue
        add(candidate,"SOURCE_CATALYST",row,idx)
    # Verified positive catalyst is prioritized over an otherwise same-coin
    # scanner notification within five minutes, not misrepresented as a BUY.
    eligible.sort(key=lambda e:(0 if e["origin"]=="SOURCE_CATALYST" else 1,
                                e["at"],e["candidate"]["candidate_id"]))
    selected=[]
    capacity_deferred=[]
    coalesced_originals=[]
    near_pairs:dict[str,datetime]={}
    for entry in eligible:
        pair=entry["candidate"]["pair"]
        if pair in near_pairs and abs((near_pairs[pair]-entry["at"]).total_seconds())<=COALESCE_SECONDS:
            # Preserve full original identifier and why this was merged with
            # a prioritized same-coin review. Later economic attribution must
            # see BOTH raw events, never claim both were independently modeled.
            coalesced_originals.append(entry["candidate"])
            exclude("SAME_PAIR_CONCURRENT_REVIEW_COALESCED_NOT_LOST","ROUTER")
            continue
        if len(selected)>=max_reviews:
            # These remain eligible next tick while the original source clock
            # is fresh; no silent model spending, and overflow is disclosed.
            capacity_deferred.append(entry["candidate"])
            exclude("CAPACITY_DEFERRED_NOT_A_NEGATIVE_MARKET_DECISION","ROUTER")
            continue
        selected.append(entry["candidate"])
        near_pairs[pair]=entry["at"]
    return {"kind":KIND,"series_id":series_id,"decision_at_utc":at.isoformat(),
            "status":"CANDIDATES_READY_FOR_KRAKEN_AND_MODEL_P4_REVIEW_ONLY"
                     if selected else "NO_FRESH_UNJOURNALED_INPUT",
            "candidates":selected,
            # This is returned original evidence ONLY, not a durable queue.
            # A future single owner must persist the deferral journal and
            # recheck the original 10-minute clock before spending a model.
            "capacity_deferred_originals":capacity_deferred,
            "same_pair_coalesced_originals":coalesced_originals,
            "rejected_originals":rejected_originals,
            "rejected_originals_audit_only_no_model_authority":True,
            "overflow_requires_durable_owner_queue_before_runtime":bool(capacity_deferred),
            "all_rejected_and_deferred_originals_not_yet_journaled":True,
            "counts":{"scanner_input":len(scanner_events),
                      "source_input":len(source_events),
                      "selected":len(selected),
                      "suppressed_or_deferred":sum(reasons.values())},
            "dispositions":reasons,
            "candidate_level_reasons":rejected,
            "requires_fresh_spot_pair_metadata_recheck":True,
            "requires_full_v3_model_and_p4":True,
            "model_http_authorized":False,"model_calls":0,"orders":False,
            "paper_writer_active":False,"v2r4_unchanged":True,
            "new_scheduler":False,"real_money_actions":False}
