#!/usr/bin/env python3
"""Shared fail-closed routing helpers for V3-H3 shadow evaluation."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SUPPORTED_PAIRS = ("XBT/EUR", "ETH/EUR", "SOL/EUR")
WS_ALIAS = {
    "XBT/EUR": "BTC/EUR",
    "ETH/EUR": "ETH/EUR",
    "SOL/EUR": "SOL/EUR",
}
MAX_STATE_AGE_MS = 2000.0
MAX_SOURCE_CLOCK_LEAD_MS = 250.0


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def route_shadow(pair: str, context_status: str, already_processed: bool) -> str:
    if already_processed:
        return "DUPLICATE_SKIPPED"
    if pair not in SUPPORTED_PAIRS:
        return "BASELINE_PASSTHROUGH_NONELIGIBLE_PAIR"
    if context_status != "PASS":
        return "BASELINE_PASSTHROUGH_H3_CONTEXT_MISSING"
    return "EVALUATE_H3_SHADOW"


def context_is_fresh(
    *,
    source_exchange_at_utc: str,
    received_at_utc: str,
    evaluation_clock_utc: str,
    maximum_state_age_ms: float = MAX_STATE_AGE_MS,
    maximum_source_clock_lead_ms: float = MAX_SOURCE_CLOCK_LEAD_MS,
) -> bool:
    source = parse_utc(source_exchange_at_utc)
    received = parse_utc(received_at_utc)
    evaluation = parse_utc(evaluation_clock_utc)
    if received > evaluation:
        return False

    # Kraken exchange timestamps and the local Windows clock are independently
    # synchronized. A very small negative transport age can therefore be benign
    # clock skew rather than "future market data". Bound that skew separately
    # instead of weakening the 2s point-in-time freshness requirement.
    source_lead_ms = (source - received).total_seconds() * 1000.0
    if source_lead_ms > float(maximum_source_clock_lead_ms):
        return False

    source_age_ms = (evaluation - source).total_seconds() * 1000.0
    local_handoff_age_ms = (evaluation - received).total_seconds() * 1000.0
    effective_source_age_ms = max(0.0, source_age_ms)
    return (
        0.0 <= local_handoff_age_ms <= float(maximum_state_age_ms)
        and effective_source_age_ms <= float(maximum_state_age_ms)
    )


def compact_h3_context(
    *,
    pair: str,
    source_exchange_at_utc: str,
    received_at_utc: str,
    spread_bps: float,
    bid_depth_quote_top10: float,
    ask_depth_quote_top10: float,
    depth_imbalance_top10: float,
) -> dict[str, Any]:
    if pair not in SUPPORTED_PAIRS:
        raise ValueError("unsupported H3 pair")
    return {
        "schema_version": 1,
        "kind": "V3_H3_ORDERBOOK_CONTEXT_V1",
        "status": "PASS",
        "pair": pair,
        "kraken_ws_symbol": WS_ALIAS[pair],
        "source_exchange_at_utc": source_exchange_at_utc,
        "received_at_utc": received_at_utc,
        "depth": 10,
        "checksum_valid": True,
        "features": {
            "spread_bps": float(spread_bps),
            "bid_depth_quote_top10": float(bid_depth_quote_top10),
            "ask_depth_quote_top10": float(ask_depth_quote_top10),
            "depth_imbalance_top10": float(depth_imbalance_top10),
        },
        "interpretation": (
            "Raw point-in-time H3 context only. No directional-sign assumption, "
            "threshold, transform, score weight, pair ranking or automatic trade rule."
        ),
    }
