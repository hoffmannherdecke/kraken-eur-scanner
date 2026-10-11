#!/usr/bin/env python3
"""V3 experimental PAPER initial entry: FULL fresh model review, not a BUY.

Historical finding: V2R3/R4 WAIT and EXTENDED delayed or terminalized the
strongest fresh signals. Allow a complete independent full-model review at the
FIRST actual scanner opportunity across IGNITION/CONTINUITY/REVERSAL/EXTENDED
without requiring a post-signal 15m/5m wait. Unlike later P1/P2/P3 reviews,
the 1/5/15m Kraken OHLC MUST have closed before original decision clock.
No score/macro/derivative/news/onchain hard veto. Core Spot EUR/ATR/stop/ask/
spread data are required; discretionary volume quality belongs to full
model decision, not a universal "volume >= 1.2" research gate.

PURE research code, no model call, orders, writers or V2R4 modifications.
"""
from __future__ import annotations

import math
from typing import Any
from paper_evaluator.v3_entry_handoff_probe import attach_to_future_evaluator, utc

KIND="V3_EXPERIMENTAL_PAPER_INITIAL_FRESH_FULL_REVIEW_V1"
ELIGIBLE="INITIAL_FRESH_PIT_READY_FOR_FULL_V3_MODEL_ONLY"
MAX_AGE=15*60
MAX_PIT_AGE=120
MAX_SPREAD_PCT=0.5
CHECKS=frozenset({
    "fresh_original_candidate",
    "complete_real_closed_coin_frames",
    "positive_coin_atr",
    "structural_invalidating_low_below_ask",
    "current_online_kraken_spot_eur",
    "kraken_order_minimum_pass",
    "fresh_noninverted_ask_bid",
    "execution_spread_at_most_half_percent",
})


def propose_initial_full_review(candidate:dict[str,Any],
                                entry_evidence:dict[str,Any],
                                fresh_ticker:dict[str,Any],
                                pair_metadata:dict[str,Any],
                                *,decision_at_utc:str,
                                optional_context:dict[str,Any]|None=None)->dict[str,Any]:
    cid=candidate.get("candidate_id")
    pair=candidate.get("pair")
    def result(status:str,**fields:Any)->dict[str,Any]:
        return {
            "kind":KIND,"status":status,"source_candidate_id":cid,"pair":pair,
            "decision":"NO_DECISION_AUTHORITY",
            "request_model_recheck_only":False,"approval_to_call_model":False,
            "paper_trade":False,"paper_writer_started":False,"model_called":False,
            "paper_state_changed":False,"orders":False,"real_money_actions":False,
            "auto_buy":False,"release_evidence":False,"economic_edge_proven":False,
            "must_run_full_independent_v3_model_and_shared_p4":True,
            "fee_pct_each_side":0.6,"scout_eur":50,"stage2_eur":50,
            "no_automatic_activation":True,
            "optional_context_never_required":True,
            "optional_context_names":sorted((optional_context or {}).keys()),
            "no_scanner_score_shortcut":True,
            "no_universal_volume_1_2_hard_gate":True,
            "new_strategy_version_required":True,**fields,
        }
    if not isinstance(cid,str) or not cid or not isinstance(pair,str) or not pair.endswith("/EUR"):
        return result("UNKNOWN_CANONICAL_CANDIDATE")
    stage="ORIGINAL_CANDIDATE_TIME"
    try:
        clock=utc(decision_at_utc)
        detected=utc(candidate["event_time_utc"])
        if not 0<=(clock-detected).total_seconds()<=MAX_AGE:
            return result("STALE_OR_FUTURE_ORIGINAL_CANDIDATE")
        stage="CLOSED_1M_5M_15M_COIN"
        attach_to_future_evaluator(
            {"pair":pair},{},entry_evidence,decision_at_utc,
            max_evidence_age_seconds=MAX_PIT_AGE
        )
        frames=entry_evidence["frames"]
        atr=frames["15"]["atr14_eur"]
        low=frames["15"]["recent_8bar_low_eur"]
        volume=frames["5"]["volume_ratio_prior_5"]
        if (type(atr) not in (int,float) or not math.isfinite(atr) or atr<=0
                or type(low) not in (int,float) or not math.isfinite(low) or low<=0
                or type(volume) not in (int,float) or not math.isfinite(volume)
                or volume<0):
            return result("UNKNOWN_COIN_ATR_LOW_OR_VOLUME")
        # Existing valid frames confirm OHLC source integrity. A closed bar
        # may precede detection, but NEVER originate after the known-at clock.
        stage="KRAKEN_EXECUTION_METADATA"
        ticker_at=utc(fresh_ticker["observed_at_utc"])
        meta_at=utc(pair_metadata["observed_at_utc"])
        known_at=utc(entry_evidence["known_at_utc"])
        if not known_at<=ticker_at<=clock or not meta_at<=clock:
            return result("UNKNOWN_EXECUTION_OR_METADATA_CLOCK")
        if ((clock-ticker_at).total_seconds()>MAX_PIT_AGE or
                (clock-meta_at).total_seconds()>MAX_PIT_AGE):
            return result("UNKNOWN_STALE_EXECUTION_OR_METADATA")
        ask=fresh_ticker["ask"];bid=fresh_ticker["bid"]
        if (type(ask) not in (int,float) or type(bid) not in (int,float)
                or not math.isfinite(ask) or not math.isfinite(bid)
                or min(ask,bid)<=0 or bid>ask):
            return result("UNKNOWN_INVERTED_OR_INVALID_EXECUTION_QUOTE")
        if fresh_ticker.get("pair")!=pair or pair_metadata.get("pair")!=pair:
            return result("UNKNOWN_KRAKEN_EUR_PAIR_MISMATCH")
        spread=(ask-bid)/((ask+bid)/2)*100
        checks={
            "fresh_original_candidate":0<=(clock-detected).total_seconds()<=MAX_AGE,
            "complete_real_closed_coin_frames":True,
            "positive_coin_atr":True,
            "structural_invalidating_low_below_ask":0<low<ask,
            "current_online_kraken_spot_eur":(
                pair_metadata.get("status")=="online"
                and pair_metadata.get("spot") is True
                and pair_metadata.get("quote")=="EUR"),
            "kraken_order_minimum_pass":pair_metadata.get("minimum_order_passed") is True,
            "fresh_noninverted_ask_bid":0<bid<=ask,
            "execution_spread_at_most_half_percent":spread<=MAX_SPREAD_PCT,
        }
        if not all(checks.values()):
            return result("CORE_ENTRY_OR_TRADABILITY_NOT_READY",checks=checks,
                          failing_checks=sorted(k for k,v in checks.items() if not v))
        return result(
            ELIGIBLE,request_model_recheck_only=True,
            checks=checks,
            original_candidate_fresh=True,
            new_snapshot_known_at_utc=entry_evidence["known_at_utc"],
            decision_at_utc=decision_at_utc,
            source_5m_volume_ratio=round(float(volume),6),
            descriptive_stop_low_eur=round(float(low),10),
            descriptive_atr_eur=round(float(atr),10),
            spread_pct=round(spread,6),
            indicative_round_trip_cost_pct_before_slippage=round(1.2+spread,6),
            exact_full_model_consumer_required=True,
            next_action="USE_AUTHORIZED_V3_PAPER_MODEL_WITH_FULL_P4_NOT_AUTOBUY",
        )
    except (KeyError,ValueError,TypeError,OverflowError,AttributeError):
        return result("UNKNOWN_REQUIRED_INITIAL_PIT_OR_QUOTE",validation_stage=stage)
