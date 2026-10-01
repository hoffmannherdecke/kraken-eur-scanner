#!/usr/bin/env python3
"""Validation-only failure-mode review for frozen EUR15 Performance Replay V1.

This tool deliberately does NOT:
- open or read the sealed holdout;
- sweep thresholds, horizons, pairs, months, or costs;
- rank pairs for selection;
- modify strategy/runtime state.

It summarizes why the already-frozen V1 validation outcome failed or succeeded
using only the validation events and the already-frozen primary cost.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"JSON object required: {path}")
    return obj


def load_events(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            if not line.strip():
                continue
            obj = json.loads(line)
            if not isinstance(obj, dict):
                raise ValueError(f"{path}:{line_no}: JSON object required")
            rows.append(obj)
    return rows


def q(values: list[float], p: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * p
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi - pos) + xs[hi] * (pos - lo)


def summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "p10": None,
            "p90": None,
        }
    return {
        "count": len(values),
        "mean": round(statistics.fmean(values), 12),
        "median": round(statistics.median(values), 12),
        "p10": round(q(values, 0.10), 12),
        "p90": round(q(values, 0.90), 12),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", type=Path, required=True)
    ap.add_argument("--result", type=Path, required=True)
    ap.add_argument("--events", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    spec = load_json(args.spec)
    result = load_json(args.result)
    events = load_events(args.events)

    if spec.get("kind") != "KRAKEN_EUR15_PERFORMANCE_REPLAY_SPEC_V1":
        raise SystemExit("unexpected spec kind")
    if result.get("kind") != "KRAKEN_EUR15_PERFORMANCE_REPLAY_V1_RESULT":
        raise SystemExit("unexpected result kind")
    if result.get("status") != "PASS":
        raise SystemExit("performance replay result is not PASS")

    holdout = result.get("holdout_guard", {})
    if holdout.get("holdout_metrics_computed") is not False:
        raise SystemExit("holdout metrics were computed")
    if int(holdout.get("holdout_events_generated", -1)) != 0:
        raise SystemExit("holdout events were generated")
    if holdout.get("holdout_used_for_threshold_selection") is not False:
        raise SystemExit("holdout was used for threshold selection")

    validation = [e for e in events if e.get("split") == "validation"]
    if len(validation) != int(result["split_event_counts"]["validation"]):
        raise SystemExit(
            f"validation event count mismatch: result={result['split_event_counts']['validation']} "
            f"events={len(validation)}"
        )

    unexpected_splits = sorted(
        {str(e.get("split")) for e in events}
        - {"research_train", "calibration", "validation"}
    )
    if unexpected_splits:
        raise SystemExit(f"unexpected/holdout event splits present: {unexpected_splits}")

    primary_cost = float(
        spec["cost_model"]["primary_cost_for_trial_selection_pct_round_trip"]
    )

    gross = [float(e["gross_return_pct"]) for e in validation]
    net = [v - primary_cost for v in gross]
    mfe = [float(e["mfe_pct"]) for e in validation]
    mae = [float(e["mae_pct"]) for e in validation]
    giveback = [m - g for m, g in zip(mfe, gross)]

    negative_pre_cost = sum(1 for g in gross if g <= 0)
    positive_pre_but_not_post = sum(1 for g in gross if 0 < g <= primary_cost)
    positive_post = sum(1 for g in gross if g > primary_cost)

    reached_cost_cover_intrabar = sum(1 for m in mfe if m > primary_cost)
    reached_cost_cover_but_failed_exit = sum(
        1 for m, g in zip(mfe, gross) if m > primary_cost and g <= primary_cost
    )

    pair_counts = Counter(str(e["pair"]) for e in validation)
    month_counts = Counter(str(e["decision_time_utc"])[:7] for e in validation)

    top_n = max(1, math.ceil(len(gross) * 0.05)) if gross else 0
    ordered_gross = sorted(gross, reverse=True)
    positive_sum = sum(v for v in gross if v > 0)
    top5_positive_contribution = (
        sum(v for v in ordered_gross[:top_n] if v > 0) / positive_sum
        if positive_sum > 0
        else None
    )

    mean_gross = statistics.fmean(gross) if gross else None
    median_gross = statistics.median(gross) if gross else None
    mean_net = statistics.fmean(net) if net else None
    median_net = statistics.median(net) if net else None

    failure_flags = {
        "mean_net_negative": mean_net is not None and mean_net < 0,
        "median_net_negative": median_net is not None and median_net < 0,
        "median_gross_nonpositive": median_gross is not None and median_gross <= 0,
        "majority_negative_after_cost": (
            bool(net) and sum(1 for v in net if v > 0) / len(net) < 0.5
        ),
        "right_skew_signature": (
            mean_gross is not None
            and median_gross is not None
            and mean_gross > 0
            and median_gross <= 0
        ),
    }

    report = {
        "kind": "KRAKEN_EUR15_PERFORMANCE_REPLAY_V1_VALIDATION_REVIEW",
        "status": "PASS",
        "validation_event_count": len(validation),
        "primary_round_trip_cost_pct": primary_cost,
        "return_summary": {
            "gross": summary(gross),
            "net_primary_cost": summary(net),
            "mfe": summary(mfe),
            "mae": summary(mae),
            "peak_to_exit_giveback_pct": summary(giveback),
        },
        "outcome_decomposition": {
            "negative_or_flat_before_cost_count": negative_pre_cost,
            "positive_before_cost_but_negative_after_cost_count": positive_pre_but_not_post,
            "positive_after_primary_cost_count": positive_post,
            "negative_or_flat_before_cost_rate": round(
                negative_pre_cost / len(validation), 12
            ) if validation else None,
            "cost_flip_rate": round(
                positive_pre_but_not_post / len(validation), 12
            ) if validation else None,
            "positive_after_primary_cost_rate": round(
                positive_post / len(validation), 12
            ) if validation else None,
        },
        "excursion_diagnostics": {
            "reached_primary_cost_cover_intrabar_count": reached_cost_cover_intrabar,
            "reached_primary_cost_cover_intrabar_rate": round(
                reached_cost_cover_intrabar / len(validation), 12
            ) if validation else None,
            "reached_cost_cover_but_failed_by_exit_count": reached_cost_cover_but_failed_exit,
            "reached_cost_cover_but_failed_by_exit_rate": round(
                reached_cost_cover_but_failed_exit / len(validation), 12
            ) if validation else None,
        },
        "concentration_diagnostics": {
            "unique_pairs": len(pair_counts),
            "unique_months": len(month_counts),
            "top10_pair_event_share": round(
                sum(v for _, v in pair_counts.most_common(10)) / len(validation), 12
            ) if validation else None,
            "events_by_month": dict(sorted(month_counts.items())),
            "top5pct_event_positive_gross_contribution_share": (
                round(top5_positive_contribution, 12)
                if top5_positive_contribution is not None
                else None
            ),
        },
        "failure_flags": failure_flags,
        "interpretation": {
            "threshold_sweep_performed": False,
            "horizon_sweep_performed": False,
            "pair_selection_performed": False,
            "month_selection_performed": False,
            "holdout_opened": False,
            "diagnostic_only": True,
            "later_design_must_use_new_version_and_trial": True,
        },
        "guardrails": {
            "network_used": False,
            "active_strategy_changed": False,
            "paper_shadow_runtime_changed": False,
            "real_money_action": False,
        },
        "next_gate": "decide_reject_family_or_preregister_distinct_v2_hypothesis",
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    tmp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", "utf-8")
    tmp.replace(args.output)

    compact = {
        "kind": report["kind"],
        "status": report["status"],
        "validation_event_count": report["validation_event_count"],
        "primary_round_trip_cost_pct": primary_cost,
        "gross_mean": report["return_summary"]["gross"]["mean"],
        "gross_median": report["return_summary"]["gross"]["median"],
        "net_mean": report["return_summary"]["net_primary_cost"]["mean"],
        "net_median": report["return_summary"]["net_primary_cost"]["median"],
        "failure_flags": failure_flags,
        "output": str(args.output),
        "next_gate": report["next_gate"],
    }
    print("PERFORMANCE_V1_VALIDATION_REVIEW " + json.dumps(compact, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
