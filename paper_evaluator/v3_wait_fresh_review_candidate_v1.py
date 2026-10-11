#!/usr/bin/env python3
"""INACTIVE V3 P2: a genuinely NEW evaluation opportunity after a completed V2R4 WAIT expiry.

The old WAIT/expiry remains final. Only newly known, closed Kraken EUR bars
can propose a *fresh full-model review* in a separately approved experiment.
Never continues the old watcher, reopens V2R4, generates a BUY, or writes state.
Independent from the EXTENDED-only V3-B Second-Leg policy, but shares the
existing canonical PIT validator and immutable research risk-confirmation floors.
"""
from __future__ import annotations

import math
from datetime import timedelta
from typing import Any

from paper_evaluator.v3_entry_handoff_probe import attach_to_future_evaluator, utc
from paper_evaluator.v3_second_leg_policy_candidate_v1 import (
    _bar_start,
    MAX_RECLAIM_EXTENSION_ATR,
    MAX_BASE_WIDTH_ATR,
    MAX_REVIEW_HORIZON_SECONDS,
    SOURCE_MAX_AGE_SECONDS,
    SPREAD_LIMIT_PCT,
    CLOSED_BAR_SECONDS,
)
from paper_evaluator.v3_extended_reentry_review_v1 import (
    EXISTING_V2R4_VOLUME_RATIO_REVIEW_FLOOR,
    _finite_positive,
)

KIND = "V3_P2_INACTIVE_WAIT_FRESH_REVIEW_ELIGIBILITY_V1"
ELIGIBLE = "WAIT_FRESH_STRUCTURE_SUPPORTS_NEW_FULL_REVIEW_ONLY"
EXPIRY_KIND = "V2R4_WAIT_EXPIRY_V1"
# Two genuinely closed 15m reference bars and one *new* closed 15m reclaim.
# Minimum base length is fixed for this pre-registered research variant, not
# optimized using the 24h-MFE after rejection.
REFERENCE_BASE_BARS = 2


def _outcome(status: str, *, candidate_id: Any, pair: Any, **fields: Any) -> dict[str, Any]:
    return {
        "kind": KIND,
        "status": status,
        "source_candidate_id": candidate_id,
        "pair": pair,
        "decision": "NO_DECISION_AUTHORITY",
        "request_model_recheck_only": False,
        "approval_to_call_model": False,
        "snapshot_recheck_must_be_deduplicated": True,
        "original_wait_and_expiry_immutable": True,
        "changes_v2r4": False,
        "changes_wait_ttl": False,
        "changes_h3_h6": False,
        "changes_stop_or_stage2_policy": False,
        "paper_state_changed": False,
        "paper_trade": False,
        "orders": False,
        "real_money_actions": False,
        "auto_buy": False,
        "economic_edge_proven": False,
        "new_strategy_version_required": True,
        "fee_pct_each_side_unchanged": 0.6,
        "scout_eur_unchanged": 50,
        "stage2_eur_unchanged": 50,
        "next_action": "NONE_RESEARCH_ONLY",
        **fields,
    }


def propose_wait_fresh_review(
    original_candidate: dict[str, Any],
    original_decision: dict[str, Any],
    completed_expiry: dict[str, Any],
    new_coin_evidence: dict[str, Any],
    fresh_ticker: dict[str, Any],
    closed_15m_bars: list[dict[str, Any]],
    *,
    decision_at_utc: str,
    optional_sources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Offline review eligibility ONLY; always full-model + P4 validation later.

    Only P2 changes vs V2R4: an *already expired* WAIT can be the historical
    anchor of a later independent, bounded, PIT-verified research assessment.
    This is NOT a blanket change of the existing V2R4 trigger or TTL policy.
    """
    candidate_id = original_candidate.get("candidate_id")
    pair = original_candidate.get("pair")
    neutral = {"optional_sources_are_context_only": True,
               "optional_source_names": tuple(sorted((optional_sources or {}).keys()))}
    def out(status: str, **details: Any) -> dict[str, Any]:
        return _outcome(status, candidate_id=candidate_id, pair=pair, **neutral, **details)

    if original_decision.get("decision") != "WAIT":
        return out("OUT_OF_SCOPE_ORIGINAL_NOT_WAIT")
    if not isinstance(candidate_id, str) or not candidate_id or not isinstance(pair, str) or not pair.endswith("/EUR"):
        return out("MISSING_CANONICAL_ORIGINAL_EUR_ID")
    old_outcome=completed_expiry.get("decision")
    if (not isinstance(old_outcome, dict) or
            completed_expiry.get("kind") != EXPIRY_KIND or
            completed_expiry.get("candidate_id") != candidate_id or
            completed_expiry.get("pair") != pair or
            old_outcome.get("decision") != "REJECT"):
        return out("EXPIRY_NOT_PROVEN_OR_ID_MISMATCH")

    stage = "ORIGINAL_EXPIRY_AND_NEW_PIT_CLOCK"
    try:
        original_time = utc(original_candidate["event_time_utc"])
        expiry_time = utc(completed_expiry["recheck_completed_at_utc"])
        at = utc(decision_at_utc)
        if not original_time < expiry_time < at:
            return out("INVALID_OR_NOT_PAST_WAIT_EXPIRY")
        if (at-expiry_time).total_seconds() > MAX_REVIEW_HORIZON_SECONDS:
            return out("EXPIRED_ANCHOR_TOO_OLD_FOR_BOUNDED_RESEARCH")
        if completed_expiry.get("evaluator", {}).get("attempt") not in (0, None):
            return out("EXPIRY_HAS_UNEXPECTED_MODEL_RECHECK")
        # The old WAIT price, triggers and (future-known) followup labels must
        # never be copied into the proposed fresh evaluation.
        attach_to_future_evaluator(
            {"pair": pair}, {}, new_coin_evidence, decision_at_utc,
            max_evidence_age_seconds=SOURCE_MAX_AGE_SECONDS,
        )
        ticker_at = utc(fresh_ticker["observed_at_utc"])
        if not expiry_time < ticker_at <= at or (at-ticker_at).total_seconds() > SOURCE_MAX_AGE_SECONDS:
            return out("UNKNOWN_TICKER_NOT_FRESH_AFTER_EXPIRY")
        observed = utc(new_coin_evidence["observed_at_utc"])

        stage = "NEW_CLOSED_CANDLE_HISTORY"
        if not isinstance(closed_15m_bars, list) or len(closed_15m_bars) < REFERENCE_BASE_BARS+1:
            return out("MISSING_NEW_CLOSED_BAR_HISTORY")
        bars = closed_15m_bars[-(REFERENCE_BASE_BARS+1):]
        ticks = [_bar_start(b) for b in bars]
        if any(ticks[i]-ticks[i-1] != timedelta(seconds=CLOSED_BAR_SECONDS) for i in (1, 2)):
            return out("NONCONTIGUOUS_NEW_BAR_HISTORY")
        # The decisive NEW 15m bar must start after expiry. A bar merely
        # closing after expiry but already opened before it is insufficient.
        if ticks[-1] < expiry_time:
            return out("NO_INDEPENDENT_POST_EXPIRY_BAR")
        end = ticks[-1]+timedelta(seconds=CLOSED_BAR_SECONDS)
        if not end <= observed:
            return out("OPEN_OR_FUTURE_RECLAIM_BAR")
        f15 = new_coin_evidence["frames"]["15"]
        if utc(f15["last_closed_bar_end_utc"]) != end:
            return out("15M_PRICE_CLOCK_MISMATCH")
        for bar in bars:
            lo=_finite_positive(bar.get("low"))
            hi=_finite_positive(bar.get("high"))
            op=_finite_positive(bar.get("open"))
            close=_finite_positive(bar.get("close"))
            if not lo <= min(op,close) <= max(op,close) <= hi:
                return out("INVALID_CLOSED_OHLC_SEQUENCE")
        base_high=max(float(b["high"]) for b in bars[:-1])
        base_low=min(float(b["low"]) for b in bars[:-1])
        reclaimed=float(bars[-1]["close"])
        if not math.isclose(reclaimed,float(f15["closed_close_eur"]),rel_tol=1e-9):
            return out("15M_PRICE_EVIDENCE_MISMATCH")

        stage = "FRESH_VOLUME_SPREAD_AND_RISK_REFERENCE"
        atr=_finite_positive(f15["atr14_eur"])
        closed5=_finite_positive(new_coin_evidence["frames"]["5"]["closed_close_eur"])
        # Canonical validator accepts VALID zero-volume ratios. They are
        # confirmed false at the floor, NOT unknown data.
        vol=float(new_coin_evidence["frames"]["5"]["volume_ratio_prior_5"])
        bid=_finite_positive(fresh_ticker["bid"])
        ask=_finite_positive(fresh_ticker["ask"])
        if bid > ask:
            return out("INVERTED_KRAKEN_EUR_TICKER")
        spread=(ask-bid)/((ask+bid)/2)*100
        ref=min(base_low,_finite_positive(f15["recent_8bar_low_eur"]))
        checks={
            "closed_post_expiry_reclaim": reclaimed > base_high,
            "closed_reference_base_not_excessive": (base_high-base_low) <= MAX_BASE_WIDTH_ATR*atr,
            "not_late_chasing_fresh_reclaim": (reclaimed-base_high) <= MAX_RECLAIM_EXTENSION_ATR*atr,
            "closed_5m_price_confirmation": closed5 >= base_high,
            "unchanged_v2r4_closed_5m_volume_confirmation": vol >= EXISTING_V2R4_VOLUME_RATIO_REVIEW_FLOOR,
            "fresh_eur_spread_guard": spread <= SPREAD_LIMIT_PCT,
            "current_ask_not_chasing_reclaim": (ask-base_high) <= MAX_RECLAIM_EXTENSION_ATR*atr,
            "valid_structural_stop_reference_only": 0 < ref < ask,
        }
        if not all(checks.values()):
            return out("FRESH_WAIT_CONDITIONS_NOT_CONFIRMED", checks=checks,
                       fresh_post_expiry_15m_close=end.isoformat(),
                       fee_plus_spread_pct_before_slippage=round(1.2+spread,4))
        result=out(
            ELIGIBLE, checks=checks, prior_wait_recheck_kind=EXPIRY_KIND,
            expired_at_utc=expiry_time.isoformat(),
            fresh_bar_closed_after_expiry=True,
            fresh_post_expiry_15m_close=end.isoformat(),
            # Consumer deduplicates this immutable source+closed-bar key; this
            # offline policy intentionally has no durable state or scheduler.
            snapshot_recheck_key=f"{candidate_id}|{end.isoformat()}",
            new_snapshot_observed_at_utc=new_coin_evidence["observed_at_utc"],
            new_snapshot_known_at_utc=new_coin_evidence["known_at_utc"],
            fee_plus_spread_pct_before_slippage=round(1.2+spread,4),
            descriptive_base_high_eur=round(base_high,10),
            descriptive_stop_reference_eur=round(ref,10),
            only_full_evaluator_can_decide_buy=True,
        )
        result["request_model_recheck_only"]=True
        result["next_action"]="ONLY_IF_SEPARATELY_APPROVED_FRESH_FULL_MODEL_REVIEW"
        return result
    except (ValueError, TypeError, KeyError, OverflowError, OSError, AttributeError):
        return out("UNKNOWN_REQUIRED_NEW_PIT_OR_STRUCTURE_EVIDENCE", validation_stage=stage)
