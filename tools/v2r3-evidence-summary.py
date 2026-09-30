#!/usr/bin/env python3
"""Read-only evidence summary for the active V2R3 paper series.

This script does not change strategy state, does not fetch market data and does
not make promotion decisions. It only aggregates already-persisted repository
evidence so timing, selectivity and missed-move behavior can be reviewed before
any V2R4 activation.
"""
from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text("utf-8"))
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def stats(values: list[float]) -> dict[str, Any]:
    clean = sorted(x for x in values if math.isfinite(x))
    if not clean:
        return {"n": 0, "mean": None, "median": None, "p90": None, "max": None}
    idx90 = min(len(clean) - 1, max(0, math.ceil(0.90 * len(clean)) - 1))
    return {
        "n": len(clean),
        "mean": round(statistics.fmean(clean), 3),
        "median": round(statistics.median(clean), 3),
        "p90": round(clean[idx90], 3),
        "max": round(clean[-1], 3),
    }


def pct(n: int, d: int) -> float | None:
    return round(100.0 * n / d, 2) if d else None


def main() -> int:
    control = load_json(ROOT / "paper_runtime_control.json") or {}
    series_id = control.get("series_id")
    if not series_id:
        raise SystemExit("series_id missing from paper_runtime_control.json")

    decisions: dict[str, dict[str, Any]] = {}
    for p in sorted((ROOT / "paper_decisions").glob("*.json")):
        d = load_json(p)
        if d and d.get("series_id") == series_id:
            decisions[p.name] = d

    revals: dict[str, dict[str, Any]] = {}
    for p in sorted((ROOT / "paper_revalidations").glob("*.json")):
        d = load_json(p)
        if d and d.get("series_id") == series_id:
            revals[p.name] = d

    followups: dict[str, dict[str, Any]] = {}
    for p in sorted((ROOT / "paper_followups").glob("*.json")):
        d = load_json(p)
        if d and d.get("series_id") == series_id:
            followups[p.name] = d

    handoffs: dict[str, dict[str, Any]] = {}
    for name in decisions:
        q = load_json(ROOT / "handoff_queue" / name)
        if q:
            handoffs[name] = q

    original = Counter()
    terminal = Counter()
    paths = Counter()
    reason_counts = Counter()
    lane_counts = Counter()
    score_values: list[float] = []
    decision_latency: list[float] = []
    eval_runtime: list[float] = []
    handoff_latency: list[float] = []
    reval_ttl_lag: list[float] = []
    waits = 0
    wait_to_buy = 0
    wait_to_reject = 0
    wait_pending = 0
    buy_count = 0

    for name, d in decisions.items():
        dec = d.get("decision") or {}
        kind = str(dec.get("decision") or "UNKNOWN")
        original[kind] += 1
        lane_counts[str(dec.get("setup_lane") or "UNKNOWN")] += 1
        reason_counts.update(str(x) for x in (dec.get("reason_codes") or []))

        timing = d.get("timing") or {}
        for target, key in (
            (decision_latency, "detected_to_evaluation_complete_seconds"),
            (eval_runtime, "evaluation_runtime_seconds"),
            (handoff_latency, "handoff_to_evaluation_start_seconds"),
        ):
            v = num(timing.get(key))
            if v is not None:
                target.append(v)

        q = handoffs.get(name) or {}
        score = num((q.get("scanner_candidate") or {}).get("score"))
        if score is not None:
            score_values.append(score)

        if kind == "WAIT":
            waits += 1
            rv = revals.get(name)
            if rv:
                rkind = str((rv.get("decision") or {}).get("decision") or "UNKNOWN")
                lag = num((rv.get("timing") or {}).get("ttl_lag_seconds"))
                if lag is not None:
                    reval_ttl_lag.append(lag)
                if rkind == "BUY_SCOUT":
                    wait_to_buy += 1
                    paths["WAIT_TO_BUY"] += 1
                    terminal["BUY_SCOUT"] += 1
                    buy_count += 1
                elif rkind == "REJECT":
                    wait_to_reject += 1
                    paths["WAIT_TO_REJECT"] += 1
                    terminal["REJECT"] += 1
                else:
                    paths["WAIT_TO_OTHER"] += 1
                    terminal[rkind] += 1
            else:
                wait_pending += 1
                paths["WAIT_PENDING"] += 1
        else:
            terminal[kind] += 1
            if kind == "BUY_SCOUT":
                buy_count += 1
            paths[kind] += 1

    # Follow-up / missed-move evidence.
    h6_mfe: list[float] = []
    h6_mae: list[float] = []
    h6_end: list[float] = []
    missed = Counter()
    top_missed: list[dict[str, Any]] = []

    opp_horizon_stats: dict[str, dict[str, list[float]]] = {
        h: {"mfe": [], "mae": [], "end": []}
        for h in ("15", "60", "240", "720", "1440")
    }
    flagged_already_run = {"n": 0, "h6_complete": 0, "h6_mfe": []}
    not_flagged_already_run = {"n": 0, "h6_complete": 0, "h6_mfe": []}

    reason_h6: dict[str, list[float]] = defaultdict(list)
    lane_h6: dict[str, list[float]] = defaultdict(list)
    scanner_late_h6: dict[str, list[float]] = defaultdict(list)

    for name, rec in followups.items():
        if rec.get("excluded_from_missed_move_stats") is True:
            continue

        h6 = (rec.get("horizons") or {}).get("360") or {}
        mfe6 = num(h6.get("mfe_pct")) if h6.get("complete") else None
        mae6 = num(h6.get("mae_pct")) if h6.get("complete") else None
        end6 = num(h6.get("end_close_pct")) if h6.get("complete") else None
        if mfe6 is not None:
            h6_mfe.append(mfe6)
            if mae6 is not None:
                h6_mae.append(mae6)
            if end6 is not None:
                h6_end.append(end6)
            for threshold in (2, 5, 8, 10, 15):
                if mfe6 >= threshold:
                    missed[str(threshold)] += 1

            d = decisions.get(name) or {}
            for code in (d.get("decision") or {}).get("reason_codes") or []:
                reason_h6[str(code)].append(mfe6)
            lane_h6[str((d.get("decision") or {}).get("setup_lane") or "UNKNOWN")].append(mfe6)

            q = handoffs.get(name) or {}
            late = (q.get("scanner_candidate") or {}).get("late")
            scanner_late_h6["late" if late is True else "not_late"].append(mfe6)

            top_missed.append({
                "candidate_id": rec.get("candidate_id"),
                "pair": rec.get("pair"),
                "original_decision": rec.get("original_decision"),
                "path_classification": rec.get("path_classification"),
                "mfe_6h_pct": round(mfe6, 3),
                "mae_6h_pct": round(mae6, 3) if mae6 is not None else None,
                "end_6h_pct": round(end6, 3) if end6 is not None else None,
                "reason_codes": (d.get("decision") or {}).get("reason_codes") or [],
                "setup_lane": (d.get("decision") or {}).get("setup_lane"),
                "scanner_late": late,
                "score": num((q.get("scanner_candidate") or {}).get("score")),
            })

        audit = rec.get("opportunity_audit") or {}
        bucket = flagged_already_run if audit.get("flagged_as_already_run") is True else not_flagged_already_run
        bucket["n"] += 1
        if mfe6 is not None:
            bucket["h6_complete"] += 1
            bucket["h6_mfe"].append(mfe6)

        for h, parts in opp_horizon_stats.items():
            row = (audit.get("horizons") or {}).get(h) or {}
            if not row.get("complete"):
                continue
            for metric, key in (("mfe", "mfe_pct"), ("mae", "mae_pct"), ("end", "end_close_pct")):
                v = num(row.get(key))
                if v is not None:
                    parts[metric].append(v)

    top_missed.sort(key=lambda x: x["mfe_6h_pct"], reverse=True)

    def grouped_summary(mapping: dict[str, list[float]], min_n: int = 5) -> list[dict[str, Any]]:
        rows = []
        for key, values in mapping.items():
            if len(values) < min_n:
                continue
            rows.append({
                "key": key,
                "n": len(values),
                "median_mfe_6h_pct": round(statistics.median(values), 3),
                "mean_mfe_6h_pct": round(statistics.fmean(values), 3),
                "missed_5pct_n": sum(v >= 5 for v in values),
                "missed_5pct_rate_pct": pct(sum(v >= 5 for v in values), len(values)),
            })
        rows.sort(key=lambda x: (x["missed_5pct_rate_pct"] or 0, x["median_mfe_6h_pct"]), reverse=True)
        return rows

    report = {
        "kind": "V2R3_EVIDENCE_SUMMARY_V1",
        "series_id": series_id,
        "strategy_revision": control.get("strategy_revision"),
        "target_completed_paper_trades": control.get("target_completed_paper_trades"),
        "counts": {
            "decisions": len(decisions),
            "revalidations": len(revals),
            "followups": len(followups),
            "handoffs_loaded": len(handoffs),
            "original_decisions": dict(original),
            "terminal_decisions": dict(terminal),
            "paths": dict(paths),
            "waits": waits,
            "wait_to_buy": wait_to_buy,
            "wait_to_reject": wait_to_reject,
            "wait_pending": wait_pending,
            "paper_buys": buy_count,
        },
        "timing_seconds": {
            "detected_to_evaluation_complete": stats(decision_latency),
            "handoff_to_evaluation_start": stats(handoff_latency),
            "evaluation_runtime": stats(eval_runtime),
            "wait_ttl_lag": stats(reval_ttl_lag),
            "wait_ttl_lag_over_300s_n": sum(v > 300 for v in reval_ttl_lag),
            "wait_ttl_lag_over_600s_n": sum(v > 600 for v in reval_ttl_lag),
        },
        "scanner_scores": stats(score_values),
        "reason_code_counts": reason_counts.most_common(),
        "setup_lane_counts": dict(lane_counts),
        "six_hour_followup": {
            "complete_n": len(h6_mfe),
            "mfe_pct": stats(h6_mfe),
            "mae_pct": stats(h6_mae),
            "end_close_pct": stats(h6_end),
            "mfe_ge_2pct_n": missed["2"],
            "mfe_ge_5pct_n": missed["5"],
            "mfe_ge_8pct_n": missed["8"],
            "mfe_ge_10pct_n": missed["10"],
            "mfe_ge_15pct_n": missed["15"],
            "mfe_ge_5pct_rate_pct": pct(missed["5"], len(h6_mfe)),
        },
        "opportunity_horizons": {
            h: {metric + "_pct": stats(vals) for metric, vals in parts.items()}
            for h, parts in opp_horizon_stats.items()
        },
        "already_run_flag_comparison": {
            "flagged": {
                "n": flagged_already_run["n"],
                "h6_complete": flagged_already_run["h6_complete"],
                "h6_mfe_pct": stats(flagged_already_run["h6_mfe"]),
            },
            "not_flagged": {
                "n": not_flagged_already_run["n"],
                "h6_complete": not_flagged_already_run["h6_complete"],
                "h6_mfe_pct": stats(not_flagged_already_run["h6_mfe"]),
            },
        },
        "grouped_by_reason_code_h6": grouped_summary(reason_h6),
        "grouped_by_setup_lane_h6": grouped_summary(lane_h6),
        "grouped_by_scanner_late_h6": grouped_summary(scanner_late_h6),
        "top_missed_6h": top_missed[:25],
        "guardrails": {
            "read_only_aggregation": True,
            "strategy_changed": False,
            "paper_runtime_changed": False,
            "promotion_decision_made": False,
            "real_money_actions": False,
        },
    }

    out = Path("v2r3-evidence-summary.json")
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", "utf-8")

    print("V2R3_EVIDENCE_SUMMARY " + json.dumps({
        "series_id": series_id,
        "decisions": len(decisions),
        "original_decisions": dict(original),
        "terminal_decisions": dict(terminal),
        "waits": waits,
        "wait_to_buy": wait_to_buy,
        "wait_to_reject": wait_to_reject,
        "wait_pending": wait_pending,
        "paper_buys": buy_count,
        "six_hour_complete": len(h6_mfe),
        "missed_5pct": missed["5"],
        "missed_8pct": missed["8"],
        "missed_10pct": missed["10"],
        "missed_15pct": missed["15"],
        "detected_to_eval_median_s": stats(decision_latency)["median"],
        "detected_to_eval_p90_s": stats(decision_latency)["p90"],
        "ttl_lag_median_s": stats(reval_ttl_lag)["median"],
        "ttl_lag_p90_s": stats(reval_ttl_lag)["p90"],
    }, sort_keys=True))

    print("V2R3_TOP_REASONS " + json.dumps(reason_counts.most_common(12)))
    print("V2R3_GROUPED_REASON_H6 " + json.dumps(report["grouped_by_reason_code_h6"][:20], separators=(",", ":"), sort_keys=True))
    print("V2R3_SETUP_LANE_H6 " + json.dumps(report["grouped_by_setup_lane_h6"], separators=(",", ":"), sort_keys=True))
    print("V2R3_SCANNER_LATE_H6 " + json.dumps(report["grouped_by_scanner_late_h6"], separators=(",", ":"), sort_keys=True))
    print("V2R3_ALREADY_RUN " + json.dumps(report["already_run_flag_comparison"], separators=(",", ":"), sort_keys=True))
    print("V2R3_OPPORTUNITY_HORIZONS " + json.dumps(report["opportunity_horizons"], separators=(",", ":"), sort_keys=True))
    print("V2R3_TOP_MISSED_6H " + json.dumps(top_missed[:10], separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
