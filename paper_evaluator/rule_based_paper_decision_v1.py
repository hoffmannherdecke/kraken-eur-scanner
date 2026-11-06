"""Pure, zero-cost candidate decision shared by V2R4 and future V3 paper.

The rules are hypotheses for PAPER experimentation, not a claim of edge.
Only proven closed Kraken 1/5/15m candles and source-bound quotes can yield
BUY_SCOUT. No LLM, trading, disk, timers, secrets or network calls here.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

FEE_PCT_PER_SIDE = 0.60
SLIPPAGE_PCT_PER_SIDE = 0.08
MAX_SPREAD_PCT = 0.35
MAX_CANDIDATE_AGE_SECONDS = 900
MAX_EVIDENCE_AGE_SECONDS = 120


def _utc(value):
    d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("naive time")
    return d.astimezone(timezone.utc)


def _number(value):
    if type(value) not in (float, int):
        raise ValueError("non-numeric evidence")
    n = float(value)
    if not math.isfinite(n):
        raise ValueError("nonfinite evidence")
    return n


def _decision(kind, lane, reason, summary, *, missing=None, watch=None,
              ttl=0, stop=None, target=None, net=None, reward_risk=None):
    return {
        "decision": kind, "setup_lane": lane,
        "summary": summary, "reason_codes": [reason],
        "missing_triggers": list(missing or []),
        "stop_eur": stop, "ttl_minutes": ttl,
        "expected_remaining_move_pct": target,
        "risk_reward_after_costs": reward_risk if kind == "BUY_SCOUT" else None,
        "stage2_trigger_eur": (
            round(target["stage2_eur"], 10) if kind == "BUY_SCOUT" and isinstance(target, dict)
            else None
        ),
        "stage2_ttl_minutes": 30 if kind == "BUY_SCOUT" else 0,
        "watch_conditions": list(watch or []),
    }


def _reject(code, summary):
    return _decision("REJECT", "NONE", code, summary)


def fetch_rule_evidence(altname, pair, *, loader):
    """Reuse the tested read-only closed-candle adapter as public evidence.

    Importing this data-only helper never invokes V3 writer/model/release code.
    It is not a decision and carries no automatic permission to trade.
    """
    from paper_evaluator.successor_coin_entry_evidence_v1 import fetch_public_entry_evidence
    return fetch_public_entry_evidence(altname, pair, loader=loader)


def assess(candidate, ticker, context, spec, control, *, decision_at_utc=None):
    """Return executable V2R4-compatible decision using closed public data.

    No automatic positive signal from scanner strength, an absent optional
    source, or the hypothetical ATR-based reward estimate.
    """
    now = _utc(decision_at_utc) if decision_at_utc else datetime.now(timezone.utc)
    try:
        if (candidate.get("action") != "REVIEW_ONLY_NOT_ORDER"
                or not str(candidate["pair"]).endswith("/EUR")
                or not candidate.get("candidate_id")
                or not candidate.get("altname")
                or spec.get("real_money_actions_enabled") is not False
                or control.get("real_money_actions_enabled") is not False):
            return _reject("RULE_SOURCE_AUTHORITY_MISSING", "Paper source authority not confirmed.")
        event_at = _utc(candidate["event_time_utc"])
        age = (now - event_at).total_seconds()
        triggered = candidate.get("v2r4_fresh_recheck_context") or {}
        if not isinstance(triggered, dict):
            return _reject("RULE_RECHECK_RECEIPT_INVALID", "WAIT continuation has invalid context.")
        receipt = triggered.get("trigger_receipt") or {}
        if not isinstance(receipt, dict):
            return _reject("RULE_RECHECK_RECEIPT_INVALID", "WAIT continuation has invalid receipt.")
        fresh_recheck = False
        if triggered.get("kind") == "V2R4_TRIGGERED_FRESH_PAPER_RECHECK":
            try:
                receipt_at = _utc(receipt["observed_at_utc"])
                fresh_recheck = (
                    receipt.get("kind") == "V2R4_PAPER_WAIT_TRIGGER_RECEIPT"
                    and receipt.get("candidate_id") == candidate["candidate_id"]
                    and receipt.get("pair") == candidate["pair"]
                    and receipt.get("paper_only") is True
                    and receipt.get("matched") is True
                    and receipt.get("expired") is False
                    and receipt.get("real_money_actions_enabled") is False
                    and receipt.get("next_action") == "FRESH_PAPER_RECHECK_ONLY"
                    and event_at <= receipt_at <= now
                    and (now-receipt_at).total_seconds() <= 120
                )
            except (KeyError, TypeError, ValueError):
                fresh_recheck = False
            if not fresh_recheck:
                return _reject("RULE_RECHECK_RECEIPT_INVALID", "WAIT continuation requires a fresh matching receipt.")
        max_age = 3600 if fresh_recheck else MAX_CANDIDATE_AGE_SECONDS
        if not 0 <= age <= max_age:
            return _reject("RULE_CANDIDATE_STALE", "Candidate or WAIT continuation is too old.")
        ask, bid, spread = (
            _number(ticker["ask"]), _number(ticker["bid"]),
            _number(ticker["spread_pct"]))
        if not 0 < bid <= ask or not 0 <= spread <= MAX_SPREAD_PCT:
            return _reject("RULE_EXECUTION_SPREAD_OR_QUOTE", "Invalid or expensive Kraken EUR quote.")
        meta = context.get("kraken_pair_metadata") or {}
        if meta.get("available") is not True or meta.get("status") != "online":
            return _reject("RULE_KRAKEN_PAIR_NOT_VERIFIED", "No verified online Kraken Spot EUR market.")
        evidence = context.get("candidate_entry_evidence") or {}
        if (evidence.get("kind") != "SUCCESSOR_COIN_ENTRY_EVIDENCE_V1"
                or evidence.get("pair") != candidate["pair"]
                or evidence.get("status") != "COMPLETE"):
            return _reject("RULE_CLOSED_OHLC_MISSING", "Closed 1m/5m/15m candles are required.")
        observed, known = _utc(evidence["observed_at_utc"]), _utc(evidence["known_at_utc"])
        if not observed <= known <= now or (now-known).total_seconds() > MAX_EVIDENCE_AGE_SECONDS:
            return _reject("RULE_SOURCE_CLOCK_INVALID", "Closed candle evidence is stale or future-known.")
        frames = evidence["frames"]
        if not isinstance(frames, dict) or set(frames) != {"1", "5", "15"}:
            return _reject("RULE_FRAMES_INCOMPLETE", "Required closed market intervals absent.")
        for period in ("1", "5", "15"):
            frame = frames[period]
            end = _utc(frame["last_closed_bar_end_utc"])
            if (frame.get("status") != "VALID" or
                    frame.get("interval_min") != int(period) or
                    not 0 <= (observed-end).total_seconds() <= int(period)*90):
                return _reject("RULE_FRAME_NOT_FRESH_CLOSED", "Invalid or unclosed market candle.")
        f1, f5, f15 = frames["1"], frames["5"], frames["15"]
        c1, c5, c15 = (_number(f["closed_close_eur"]) for f in (f1, f5, f15))
        high5 = _number(f5["closed_high_eur"])
        atr = _number(f15["atr14_eur"])
        low = _number(f15["recent_8bar_low_eur"])
        volume = _number(f5["volume_ratio_prior_5"])
        if min(c1, c5, c15, high5, atr, low) <= 0 or volume < 0 or low >= ask:
            return _reject("RULE_INVALID_STRUCTURE", "Structural stop, ATR or volume not available.")
        if (abs(ask/c1-1)*100 > 3 or ask/c15 > 1.06):
            return _reject("RULE_LATE_CHASE", "Current ask has run too far beyond confirmed closed structure.")
        risk_pct = (ask-low)/ask*100
        if not 0.5 <= risk_pct <= 5.0:
            return _reject("RULE_STOP_NOT_EXECUTABLE", "Structural stop outside permitted risk band.")
        # A research target assumption, explicitly not a claimed market forecast.
        # Net projected upside must cover two taker fees, spread and slippage.
        hypothetical_gross_pct = 4*atr/ask*100
        costs_pct = 2*FEE_PCT_PER_SIDE + spread + 2*SLIPPAGE_PCT_PER_SIDE
        net_pct = hypothetical_gross_pct-costs_pct
        net_rr = net_pct/risk_pct
        strong_price = (c1 >= c5 >= c15 and ask >= c1*0.995)
        adequate_volume = volume >= 1.2
        if strong_price and adequate_volume and net_pct >= 2.0 and net_rr >= 1.5:
            trigger = max(ask*1.003, high5*1.001)
            if trigger <= ask or (trigger-ask)/ask*100 > 2:
                return _reject("RULE_STAGE2_CONFIRMATION_TOO_FAR", "No valid near-term Stage 2 level.")
            return {
                "decision": "BUY_SCOUT", "setup_lane": "CONTINUITY",
                "summary": "Paper-only closed-candle continuation with structural stop, volume and cost coverage; ATR reward is a research assumption.",
                "reason_codes": ["RULE_CLOSED_PRICE_VOLUME_AND_RISK_PASS"],
                "missing_triggers": [], "stop_eur": round(low, 10),
                "ttl_minutes": 0,
                "expected_remaining_move_pct": round(hypothetical_gross_pct, 4),
                "risk_reward_after_costs": round(net_rr, 4),
                "stage2_trigger_eur": round(trigger, 10),
                "stage2_ttl_minutes": 30,
                "watch_conditions": [],
            }
        # WAIT remains machine-executable; never infer a signal from prose.
        if c5 >= c15 and volume >= 0.7 and net_pct >= 1.5 and net_rr >= 1.25:
            threshold = round(max(c5, high5)*1.002, 10)
            return _decision(
                "WAIT", "CONTINUITY", "RULE_CONFIRMATION_PENDING",
                "Wait for next closed 5m breakout and volume confirmation.",
                missing=["Closed 5m close above recent high", "Closed 5m volume ratio at least 1.2"],
                watch=[{"metric": "closed_5m_close_eur", "op": ">=", "value": threshold},
                       {"metric": "closed_5m_volume_ratio_5", "op": ">=", "value": 1.2}],
                ttl=30)
        return _reject("RULE_RISK_OR_CONTINUITY_NOT_PROVEN",
                       "No cost-adjusted closed-candle entry or executable WAIT confirmation.")
    except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
        return _reject("RULE_SOURCE_INVALID", "Incomplete or invalid source data; no paper entry.")
