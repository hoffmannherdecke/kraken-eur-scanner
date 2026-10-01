#!/usr/bin/env python3
"""Broad point-in-time methodology smoke across normalized Kraken EUR 15m pairs.

This is NOT a strategy backtest. It verifies that point-in-time replay mechanics
hold across a deterministic cross-section of real normalized pairs and multiple
contiguous decision windows per pair.

Selection rules are deterministic and return-agnostic:
- pairs are chosen evenly across alphabetically sorted eligible pair files;
- decision anchors are chosen evenly across each pair's eligible contiguous
  windows;
- no label/performance value participates in selection.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


def load_v2(repo_root: Path):
    path = repo_root / "tools" / "historical-real-pair-replay-smoke-v2.py"
    spec = importlib.util.spec_from_file_location("pit_replay_v2", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to import PIT replay V2")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def even_indices(length: int, count: int) -> list[int]:
    if count < 1:
        raise ValueError("count must be >=1")
    if length < 1:
        return []
    if count >= length:
        return list(range(length))
    if count == 1:
        return [length // 2]
    positions = [round(i * (length - 1) / (count - 1)) for i in range(count)]
    # rounding can only duplicate in extreme small cases; dedupe deterministically
    out: list[int] = []
    for pos in positions:
        if pos not in out:
            out.append(pos)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("normalized_dir", type=Path)
    ap.add_argument("--repo-root", type=Path, required=True)
    ap.add_argument("--expected-count", type=int, default=648)
    ap.add_argument("--pair-count", type=int, default=12)
    ap.add_argument("--anchors-per-pair", type=int, default=3)
    ap.add_argument("--lookback-bars", type=int, default=20)
    ap.add_argument("--horizon-bars", type=int, default=24)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    v2 = load_v2(args.repo_root)

    files = sorted(
        args.normalized_dir.glob("*EUR_15.normalized.csv.gz"),
        key=lambda p: p.name.upper(),
    )
    if len(files) != args.expected_count:
        raise SystemExit(
            f"normalized pair count mismatch: expected {args.expected_count}, got {len(files)}"
        )

    eligible: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for path in files:
        rows = v2.load_rows(path)
        candidates = v2.eligible_indices(
            rows,
            args.lookback_bars,
            args.horizon_bars,
        )
        if candidates:
            eligible.append(
                {
                    "path": path,
                    "row_count": len(rows),
                    "eligible_indices": candidates,
                }
            )
        else:
            skipped.append(
                {
                    "file": path.name,
                    "row_count": len(rows),
                    "reason": "no_contiguous_window",
                }
            )

    if len(eligible) < args.pair_count:
        raise SystemExit(
            f"only {len(eligible)} pairs have eligible contiguous windows; "
            f"requested {args.pair_count}"
        )

    selected = [eligible[i] for i in even_indices(len(eligible), args.pair_count)]

    cases: list[dict[str, Any]] = []
    for pair_entry in selected:
        candidates = pair_entry["eligible_indices"]
        anchor_positions = even_indices(len(candidates), args.anchors_per_pair)
        for anchor_pos in anchor_positions:
            decision_index = candidates[anchor_pos]
            result = v2.run_replay(
                pair_entry["path"],
                args.lookback_bars,
                args.horizon_bars,
                decision_index,
            )

            decision = result["decision"]
            label = result["label"]
            if decision["point_in_time_assertions"]["future_bar_in_features"]:
                raise AssertionError("future feature leakage detected")
            if not decision["point_in_time_assertions"]["history_contiguous_15m"]:
                raise AssertionError("non-contiguous history accepted")
            if not label["future_contiguous_15m"]:
                raise AssertionError("non-contiguous future label accepted")

            cases.append(
                {
                    "pair_file": pair_entry["path"].name,
                    "row_count": result["row_count"],
                    "eligible_contiguous_decision_windows": result[
                        "eligible_contiguous_decision_windows"
                    ],
                    "decision_index": decision_index,
                    "decision_time_utc": decision["decision_time_utc"],
                    "decision_sha256": result["decision_sha256"],
                    "history_contiguous_15m": True,
                    "future_contiguous_15m": True,
                    "future_bar_in_features": False,
                    "label_generated_after_decision_freeze": label[
                        "generated_after_decision_freeze"
                    ],
                    # Labels are retained per-case for auditability only.
                    # This smoke intentionally does not aggregate/rank performance.
                    "audit_label": {
                        "end_return_pct": label["end_return_pct"],
                        "mfe_pct": label["mfe_pct"],
                        "mae_pct": label["mae_pct"],
                    },
                }
            )

    hashes = [c["decision_sha256"] for c in cases]
    if len(set(hashes)) != len(hashes):
        raise AssertionError("duplicate decision hashes in broad methodology smoke")

    result = {
        "kind": "KRAKEN_EUR15_BROAD_PIT_METHODOLOGY_SMOKE_V1",
        "status": "PASS",
        "normalized_dir": str(args.normalized_dir),
        "normalized_file_count": len(files),
        "eligible_pair_count": len(eligible),
        "skipped_pair_count": len(skipped),
        "selected_pair_count": len(selected),
        "anchors_per_pair_requested": args.anchors_per_pair,
        "case_count": len(cases),
        "lookback_bars": args.lookback_bars,
        "horizon_bars": args.horizon_bars,
        "selection_contract": {
            "pair_selection": "evenly_spaced_alphabetical_among_contiguous_eligible_pairs",
            "anchor_selection": "evenly_spaced_among_contiguous_eligible_indices",
            "performance_used_for_selection": False,
            "selection_frozen_before_label_interpretation": True,
        },
        "integrity_summary": {
            "future_feature_leak_cases": sum(
                1 for c in cases if c["future_bar_in_features"]
            ),
            "non_contiguous_history_cases": sum(
                1 for c in cases if not c["history_contiguous_15m"]
            ),
            "non_contiguous_future_cases": sum(
                1 for c in cases if not c["future_contiguous_15m"]
            ),
            "labels_not_generated_after_freeze": sum(
                1 for c in cases if not c["label_generated_after_decision_freeze"]
            ),
            "unique_decision_hashes": len(set(hashes)),
        },
        "selected_pairs": [
            {
                "file": entry["path"].name,
                "row_count": entry["row_count"],
                "eligible_contiguous_decision_windows": len(entry["eligible_indices"]),
            }
            for entry in selected
        ],
        "skipped_pairs_sample": skipped[:25],
        "cases": cases,
        "interpretation_guardrail": (
            "Methodology/integrity smoke only. Audit labels are not aggregated, "
            "ranked, optimized or valid evidence of trading edge."
        ),
        "guardrails": {
            "network_used": False,
            "active_strategy_changed": False,
            "paper_shadow_runtime_changed": False,
            "strategy_parameters_tuned": False,
            "performance_claim_made": False,
        },
        "next_gate": "freeze_historical_strategy_replay_spec_before_any_performance_backtest",
    }

    summary = result["integrity_summary"]
    if any(
        summary[key] != 0
        for key in (
            "future_feature_leak_cases",
            "non_contiguous_history_cases",
            "non_contiguous_future_cases",
            "labels_not_generated_after_freeze",
        )
    ):
        raise AssertionError("broad PIT integrity summary failed")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    tmp.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", "utf-8")
    tmp.replace(args.output)

    compact = {
        "kind": result["kind"],
        "status": result["status"],
        "normalized_file_count": result["normalized_file_count"],
        "eligible_pair_count": result["eligible_pair_count"],
        "skipped_pair_count": result["skipped_pair_count"],
        "selected_pair_count": result["selected_pair_count"],
        "case_count": result["case_count"],
        "integrity_summary": result["integrity_summary"],
        "output": str(args.output),
        "next_gate": result["next_gate"],
        "guardrails": result["guardrails"],
    }
    print("KRAKEN_EUR15_BROAD_PIT_SMOKE " + json.dumps(compact, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
