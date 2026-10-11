#!/usr/bin/env python3
"""One explicitly approved finite V3 P3 Standard/Experimental research trial.

Manual Mini-PC only. No orders, Paper writer, Supabase writes, service, or
scheduled model work. Old V2R4 remains the only active PAPER strategy.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from paper_context import build_context
from paper_evaluator import evaluate
from paper_evaluator.successor_coin_entry_evidence_v1 import fetch_public_entry_evidence
from paper_evaluator.v3_entry_handoff_probe import attach_to_future_evaluator, utc
from paper_evaluator.v3_bounded_four_candidate_compare import (
    BudgetExhausted, checkpoint, discover_active_paper_runtime,
    freeze_runtime_provenance, safe_token, verify_frozen_strategy_spec,
)
from paper_evaluator.v3_b_bounded_shadow_five import closed_15m_history
from paper_evaluator.v3_continuity_fresh_review_candidate_v1 import (
    ELIGIBLE as STANDARD_ELIGIBLE, propose_continuity_fresh_review,
)
from paper_evaluator.v3_experimental_continuity_volume_review_v1 import (
    ELIGIBLE as EXPERIMENTAL_ELIGIBLE, propose_experimental_continuity_review,
)
from paper_evaluator.v3_full_entry_decision_candidate_v1 import validate_full_entry_decision

APPROVAL = "research/v3/v3-p3-ab-five-approval-20261011.json"
APPROVAL_LABEL = "APPROVE V3-P3 STANDARD-EXPERIMENTAL SAME-CLOCK 5 QUALIFIED HTTP10 6H PAPER-ONLY"
EXPECTED_SERIES = "PAPER-V2R4-20261009T110135Z"
REPORT_NAME = "v3-p3-ab-five-http10-6h-20261011.json"
MAX_SETUPS = 5
MAX_HTTP = 10
MAX_PER_SETUP_HTTP = 2
MAX_MINUTES = 360
MAX_ORIGINAL_AGE_SECONDS = 900
SLEEP_SECONDS = 60
SLIPPAGE_PCT_EACH_SIDE = 0.08  # conservative pre-registered research assumption, not an observed fill


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def require_authority(root: Path) -> dict:
    a = json.loads((root / APPROVAL).read_text("utf-8"))
    required = {
        "kind": "V3_P3_STANDARD_EXPERIMENTAL_BOUND_RESEARCH_APPROVAL_V1",
        "approval_label": APPROVAL_LABEL,
        "status": "USER_APPROVED_ONE_TIME_BOUNDED_MANUAL_RESEARCH",
        "max_qualified_setups": MAX_SETUPS,
        "max_model_http_attempts_including_retries": MAX_HTTP,
        "max_model_http_attempts_per_setup_including_retries": MAX_PER_SETUP_HTTP,
        "max_observation_minutes": MAX_MINUTES,
        "expected_v2r4_source_series": EXPECTED_SERIES,
    }
    if any(a.get(k) != v or type(a.get(k)) is not type(v) for k, v in required.items()):
        raise ValueError("EXPLICIT_V3_P3_AB_APPROVAL_MISMATCH")
    required_guards = (
        "no_real_money", "no_orders", "no_paper_writer", "no_v3_paper_cutover",
        "no_v2r4_tuning", "no_new_scheduler", "no_new_daemon",
        "no_concurrent_strategy_changing_shadow", "no_auto_retry_or_extension",
        "h3_h6_inactive", "required_fresh_kraken_spot_eur_1m_5m_15m",
        "requires_actual_full_model_assessment",
    )
    if any(a.get("hard_guards", {}).get(k) is not True for k in required_guards):
        raise ValueError("EXPLICIT_V3_P3_AB_SAFETY_GUARD_MISSING")
    if any(a["hard_guards"].get(k) != v for k, v in (
            ("fee_pct_each_side", 0.6), ("scout_eur", 50), ("stage2_eur", 50))):
        raise ValueError("EXPLICIT_V3_P3_AB_COST_OR_SIZE_DRIFT")
    return a


def guarded_http(journal: dict, report: Path, case: dict, real_http):
    """Atomic budget reservation precedes ALL model HTTP requests, retries too."""
    def call(url, method="GET", headers=None, body=None, timeout=30):
        if url.startswith("https://api.openai.com/"):
            if (journal["model_http_attempts_reserved"] >= MAX_HTTP
                    or case["model_http_attempts_reserved"] >= MAX_PER_SETUP_HTTP):
                raise BudgetExhausted("EXPLICIT_V3_P3_AB_MODEL_BUDGET_EXHAUSTED")
            journal["model_http_attempts_reserved"] += 1
            case["model_http_attempts_reserved"] += 1
            checkpoint(report, journal)
        return real_http(url, method, headers, body, timeout)
    return call


def verified_spot_metadata(altname: str, pair: str, ticker: dict) -> dict:
    """Do not mint 'online Spot EUR' from a suffix or cached status flag."""
    query = urllib.parse.urlencode({"pair": altname})
    data = evaluate.http_json(
        "https://api.kraken.com/0/public/AssetPairs?" + query,
        headers={"User-Agent": "v3-p3-paper-research/1"})
    entries = data.get("result") if isinstance(data, dict) and not data.get("error") else None
    if not isinstance(entries, dict) or len(entries) != 1:
        raise ValueError("KRAKEN_ASSET_PAIRS_NOT_UNIQUE")
    row = next(iter(entries.values()))
    if (not isinstance(row, dict) or row.get("status") != "online"
            or row.get("wsname") != pair
            or row.get("quote") not in ("ZEUR", "EUR")):
        raise ValueError("ONLINE_KRAKEN_SPOT_EUR_NOT_PROVEN")
    ordermin = float(row["ordermin"])
    costmin = float(row.get("costmin") or 0)
    ask = float(ticker["ask"])
    if (not all(math.isfinite(x) for x in (ordermin, costmin, ask))
            or min(ordermin, ask) <= 0 or costmin < 0
            or 50.0 < costmin or 50.0 / ask < ordermin):
        raise ValueError("KRAKEN_50_EUR_ORDER_MINIMUM_NOT_PASSED")
    return {"pair": pair, "status": "online", "spot": True, "quote": "EUR",
            "minimum_order_passed": True, "observed_at_utc": now_utc().isoformat()}


def select_fresh_continuity(runtime: Path, control: dict, started: datetime,
                            now: datetime, visited: set[str]) -> list[tuple[dict, dict]]:
    """Pre-decision chronologically ordered source cohort, never select by later MFE."""
    rows = []
    decisions = runtime / "paper_decisions"
    queue = runtime / "handoff_queue"
    if not decisions.is_dir() or not queue.is_dir():
        return rows
    for path in sorted(decisions.glob("*.json"), key=lambda p: (p.stat().st_mtime, p.name),
                       reverse=True)[:500]:
        try:
            item = json.loads(path.read_text("utf-8-sig"))
            cid = item["candidate_id"]
            d = item["decision"]
            if cid in visited or item.get("series_id") != control["series_id"]:
                continue
            if d.get("setup_lane") != "CONTINUITY" or d.get("decision") not in ("WAIT", "REJECT"):
                continue
            original_at = utc(item["candidate_event_time_utc"])
            if not (max(started, utc(control["series_started_at_utc"])) <= original_at <= now
                    and 0 <= (now - original_at).total_seconds() <= MAX_ORIGINAL_AGE_SECONDS):
                continue
            file = queue / (cid + ".json")
            if not file.is_file():
                continue
            candidate = json.loads(file.read_text("utf-8-sig"))
            evaluate.validate_candidate(candidate, str(file))
            if (candidate["candidate_id"] != cid or candidate["pair"] != item["pair"]
                    or candidate["event_time_utc"] != item["candidate_event_time_utc"]):
                continue
            rows.append((candidate, d))
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            continue
    return sorted(rows, key=lambda x: (x[0]["event_time_utc"], x[0]["candidate_id"]))


def run_one(trading_root: Path, code_root: Path, *, minutes: int = MAX_MINUTES,
            dry_run: bool = False, now_fn=now_utc, sleep_fn=time.sleep) -> dict:
    if type(minutes) is not int or not 0 <= minutes <= MAX_MINUTES:
        raise ValueError("UNAPPROVED_V3_P3_AB_TIME_WINDOW")
    require_authority(code_root)
    report = trading_root / "Research" / REPORT_NAME
    if report.exists():
        raise ValueError("EXISTING_V3_P3_AB_JOURNAL_NO_RESTART_NO_BUDGET_RESET")
    runtime, control = discover_active_paper_runtime(trading_root, EXPECTED_SERIES)
    freeze_runtime_provenance(runtime, code_root, control)
    spec = json.loads((runtime / "paper_strategy_spec.json").read_text("utf-8"))
    verify_frozen_strategy_spec(spec)
    if dry_run:
        return {"kind": "V3_P3_AB_FIVE_PREFLIGHT_V1", "status": "PREFLIGHT_PASS_NO_MODEL",
                "series": control["series_id"], "approval_verified": True,
                "model_http_attempts_reserved": 0, "paper_changed": False, "orders": 0}
    if not report.parent.is_dir():
        raise ValueError("RESEARCH_REPORT_DIRECTORY_REQUIRED")
    start = now_fn()
    j = {"kind": "V3_P3_AB_FIVE_HTTP10_6H_RESEARCH_V1", "status": "RUNNING",
         "approval_label": APPROVAL_LABEL, "started_at_utc": start.isoformat(),
         "source_series": control["series_id"], "observation_minutes": minutes,
         "max_qualified_setups": MAX_SETUPS,
         "max_model_http_attempts_including_retries": MAX_HTTP,
         "model_http_attempts_reserved": 0, "qualified_setups": 0,
         "cases": [], "diagnostics": {"observed_origins": 0, "no_review": 0,
                                       "invalid_input": 0, "metadata_fail": 0},
         "no_automatic_retry": True, "paper_changed": False, "paper_writer_started": False,
         "orders": 0, "real_money_actions": False,
         "actual_6h_24h_net_outcomes_verified": False, "economic_edge_proven": False}
    with report.open("x", encoding="utf-8") as f:
        json.dump(j, f, sort_keys=True)
    original_http = evaluate.http_json
    previous_key = os.environ.get("OPENAI_API_KEY")
    visited: set[str] = set()
    used_pair_clock: dict[str, datetime] = {}
    deadline = start + timedelta(minutes=minutes)
    try:
        while now_fn() <= deadline and j["qualified_setups"] < MAX_SETUPS:
            another, latest = discover_active_paper_runtime(trading_root, EXPECTED_SERIES)
            if another != runtime or latest != control:
                raise ValueError("V2R4_SERIES_CHANGED_STOP_NO_MODEL")
            freeze_runtime_provenance(runtime, code_root, control)
            origins = select_fresh_continuity(runtime, control, start, now_fn(), visited)
            if not origins:
                remain = (deadline - now_fn()).total_seconds()
                if remain <= 0:
                    break
                sleep_fn(min(SLEEP_SECONDS, remain))
                continue
            candidate, baseline_decision = origins[0]
            cid, pair = candidate["candidate_id"], candidate["pair"]
            # Wait until a genuinely NEW 15m bar closes after this candidate.
            # Do not mark a still-open candidate as permanently visited.
            last_15m_end = int(now_fn().timestamp()) // 900 * 900
            if utc(candidate["event_time_utc"]).timestamp() >= last_15m_end:
                remain = (deadline - now_fn()).total_seconds()
                if remain <= 0:
                    break
                sleep_fn(min(SLEEP_SECONDS, remain))
                continue
            visited.add(cid)
            j["diagnostics"]["observed_origins"] += 1
            try:
                # Existing optional market/source context cannot become a second hard veto.
                current = evaluate.kraken_ticker(candidate["altname"])
                context = build_context(candidate, current)
                coin = fetch_public_entry_evidence(candidate["altname"], pair)
                bars = closed_15m_history(candidate["altname"], now_fn())
                # Execution ticker comes strictly AFTER evidence acquisition.
                current = evaluate.kraken_ticker(candidate["altname"])
                current["pair"] = pair
                current["observed_at_utc"] = now_fn().isoformat()
                model_context = attach_to_future_evaluator(
                    candidate, context, coin, current["observed_at_utc"])
                meta = verified_spot_metadata(candidate["altname"], pair, current)
                same_clock = now_fn().isoformat()
                standard = propose_continuity_fresh_review(
                    candidate, baseline_decision, coin, current, bars,
                    decision_at_utc=same_clock)
                experiment = propose_experimental_continuity_review(
                    candidate, baseline_decision, coin, current, bars,
                    decision_at_utc=same_clock)
            except Exception:
                j["diagnostics"]["invalid_input"] += 1
                checkpoint(report, j)
                continue
            is_standard = standard.get("status") == STANDARD_ELIGIBLE
            is_experimental = experiment.get("status") == EXPERIMENTAL_ELIGIBLE
            if not (is_standard or is_experimental):
                j["diagnostics"]["no_review"] += 1
                checkpoint(report, j)
                continue
            previous_clock = used_pair_clock.get(pair)
            if previous_clock and 0 <= (utc(same_clock) - previous_clock).total_seconds() < 6 * 3600:
                continue
            used_pair_clock[pair] = utc(same_clock)
            if (now_fn() - utc(coin["known_at_utc"])).total_seconds() > 120:
                j["diagnostics"]["invalid_input"] += 1
                checkpoint(report, j)
                continue
            hint = standard if is_standard else experiment
            selected_arm = "STANDARD" if is_standard else "EXPERIMENTAL_INCREMENTAL"
            c = {"candidate_id": safe_token(cid), "pair": safe_token(pair),
                 "original_event_at_utc": candidate["event_time_utc"],
                 "decision_at_utc": same_clock, "known_at_utc": coin["known_at_utc"],
                 "standard_status": standard.get("status"),
                 "experimental_status": experiment.get("status"),
                 "eligible_arm": selected_arm, "model_http_attempts_reserved": 0,
                 "status": "QUALIFIED_PENDING_MODEL"}
            j["cases"].append(c)
            j["qualified_setups"] += 1
            checkpoint(report, j)
            phase = "MODEL_AUTHORITY"
            try:
                secret = (trading_root / "Secrets" / "openai-api-key.txt").read_text("utf-8").strip()
                if len(secret) < 20:
                    raise ValueError("MODEL_SECRET_NOT_PRESENT")
                os.environ["OPENAI_API_KEY"] = secret
                secret = ""
                enriched = dict(model_context)
                enriched["kraken_execution_ticker"] = current
                # Only a research review flag. NEVER feed eligibility as an order.
                enriched["v3_p3_inactive_full_model_review_only"] = {
                    "status": hint["status"], "one_change": selected_arm,
                    "original_v2r4_decision_unchanged": True,
                    "full_risk_and_fee_validation_required": True,
                    "no_execution_authority": True}
                evaluate.http_json = guarded_http(j, report, c, original_http)
                phase = "FULL_MODEL"
                raw, metadata = evaluate.call_evaluator(candidate, current, enriched, spec, control)
                received_at = now_fn().isoformat()
                # Raw model reply is not trusted and is not persisted.
                normalized = evaluate.fail_safe_normalize(raw, current)
                full_assessment = {
                    "candidate_id": cid, "pair": pair, "decision_at_utc": received_at,
                    "decision": normalized["decision"], "setup_lane": normalized["setup_lane"],
                    "reason_codes": normalized["reason_codes"],
                    # Anti-chase is a positive deterministic structural assertion,
                    # not a self-certification in the model's raw prose.
                    "anti_chase_passed": bool(is_standard or is_experimental),
                    "stop_eur": normalized.get("stop_eur"),
                    "stage2_trigger_eur": normalized.get("stage2_trigger_eur"),
                    "stage2_ttl_minutes": normalized.get("stage2_ttl_minutes"),
                    "expected_remaining_move_pct": normalized.get("expected_remaining_move_pct"),
                    "ttl_minutes": normalized.get("ttl_minutes"),
                    "watch_conditions": normalized.get("watch_conditions"),
                }
                phase = "FULL_P4_RISK_VALIDATION"
                validated = validate_full_entry_decision(
                    hint, candidate, coin, current, meta, full_assessment,
                    decision_at_utc=received_at,
                    slippage_pct_each_side=SLIPPAGE_PCT_EACH_SIDE)
                c["status"] = validated["status"]
                c["full_model_decision"] = normalized["decision"]
                c["model_setup_lane"] = normalized["setup_lane"]
                c["validated_decision"] = validated["decision"]
                c["reason_codes"] = [safe_token(x, 60) for x in normalized["reason_codes"][:8]]
                c["response_id"] = safe_token(metadata.get("response_id") or "", 80)
                if validated["decision"] == "BUY_SCOUT":
                    for k in ("execution_ask_eur", "execution_bid_eur", "stop_eur",
                              "stage2_trigger_eur", "stage2_ttl_minutes",
                              "total_round_trip_cost_pct", "spread_pct",
                              "slippage_pct_each_side", "net_edge_pct_before_path_outcome"):
                        c[k] = validated[k]
                    c["followup_6h"] = "PENDING_CAUSAL_PATHWISE_ASSESSMENT"
                    c["followup_24h"] = "PENDING_CAUSAL_PATHWISE_ASSESSMENT"
                checkpoint(report, j)
            except BudgetExhausted:
                c["status"] = "STOP_HTTP_BUDGET_NO_RETRY"
                j["status"] = "STOPPED_HTTP_BUDGET"
                checkpoint(report, j)
                break
            except Exception as exc:
                c["status"] = "STOPPED_UNVERIFIED_MODEL_OR_RISK_INPUT"
                c["failure_phase"] = phase
                c["failure_type"] = type(exc).__name__
                j["status"] = "STOPPED_UNVERIFIED_NO_AUTO_RETRY"
                checkpoint(report, j)
                break
            finally:
                evaluate.http_json = original_http
                if previous_key is None:
                    os.environ.pop("OPENAI_API_KEY", None)
                else:
                    os.environ["OPENAI_API_KEY"] = previous_key
            if j["model_http_attempts_reserved"] >= MAX_HTTP:
                j["status"] = "FINISHED_HTTP_CAP"
                break
        if j["status"] == "RUNNING":
            j["status"] = "FINISHED_FIVE_QUALIFIED_OR_SIX_HOUR_WINDOW"
    except Exception as exc:
        j["status"] = "STOPPED_PRECONDITION_NO_AUTO_RETRY"
        j["failure_type"] = type(exc).__name__
    finally:
        evaluate.http_json = original_http
        if previous_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = previous_key
        checkpoint(report, j)
    return j


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trading-root", type=Path, required=True)
    ap.add_argument("--code-root", type=Path, required=True)
    ap.add_argument("--minutes", type=int, default=MAX_MINUTES)
    ap.add_argument("--diagnose-only", action="store_true")
    args = ap.parse_args()
    try:
        out = run_one(args.trading_root, args.code_root, minutes=args.minutes,
                      dry_run=args.diagnose_only)
    except Exception as exc:
        out = {"kind": "V3_P3_AB_FIVE_RESEARCH_V1",
               "status": "BLOCKED_SAFE_PRECONDITION",
               "failure_type": type(exc).__name__,
               "model_http_attempts_reserved": 0, "paper_changed": False, "orders": 0}
    # Never emit model prompt, responses, API key, or raw source data.
    print(json.dumps(out, sort_keys=True))
    return 0 if out["status"] in (
        "PREFLIGHT_PASS_NO_MODEL", "FINISHED_FIVE_QUALIFIED_OR_SIX_HOUR_WINDOW",
        "FINISHED_HTTP_CAP") else 2


if __name__ == "__main__":
    raise SystemExit(main())
