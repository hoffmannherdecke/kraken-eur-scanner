#!/usr/bin/env python3
"""Inactive V3 EXTENDED second-leg *review eligibility* using real Kraken entry evidence.

Reuses V2R4 EXTENDED and canonical V3 candidate coin evidence, NOT an extra
REVERSAL lane/H6 vote/H4 stop policy. No models, paper fills or order authority.
This is a separately gated hypothesis; it must not be combined with the first
prospective "coin evidence only" test.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from paper_evaluator.v3_entry_handoff_probe import attach_to_future_evaluator, utc

# V2R4 already models five-minute volume ratio >=1.2 as a WAIT condition.
# Do not optimize this on Oct-08/09 retrospectively.
EXISTING_V2R4_VOLUME_RATIO_REVIEW_FLOOR = 1.2
MAX_STALE_SOURCE_SECONDS = 120
MAX_FRESH_CANDIDATE_SECONDS = 15 * 60


def _finite_positive(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("positive numeric feature missing")
    v = float(value)
    if not math.isfinite(v) or v <= 0:
        raise ValueError("invalid feature")
    return v


def extended_reentry_review(
    candidate: dict[str, Any],
    original_decision: dict[str, Any],
    evidence: dict[str, Any],
    ticker: dict[str, Any],
    *,
    decision_at_utc: str,
) -> dict[str, Any]:
    """Return compact observation, never BUY/WAIT/REJECT or a stop instruction.

    Inputs should come from the same *prospective* candidate/model snapshot.
    No data source may be backdated to recreate October 2026 missed entries.
    """
    common = {
        "kind": "V3_EXISTING_EXTENDED_REENTRY_REVIEW_ONLY_V1",
        "candidate_id": candidate.get("candidate_id"),
        "pair": candidate.get("pair"),
        "canonical_owner": "late_chase_protection",
        "reuses_coin_evidence_owner": "coin_specific_entry_evidence_provenance",
        "duplicates_h6_volume_vote": False,
        "creates_h4_stop_policy": False,
        "changes_existing_v2r4_wait": False,
        "independent_trade_signal": False,
        "request_model_recheck_only": False,
        "decision": "NO_DECISION_AUTHORITY",
        "paper_trade": False,
        "orders": False,
        "real_money_actions": False,
        "automatic_promotion": False,
    }
    if original_decision.get("setup_lane") != "EXTENDED":
        return {**common, "state": "OUT_OF_SCOPE_EXISTING_LANE_RETAINED"}
    if original_decision.get("decision") not in {"WAIT", "REJECT"}:
        return {**common, "state": "OUT_OF_SCOPE_NOT_A_MISSED_EXTENDED_ENTRY"}
    try:
        evaluated = utc(decision_at_utc)
        created = utc(candidate["event_time_utc"])
        age = (evaluated-created).total_seconds()
        if age < 0 or age > MAX_FRESH_CANDIDATE_SECONDS:
            return {**common, "state": "UNKNOWN_STALE_OR_FUTURE_CANDIDATE"}
        _ = attach_to_future_evaluator(
            candidate, {}, evidence, decision_at_utc,
            max_evidence_age_seconds=MAX_STALE_SOURCE_SECONDS,
        )
        ask = _finite_positive(ticker.get("ask"))
        bid = _finite_positive(ticker.get("bid"))
        if ask < bid:
            raise ValueError("inverted ticker")
        spread = 100 * (ask - bid) / ((ask + bid) / 2)
        f = evidence["frames"]
        last5 = _finite_positive(f["5"]["closed_close_eur"])
        last15 = _finite_positive(f["15"]["closed_close_eur"])
        relvol = _finite_positive(f["5"]["volume_ratio_prior_5"])
        atr = _finite_positive(f["15"]["atr14_eur"])
        low = _finite_positive(f["15"]["recent_8bar_low_eur"])
        stop_reference = min(low, last15 - atr * 0.5)
        if stop_reference <= 0 or not stop_reference < ask:
            return {**common, "state": "STRUCTURAL_REFERENCE_NOT_VALID",
                    "spread_pct": round(spread, 4)}
    except (ValueError, TypeError, KeyError, IndexError):
        return {**common, "state": "UNKNOWN_INSUFFICIENT_PROSPECTIVE_EVIDENCE"}

    # Only an isolated research model *recheck* can be proposed here.
    # This is deliberately not a buy and doesn't loosen cost/risk/size guards.
    price_recovered = last5 > last15
    vol_recovered = relvol >= EXISTING_V2R4_VOLUME_RATIO_REVIEW_FLOOR
    spread_not_excessive = spread <= 0.5
    risk_distance_pct = (ask-stop_reference) / ask * 100
    eligible = price_recovered and vol_recovered and spread_not_excessive
    return {
        **common,
        "state": ("STRUCTURE_AND_VOLUME_SUPPORT_FRESH_REVIEW_NOT_BUY"
                  if eligible else "PROSPECTIVE_CONFIRMATION_INCOMPLETE"),
        "request_model_recheck_only": eligible,
        "checks": {
            "closed_5m_price_above_closed_15m_price": price_recovered,
            "closed_5m_volume_ratio_at_least_existing_v2r4_1_2": vol_recovered,
            "spread_at_most_half_percent": spread_not_excessive,
            "closed_5m_volume_ratio": round(relvol,4),
        },
        "stop_reference_eur_descriptive_only": round(stop_reference,10),
        "stop_distance_pct_descriptive_only": round(risk_distance_pct,4),
        "fee_roundtrip_pct_before_spread_and_slippage": 1.2,
        "spread_pct": round(spread,4),
        "conservative_minimum_cost_hurdle_pct_excluding_slippage": round(1.2+spread,4),
        "model_must_validate_remaining_upside": True,
        "model_must_validate_real_stop_and_stage2": True,
        "slippage_and_fill_unproven": True,
        "not_in_existing_v2r4_wait_cycle": True,
    }
