"""Durable V3 experimental PAPER decision funnel / reason / followup journal.

Every candidate has its OWN immutable event receipts, including first skip
before model HTTP. A missing or censored 6h/24h/72h outcome is UNKNOWN, never
0 P&L. A technical series rotation does not modify predecessor receipts.

Only an EXPLICIT caller-provided directory can be written, with O_EXCL
and exact-payload duplicate check. No default production path, cloud, model,
scheduler, Paper writer or orders are created by importing this module.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
import re
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from typing import Any

KIND="V3_EXPERIMENTAL_PAPER_CANDIDATE_EVENT_V1"
PHASES=frozenset({
    "SCANNER_CAPTURE","SOURCE_CATALYST","SOURCE_INPUT","FULL_REVIEW_ELIGIBILITY","MODEL_REQUEST",
    "MODEL_RESPONSE","MODEL_ERROR","P4_VALIDATION","WAIT_WATCH","WAIT_EXPIRY",
    "WAIT_RECHECK","FRESH_SECOND_LEG","PAPER_FILL","PAPER_EXIT",
    "FOLLOWUP_6H","FOLLOWUP_24H","FOLLOWUP_72H","SERIES_ROTATION",
})
OUTCOME_PHASES={"FOLLOWUP_6H":6,"FOLLOWUP_24H":24,"FOLLOWUP_72H":72}
RESULTS=frozenset({
    "SEEN","PASS","SKIP","UNKNOWN","ERROR","WAIT","REJECT","BUY_SCOUT",
    "PAPER_FILLED","CLOSED","MATURE_COMPLETE","CENSORED","PENDING"
})
DATA_FIELDS=frozenset({
    "source_phase","source_status","input_known_at_utc",
    "frame_status_1m","frame_status_5m","frame_status_15m",
    "frame_closed_end_1m","frame_closed_end_5m","frame_closed_end_15m",
    "frame_close_1m_eur","frame_close_5m_eur","frame_close_15m_eur",
    "frame_volume_ratio_1m","frame_volume_ratio_5m","frame_volume_ratio_15m",
    "atr14_15m_eur","structural_low_15m_eur",
    "kraken_online_spot_eur","ask_eur","bid_eur","spread_pct",
    "source_pair_metadata_status","source_latency_ms","candidate_latency_ms",
    "review_lane","review_family","review_status","review_checks",
    "standard_status","experimental_status","failed_hard_checks",
    "phase_failure_class","phase_failure_stage",
    "input_fingerprint_sha256","model_response_id","model_name",
    "model_request_at_utc","model_response_at_utc","p4_completed_at_utc",
    "model_http_attempts_reserved","raw_model_decision","raw_setup_lane",
    "raw_reason_codes","raw_missing_triggers","raw_stop_eur",
    "raw_stage2_trigger_eur","raw_wait_ttl_minutes","raw_watch_conditions",
    "normalized_model_decision","normalized_reason_codes",
    "p4_status","p4_decision","p4_reason_codes",
    "proposed_stop_eur","validated_stop_eur","validated_stage2_eur",
    "stage2_ttl_minutes","expected_remaining_move_pct",
    "total_cost_pct","estimated_slippage_pct_each_side",
    "paper_entry_ask_eur","paper_entry_qty","paper_entry_fee_eur",
    "paper_stage2_triggered","paper_stage2_fill_eur","paper_stage2_fee_eur",
    "paper_exit_bid_eur","paper_exit_fee_eur","paper_exit_reason",
    "position_net_pnl_eur","position_net_return_pct",
    "mfe_pct","mae_pct","close_return_pct","first_stop_hit_at_utc",
    "stop_before_profit_ordering","path_contiguous_1m_verified",
    "followup_source","censor_reason","predecessor_series_id",
    "original_strategy_epoch_id","strategy_fingerprint_sha256",
    "market_regime_known_at","pair_six_hour_episode",
    "candidate_origin","positive_source_name","positive_source_event_id",
    "positive_source_status","positive_source_reason","positive_source_owner",
    "positive_coin_impact_mechanism","independent_source_entry",
    "wait_recheck_at_utc","watch_closed_5m_end_utc","watch_evaluated_conditions",
    "watch_conditions_met","watch_snapshot_values","watch_valid_snapshot_count",
    "watch_did_not_prove_no_trigger",
    "optional_context_states","market_phase_evidence","smart_money_evidence",
    "polymarket_evidence","news_sentiment_evidence","source_management_evidence",
})
CODE=re.compile(r"^[A-Z][A-Z0-9_]{1,90}$")
HEX=re.compile(r"^[0-9a-f]{64}$")


def clock(stamp:str)->datetime:
    if not isinstance(stamp,str):
        raise ValueError("timestamp must be a string")
    x=datetime.fromisoformat(stamp.replace("Z","+00:00"))
    if x.tzinfo is None or x.utcoffset() is None:
        raise ValueError("all clocks must be explicit timezone-aware")
    return x.astimezone(timezone.utc)


def _validate_tree(value:Any)->None:
    if value is None or isinstance(value,(str,bool)):
        return
    if isinstance(value,(int,float)):
        if not math.isfinite(value):
            raise ValueError("nonfinite journal number")
        return
    if isinstance(value,(list,tuple)):
        if len(value)>50: raise ValueError("oversized journal list")
        for item in value:_validate_tree(item)
        return
    if isinstance(value,dict):
        if len(value)>80: raise ValueError("oversized journal dictionary")
        for key,item in value.items():
            if not isinstance(key,str) or len(key)>110:
                raise ValueError("invalid journal field name")
            _validate_tree(item)
        return
    raise ValueError("nonportable journal value")


def make_receipt(*,series_id:str,revision:str,candidate_id:str,pair:str,
                 event_time_utc:str,known_at_utc:str,phase:str,
                 result:str,data:dict[str,Any]|None=None,
                 event_key:str="FIRST")->dict[str,Any]:
    if (not isinstance(series_id,str) or not series_id.startswith("PAPER-V3-")
            or not isinstance(revision,str) or not revision.startswith("V3-")
            or not isinstance(candidate_id,str) or not 1<=len(candidate_id)<=150
            or not isinstance(pair,str) or not pair.endswith("/EUR")):
        raise ValueError("canonical V3 Paper identity required")
    if phase not in PHASES or result not in RESULTS or not CODE.fullmatch(event_key):
        raise ValueError("unsupported phase, result or event key")
    if phase in OUTCOME_PHASES and result not in {"PENDING","CENSORED","MATURE_COMPLETE"}:
        raise ValueError("outcome must be pending/censored/completely mature")
    t=clock(event_time_utc);k=clock(known_at_utc)
    if k<t:
        raise ValueError("future-known data cannot predate actual candidate event")
    if phase in OUTCOME_PHASES and result=="MATURE_COMPLETE":
        if (k-t).total_seconds()<OUTCOME_PHASES[phase]*3600:
            raise ValueError("6h/24h/72h followup is not yet mature")
    if data is None:
        data = {}
    if not isinstance(data,dict) or not set(data).issubset(DATA_FIELDS):
        raise ValueError("only canonical non-secret telemetry fields allowed")
    _validate_tree(data)
    if result=="CENSORED" and not data.get("censor_reason"):
        raise ValueError("censored observation must state why it is missing")
    if phase in OUTCOME_PHASES and result=="MATURE_COMPLETE":
        if (data.get("followup_source") is None
                or data.get("path_contiguous_1m_verified") is not True):
            raise ValueError("mature outcome requires independently verified path")
    if phase=="P4_VALIDATION" and result=="BUY_SCOUT":
        if (data.get("p4_decision")!="BUY_SCOUT"
                or data.get("p4_status")!="FULL_BUY_SCOUT_CONTRACT_VALIDATED_OFFLINE_NOT_RELEASE_EVIDENCE"):
            raise ValueError("model BUY alone never means validated Paper entry")
        ask,stop,trigger=data.get("ask_eur"),data.get("validated_stop_eur"),data.get("validated_stage2_eur")
        if (any(type(v) not in (int,float) for v in (ask,stop,trigger))
                or not 0<stop<ask<trigger
                or type(data.get("total_cost_pct")) not in (int,float)
                or data["total_cost_pct"]<1.2):
            raise ValueError("no risk/fee valid Paper BUY")
    return {
        "kind":KIND,"series_id":series_id,"revision":revision,
        "candidate_id":candidate_id,"pair":pair,"event_time_utc":event_time_utc,
        "known_at_utc":known_at_utc,"phase":phase,"result":result,
        "event_key":event_key,"data":data,
        "real_money_actions":False,"orders":False,
        "unknown_is_not_reject":True,"mfe_is_not_net_profit":True,
    }


def store_receipt_explicitly(directory:Path,receipt:dict[str,Any])->tuple[str,Path]:
    """Durable exclusive local receipt. Never mutates an existing row or series."""
    if receipt.get("kind")!=KIND or receipt.get("orders") is not False:
        raise ValueError("unverified journal receipt")
    directory=Path(directory)
    # Do not silently create the runtime root or a new arbitrary daemon:
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("caller must prepare a regular standalone journal directory")
    data=(json.dumps(receipt,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode("utf-8")
    digest=hashlib.sha256(data).hexdigest()
    key="|".join(str(receipt[x]) for x in
                 ("series_id","candidate_id","phase","event_key"))
    label=hashlib.sha256(key.encode("utf-8")).hexdigest()
    path=directory/(label+".json")
    try:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:
        if path.read_bytes()==data:
            return "IDEMPOTENT_IDENTICAL",path
        raise ValueError("conflicting event identity; never overwrite historical paper evidence")
    with os.fdopen(fd,"wb") as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())
    # The digest is recomputable from the immutable bytes; cloud sync must
    # mirror/check this receipt, never rewrite under a rotated Paper series.
    if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
        raise OSError("receipt durability validation failed")
    return "IMMUTABLE_NEW_RECEIPT",path


def funnel_summary(receipts:list[dict[str,Any]])->dict[str,Any]:
    """Unique candidates by phase, all gaps reported; no ex-post profit claim."""
    seen=set();counts=Counter();statuses=Counter();missing=set()
    reasons=Counter();per_episode=set();horizons=Counter()
    for r in receipts:
        if r.get("kind")!=KIND:
            raise ValueError("unknown journal item")
        pair=r["pair"];sid=r["series_id"];cid=r["candidate_id"]
        key=(sid,cid,r["phase"],r["event_key"])
        if key in seen: raise ValueError("duplicate paper event receipt")
        seen.add(key)
        counts[(sid,cid)]=1
        statuses[(r["phase"],r["result"])]+=1
        if r["result"] in {"SKIP","UNKNOWN","ERROR","CENSORED"}:
            missing.add((sid,cid,r["phase"],r["result"]))
        if r["phase"] in OUTCOME_PHASES:
            horizons[(r["phase"],r["result"])]+=1
        for code in set(r["data"].get("raw_reason_codes") or []):
            if isinstance(code,str) and CODE.fullmatch(code):
                reasons[code]+=1
        episode=r["data"].get("pair_six_hour_episode")
        if isinstance(episode,str) and episode:
            per_episode.add((pair,episode))
    return {
        "kind":"V3_EXPERIMENTAL_PAPER_FUNNEL_SUMMARY_V1",
        "unique_series_candidate_count":len(counts),
        "observed_event_count":len(seen),
        "phase_result_counts":{f"{p}:{status}":n for (p,status),n in sorted(statuses.items())},
        "reason_mentions_not_exclusive_causes":dict(reasons.most_common()),
        "technical_missing_unknown_or_censored_events":len(missing),
        "horizon_maturity":{f"{h}:{result}":n for (h,result),n in sorted(horizons.items())},
        "distinct_pair_six_hour_episodes":len(per_episode),
        "realized_net_pnl_sum_eur":None,
        "warning":"Raw MFE and subjective multi-reason model codes never become realizable net PnL",
    }
