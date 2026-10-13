#!/usr/bin/env python3
"""V3 experimental Paper MINI-PC canary worker, NEVER trading/order endpoints.

This is a callable component of the FUTURE single-writer runtime, not a
scheduled process. One real Kraken EUR + full V3 model + P4 + immutable audit
path per candidate. Model HTTP forbidden without an independent positive,
numeric, one-shot, user-approved budget file. No V2R4 state touched.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from datetime import datetime,timezone
from pathlib import Path
from typing import Any,Callable

from paper_evaluator import evaluate
from paper_evaluator.successor_coin_entry_evidence_v1 import fetch_public_entry_evidence
from paper_evaluator.v3_p3_ab_five_bounded_research import verified_spot_metadata
from paper_evaluator.v3_experimental_paper_initial_review_v1 import propose_initial_full_review,ELIGIBLE
from paper_evaluator.v3_experimental_paper_model_prompt_v1 import build_v3_paper_full_model_prompt
from paper_evaluator.v3_full_entry_decision_candidate_v1 import validate_full_entry_decision
from paper_evaluator.v3_experimental_paper_journal_v1 import make_receipt,store_receipt_explicitly,clock as receipt_clock
from paper_evaluator.v3_paper_context_bridge_v1 import fuse_existing_sources
from paper_evaluator.v3_paper_positive_source_entry_v1 import (
    ELIGIBLE as POSITIVE_SOURCE_ELIGIBLE,
    assess_positive_source, make_source_candidate,
)

REVISION="V3-EXPERIMENTAL-PAPER-20261011-ALL-LESSONS-001"
MODEL_URL="https://api.openai.com/v1/responses"
MAX_ONE_SHOT_HTTP=1
APPROVED_MODEL="gpt-5.6-terra"
MAX_PROMPT_UTF8_BYTES=25000
MAX_OUTPUT_TOKENS=3000
MAX_ESTIMATED_COST_USD=0.15
# Official standard non-cached pricing, not an account-level charge stop.
# Even 1 UTF-8 byte per input token + 10% premium remains under $0.15.
PRICE_INPUT_PER_MILLION_USD=2.00
PRICE_OUTPUT_PER_MILLION_USD=12.00
MAX_ESTIMATED_USD=((MAX_PROMPT_UTF8_BYTES*PRICE_INPUT_PER_MILLION_USD+
                    MAX_OUTPUT_TOKENS*PRICE_OUTPUT_PER_MILLION_USD)/1_000_000)*1.10
assert MAX_ESTIMATED_USD<MAX_ESTIMATED_COST_USD

def now()->str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def read(path:Path)->dict:
    out=json.loads(Path(path).read_text("utf-8"))
    if not isinstance(out,dict):raise ValueError("canonical JSON object required")
    return out

def preflight_budget(approval:dict,series_id:str)->None:
    if (approval.get("kind")!="V3_MINIPC_SINGLE_CANDIDATE_MODEL_HTTP_USER_APPROVAL_V1"
            or approval.get("strategy_revision")!=REVISION
            or approval.get("series_id")!=series_id
            or approval.get("paper_only") is not True
            or approval.get("real_money_actions") is not False
            or type(approval.get("max_model_http_attempts_including_retries")) is not int
            or approval.get("max_model_http_attempts_including_retries")!=1
            or type(approval.get("max_candidates")) is not int
            or approval.get("max_candidates")!=1
            or not isinstance(approval.get("unique_approval_id"),str)
            or not 16<=len(approval["unique_approval_id"])<=128
            or approval.get("explicit_user_new_budget_approval") is not True
            or approval.get("consumed_pr186_budget") is not False
            or approval.get("model")!=APPROVED_MODEL
            or type(approval.get("max_input_utf8_bytes")) is not int
            or approval.get("max_input_utf8_bytes")!=MAX_PROMPT_UTF8_BYTES
            or type(approval.get("max_output_tokens")) is not int
            or approval.get("max_output_tokens")!=MAX_OUTPUT_TOKENS
            or type(approval.get("estimated_usd_ceiling")) not in (int,float)
            or approval.get("estimated_usd_ceiling")!=MAX_ESTIMATED_COST_USD):
        raise ValueError("NEW_USER_APPROVED_FIXED_BUDGET_NOT_PRESENT")
    try:
        expiry=datetime.fromisoformat(approval["expires_at_utc"].replace("Z","+00:00"))
        if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
            raise ValueError("expired or naive approval")
    except (KeyError,ValueError,TypeError,AttributeError):
        raise ValueError("EXPIRED_ONE_SHOT_API_BUDGET")

def reserve_before_http(d:Path,approval:dict,series_id:str,candidate_id:str,known_at:str)->Path:
    preflight_budget(approval,series_id)
    d=Path(d)
    if not d.is_dir() or d.is_symlink():raise ValueError("budget directory not created")
    # Independent one-off approval ID: no reuse for 5/10 calls or retries.
    serial=approval.get("unique_approval_id")
    if not isinstance(serial,str) or len(serial)<16:raise ValueError("approval ID required")
    # O_EXCL is atomic even after crash. A prior failed request is STILL spent.
    # The same approved budget can NEVER be retried automatically.
    label=hashlib.sha256((serial+"|"+series_id).encode()).hexdigest()
    path=d/(label+".reserved.json")
    body={"kind":"V3_PAPER_MODEL_HTTP_RESERVED_BEFORE_NETWORK_V1",
          "unique_approval_id":serial,"series_id":series_id,
          "candidate_id":candidate_id,"known_at_utc":known_at,
          "reserved_at_utc":now(),"maximum":1,
          "may_have_spent":True,"no_automatic_retry":True,
          "model":APPROVED_MODEL,"max_input_utf8_bytes":MAX_PROMPT_UTF8_BYTES,
          "max_output_tokens":MAX_OUTPUT_TOKENS,
          "estimated_usd_ceiling":MAX_ESTIMATED_COST_USD,
          "real_money_actions":False}
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as out:
        json.dump(body,out,sort_keys=True);out.flush();os.fsync(out.fileno())
    return path

def one_candidate(*,candidate:dict[str,Any],series_id:str,
                  local_receipts:Path,model_reservations:Path,
                  approval:dict|None=None,model_key:str|None=None,
                  existing_context:dict|None=None,allow_model:bool=False,
                  admit_staged_scanner_no_model:bool=False,
                  admit_staged_scanner_one_approved_model:bool=False,
                  acquire:Callable[[dict],tuple[dict,dict,dict]]|None=None,
                  model_client:Callable[[str,str],tuple[dict,dict]]|None=None,
                  clock:Callable[[],str]=now)->dict:
    if not series_id.startswith("PAPER-V3-") or candidate.get("pair","").endswith("/EUR") is False:
        raise ValueError("isolated V3 EUR PAPER series only")
    cid=candidate.get("candidate_id")
    if not isinstance(cid,str) or not cid:
        raise ValueError("real canonical candidate required")
    stamp=candidate["event_time_utc"]
    if not local_receipts.is_dir() or local_receipts.is_symlink():
        raise ValueError("independent V3 Paper journal directory must already exist")
    # The original intake journal precedes physical Kraken P0. The existing
    # zero-model continuation remains distinct from an explicitly authorized
    # ONE MODEL continuation; both require the same immutable staged Scanner
    # receipts and may never substitute an owner-source identity.
    if admit_staged_scanner_no_model and admit_staged_scanner_one_approved_model:
        raise ValueError("two staged V3 continuation modes cannot be combined")
    staged=admit_staged_scanner_no_model or admit_staged_scanner_one_approved_model
    if admit_staged_scanner_no_model and (
            allow_model or approval is not None or model_key is not None
            or candidate.get("entry_origin")!="SCANNER"):
        raise ValueError("staged no-model continuation forbids HTTP and owner promotion")
    if admit_staged_scanner_one_approved_model:
        if (not allow_model or not isinstance(model_key,str)
                or len(model_key)<20 or not isinstance(approval,dict)
                or candidate.get("entry_origin")!="SCANNER"):
            raise ValueError("staged model continuation requires explicit unique budget and Scanner")
        # Before even reading source, verify the existing exact one-shot
        # human/budget contract. Actual spend is separately reserved with
        # O_EXCL immediately before a single authorized model HTTP attempt.
        preflight_budget(approval,series_id)
    prior=[]
    for old in local_receipts.glob("*.json"):
        try:
            row=read(old)
        except (OSError,ValueError):
            raise ValueError("corrupt immutable V3 journal; human recovery required")
        if row.get("series_id")==series_id and row.get("candidate_id")==cid:
            prior.append(row)
    if staged:
        if any(row.get("pair")!=candidate["pair"]
               or row.get("event_time_utc")!=stamp
               or row.get("revision")!=REVISION for row in prior):
            raise ValueError("staged original candidate identity conflicts with immutable evidence")
        by_event={(row.get("phase"),row.get("event_key")):row for row in prior}
        recheck=candidate.get("deferred_recheck") is True
        wanted_key="DEFERREDRECHECK" if recheck else "FIRST"
        scanner=by_event.get(("SCANNER_CAPTURE",wanted_key),{})
        review=by_event.get(("FULL_REVIEW_ELIGIBILITY",wanted_key),{})
        regular=(len(prior)==2 and not recheck and len(by_event)==2)
        deferred_original=by_event.get(("SCANNER_CAPTURE","FIRST"),{})
        retry=(recheck and len(prior)==3 and len(by_event)==3
               and deferred_original.get("result")=="SKIP"
               and deferred_original.get("data",{}).get("candidate_origin")=="SCANNER"
               and deferred_original.get("data",{}).get("source_status")==
               "CAPACITY_DEFERRED_NOT_A_NEGATIVE_MARKET_DECISION")
        exact_staged=((regular or retry)
            and scanner.get("result")=="SEEN"
            and scanner.get("data",{}).get("candidate_origin")=="SCANNER"
            and scanner.get("data",{}).get("source_status")==
                "ORIGINAL_SELECTED_FOR_PRE_MODEL_REVIEW_ONLY"
            and review.get("result") in ("PASS","UNKNOWN"))
        if not exact_staged:
            return {"status":"NO_UNIQUE_UNPROCESSED_STAGED_SCANNER_NO_RECHECK",
                    "paper_only":True,"model_called":False,"orders":False}
        current=receipt_clock(clock())
        age=(current-receipt_clock(stamp)).total_seconds()
        if not 0<=age<=600:
            # No backdating an expired missed opportunity into a live review.
            expired=make_receipt(series_id=series_id,revision=REVISION,
                candidate_id=cid,pair=candidate["pair"],event_time_utc=stamp,
                known_at_utc=current.isoformat(),phase="SOURCE_INPUT",
                result="UNKNOWN",event_key="FRESHRECHECK",
                data={"phase_failure_stage":"STAGED_ORIGINAL_10M_WINDOW_EXPIRED",
                      "source_status":"ORIGINAL_TOO_OLD_FOR_LIVE_REVIEW"})
            store_receipt_explicitly(local_receipts,expired)
            return {"status":"STAGED_ORIGINAL_EXPIRED_JOURNALED_NO_KRAKEN_NO_MODEL",
                    "paper_only":True,"model_called":False,"orders":False}
    elif prior:
        return {"status":"V3_CANDIDATE_ALREADY_JOURNALED_NO_REPROCESS",
                "paper_only":True,"model_called":False}
    def receipt(phase:str,status:str,info:dict|None=None)->None:
        event=make_receipt(series_id=series_id,revision=REVISION,
            candidate_id=cid,pair=candidate["pair"],event_time_utc=stamp,
            known_at_utc=clock(),phase=phase,result=status,
            data=info or {},
            event_key="FRESHRECHECK" if staged else "FIRST")
        store_receipt_explicitly(local_receipts,event)
    # The original capture is already fsynced in the staged path. Never
    # overwrite its immutable FIRST event with a second incompatible payload.
    if not staged:
        receipt("SCANNER_CAPTURE","SEEN",{
            "candidate_origin":candidate.get("entry_origin","SCANNER"),
            "positive_source_name":candidate.get("positive_source_name"),
            "positive_source_event_id":candidate.get("positive_source_event_id")
        })
    positive_source=None
    if candidate.get("entry_origin")=="VERIFIED_POSITIVE_SOURCE_CATALYST":
        name=candidate.get("positive_source_name")
        sources=existing_context or {}
        snap=sources.get(name)
        positive_source=assess_positive_source(
            pair=candidate["pair"],source_name=name,snapshot=snap,
            decision_at_utc=clock(),market_move=sources.get("dynamic_move_radar"))
        if positive_source["status"]==POSITIVE_SOURCE_ELIGIBLE:
            try:
                canonical=make_source_candidate(
                    pair=candidate["pair"],kraken_altname=candidate["altname"],
                    source_name=name,snapshot=snap,decision_at_utc=clock(),
                    market_move=sources.get("dynamic_move_radar"))
                if any(canonical[k]!=candidate.get(k) for k in
                       ("candidate_id","event_time_utc","positive_source_event_id")):
                    raise ValueError("forged catalyst event identity")
            except (ValueError,KeyError,TypeError):
                positive_source={**positive_source,"status":"INVALID_SOURCE_CANDIDATE_IDENTITY"}
        ppass=positive_source["status"]==POSITIVE_SOURCE_ELIGIBLE
        receipt("SOURCE_CATALYST","PASS" if ppass else "SKIP",{
            "positive_source_name":name,
            "positive_source_event_id":candidate.get("positive_source_event_id"),
            "positive_source_status":positive_source["status"],
            "positive_source_reason":positive_source.get("positive_reason"),
            "positive_source_owner":positive_source.get("source_owner"),
            "positive_coin_impact_mechanism":positive_source.get("impact_mechanism"),
            "independent_source_entry":True,
        })
        if not ppass:
            return {"status":"SOURCE_CATALYST_NOT_VERIFIED_NO_MODEL",
                    "source_reason":positive_source["status"],
                    "model_called":False,"paper_only":True}
    elif candidate.get("entry_origin") not in (None,"SCANNER"):
        receipt("SOURCE_CATALYST","SKIP",
                {"positive_source_status":"UNSUPPORTED_CANDIDATE_ORIGIN"})
        return {"status":"UNSUPPORTED_ORIGIN_NO_MODEL",
                "model_called":False,"paper_only":True}
    try:
        if acquire is None:
            altname=candidate["altname"]
            if not isinstance(altname,str) or not altname.isalnum():
                raise ValueError("verified Kraken altname required")
            coin=fetch_public_entry_evidence(altname,candidate["pair"])
            quote=evaluate.kraken_ticker(altname)
            quote["pair"]=candidate["pair"];quote["observed_at_utc"]=clock()
            meta=verified_spot_metadata(altname,candidate["pair"],quote)
        else:
            coin,quote,meta=acquire(candidate)
        evidence_status=coin.get("status","UNKNOWN")
        frames=coin.get("frames") or {}
        src={"source_status":evidence_status,
             "input_known_at_utc":coin.get("known_at_utc"),
             "ask_eur":quote.get("ask"),"bid_eur":quote.get("bid"),
             "spread_pct":quote.get("spread_pct"),
             "kraken_online_spot_eur":meta.get("status")=="online",
             "source_pair_metadata_status":meta.get("status")}
        for label,key in (("1m","1"),("5m","5"),("15m","15")):
            v=frames.get(key) or {}
            src["frame_status_"+label]=v.get("status")
            src["frame_closed_end_"+label]=v.get("last_closed_bar_end_utc")
            src["frame_close_"+label+"_eur"]=v.get("closed_close_eur")
            src["frame_volume_ratio_"+label]=v.get("volume_ratio_prior_5")
        src["atr14_15m_eur"]=(frames.get("15") or {}).get("atr14_eur")
        src["structural_low_15m_eur"]=(frames.get("15") or {}).get("recent_8bar_low_eur")
        receipt("SOURCE_INPUT","PASS" if evidence_status=="COMPLETE" else "UNKNOWN",src)
    except Exception as exc:
        receipt("SOURCE_INPUT","ERROR",
                {"phase_failure_class":type(exc).__name__,
                 "phase_failure_stage":"KRAKEN_COIN_TICKER_ASSETPAIRS"})
        return {"status":"UNKNOWN_SOURCE_INPUT_FAILED","paper_only":True}
    requested_at=clock()
    context=fuse_existing_sources(existing_context or {},decision_at_utc=requested_at,
                                  pair=candidate["pair"])
    eligibility=propose_initial_full_review(candidate,coin,quote,meta,
                                             decision_at_utc=requested_at)
    if positive_source and positive_source["status"]==POSITIVE_SOURCE_ELIGIBLE:
        eligibility["source_catalyst_qualified"]=True
        eligibility["source_catalyst_event_id"]=positive_source["source_event_id"]
    receipt("FULL_REVIEW_ELIGIBILITY",
            "PASS" if eligibility["status"]==ELIGIBLE else "SKIP",
            {"review_status":eligibility["status"],"review_family":(
                 "SOURCE_CATALYST_INDEPENDENT" if positive_source else
                 "FIRST_SCANNER_EARLY_REVIEW"),
             "candidate_origin":candidate.get("entry_origin","SCANNER"),
             "positive_source_name":candidate.get("positive_source_name"),
             "positive_source_event_id":candidate.get("positive_source_event_id"),
             "positive_source_status":positive_source["status"] if positive_source else None,
             "positive_source_reason":positive_source.get("positive_reason") if positive_source else None,
             "review_checks":eligibility.get("checks") or {},
             "optional_context_states":{k:v["state"] for k,v in context["sources"].items()},
             "market_phase_evidence":context["sources"]["market_phase_radar"],
             "smart_money_evidence":context["sources"]["smart_money_h10"],
             "polymarket_evidence":context["sources"]["polymarket_h11"],
             "news_sentiment_evidence":context["sources"]["news_sentiment"],
             "source_management_evidence":context["sources"]["source_stewardship"],
             # Four PR251 streams are already included in the existing
             # optional_context_states journal field. No SHA-pinned journal
             # schema changes; source values enter only the P-I-T model prompt.
             "phase_failure_stage":eligibility.get("validation_stage")})
    if eligibility["status"]!=ELIGIBLE:
        return {"status":"NO_ELIGIBLE_INITIAL_V3_MODEL_REVIEW",
                "review_status":eligibility["status"],"paper_only":True}
    # Preflight is NON-WRITING except audit receipts, no charge and no model.
    if not allow_model:
        receipt("MODEL_REQUEST","SKIP",{"source_status":"PREFLIGHT_NO_MODEL"})
        return {"status":"V3_PAPER_REAL_KRAKEN_PIT_PREFLIGHT_PASS_MODEL_NOT_CALLED",
                "paper_only":True,"model_called":False}
    if approval is None or not model_key or len(model_key)<20:
        receipt("MODEL_REQUEST","UNKNOWN",
                {"phase_failure_stage":"NEW_USER_APPROVED_API_BUDGET_OR_KEY_MISSING"})
        return {"status":"MODEL_SPEND_BLOCKED","paper_only":True}
    prompt=build_v3_paper_full_model_prompt(
        candidate=candidate,eligibility=eligibility,entry_evidence=coin,
        ticker=quote,pair_metadata=meta,decision_at_utc=requested_at,
        optional_context={"kind":"V3_PAPER_EXISTING_RESEARCH_CONTEXT_BRIDGE_V1",
                          "raw_snapshots":existing_context or {}})
    # Price bound must be checked BEFORE irreversible one-time API reservation.
    # Input size is an intentionally pessimistic proxy for token upper bound,
    # not a real-time billing estimate; no tools, retries, or batch jobs.
    prompt_bytes=len(prompt.encode("utf-8"))
    if prompt_bytes>MAX_PROMPT_UTF8_BYTES:
        receipt("MODEL_REQUEST","UNKNOWN",{
            "phase_failure_stage":"PROMPT_TOO_LARGE_NO_API_SPEND"})
        return {"status":"MODEL_PROMPT_SIZE_GATE_NO_SPEND","paper_only":True,
                "model_called":False}
    try:
        reservation=reserve_before_http(model_reservations,approval,series_id,cid,
                                        coin["known_at_utc"])
    except (ValueError,FileExistsError,OSError):
        receipt("MODEL_REQUEST","UNKNOWN",
                {"phase_failure_stage":"HTTP_ALREADY_RESERVED_OR_BUDGET_DENIED"})
        return {"status":"MODEL_HTTP_NOT_AUTHORIZED_OR_ALREADY_RESERVED","paper_only":True}
    receipt("MODEL_REQUEST","PASS",{
        "input_fingerprint_sha256":hashlib.sha256(prompt.encode()).hexdigest(),
        "model_http_attempts_reserved":1,
        "model_request_at_utc":clock()})
    try:
        if model_client is None:
            result=evaluate.http_json(
                MODEL_URL,"POST",
                {"Authorization":"Bearer "+model_key,
                 "Content-Type":"application/json",
                 "User-Agent":"v3-paper-prospective-canary/1"},
                json.dumps({
                    "model":APPROVED_MODEL,
                    "input":prompt,
                    "max_output_tokens":MAX_OUTPUT_TOKENS,
                    "reasoning":{"effort":"low"},
                    "text":{"format":{"type":"json_object"}},
                    "store":False,
                }).encode(),70)
            if result.get("status")!="completed":
                raise ValueError("one-shot API response incomplete")
            raw=evaluate.parse_json_text(evaluate.extract_text(result))
            metadata={"response_id":result.get("id"),"model":result.get("model")}
        else:
            raw,metadata=model_client(prompt,model_key)
        returned_at=clock()
        if not isinstance(raw,dict):raise ValueError("model JSON object required")
        receipt("MODEL_RESPONSE","PASS",{
            "model_response_at_utc":returned_at,
            "model_response_id":str(metadata.get("response_id") or "")[:150],
            "model_name":str(metadata.get("model") or "")[:80],
            "raw_model_decision":raw.get("decision"),
            "raw_reason_codes":[str(c)[:90] for c in (raw.get("reason_codes") or [])[:8]],
            "raw_stop_eur":raw.get("stop_eur"),"raw_stage2_trigger_eur":raw.get("stage2_trigger_eur"),
            "raw_watch_conditions":raw.get("watch_conditions")})
    except Exception as exc:
        receipt("MODEL_ERROR","ERROR",{
            "phase_failure_class":type(exc).__name__,
            "phase_failure_stage":"ONE_MODEL_HTTP_NO_RETRY"})
        return {"status":"MODEL_FAILED_HTTP_ATTEMPT_BUDGET_CONSUMED",
                "paper_only":True,"model_retries":0}
    # Never trust model's own clock, candidate identity or execution authority.
    model=dict(raw,candidate_id=cid,pair=candidate["pair"],
               decision_at_utc=returned_at)
    validated=validate_full_entry_decision(
        eligibility,candidate,coin,quote,meta,model,
        decision_at_utc=returned_at,slippage_pct_each_side=0.08)
    receipt("P4_VALIDATION",
        "BUY_SCOUT" if validated["decision"]=="BUY_SCOUT" else
        ("WAIT" if validated["decision"]=="WAIT" else "REJECT" if
         validated["decision"]=="REJECT" else "UNKNOWN"),
        {"p4_status":validated["status"],"p4_decision":validated["decision"],
         "candidate_origin":candidate.get("entry_origin","SCANNER"),
         "positive_source_name":candidate.get("positive_source_name"),
         "positive_source_event_id":candidate.get("positive_source_event_id"),
         "positive_source_status":positive_source["status"] if positive_source else None,
         "raw_reason_codes":[str(c)[:90] for c in (raw.get("reason_codes") or [])[:8]],
         "ask_eur":quote["ask"],"validated_stop_eur":validated.get("stop_eur"),
         "validated_stage2_eur":validated.get("stage2_trigger_eur"),
         "total_cost_pct":validated.get("total_round_trip_cost_pct")})
    if validated["decision"]=="WAIT":
        receipt("WAIT_WATCH","WAIT",{
            "raw_wait_ttl_minutes":model.get("ttl_minutes"),
            "raw_watch_conditions":model.get("watch_conditions")})
    if validated["decision"]=="BUY_SCOUT":
        receipt("PAPER_FILL","PAPER_FILLED",{
            "paper_entry_ask_eur":validated["execution_ask_eur"],
            "paper_entry_qty":round(50/validated["execution_ask_eur"],10),
            "paper_entry_fee_eur":round(50*0.006,6),
            "validated_stop_eur":validated["stop_eur"],
            "validated_stage2_eur":validated["stage2_trigger_eur"],
            "stage2_ttl_minutes":validated["stage2_ttl_minutes"],
            "total_cost_pct":validated["total_round_trip_cost_pct"],
            "source_status":"ASSUMED_VIRTUAL_PAPER_ASK_NOT_REAL_EXCHANGE_FILL"})
        for h in (6,24,72):
            receipt(f"FOLLOWUP_{h}H","PENDING",{"followup_source":"KRAKEN_1M_PENDING"})
    return {"status":"V3_CANARY_MODEL_P4_RECORDED_NO_PAPER_ACTIVATION",
            "p4_status":validated["status"],"p4_decision":validated["decision"],
            "candidate_id":cid,"series_id":series_id,
            "model_http_attempts_reserved":1,"paper_only":True,
            "model_retries":0,"orders":False,"real_money_actions":False,
            "has_actual_trade_writer":False}

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--candidate",type=Path,required=True)
    p.add_argument("--series",required=True)
    p.add_argument("--journal",type=Path,required=True)
    p.add_argument("--budget-directory",type=Path,required=True)
    p.add_argument("--optional-sources",type=Path)
    p.add_argument("--approved-one-model-call",type=Path)
    p.add_argument("--admit-staged-scanner-no-model",action="store_true")
    p.add_argument("--admit-staged-scanner-one-approved-model",action="store_true")
    p.add_argument("--model-key-file",type=Path)
    a=p.parse_args()
    sources=read(a.optional_sources) if a.optional_sources else {}
    approval=read(a.approved_one_model_call) if a.approved_one_model_call else None
    key=a.model_key_file.read_text("utf-8").strip() if a.model_key_file else None
    res=one_candidate(candidate=read(a.candidate),series_id=a.series,
                      local_receipts=a.journal,model_reservations=a.budget_directory,
                      approval=approval,model_key=key,existing_context=sources,
                      allow_model=bool(a.approved_one_model_call),
                      admit_staged_scanner_no_model=a.admit_staged_scanner_no_model,
                      admit_staged_scanner_one_approved_model=
                          a.admit_staged_scanner_one_approved_model)
    print(json.dumps(res,sort_keys=True))
    return 0 if not res["status"].startswith("MODEL_FAILED") else 1

if __name__=="__main__":
    raise SystemExit(main())
