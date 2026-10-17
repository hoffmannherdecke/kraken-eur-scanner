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
import argparse,json,re
from datetime import datetime,timedelta,timezone
from pathlib import Path
from typing import Any,Callable
from contextlib import contextmanager
import os
from paper_evaluator import evaluate
from paper_evaluator.v3_paper_minipc_one_candidate_v1 import REVISION
from paper_evaluator.successor_coin_entry_evidence_v1 import fetch_public_entry_evidence
from paper_evaluator.v3_paper_minipc_closed_1m_capture_v1 import (
    capture_public_1m,assemble,early_path_coverage,
)
from paper_evaluator.v3_paper_minipc_followup_v1 import record_horizon
from paper_evaluator.v3_paper_missed_opportunity_followup_v1 import followup_no_buy
from paper_evaluator.v3_paper_wait_observer_v1 import (
    candidate_receipts,observe_wait,finish_wait,
)
from paper_evaluator.v3_experimental_paper_journal_v1 import clock

def utc_now()->str:
    return datetime.now(timezone.utc).isoformat()

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
    origin=next((r for r in rows if r["phase"]=="SCANNER_CAPTURE"),None)
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
    now=clock(clock_now())
    # The original model decision is final if no BUY: followup even SKIP/WAIT/
    # source-UNKNOWN cases, never reclassify ex-post MFE as earned trades.
    capture_path=assemble(snapshots=capture_dir,pair=pair,
        entry_at_utc=origin["event_time_utc"],observed_at_utc=clock_now(),
        max_live_capture_lag_minutes=15)
    results["prospective_1m_bars"]=len(capture_path["closed_bars"])
    # Zero extra Kraken requests, receipts, or tasks: signal a missing
    # first minute while the event is still fresh instead of pretending
    # a later historic OHLC download was a live witnessed source path.
    results["early_1m_coverage"]=early_path_coverage(
        assembled=capture_path,entry_at_utc=origin["event_time_utc"],
        observed_at_utc=capture_path["captured_at_utc"])
    results["horizons"]={}
    buys=any(r["phase"]=="PAPER_FILL" and r["result"]=="PAPER_FILLED" for r in rows)
    for hrs in (6,24,72):
        if now<source_time+timedelta(hours=hrs):
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
    if (not isinstance(series_id,str)
            or re.fullmatch(r"PAPER-V3-[0-9]{8}T[0-9]{6}Z",series_id) is None
            or not all(isinstance(x,str) and re.fullmatch(pattern,x)
                       for x,pattern in (
                           (expected_repo_sha,r"[0-9a-f]{40}"),
                           (expected_bundle_sha256,r"[0-9a-f]{64}"),
                           (expected_strategy_sha256,r"[0-9a-f]{64}")))
            or not callable(read_active_series)):
        raise ValueError("exact release-pinned non-CANARY Paper identity required")
    # Never permit a non-CANARY tick from the unguarded standalone CLI.
    with _one_canary_owner(journal):
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
    origins=[r for r in rows if r["phase"]=="SCANNER_CAPTURE"
             and r["result"]=="SEEN"
             and r["data"].get("candidate_origin")=="SCANNER"]
    if len(origins)!=1 or origins[0]["event_key"]!="FIRST":
        return block("ORIGINAL_SCANNER_NOT_EXACT_NO_AUTOMATIC_RESTART")
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
