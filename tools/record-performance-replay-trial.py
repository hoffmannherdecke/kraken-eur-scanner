#!/usr/bin/env python3
"""Record frozen performance replay V1 into the immutable historical trial ledger.

The recorder is idempotent for an identical already-recorded trial and fails
closed if the same trial ID exists with a different payload.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(8 * 1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def tool_fingerprint(repo_root: Path) -> str:
    rels = (
        "research/historical/performance-replay-spec-v1.json",
        "research/historical/performance-replay-spec-v1.lock.json",
        "tools/validate-performance-replay-spec.py",
        "tools/historical-performance-replay-v1.py",
        "tools/record-performance-replay-trial.py",
    )
    parts: list[bytes] = []
    for rel in rels:
        path = repo_root / rel
        parts.extend((rel.encode("utf-8"), b"\0", path.read_bytes(), b"\0"))
    return "sha256:" + hashlib.sha256(b"".join(parts)).hexdigest()


def import_ledger(repo_root: Path):
    path = repo_root / "tools" / "historical-trial-ledger.py"
    spec = importlib.util.spec_from_file_location("historical_trial_ledger", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to import historical-trial-ledger.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", type=Path, required=True)
    ap.add_argument("--lock", type=Path, required=True)
    ap.add_argument("--result", type=Path, required=True)
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--schema", type=Path, required=True)
    ap.add_argument("--output-record", type=Path, required=True)
    ap.add_argument("--repo-root", type=Path, required=True)
    args = ap.parse_args()

    spec_obj = load_json(args.spec)
    lock_obj = load_json(args.lock)
    result = load_json(args.result)
    schema = load_json(args.schema)

    spec_sha = sha256_file(args.spec)
    if lock_obj.get("status") != "LOCKED":
        raise SystemExit("performance replay spec lock is not LOCKED")
    if lock_obj.get("spec_sha256") != spec_sha:
        raise SystemExit("performance replay spec checksum does not match lock")
    if result.get("status") != "PASS":
        raise SystemExit("performance replay result status is not PASS")
    if result.get("spec_sha256") != spec_sha:
        raise SystemExit("performance replay result spec checksum mismatch")
    if result.get("holdout_guard", {}).get("holdout_metrics_computed") is not False:
        raise SystemExit("sealed holdout metrics were computed")
    if result.get("holdout_guard", {}).get("holdout_events_generated") != 0:
        raise SystemExit("sealed holdout event leakage detected")
    if result.get("guardrails", {}).get("threshold_optimization_performed") is not False:
        raise SystemExit("threshold optimization guardrail violated")
    if result.get("guardrails", {}).get("cross_pair_ranking_performed") is not False:
        raise SystemExit("cross-pair ranking guardrail violated")

    topo = spec_obj["validation_topology"]
    cost = spec_obj["cost_model"]
    execution = spec_obj["execution"]
    events_sha = str(result["events_output_sha256"])
    trial_id = "PERF-EUR15-V1-" + spec_sha[:12].upper()

    record = {
        "trial_id": trial_id,
        "created_at_utc": spec_obj["frozen_date"] + "T00:00:00Z",
        "parent_hypothesis": spec_obj["parent_hypothesis"],
        "strategy_revision": "EUR15_PRICE_VOLUME_CONTINUATION_BASELINE_V1",
        "code_fingerprint": tool_fingerprint(args.repo_root),
        "feature_schema_version": "EUR15_PRICE_VOLUME_CONTINUATION_FEATURES_V1",
        "dataset_snapshot": {
            "kind": "KRAKEN_EUR15_NORMALIZED_DATASET_V1",
            "raw_archive_sha256": spec_obj["dataset"]["raw_archive_sha256"],
            "normalization_catalog_sha256": result["normalization_catalog_sha256"],
            "spec_sha256": spec_sha,
            "events_output_sha256": events_sha,
            "normalized_file_count": result["normalized_file_count"],
            "holdout_status": result["holdout_guard"]["holdout_status"],
        },
        "dataset_sha256": spec_obj["dataset"]["raw_archive_sha256"],
        "universe_method": spec_obj["dataset"]["survivorship_rule"],
        "train_window": topo["research_train"],
        "calibration_window": topo["calibration"],
        "validation_window": topo["validation"],
        "holdout_window": None,
        "purge_seconds": int(topo["purge_seconds"]),
        "embargo_seconds": int(topo["embargo_seconds"]),
        "fee_model": {
            "kind": "FROZEN_PERFORMANCE_REPLAY_V1",
            "taker_pct_per_side": float(cost["taker_fee_pct_per_side"]),
            "total_round_trip_primary_pct": float(
                cost["primary_cost_for_trial_selection_pct_round_trip"]
            ),
        },
        "spread_model": {
            "kind": cost["spread_model"],
            "separately_observed": False,
        },
        "slippage_model": {
            "kind": "FROZEN_FIXED_PROXY_V1",
            "pct_per_side": float(cost["slippage_pct_per_side"]),
        },
        "fill_ordering_policy": "NEXT_CONTIGUOUS_15M_BAR_OPEN_TO_16TH_FUTURE_BAR_CLOSE",
        "stop_policy": {
            "kind": "NO_STOP_V1",
            "stop_loss": execution["stop_loss"],
            "take_profit": execution["take_profit"],
        },
        "ttl_policy": {
            "kind": "FIXED_HOLD_V1",
            "holding_period_minutes": int(execution["holding_period_minutes"]),
        },
        "sizing_policy": {
            "kind": "EVENT_STUDY_NO_PORTFOLIO_SIZING",
            "portfolio_capital_simulation": bool(execution["portfolio_capital_simulation"]),
        },
        "parameters": {
            "eligibility": spec_obj["eligibility"],
            "signal": spec_obj["signal"],
            "execution": execution,
            "cost_model": cost,
        },
        "metrics": {
            "kind": result["kind"],
            "status": result["status"],
            "total_event_count": result["total_event_count"],
            "split_event_counts": result["split_event_counts"],
            "primary_validation_metrics": result["primary_validation_metrics"],
            "metrics_by_split": result["metrics_by_split"],
            "holdout_guard": result["holdout_guard"],
            "events_output_sha256": events_sha,
            "interpretation_guardrail": result["interpretation_guardrail"],
        },
        "influenced_later_design": False,
    }

    ledger = import_ledger(args.repo_root)
    ledger.validate_record(record, schema)

    args.output_record.parent.mkdir(parents=True, exist_ok=True)
    args.output_record.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    con = ledger.connect(args.db)
    try:
        ledger.init_db(con)
        existing = con.execute(
            "select payload_sha256,payload_json from trials where trial_id=?",
            (trial_id,),
        ).fetchone()
        digest = ledger.payload_sha256(record)

        if existing is None:
            digest = ledger.append_record(con, record, schema)
            status = "PASS_RECORDED"
        else:
            existing_digest, existing_json = existing
            existing_obj = json.loads(existing_json)
            if (
                existing_digest != digest
                or ledger.payload_sha256(existing_obj) != digest
            ):
                raise SystemExit(
                    "trial_id already exists with a different payload; immutable conflict"
                )
            status = "ALREADY_RECORDED_IDENTICAL"

        verification = ledger.verify(con)
    finally:
        con.close()

    if verification["status"] != "PASS":
        raise SystemExit("trial ledger verification failed")

    out = {
        "kind": "PERFORMANCE_REPLAY_TRIAL_RECORD_V1",
        "status": status,
        "trial_id": trial_id,
        "payload_sha256": digest,
        "spec_sha256": spec_sha,
        "events_output_sha256": events_sha,
        "ledger_trial_count": verification["trial_count"],
        "corrupt_trial_ids": verification["corrupt_trial_ids"],
        "holdout_metrics_computed": False,
        "holdout_events_generated": 0,
        "guardrails": {
            "network_used": False,
            "active_strategy_changed": False,
            "paper_shadow_runtime_changed": False,
            "real_money_action": False,
        },
        "next_gate": "review_validation_without_opening_holdout",
    }
    print("PERFORMANCE_REPLAY_TRIAL_RECORD " + json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
