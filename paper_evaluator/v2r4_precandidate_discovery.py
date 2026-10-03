#!/usr/bin/env python3
"""V2R4 pre-candidate discovery logic.

Purpose: separate *seeing a move* from *allowing execution*.

The active V2R3 scanner uses a hard EUR-turnover gate before expensive analysis.
That is useful for execution safety, but it can hide early moves in pairs whose
liquidity is still building.  V2R4 therefore keeps a broad discovery lane across
all Kraken EUR pairs and applies liquidity only after a move has been detected.

This module is paper/shadow only.  Nothing here can place an order.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

FRESH_PAPER_RECHECK_ONLY = "FRESH_PAPER_RECHECK_ONLY"
WATCH_ONLY = "WATCH_ONLY"
STANDARD_EXECUTION_GATE = "STANDARD_EXECUTION_GATE"
MICROSTRUCTURE_EXCEPTION_SHADOW = "MICROSTRUCTURE_EXCEPTION_SHADOW"

WINDOWS_SECONDS = {
    "ret10m": 10 * 60,
    "ret30m": 30 * 60,
    "ret1h": 60 * 60,
    "ret3h": 3 * 60 * 60,
    "ret6h": 6 * 60 * 60,
    "ret12h": 12 * 60 * 60,
}


@dataclass(frozen=True)
class DiscoveryAssessment:
    triggered: bool
    reasons: tuple[str, ...]
    liquidity_class: str
    next_action: str
    returns: dict[str, float | None]


def _num(value: Any, default: float | None = None) -> float | None:
    if value is None or isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def pct_change(new: float | None, old: float | None) -> float | None:
    if new is None or old is None or old <= 0:
        return None
    return 100.0 * (new / old - 1.0)


def return_from_history(
    history: Iterable[dict[str, Any]],
    *,
    now_ts: int,
    current_price: float,
    window_seconds: int,
) -> float | None:
    """Return point-in-time change using the latest sample at/before target.

    Missing history remains missing.  We do not interpolate future information.
    A bounded tolerance handles the normal 10-second/10-minute collection jitter.
    """
    target = int(now_ts) - int(window_seconds)
    eligible: list[tuple[int, float]] = []
    for row in history:
        ts = int(_num(row.get("ts"), 0) or 0)
        price = _num(row.get("price"))
        if ts <= target and price is not None and price > 0:
            eligible.append((ts, price))
    if not eligible:
        return None

    anchor_ts, anchor_price = max(eligible, key=lambda item: item[0])
    drift = target - anchor_ts
    max_drift = max(12 * 60, int(window_seconds * 0.25))
    if drift > max_drift:
        return None
    return pct_change(float(current_price), anchor_price)


def compute_returns(
    history: Iterable[dict[str, Any]],
    *,
    now_ts: int,
    current_price: float,
    day_open: float | None = None,
) -> dict[str, float | None]:
    rows = list(history)
    out = {
        name: return_from_history(
            rows,
            now_ts=now_ts,
            current_price=current_price,
            window_seconds=seconds,
        )
        for name, seconds in WINDOWS_SECONDS.items()
    }
    out["ret_day_open"] = pct_change(current_price, day_open)
    return out


def discovery_reasons(returns: dict[str, Any]) -> tuple[str, ...]:
    """Broad *recognition* triggers, deliberately not buy rules.

    Several paths exist so slow stair-step trends are not lost merely because the
    latest 15m/1h candle is cooling.  These thresholds are a V2R4 hypothesis and
    must be measured prospectively; they do not authorize execution.
    """
    def g(key: str) -> float | None:
        return _num(returns.get(key))

    reasons: list[str] = []
    tests = (
        ("FAST_10M", "ret10m", 1.25),
        ("FAST_30M", "ret30m", 2.0),
        ("MOMENTUM_1H", "ret1h", 3.0),
        ("PERSISTENT_3H", "ret3h", 4.0),
        ("PERSISTENT_6H", "ret6h", 5.0),
        ("PERSISTENT_12H", "ret12h", 7.0),
        ("DAY_MOVE_8PCT", "ret_day_open", 8.0),
    )
    for label, key, threshold in tests:
        value = g(key)
        if value is not None and value >= threshold:
            reasons.append(label)

    r1, r3, r6 = g("ret1h"), g("ret3h"), g("ret6h")
    if (
        r1 is not None and r3 is not None and r6 is not None
        and r1 >= 0.8 and r3 >= 2.0 and r6 >= 4.0
    ):
        reasons.append("STAIRCASE_6H")

    return tuple(reasons)


def classify_liquidity(
    *,
    turnover24h_eur: float,
    spread_pct: float,
    depth_1pct_eur: float | None = None,
    intended_notional_eur: float = 150.0,
) -> str:
    """Classify execution review without suppressing discovery.

    STANDARD keeps the existing coarse V2R3 safety gate.
    MICROSTRUCTURE_EXCEPTION_SHADOW is a new V2R4 paper-only hypothesis for pairs
    below EUR 150k/day that nevertheless have tight spread and enough 1%-book depth.
    """
    turnover = max(0.0, float(turnover24h_eur))
    spread = max(0.0, float(spread_pct))

    if turnover >= 150_000.0 and spread <= 1.5:
        return STANDARD_EXECUTION_GATE

    min_depth = max(3_000.0, 20.0 * float(intended_notional_eur))
    if (
        turnover >= 50_000.0
        and spread <= 0.60
        and depth_1pct_eur is not None
        and float(depth_1pct_eur) >= min_depth
    ):
        return MICROSTRUCTURE_EXCEPTION_SHADOW

    return WATCH_ONLY


def assess_discovery(
    *,
    returns: dict[str, Any],
    turnover24h_eur: float,
    spread_pct: float,
    depth_1pct_eur: float | None = None,
    intended_notional_eur: float = 150.0,
) -> DiscoveryAssessment:
    reasons = discovery_reasons(returns)
    liq = classify_liquidity(
        turnover24h_eur=turnover24h_eur,
        spread_pct=spread_pct,
        depth_1pct_eur=depth_1pct_eur,
        intended_notional_eur=intended_notional_eur,
    )
    triggered = bool(reasons)
    next_action = (
        FRESH_PAPER_RECHECK_ONLY
        if triggered and liq in {STANDARD_EXECUTION_GATE, MICROSTRUCTURE_EXCEPTION_SHADOW}
        else "NONE"
    )
    return DiscoveryAssessment(
        triggered=triggered,
        reasons=reasons,
        liquidity_class=liq,
        next_action=next_action,
        returns={k: _num(v) for k, v in returns.items()},
    )
