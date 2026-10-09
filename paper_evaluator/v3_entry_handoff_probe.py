#!/usr/bin/env python3
"""V3 inactive one-shot Kraken EUR candidate -> evidence -> evaluator-input probe.

Reads public Kraken OHLC/ticker only. No model call, trade, storage, schedules,
strategy mutation or secret access. A real V2R4 handoff may be passed explicitly.
No simulated BUY here is proof of a profitable or even acceptable entry.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from paper_evaluator.successor_coin_entry_evidence_v1 import fetch_public_entry_evidence
from paper_evaluator.evaluate import kraken_ticker, validate_candidate


def utc(value: str) -> datetime:
    d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("naive clock")
    return d.astimezone(timezone.utc)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def attach_to_future_evaluator(
    candidate: dict[str, Any],
    external: dict[str, Any],
    entry_evidence: dict[str, Any],
    decision_at_utc: str,
    *,
    max_evidence_age_seconds: int = 120,
) -> dict[str, Any]:
    """Return a *copy* with one canonical input. Never alter a live context.

    Fail closed on missing/stale/forward-known evidence. Do not reinterpret
    15m ratio(last/prior 5) as H6's distinct 1h-vs-1h volume ratio.
    """
    if entry_evidence.get("kind") != "SUCCESSOR_COIN_ENTRY_EVIDENCE_V1":
        raise ValueError("unsupported entry-evidence provenance")
    if candidate.get("pair") != entry_evidence.get("pair"):
        raise ValueError("candidate/entry-evidence pair mismatch")
    if external.get("candidate_entry_evidence") is not None:
        raise ValueError("duplicate coin entry evidence")
    known = utc(entry_evidence["known_at_utc"])
    observed = utc(entry_evidence["observed_at_utc"])
    decision = utc(decision_at_utc)
    if not observed <= known <= decision:
        raise ValueError("future-known or reversed entry timestamps")
    if (decision - known).total_seconds() > max_evidence_age_seconds:
        raise ValueError("entry evidence stale at evaluator decision")
    if entry_evidence.get("status") != "COMPLETE":
        raise ValueError("candidate entry evidence incomplete")
    frames = entry_evidence.get("frames")
    if not isinstance(frames, dict) or set(frames) != {"1", "5", "15"}:
        raise ValueError("all 1m/5m/15m closed frames required")
    for k in ("1", "5", "15"):
        f = frames[k]
        if f.get("status") != "VALID" or f.get("interval_min") != int(k):
            raise ValueError("entry frame invalid: " + k)
        t = utc(f["last_closed_bar_end_utc"])
        if t > observed or (observed - t).total_seconds() > int(k)*60*1.5:
            raise ValueError("stale/future candle in frame " + k)
        close = f.get("closed_close_eur")
        ratio = f.get("volume_ratio_prior_5")
        if not isinstance(close, (float, int)) or not math.isfinite(close) or close <= 0:
            raise ValueError("invalid closed price")
        if not isinstance(ratio, (float, int)) or not math.isfinite(ratio) or ratio < 0:
            raise ValueError("missing invalid volume ratio")
    atr = frames["15"].get("atr14_eur")
    lo = frames["15"].get("recent_8bar_low_eur")
    if not isinstance(atr, (float, int)) or not math.isfinite(atr) or atr <= 0:
        raise ValueError("ATR unavailable")
    if not isinstance(lo, (float, int)) or not math.isfinite(lo) or lo <= 0:
        raise ValueError("structure low unavailable")
    # All other proven derivatives/news/market-state fields remain untouched.
    out = dict(external)
    out["candidate_entry_evidence"] = entry_evidence
    return out


def one_shot_public_probe(pair: str, altname: str, candidate_path: Path | None = None) -> dict:
    if not pair.endswith("/EUR"):
        raise ValueError("only Kraken Spot EUR pairs")
    candidate: dict[str, Any]
    if candidate_path:
        candidate = json.loads(candidate_path.read_text("utf-8"))
        validate_candidate(candidate, str(candidate_path))
        if candidate.get("pair") != pair or candidate.get("altname") != altname:
            raise ValueError("candidate mismatch")
        source_kind = "USER_PROVIDED_EXISTING_CANONICAL_HANDOFF"
    else:
        # This proves real public source delivery only, NEVER trade validity.
        candidate = {"pair":pair, "altname":altname}
        source_kind = "PUBLIC_PAIR_SENSOR_ONLY_NOT_REAL_CANDIDATE"

    evidence = fetch_public_entry_evidence(altname,pair)
    # Keep latest public ticker distinct: spot execution ticker known after OHLC acquisition.
    ticker = kraken_ticker(altname)
    decision_at = now_utc()
    summary = {
        "kind":"V3_ENTRY_ONE_SHOT_PUBLIC_PROBE_V1",
        "pair":pair,
        "candidate_source":source_kind,
        "observed_at_utc":evidence["observed_at_utc"],
        "known_at_utc":evidence["known_at_utc"],
        "decision_at_utc":decision_at,
        "entry_evidence_status":evidence["status"],
        "frame_statuses":{i:{"status":v.get("status"),
                              "last_closed_bar_end_utc":v.get("last_closed_bar_end_utc"),
                              "volume_ratio_available":v.get("volume_ratio_prior_5") is not None}
                          for i,v in evidence["frames"].items()},
        "spread_pct":ticker["spread_pct"],
        "context_delivered_to_future_model":False,
        "full_strategy_evaluator_run":False,
        "valid_buy_scout_proven":False,
        "model_called":False,
        "orders":False,
        "real_money_actions":False,
        "stored_bars":False,
    }
    try:
        wired = attach_to_future_evaluator(candidate,{"kraken_execution_ticker":ticker},
                                            evidence,decision_at)
        assert wired.get("candidate_entry_evidence") is evidence
        summary["entry_input_handoff_ready"] = True
        summary["status"] = ("REAL_CANDIDATE_ENTRY_INPUT_READY_FOR_ISOLATED_MODEL_REPLAY"
                             if candidate_path else "PUBLIC_SOURCE_ENTRY_INPUT_READY_ONLY")
    except (ValueError, TypeError, KeyError) as exc:
        summary["entry_input_handoff_ready"] = False
        summary["status"] = "INSUFFICIENT_OR_UNAVAILABLE_ENTRY_INPUT"
        summary["failure_class"] = str(exc)[:90]
    return summary


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--pair",default="XBT/EUR")
    ap.add_argument("--altname",default="XBTEUR")
    ap.add_argument("--candidate-path",type=Path)
    ap.add_argument("--require-entry-input-ready",action="store_true")
    a=ap.parse_args()
    try:
        result=one_shot_public_probe(a.pair,a.altname,a.candidate_path)
    except (ValueError,KeyError,TypeError,OSError,TimeoutError) as exc:
        result={"kind":"V3_ENTRY_ONE_SHOT_PUBLIC_PROBE_V1",
                "status":"SOURCE_UNAVAILABLE_OR_INVALID",
                "failure_class":type(exc).__name__,
                "model_called":False,"orders":False,"real_money_actions":False}
    print(json.dumps(result,sort_keys=True))
    if a.require_entry_input_ready and not result.get("entry_input_handoff_ready",False):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
