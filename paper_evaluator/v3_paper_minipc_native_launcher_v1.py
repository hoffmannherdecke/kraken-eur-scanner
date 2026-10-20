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
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from tools.v3_experimental_paper_technical_gate import validate_experimental_paper_packet
from paper_evaluator.v3_paper_minipc_one_candidate_v1 import REVISION
from paper_evaluator.v3_paper_minipc_selective_tick_v1 import (
    released_paper_first_scanner_model_once,
    released_paper_followup_tick_once,
    released_paper_cloud_ack_once,
)

def _originalhost_wall_clock_utc() -> datetime:
    """Use actual UTC for a release readback, never the Paper test clock."""
    return datetime.now(timezone.utc)


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



def dispatch_after_native_release_readback(*,
        originalhost_readback: Callable[[], dict[str, Any]] | None = None,
        release_root: Path | None = None,
        release_packet: dict[str, Any] | None = None,
        **phase_args: Any) -> dict[str, Any]:
    """Source-only native-owner integration seam; NOT a Windows/Cloud release.

    The future separately authorized ORIGINALHOST operator must supply the
    trusted, freshly collected Windows Task/worker/fence/supervisor proof.
    A caller-created dictionary, CI mock or Cloud flag is NOT physical
    attestation. Six independently collected evidence envelopes must also pass
    the original strict release schema, but even that does not authenticate
    their physical origin without a separate actual release-owner readback. This function neither installs nor starts a Windows Task.
    The CLI below intentionally has NO live argument or execution path.

    On a complete external readback this delegates ONE phase to the exact
    existing locked native writer. That worker independently re-reads the
    active Cloud series while holding its original OS-native owner lock.
    """
    required = (
        "phase", "series_id", "repo_sha", "bundle_sha256",
        "strategy_sha256", "journal", "capture_dir",
        "model_reservations", "ack_file", "read_active_series",
    )
    if not callable(originalhost_readback) or any(
            key not in phase_args for key in required):
        raise ValueError("independent native owner and release inputs required")
    # Testing/replay clocks remain available to source-only phase unit tests,
    # but a RELEASED native host boundary may not accept an injected time.
    # Otherwise an old physical host readback could be made to look fresh.
    if "clock_now" in phase_args:
        raise ValueError("native originalhost boundary forbids injected clock override")
    validate_one_owner_contract(
        **{key: phase_args[key] for key in required})
    # Never turn a caller-provided six_proofs=True (or a Cloud config flag)
    # into release authority. Parse all six immutable, source-specific proof
    # envelopes with the EXISTING shared technical gate first. Their original
    # host/Cloud provenance must also be corroborated by the separate actual
    # release owner; successful schema/hashes are NOT physical attestation.
    if (not isinstance(release_root, Path) or release_root.is_symlink()
            or not release_root.is_dir()
            or not isinstance(release_packet, dict)
            or release_packet.get("strategy_revision") != REVISION
            or release_packet.get("strategy_fingerprint_sha256") !=
                phase_args["strategy_sha256"]):
        raise ValueError("pinned original technical release evidence missing")
    proof_errors = validate_experimental_paper_packet(
        release_root, REVISION, release_packet)
    if proof_errors:
        raise ValueError("six independent release proof envelopes incomplete: "
                         + proof_errors[0])
    # The independent originalhost task/process/fence and Cloud readbacks are
    # checked separately below and again under the existing native writer lock.
    phase = phase_args["phase"]
    series_id = phase_args["series_id"]
    pin = phase_args["repo_sha"]
    report = originalhost_readback()
    if not isinstance(report, dict):
        raise ValueError("original native host readback missing")
    expected = {
        "kind": "V3_NATIVE_ONE_OWNER_POST_CAS_ORIGINALHOST_READBACK_V1",
        "source": "ORIGINAL_MINIPC_WINDOWS_TASK_PROCESS_AND_FENCE",
        "task_name": "CryptoMiniPC-V3PaperSingleWriter",
        "task_state": "Running",
        "series_id": series_id,
        "release_repo_sha": pin,
        "old_candidates_task_state": "Disabled",
        "old_wait_task_state": "Disabled",
        "old_candidates_workers_absent": True,
        "old_wait_workers_absent": True,
        "v3_task_one_original_action_verified": True,
        "v3_worker_pinned_source_verified": True,
        "native_writer_owner_singleton_verified": True,
        "original_no_rearm_fence": "CLOUD_COMMITTED",
        "original_supervisor_no_rearm_ack": True,
        "old_lifecycle_task_running": True,
        "old_cloudsync_task_running": True,
        "independent_cloud_cas_committed": True,
        "six_external_original_e2e_proofs_approved": True,
        "paper_only": True,
        "real_money_actions": False,
    }
    if any(report.get(key) != value or type(report.get(key)) is not type(value)
           for key, value in expected.items()):
        raise ValueError("native V3 Paper task, fence, aftercare or release gate unverified")
    # No stale host assertion may authorize even the first public Kraken GET.
    try:
        seen = datetime.fromisoformat(
            report["observed_at_utc"].replace("Z", "+00:00"))
        current = _originalhost_wall_clock_utc()
        if (seen.tzinfo is None or seen.utcoffset() is None
                or current.tzinfo is None or current.utcoffset() is None
                or not 0 <= (current-seen).total_seconds() <= 90):
            raise ValueError("native originalhost release readback stale or future")
    except (KeyError, AttributeError, TypeError, OverflowError) as exc:
        raise ValueError("native originalhost readback timestamp invalid") from exc
    # No additional run loop, schedule, model call, Paper authority or Cloud
    # writer is introduced here; the existing worker locks and guards own it.
    return dispatch_one_owned_paper_phase(**phase_args)


# Reuse the ONE existing reviewed original Mini-PC inspection script. Its
# output is intentionally NOT a release proof: it cannot attest Cloud CAS,
# actual loaded module identity or the absence of other writer processes.
ORIGINALHOST_READONLY_SCRIPT = "tools/check-minipc-v3-physical-writer-readiness.ps1"
ORIGINALHOST_POWERSHELL = Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")
ORIGINALHOST_TRADING_ROOT = r"C:\Users\ADMIN\Trading"


def summarize_originalhost_readonly(report: dict[str, Any]) -> dict[str, Any]:
    """Expose a small, safe factual inventory; never mint release authority."""
    if not isinstance(report, dict) or report.get("kind") != (
            "V3_MINIPC_SINGLE_WRITER_PHYSICAL_READONLY_PREFLIGHT_V1"):
        raise ValueError("originalhost physical readonly report kind missing")
    local = report.get("physical_v3_postcas_local_inventory")
    if (not isinstance(local, dict) or local.get("kind") !=
            "V3_NATIVE_POSTCAS_LOCAL_INSPECTION_ONLY_V1"
            or local.get("status") != "NOT_INDEPENDENT_RELEASE_EVIDENCE"
            or local.get("live_paper_activation_authorized") is not False
            or local.get("tasks_changed") != 0
            or local.get("cloud_writes") != 0
            or local.get("model_calls") != 0
            or report.get("new_v3_writer_started") is not False
            or report.get("filesystem_writes") is not False
            or report.get("v2r4_changed") is not False
            or report.get("experimental_paper_release_authorized_by_this_check") is not False):
        raise ValueError("readonly host report claims unsupported authority or effects")
    state = local.get("native_task_state")
    if state not in ("Disabled", "Ready", "Running", "ABSENT", "UNKNOWN"):
        raise ValueError("unrecognized V3 native Task observation")
    return {
        "kind": "V3_NATIVE_ORIGINALHOST_DIAGNOSTIC_HANDOFF_V1",
        "status": "ORIGINALHOST_INVENTORY_ONLY_NO_RELEASE",
        "observed_at_utc": report.get("checked_at_utc"),
        "native_task_state": state,
        "native_task_uses_old_readonly_launcher":
            local.get("native_task_uses_old_readonly_launcher") is True,
        "old_intake_disabled_observed":
            local.get("old_intake_tasks_disabled") is True,
        "old_aftercare_running_observed":
            local.get("protected_old_aftercare_running") is True,
        "independent_cloud_cas_verified": False,
        "six_original_e2e_proofs_verified": False,
        "source_process_and_fence_authenticated": False,
        "runtime_bootstrap_executable": False,
        "paper_activated": False,
        "model_http_calls": 0,
        "orders": False,
        "windows_task_changes": False,
    }


def read_originalhost_readonly() -> dict[str, Any]:
    """Actual *read-only* Windows inventory, source-only until host deployment.

    No executable V3 writer or CAS/Task/Model side effect. The trusted future
    operator must still collect INDEPENDENT originalhost and Cloud proofs.
    """
    if sys.platform != "win32":
        raise ValueError("originalhost inspection requires the physical Windows host")
    source_root = Path(__file__).absolute().parent.parent
    script = source_root / ORIGINALHOST_READONLY_SCRIPT
    if (not script.is_file() or script.is_symlink()
            or not ORIGINALHOST_POWERSHELL.is_file()
            or ORIGINALHOST_POWERSHELL.is_symlink()):
        raise ValueError("fixed reviewed originalhost PowerShell source absent")
    try:
        result = subprocess.run([
            str(ORIGINALHOST_POWERSHELL), "-NoProfile", "-NonInteractive",
            "-File", str(script), "-TradingRoot", ORIGINALHOST_TRADING_ROOT,
        ], capture_output=True, text=True, timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("originalhost readonly inventory unavailable") from exc
    if (result.returncode != 0 or len(result.stdout) > 262144
            or not result.stdout.strip()):
        raise ValueError("originalhost readonly inventory failed or oversized")
    try:
        parsed = json.loads(result.stdout)
    except (ValueError, TypeError) as exc:
        raise ValueError("originalhost readonly inventory invalid JSON") from exc
    return summarize_originalhost_readonly(parsed)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inactive V3 Paper native-owner source -- no live execution")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--read-only", action="store_true")
    modes.add_argument("--originalhost-readonly", action="store_true")
    args = parser.parse_args()
    if args.originalhost_readonly:
        print(json.dumps(read_originalhost_readonly(), sort_keys=True))
        return 0
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
