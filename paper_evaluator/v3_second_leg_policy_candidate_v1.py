#!/usr/bin/env python3
"""INACTIVE V3-B second-leg decision-policy candidate: fresh review eligibility ONLY.

An old EXTENDED V2R4 outcome is a historical anchor, never fresh trade evidence.
A later independently time-stamped Kraken EUR snapshot and 1-3h closed 15m
consolidation may authorize a NEW complete model assessment in a separately
approved shadow. It never issues BUY/WAIT/REJECT, starts a watcher, calls a
model, writes storage, modifies V2R4 or prices a tradable stop.
"""
from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta, timezone
from typing import Any

from paper_evaluator.v3_entry_handoff_probe import attach_to_future_evaluator, utc
from paper_evaluator.v3_extended_reentry_review_v1 import (
    EXISTING_V2R4_VOLUME_RATIO_REVIEW_FLOOR,
    _finite_positive,
)

# Pre-registered conservative RESEARCH boundaries, not tuned on October outcomes.
MIN_BASE_BARS = 4       # 1h
MAX_BASE_BARS = 12      # 3h
CLOSED_BAR_SECONDS = 15 * 60
SOURCE_MAX_AGE_SECONDS = 120
MAX_REVIEW_HORIZON_SECONDS = 4 * 60 * 60
MAX_BASE_WIDTH_ATR = 3.0
MAX_RECLAIM_EXTENSION_ATR = 0.75
SPREAD_LIMIT_PCT = 0.5


def _outcome(state: str, **fields: Any) -> dict[str, Any]:
    return {
        "kind": "V3_B_INACTIVE_SECOND_LEG_FRESH_REVIEW_ELIGIBILITY_V1",
        "status": state,
        "decision": "NO_DECISION_AUTHORITY",
        "request_model_recheck_only": False,
        "new_strategy_version_required": True,
        "approval_to_call_model": False,
        "snapshot_recheck_must_be_deduplicated": True,
        "paper_state_changed": False,
        "paper_trade": False,
        "orders": False,
        "real_money_actions": False,
        "auto_buy": False,
        "changes_v2r4": False,
        "changes_wait_ttl": False,
        "changes_h3_h6": False,
        "changes_stop_or_stage2_policy": False,
        "economic_edge_proven": False,
        **fields,
    }


def _bar_start(bar: dict[str, Any]) -> datetime:
    raw = bar.get("start_utc")
    if type(raw) is int:
        return datetime.fromtimestamp(raw, timezone.utc)
    if isinstance(raw, str):
        return utc(raw)
    raise ValueError("bar start missing or invalid")


def canonical_second_leg_episode(*,series_id:str,
        original_candidate:dict[str,Any],closed_15m_end_utc:str,
        signal_known_at_utc:str)->dict[str,Any]:
    """Stable candidate-linked P1 episode, NOT an order or an inferred fill.

    The closed 15m bar identifies ONE potential opportunity; the recorded
    first observation/known time is the new episode event clock. A later
    Paper fill must still use its own actual immutable fill known_at clock
    for stop/Stage2 and 6/24/72-hour outcome maturity.
    """
    if (not isinstance(series_id,str) or not series_id.startswith("PAPER-V3-")
            or not isinstance(original_candidate,dict)):
        raise ValueError("canonical V3 episode series and original required")
    cid=original_candidate.get("candidate_id")
    pair=original_candidate.get("pair")
    if (not isinstance(cid,str) or not 1<=len(cid)<=150
            or not isinstance(pair,str) or not pair.endswith("/EUR")):
        raise ValueError("canonical original EUR candidate identity required")
    from paper_evaluator.v3_entry_handoff_probe import utc
    first=utc(original_candidate["event_time_utc"])
    closed=utc(closed_15m_end_utc)
    observed=utc(signal_known_at_utc)
    if (closed.second!=0 or closed.microsecond!=0
            or int(closed.timestamp())%900!=0
            or not first<closed<=observed
            or not 0<=(observed-first).total_seconds()<=4*3600
            or not 0<=(observed-closed).total_seconds()<=120):
        raise ValueError("missing fresh closed prospective 15m episode clock")
    # The identity is stable even if the same source is read again later.
    stable_close=closed.isoformat().replace("+00:00","Z")
    key="|".join((series_id,cid,pair,stable_close))
    digest=hashlib.sha256(key.encode("utf-8")).hexdigest()
    return {
        "reentry_episode_id":"V3RE-"+digest[:32],
        "reentry_parent_candidate_id":cid,
        "reentry_episode_signal_at_utc":
            observed.isoformat().replace("+00:00","Z"),
        "reentry_closed_15m_end_utc":stable_close,
        "reentry_original_event_time_utc":
            first.isoformat().replace("+00:00","Z"),
        "reentry_parent_event_key":"C"+closed.strftime("%Y%m%dT%H%M%SZ"),
        "reentry_will_use_separate_fill_time":True,
    }


def witnessed_15m_from_existing_1m_path(assembled:dict[str,Any],
        *,pair:str,observed_at_utc:str)->list[dict[str,Any]]:
    """Rebuild ONLY complete closed 15m bars from already witnessed 1m.

    assemble() has checked each source file SHA, recorded capture clock and
    maximum 15-minute acquisition lag. This adapter never calls Kraken,
    fabricates missing bars or retrospectively relabels a research move.
    The resulting 15m bars are still RESEARCH eligibility, not model/BUTY.
    """
    from paper_evaluator.v3_paper_minipc_closed_1m_capture_v1 import (
        require_prospective_assembled_path,timestamp,
    )
    require_prospective_assembled_path(assembled=assembled,pair=pair)
    observed=timestamp(observed_at_utc)
    last_seen=timestamp(assembled["captured_at_utc"])
    if last_seen>observed:
        raise ValueError("witnessed source after decision observation")
    minutes={}
    for row in assembled["closed_bars"]:
        start=timestamp(row["start_at_utc"])
        if start+timedelta(minutes=1)>observed:
            raise ValueError("open or future 1m source")
        if start in minutes:
            raise ValueError("duplicate witnessed 1m")
        vals=[]
        for field in ("open","high","low","close"):
            vals.append(_finite_positive(row[field]))
        op,hi,lo,close=vals
        if not lo<=min(op,close)<=max(op,close)<=hi:
            raise ValueError("invalid witnessed 1m OHLC")
        minutes[start]=row
    if not minutes:
        return []
    groups={}
    for ts in sorted(minutes):
        epoch=int(ts.timestamp())
        bar_start=datetime.fromtimestamp(epoch//900*900,timezone.utc)
        groups.setdefault(bar_start,[]).append((ts,minutes[ts]))
    closed=[]
    for begin,group in sorted(groups.items()):
        if begin+timedelta(minutes=15)>observed or len(group)!=15:
            continue
        if any(item[0]!=begin+timedelta(minutes=i) for i,item in enumerate(group)):
            continue
        src=[row for _,row in group]
        closed.append({"start_utc":int(begin.timestamp()),
                       "open":src[0]["open"],
                       "high":max(row["high"] for row in src),
                       "low":min(row["low"] for row in src),
                       "close":src[-1]["close"]})
    return closed[-13:]


def propose_second_leg_review(
    original_candidate: dict[str, Any],
    original_decision: dict[str, Any],
    new_coin_evidence: dict[str, Any],
    fresh_ticker: dict[str, Any],
    closed_15m_bars: list[dict[str, Any]],
    *,
    decision_at_utc: str,
    base_bars: int = MIN_BASE_BARS,
    optional_sources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return an *unprivileged* review hint, never a BUY or executable price.

    A 1-3h base is independent of the original candidate's old event clock.
    Last closed 15m bar must reclaim a genuinely observed earlier base high;
    otherwise no second-leg evaluation is requested. Price is not chased.
    """
    neutral_optional = tuple(sorted((optional_sources or {}).keys()))
    common = {
        "source_candidate_id": original_candidate.get("candidate_id"),
        "pair": original_candidate.get("pair"),
        "optional_sources_are_context_only": True,
        "optional_source_names": neutral_optional,
        "fee_pct_each_side_unchanged": 0.6,
        "scout_eur_unchanged": 50,
        "stage2_eur_unchanged": 50,
        "next_action": "NONE_RESEARCH_ONLY",
    }
    if original_decision.get("setup_lane") != "EXTENDED" or original_decision.get("decision") not in {"REJECT", "WAIT"}:
        return _outcome("OUT_OF_SCOPE_NOT_PRIOR_EXTENDED_WAIT_OR_REJECT", **common)
    if type(base_bars) is not int or not MIN_BASE_BARS <= base_bars <= MAX_BASE_BARS:
        return _outcome("INVALID_RESEARCH_BASE_WINDOW", **common)
    if not original_candidate.get("candidate_id"):
        return _outcome("MISSING_CANONICAL_ORIGINAL_ID", **common)

    validation_stage = "CORE_PIT_SOURCE"
    try:
        first = utc(original_candidate["event_time_utc"])
        decision = utc(decision_at_utc)
        observed = utc(new_coin_evidence["observed_at_utc"])
        elapsed = (decision - first).total_seconds()
        if elapsed < (base_bars + 1) * CLOSED_BAR_SECONDS or elapsed > MAX_REVIEW_HORIZON_SECONDS:
            return _outcome("OUTSIDE_FRESH_SECOND_LEG_OBSERVATION_WINDOW", **common)
        # Old candidate is historical; *new* snapshot evidence must be fresh.
        attach_to_future_evaluator(
            {"pair": original_candidate["pair"]}, {}, new_coin_evidence,
            decision_at_utc, max_evidence_age_seconds=SOURCE_MAX_AGE_SECONDS,
        )
        validation_stage = "CLOSED_BASE_HISTORY"
        if not isinstance(closed_15m_bars, list) or len(closed_15m_bars) < base_bars + 1:
            return _outcome("MISSING_CLOSED_CONSOLIDATION_HISTORY", **common)
        seq = closed_15m_bars[-(base_bars + 1):]
        ticks = [_bar_start(b) for b in seq]
        if any(ticks[i] - ticks[i - 1] != timedelta(seconds=CLOSED_BAR_SECONDS) for i in range(1, len(ticks))):
            return _outcome("NONCONTIGUOUS_BASE_HISTORY", **common)
        if ticks[0] < first:
            return _outcome("BASE_PRECEDES_ORIGINAL_SETUP", **common)
        if ticks[-1] + timedelta(seconds=CLOSED_BAR_SECONDS) > observed:
            return _outcome("FUTURE_OR_OPEN_BREAKOUT_BAR", **common)
        f15 = new_coin_evidence["frames"]["15"]
        if utc(f15["last_closed_bar_end_utc"]) != ticks[-1] + timedelta(seconds=CLOSED_BAR_SECONDS):
            return _outcome("CANDLE_EVIDENCE_CLOCK_MISMATCH", **common)
        for bar in seq:
            high = _finite_positive(bar.get("high"))
            low = _finite_positive(bar.get("low"))
            op = _finite_positive(bar.get("open"))
            close = _finite_positive(bar.get("close"))
            if not low <= min(op, close) <= max(op, close) <= high:
                return _outcome("INVALID_OHLC_BASE_HISTORY", **common)
        old = seq[:-1]
        base_high = max(float(x["high"]) for x in old)
        base_low = min(float(x["low"]) for x in old)
        breakout_close = float(seq[-1]["close"])
        if not math.isclose(float(f15["closed_close_eur"]), breakout_close, rel_tol=1e-9):
            return _outcome("CANDLE_EVIDENCE_PRICE_MISMATCH", **common)
        validation_stage = "CLOSED_COIN_PRICE_ATR_AND_VOLUME"
        atr = _finite_positive(f15["atr14_eur"])
        last_5m = _finite_positive(new_coin_evidence["frames"]["5"]["closed_close_eur"])
        # Canonical Kraken OHLC volume_ratio_prior_5 may legitimately be 0.0
        # while the 5m source frame is VALID. Zero is a CONFIRMED failed
        # volume floor, not missing PIT evidence; it must NOT become UNKNOWN.
        volume_raw = new_coin_evidence["frames"]["5"].get("volume_ratio_prior_5")
        if (isinstance(volume_raw, bool) or not isinstance(volume_raw, (float, int))
                or not math.isfinite(volume_raw) or volume_raw < 0):
            raise ValueError("missing/nonfinite/negative required five minute volume ratio")
        volume_ratio = float(volume_raw)
        validation_stage = "FRESH_EUR_TICKER"
        ask = _finite_positive(fresh_ticker["ask"])
        bid = _finite_positive(fresh_ticker["bid"])
        if ask < bid:
            return _outcome("INVALID_INVERTED_EUR_TICKER", **common)
        spread = (ask-bid) / ((ask+bid)/2) * 100
        validation_stage = "STRUCTURE_GATE_VALUES"
        # The *only* policy delta being proposed is fresh full-review eligibility
        # after a new closed-price reclaim. Existing risk/entry votes are unchanged.
        checks = {
            "base_1_to_3h_rebuilt": (base_high - base_low) <= MAX_BASE_WIDTH_ATR * atr,
            "closed_reclaim_above_prior_base_high": breakout_close > base_high,
            "reclaim_not_late_chase": (breakout_close - base_high) <= MAX_RECLAIM_EXTENSION_ATR * atr,
            "fresh_five_minute_continuation": last_5m >= base_high,
            "existing_v2r4_volume_confirmed": volume_ratio >= EXISTING_V2R4_VOLUME_RATIO_REVIEW_FLOOR,
            "liquid_eur_spread": spread <= SPREAD_LIMIT_PCT,
            "fresh_ask_not_far_past_reclaim": (ask - base_high) <= MAX_RECLAIM_EXTENSION_ATR * atr,
        }
        if not all(checks.values()):
            return _outcome("SECOND_LEG_CONDITIONS_NOT_CONFIRMED", **common,
                            checks=checks, base_15m_bars=base_bars,
                            fee_plus_spread_pct_before_slippage=round(1.2+spread,4))
        validation_stage = "STRUCTURAL_STOP_REFERENCE"
        stop_reference = min(base_low, float(f15["recent_8bar_low_eur"]))
        if stop_reference >= ask or stop_reference <= 0:
            return _outcome("NO_VALID_STRUCTURAL_RISK_REFERENCE", **common, checks=checks)
        result = _outcome(
            "SECOND_LEG_STRUCTURE_SUPPORTS_NEW_FULL_REVIEW_ONLY", **common,
            checks=checks, base_15m_bars=base_bars,
            original_candidate_historical_only=True,
            new_snapshot_observed_at_utc=new_coin_evidence["observed_at_utc"],
            new_snapshot_known_at_utc=new_coin_evidence["known_at_utc"],
            base_high_eur_descriptive_only=round(base_high,10),
            base_low_eur_descriptive_only=round(base_low,10),
            stop_reference_eur_descriptive_only=round(stop_reference,10),
            fee_plus_spread_pct_before_slippage=round(1.2+spread,4),
            full_evaluator_must_separately_validate={
                "actual_execution_ask_and_fresh_pair_metadata":True,
                "remaining_move_after_all_costs_and_slippage":True,
                "structural_stop_below_current_ask":True,
                "stage2_confirmation_above_ask_and_ttl":True,
                "market_and_derivatives_context_when_present":True,
                "anti_chase_and_risk_policy":True,
            },
        )
        result["request_model_recheck_only"] = True
        result["next_action"] = "ONLY_IF_SEPARATELY_APPROVED_FRESH_FULL_MODEL_REVIEW"
        return result
    except (ValueError, TypeError, KeyError, OverflowError, OSError):
        # Optional source absence is neutral. Missing *required execution/risk*
        # data yields UNKNOWN; never fabricate a BUY nor mark a valid REJECT.
        return _outcome("UNKNOWN_REQUIRED_PIT_OR_STRUCTURE_EVIDENCE", **common,
                        validation_stage=validation_stage)
