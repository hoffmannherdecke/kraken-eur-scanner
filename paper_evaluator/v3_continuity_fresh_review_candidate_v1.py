#!/usr/bin/env python3
"""INACTIVE V3-P3 CONTINUITY: first fresh confirmed closed-bar review eligibility.

Independent from the P1 EXTENDED second-leg and P2 completed WAIT-expiry
research families. No model calls, orders, writers, timers or live V2R4 effects.
The old V2R4 full model decision is a matched control, not trading permission.
"""
from __future__ import annotations

import math
from datetime import timedelta
from typing import Any

from paper_evaluator.v3_entry_handoff_probe import attach_to_future_evaluator, utc
from paper_evaluator.v3_second_leg_policy_candidate_v1 import (
    _bar_start, CLOSED_BAR_SECONDS, MAX_BASE_WIDTH_ATR,
    MAX_RECLAIM_EXTENSION_ATR, SOURCE_MAX_AGE_SECONDS, SPREAD_LIMIT_PCT,
)
from paper_evaluator.v3_extended_reentry_review_v1 import (
    _finite_positive, EXISTING_V2R4_VOLUME_RATIO_REVIEW_FLOOR,
)

KIND="V3_P3_INACTIVE_CONTINUITY_FRESH_REVIEW_ELIGIBILITY_V1"
ELIGIBLE="CONTINUITY_FRESH_STRUCTURE_SUPPORTS_NEW_FULL_REVIEW_ONLY"
MAX_FRESH_CANDIDATE_SECONDS=15*60


def propose_continuity_fresh_review(
    candidate: dict[str, Any],
    baseline_decision: dict[str, Any],
    entry_evidence: dict[str, Any],
    ticker: dict[str, Any],
    closed_15m_bars: list[dict[str, Any]],
    *,
    decision_at_utc: str,
    optional_sources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One new research-only REVIEW lane, not any new permissive BUY policy."""
    cid=candidate.get("candidate_id")
    pair=candidate.get("pair")
    neutral=tuple(sorted((optional_sources or {}).keys()))
    def out(status: str, **extra: Any) -> dict[str, Any]:
        return {
            "kind":KIND, "status":status, "source_candidate_id":cid, "pair":pair,
            "decision":"NO_DECISION_AUTHORITY", "request_model_recheck_only":False,
            "approval_to_call_model":False, "no_automatic_model_or_shadow":True,
            "baseline_v2r4_decision_unchanged":True, "changes_v2r4":False,
            "changes_wait_ttl":False, "changes_stop_or_stage2_policy":False,
            "changes_h3_h6":False, "paper_state_changed":False,
            "paper_trade":False, "orders":False, "real_money_actions":False,
            "auto_buy":False, "economic_edge_proven":False,
            "new_strategy_version_required":True,
            "snapshot_recheck_must_be_deduplicated":True,
            "fee_pct_each_side_unchanged":.6,"scout_eur_unchanged":50,
            "stage2_eur_unchanged":50,
            "optional_sources_are_context_only":True,
            "optional_source_names":neutral,
            "next_action":"NONE_RESEARCH_ONLY", **extra,
        }
    if baseline_decision.get("setup_lane")!="CONTINUITY" or baseline_decision.get("decision") not in {"WAIT","REJECT"}:
        return out("OUT_OF_SCOPE_NOT_EARLY_CONTINUITY_WAIT_OR_REJECT")
    if not isinstance(cid,str) or not cid or not isinstance(pair,str) or not pair.endswith("/EUR"):
        return out("MISSING_CANONICAL_EUR_CANDIDATE_ID")

    stage="FRESH_CANDIDATE_AND_CANONICAL_ENTRY_PIT"
    try:
        at=utc(decision_at_utc)
        detected=utc(candidate["event_time_utc"])
        if not 0 <= (at-detected).total_seconds() <= MAX_FRESH_CANDIDATE_SECONDS:
            return out("NOT_A_FRESH_CONTINUITY_CANDIDATE")
        attach_to_future_evaluator({"pair":pair},{},entry_evidence,
                                   decision_at_utc,max_evidence_age_seconds=SOURCE_MAX_AGE_SECONDS)
        quote_at=utc(ticker["observed_at_utc"])
        if not detected <= quote_at <= at or (at-quote_at).total_seconds()>SOURCE_MAX_AGE_SECONDS:
            return out("UNKNOWN_FRESH_EUR_TICKER_CLOCK")

        stage="CLOSED_15M_CONTINUITY_STRUCTURE"
        if not isinstance(closed_15m_bars,list) or len(closed_15m_bars)<3:
            return out("MISSING_CONTIGUOUS_CLOSED_15M_HISTORY")
        seq=closed_15m_bars[-3:]
        times=[_bar_start(x) for x in seq]
        if any(times[i]-times[i-1]!=timedelta(seconds=CLOSED_BAR_SECONDS) for i in (1,2)):
            return out("NONCONTIGUOUS_CLOSED_15M_HISTORY")
        newest_end=times[-1]+timedelta(seconds=CLOSED_BAR_SECONDS)
        observed=utc(entry_evidence["observed_at_utc"])
        # The evidence must close AFTER candidate detection, known no earlier
        # than the close; an old remembered breakout cannot be recycled.
        if not detected < newest_end <= observed:
            return out("NO_NEW_CLOSED_CONTINUITY_BAR_AFTER_CANDIDATE")
        f15=entry_evidence["frames"]["15"]
        if utc(f15["last_closed_bar_end_utc"])!=newest_end:
            return out("CONTINUITY_CLOSED_CANDLE_CLOCK_MISMATCH")
        for bar in seq:
            lo=_finite_positive(bar.get("low"))
            hi=_finite_positive(bar.get("high"))
            op=_finite_positive(bar.get("open"))
            cl=_finite_positive(bar.get("close"))
            if not lo <= min(op,cl) <= max(op,cl) <= hi:
                return out("INVALID_CONTINUITY_OHLC_HISTORY")
        old_high=max(float(x["high"]) for x in seq[:-1])
        old_low=min(float(x["low"]) for x in seq[:-1])
        latest=float(seq[-1]["close"])
        if not math.isclose(latest,float(f15["closed_close_eur"]),rel_tol=1e-9):
            return out("CONTINUITY_BAR_EVIDENCE_PRICE_MISMATCH")

        stage="VOLUME_ANTI_CHASE_SPREAD_AND_STOP_REFERENCE"
        atr=_finite_positive(f15["atr14_eur"])
        close5=_finite_positive(entry_evidence["frames"]["5"]["closed_close_eur"])
        # 0.0 is a VALID but insufficient 5m volume ratio, not UNKNOWN.
        relative_volume=float(entry_evidence["frames"]["5"]["volume_ratio_prior_5"])
        ask=_finite_positive(ticker["ask"])
        bid=_finite_positive(ticker["bid"])
        if bid>ask:
            return out("INVERTED_KRAKEN_EUR_TICKER")
        spread=(ask-bid)/((ask+bid)/2)*100
        low=min(old_low,_finite_positive(f15["recent_8bar_low_eur"]))
        checks={
            "closed_new_15m_continuation_above_base":latest>old_high,
            "prior_15m_base_not_excessive":(old_high-old_low)<=MAX_BASE_WIDTH_ATR*atr,
            "no_new_excessive_extension":(latest-old_high)<=MAX_RECLAIM_EXTENSION_ATR*atr,
            "closed_5m_price_continuation":close5>=old_high,
            "unchanged_closed_5m_volume_floor":relative_volume>=EXISTING_V2R4_VOLUME_RATIO_REVIEW_FLOOR,
            "fresh_eur_spread_guard":spread<=SPREAD_LIMIT_PCT,
            "fresh_ask_not_chase":(ask-old_high)<=MAX_RECLAIM_EXTENSION_ATR*atr,
            "only_structural_reference_below_ask":0<low<ask,
        }
        if not all(checks.values()):
            return out("CONTINUITY_EARLY_CONFIRMATION_NOT_PROVEN",checks=checks)
        ans=out(
            ELIGIBLE,checks=checks,
            original_candidate_fresh=True,
            new_closed_15m_bar_after_candidate=True,
            fresh_close_at_utc=newest_end.isoformat(),
            new_snapshot_known_at_utc=entry_evidence["known_at_utc"],
            snapshot_recheck_key=f"{cid}|{newest_end.isoformat()}",
            fee_plus_spread_pct_before_slippage=round(1.2+spread,4),
            descriptive_stop_reference_eur=round(low,10),
            only_full_evaluator_can_decide_buy=True,
        )
        ans["request_model_recheck_only"]=True
        ans["next_action"]="ONLY_IF_SEPARATELY_APPROVED_FULL_MODEL_COMPARE"
        return ans
    except (ValueError, TypeError, KeyError, OverflowError, OSError, AttributeError):
        return out("UNKNOWN_REQUIRED_COIN_OR_CONTINUITY_PIT",validation_stage=stage)
