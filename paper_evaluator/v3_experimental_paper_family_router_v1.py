"""V3 experimental Paper: deterministic family arbitration, NO model/BUY/writer.

A candidate can be eligible under multiple entry hypotheses. At an identical
candidate + Kraken known-at snapshot only ONE fresh full-model request can be
reserved; all other eligible/failed family reasons remain available for the
journal. The caller must atomically persist an independent reservation before
any real HTTP; this pure choice alone never authorizes spend or runtime.
"""
from __future__ import annotations
import hashlib
from typing import Any

KIND="V3_EXPERIMENTAL_PAPER_FAMILY_SELECTION_V1"
PRIORITY=(
    ("SOURCE_CATALYST_INDEPENDENT",
     "V3_EXPERIMENTAL_PAPER_INITIAL_FRESH_FULL_REVIEW_V1",
     "INITIAL_FRESH_PIT_READY_FOR_FULL_V3_MODEL_ONLY"),
    ("FIRST_SCANNER_EARLY_REVIEW",
     "V3_EXPERIMENTAL_PAPER_INITIAL_FRESH_FULL_REVIEW_V1",
     "INITIAL_FRESH_PIT_READY_FOR_FULL_V3_MODEL_ONLY"),
    ("CONTINUITY_FRESH_5M",
     "V3_P3_INACTIVE_EARLY_5M_CONTINUITY_FRESH_REVIEW_V1",
     "EARLY_5M_CONTINUITY_SUPPORTS_NEW_FULL_REVIEW_ONLY"),
    ("P3_CONTINUITY_15M_STANDARD",
     "V3_P3_INACTIVE_CONTINUITY_FRESH_REVIEW_ELIGIBILITY_V1",
     "CONTINUITY_FRESH_STRUCTURE_SUPPORTS_NEW_FULL_REVIEW_ONLY"),
    ("WAIT_EXPIRED_FRESH_REENTRY",
     "V3_P2_INACTIVE_WAIT_FRESH_REVIEW_ELIGIBILITY_V1",
     "WAIT_FRESH_STRUCTURE_SUPPORTS_NEW_FULL_REVIEW_ONLY"),
    ("EXTENDED_GENUINE_NEW_BASE",
     "V3_B_INACTIVE_SECOND_LEG_FRESH_REVIEW_ELIGIBILITY_V1",
     "SECOND_LEG_STRUCTURE_SUPPORTS_NEW_FULL_REVIEW_ONLY"),
    ("CONTINUITY_VOLUME_RESEARCH_ONLY",
     "V3_EXP_INACTIVE_CONTINUITY_ONE_CHANGE_VOLUME_REVIEW_V1",
     "EXPERIMENTAL_CONTINUITY_VOLUME_SUPPORTS_NEW_FULL_REVIEW_ONLY"),
)


def select_one_full_review(*,series_id:str,candidate_id:str,pair:str,
                           known_at_utc:str,
                           hints:dict[str,dict[str,Any]],
                           prior_reserved_review_keys:set[str]|None=None)->dict[str,Any]:
    """Returns at most ONE research hint. Unknown/malformed families fail closed."""
    def res(status:str,**kwargs:Any)->dict[str,Any]:
        return {"kind":KIND,"status":status,"series_id":series_id,
                "source_candidate_id":candidate_id,"pair":pair,
                "decision":"NO_DECISION_AUTHORITY",
                "model_called":False,"paper_writer_started":False,
                "orders":False,"real_money_actions":False,
                "approval_to_call_model":False,
                "reserve_model_call_here":False,
                "active_strategy_changed":False,**kwargs}
    if (not isinstance(series_id,str) or not series_id.startswith("PAPER-V3-")
            or not isinstance(candidate_id,str) or not candidate_id
            or not isinstance(pair,str) or not pair.endswith("/EUR")
            or not isinstance(known_at_utc,str) or not known_at_utc):
        return res("UNKNOWN_INVALID_REVIEW_IDENTITY")
    if not isinstance(hints,dict) or not hints or not set(hints).issubset(
            {x[0] for x in PRIORITY}):
        return res("UNKNOWN_FAMILY_HYPOTHESES")
    if (prior_reserved_review_keys is not None and
            (not isinstance(prior_reserved_review_keys,set)
             or any(not isinstance(x,str) for x in prior_reserved_review_keys))):
        return res("UNKNOWN_DEDUPLICATION_STATE")
    key=hashlib.sha256("|".join((series_id,pair,known_at_utc)).encode()).hexdigest()
    if key in (prior_reserved_review_keys or set()):
        return res("ALREADY_RESERVED_MODEL_REVIEW_IDEMPOTENT",
                   dedup_review_key=key)
    eligible=[]
    diag={}
    for family,expected_kind,expected_status in PRIORITY:
        if family not in hints:continue
        h=hints[family]
        if not isinstance(h,dict):
            return res("UNKNOWN_MALFORMED_FAMILY_REVIEW",failed_family=family)
        if (h.get("kind")!=expected_kind or h.get("pair")!=pair
                or h.get("source_candidate_id")!=candidate_id):
            return res("UNKNOWN_MISMATCHED_FAMILY_REVIEW",failed_family=family)
        status=h.get("status")
        diag[family]={"status":status,
                      "failed_checks":sorted(k for k,v in
                          (h.get("checks") or {}).items() if v is False)}
        if status==expected_status:
            if family=="SOURCE_CATALYST_INDEPENDENT" and (
                    h.get("source_catalyst_qualified") is not True
                    or not isinstance(h.get("source_catalyst_event_id"),str)
                    or not h["source_catalyst_event_id"]):
                return res("UNKNOWN_UNVERIFIED_SOURCE_ORIGIN_TICKET",
                           failed_family=family)
            if h.get("request_model_recheck_only") is not True:
                return res("UNKNOWN_REVIEW_TICKET_INCONSISTENT",failed_family=family)
            if h.get("new_snapshot_known_at_utc")!=known_at_utc:
                return res("UNKNOWN_FAMILY_PIT_CLOCK_MISMATCH",failed_family=family)
            if (h.get("decision")!="NO_DECISION_AUTHORITY"
                    or h.get("orders") is not False
                    or h.get("real_money_actions") is not False):
                return res("UNKNOWN_FAMILY_MODEL_AUTHORITY_MISMATCH",failed_family=family)
            eligible.append(family)
        elif h.get("request_model_recheck_only") is True:
            return res("UNKNOWN_UNEXPECTED_FAMILY_MODEL_REVIEW_PERMISSION",
                       failed_family=family)
    if not eligible:
        return res("NO_FULL_REVIEW_ELIGIBLE",family_statuses=diag,
                   dedup_review_key=key)
    return res("SINGLE_FAMILY_FULL_MODEL_REVIEW_ELIGIBLE_NOT_RESERVED",
               selected_family=eligible[0],
               also_eligible_not_requested=eligible[1:],
               family_statuses=diag,dedup_review_key=key,
               explicit_separate_model_budget_required=True,
               must_atomically_reserve_before_actual_http=True,
               full_model_and_p4_must_validate_entry=True)
