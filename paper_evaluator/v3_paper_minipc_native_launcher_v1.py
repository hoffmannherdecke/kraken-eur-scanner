#!/usr/bin/env python3
"""Original V3 Paper one-shot owner dispatch -- SOURCE ONLY, NOT INSTALLED.

The ONE future native Windows Task will call this module after a separately
verified physical task/source/PID/old-aftercare release gate. All three phases
delegate to EXISTING release-pinned OS-native-lock functions; this module does
not create a task, second scanner/Cloud worker, Cloud CAS, loop or model permit.

The CLI deliberately offers only a pure source-only readiness description.
A CLI execution mode requires a future separately authorized host bootstrap
that independently verifies native Task/PID, old V2R4 no-rearm, six real E2E
proofs and active Cloud release. This source file does NOT create that proof.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Callable

from paper_evaluator.v3_paper_minipc_one_candidate_v1 import REVISION
from paper_evaluator.v3_paper_minipc_selective_tick_v1 import (
    released_paper_first_scanner_model_once,
    released_paper_followup_tick_once,
    released_paper_cloud_ack_once,
)

PHASES = ("FIRST_SCANNER_MODEL_P4", "FOLLOWUP_6H24H72H", "CLOUD_RECEIPT_ACK")
SERIES = re.compile(r"PAPER-V3-[0-9]{8}T[0-9]{6}Z")
REPO_SHA = re.compile(r"[0-9a-f]{40}")
FILE_SHA = re.compile(r"[0-9a-f]{64}")


def validate_one_owner_contract(*, phase: str, series_id: str,
        repo_sha: str, bundle_sha256: str, strategy_sha256: str,
        journal: Path, capture_dir: Path, model_reservations: Path,
        ack_file: Path, read_active_series: Callable) -> None:
    """Reject incomplete/wrong release inputs BEFORE invoking a worker.

    Strongest actual safety is still held in the ORIGINAL native locks and
    fresh active exact Supabase series readback inside each worker. This pure
    validation is NOT a substitute for physical Windows Task proof.
    """
    if (phase not in PHASES or not isinstance(series_id, str)
            or SERIES.fullmatch(series_id) is None
            or not isinstance(repo_sha, str) or REPO_SHA.fullmatch(repo_sha) is None
            or not isinstance(bundle_sha256, str)
            or FILE_SHA.fullmatch(bundle_sha256) is None
            or not isinstance(strategy_sha256, str)
            or FILE_SHA.fullmatch(strategy_sha256) is None
            or not callable(read_active_series)):
        raise ValueError("exact released non-CANARY single-owner identity required")
    paths = (journal, capture_dir, model_reservations)
    if (any(not isinstance(p, Path) or not p.is_dir() or p.is_symlink()
            for p in paths)
            or len({p.resolve() for p in paths}) != 3
            or not isinstance(ack_file, Path)
            or ack_file.is_symlink() or not ack_file.parent.is_dir()
            or ack_file.parent.is_symlink()
            or ack_file.parent.resolve() in {p.resolve() for p in paths}):
        raise ValueError("isolated preexisting Paper source/journal/budget/ACK roots required")


def dispatch_one_owned_paper_phase(*, phase: str,
        series_id: str, repo_sha: str, bundle_sha256: str,
        strategy_sha256: str, journal: Path, capture_dir: Path,
        model_reservations: Path, ack_file: Path,
        read_active_series: Callable[[str], dict[str, Any]],
        candidate: dict[str, Any] | None = None,
        preflight: dict[str, Any] | None = None,
        approval: dict[str, Any] | None = None,
        model_key: str | None = None,
        relay_token: str | None = None,
        clock_now: Callable | None = None,
        source_capture: Callable | None = None,
        source_acquire: Callable | None = None,
        model_client: Callable | None = None,
        existing_context: dict[str, Any] | None = None,
        source_fetch: Callable | None = None,
        source_ticker: Callable | None = None,
        cloud_post: Callable | None = None) -> dict[str, Any]:
    """Dispatch exactly ONE phase to its existing locked release-bound worker.

    The caller must independently verify actual Windows Task/PID ownership,
    the old V2R4 Candidate+WAIT stop fence, preserved Lifecycle/PR332 aftercare,
    and six authentic technical E2E proofs BEFORE invoking this function.
    Callable injection is for real integration/testing, not physical authority.
    No callback in this function can itself prove those host facts.
    """
    validate_one_owner_contract(
        phase=phase, series_id=series_id, repo_sha=repo_sha,
        bundle_sha256=bundle_sha256, strategy_sha256=strategy_sha256,
        journal=journal, capture_dir=capture_dir,
        model_reservations=model_reservations, ack_file=ack_file,
        read_active_series=read_active_series)
    common = dict(
        series_id=series_id, journal=journal,
        expected_repo_sha=repo_sha,
        expected_bundle_sha256=bundle_sha256,
        expected_strategy_sha256=strategy_sha256,
        read_active_series=read_active_series)
    if clock_now is not None:
        if not callable(clock_now):
            raise ValueError("invalid single owner clock")
        common["clock_now"] = clock_now

    if phase == "FIRST_SCANNER_MODEL_P4":
        if (not isinstance(candidate, dict)
                or not isinstance(preflight, dict)
                or not isinstance(approval, dict)
                or not isinstance(model_key, str)
                or relay_token is not None or cloud_post is not None
                or source_fetch is not None or source_ticker is not None):
            raise ValueError("first Scanner demands exact independent one-shot model approval")
        params = dict(common, preflight=preflight, candidate=candidate,
                      capture_dir=capture_dir, model_reservations=model_reservations,
                      approval=approval, model_key=model_key)
        if source_capture is not None: params["capture"] = source_capture
        if source_acquire is not None: params["acquire"] = source_acquire
        if model_client is not None: params["model_client"] = model_client
        if existing_context is not None: params["existing_context"] = existing_context
        return released_paper_first_scanner_model_once(**params)

    if phase == "FOLLOWUP_6H24H72H":
        if (not isinstance(candidate, dict) or preflight is not None
                or approval is not None or model_key is not None
                or relay_token is not None or cloud_post is not None
                or source_acquire is not None or model_client is not None
                or existing_context is not None):
            raise ValueError("followup cannot spend model or post Cloud")
        params = dict(common, candidate=candidate, capture_dir=capture_dir,
                      model_reservations=model_reservations, ack_file=ack_file)
        if source_capture is not None: params["capture"] = source_capture
        if source_fetch is not None: params["fetch"] = source_fetch
        if source_ticker is not None: params["ticker"] = source_ticker
        return released_paper_followup_tick_once(**params)

    # The only remaining phase is original locked Cloud ACK.
    if (candidate is not None or preflight is not None
            or approval is not None or model_key is not None
            or not isinstance(relay_token, str) or len(relay_token) < 24
            or any(x is not None for x in (
                source_capture, source_acquire, model_client,
                existing_context, source_fetch, source_ticker))):
        raise ValueError("Cloud ACK cannot source market or spend model")
    params = dict(common, ack_file=ack_file, token=relay_token)
    if cloud_post is not None: params["cloud_post"] = cloud_post
    return released_paper_cloud_ack_once(**params)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inactive V3 Paper native-owner source -- no live execution")
    parser.add_argument("--read-only", action="store_true")
    args = parser.parse_args()
    if not args.read_only:
        parser.error("No live Mini-PC owner Task, original fence or Cloud CAS is installed")
    print(json.dumps({
        "kind": "V3_PAPER_NATIVE_OWNER_ONE_SHOT_SOURCE_PLAN_V1",
        "status": "SOURCE_DISPATCH_READY_RUNTIME_NOT_AUTHORIZED",
        "revision": REVISION, "phases": list(PHASES),
        "native_windows_task_installed": False,
        "originalhost_source_pins_verified": False,
        "independent_six_e2e_proofs_verified": False,
        "cloud_cas_performed": False, "v3_paper_activated": False,
        "model_http_calls": 0, "task_changes": False,
        "orders": False, "real_money_actions": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
