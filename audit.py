#!/usr/bin/env python3
"""Private-workflow-friendly missed-move audit for the Kraken EUR scanner.

Reads only rolling public-market telemetry created by scan.yml and public Kraken
OHLC. It never uses exchange credentials and never places orders.
"""
from __future__ import annotations

import json
import os
import re
import statistics
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API = "https://api.kraken.com/0/public"
STATE_PATH = Path(os.getenv("AUDIT_HISTORY_PATH", ".scanner/kraken_eur_scanner/.state/audit_history.jsonl"))
OUT_JSON = Path(os.getenv("AUDIT_OUT_JSON", "missed_move_audit.json"))
OUT_MD = Path(os.getenv("AUDIT_OUT_MD", "missed_move_audit.md"))

LOOKBACK_HOURS = float(os.getenv("AUDIT_LOOKBACK_HOURS", "36"))
HORIZON_HOURS = float(os.getenv("AUDIT_HORIZON_HOURS", "6"))
MIN_AGE_HOURS = float(os.getenv("AUDIT_MIN_AGE_HOURS", str(HORIZON_HOURS)))
MOVE_THRESHOLD_PCT = float(os.getenv("AUDIT_MOVE_THRESHOLD_PCT", "8"))
EARLY_FRESH_MOVE_MAX_PCT = float(os.getenv("AUDIT_EARLY_FRESH_MOVE_MAX_PCT", "10"))
CANDIDATE_THRESHOLD = float(os.getenv("AUDIT_CANDIDATE_THRESHOLD", "5.0"))
REQUEST_SPACING = float(os.getenv("AUDIT_REQUEST_SPACING", "1.05"))
USER_AGENT = "kraken-eur-missed-move-audit/1.0"


class RateLimiter:
    def __init__(self, spacing: float):
        self.spacing = spacing
        self.last = 0.0

    def wait(self) -> None:
        delay = self.spacing - (time.monotonic() - self.last)
        if delay > 0:
            time.sleep(delay)
        self.last = time.monotonic()


limiter = RateLimiter(REQUEST_SPACING)


def kraken_get(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    limiter.wait()
    url = API + "/" + endpoint + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    errors = payload.get("error") or []
    if errors:
        raise RuntimeError("; ".join(map(str, errors)))
    return payload.get("result", {})


def fetch_ohlc(altname: str) -> list[dict[str, float]]:
    result = kraken_get("OHLC", {"pair": altname, "interval": 15})
    keys = [k for k in result if k != "last"]
    if not keys:
        raise RuntimeError("no OHLC pair data")
    rows = []
    for c in result[keys[0]]:
        rows.append({
            "ts": int(c[0]),
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
        })
    return rows


def load_events() -> list[dict[str, Any]]:
    if not STATE_PATH.exists():
        return []
    out = []
    for line in STATE_PATH.read_text("utf-8").splitlines():
        try:
            event = json.loads(line)
            if isinstance(event, dict) and event.get("type") in {"row", "posted", "cooldown"}:
                out.append(event)
        except Exception:
            continue
    return out


def parse_post_price(text: str) -> float | None:
    m = re.search(r"(?:^|\|\s*)price_eur=([^|\s]+)", text or "")
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def future_range(candles: list[dict[str, float]], start: int, end: int, entry: float) -> dict[str, Any] | None:
    window = [c for c in candles if start <= c["ts"] <= end]
    if not window or entry <= 0:
        return None
    peak = max(window, key=lambda c: c["high"])
    trough = min(window, key=lambda c: c["low"])
    return {
        "peak_pct": round((peak["high"] / entry - 1) * 100, 2),
        "peak_ts": peak["ts"],
        "drawdown_pct": round((trough["low"] / entry - 1) * 100, 2),
        "trough_ts": trough["ts"],
    }


def iso(ts: int | float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()


def main() -> None:
    now = int(time.time())
    events = load_events()
    rows = [e for e in events if e.get("type") == "row"]
    posts = [e for e in events if e.get("type") == "posted"]
    cooldowns = [e for e in events if e.get("type") == "cooldown"]

    mature_start = now - int(LOOKBACK_HOURS * 3600)
    mature_end = now - int(MIN_AGE_HOURS * 3600)
    mature_rows = [e for e in rows if mature_start <= int(e.get("ts", 0)) <= mature_end]
    mature_posts = [e for e in posts if mature_start <= int(e.get("ts", 0)) <= mature_end]

    pair_altnames: dict[str, str] = {}
    for e in rows:
        f = e.get("features") or {}
        pair = str(e.get("pair") or f.get("pair") or "")
        alt = str(f.get("altname") or "")
        if pair and alt:
            pair_altnames[pair] = alt

    ohlc: dict[str, list[dict[str, float]]] = {}
    errors: dict[str, str] = {}
    for pair in sorted({str(e.get("pair") or "") for e in mature_rows + mature_posts if e.get("pair")}):
        alt = pair_altnames.get(pair)
        if not alt:
            errors[pair] = "missing altname in telemetry"
            continue
        try:
            ohlc[pair] = fetch_ohlc(alt)
        except Exception as exc:
            errors[pair] = str(exc)

    rows_by_ts: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for e in rows:
        rows_by_ts[int(e.get("ts", 0))].append(e)

    posts_by_pair: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in posts:
        posts_by_pair[str(e.get("pair") or "")].append(e)
    cooldowns_by_pair: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in cooldowns:
        cooldowns_by_pair[str(e.get("pair") or "")].append(e)

    qualifying_by_pair: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in mature_rows:
        pair = str(e.get("pair") or "")
        candles = ohlc.get(pair)
        f = e.get("features") or {}
        if not candles:
            continue
        price = float(f.get("price") or 0)
        outcome = future_range(candles, int(e["ts"]), int(e["ts"]) + int(HORIZON_HOURS * 3600), price)
        if not outcome:
            continue
        fresh = float(f.get("fresh_move_3h") or 999)
        late = bool(f.get("late"))
        if outcome["peak_pct"] >= MOVE_THRESHOLD_PCT and fresh <= EARLY_FRESH_MOVE_MAX_PCT and not late:
            qualifying_by_pair[pair].append({"event": e, "outcome": outcome})

    cases = []
    for pair, options in sorted(qualifying_by_pair.items()):
        options.sort(key=lambda x: int(x["event"]["ts"]))
        first = options[0]
        e = first["event"]
        f = e.get("features") or {}
        outcome = first["outcome"]
        start_ts = int(e["ts"])
        peak_ts = int(outcome["peak_ts"])

        first_post = next(
            (p for p in sorted(posts_by_pair.get(pair, []), key=lambda x: int(x.get("ts", 0)))
             if start_ts - 60 <= int(p.get("ts", 0)) <= peak_ts),
            None,
        )
        same_run = rows_by_ts.get(start_ts, [])
        eligible = [
            r for r in same_run
            if float((r.get("features") or {}).get("score") or -99) >= CANDIDATE_THRESHOLD
            and not bool((r.get("features") or {}).get("late"))
        ]
        eligible.sort(key=lambda r: float((r.get("features") or {}).get("score") or -99), reverse=True)
        position = next((i + 1 for i, r in enumerate(eligible) if r.get("pair") == pair), None)
        cooldown = next(
            (c for c in cooldowns_by_pair.get(pair, [])
             if abs(int(c.get("ts", 0)) - start_ts) <= 180),
            None,
        )

        score = float(f.get("score") or -99)
        if first_post:
            delay_min = round((int(first_post["ts"]) - start_ts) / 60, 1)
            status = "DETECTED_EARLY" if delay_min <= 45 else "DETECTED_LATER"
            cause = "SCANNER_OK_DOWNSTREAM_REVIEW_IF_NO_USER_ALERT"
        elif cooldown:
            delay_min = None
            status = "NOT_POSTED"
            cause = "COOLDOWN_SUPPRESSED"
        elif score < CANDIDATE_THRESHOLD:
            delay_min = None
            status = "NOT_POSTED"
            cause = "SCORE_FILTER"
        elif position is not None and position > 3:
            delay_min = None
            status = "NOT_POSTED"
            cause = "TOP3_CAP"
        else:
            delay_min = None
            status = "NOT_POSTED"
            cause = "UNRESOLVED_SCANNER_PATH"

        cases.append({
            "pair": pair,
            "early_row_at_utc": iso(start_ts),
            "early_price_eur": f.get("price"),
            "early_score": f.get("score"),
            "fresh_move_3h_pct": f.get("fresh_move_3h"),
            "ret1h_pct": f.get("ret1h"),
            "ret3h_pct": f.get("ret3h"),
            "volume_ratio_live": f.get("volume_ratio_live"),
            "volume_ratio_closed": f.get("volume_ratio_closed"),
            "eligible_rank_within_run": position,
            "future_peak_pct": outcome["peak_pct"],
            "future_peak_at_utc": iso(peak_ts),
            "future_drawdown_pct": outcome["drawdown_pct"],
            "scanner_status": status,
            "root_cause": cause,
            "first_post_at_utc": iso(first_post.get("ts")) if first_post else None,
            "post_delay_minutes": delay_min,
        })

    post_outcomes = []
    for p in mature_posts:
        pair = str(p.get("pair") or "")
        candles = ohlc.get(pair)
        price = parse_post_price(str(p.get("text") or ""))
        if not candles or not price:
            continue
        outcome = future_range(candles, int(p["ts"]), int(p["ts"]) + int(HORIZON_HOURS * 3600), price)
        if not outcome:
            continue
        post_outcomes.append({
            "pair": pair,
            "posted_at_utc": iso(p["ts"]),
            "price_eur": price,
            "future_peak_pct": outcome["peak_pct"],
            "future_drawdown_pct": outcome["drawdown_pct"],
        })

    gains = [float(x["future_peak_pct"]) for x in post_outcomes]
    summary = {
        "telemetry_events": len(events),
        "mature_rows_analyzed": len(mature_rows),
        "mature_posts_analyzed": len(post_outcomes),
        "strong_early_cases": len(cases),
        "scanner_posted_cases": sum(1 for c in cases if c["scanner_status"].startswith("DETECTED")),
        "not_posted_cases": sum(1 for c in cases if c["scanner_status"] == "NOT_POSTED"),
        "median_post_future_peak_pct": round(statistics.median(gains), 2) if gains else None,
        "errors": errors,
    }

    report = {
        "schema_version": 1,
        "generated_at_utc": iso(now),
        "parameters": {
            "lookback_hours": LOOKBACK_HOURS,
            "horizon_hours": HORIZON_HOURS,
            "min_age_hours": MIN_AGE_HOURS,
            "move_threshold_pct": MOVE_THRESHOLD_PCT,
            "early_fresh_move_max_pct": EARLY_FRESH_MOVE_MAX_PCT,
            "candidate_threshold": CANDIDATE_THRESHOLD,
        },
        "summary": summary,
        "strong_early_cases": cases,
        "posted_candidate_outcomes": post_outcomes,
        "limitations": [
            "This audit diagnoses the scanner layer. If SCANNER_OK is shown but the user received no actionable push, downstream integration/filter/push review is still required.",
            "Telemetry started only after audit instrumentation was deployed; older historical runs are covered separately by the reference baseline.",
            "Kraken 15m OHLC is used for ex-post peak/drawdown measurement and can differ slightly from executable tick prices.",
        ],
    }

    OUT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Kraken missed-move audit",
        "",
        f"Generated: {report['generated_at_utc']}",
        f"Strong early cases: **{summary['strong_early_cases']}**",
        f"Scanner-posted cases: **{summary['scanner_posted_cases']}**",
        f"Not-posted cases: **{summary['not_posted_cases']}**",
        "",
        "## Cases",
        "",
    ]
    if not cases:
        lines.append("No mature strong-move case is available yet; telemetry is warming up.")
    else:
        for c in cases:
            lines.append(
                f"- **{c['pair']}** — {c['root_cause']} | early {c['early_row_at_utc']} | "
                f"score {c['early_score']} | fresh {c['fresh_move_3h_pct']}% | "
                f"future +{c['future_peak_pct']}% | post delay {c['post_delay_minutes']} min"
            )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
