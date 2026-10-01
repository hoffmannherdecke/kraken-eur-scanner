#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def normalized_text_sha256(p: Path) -> str:
    # Git may materialize text files with CRLF on Windows. The frozen spec
    # identity is based on LF-normalized UTF-8 bytes so checkout line endings
    # cannot change the lock identity.
    text=p.read_text("utf-8")
    text=text.replace("\r\n","\n").replace("\r","\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("spec", type=Path)
    ap.add_argument("--expected-sha256")
    args=ap.parse_args()
    s=json.loads(args.spec.read_text("utf-8"))
    assert s["kind"]=="KRAKEN_EUR15_PERFORMANCE_REPLAY_SPEC_V1"
    assert s["status"]=="FROZEN_PRE_REGISTERED_NOT_YET_EXECUTED"
    assert s["dataset"]["expected_normalized_pair_files"]==648
    assert s["point_in_time_contract"]["require_history_contiguous_15m"] is True
    assert s["point_in_time_contract"]["require_future_label_contiguous_15m"] is True
    assert s["pre_registration"]["holdout_must_remain_sealed_during_v1_selection"] is True
    assert s["validation_topology"]["sealed_holdout"]["status"]=="LOCKED_DO_NOT_READ_IN_V1_SELECTION"
    assert s["execution"]["holding_period_minutes"]==240
    assert s["execution"]["stop_loss"] is None
    assert s["execution"]["take_profit"] is None
    assert s["cost_model"]["primary_cost_for_trial_selection_pct_round_trip"]==1.40
    assert s["signal"]["no_cross_pair_ranking"] is True
    assert s["signal"]["no_score_optimization"] is True
    assert s["search_accounting"]["v1_counts_as_one_pre_registered_trial"] is True
    assert s["safety"]["active_strategy_changed"] is False
    spec_sha=normalized_text_sha256(args.spec)
    if args.expected_sha256 and spec_sha != args.expected_sha256.lower():
        raise SystemExit(
            f"frozen spec checksum mismatch: expected {args.expected_sha256.lower()} got {spec_sha}"
        )
    print(json.dumps({
        "kind":"PERFORMANCE_REPLAY_SPEC_VALIDATION_V1",
        "status":"PASS",
        "spec_sha256":spec_sha,
        "holdout_status":s["validation_topology"]["sealed_holdout"]["status"],
        "primary_cost_pct":s["cost_model"]["primary_cost_for_trial_selection_pct_round_trip"],
        "signal_conditions":s["signal"]["all_conditions_required"],
    },sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
