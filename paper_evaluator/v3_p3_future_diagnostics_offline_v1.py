#!/usr/bin/env python3
"""INACTIVE V3 P3 future-research observability contract: pure offline functions.

Designed after the 11 Oct completed five-WAIT trial.  Deliberately NOT
imported by the consumed one-time trial, the V2R4 runtime, a scheduler or a
model client.  Does not fetch data, log secrets, write state or create orders.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from paper_evaluator.v3_continuity_fresh_review_candidate_v1 import (
    KIND as STANDARD_KIND, ELIGIBLE as STANDARD_ELIGIBLE,
)
from paper_evaluator.v3_experimental_continuity_volume_review_v1 import (
    KIND as EXPERIMENT_KIND, ELIGIBLE as EXPERIMENT_ELIGIBLE,
    EXPECTED_STANDARD_CHECKS,
)
from paper_evaluator.v2r4_trigger_contract import ALLOWED_METRICS, ALLOWED_OPS

KIND = "V3_P3_FUTURE_DIAGNOSTICS_OFFLINE_V1"
PHASES = frozenset({
    "FRESH_KRAKEN_TICKER", "PUBLIC_OPTIONAL_CONTEXT", "COIN_1M_5M_15M_PIT",
    "CLOSED_15M_STRUCTURE", "FRESH_EXECUTION_TICKER", "COIN_ENTRY_HANDOFF",
    "KRAKEN_ONLINE_SPOT_EUR_ASSETPAIRS", "P3_STANDARD_EXPERIMENTAL_REVIEW",
    "MODEL_AUTHORITY", "FULL_MODEL_HTTP", "P4_VALIDATION",
})
ALLOWED_ERRORS = frozenset({
    "ValueError", "TypeError", "KeyError", "RuntimeError", "TimeoutError",
    "ConnectionError", "OSError", "OverflowError", "JSONDecodeError",
    "IndexError", "AttributeError",
})
VALID_P4 = {
    "WAIT": "FULL_WAIT_VALIDATED_OFFLINE",
    "REJECT": "FULL_REJECT_VALIDATED_OFFLINE",
    "BUY_SCOUT": "FULL_BUY_SCOUT_CONTRACT_VALIDATED_OFFLINE_NOT_RELEASE_EVIDENCE",
}
STAMP_MAX_AGE_SECONDS = 120
SAFE_CODE = re.compile(r"[A-Z][A-Z0-9_]{1,100}\Z")


def _clock(s: str) -> datetime:
    if not isinstance(s, str) or len(s) > 45:
        raise ValueError("time format missing")
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise ValueError("time format invalid") from exc
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError("timezone required")
    return d.astimezone(timezone.utc)


def _stamp(d: datetime) -> str:
    return d.isoformat().replace("+00:00", "Z")


def _safe_code(value: Any) -> str:
    """Never echo raw exception text, URLs, prompt or arbitrary model output."""
    return value if isinstance(value, str) and SAFE_CODE.fullmatch(value) else "UNKNOWN_STATUS"


def review_diagnostic(standard: dict[str, Any], experimental: dict[str, Any]) -> dict[str, Any]:
    """Explain both P3 arms from the SAME existing result; never recompute gates."""
    if not isinstance(standard, dict) or not isinstance(experimental, dict):
        raise ValueError("review objects missing")
    if standard.get("kind") != STANDARD_KIND or experimental.get("kind") != EXPERIMENT_KIND:
        raise ValueError("canonical P3 review lineage missing")
    s = _safe_code(standard.get("status"))
    e = _safe_code(experimental.get("status"))
    s_allowed = standard.get("request_model_recheck_only") is True and s == STANDARD_ELIGIBLE
    e_allowed = (experimental.get("request_model_recheck_only") is True
                 and e == EXPERIMENT_ELIGIBLE and not s_allowed)
    status = ("STANDARD_REVIEW_ONLY" if s_allowed else
              "EXPERIMENTAL_INCREMENTAL_REVIEW_ONLY" if e_allowed else
              "NO_REVIEW")
    checks = standard.get("checks")
    known_checks = (isinstance(checks, dict)
                    and set(checks) == EXPECTED_STANDARD_CHECKS
                    and all(type(v) is bool for v in checks.values()))
    if known_checks:
        failed = sorted(k for k, v in checks.items() if v is False)
    else:
        failed = None  # Not a pass; reason details simply were not produced.
    if s == STANDARD_ELIGIBLE and (not known_checks or failed):
        raise ValueError("eligible standard missing eight passing gates")
    if status == "EXPERIMENTAL_INCREMENTAL_REVIEW_ONLY":
        if (not known_checks or failed != ["unchanged_closed_5m_volume_floor"]
                or experimental.get("old_standard_all_other_checks_passed") is not True):
            raise ValueError("experimental one-change evidence mismatch")
    if s_allowed and experimental.get("status") != "BASELINE_ALREADY_ELIGIBLE_NOT_INCREMENTAL":
        raise ValueError("standard cannot be double charged as incremental")
    if (s == "UNKNOWN_STATUS" or e == "UNKNOWN_STATUS"
            or (s == STANDARD_ELIGIBLE and not s_allowed)
            or (e == EXPERIMENT_ELIGIBLE and not e_allowed)):
        status = "UNKNOWN_REVIEW_OR_PERMISSION"
    return {
        "kind": KIND, "status": status,
        "standard_status": s, "experimental_status": e,
        "standard_hard_checks_present": known_checks,
        "failed_standard_hard_check_names": failed,
        "model_http_attempts": 0, "new_model_permission": False,
        "no_automatic_buy": True, "paper_changed": False,
    }


def phase_failure(phase: str, exc: Exception) -> dict[str, Any]:
    """Small privacy-safe phase taxonomy; no exception messages or source rows."""
    if not isinstance(exc, Exception):
        raise TypeError("Exception required")
    name = type(exc).__name__
    return {
        "kind": KIND, "status": "INPUT_OR_MODEL_PHASE_FAILED",
        "phase": phase if phase in PHASES else "UNCLASSIFIED_PHASE",
        "exception_type": name if name in ALLOWED_ERRORS else "OtherError",
        "assetpairs_phase_failed": phase == "KRAKEN_ONLINE_SPOT_EUR_ASSETPAIRS",
        "model_http_attempts": 0, "new_model_permission": False,
        "no_automatic_buy": True, "paper_changed": False,
    }


def full_review_receipt(
    *,
    entry_known_at_utc: str,
    execution_ticker_at_utc: str,
    assetpairs_at_utc: str,
    eligibility_at_utc: str,
    model_request_at_utc: str,
    model_response_at_utc: str,
    p4_completed_at_utc: str,
    model_decision: str,
    p4_result: dict[str, Any],
) -> dict[str, Any]:
    """Sanitised *future* model/P4 lineage. Does not reconstruct October data."""
    if not isinstance(p4_result, dict):
        raise ValueError("verified P4 result required")
    if (model_decision not in VALID_P4
            or p4_result.get("kind") != "V3_B_INACTIVE_FULL_ENTRY_DECISION_V1"
            or p4_result.get("status") != VALID_P4[model_decision]
            or p4_result.get("decision") != model_decision
            or p4_result.get("orders") is not False
            or p4_result.get("real_money_actions") is not False
            or p4_result.get("paper_writer_started") is not False):
        raise ValueError("unverified or unsafe P4 lineage")
    k = _clock(entry_known_at_utc)
    t = _clock(execution_ticker_at_utc)
    a = _clock(assetpairs_at_utc)
    e = _clock(eligibility_at_utc)
    req = _clock(model_request_at_utc)
    resp = _clock(model_response_at_utc)
    p4 = _clock(p4_completed_at_utc)
    if not (k <= t <= e <= req <= resp <= p4 and a <= e):
        raise ValueError("PIT/order/response clock reversal")
    if (e - k).total_seconds() > STAMP_MAX_AGE_SECONDS or (
            e - a).total_seconds() > STAMP_MAX_AGE_SECONDS:
        raise ValueError("stale eligibility input")
    # A model answering late cannot become a fresh execution decision.
    if (p4-k).total_seconds() > STAMP_MAX_AGE_SECONDS or (
            p4-t).total_seconds() > STAMP_MAX_AGE_SECONDS or (
            p4-a).total_seconds() > STAMP_MAX_AGE_SECONDS:
        raise ValueError("stale full-model consumer input")
    result = {
        "kind": KIND, "status": "VALIDATED_MODEL_RECEIPT_NOT_EXECUTED_TRADE",
        "eligibility_at_utc": _stamp(e),
        "model_request_at_utc": _stamp(req),
        "model_response_at_utc": _stamp(resp),
        "p4_completed_at_utc": _stamp(p4),
        "model_request_to_response_ms": round((resp-req).total_seconds()*1000, 3),
        "p4_status": p4_result["status"], "validated_decision": model_decision,
        "wait_ttl_minutes": None, "wait_expires_at_utc": None,
        "watch_conditions": [],
        "model_http_attempts": 0, "new_model_permission": False,
        "paper_changed": False, "paper_writer_started": False,
        "orders": 0, "economic_edge_proven": False, "actual_pnl_eur": None,
    }
    if model_decision == "WAIT":
        ttl = p4_result.get("ttl_minutes")
        watch = p4_result.get("watch_conditions")
        if type(ttl) is not int or not 1 <= ttl <= 60:
            raise ValueError("P4 WAIT TTL unproven")
        if not isinstance(watch, list) or not 1 <= len(watch) <= 6:
            raise ValueError("P4 WAIT condition count invalid")
        safe_watch = []
        for c in watch:
            if not isinstance(c, dict) or set(c) != {"metric", "op", "value"}:
                raise ValueError("noncanonical WAIT condition")
            metric, op, value = c["metric"], c["op"], c["value"]
            if (metric not in ALLOWED_METRICS or op not in ALLOWED_OPS
                    or type(value) not in (float, int) or not math.isfinite(value)):
                raise ValueError("unsafe WAIT trigger")
            safe_watch.append({"metric": metric, "op": op, "value": value})
        result["wait_ttl_minutes"] = ttl
        result["wait_expires_at_utc"] = _stamp(p4+timedelta(minutes=ttl))
        result["watch_conditions"] = safe_watch
    return result
