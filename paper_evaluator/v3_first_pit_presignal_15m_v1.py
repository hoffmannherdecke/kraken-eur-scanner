"""V3-only original first-PIT 15m base evidence; no polling or trade authority.

The already fetched initial Kraken OHLC contains historically CLOSED base bars.
They were FIRST OBSERVED at the original candidate's P0, NOT when the bars
closed. This distinction is essential for a lawful later early-5m comparison.
The source is preserved in the existing immutable SOURCE_INPUT receipt.
"""
from __future__ import annotations
from datetime import datetime, timezone
import math
from typing import Any

KIND = "V3_ORIGINAL_FIRST_PIT_PRE_SIGNAL_15M_BASE_V1"


def _utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("missing original source clock")
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError("timezone-aware PIT clock required")
    return d.astimezone(timezone.utc)


def _pair_base(candidate: dict[str, Any], rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or len(rows) < 2 or len(rows) > 4:
        raise ValueError("bounded original Kraken 15m source bars required")
    signal = _utc(candidate["event_time_utc"])
    parsed = []
    previous = None
    for row in rows:
        if not isinstance(row, dict) or type(row.get("start_utc")) is not int:
            raise ValueError("malformed Kraken 15m candle identity")
        start = row["start_utc"]
        if start <= 0 or start % 900 or (previous is not None and start <= previous):
            raise ValueError("out-of-order or unaligned original 15m source")
        previous = start
        vals = [row.get(k) for k in ("open", "high", "low", "close")]
        if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0
               for v in vals):
            raise ValueError("invalid Kraken 15m OHLC")
        op, hi, lo, close = vals
        if not lo <= min(op, close) <= max(op, close) <= hi:
            raise ValueError("invalid original pre-signal 15m geometry")
        if datetime.fromtimestamp(start + 900, timezone.utc) <= signal:
            parsed.append({"start_utc": start, "open": float(op),
                           "high": float(hi), "low": float(lo),
                           "close": float(close)})
    if len(parsed) < 2 or parsed[-1]["start_utc"] - parsed[-2]["start_utc"] != 900:
        raise ValueError("two consecutive completed pre-signal 15m bars missing")
    return parsed[-2:]


def capture_first_pit_base(candidate: dict[str, Any],
                           coin: dict[str, Any],
                           *, written_at_utc: str) -> dict[str, Any] | None:
    """Optional safe enrichment of an ALREADY acquired first SOURCE_INPUT."""
    try:
        if (candidate.get("entry_origin", "SCANNER") != "SCANNER"
                or coin.get("pair") != candidate.get("pair")
                or coin.get("status") != "COMPLETE"
                or coin.get("frames", {}).get("15", {}).get("status") != "VALID"):
            return None
        signal = _utc(candidate["event_time_utc"])
        observed = _utc(coin["observed_at_utc"])
        known = _utc(coin["known_at_utc"])
        written = _utc(written_at_utc)
        if not (signal <= observed <= known <= written
                and (known - signal).total_seconds() <= 600):
            return None
        bars = _pair_base(candidate, coin.get("initial_pit_closed_15m_ohlc"))
        return {"kind": KIND, "pair": candidate["pair"],
                "candidate_id": candidate["candidate_id"],
                "original_signal_at_utc": candidate["event_time_utc"],
                "first_observed_at_utc": coin["observed_at_utc"],
                "first_known_at_utc": coin["known_at_utc"],
                "bar_closes_are_not_observation_times": True,
                "bars": bars}
    except (ValueError, TypeError, OverflowError, KeyError, AttributeError):
        return None


def read_first_pit_base(candidate: dict[str, Any],
                        receipt: dict[str, Any],
                        *, decision_at_utc: str) -> dict[str, Any] | None:
    """Revalidate immutable first-PIT lineage before any second market read."""
    try:
        data = receipt["data"]
        base = data["initial_pit_15m_base"]
        if (receipt.get("phase") != "SOURCE_INPUT" or receipt.get("result") != "PASS"
                or receipt.get("pair") != candidate.get("pair")
                or receipt.get("candidate_id") != candidate.get("candidate_id")
                or _utc(receipt["event_time_utc"]) != _utc(candidate["event_time_utc"])
                or base.get("kind") != KIND
                or base.get("pair") != candidate.get("pair")
                or base.get("candidate_id") != candidate.get("candidate_id")
                or _utc(base["original_signal_at_utc"]) != _utc(candidate["event_time_utc"])
                or base.get("bar_closes_are_not_observation_times") is not True
                or _utc(data["input_known_at_utc"]) != _utc(base["first_known_at_utc"])):
            return None
        signal = _utc(candidate["event_time_utc"])
        observed = _utc(base["first_observed_at_utc"])
        known = _utc(base["first_known_at_utc"])
        written = _utc(receipt["known_at_utc"])
        now = _utc(decision_at_utc)
        if not (signal <= observed <= known <= written <= now
                and 0 <= (known - signal).total_seconds() <= 600):
            return None
        bars = _pair_base(candidate, base["bars"])
        return {**base, "bars": bars}
    except (ValueError, KeyError, TypeError, OverflowError, AttributeError):
        return None
