#!/usr/bin/env python3
"""Record the physical real-pair PIT replay into the immutable trial ledger.

Reads the local normalization catalog + replay report produced by the MINI-PC
orchestrator, constructs a methodology-only trial record, writes an audit JSON,
and appends it to the immutable SQLite trial ledger.

Idempotency:
- trial_id is derived from decision_sha256;
- rerun with an identical record returns ALREADY_RECORDED_IDENTICAL;
- rerun with same trial_id but different payload fails closed.

This tool never changes active Paper/Shadow strategy state and never uses network.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"JSON object required: {path}")
    return obj


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(8 * 1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def tool_fingerprint(repo_root: Path) -> str:
    parts = []
    for rel in (
        "tools/normalize-kraken-eur15.py",
        "tools/historical-real-pair-replay-smoke.py",
        "tools/run-minipc-eur15-normalization.ps1",
    ):
        path = repo_root / rel
        parts.append(rel.encode("utf-8"))
        parts.append(b"\0")
        parts.append(path.read_bytes())
        parts.append(b"\0")
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
    ap.add_argument("--normalization-catalog", type=Path, required=True)
    ap.add_argument("--replay-report", type=Path, required=True)
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--schema", type=Path, required=True)
    ap.add_argument("--output-record", type=Path, required=True)
    ap.add_argument("--repo-root", type=Path, required=True)
    args = ap.parse_args()

    norm = load_json(args.normalization_catalog)
    replay = load_json(args.replay_report)
    schema = load_json(args.schema)

    if norm.get("status") != "PASS":
        raise SystemExit("normalization catalog status is not PASS")
    if replay.get("status") != "PASS":
        raise SystemExit("replay report status is not PASS")
    if int(norm.get("file_count", -1)) != 648:
        raise SystemExit("normalization catalog file_count is not 648")

    decision = replay["decision"]
    label = replay["label"]
    decision_sha = str(replay["decision_sha256"])
    if len(decision_sha) != 64:
        raise SystemExit("decision_sha256 invalid")

    normalized_pair_sha = str(replay["normalized_pair_sha256"])
    if len(normalized_pair_sha) != 64:
        raise SystemExit("normalized_pair_sha256 invalid")

    trial_id = "REALPAIR-PIT-" + decision_sha[:20].upper()

    record = {
        "trial_id": trial_id,
        "created_at_utc": decision["decision_time_utc"],
        "parent_hypothesis": "docs/historical-backtest-preflight.md#real-pair-point-in-time-replay",
        "strategy_revision": "NO_STRATEGY_REPLAY_METHODOLOGY_SMOKE_V1",
        "code_fingerprint": tool_fingerprint(args.repo_root),
        "feature_schema_version": decision["feature_schema_version"],
        "dataset_snapshot": {
            "kind": "KRAKEN_EUR15_NORMALIZED_PAIR_V1",
            "pair_file": replay["normalized_pair"],
            "normalization_schema": norm["schema_version"],
            "source_archive_sha256": norm.get("source_archive_sha256"),
            "normalization_catalog_sha256": sha256_file(args.normalization_catalog),
            "replay_report_sha256": sha256_file(args.replay_report),
        },
        "dataset_sha256": normalized_pair_sha,
        "universe_method": (
            "single real Kraken EUR normalized pair chosen by guarded orchestrator "
            "for methodology/integrity smoke only; not a performance-selected sample"
        ),
        "train_window": {
            "start": norm["files"][0]["first_bar_start_utc"] if norm.get("files") else None,
            "end": decision["decision_time_utc"],
            "role": "feature_history_only_no_training",
        },
        "calibration_window": {
            "start": decision["decision_time_utc"],
            "end": decision["decision_time_utc"],
            "role": "not_used_methodology_smoke",
        },
        "validation_window": {
            "start_epoch": label["label_first_bar_start_epoch"],
            "end_epoch": label["label_last_bar_end_epoch"],
            "role": "post_decision_label_only",
        },
        "holdout_window": None,
        "purge_seconds": 0,
        "embargo_seconds": 0,
        "fee_model": {
            "kind": "baseline_reference_not_applied_to_methodology_smoke",
            "taker_pct_per_side": 0.60,
        },
        "spread_model": {"kind": "not_applied_methodology_smoke"},
        "slippage_model": {"kind": "not_applied_methodology_smoke"},
        "fill_ordering_policy": "not_applicable_no_trade_execution",
        "stop_policy": "not_applied_methodology_smoke",
        "ttl_policy": "not_applied_methodology_smoke",
        "sizing_policy": "not_applied_methodology_smoke",
        "parameters": {
            "lookback_bars": decision["lookback_bars"],
            "horizon_bars": label["horizon_bars"],
            "decision_index": decision["decision_index"],
            "decision_sha256": decision_sha,
            "feature_visibility_rule": decision["point_in_time_assertions"]["feature_visibility_rule"],
        },
        "metrics": {
            "status": replay["status"],
            "row_count": replay["row_count"],
            "future_bar_in_features": decision["point_in_time_assertions"]["future_bar_in_features"],
            "generated_after_decision_freeze": label["generated_after_decision_freeze"],
            "end_return_pct": label["end_return_pct"],
            "mfe_pct": label["mfe_pct"],
            "mae_pct": label["mae_pct"],
            "performance_interpretation_allowed": False,
            "methodology_integrity_only": True,
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

        record_digest = ledger.payload_sha256(record)

        if existing is None:
            digest = ledger.append_record(con, record, schema)
            status = "PASS_RECORDED"
        else:
            existing_digest, existing_json = existing
            existing_obj = json.loads(existing_json)
            if existing_digest != record_digest or ledger.payload_sha256(existing_obj) != record_digest:
                raise SystemExit(
                    "trial_id already exists with different payload; immutable ledger conflict"
                )
            digest = existing_digest
            status = "ALREADY_RECORDED_IDENTICAL"

        verification = ledger.verify(con)
    finally:
        con.close()

    if verification["status"] != "PASS":
        raise SystemExit("trial ledger verification failed after record operation")

    result = {
        "kind": "REAL_PAIR_PIT_TRIAL_RECORD_V1",
        "status": status,
        "trial_id": trial_id,
        "payload_sha256": digest,
        "decision_sha256": decision_sha,
        "dataset_sha256": normalized_pair_sha,
        "ledger_trial_count": verification["trial_count"],
        "corrupt_trial_ids": verification["corrupt_trial_ids"],
        "output_record": str(args.output_record),
        "guardrails": {
            "network_used": False,
            "active_strategy_changed": False,
            "paper_shadow_runtime_changed": False,
            "strategy_performance_claim_made": False,
        },
        "next_gate": "broader_historical_point_in_time_replay",
    }
    print("REAL_PAIR_PIT_TRIAL_RECORD " + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
