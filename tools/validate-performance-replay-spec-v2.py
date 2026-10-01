#!/usr/bin/env python3
"""Validate the frozen second-leg Performance Replay V2 specification."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def normalized_text_sha256(path: Path) -> str:
    text = path.read_text("utf-8")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", type=Path)
    ap.add_argument("--expected-sha256")
    args = ap.parse_args()

    s = json.loads(args.spec.read_text("utf-8"))
    assert s["kind"] == "KRAKEN_EUR15_PERFORMANCE_REPLAY_SPEC_V2"
    assert s["status"] == "FROZEN_PRE_REGISTERED_NOT_YET_EXECUTED"
    assert s["provenance"]["influenced_by_v1_validation"] is True
    assert s["dataset"]["expected_normalized_pair_files"] == 648
    assert s["evaluation_topology"]["sealed_holdout"]["status"] == "LOCKED_DO_NOT_READ_IN_V2_DEVELOPMENT"
    assert s["point_in_time_contract"]["confirmation_is_observed_before_entry"] is True
    assert s["point_in_time_contract"]["entry_occurs_only_after_confirmation_close"] is True
    assert s["confirmation"]["max_wait_bars"] == 4
    assert s["confirmation"]["condition"] == "FIRST_SUBSEQUENT_CONTIGUOUS_BAR_CLOSE_STRICTLY_ABOVE_SIGNAL_BAR_HIGH"
    assert s["execution"]["holding_period_bars"] == 16
    assert s["execution"]["holding_period_minutes"] == 240
    assert s["cost_model"]["primary_cost_pct_round_trip"] == 1.40
    gate = s["development_gate_before_holdout"]
    assert gate["min_confirmed_event_count"] == 500
    assert gate["require_mean_net_return_gt_zero"] is True
    assert gate["require_median_net_return_gt_zero"] is True
    assert gate["require_positive_net_rate_gte"] == 0.50
    assert gate["require_top10_pair_event_share_lte"] == 0.40
    for key in ("threshold_sweep","horizon_sweep","pair_subset_selection","month_subset_selection","holdout_metrics","holdout_event_generation"):
        assert s["prohibited"][key] is True

    digest = normalized_text_sha256(args.spec)
    if args.expected_sha256 and digest != args.expected_sha256.lower():
        raise SystemExit(
            f"frozen V2 spec checksum mismatch: expected {args.expected_sha256.lower()} got {digest}"
        )

    print(json.dumps({
        "kind":"PERFORMANCE_REPLAY_SPEC_V2_VALIDATION",
        "status":"PASS",
        "spec_sha256":digest,
        "holdout_status":s["evaluation_topology"]["sealed_holdout"]["status"],
        "confirmation":s["confirmation"],
        "development_gate":gate,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
