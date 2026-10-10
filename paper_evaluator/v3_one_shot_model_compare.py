#!/usr/bin/env python3
"""Manual SINGLE-CANDIDATE PAPER-only model comparison on the Mini-PC.

All V2R4 runtime paths are READ ONLY. No state writes, trading API, Supabase,
GitHub runtime updates, scheduled tasks, position simulator, secrets output.
Only two isolated research LLM evaluations, each with the SAME fresh snapshot.
This is an input/decision-path experiment, NOT a net-profit or promotion gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from paper_evaluator import evaluate
from paper_evaluator.v3_entry_handoff_probe import (
    attach_to_future_evaluator, now_utc, utc,
)
from paper_evaluator.successor_coin_entry_evidence_v1 import fetch_public_entry_evidence
from paper_context import build_context


class PreflightStageError(Exception):
    """Public, strictly bounded diagnostic. Never publish raw exception text."""
    def __init__(self, phase: str, cause: Exception):
        self.phase = phase
        self.failure_type = type(cause).__name__
        # Only known constant messages from our own validation code are mapped;
        # arbitrary API, secret or filesystem exception strings are suppressed.
        msg = str(cause)
        reasons = (
            ("frozen active evaluator code differs", "FROZEN_RUNTIME_CODE_MISMATCH"),
            ("required frozen evaluator/context file missing", "FROZEN_RUNTIME_FILE_MISSING"),
            ("exactly one verified active technical successor", "STAGE_UNIQUE_MATCH_FAILED"),
            ("technical stage directory and frozen release SHA mismatch", "STAGE_RELEASE_SHA_MISMATCH"),
            ("candidate entry evidence incomplete", "COIN_BARS_INCOMPLETE_OR_STALE"),
            ("entry evidence stale", "ENTRY_EVIDENCE_TOO_OLD"),
            ("future-known or reversed", "EVIDENCE_TIME_ORDER_INVALID"),
            ("candidate/entry-evidence pair mismatch", "COIN_PAIR_MISMATCH"),
            ("entry frame invalid: 1", "COIN_1M_FRAME_INVALID"),
            ("entry frame invalid: 5", "COIN_5M_FRAME_INVALID"),
            ("entry frame invalid: 15", "COIN_15M_FRAME_INVALID"),
            ("missing invalid volume ratio", "COIN_VOLUME_BASELINE_MISSING"),
            ("ATR unavailable", "COIN_ATR_UNAVAILABLE"),
            ("structure low unavailable", "COIN_LOCAL_LOW_UNAVAILABLE"),
            ("candidate aged out", "CANDIDATE_TOO_OLD"),
            ("expected active PAPER-only", "PAPER_SAFETY_CHECK_FAILED"),
            ("unexpected source strategy revision", "SOURCE_STRATEGY_REVISION_MISMATCH"),
        )
        self.safe_reason = next((code for needle, code in reasons if needle in msg), "UNCLASSIFIED_PRECONDITION")
        super().__init__(phase)


def checked(phase: str, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        raise PreflightStageError(phase, exc) from None


def select_fresh_handoff(directory: Path, control: dict, *,
                         observed_now: datetime | None = None,
                         max_age_seconds: int = 900) -> tuple[Path, dict] | None:
    now = observed_now or datetime.now(timezone.utc)
    start = utc(control["series_started_at_utc"])
    if not directory.is_dir():
        return None
    # Deterministic finite scan; no re-evaluation or backfill of old events.
    files = sorted(directory.glob("*.json"), key=lambda p:(p.stat().st_mtime,p.name),reverse=True)[:40]
    for path in files:
        try:
            item=json.loads(path.read_text("utf-8"))
            evaluate.validate_candidate(item,str(path))
            ts=utc(item["event_time_utc"])
            age=(now-ts).total_seconds()
            if start <= ts <= now and 0 <= age <= max_age_seconds:
                return path,item
        except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError):
            continue
    return None


def freeze_runtime_provenance(runtime_app: Path, code_root: Path,
                              control: dict) -> dict[str,str]:
    if control.get("enabled") is not True or control.get("real_money_actions_enabled") is not False:
        raise ValueError("expected active PAPER-only V2R4 control")
    if control.get("strategy_revision") != "V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION":
        raise ValueError("unexpected source strategy revision")
    paths=("paper_evaluator/evaluate.py","paper_context.py")
    result={}
    for path in paths:
        running=runtime_app/path
        prepared=code_root/path
        if not running.is_file() or not prepared.is_file():
            raise ValueError("required frozen evaluator/context file missing")
        h1=hashlib.sha256(running.read_bytes()).hexdigest()
        h2=hashlib.sha256(prepared.read_bytes()).hexdigest()
        if h1!=h2:
            raise ValueError("frozen active evaluator code differs from detached research checkout: "+path)
        result[path]=h1
    return result


def clean_decision(raw: dict, ticker: dict, external: dict, spec: dict) -> dict:
    # No apply_sample_cap/position side effects: this is a decision-input probe,
    # NOT an official paper fill or recheck. Kraken public execution gates remain.
    d=evaluate.apply_public_tradability_gate(
        evaluate.fail_safe_normalize(raw,ticker),ticker,external,spec)
    return {"decision":d["decision"],"setup_lane":d["setup_lane"],
            "reason_codes":(d.get("reason_codes") or [])[:8],
            "valid_stop_below_ask":(
                d.get("decision")=="BUY_SCOUT"
                and isinstance(d.get("stop_eur"),(int,float))
                and 0 < d["stop_eur"] < ticker["ask"]),
            "valid_stage2_above_ask":(
                d.get("decision")=="BUY_SCOUT"
                and isinstance(d.get("stage2_trigger_eur"),(int,float))
                and d["stage2_trigger_eur"]>ticker["ask"]),
            "expected_remaining_move_pct":d.get("expected_remaining_move_pct"),
            "risk_reward_after_costs":d.get("risk_reward_after_costs"),
            "wait_conditions":len(d.get("watch_conditions") or [])}


def discover_active_paper_runtime(trading_root: Path, expected_series_id: str) -> tuple[Path, dict]:
    """Select exactly one known, verified technical successor without old-series fallback.

    The 2026-10-09 technical cutover intentionally preserved the old
    Runtime/v2r4-paper-app. Active candidates live under
    Runtime/v2r4-paper-stage-<release-sha-prefix>.
    """
    if not expected_series_id.startswith("PAPER-V2R4-"):
        raise ValueError("explicit current V2R4 series id required")
    runtime_root = trading_root / "Runtime"
    matching = []
    other_controls = []
    for path in sorted(runtime_root.glob("v2r4-paper-stage-*")):
        if not path.is_dir():
            continue
        control_path = path / "paper_runtime_control.json"
        if not control_path.is_file():
            continue  # an inert/staged predecessor is never selected
        control = json.loads(control_path.read_text("utf-8"))
        other_controls.append((path, control.get("series_id")))
        if control.get("series_id") != expected_series_id:
            continue
        if control.get("paper_only") is not True:
            raise ValueError("technical successor is not PAPER only")
        if control.get("enabled") is not True or control.get("real_money_actions_enabled") is not False:
            raise ValueError("technical successor disabled or real-money guard unsafe")
        release_sha = str(control.get("release_repo_sha") or "").lower()
        if len(release_sha) != 40 or path.name != "v2r4-paper-stage-" + release_sha[:12]:
            raise ValueError("technical stage directory and frozen release SHA mismatch")
        matching.append((path, control))
    if len(matching) != 1 or len(other_controls) != 1:
        raise ValueError("exactly one verified active technical successor required")
    return matching[0]


def execute_one_shot(trading_root:Path,code_root:Path,
                     expected_series_id: str, *, diagnose_only: bool = False) -> dict:
    runtime,control=checked("STAGE_DISCOVERY",discover_active_paper_runtime,trading_root,expected_series_id)
    spec=checked("STRATEGY_SPEC",lambda: json.loads((runtime/"paper_strategy_spec.json").read_text("utf-8")))
    frozen_hashes=checked("FROZEN_CODE_PROVENANCE",freeze_runtime_provenance,runtime,code_root,control)
    selected=checked("FRESH_CANDIDATE",select_fresh_handoff,runtime/"handoff_queue",control)
    if selected is None:
        return {"status":"BLOCKED_NO_FRESH_CANONICAL_CANDIDATE_IN_LAST_15M",
                "source_series_id":control["series_id"],"model_calls":0,
                "active_v2r4_changed":False,"orders":False}
    path,c=selected
    # Snapshot is collected ONCE for both branches, and all observations are
    # prospective. No replay using OHLC published after candidate detection.
    current=checked("PUBLIC_KRAKEN_TICKER",evaluate.kraken_ticker,c["altname"])
    base_context=checked("READONLY_STANDARD_CONTEXT",build_context,c,current)
    entry=checked("PUBLIC_COIN_OHLC",fetch_public_entry_evidence,c["altname"],c["pair"])
    observed_at=now_utc()
    enriched=checked("COIN_INPUT_ATTACH",attach_to_future_evaluator,c,base_context,entry,observed_at)
    # Block API/model calls if context fetch took too long or source is missing.
    model_current=utc(observed_at)
    if (model_current-utc(c["event_time_utc"])).total_seconds()>900:
        raise PreflightStageError("CANDIDATE_FRESHNESS",ValueError("candidate aged out during context acquisition"))

    if diagnose_only:
        return {"kind":"V3_ONE_SHOT_INPUT_PREFLIGHT_V1",
                "status":"INPUT_READY_NO_MODEL_CALLS_NOT_A_STRATEGY_PASS",
                "source_series_id":control["series_id"],
                "candidate_id":c["candidate_id"],"pair":c["pair"],
                "entry_evidence_status":entry["status"],
                "frames":{k:v.get("status") for k,v in entry["frames"].items()},
                "frozen_evaluator_hashes":frozen_hashes,
                "model_calls":0,"secret_read":False,"orders":False,
                "active_v2r4_changed":False,"economic_edge_proven":False}

    keyfile=trading_root/"Secrets"/"openai-api-key.txt"
    key=checked("EXISTING_MODEL_SECRET",lambda: keyfile.read_text("utf-8").strip())
    if len(key)<20:
        raise PreflightStageError("EXISTING_MODEL_SECRET",ValueError("existing local OpenAI key not readable/valid"))
    os.environ["OPENAI_API_KEY"]=key
    # No additional archive; same score/snapshot, candidate and V2R4 spec.
    baseline_raw,baseline_meta=checked("BASELINE_MODEL_CALL",evaluate.call_evaluator,c,current,base_context,spec,control)
    successor_raw,successor_meta=checked("SUCCESSOR_MODEL_CALL",evaluate.call_evaluator,c,current,enriched,spec,control)
    base=checked("BASELINE_NORMALIZATION",clean_decision,baseline_raw,current,base_context,spec)
    nextv=checked("SUCCESSOR_NORMALIZATION",clean_decision,successor_raw,current,enriched,spec)
    return {
      "kind":"V3_ONE_SHOT_SAME_SNAPSHOT_MODEL_COMPARISON_V1",
      "status":"ISOLATED_MODEL_PAIR_COMPLETE_NOT_A_PROFITABILITY_RESULT",
      "candidate_id":c["candidate_id"],"pair":c["pair"],
      "source_series_id":control["series_id"],
      "source_runtime_dir":runtime.name,
      "source_strategy_revision":control["strategy_revision"],
      "source_candidate_event_utc":c["event_time_utc"],
      "evidence_known_at_utc":entry["known_at_utc"],
      "model_snapshot_at_utc":observed_at,
      "same_candidate_same_ticker_same_standard_context":True,
      "coin_evidence_only_changed_input":True,
      "baseline_is_new_independent_replay_not_official_original_decision":True,
      "candidate_specific_features_ready":True,
      "frozen_evaluator_hashes":frozen_hashes,
      "baseline":base,"successor_with_coin_evidence":nextv,
      "baseline_response_id":baseline_meta.get("response_id"),
      "successor_response_id":successor_meta.get("response_id"),
      "model_calls":2,"paper_positions_created":0,"real_orders":0,
      "active_v2r4_changed":False,"active_h3_changed":False,
      "automatic_promotion":False,"valid_paper_trade_proven":False,
      "economic_edge_proven":False,
      "note":"Only a one-candidate input sensitivity experiment. BUY here is model suggestion, NOT prospective completed Paper trade or net edge."
    }


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--trading-root",type=Path,required=True)
    parser.add_argument("--code-root",type=Path,required=True)
    parser.add_argument("--expected-series-id",required=True)
    parser.add_argument("--diagnose-only",action="store_true",help="Read-only real candidate+public input diagnostics; no secret/model/order")
    args=parser.parse_args()
    try:
        r=execute_one_shot(args.trading_root,args.code_root,args.expected_series_id,diagnose_only=args.diagnose_only)
    except Exception as e:
        # Exclude raw exception strings: they may contain secrets/urls.
        r={"kind":"V3_ONE_SHOT_SAME_SNAPSHOT_MODEL_COMPARISON_V1",
           "status":"BLOCKED_PRECONDITION_OR_SOURCE",
           "failure_type":e.failure_type if isinstance(e,PreflightStageError) else type(e).__name__,
           "failure_phase":e.phase if isinstance(e,PreflightStageError) else "UNCLASSIFIED",
           "safe_reason":e.safe_reason if isinstance(e,PreflightStageError) else "UNCLASSIFIED",
           "model_calls":0 if args.diagnose_only else "UNVERIFIED_MAY_HAVE_STARTED",
           "secret_read":False if args.diagnose_only else "UNVERIFIED",
           "active_v2r4_changed":False,"real_orders":0}
    print(json.dumps(r,sort_keys=True))
    return 0 if r.get("status") in ("ISOLATED_MODEL_PAIR_COMPLETE_NOT_A_PROFITABILITY_RESULT", "INPUT_READY_NO_MODEL_CALLS_NOT_A_STRATEGY_PASS") else 2


if __name__=="__main__":
    raise SystemExit(main())
