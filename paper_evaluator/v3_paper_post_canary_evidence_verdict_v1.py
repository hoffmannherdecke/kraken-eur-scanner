"""Read-only prospective V3 Canary evidence verdict; NOT a strategy release gate.

The existing 28h watcher and isolated PR220 one-shot are two DIFFERENT
observational cohorts. Never merge their 6/24/72h outcomes into one economic
estimate, or turn technical health into Paper permission.

Accept only independently fetched cloud receipt rows with their immutable
event identifiers, not user-edited summary counts. No IO/network/model/
scheduler/Cloud writing, no automatic Paper cutover. 72h maturation is tracked
but is NOT an artificial prerequisite for reviewing a completed 28h window.
"""
from __future__ import annotations

from collections import Counter
import json
from datetime import timedelta
from hashlib import sha256
from math import isfinite
import re
from typing import Any

from paper_evaluator.v3_experimental_paper_journal_v1 import (
    clock, KIND as RECEIPT_KIND, PHASES, OUTCOME_PHASES, RESULTS,
)
from paper_evaluator.v3_paper_cloud_receipt_sync_v1 import REVISION

KIND="V3_POST_28H_CANARY_EVIDENCE_VERDICT_READONLY_V1"
WATCH="PAPER-V3-CANARY-20261011"
SMOKE="PAPER-V3-CANARY-WRITER-SMOKE-20261012"
ORIGINAL_ACTIVE="PAPER-V2R4-20261009T110135Z"
SMOKE_STAGES={
    ("SCANNER_CAPTURE","SEEN","FIRST"),
    ("FULL_REVIEW_ELIGIBILITY","UNKNOWN","FIRST"),
    ("SOURCE_INPUT","PASS","FRESHRECHECK"),
    ("FULL_REVIEW_ELIGIBILITY","PASS","FRESHRECHECK"),
    ("MODEL_REQUEST","SKIP","FRESHRECHECK"),
}
HEX=re.compile(r"^[0-9a-f]{64}$")
HORIZONS=(6,24,72)


def verdict(*,cloud_rows:list[dict[str,Any]],as_of_utc:str,
            observer_deadline_utc:str,active_paper_series:list[str],
            physical_observer_end_ack:bool=False)->dict[str,Any]:
    """Describe evidence, never authorize model HTTP, a cutover, or orders.

    Cloud rows are read-only SUPABASE event_id/content_sha256/payload
    envelopes. A report cannot authenticate the collection method itself:
    callers must supply the true database snapshot, not locally forged rows.
    """
    at=clock(as_of_utc)
    end=clock(observer_deadline_utc)
    if end!=clock("2026-10-13T12:00:12.2795431Z"):
        raise ValueError("invalid original bounded observation deadline")
    if type(physical_observer_end_ack) is not bool:
        raise ValueError("physical watcher end acknowledgement must be explicit")
    if (not isinstance(cloud_rows,list) or len(cloud_rows)>50000
            or not isinstance(active_paper_series,list)
            or any(not isinstance(s,str) for s in active_paper_series)):
        raise ValueError("complete bounded cloud and Paper inputs required")
    identities=set()
    grouped={WATCH:{},SMOKE:{}}
    phases={WATCH:Counter(),SMOKE:Counter()}
    checked=0
    for envelope in cloud_rows:
        if not isinstance(envelope,dict):
            raise ValueError("Cloud event envelope is missing")
        payload=envelope.get("payload")
        event_id=envelope.get("event_id")
        content_digest=envelope.get("content_sha256")
        if (not isinstance(payload,dict)
                or payload.get("kind")!=RECEIPT_KIND
                or payload.get("real_money_actions") is not False
                or payload.get("orders") is not False
                or payload.get("revision")!=REVISION
                or not isinstance(event_id,str) or not HEX.fullmatch(event_id)
                or not isinstance(content_digest,str) or not HEX.fullmatch(content_digest)):
            raise ValueError("unverified cloud receipt envelope")
        # The local O_EXCL journal hashes canonical sorted JSON + one newline.
        # A digest merely shaped like SHA-256 is not a payload-integrity
        # check. Compare against the exact original local serialization so
        # mutated JSONB data cannot appear to be verified Cloud evidence.
        try:
            canonical=(json.dumps(payload,sort_keys=True,separators=(",",":"),
                                  allow_nan=False)+"\n").encode("utf-8")
        except (TypeError,ValueError) as exc:
            raise ValueError("noncanonical V3 cloud receipt payload") from exc
        if sha256(canonical).hexdigest()!=content_digest:
            raise ValueError("tampered V3 cloud receipt content digest")
        series=payload.get("series_id")
        if series not in grouped or envelope.get("series_id")!=series:
            raise ValueError("unexpected/mismatched V3 study series")
        cid=payload.get("candidate_id")
        pair=payload.get("pair")
        phase=payload.get("phase")
        result=payload.get("result")
        event_key=payload.get("event_key")
        if (not isinstance(cid,str) or not 1<=len(cid)<=150
                or not isinstance(pair,str) or not pair.endswith("/EUR")
                or phase not in PHASES or result not in RESULTS
                or not isinstance(event_key,str)
                or not re.fullmatch(r"[A-Z][A-Z0-9_]{1,90}",event_key)
                or not isinstance(payload.get("data"),dict)):
            raise ValueError("invalid immutable candidate identity or event")
        known=clock(payload["known_at_utc"])
        original=clock(payload["event_time_utc"])
        if known<original or known>at+timedelta(minutes=2):
            raise ValueError("retrospective/future-dated event clock")
        stable="|".join((series,cid,phase,event_key))
        if sha256(stable.encode()).hexdigest()!=event_id or event_id in identities:
            raise ValueError("tampered or duplicate immutable event identity")
        identities.add(event_id)
        checked+=1
        phases[series][(phase,result)]+=1
        record=grouped[series].setdefault(cid,[])
        if record and (record[0]["pair"]!=pair or
                       clock(record[0]["event_time_utc"])!=original):
            raise ValueError("same original candidate has conflicting provenance")
        record.append(payload)

    watch=grouped[WATCH]
    smoke=grouped[SMOKE]
    smoke_structural=False
    smoke_p0_checks=0
    if len(smoke)==1:
        only=next(iter(smoke.values()))
        actual={(r["phase"],r["result"],r["event_key"]) for r in only}
        staged=[r for r in only if r["phase"]=="FULL_REVIEW_ELIGIBILITY"
                and r["event_key"]=="FRESHRECHECK"]
        checks=staged[0].get("data",{}).get("review_checks") if len(staged)==1 else None
        smoke_p0_checks=sum(v is True for v in checks.values()) if isinstance(checks,dict) else 0
        smoke_structural=(len(only)==5 and actual==SMOKE_STAGES
                          and isinstance(checks,dict) and len(checks)==8
                          and smoke_p0_checks==8
                          and all(r["pair"]=="RENDER/EUR" for r in only)
                          and any(r["phase"]=="SOURCE_INPUT"
                              and r["data"].get("source_status")=="COMPLETE"
                              for r in only)
                          and any(r["phase"]=="MODEL_REQUEST"
                              and r["data"].get("source_status")=="PREFLIGHT_NO_MODEL"
                              for r in only))
    buckets={str(h):{"not_yet_due":0,"due_missing_or_pending":0,
                     "mature_complete":0,"censored":0} for h in HORIZONS}
    cases=[]
    valid_model_responses=0
    p4_valid_buy=0
    mature_paper_net_count=0
    next_due=[]
    overdue_recovery_exhausted=Counter()
    for cid,rows in sorted(watch.items()):
        # Audit-only synthetic invalid inputs have no coin identity or P&L.
        audit=cid.startswith("V3-INPUT-REJECT-")
        origs=[r for r in rows if r["phase"]=="SCANNER_CAPTURE"
               and r["event_key"]=="FIRST"]
        if audit:
            if any(r["phase"] in OUTCOME_PHASES or r["phase"]=="PAPER_FILL"
                   for r in rows):
                raise ValueError("synthetic input rejection cannot receive a market outcome")
            continue
        if len(origs)!=1:
            raise ValueError("no uniquely identified original scanner receipt")
        first=origs[0]
        model_good=any(r["phase"]=="MODEL_RESPONSE" and r["result"]=="PASS"
                       for r in rows)
        p4_good=any(r["phase"]=="P4_VALIDATION" and r["result"]=="BUY_SCOUT"
                    and r["data"].get("p4_decision")=="BUY_SCOUT"
                    for r in rows)
        valid_model_responses+=int(model_good)
        p4_valid_buy+=int(model_good and p4_good)
        by_h={}
        due_clock={}
        recovery_clock={}
        for h in HORIZONS:
            phase=f"FOLLOWUP_{h}H"
            finals=[r for r in rows if r["phase"]==phase
                    and r["result"] in ("MATURE_COMPLETE","CENSORED")]
            if len(finals)>1:
                raise ValueError("contradictory final followup for one horizon")
            due=clock(first["event_time_utc"])+timedelta(hours=h)
            due_clock[str(h)]=due.isoformat()
            recovery_clock[str(h)]=(due+timedelta(minutes=60)).isoformat()
            if finals:
                outcome=finals[0]
                if clock(outcome["known_at_utc"])<due:
                    raise ValueError("premature 6/24/72h economic event")
                if outcome["result"]=="MATURE_COMPLETE":
                    data=outcome["data"]
                    if (data.get("path_contiguous_1m_verified") is not True
                            or data.get("followup_source")!="KRAKEN_CLOSED_1M_PATH_CAPTURE_V1"):
                        raise ValueError("mature 1m clock/market provenance missing")
                    num=data.get("position_net_pnl_eur")
                    if num is not None:
                        if type(num) not in (int,float) or not isfinite(num):
                            raise ValueError("invalid fee-adjusted Paper net estimate")
                        if not any(r["phase"]=="PAPER_FILL" for r in rows):
                            raise ValueError("non-buy raw opportunity cannot claim trade profit")
                        mature_paper_net_count+=1
                    label="mature_complete"
                else:
                    if not outcome["data"].get("censor_reason"):
                        raise ValueError("censor cannot be a silent loss or zero")
                    label="censored"
            elif at<due:
                label="not_yet_due"
                next_due.append((due,first["pair"],cid,h))
            else:
                label="due_missing_or_pending"
                if at>=due+timedelta(minutes=60):
                    overdue_recovery_exhausted[str(h)]+=1
            buckets[str(h)][label]+=1
            by_h[str(h)]=label
        cases.append({"candidate_id":cid,"pair":first["pair"],
                      "original_at_utc":first["event_time_utc"],
                      "model_response_verified":model_good,
                      "p4_buy_contract_after_model":bool(model_good and p4_good),
                      "horizons":by_h,
                      "followup_due_at_utc":due_clock,
                      "recovery_until_utc":recovery_clock})
    window_elapsed=at>=end
    watcher_status=("AWAIT_FIXED_DEADLINE" if not window_elapsed else
                    "ENDED_TIME_ONLY_PHYSICAL_STOP_NOT_VERIFIED"
                    if not physical_observer_end_ack else
                    "WINDOW_ENDED_HOST_STOP_ACK_SUPPLIED")
    original_still_only_active=active_paper_series==[ORIGINAL_ACTIVE]
    missing_24=buckets["24"]["due_missing_or_pending"]
    complete_24=buckets["24"]["mature_complete"]
    return {
        "kind":KIND,"as_of_utc":at.isoformat(),
        "original_window_end_utc":end.isoformat(),
        "observation_window":watcher_status,
        "physical_end_ack_supplied_not_independently_authenticated":physical_observer_end_ack,
        "separate_series":{WATCH:{"cloud_rows":sum(phases[WATCH].values()),
                                  "unique_real_originals":len(cases)},
                           SMOKE:{"cloud_rows":sum(phases[SMOKE].values()),
                                  "one_shot_real_p0_proof":smoke_structural,
                                  "p0_validations_passed":smoke_p0_checks}},
        "watcher_phase_results":{f"{k[0]}:{k[1]}":n for k,n in
                                 sorted(phases[WATCH].items())},
        "watcher_followup_coverage":buckets,
        "watcher_cases":cases,
        "watcher_valid_model_responses":valid_model_responses,
        "watcher_p4_model_backed_buy_count":p4_valid_buy,
        "watcher_mature_virtual_fee_adjusted_paper_net_count":mature_paper_net_count,
        "watcher_24h_mature_cases":complete_24,
        "watcher_24h_due_missing_cases":missing_24,
        "watcher_due_missing_past_60m_recovery":dict(overdue_recovery_exhausted),
        "watcher_next_unmatured_horizon":(
            {"due_at_utc":min(next_due)[0].isoformat(),
             "pair":min(next_due)[1],
             "candidate_id":min(next_due)[2],
             "hours":min(next_due)[3]}
            if next_due else None),
        "only_v2r4_active_as_reported":original_still_only_active,
        "transport_one_shot_proven_not_continuous_writer":smoke_structural,
        "economics_not_proven_by_no_buy_mfe":True,
        "automatic_model_api_authorized":False,
        "strategy_v3_auto_activation_authorized":False,
        "real_money_actions":False,
        "new_schedules":0,
        "next_research_disposition":(
            "WAIT_FOR_ORIGINAL_FIXED_OBSERVATION_END_NO_EXTENSION" if not window_elapsed
            else "REVIEW_MISSING_OR_CENSORED_24H_DATA_NO_FALSE_PNL" if missing_24
            else "REVIEW_FEE_ADJUSTED_DECISION_QUALITY_WITH_EXISTING_CONTROL_PLANE"
        ),
        "release": "BLOCKED_NEW_V3_PAPER_REQUIRES_SEPARATE_CAUSAL_STRATEGY_AND_RUNTIME_GATES",
        "important_limit":("A verified one-shot P0 and Cloud ACK cannot prove a "
                            "permanent V3 Writer, a source-authenticated positive "
                            "catalyst, or an economic edge. 72h is informational, "
                            "not a new blanket waiting period."),
    }
