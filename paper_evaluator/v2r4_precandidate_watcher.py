#!/usr/bin/env python3
"""Local V2R4 broad EUR pre-candidate watcher.

Scans *all* Kraken EUR spot pairs with cheap public ticker data, keeps a rolling
price tape, and only fetches order-book depth for pairs that already triggered a
broad discovery rule.  This removes the "liquidity gate before visibility" blind
spot while preserving execution gates.

Paper/shadow only. No private credentials. No order endpoint. No real-money action.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .v2r4_precandidate_discovery import (
        FRESH_PAPER_RECHECK_ONLY,
        MICROSTRUCTURE_EXCEPTION_SHADOW,
        STANDARD_EXECUTION_GATE,
        WATCH_ONLY,
        assess_discovery,
        compute_returns,
    )
except ImportError:
    from v2r4_precandidate_discovery import (
        FRESH_PAPER_RECHECK_ONLY,
        MICROSTRUCTURE_EXCEPTION_SHADOW,
        STANDARD_EXECUTION_GATE,
        WATCH_ONLY,
        assess_discovery,
        compute_returns,
    )

UA = "kraken-v2r4-precandidate/0.1-paper-only"
STATE_SCHEMA = 1
EVENT_SCHEMA = 1


def utcnow_ts() -> int:
    return int(time.time())


def iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def http_json(path: str, params: dict[str, Any] | None = None, timeout: int = 20) -> dict:
    query = urllib.parse.urlencode(params or {})
    url = "https://api.kraken.com" + path + (("?" + query) if query else "")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("error"):
        raise RuntimeError(f"Kraken public error {path}: {payload['error']}")
    return payload.get("result", {})


def norm(value: str) -> str:
    return "".join(ch for ch in str(value).upper() if ch.isalnum())


def eur_pairs() -> list[dict[str, str]]:
    result = http_json("/0/public/AssetPairs")
    out: list[dict[str, str]] = []
    for pair_key, info in result.items():
        wsname = str(info.get("wsname") or "")
        altname = str(info.get("altname") or pair_key)
        quote = str(info.get("quote") or "")
        if not (wsname.endswith("/EUR") or quote in {"ZEUR", "EUR"}):
            continue
        pair = wsname if wsname.endswith("/EUR") else altname.removesuffix("EUR") + "/EUR"
        out.append({"pair": pair, "pair_key": str(pair_key), "altname": altname})
    return out


def chunks(rows: list[Any], size: int) -> list[list[Any]]:
    return [rows[i : i + size] for i in range(0, len(rows), size)]


def tickers(pairs: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    aliases: dict[str, str] = {}
    for meta in pairs:
        aliases[norm(meta["pair_key"])] = meta["pair"]
        aliases[norm(meta["altname"])] = meta["pair"]
        aliases[norm(meta["pair"])] = meta["pair"]

    out: dict[str, dict[str, Any]] = {}
    for batch in chunks(pairs, 70):
        result = http_json("/0/public/Ticker", {"pair": ",".join(x["altname"] for x in batch)})
        for key, row in result.items():
            pair = aliases.get(norm(key))
            if not pair:
                continue
            out[pair] = row
        time.sleep(0.20)
    return out


def parse_ticker(row: dict[str, Any]) -> dict[str, float]:
    bid = float(row["b"][0])
    ask = float(row["a"][0])
    last = float(row["c"][0])
    volume24 = float(row["v"][1])
    day_open = float(row["o"])
    mid = (bid + ask) / 2.0
    return {
        "bid_eur": bid,
        "ask_eur": ask,
        "last_eur": last,
        "spread_pct": 100.0 * (ask - bid) / mid if mid > 0 else 999.0,
        "turnover24h_eur": last * volume24,
        "day_open_eur": day_open,
    }


def depth_1pct_eur(altname: str, reference_price: float) -> float | None:
    result = http_json("/0/public/Depth", {"pair": altname, "count": 50})
    if not result:
        return None
    book = next(iter(result.values()))
    lower = reference_price * 0.99
    upper = reference_price * 1.01

    bid_depth = sum(
        float(price) * float(volume)
        for price, volume, *_ in book.get("bids", [])
        if float(price) >= lower
    )
    ask_depth = sum(
        float(price) * float(volume)
        for price, volume, *_ in book.get("asks", [])
        if float(price) <= upper
    )
    return min(bid_depth, ask_depth)


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": STATE_SCHEMA, "pairs": {}}
    try:
        state = json.loads(path.read_text("utf-8"))
    except Exception:
        return {"schema_version": STATE_SCHEMA, "pairs": {}}
    if int(state.get("schema_version", 0)) != STATE_SCHEMA:
        return {"schema_version": STATE_SCHEMA, "pairs": {}}
    state.setdefault("pairs", {})
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, separators=(",", ":"), sort_keys=True) + "\n", "utf-8")
    tmp.replace(path)


def write_event(directory: Path, event: dict[str, Any]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    safe_pair = event["pair"].replace("/", "-")
    path = directory / f"{event['observed_at_utc'].replace(':','').replace('-','')}-{safe_pair}.json"
    path.write_text(json.dumps(event, indent=2, sort_keys=True) + "\n", "utf-8")
    return path


def discovery_strength(returns: dict[str, float | None]) -> float:
    values = [v for v in returns.values() if isinstance(v, (int, float))]
    return max(values) if values else 0.0


def run_once(
    *,
    state_path: Path,
    event_dir: Path,
    intended_notional_eur: float,
    max_depth_checks: int,
    cooldown_seconds: int,
) -> dict[str, int]:
    now = utcnow_ts()
    pairs = eur_pairs()
    meta_by_pair = {x["pair"]: x for x in pairs}
    ticker_rows = tickers(pairs)
    state = load_state(state_path)
    pair_state = state["pairs"]

    prelim: list[dict[str, Any]] = []
    keep_after = now - 26 * 60 * 60

    for pair, raw in ticker_rows.items():
        try:
            market = parse_ticker(raw)
        except Exception:
            continue
        entry = pair_state.setdefault(pair, {"snapshots": [], "last_event_ts": 0, "last_liquidity_class": WATCH_ONLY})
        history = [
            x for x in entry.get("snapshots", [])
            if int(x.get("ts", 0)) >= keep_after
        ]
        returns = compute_returns(
            history,
            now_ts=now,
            current_price=market["last_eur"],
            day_open=market["day_open_eur"],
        )
        assessment = assess_discovery(
            returns=returns,
            turnover24h_eur=market["turnover24h_eur"],
            spread_pct=market["spread_pct"],
            depth_1pct_eur=None,
            intended_notional_eur=intended_notional_eur,
        )
        entry["snapshots"] = history + [{"ts": now, "price": market["last_eur"]}]
        if assessment.triggered:
            prelim.append({
                "pair": pair,
                "market": market,
                "returns": returns,
                "assessment": assessment,
                "strength": discovery_strength(returns),
            })

    # Only possible sub-EUR150k execution exceptions need an order-book request.
    need_depth = [
        row for row in prelim
        if row["assessment"].liquidity_class == WATCH_ONLY
        and 50_000 <= row["market"]["turnover24h_eur"] < 150_000
        and row["market"]["spread_pct"] <= 0.60
    ]
    need_depth.sort(key=lambda x: x["strength"], reverse=True)
    depth_checked = 0
    for row in need_depth[:max_depth_checks]:
        meta = meta_by_pair.get(row["pair"])
        if not meta:
            continue
        try:
            depth = depth_1pct_eur(meta["altname"], row["market"]["last_eur"])
        except Exception:
            depth = None
        depth_checked += 1
        row["depth_1pct_eur"] = depth
        row["assessment"] = assess_discovery(
            returns=row["returns"],
            turnover24h_eur=row["market"]["turnover24h_eur"],
            spread_pct=row["market"]["spread_pct"],
            depth_1pct_eur=depth,
            intended_notional_eur=intended_notional_eur,
        )

    emitted = 0
    review_eligible = 0
    watch_only = 0
    for row in sorted(prelim, key=lambda x: x["strength"], reverse=True):
        pair = row["pair"]
        assessment = row["assessment"]
        entry = pair_state[pair]
        last_event = int(entry.get("last_event_ts", 0) or 0)
        previous_liq = str(entry.get("last_liquidity_class") or WATCH_ONLY)
        became_reviewable = (
            previous_liq == WATCH_ONLY
            and assessment.liquidity_class in {STANDARD_EXECUTION_GATE, MICROSTRUCTURE_EXCEPTION_SHADOW}
        )
        if now - last_event < cooldown_seconds and not became_reviewable:
            entry["last_liquidity_class"] = assessment.liquidity_class
            continue

        event = {
            "schema_version": EVENT_SCHEMA,
            "kind": "V2R4_PRE_CANDIDATE_DISCOVERY",
            "paper_only": True,
            "real_money_actions_enabled": False,
            "observed_at_utc": iso(now),
            "observed_ts": now,
            "pair": pair,
            "altname": meta_by_pair.get(pair, {}).get("altname"),
            "reasons": list(assessment.reasons),
            "returns": assessment.returns,
            "last_eur": row["market"]["last_eur"],
            "spread_pct": row["market"]["spread_pct"],
            "turnover24h_eur": row["market"]["turnover24h_eur"],
            "depth_1pct_eur": row.get("depth_1pct_eur"),
            "liquidity_class": assessment.liquidity_class,
            "next_action": assessment.next_action,
            "note": "Discovery is independent of execution eligibility; any recheck must re-fetch current Kraken execution data.",
        }
        path = write_event(event_dir, event)
        print("V2R4_PRE_CANDIDATE " + json.dumps(event, separators=(",", ":"), sort_keys=True), flush=True)
        print(f"EVENT {path}", flush=True)
        emitted += 1
        if assessment.next_action == FRESH_PAPER_RECHECK_ONLY:
            review_eligible += 1
        else:
            watch_only += 1
        entry["last_event_ts"] = now
        entry["last_liquidity_class"] = assessment.liquidity_class

    state["updated_at_utc"] = iso(now)
    save_state(state_path, state)
    summary = {
        "eur_pairs": len(pairs),
        "ticker_rows": len(ticker_rows),
        "triggered": len(prelim),
        "events_emitted": emitted,
        "review_eligible": review_eligible,
        "watch_only": watch_only,
        "depth_checked": depth_checked,
    }
    print("V2R4_PRE_CANDIDATE_SUMMARY " + json.dumps(summary, sort_keys=True), flush=True)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, default=Path(".v2r4-precandidate/state.json"))
    parser.add_argument("--event-dir", type=Path, default=Path(".v2r4-precandidate/events"))
    parser.add_argument("--poll-seconds", type=float, default=10.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--intended-notional-eur", type=float, default=150.0)
    parser.add_argument("--max-depth-checks", type=int, default=12)
    parser.add_argument("--cooldown-seconds", type=int, default=1800)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.poll_seconds < 5:
        raise SystemExit("--poll-seconds must be >= 5")
    if args.intended_notional_eur <= 0:
        raise SystemExit("--intended-notional-eur must be > 0")
    while True:
        run_once(
            state_path=args.state,
            event_dir=args.event_dir,
            intended_notional_eur=args.intended_notional_eur,
            max_depth_checks=max(0, args.max_depth_checks),
            cooldown_seconds=max(0, args.cooldown_seconds),
        )
        if args.once:
            return 0
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
