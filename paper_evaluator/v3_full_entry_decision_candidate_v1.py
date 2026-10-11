#!/usr/bin/env python3
"""Inactive V3-B full-entry decision contract.

This module is deliberately pure and offline.  It validates that a separately
produced full assessment is tied to fresh point-in-time Kraken Spot-EUR input
and that BUY_SCOUT has an executable two-stage, cost-adjusted paper plan.
Second-leg review eligibility alone never becomes a decision.

It is not imported by the active V2R4 runtime, calls no model or network,
writes no state, starts no shadow and has no order authority.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

ELIGIBLE_STATUS = "SECOND_LEG_STRUCTURE_SUPPORTS_NEW_FULL_REVIEW_ONLY"
# One risk/stop/stage2 validator shared across separately tested review families.
WAIT_FRESH_ELIGIBLE_STATUS = "WAIT_FRESH_STRUCTURE_SUPPORTS_NEW_FULL_REVIEW_ONLY"
WAIT_FRESH_ELIGIBLE_KIND = "V3_P2_INACTIVE_WAIT_FRESH_REVIEW_ELIGIBILITY_V1"
CONTINUITY_ELIGIBLE_STATUS = "CONTINUITY_FRESH_STRUCTURE_SUPPORTS_NEW_FULL_REVIEW_ONLY"
CONTINUITY_ELIGIBLE_KIND = "V3_P3_INACTIVE_CONTINUITY_FRESH_REVIEW_ELIGIBILITY_V1"
SOURCE_MAX_AGE_SECONDS = 120
FEE_PCT_EACH_SIDE = 0.6
SCOUT_EUR = 50
STAGE2_EUR = 50
ALLOWED_DECISIONS = {"BUY_SCOUT", "WAIT", "REJECT"}
ALLOWED_SETUP_LANES = {"IGNITION", "CONTINUITY", "EXTENDED", "REVERSAL", "NONE"}


def _utc(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return dt.astimezone(timezone.utc)


def _positive(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("boolean is not numeric")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError("positive finite number required")
    return number


def _nonnegative(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("boolean is not numeric")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError("nonnegative finite number required")
    return number


def _result(status: str, *, decision: str = "UNKNOWN", **fields: Any) -> dict[str, Any]:
    return {
        "kind": "V3_B_INACTIVE_FULL_ENTRY_DECISION_V1",
        "status": status,
        "decision": decision,
        "strategy_revision": "V3-B-INACTIVE-FULL-ENTRY-CANDIDATE-V1",
        "active_runtime_change": False,
        "model_called": False,
        "shadow_started": False,
        "paper_writer_started": False,
        "orders": False,
        "real_money_actions": False,
        "economic_edge_proven": False,
        "release_evidence": False,
        **fields,
    }


def validate_full_entry_decision(
    review_eligibility: dict[str, Any],
    candidate: dict[str, Any],
    entry_evidence: dict[str, Any],
    fresh_ticker: dict[str, Any],
    pair_metadata: dict[str, Any],
    full_assessment: dict[str, Any] | None,
    *,
    decision_at_utc: str,
    slippage_pct_each_side: float,
) -> dict[str, Any]:
    """Validate one inactive V3-B full decision on a single known-at clock.

    ``full_assessment`` is an already-produced decision payload (mocked in the
    offline acceptance tests).  This function never produces strategy signal
    from eligibility or market data.  Missing required data is UNKNOWN, while
    an explicit but non-executable BUY is fail-closed REJECT.
    """
    common = {
        "candidate_id": candidate.get("candidate_id"),
        "pair": candidate.get("pair"),
        "source_review_status": review_eligibility.get("status"),
        "fee_pct_each_side": FEE_PCT_EACH_SIDE,
        "scout_eur": SCOUT_EUR,
        "stage2_eur": STAGE2_EUR,
        "eligibility_is_not_buy": True,
    }
    review_status = review_eligibility.get("status")
    if (review_status not in {ELIGIBLE_STATUS, WAIT_FRESH_ELIGIBLE_STATUS, CONTINUITY_ELIGIBLE_STATUS}
            or review_eligibility.get("request_model_recheck_only") is not True):
        return _result("NO_FULL_REVIEW_ELIGIBILITY", **common)
    if review_status == WAIT_FRESH_ELIGIBLE_STATUS:
        # An arbitrary review=True cannot bypass an actual post-expiry proof.
        if (review_eligibility.get("kind") != WAIT_FRESH_ELIGIBLE_KIND
                or review_eligibility.get("prior_wait_recheck_kind") != "V2R4_WAIT_EXPIRY_V1"
                or review_eligibility.get("fresh_bar_closed_after_expiry") is not True
                or review_eligibility.get("original_wait_and_expiry_immutable") is not True):
            return _result("NO_FULL_REVIEW_ELIGIBILITY", **common)
    if review_status == CONTINUITY_ELIGIBLE_STATUS:
        if (review_eligibility.get("kind") != CONTINUITY_ELIGIBLE_KIND
                or review_eligibility.get("original_candidate_fresh") is not True
                or review_eligibility.get("new_closed_15m_bar_after_candidate") is not True
                or review_eligibility.get("baseline_v2r4_decision_unchanged") is not True):
            return _result("NO_FULL_REVIEW_ELIGIBILITY", **common)
    if full_assessment is None:
        return _result("UNKNOWN_FULL_ASSESSMENT_NOT_PRODUCED", **common)

    try:
        pair = str(candidate["pair"])
        candidate_id = str(candidate["candidate_id"])
        if not pair.endswith("/EUR") or not candidate_id:
            raise ValueError("canonical EUR candidate required")
        if review_eligibility.get("pair") != pair or review_eligibility.get("source_candidate_id") != candidate_id:
            raise ValueError("review/candidate identity mismatch")
        if entry_evidence.get("kind") != "SUCCESSOR_COIN_ENTRY_EVIDENCE_V1" or entry_evidence.get("status") != "COMPLETE":
            raise ValueError("complete canonical entry evidence required")
        if entry_evidence.get("pair") != pair:
            raise ValueError("entry evidence pair mismatch")
        frames = entry_evidence.get("frames")
        if not isinstance(frames, dict) or set(frames) != {"1", "5", "15"}:
            raise ValueError("1m/5m/15m frames required")
        for key in ("1", "5", "15"):
            frame = frames[key]
            if frame.get("status") != "VALID" or frame.get("interval_min") != int(key):
                raise ValueError("invalid closed frame")
            _positive(frame.get("closed_close_eur"))
            _nonnegative(frame.get("volume_ratio_prior_5"))
        _positive(frames["15"].get("atr14_eur"))
        _positive(frames["15"].get("recent_8bar_low_eur"))

        decision_at = _utc(decision_at_utc)
        if review_status == WAIT_FRESH_ELIGIBLE_STATUS:
            expired = _utc(review_eligibility["expired_at_utc"])
            reclaimed_at = _utc(review_eligibility["fresh_post_expiry_15m_close"])
            if not expired < reclaimed_at <= decision_at:
                raise ValueError("P2 bar not proven after WAIT expiry")
            if review_eligibility.get("new_snapshot_known_at_utc") != entry_evidence.get("known_at_utc"):
                raise ValueError("P2 review/evidence clock mismatch")
        if review_status == CONTINUITY_ELIGIBLE_STATUS:
            fresh_bar_end = _utc(review_eligibility["fresh_close_at_utc"])
            if not fresh_bar_end <= decision_at:
                raise ValueError("P3 fresh closed bar must predate assessment")
            if review_eligibility.get("new_snapshot_known_at_utc") != entry_evidence.get("known_at_utc"):
                raise ValueError("P3 review/evidence clock mismatch")
        known_at = _utc(entry_evidence["known_at_utc"])
        observed_at = _utc(entry_evidence["observed_at_utc"])
        ticker_at = _utc(fresh_ticker["observed_at_utc"])
        metadata_at = _utc(pair_metadata["observed_at_utc"])
        if not observed_at <= known_at <= ticker_at <= decision_at:
            raise ValueError("forward-known or reversed PIT clock")
        if max((decision_at-known_at).total_seconds(), (decision_at-ticker_at).total_seconds(),
               (decision_at-metadata_at).total_seconds()) > SOURCE_MAX_AGE_SECONDS:
            raise ValueError("stale decision input")
        if any(_utc(frames[k]["last_closed_bar_end_utc"]) > observed_at for k in frames):
            raise ValueError("open/future candle")

        if pair_metadata.get("pair") != pair or pair_metadata.get("status") != "online":
            raise ValueError("Kraken pair is not current online authority")
        if pair_metadata.get("spot") is not True or pair_metadata.get("quote") != "EUR":
            raise ValueError("Kraken online Spot EUR required")
        if pair_metadata.get("minimum_order_passed") is not True:
            raise ValueError("public minimum order gate missing")

        if fresh_ticker.get("pair") != pair:
            raise ValueError("ticker pair mismatch")
        ask = _positive(fresh_ticker["ask"])
        bid = _positive(fresh_ticker["bid"])
        if bid > ask:
            raise ValueError("inverted ticker")
        spread_pct = (ask-bid) / ((ask+bid)/2) * 100
        supplied_spread = _nonnegative(fresh_ticker["spread_pct"])
        if not math.isclose(spread_pct, supplied_spread, rel_tol=1e-4, abs_tol=1e-4):
            raise ValueError("ticker spread mismatch")

        if full_assessment.get("candidate_id") != candidate_id or full_assessment.get("pair") != pair:
            raise ValueError("assessment identity mismatch")
        if _utc(full_assessment["decision_at_utc"]) != decision_at:
            raise ValueError("assessment clock mismatch")
        decision = full_assessment.get("decision")
        lane = full_assessment.get("setup_lane")
        if decision not in ALLOWED_DECISIONS or lane not in ALLOWED_SETUP_LANES:
            raise ValueError("invalid full assessment decision")
        if not isinstance(full_assessment.get("reason_codes"), list):
            raise ValueError("reason codes required")
    except (KeyError, TypeError, ValueError, OverflowError):
        return _result("UNKNOWN_REQUIRED_PIT_OR_EXECUTION_EVIDENCE", **common)

    if decision == "REJECT":
        return _result("FULL_REJECT_VALIDATED_OFFLINE", decision="REJECT", **common,
                       setup_lane=lane, reason_codes=full_assessment["reason_codes"][:8])
    if decision == "WAIT":
        ttl = full_assessment.get("ttl_minutes")
        watch = full_assessment.get("watch_conditions")
        if type(ttl) is not int or not 1 <= ttl <= 60 or not isinstance(watch, list) or not watch:
            return _result("UNKNOWN_INVALID_WAIT_CONTRACT", **common)
        return _result("FULL_WAIT_VALIDATED_OFFLINE", decision="WAIT", **common,
                       setup_lane=lane, ttl_minutes=ttl, watch_conditions=watch,
                       reason_codes=full_assessment["reason_codes"][:8])

    # BUY_SCOUT: an explicit full decision is still only an inactive candidate.
    try:
        if full_assessment.get("anti_chase_passed") is not True:
            raise ValueError("anti-chase did not pass")
        stop = _positive(full_assessment["stop_eur"])
        stage2 = _positive(full_assessment["stage2_trigger_eur"])
        stage2_ttl = full_assessment["stage2_ttl_minutes"]
        expected_move = _positive(full_assessment["expected_remaining_move_pct"])
        slippage = _nonnegative(slippage_pct_each_side)
        if not stop < ask or not stage2 > ask or type(stage2_ttl) is not int or not 1 <= stage2_ttl <= 60:
            raise ValueError("invalid two-stage risk plan")
        total_cost_pct = 2*FEE_PCT_EACH_SIDE + spread_pct + 2*slippage
        net_edge_pct = expected_move-total_cost_pct
        downside_pct = (ask-stop)/ask*100 + total_cost_pct
        risk_reward_after_costs = net_edge_pct/downside_pct
        if net_edge_pct <= 0 or risk_reward_after_costs <= 0:
            raise ValueError("no positive cost-adjusted edge")
    except (KeyError, TypeError, ValueError, OverflowError):
        return _result("FAIL_CLOSED_NONEXECUTABLE_BUY_AS_REJECT", decision="REJECT", **common,
                       reason_codes=["INVALID_COST_OR_TWO_STAGE_PLAN"])

    return _result(
        "FULL_BUY_SCOUT_CONTRACT_VALIDATED_OFFLINE_NOT_RELEASE_EVIDENCE",
        decision="BUY_SCOUT", **common, setup_lane=lane,
        reason_codes=full_assessment["reason_codes"][:8],
        decision_at_utc=decision_at_utc,
        execution_ask_eur=round(ask, 10),
        execution_bid_eur=round(bid, 10),
        stop_eur=round(stop, 10),
        stage2_trigger_eur=round(stage2, 10),
        stage2_ttl_minutes=stage2_ttl,
        spread_pct=round(spread_pct, 6),
        slippage_pct_each_side=round(slippage, 6),
        total_round_trip_cost_pct=round(total_cost_pct, 6),
        expected_remaining_move_pct=round(expected_move, 6),
        net_edge_pct_before_path_outcome=round(net_edge_pct, 6),
        risk_reward_after_costs=round(risk_reward_after_costs, 6),
        full_e2e_economic_outcome_required=True,
    )
