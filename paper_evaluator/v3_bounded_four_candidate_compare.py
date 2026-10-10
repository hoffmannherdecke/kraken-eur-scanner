#!/usr/bin/env python3
"""Manual finite V3-A research batch: max FOUR new V2R4 handoffs, EIGHT HTTP model requests.

Separate read-only research process. Runtime and live strategy are never written.
The only durable output is a sanitized budget journal at an explicitly supplied
research path outside Runtime. Model budget is reserved BEFORE each HTTP request,
including the frozen evaluator's internal retry. No model or order is called
until one prospective candidate has closed Kraken-EUR Coin-Evidence ready.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import re
import time

from paper_evaluator import evaluate
from paper_evaluator.v3_one_shot_model_compare import (
    clean_decision, discover_active_paper_runtime, freeze_runtime_provenance,
)
from paper_evaluator.v3_entry_handoff_probe import attach_to_future_evaluator, utc, now_utc
from paper_evaluator.successor_coin_entry_evidence_v1 import fetch_public_entry_evidence
from paper_context import build_context

MAX_CASES = 4
MAX_HTTP_REQUESTS = 8
MAX_PER_CASE = 2
MAX_WAIT_MINUTES = 90
MAX_CANDIDATE_AGE_SECONDS = 900
MAX_SNAPSHOT_AGE_SECONDS = 120
EXPECTED_SERIES = "PAPER-V2R4-20261009T110135Z"
REVISION = "V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION"


class BudgetExhausted(BaseException):
    """Bypass the frozen evaluator's internal 'except Exception' retry."""


def safe_token(value: object, limit: int = 70) -> str:
    return re.sub(r"[^A-Za-z0-9_.+:/-]", "_", str(value))[:limit]


def new_journal(path: Path, control: dict, start: datetime, wait_minutes: int) -> dict:
    """Exclusive creation: interrupted/repeated launch must not charge twice."""
    if path.exists():
        raise ValueError("EXISTING_REPORT_STOP_NO_REPEAT")
    if not path.parent.is_dir():
        raise ValueError("RESEARCH_REPORT_PARENT_MISSING")
    data = {
        "kind": "V3_A_FOUR_CANDIDATE_INPUT_ONLY_MANUAL_BATCH_V1",
        "status": "RUNNING",
        "started_at_utc": start.isoformat(),
        "expected_series_id": control["series_id"],
        "strategy_revision": REVISION,
        "max_cases": MAX_CASES,
        "max_model_http_requests": MAX_HTTP_REQUESTS,
        "wait_minutes": wait_minutes,
        "actual_model_http_requests_reserved": 0,
        "completed_comparisons": 0,
        "cases": [],
        "paper_state_changed": False,
        "positions_created": 0,
        "orders": 0,
        "real_money_actions": False,
        "other_v3_h_factors_active": False,
        "prospective_net_edge_proven": False,
        "model_results_are_research_only_not_paper_trades": True,
    }
    with path.open("x", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"), sort_keys=True)
    return data


def checkpoint(path: Path, journal: dict) -> None:
    """Replace a small research-only report atomically; never touch V2R4."""
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as f:
        json.dump(journal, f, separators=(",", ":"), sort_keys=True)
    os.replace(temporary, path)


def eligible_handoffs(queue: Path, launch: datetime, control: dict,
                      done: set[str], used_pairs: set[str],
                      at: datetime) -> list[tuple[Path, dict]]:
    if not queue.is_dir():
        return []
    result = []
    active_from = utc(control["series_started_at_utc"])
    # Bounded directory work, no scan of other Windows drives or raw archives.
    for path in sorted(queue.glob("*.json"), key=lambda p: (p.stat().st_mtime, p.name),
                       reverse=True)[:150]:
        try:
            c = json.loads(path.read_text("utf-8-sig"))
            evaluate.validate_candidate(c, str(path))
            t = utc(c["event_time_utc"])
            age = (at - t).total_seconds()
            if (c["candidate_id"] not in done and c["pair"] not in used_pairs
                    and max(active_from, launch) <= t <= at
                    and 0 <= age <= MAX_CANDIDATE_AGE_SECONDS):
                result.append((path, c))
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            continue
    # Earliest new candidate first; only single order-independent comparison per pair.
    return sorted(result, key=lambda x: (x[1]["event_time_utc"], x[1]["candidate_id"]))


def make_guarded_http(journal: dict, report: Path, original_http, case: dict):
    def http(url, method="GET", headers=None, body=None, timeout=30):
        if url.startswith("https://api.openai.com/"):
            if (journal["actual_model_http_requests_reserved"] >= MAX_HTTP_REQUESTS
                    or case["model_http_requests_reserved"] >= MAX_PER_CASE):
                raise BudgetExhausted("MODEL_HTTP_BUDGET_EXHAUSTED")
            # Reserve BEFORE the network request: a timeout/crash still burns
            # the budget, preventing an accidental retry after restart.
            journal["actual_model_http_requests_reserved"] += 1
            case["model_http_requests_reserved"] += 1
            checkpoint(report, journal)
        return original_http(url, method, headers, body, timeout)
    return http


def ensure_safety(trading_root: Path, expected_series: str,
                  runtime: Path, pinned_control: dict, code_root: Path) -> None:
    other, control = discover_active_paper_runtime(trading_root, expected_series)
    if other != runtime or control != pinned_control:
        raise ValueError("STAGE_CHANGED_STOP")
    freeze_runtime_provenance(runtime, code_root, control)


def verify_frozen_strategy_spec(spec: dict) -> None:
    """Use the canonical V2R4 'fees' structure, without relaxing any limits."""
    entry = spec.get("entry", {})
    fees = spec.get("fees", {})
    if (spec.get("strategy_revision") != REVISION
            or entry.get("scout_notional_eur") != 50
            or entry.get("stage2_notional_eur") != 50
            or fees.get("taker_pct_per_side") != 0.6):
        raise ValueError("SIZING_FEE_OR_REVISION_DRIFT_STOP")


def run_batch(trading_root: Path, code_root: Path, expected_series: str,
              report: Path, wait_minutes: int = 60, *,
              sleep_fn=time.sleep, now_fn=lambda: datetime.now(timezone.utc)) -> dict:
    if not isinstance(wait_minutes, int) or not 0 <= wait_minutes <= MAX_WAIT_MINUTES:
        raise ValueError("WAIT_WINDOW_INVALID")
    if expected_series != EXPECTED_SERIES:
        raise ValueError("UNREVIEWED_SERIES_STOP")
    # Idempotency takes priority even if the previously active Paper stage has
    # since rotated: a duplicate user action must never reopen the cost budget.
    if report.exists():
        raise ValueError("EXISTING_REPORT_STOP_NO_REPEAT")
    runtime, control = discover_active_paper_runtime(trading_root, expected_series)
    ensure_safety(trading_root, expected_series, runtime, control, code_root)
    spec = json.loads((runtime / "paper_strategy_spec.json").read_text("utf-8"))
    verify_frozen_strategy_spec(spec)
    started = now_fn()
    journal = new_journal(report, control, started, wait_minutes)
    deadline = started + timedelta(minutes=wait_minutes)
    seen: set[str] = set()
    used_pairs: set[str] = set()
    models_started = False
    original_http = evaluate.http_json
    try:
        while len(journal["cases"]) < MAX_CASES:
            observed = now_fn()
            if observed > deadline:
                break
            ensure_safety(trading_root, expected_series, runtime, control, code_root)
            eligible = eligible_handoffs(runtime / "handoff_queue", started, control,
                                         seen, used_pairs, observed)
            if not eligible:
                if observed >= deadline:
                    break
                sleep_fn(min(60, max(0.0, (deadline - observed).total_seconds())))
                continue
            _, candidate = eligible[0]
            cid, pair = candidate["candidate_id"], candidate["pair"]
            seen.add(cid)
            used_pairs.add(pair)
            case = {
                "candidate_id": safe_token(cid),
                "pair": safe_token(pair),
                "source_event_at_utc": candidate["event_time_utc"],
                "status": "INPUT_PENDING",
                "model_http_requests_reserved": 0,
            }
            journal["cases"].append(case)
            checkpoint(report, journal)
            phase = "PUBLIC_TICKER"
            try:
                ticker = evaluate.kraken_ticker(candidate["altname"])
                phase = "STANDARD_CONTEXT"
                standard = build_context(candidate, ticker)
                phase = "COIN_ENTRY_EVIDENCE"
                coin_evidence = fetch_public_entry_evidence(candidate["altname"], pair)
                snapshot_at = now_utc()
                phase = "COIN_ATTACH"
                enriched = attach_to_future_evaluator(candidate, standard, coin_evidence, snapshot_at)
                if (utc(snapshot_at) - utc(candidate["event_time_utc"])).total_seconds() > MAX_CANDIDATE_AGE_SECONDS:
                    raise ValueError("CANDIDATE_OUTDATED")
                case.update({
                    "same_candidate_same_ticker_standard_context": True,
                    "coin_input_only_new_feature": True,
                    "coin_evidence_known_at_utc": coin_evidence["known_at_utc"],
                    "model_snapshot_at_utc": snapshot_at,
                    "status": "INPUT_READY",
                })
                checkpoint(report, journal)
            except Exception as exc:
                case.update({"status": "SKIPPED_INPUT_UNAVAILABLE", "phase": phase,
                             "failure_type": type(exc).__name__})
                checkpoint(report, journal)
                continue

            # Validate frozen runtime and experiment time prior to consuming budget.
            ensure_safety(trading_root, expected_series, runtime, control, code_root)
            if (now_fn() - utc(snapshot_at)).total_seconds() > MAX_SNAPSHOT_AGE_SECONDS:
                case["status"] = "SKIPPED_SNAPSHOT_STALE"
                checkpoint(report, journal)
                continue
            phase = "MODEL_SECRET"
            try:
                key = (trading_root / "Secrets" / "openai-api-key.txt").read_text("utf-8").strip()
                if len(key) < 20:
                    raise ValueError("INVALID_EXISTING_MODEL_KEY")
                os.environ["OPENAI_API_KEY"] = key
                key = ""
                models_started = True
                evaluate.http_json = make_guarded_http(journal, report, original_http, case)
                phase = "BASELINE_MODEL"
                raw_a, _ = evaluate.call_evaluator(candidate, ticker, standard, spec, control)
                baseline = clean_decision(raw_a, ticker, standard, spec)
                case["baseline"] = baseline
                case["status"] = "BASELINE_COMPLETE"
                checkpoint(report, journal)
                phase = "SUCCESSOR_MODEL"
                if (now_fn() - utc(snapshot_at)).total_seconds() > MAX_SNAPSHOT_AGE_SECONDS:
                    raise ValueError("MODEL_SNAPSHOT_TOO_OLD_FOR_SECOND_ARM")
                raw_b, _ = evaluate.call_evaluator(candidate, ticker, enriched, spec, control)
                successor = clean_decision(raw_b, ticker, enriched, spec)
                case["successor_with_coin_evidence"] = successor
                case["status"] = "COMPLETE_SAME_SNAPSHOT_NOT_PROFITABILITY_PROOF"
                journal["completed_comparisons"] += 1
                checkpoint(report, journal)
                print("CASE " + safe_token(pair) + " baseline=" + safe_token(baseline["decision"]) +
                      " v3_coin=" + safe_token(successor["decision"]) +
                      " requests=" + str(journal["actual_model_http_requests_reserved"]), flush=True)
            except BudgetExhausted:
                case.update({"status": "STOP_MODEL_BUDGET", "phase": phase})
                checkpoint(report, journal)
                break
            except Exception as exc:
                case.update({"status": "STOP_MODEL_PHASE_UNVERIFIED", "phase": phase,
                             "failure_type": type(exc).__name__})
                checkpoint(report, journal)
                # Never move to a new candidate after possible model/API failure.
                break
            finally:
                evaluate.http_json = original_http
                os.environ.pop("OPENAI_API_KEY", None)

            if journal["actual_model_http_requests_reserved"] >= MAX_HTTP_REQUESTS:
                break

        journal["status"] = ("COMPLETE_UP_TO_FOUR_OR_WINDOW_ELAPSED"
                             if all(c["status"] != "STOP_MODEL_PHASE_UNVERIFIED" and c["status"] != "STOP_MODEL_BUDGET"
                                    for c in journal["cases"])
                             else "STOPPED_PRESERVE_BUDGET")
    except Exception as exc:
        journal["status"] = "STOPPED_PRECONDITION"
        journal["failure_type"] = type(exc).__name__
    finally:
        evaluate.http_json = original_http
        if models_started:
            os.environ.pop("OPENAI_API_KEY", None)
        checkpoint(report, journal)
    return journal


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trading-root", required=True, type=Path)
    ap.add_argument("--code-root", required=True, type=Path)
    ap.add_argument("--expected-series-id", required=True)
    ap.add_argument("--report", required=True, type=Path)
    ap.add_argument("--wait-minutes", type=int, default=60)
    args = ap.parse_args()
    try:
        result = run_batch(args.trading_root, args.code_root,
                           args.expected_series_id, args.report, args.wait_minutes)
    except (OSError, ValueError, TypeError, KeyError):
        print("BATCH_BLOCKED_BEFORE_MODEL_OR_EXISTING_REPORT", flush=True)
        return 2
    print("SUMMARY " + json.dumps({
        "status": result["status"], "cases": len(result["cases"]),
        "completed": result["completed_comparisons"],
        "http_model_requests_reserved": result["actual_model_http_requests_reserved"],
        "budget_max": MAX_HTTP_REQUESTS, "report": str(args.report),
        "orders": 0, "paper_state_changed": False,
        "economic_edge_proven": False,
    }, sort_keys=True), flush=True)
    return 0 if result["status"] == "COMPLETE_UP_TO_FOUR_OR_WINDOW_ELAPSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
