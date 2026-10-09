#!/usr/bin/env python3
"""Inactive, public Kraken Spot-EUR entry-evidence adapter for a future PAPER candidate.

NOT imported by active V2R4. No orders or model calls. It does not decide BUY/WAIT/REJECT.
A live observation may be used only *after* known_at_utc; never backdate a fetch.
"""
from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable

INTERVALS = (1, 5, 15)
MAX_ROWS = 32
USER_AGENT = "kraken-paper-successor-context/1.0 (public-readonly)"


def _utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return dt.astimezone(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _number(value: Any) -> float:
    n = float(value)
    if not math.isfinite(n):
        raise ValueError("nonfinite OHLC value")
    return n


def _normalize(rows: list[Any], interval: int, as_of: datetime) -> list[dict[str, float | int]]:
    """Strictly discard the still-open Kraken bar and any look-ahead data."""
    if not isinstance(rows, list):
        raise ValueError("OHLC rows must be a list")
    result = []
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) < 7:
            raise ValueError("invalid Kraken OHLC row")
        ts = int(row[0]); span = interval * 60
        if ts <= 0 or ts % span:
            raise ValueError("unaligned Kraken candle timestamp")
        if ts + span > as_of.timestamp():
            continue  # newest mutable candle, even if it looks promising
        o, h, l, c, v = (_number(row[k]) for k in (1, 2, 3, 4, 6))
        if min(o, h, l, c) <= 0 or v < 0 or h < max(o, c) or l > min(o, c) or l > h:
            raise ValueError("invalid Kraken candle prices or volume")
        result.append({"start_utc": ts, "open": o, "high": h, "low": l, "close": c, "volume": v})
    result.sort(key=lambda a: a["start_utc"])
    if any(result[i]["start_utc"] == result[i - 1]["start_utc"] for i in range(1, len(result))):
        raise ValueError("duplicate Kraken candle")
    return result[-MAX_ROWS:]


def _contiguous(rows: list[dict], interval: int, count: int) -> bool:
    if len(rows) < count:
        return False
    seq = rows[-count:]
    return all(seq[i]["start_utc"] - seq[i - 1]["start_utc"] == interval * 60
               for i in range(1, len(seq)))


def _frame(rows: list[Any], interval: int, as_of: datetime) -> dict[str, Any]:
    candles = _normalize(rows, interval, as_of)
    if not candles:
        return {"status": "MISSING", "reason": "NO_CLOSED_BARS", "interval_min": interval}
    last = candles[-1]
    age = as_of.timestamp() - (last["start_utc"] + interval * 60)
    if age > interval * 60 * 1.5:
        return {"status": "STALE", "reason": "LAST_CLOSED_BAR_TOO_OLD", "interval_min": interval,
                "last_closed_bar_end_utc": _iso(datetime.fromtimestamp(last["start_utc"] + interval * 60, timezone.utc))}
    if not _contiguous(candles, interval, 6):
        return {"status": "INCOMPLETE", "reason": "INSUFFICIENT_CONTIGUOUS_BARS", "interval_min": interval,
                "last_closed_bar_end_utc": _iso(datetime.fromtimestamp(last["start_utc"] + interval * 60, timezone.utc))}
    prev_vols = [r["volume"] for r in candles[-6:-1]]
    avg_prior = sum(prev_vols) / len(prev_vols)
    out: dict[str, Any] = {
        "status": "VALID", "interval_min": interval,
        "last_closed_bar_end_utc": _iso(datetime.fromtimestamp(last["start_utc"] + interval * 60, timezone.utc)),
        "closed_close_eur": round(last["close"], 10),
        "closed_high_eur": round(last["high"], 10),
        "closed_low_eur": round(last["low"], 10),
        "closed_volume_base": round(last["volume"], 10),
        "volume_ratio_prior_5": round(last["volume"] / avg_prior, 5) if avg_prior > 0 else None,
        "volume_ratio_status": "VALID" if avg_prior > 0 else "MISSING_ZERO_BASELINE",
    }
    if interval == 15:
        if _contiguous(candles, 15, 15):
            tail = candles[-15:]
            tr = [max(r["high"] - r["low"], abs(r["high"] - tail[i - 1]["close"]),
                      abs(r["low"] - tail[i - 1]["close"]))
                  for i, r in enumerate(tail) if i > 0]
            out["atr14_eur"] = round(sum(tr) / len(tr), 10)
            out["atr_status"] = "VALID"
        else:
            out["atr14_eur"] = None
            out["atr_status"] = "MISSING_CONTIGUOUS_15_BARS"
        if _contiguous(candles, 15, 8):
            out["recent_8bar_low_eur"] = round(min(r["low"] for r in candles[-8:]), 10)
        else:
            out["recent_8bar_low_eur"] = None
    return out


def build_entry_evidence(
    pair: str, rows_by_interval: dict[int, list[Any] | None], *,
    observed_at_utc: str, known_at_utc: str,
) -> dict[str, Any]:
    """Pure, independently testable adapter. Missing source is NOT a bearish signal.

    observed_at_utc is the timestamp fixed before acquisition.
    known_at_utc is the completion timestamp (never earlier than observed_at_utc).
    The result must never be treated as known before known_at_utc.
    """
    observed, known = _utc(observed_at_utc), _utc(known_at_utc)
    if known < observed:
        raise ValueError("known_at earlier than observation")
    if not isinstance(pair, str) or not pair.endswith("/EUR") or len(pair) > 24:
        raise ValueError("Kraken EUR pair required")
    frames = {}
    for interval in INTERVALS:
        rows = rows_by_interval.get(interval)
        if rows is None:
            frames[str(interval)] = {"status": "MISSING", "reason": "SOURCE_UNAVAILABLE", "interval_min": interval}
            continue
        try:
            frames[str(interval)] = _frame(rows, interval, observed)
        except (ValueError, TypeError, OverflowError, KeyError) as exc:
            frames[str(interval)] = {"status": "INVALID", "reason": type(exc).__name__, "interval_min": interval}
    statuses = [f["status"] for f in frames.values()]
    return {
        "kind": "SUCCESSOR_COIN_ENTRY_EVIDENCE_V1", "schema_version": 1,
        "authority": "RESEARCH_ONLY_NOT_A_TRADE_OR_STOP_PLAN",
        "source": "kraken_public_spot_eur_ohlc_closed_bars", "pair": pair,
        "observed_at_utc": _iso(observed), "known_at_utc": _iso(known),
        "available_for_decision_no_earlier_than_utc": _iso(known),
        "status": "COMPLETE" if all(s == "VALID" for s in statuses) and frames["15"].get("atr_status") == "VALID" else "PARTIAL_OR_MISSING",
        "frames": frames,
        "guardrails": {"no_orders": True, "no_buy_authority": True,
                       "missing_is_not_negative": True, "incomplete_bar_discarded": True,
                       "historical_backfill_claimed": False},
    }


def fetch_public_entry_evidence(altname: str, pair: str, *,
                                clock: Callable[[], datetime] | None = None,
                                loader: Callable[[str, int], dict] | None = None) -> dict[str, Any]:
    """Manual research invocation only. Three bounded public reads, no persistence."""
    clock = clock or (lambda: datetime.now(timezone.utc))
    if not altname or len(altname) > 40 or not altname.isalnum():
        raise ValueError("verified Kraken AssetPairs altname required")
    start = clock()
    if start.tzinfo is None:
        raise ValueError("clock must be timezone-aware")
    def live_loader(symbol: str, interval: int) -> dict:
        qs = urllib.parse.urlencode({"pair": symbol, "interval": interval})
        request = urllib.request.Request("https://api.kraken.com/0/public/OHLC?" + qs,
                                         headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=9) as response:
            return json.loads(response.read(1_000_000).decode("utf-8"))
    loader = loader or live_loader
    snapshots: dict[int, list[Any] | None] = {}
    for interval in INTERVALS:
        try:
            reply = loader(altname, interval)
            if not isinstance(reply, dict) or reply.get("error") or not isinstance(reply.get("result"), dict):
                raise ValueError("Kraken OHLC source error")
            matching = [(k, v) for k, v in reply["result"].items() if k != "last"]
            if len(matching) != 1 or not isinstance(matching[0][1], list):
                raise ValueError("ambiguous Kraken OHLC response")
            snapshots[interval] = matching[0][1]
        except (ValueError, KeyError, TypeError, OSError, TimeoutError):
            snapshots[interval] = None
    end = clock()
    return build_entry_evidence(pair, snapshots, observed_at_utc=_iso(start), known_at_utc=_iso(end))
