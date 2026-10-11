#!/usr/bin/env python3
"""Manual finite V3-B shadow-5 research on active V2R4, NEVER a paper writer.

Consumes a user-approved maximum of 5 historical-origin EXTENDED opportunities
and 10 total model HTTP requests INCLUDING retries. Only fresh independently
observed second-leg evidence can trigger a same-snapshot matched model pair.
Never edits V2R4, its scheduler, Supabase, shadow registrations or active series.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import time
import urllib.parse

from paper_evaluator import evaluate
from paper_evaluator.v3_bounded_four_candidate_compare import (
    BudgetExhausted, checkpoint, discover_active_paper_runtime,
    freeze_runtime_provenance, safe_token, verify_frozen_strategy_spec)
from paper_evaluator.v3_entry_handoff_probe import attach_to_future_evaluator, utc
from paper_evaluator.v3_second_leg_policy_candidate_v1 import (
    propose_second_leg_review, MIN_BASE_BARS, CLOSED_BAR_SECONDS)
from paper_evaluator.successor_coin_entry_evidence_v1 import fetch_public_entry_evidence
from paper_context import build_context

EXPECTED_SERIES = "PAPER-V2R4-20261009T110135Z"
MAX_CASES = 5
MAX_MODEL_HTTP_ATTEMPTS = 10
MAX_PER_CASE = 2
MAX_WAIT_MINUTES = 90
MAX_SECOND_LEG_AGE_SECONDS = 4 * 3600
MIN_SECOND_LEG_AGE_SECONDS = (MIN_BASE_BARS + 1) * CLOSED_BAR_SECONDS
RECHECK_AT_MOST_ONCE_PER_CLOSED_15M_SECONDS = CLOSED_BAR_SECONDS
ELIGIBLE = "SECOND_LEG_STRUCTURE_SUPPORTS_NEW_FULL_REVIEW_ONLY"
USER_APPROVAL = "APPROVE V3-B SHADOW-5 / HTTP-10"
AUTHORITY_FILE = "research/v3/v3-b-shadow5-approval-20261011.json"


def verified_authorization(root: Path) -> dict:
    auth = json.loads((root / AUTHORITY_FILE).read_text("utf-8"))
    if (auth.get("status") != "USER_APPROVED_BOUNDED_MANUAL_SHADOW_ONLY"
            or auth.get("approval_label") != USER_APPROVAL
            or auth.get("max_distinct_candidates") != MAX_CASES
            or auth.get("max_model_http_attempts_including_retries") != MAX_MODEL_HTTP_ATTEMPTS
            or auth.get("no_orders") is not True
            or auth.get("no_v3_paper_cutover") is not True
            or auth.get("no_auto_extension") is not True):
        raise ValueError("V3_B_SHADOW5_AUTHORITY_MISMATCH")
    return auth


def journal_start(report: Path, series: str, now: datetime, wait_minutes: int) -> dict:
    data = {
        "kind": "V3_B_MANUAL_SHADOW5_HTTP10_V1",
        "status": "RUNNING",
        "approval": USER_APPROVAL,
        "active_v2r4_series": series,
        "started_at_utc": now.isoformat(),
        "wait_minutes": wait_minutes,
        "max_distinct_candidates": MAX_CASES,
        "max_model_http_attempts_including_retries": MAX_MODEL_HTTP_ATTEMPTS,
        "model_http_attempts_reserved": 0,
        "completed_matched_reviews": 0,
        "cases": [],
        "active_v2r4_changed": False,
        "v3_paper_writer_started": False,
        "shadow_service_started": False,
        "orders": 0,
        "real_money_actions": False,
        "economic_edge_proven": False,
        "no_auto_extension": True,
    }
    if report.exists():
        raise ValueError("EXISTING_V3B_SHADOW5_REPORT_NO_RESTART_OR_BUDGET_RESET")
    if not report.parent.is_dir():
        raise ValueError("RESEARCH_FOLDER_MISSING")
    # Atomic exclusive create of the durable budget journal BEFORE model access.
    with report.open("x", encoding="utf-8") as f:
        json.dump(data, f, sort_keys=True, separators=(",", ":"))
    return data


def select_original_extended(decisions: Path, queue: Path, control: dict,
                             now: datetime, seen: set[str]) -> list[tuple[dict, dict]]:
    """Read-only cohort, not cherry-picked from future returns; old model is anchor."""
    if not decisions.is_dir() or not queue.is_dir():
        return []
    result: list[tuple[dict, dict]] = []
    start = utc(control["series_started_at_utc"])
    for path in list(decisions.glob("*.json"))[-2000:]:
        try:
            row = json.loads(path.read_text("utf-8-sig"))
            cid = row["candidate_id"]
            d = row["decision"]
            age = (now - utc(row["candidate_event_time_utc"])).total_seconds()
            if (cid in seen or row.get("series_id") != control["series_id"]
                    or d.get("setup_lane") != "EXTENDED"
                    or d.get("decision") not in ("WAIT", "REJECT")
                    or not 0 <= age <= MAX_SECOND_LEG_AGE_SECONDS
                    or utc(row["candidate_event_time_utc"]) < start):
                continue
            candidate_path = queue / (cid + ".json")
            if not candidate_path.is_file():
                continue
            candidate = json.loads(candidate_path.read_text("utf-8-sig"))
            evaluate.validate_candidate(candidate, str(candidate_path))
            if (candidate["candidate_id"] != cid or candidate["pair"] != row["pair"]
                    or candidate["event_time_utc"] != row["candidate_event_time_utc"]):
                continue
            result.append((candidate, row))
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            continue
    # Deterministic, chronological; no hindsight/return-based selection.
    return sorted(result, key=lambda p: (p[0]["event_time_utc"], p[0]["candidate_id"]))



def select_due_second_leg(cohort: list[tuple[dict, dict]], existing: list[dict],
                          now: datetime) -> tuple[dict, dict, dict | None] | None:
    """At most 5 original cases; revisit SAME cases only after a new closed 15m.

    A not-yet-matured original candidate costs no case-slot and no model
    budget. A temporary non-reclaim/volume setup is NOT permanently discarded
    on its first sample. The same cohort is sampled at most once per 15 minutes;
    after 4h the original exits and can never re-enter this finite trial.
    """
    by_id={case["source_candidate_id"]:case for case in existing}
    for candidate, original in cohort:
        cid=candidate["candidate_id"]
        age=(now-utc(candidate["event_time_utc"])).total_seconds()
        if not MIN_SECOND_LEG_AGE_SECONDS <= age <= MAX_SECOND_LEG_AGE_SECONDS:
            continue
        found=by_id.get(safe_token(cid))
        if found is None:
            if len(existing) >= MAX_CASES:
                continue
            return candidate, original, None
        if found["status"] in (
            "MATCHED_RESEARCH_COMPLETE_NOT_PAPER_BUY",
            "STOP_BUDGET_CAP", "STOPPED_UNVERIFIED_MODEL_OR_INPUT"):
            continue
        last=found.get("last_eligibility_checked_at_utc")
        if last is not None and (now-utc(last)).total_seconds() < RECHECK_AT_MOST_ONCE_PER_CLOSED_15M_SECONDS:
            continue
        return candidate,original,found
    return None


def closed_15m_history(altname: str, observed: datetime) -> list[dict]:
    qs = urllib.parse.urlencode({"pair":altname, "interval":15})
    response = evaluate.http_json(
        "https://api.kraken.com/0/public/OHLC?" + qs,
        headers={"User-Agent":"v3-b-shadow5-readonly/1"})
    if not isinstance(response, dict) or response.get("error") or not isinstance(response.get("result"), dict):
        raise ValueError("PUBLIC_OHLC_MISSING")
    entries = [v for k,v in response["result"].items() if k != "last"]
    if len(entries) != 1 or not isinstance(entries[0], list):
        raise ValueError("AMBIGUOUS_KRAKEN_OHLC_PAIR")
    bars = []
    for row in entries[0][-22:]:
        start = datetime.fromtimestamp(int(row[0]),timezone.utc)
        if start + timedelta(minutes=15) > observed:
            continue  # Kraken may include the current unfinished candle.
        bars.append({"start_utc": start.isoformat(),
                     "open":float(row[1]), "high":float(row[2]),
                     "low":float(row[3]),"close":float(row[4])})
    return bars



def compact_gate_evidence(hint: dict, coin: dict, closed_bars: list[dict]) -> dict:
    """Keep enough pre-model reasons to triage UNKNOWN, without raw market/API data.

    A boolean-only, bounded diagnostic snapshot; no prompts, identities, keys,
    ticker values, raw Kraken candles or future outcome labels are persisted.
    """
    checks = hint.get("checks") or {}
    if not isinstance(checks, dict):
        checks = {}
    known_checks = (
        "base_1_to_3h_rebuilt",
        "closed_reclaim_above_prior_base_high",
        "reclaim_not_late_chase",
        "fresh_five_minute_continuation",
        "existing_v2r4_volume_confirmed",
        "liquid_eur_spread",
        "fresh_ask_not_far_past_reclaim",
    )
    result = {
        "second_leg_status": str(hint.get("status") or "UNKNOWN")[:90],
        "checks": {k: checks.get(k) if type(checks.get(k)) is bool else None
                   for k in known_checks},
        "observed_at_utc": coin.get("observed_at_utc"),
        "known_at_utc": coin.get("known_at_utc"),
        "coin_evidence_status": coin.get("status"),
        "closed_15m_bar_count": len(closed_bars),
        "latest_closed_15m_start_utc":
            closed_bars[-1].get("start_utc") if closed_bars else None,
    }
    frames = coin.get("frames") or {}
    result["required_coin_frames"] = {
        k: {"status": v.get("status"), "reason": v.get("reason"),
            "atr_status": v.get("atr_status") if k == "15" else None,
            "volume_ratio_status": v.get("volume_ratio_status") if k == "5" else None}
        for k in ("1", "5", "15")
        for v in [frames.get(k) if isinstance(frames.get(k), dict) else {}]
    }
    return result


def model_http_gate(journal: dict, report: Path, case: dict, http):
    def guarded(url, method="GET", headers=None, body=None, timeout=30):
        if url.startswith("https://api.openai.com/"):
            if (journal["model_http_attempts_reserved"] >= MAX_MODEL_HTTP_ATTEMPTS
                    or case["model_http_attempts_reserved"] >= MAX_PER_CASE):
                raise BudgetExhausted("V3B_APPROVED_MODEL_HTTP_CAP")
            journal["model_http_attempts_reserved"] += 1
            case["model_http_attempts_reserved"] += 1
            checkpoint(report, journal)
        return http(url,method,headers,body,timeout)
    return guarded


def main_run(trading_root: Path, code_root: Path, report: Path, wait_minutes: int,
             *, diagnose_only: bool = False, now_fn=lambda: datetime.now(timezone.utc),
             sleep_fn=time.sleep) -> dict:
    if not type(wait_minutes) is int or not 0 <= wait_minutes <= MAX_WAIT_MINUTES:
        raise ValueError("UNAPPROVED_WAIT_WINDOW")
    verified_authorization(code_root)
    if report.exists() and not diagnose_only:
        raise ValueError("EXISTING_REPORT_NO_RETRY")
    runtime, control = discover_active_paper_runtime(trading_root, EXPECTED_SERIES)
    freeze_runtime_provenance(runtime, code_root, control)
    verify_frozen_strategy_spec(json.loads((runtime/"paper_strategy_spec.json").read_text("utf-8")))
    initial = now_fn()
    if diagnose_only:
        items = select_original_extended(runtime/"paper_decisions", runtime/"handoff_queue",
                                         control,initial,set())
        return {"kind":"V3_B_SHADOW5_PREFLIGHT_V1","status":"READY_READ_ONLY_NO_MODEL_CALL",
                "original_extended_candidate_count":len(items),
                "note":"0 eligible is not an error; 1-3h live consolidation still required",
                "model_http_attempts_reserved":0,"orders":0,"paper_changed":False}
    journal = journal_start(report, control["series_id"],initial,wait_minutes)
    original_http = evaluate.http_json
    previous_model_key = os.environ.get("OPENAI_API_KEY")
    deadline = initial + timedelta(minutes=wait_minutes)
    try:
        while (journal["completed_matched_reviews"] < MAX_CASES
               and now_fn() <= deadline):
            runtime_now,control_now = discover_active_paper_runtime(trading_root,EXPECTED_SERIES)
            if runtime_now != runtime or control_now != control:
                raise ValueError("ACTIVE_PAPER_IDENTITY_CHANGED_STOP")
            freeze_runtime_provenance(runtime,code_root,control)
            observed_now = now_fn()
            cohort = select_original_extended(runtime/"paper_decisions",
                runtime/"handoff_queue",control,observed_now,set())
            selected = select_due_second_leg(cohort,journal["cases"],observed_now)
            if selected is None:
                remaining = (deadline-now_fn()).total_seconds()
                if remaining <= 0:
                    break
                sleep_fn(min(60,remaining))
                continue
            candidate, historical, case = selected
            cid = candidate["candidate_id"]
            if case is None:
                case = {"source_candidate_id":safe_token(cid),
                        "pair":safe_token(candidate["pair"]),
                        "original_decision":historical["decision"]["decision"],
                        "original_lane":historical["decision"]["setup_lane"],
                        "original_event_at_utc":candidate["event_time_utc"],
                        "model_http_attempts_reserved":0,
                        "eligibility_checks":0,
                        "status":"INPUT_PENDING"}
                journal["cases"].append(case)
                checkpoint(report,journal)
            phase = "PUBLIC_COIN_SECOND_LEG"
            try:
                ticker = evaluate.kraken_ticker(candidate["altname"])
                context = build_context(candidate,ticker)
                coin = fetch_public_entry_evidence(candidate["altname"],candidate["pair"])
                bars = closed_15m_history(candidate["altname"],now_fn())
                clock = now_fn().isoformat()
                hint = propose_second_leg_review(
                    candidate,historical["decision"],coin,ticker,bars,decision_at_utc=clock)
                case["second_leg_eligibility_status"]=hint["status"]
                case["eligibility_gate_evidence"]=compact_gate_evidence(hint,coin,bars)
                case["new_coin_known_at_utc"]=coin.get("known_at_utc")
                case["review_decision_clock_utc"]=clock
                case["last_eligibility_checked_at_utc"]=clock
                case["eligibility_checks"] += 1
                case["status"]="ELIGIBILITY_PENDING_NEXT_CLOSED_BAR_NO_BUY"
                checkpoint(report,journal)
                if hint["status"] != ELIGIBLE or hint.get("request_model_recheck_only") is not True:
                    continue
                # ONE policy delta: both use IDENTICAL later coin evidence,
                # the B arm alone receives the fresh second-leg review hint.
                enriched = attach_to_future_evaluator(candidate,context,coin,clock)
                with_hint = dict(enriched)
                with_hint["v3_b_new_independent_second_leg_review_only"] = {
                    "status":hint["status"],"checks":hint.get("checks",{}),
                    "base_high_eur":hint.get("base_high_eur_descriptive_only"),
                    "base_low_eur":hint.get("base_low_eur_descriptive_only"),
                    "old_candidate_is_historical":True,
                    "buy_requires_independent_full_assessment":True}
                # No live Paper mutation. Real model budget reserved pre-HTTP.
                secret = (trading_root/"Secrets"/"openai-api-key.txt").read_text("utf-8").strip()
                if len(secret) < 20:
                    raise ValueError("MODEL_SECRET_UNAVAILABLE")
                os.environ["OPENAI_API_KEY"]=secret
                secret = ""
                evaluate.http_json=model_http_gate(journal,report,case,original_http)
                phase="MATCHED_FULL_MODEL_BASELINE"
                raw_a,_=evaluate.call_evaluator(candidate,ticker,enriched,
                    json.loads((runtime/"paper_strategy_spec.json").read_text("utf-8")),control)
                base=evaluate.fail_safe_normalize(raw_a,ticker)
                case["matched_later_baseline_decision"]=base["decision"]
                case["status"]="MATCHED_BASELINE_COMPLETE"
                checkpoint(report,journal)
                phase="MATCHED_V3_B_SECOND_LEG_FULL_MODEL"
                raw_b,_=evaluate.call_evaluator(candidate,ticker,with_hint,
                    json.loads((runtime/"paper_strategy_spec.json").read_text("utf-8")),control)
                new=evaluate.fail_safe_normalize(raw_b,ticker)
                case["matched_later_v3_b_decision"]=new["decision"]
                case["candidate_stop_below_ask"]=bool(new["decision"]=="BUY_SCOUT"
                    and new.get("stop_eur") and new["stop_eur"] < ticker["ask"])
                case["candidate_stage2_above_ask"]=bool(new["decision"]=="BUY_SCOUT"
                    and new.get("stage2_trigger_eur") and new["stage2_trigger_eur"]>ticker["ask"])
                case["status"]="MATCHED_RESEARCH_COMPLETE_NOT_PAPER_BUY"
                journal["completed_matched_reviews"] += 1
                checkpoint(report,journal)
            except BudgetExhausted:
                case["status"]="STOP_BUDGET_CAP"
                journal["status"]="STOPPED_BUDGET_CAP_NO_AUTO_RETRY"
                checkpoint(report,journal)
                break
            except Exception as exc:
                # Never log raw API errors, raw model responses or keys.
                case["status"]="STOPPED_UNVERIFIED_MODEL_OR_INPUT"
                case["phase"]=phase
                case["failure_type"]=type(exc).__name__
                journal["status"]="STOPPED_UNVERIFIED_NO_AUTO_RETRY"
                checkpoint(report,journal)
                break
            finally:
                evaluate.http_json=original_http
                if previous_model_key is None:
                    os.environ.pop("OPENAI_API_KEY",None)
                else:
                    os.environ["OPENAI_API_KEY"]=previous_model_key
        else:
            journal["status"]="WINDOW_ELAPSED_OR_FIVE_ORIGINAL_CASES_REVIEWED"
        if journal["status"]=="RUNNING":
            journal["status"]="WINDOW_ELAPSED_OR_FIVE_ORIGINAL_CASES_REVIEWED"
        if journal["status"]=="WINDOW_ELAPSED_OR_FIVE_ORIGINAL_CASES_REVIEWED" and journal["completed_matched_reviews"] == 0:
            journal["status"]="COMPLETED_NO_ELIGIBLE_SECOND_LEG_MODEL_EVIDENCE"
    except Exception as exc:
        journal["status"]="STOPPED_PRECONDITION_NO_AUTO_RETRY"
        journal["failure_type"]=type(exc).__name__
    finally:
        evaluate.http_json=original_http
        if previous_model_key is None:
            os.environ.pop("OPENAI_API_KEY",None)
        else:
            os.environ["OPENAI_API_KEY"]=previous_model_key
        checkpoint(report,journal)
    return journal


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--trading-root",type=Path,required=True)
    ap.add_argument("--code-root",type=Path,required=True)
    ap.add_argument("--report",type=Path,required=True)
    ap.add_argument("--wait-minutes",type=int,default=90)
    ap.add_argument("--diagnose-only",action="store_true")
    args=ap.parse_args()
    try:
        result=main_run(args.trading_root,args.code_root,args.report,args.wait_minutes,
                        diagnose_only=args.diagnose_only)
        print("V3_B_SHADOW5_SUMMARY "+json.dumps({
            "kind":result["kind"],"status":result["status"],
            "model_http_attempts_reserved":result.get("model_http_attempts_reserved",0),
            "completed_matched_reviews":result.get("completed_matched_reviews",0),
            "original_extended_candidate_count":result.get("original_extended_candidate_count"),
            "cases":len(result.get("cases",[])), "report":str(args.report),
            "orders":0,"paper_changed":False},sort_keys=True),flush=True)
        return 0 if result["status"] in ("READY_READ_ONLY_NO_MODEL_CALL",
            "WINDOW_ELAPSED_OR_FIVE_ORIGINAL_CASES_REVIEWED",
            "COMPLETED_NO_ELIGIBLE_SECOND_LEG_MODEL_EVIDENCE") else 2
    except (OSError,ValueError,TypeError,KeyError):
        print("V3_B_SHADOW5_BLOCKED_BEFORE_MODEL_OR_ALREADY_RECORDED",flush=True)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
