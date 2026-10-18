#!/usr/bin/env python3
"""INACTIVE V3 candidate: one-change EARLY closed-5m CONTINUITY review.

Unlike P3, this need not wait for a new closed 15m candle AFTER the scanner
candidate. It DOES require fresh closed 5m after detection, a completed
pre-existing 15m consolidation base, OHLC/ATR/low, unchanged 1.2 relative
volume, ask, spread and anti-chase. Review permission is NEVER a BUY.
No models, writers, storage, scheduling, cloud traffic or active V2R4 imports.
"""
from __future__ import annotations

import math
from datetime import timedelta
from typing import Any

from paper_evaluator.v3_entry_handoff_probe import attach_to_future_evaluator,utc
from paper_evaluator.v3_second_leg_policy_candidate_v1 import (
    _bar_start, CLOSED_BAR_SECONDS, SOURCE_MAX_AGE_SECONDS,
    MAX_BASE_WIDTH_ATR, MAX_RECLAIM_EXTENSION_ATR, SPREAD_LIMIT_PCT,
)
from paper_evaluator.v3_continuity_fresh_review_candidate_v1 import MAX_FRESH_CANDIDATE_SECONDS
from paper_evaluator.v3_extended_reentry_review_v1 import (
    _finite_positive, EXISTING_V2R4_VOLUME_RATIO_REVIEW_FLOOR,
)

KIND="V3_P3_INACTIVE_EARLY_5M_CONTINUITY_FRESH_REVIEW_V1"
ELIGIBLE="EARLY_5M_CONTINUITY_SUPPORTS_NEW_FULL_REVIEW_ONLY"
CHECKS=frozenset({
    "new_closed_5m_after_original_candidate",
    "old_closed_15m_base_precedes_candidate",
    "prior_15m_base_not_excessive",
    "closed_5m_price_continuation",
    "unchanged_closed_5m_volume_floor",
    "fresh_eur_spread_guard",
    "fresh_ask_not_chase",
    "only_structural_reference_below_ask",
})


def propose_early_5m_continuity_review(
    candidate: dict[str,Any], baseline_decision: dict[str,Any],
    entry_evidence: dict[str,Any], ticker: dict[str,Any],
    closed_15m_bars: list[dict[str,Any]], *, decision_at_utc: str,
    optional_sources: dict[str,Any]|None=None,
)->dict[str,Any]:
    cid=candidate.get("candidate_id")
    pair=candidate.get("pair")
    base={
        "kind":KIND,"pair":pair,"source_candidate_id":cid,
        "decision":"NO_DECISION_AUTHORITY","request_model_recheck_only":False,
        "approval_to_call_model":False,"model_called":False,
        "paper_trade":False,"paper_writer_started":False,"paper_state_changed":False,
        "orders":False,"real_money_actions":False,"auto_buy":False,
        "economic_edge_proven":False,"release_evidence":False,
        "baseline_v2r4_decision_unchanged":True,
        "changes_v2r4":False,"changes_wait_ttl":False,
        "changes_stop_or_stage2_policy":False,"changes_h3_h6":False,
        "fee_pct_each_side_unchanged":0.6,"scout_eur_unchanged":50,
        "stage2_eur_unchanged":50,"optional_sources_are_context_only":True,
        "optional_source_names":tuple(sorted((optional_sources or {}).keys())),
        "same_clock_comparison_required":True,
        "snapshot_recheck_must_be_deduplicated":True,
        "new_strategy_version_required":True,
    }
    def result(status:str,**extra:Any)->dict[str,Any]:
        return {**base,"status":status,**extra}
    if baseline_decision.get("setup_lane")!="CONTINUITY" or baseline_decision.get("decision") not in ("WAIT","REJECT"):
        return result("OUT_OF_SCOPE_NOT_ORIGINAL_CONTINUITY_NONBUY")
    if not isinstance(cid,str) or not cid or not isinstance(pair,str) or not pair.endswith("/EUR"):
        return result("UNKNOWN_CANONICAL_EUR_IDENTITY")
    stage="PIT_FRESH_SOURCE"
    try:
        at=utc(decision_at_utc); detected=utc(candidate["event_time_utc"])
        if not 0 <= (at-detected).total_seconds() <= MAX_FRESH_CANDIDATE_SECONDS:
            return result("ORIGINAL_CANDIDATE_TOO_OLD_OR_FUTURE")
        attach_to_future_evaluator({"pair":pair},{},entry_evidence,
                                   decision_at_utc,max_evidence_age_seconds=SOURCE_MAX_AGE_SECONDS)
        observed=utc(entry_evidence["observed_at_utc"])
        quote_at=utc(ticker["observed_at_utc"])
        if not detected <= quote_at <= at or (at-quote_at).total_seconds()>SOURCE_MAX_AGE_SECONDS:
            return result("UNKNOWN_KRAKEN_EUR_TICKER_AGE")

        stage="EXISTING_CLOSED_15M_BASE"
        if not isinstance(closed_15m_bars,list) or len(closed_15m_bars)<2:
            return result("UNKNOWN_PREEXISTING_15M_BASE")
        base_bars=closed_15m_bars[-2:]
        times=[_bar_start(x) for x in base_bars]
        if times[1]-times[0] != timedelta(seconds=CLOSED_BAR_SECONDS):
            return result("NONCONTIGUOUS_PRIOR_15M_BASE")
        ends=times[-1]+timedelta(seconds=CLOSED_BAR_SECONDS)
        # Early hypothesis is ONLY applicable before the next 15m close;
        # it is not another P3 eligibility after that close.
        if not ends <= detected:
            return result("NO_PRIOR_CLOSED_15M_BASE")
        f15=entry_evidence["frames"]["15"]
        if utc(f15["last_closed_bar_end_utc"]) != ends:
            return result("15M_BASE_AND_KRAKEN_FRAME_CLOCK_MISMATCH")
        if not math.isclose(float(base_bars[-1]["close"]),
                            _finite_positive(f15["closed_close_eur"]),
                            rel_tol=1e-9, abs_tol=1e-10):
            return result("15M_BASE_CLOSE_PRICE_AND_PIT_MISMATCH")
        for bar in base_bars:
            lo=_finite_positive(bar["low"]);hi=_finite_positive(bar["high"])
            op=_finite_positive(bar["open"]);cl=_finite_positive(bar["close"])
            if not lo<=min(op,cl)<=max(op,cl)<=hi:
                return result("INVALID_PREEXISTING_15M_OHLC")

        stage="ONE_CHANGE_FRESH_CLOSED_5M"
        f5=entry_evidence["frames"]["5"]
        if f5.get("status") != "VALID":
            return result("UNKNOWN_REQUIRED_CLOSED_5M_SOURCE_STATUS")
        close5_end=utc(f5["last_closed_bar_end_utc"])
        if not detected < close5_end <= observed:
            return result("NO_NEW_CLOSED_5M_AFTER_CANDIDATE")
        # No current unclosed 15m candle may be used as if already known.
        if close5_end > ends+timedelta(seconds=CLOSED_BAR_SECONDS):
            return result("NEW_15M_PERIOD_ALREADY_PASSED_USE_STANDARD_FAMILY")
        close5=_finite_positive(f5["closed_close_eur"])
        atr=_finite_positive(f15["atr14_eur"])
        ask=_finite_positive(ticker["ask"]);bid=_finite_positive(ticker["bid"])
        if bid>ask:
            return result("INVERTED_KRAKEN_EUR_BID_ASK")
        ratio=f5["volume_ratio_prior_5"]
        if type(ratio) not in (int,float) or not math.isfinite(ratio) or ratio<0:
            return result("UNKNOWN_5M_RELATIVE_VOLUME")
        low=min(_finite_positive(f15["recent_8bar_low_eur"]),
                min(float(b["low"]) for b in base_bars))
        high=max(float(b["high"]) for b in base_bars)
        base_low=min(float(b["low"]) for b in base_bars)
        spread=(ask-bid)/((ask+bid)/2)*100
        checks={
            "new_closed_5m_after_original_candidate": detected<close5_end<=observed,
            "old_closed_15m_base_precedes_candidate": ends<=detected,
            "prior_15m_base_not_excessive": high-base_low<=MAX_BASE_WIDTH_ATR*atr,
            "closed_5m_price_continuation": high<close5<=high+MAX_RECLAIM_EXTENSION_ATR*atr,
            "unchanged_closed_5m_volume_floor": ratio>=EXISTING_V2R4_VOLUME_RATIO_REVIEW_FLOOR,
            "fresh_eur_spread_guard": spread<=SPREAD_LIMIT_PCT,
            "fresh_ask_not_chase": close5<=ask<=high+MAX_RECLAIM_EXTENSION_ATR*atr,
            "only_structural_reference_below_ask": 0<low<ask,
        }
        if not all(checks.values()):
            return result("EARLY_5M_FRESH_CONFIRMATION_INSUFFICIENT",checks=checks)
        r=result(
            ELIGIBLE,checks=checks,request_model_recheck_only=True,
            original_candidate_fresh=True,
            new_closed_5m_bar_after_candidate=True,
            prior_closed_15m_base_end_at_utc=ends.isoformat(),
            fresh_close_at_utc=close5_end.isoformat(),
            new_snapshot_known_at_utc=entry_evidence["known_at_utc"],
            snapshot_recheck_key=f"{cid}|{close5_end.isoformat()}|EARLY_5M_P3",
            descriptive_stop_reference_eur=round(low,10),
            fee_plus_spread_pct_before_slippage=round(1.2+spread,6),
            only_full_evaluator_can_decide_buy=True,
            next_action="ONLY_SEPARATELY_AUTHORIZED_RESEARCH_FULL_MODEL_REVIEW",
        )
        return r
    except (ValueError,TypeError,KeyError,OverflowError,AttributeError,OSError):
        return result("UNKNOWN_PIT_OR_INPUT_FAILURE",validation_stage=stage)
