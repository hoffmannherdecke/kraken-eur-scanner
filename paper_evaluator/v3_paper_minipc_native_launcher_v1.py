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
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from tools.v3_experimental_paper_technical_gate import (
    assess_v3_native_source_import_closure, validate_experimental_paper_packet,
)
from paper_evaluator.v3_paper_minipc_one_candidate_v1 import REVISION
from paper_evaluator.v3_paper_cloud_receipt_sync_v1 import read_active_paper_series
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
    # Proof-file integrity is insufficient when that valid packet describes
    # a different bundle from the exact runtime about to execute. The
    # external host approval and real Cloud series must pin this SAME code.
    if release_packet.get("code_fingerprint_sha256") != phase_args["bundle_sha256"]:
        raise ValueError("six-proof release packet code fingerprint differs from worker bundle")
    # The independently authenticated originalhost release owner MUST have
    # reviewed the exact same six-proof packet, not a different packet for
    # the same series/repository. The packet's individual files/hashes were
    # verified above by the ONE existing technical gate. This is identity
    # correlation only; its self-hash does not authenticate physical origin.
    try:
        packet_bytes = json.dumps(
            release_packet, sort_keys=True, separators=(",", ":"),
            allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError("native release packet cannot be canonically hashed") from exc
    if not 0 < len(packet_bytes) <= 65536:
        raise ValueError("native release packet size invalid")
    expected_release_packet_sha256 = hashlib.sha256(packet_bytes).hexdigest()
    # The independent originalhost task/process/fence and Cloud readbacks are
    # checked separately below and again under the existing native writer lock.
    phase = phase_args["phase"]
    series_id = phase_args["series_id"]
    pin = phase_args["repo_sha"]
    report = originalhost_readback()
    if not isinstance(report, dict):
        raise ValueError("original native host readback missing")
    if (not isinstance(report.get("approved_six_proof_release_packet_sha256"), str)
            or report["approved_six_proof_release_packet_sha256"]
                != expected_release_packet_sha256):
        raise ValueError("independent originalhost approved different six-proof release packet")
    expected = {
        "kind": "V3_NATIVE_ONE_OWNER_POST_CAS_ORIGINALHOST_READBACK_V1",
        "source": "ORIGINAL_MINIPC_WINDOWS_TASK_PROCESS_AND_FENCE",
        "task_name": "CryptoMiniPC-V3PaperSingleWriter",
        "task_state": "Running",
        "series_id": series_id,
        "release_repo_sha": pin,
        # A matching Git commit alone cannot prove this Windows process
        # actually runs the same pinned source bundle and strategy reviewed
        # in the independent external six-proof release packet. These must
        # come from independent ORIGINALHOST bytes/source observations.
        "release_bundle_sha256": phase_args["bundle_sha256"],
        "release_strategy_sha256": phase_args["strategy_sha256"],
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
    # Maintenance belongs to the already required original MINIPC physical
    # supervisor/stop-start/source release proof, not a seventh technical
    # proof. The final V3 Paper phase may never accept a PRE-MAINTENANCE
    # host report, even if old six-proof/Cloud fields appear positive.
    # The original release owner must independently corroborate the actual
    # maintenance receipt, restored V2R4 operation, source/SHA, Windows
    # readiness, and its physical origin. A client-made dict is not authority.
    # UPS/USV is optional hardware resilience, not a Paper release precondition.
    maintenance_fields = (
        "maintenance_cpu_bios_boot_thermal_originalhost_pass",
        "maintenance_windows_drivers_reboots_originalhost_pass",
        "maintenance_scripts_originalhost_source_ack_pass",
        "maintenance_v2r4_restart_and_aftercare_originalhost_pass",
    )
    if (any(report.get(key) is not True or type(report.get(key)) is not bool
            for key in maintenance_fields)
            or report.get("maintenance_release_repo_sha") != pin
            or report.get("maintenance_receipt_kind") !=
                "V3_EXISTING_MINIPC_MAINTENANCE_ORIGINALHOST_ACK_V1"
            or not isinstance(report.get("maintenance_receipt_sha256"), str)
            or not FILE_SHA.fullmatch(report["maintenance_receipt_sha256"])):
        raise ValueError("final V3 Paper activation blocked until physical maintenance and script acceptance")
    # Both observations use real clock; maintenance may precede the runtime
    # report but cannot claim to occur after it. An already edited SHA is not
    # a current executable source acknowledgement.
    try:
        maintained = datetime.fromisoformat(
            report["maintenance_completed_at_utc"].replace("Z", "+00:00"))
        observed = datetime.fromisoformat(
            report["observed_at_utc"].replace("Z", "+00:00"))
        if (maintained.tzinfo is None or maintained.utcoffset() is None
                or observed.tzinfo is None or observed.utcoffset() is None
                or maintained > observed):
            raise ValueError("maintenance receipt time missing or after originalhost readback")
    except (KeyError, AttributeError, TypeError, OverflowError) as exc:
        raise ValueError("originalhost maintenance time invalid") from exc

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


def dispatch_after_originalhost_and_cloud_readback(*,
        originalhost_readback: Callable[[], dict[str, Any]] | None = None,
        release_root: Path | None = None,
        release_packet: dict[str, Any] | None = None,
        original_cloud_relay_token: str | None = None,
        **phase_args: Any) -> dict[str, Any]:
    """Use the ORIGINAL authenticated relay for the native locked phase.

    This is an integration function, NOT a separately installed CLI or an
    original Windows proof provider. The caller must independently establish
    the actual Windows Task/PID/fence and approved original six-proof packet.
    The existing phase worker re-reads Cloud *inside its native owner lock*.
    No caller-supplied Cloud readback or transport can become release authority.
    """
    if (not isinstance(original_cloud_relay_token, str)
            or not 24 <= len(original_cloud_relay_token) <= 512
            or any(ch.isspace() for ch in original_cloud_relay_token)):
        raise ValueError("original authenticated V3 Cloud relay token missing")
    # No cloud_callback, alternate relay URL or fake transport can be supplied
    # to this future production-bound entry. Stubs belong to isolated tests.
    prohibited = ("read_active_series", "cloud_post", "relay_token",
                  "clock_now", "model_client", "source_capture",
                  "source_acquire", "source_fetch", "source_ticker")
    if any(name in phase_args for name in prohibited):
        raise ValueError("caller-injected V3 owner, clock or Cloud transport forbidden")
    phase = phase_args.get("phase")
    if phase not in PHASES:
        raise ValueError("exact original V3 Paper phase required")

    # The released entry obtains ONE externally verified originalhost report
    # before the actual worker acquires its native OS lock. That same report
    # must still be fresh AFTER the authenticated Cloud relay returns under
    # that lock. The separate read-only PR468/469 diagnostic cannot confer
    # this authority or protect the execution path on its own.
    observed_host_stamp: datetime | None = None

    def captured_originalhost_readback() -> dict[str, Any]:
        nonlocal observed_host_stamp
        if observed_host_stamp is not None:
            raise ValueError("originalhost release readback repeated")
        if not callable(originalhost_readback):
            raise ValueError("independent originalhost release provider absent")
        report = originalhost_readback()
        if not isinstance(report, dict):
            raise ValueError("native release originalhost report missing")
        try:
            seen = datetime.fromisoformat(
                report["observed_at_utc"].replace("Z", "+00:00"))
        except (KeyError, AttributeError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("native release originalhost clock invalid") from exc
        if seen.tzinfo is None or seen.utcoffset() is None:
            raise ValueError("native release originalhost clock lacks timezone")
        observed_host_stamp = seen
        return report

    def original_cloud_readback(series_id: str) -> dict[str, Any]:
        # The pre-existing Edge relay authenticates its request and reads
        # the actual active Paper series. Its config is independently checked
        # by _require_released_paper_cloud inside the original worker lock.
        if observed_host_stamp is None:
            raise ValueError("originalhost release missing before locked Cloud read")
        reply = read_active_paper_series(
            series_id=series_id, token=original_cloud_relay_token)
        # No second relay call or standalone timer. PR468's real post-relay
        # clock principle is applied at the *actual* native phase boundary,
        # where a slow response could otherwise outlive the prior 90s host
        # approval while leaving the worker Cloud sample fresh.
        now = _originalhost_wall_clock_utc()
        if (now.tzinfo is None or now.utcoffset() is None
                or not 0 <= (now - observed_host_stamp).total_seconds() <= 90):
            raise ValueError("native release originalhost stale after Cloud relay")
        return reply

    # Only the original Cloud ACK worker receives its existing relay token.
    # The other phases are never allowed to perform a Cloud POST here.
    if phase == "CLOUD_RECEIPT_ACK":
        phase_args["relay_token"] = original_cloud_relay_token
    return dispatch_after_native_release_readback(
        originalhost_readback=captured_originalhost_readback,
        release_root=release_root,
        release_packet=release_packet,
        read_active_series=original_cloud_readback,
        **phase_args)


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
        # Observed exact native Windows bytes are only a future pin comparison
        # input. A file SHA neither proves the loaded Python process nor CAS.
        "native_task_action_sha256":
            local.get("native_task_action_sha256")
            if isinstance(local.get("native_task_action_sha256"), str)
            and FILE_SHA.fullmatch(local["native_task_action_sha256"])
            else None,
        "native_task_launcher_file_sha256":
            local.get("native_task_launcher_file_sha256")
            if isinstance(local.get("native_task_launcher_file_sha256"), str)
            and FILE_SHA.fullmatch(local["native_task_launcher_file_sha256"])
            else None,
        "native_task_loaded_module_independently_verified": False,
        "native_python_parent_process_observed":
            local.get("native_python_parent_process_observed") is True,
        "native_python_parent_matches_task_action_hint":
            local.get("native_python_parent_matches_task_action_hint") is True,
        "native_python_parent_pid":
            local.get("native_python_parent_pid")
            if type(local.get("native_python_parent_pid")) is int
            and 0 < local["native_python_parent_pid"] < 2147483648 else None,
        "native_python_parent_started_at_utc":
            local.get("native_python_parent_started_at_utc")
            if isinstance(local.get("native_python_parent_started_at_utc"), str)
            and len(local["native_python_parent_started_at_utc"]) <= 40 else None,
        "native_powershell_process_token_is_system":
            local.get("native_powershell_process_token_is_system") is True,
        "native_runtime_identity_independently_verified": False,
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
            # Windows host policy denies ordinary .ps1 execution. A single
            # child-process-only override permits this exact reviewed
            # original read-only inspection without changing system/user
            # policy or touching Windows Task configuration.
            "-ExecutionPolicy", "Bypass",
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




def _read_only_snapshot_time(value: Any, *, source: str,
                             now: datetime) -> datetime:
    """Require real, bounded timestamps without granting release authority.

    Diagnostics have a wider 180s read window than the hard 90s actual
    native release gate: two sequential physical host+relay calls can take
    time. A 10s future tolerance is clock-skew diagnostics ONLY.
    """
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError(source + " read-only snapshot timestamp invalid")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError) as exc:
        raise ValueError(source + " read-only snapshot timestamp invalid") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError(source + " read-only snapshot timestamp lacks timezone")
    age = (now - stamp).total_seconds()
    if not -10 <= age <= 180:
        raise ValueError(source + " read-only snapshot stale or future")
    return stamp


def _require_one_loaded_release_module_root() -> None:
    """Reject imported V3 core modules from another directory BEFORE Paper.

    This is local runtime SOURCE-CONSISTENCY only, not independent proof of
    executed Python bytecode, external Windows Task identity or physical CAS.
    The authoritative originalhost release owner must still attest those.
    """
    source = Path(__file__).absolute()
    root = source.parent.parent
    if (not source.is_file() or source.is_symlink()
            or not root.is_dir() or root.is_symlink()
            or source.parent.is_symlink()):
        raise ValueError("native V3 launcher staged source not regular")
    modules = (
        ("paper_evaluator.v3_paper_minipc_one_candidate_v1",
         "paper_evaluator/v3_paper_minipc_one_candidate_v1.py"),
        ("paper_evaluator.v3_paper_minipc_selective_tick_v1",
         "paper_evaluator/v3_paper_minipc_selective_tick_v1.py"),
        ("paper_evaluator.v3_paper_cloud_receipt_sync_v1",
         "paper_evaluator/v3_paper_cloud_receipt_sync_v1.py"),
        ("tools.v3_experimental_paper_technical_gate",
         "tools/v3_experimental_paper_technical_gate.py"),
    )
    for name, relative in modules:
        module = sys.modules.get(name)
        target = root / relative
        origin = getattr(getattr(module, "__spec__", None), "origin", None)
        path = getattr(module, "__file__", None)
        if (module is None or not isinstance(origin, str)
                or not isinstance(path, str)
                or not target.is_file() or target.is_symlink()
                or target.parent.is_symlink()):
            raise ValueError("native V3 core module source unavailable: " + name)
        # Original import path AND Python import-spec origin must both be the
        # exact existing file within this launcher's single staged root.
        # Never derive a release path from argv, env, user JSON or sys.path.
        if (Path(path).absolute() != target.absolute()
                or Path(origin).absolute() != target.absolute()):
            raise ValueError("native V3 mixed-vintage core module origin: " + name)


def _require_staged_v3_source_manifest(*, repo_sha: str, stage_root: Path | None = None) -> None:
    """Recheck the ONE original pinned inactive stage before a released phase.

    Exact staged file bytes, plus the existing native static import closure,
    must match the original stage manifest and externally approved repo SHA.
    This is a local *source* consistency check, not evidence of loaded Python
    bytecode, independent host provenance, six E2Es, CAS, or Paper authority.
    A caller cannot pass a stage root through the production native entry.
    """
    if not isinstance(repo_sha, str) or REPO_SHA.fullmatch(repo_sha) is None:
        raise ValueError("native staged source requires exact approved repo SHA")
    root = stage_root if stage_root is not None else Path(__file__).absolute().parent.parent
    if (not isinstance(root, Path) or root.is_symlink()
            or getattr(root, "is_junction", lambda: False)()
            or not root.is_dir()
            or root.name != "V3Paper-INACTIVE-" + repo_sha[:12]
            or root.parent.name != "Staging"
            or root.parent.is_symlink()
            or getattr(root.parent, "is_junction", lambda: False)()):
        raise ValueError("native source not in exact original inactive stage")
    marker = root / "v3-paper-inactive-source-manifest.json"
    if marker.is_symlink() or not marker.is_file() or marker.stat().st_size > 131072:
        raise ValueError("native source stage manifest missing or unsafe")
    try:
        manifest = json.loads(marker.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError, OSError) as exc:
        raise ValueError("native source stage manifest invalid") from exc
    if (not isinstance(manifest, dict)
            or manifest.get("kind") != "V3_PAPER_INACTIVE_ISOLATED_SOURCE_STAGE_V1"
            or manifest.get("status") != "STAGED_INACTIVE_CODE_ONLY_NOT_INSTALLED"
            or manifest.get("source_git_sha") != repo_sha
            or manifest.get("v3_paper_activated") is not False
            or manifest.get("task_changes") is not False
            or manifest.get("source_closure_is_only_candidate_not_loaded_code_ack") is not True):
        raise ValueError("native staged source identity or inactivity assertion drift")
    rows = manifest.get("source_manifest")
    if (not isinstance(rows, list) or not 20 <= len(rows) <= 350
            or type(manifest.get("tracked_code_files")) is not int
            or manifest["tracked_code_files"] != len(rows)):
        raise ValueError("native stage source file inventory invalid")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("native staged source row invalid")
        rel, digest = row.get("relative_path"), row.get("sha256")
        if (not isinstance(rel, str) or len(rel) > 180
                or re.fullmatch(r"[A-Za-z0-9_./-]+", rel) is None
                or rel.startswith("/") or "//" in rel
                or ".." in Path(rel).parts or rel in seen
                or not isinstance(digest, str) or FILE_SHA.fullmatch(digest) is None):
            raise ValueError("native staged source path/digest unsafe or duplicated")
        seen.add(rel)
        target = root / rel
        if not target.is_file() or target.is_symlink():
            raise ValueError("native staged source file absent or linked: " + rel)
        parent = target.parent
        while parent != root:
            if (parent == parent.parent or not parent.is_dir()
                    or parent.is_symlink()
                    or getattr(parent, "is_junction", lambda: False)()):
                raise ValueError("native staged source parent linked or outside")
            parent = parent.parent
        try:
            if target.stat().st_size > 524288 or (
                    hashlib.sha256(target.read_bytes()).hexdigest() != digest):
                raise ValueError("native staged source byte drift: " + rel)
        except OSError as exc:
            raise ValueError("native staged source unreadable: " + rel) from exc
    required = {
        "paper_evaluator/v3_paper_minipc_native_launcher_v1.py",
        "paper_evaluator/v3_paper_minipc_one_candidate_v1.py",
        "paper_evaluator/v3_paper_minipc_selective_tick_v1.py",
        "paper_evaluator/v3_paper_cloud_receipt_sync_v1.py",
        "tools/v3_experimental_paper_technical_gate.py",
        "tools/paper_series_transition_guard.py",
        "research/v3/v3-experimental-paper-all-lessons-bundle-20261011.json",
    }
    closure_files = manifest.get("static_transitive_closure_files")
    if (not required.issubset(seen) or not isinstance(closure_files, list)
            or not 20 <= len(closure_files) <= 512
            or not all(isinstance(rel, str) for rel in closure_files)
            or len(closure_files) != len(set(closure_files))
            or not set(closure_files).issubset(seen)
            or type(manifest.get("static_transitive_closure_file_count")) is not int
            or manifest["static_transitive_closure_file_count"] != len(closure_files)
            or not isinstance(manifest.get("static_transitive_closure_sha256"), str)
            or FILE_SHA.fullmatch(manifest["static_transitive_closure_sha256"]) is None):
        raise ValueError("native staged transitive closure inventory incomplete")
    # Reuse the original AST transitive-import checker, not a second source
    # dependency engine or a self-attesting release signature.
    closure = assess_v3_native_source_import_closure(root)
    if (closure.get("static_local_import_closure_complete") is not True
            or closure.get("candidate_transitive_source_sha256")
                != manifest["static_transitive_closure_sha256"]
            or closure.get("candidate_transitive_file_count") != len(closure_files)
            or {item[0] for item in closure.get("candidate_transitive_files", [])}
                != set(closure_files)):
        raise ValueError("native staged source closure changed after staging")


def _observed_originalhost_parent_identity(report: dict[str, Any]) -> tuple[int, datetime]:
    """OS PID and birth observed separately; does NOT attest loaded modules."""
    if not isinstance(report, dict):
        raise ValueError("originalhost Task/PID/source parent report missing")
    pid = report.get("native_python_parent_pid")
    born = report.get("native_python_parent_started_at_utc")
    if (type(pid) is not int or not 0 < pid < 2147483648
            or not isinstance(born, str) or not 10 <= len(born) <= 40):
        raise ValueError("originalhost Task/PID/source parent identity missing")
    try:
        started = datetime.fromisoformat(born.replace("Z", "+00:00"))
    except (ValueError, OverflowError) as exc:
        raise ValueError("originalhost Task/PID/source parent birth invalid") from exc
    if started.tzinfo is None or started.utcoffset() is None:
        raise ValueError("originalhost Task/PID/source parent birth without timezone")
    return pid, started.astimezone(timezone.utc)


def _require_running_originalhost_source_hint(report: dict[str, Any]) -> None:
    """Correlate *read-only hints* to this launched source; never grant a release.

    The original Windows inspector collects Task action / parent PID / SYSTEM
    observations independently of Python's caller. A matching file digest
    means only that the current launcher bytes equal the inspected Task file:
    it cannot attest the loaded Python module, prevent other native writers,
    prove Cloud CAS, or replace the signed external release-owner gate.
    """
    if not isinstance(report, dict) or report.get("status") != (
            "ORIGINALHOST_INVENTORY_ONLY_NO_RELEASE"):
        raise ValueError("originalhost Task/PID/source diagnostic missing")
    source_file = Path(__file__).absolute()
    try:
        if not source_file.is_file() or source_file.is_symlink():
            raise ValueError("originalhost running launcher is not a regular file")
        local_sha = hashlib.sha256(source_file.read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError("originalhost running launcher bytes unavailable") from exc
    conditions = (
        report.get("native_task_state") == "Running",
        report.get("native_task_uses_old_readonly_launcher") is False,
        report.get("native_python_parent_process_observed") is True,
        report.get("native_python_parent_matches_task_action_hint") is True,
        report.get("native_powershell_process_token_is_system") is True,
        isinstance(report.get("native_task_action_sha256"), str)
        and FILE_SHA.fullmatch(report["native_task_action_sha256"]) is not None,
        report.get("native_task_launcher_file_sha256") == local_sha,
    )
    if not all(conditions):
        raise ValueError("originalhost Task/PID/source read-only correlation failed")
    _observed_originalhost_parent_identity(report)


def dispatch_from_original_windows_one_shot(*,
        originalhost_release_readback: Callable[[], dict[str, Any]] | None = None,
        release_root: Path | None = None,
        release_packet: dict[str, Any] | None = None,
        original_cloud_relay_token: str | None = None,
        **phase_args: Any) -> dict[str, Any]:
    """Windows-only handoff to the ONE existing native V3 Paper dispatcher.

    First observe the running original Task, SYSTEM/Python parent and exact
    on-disk launcher bytes with the already reviewed originalhost PowerShell
    script. These are independent OBSERVATIONS, not proof of release or of
    the loaded module. A separate physical release owner MUST supply the
    authenticated post-CAS Task/fence/maintenance/six-proof readback callback;
    its provenance cannot be manufactured by this Python adapter.

    Intentionally NOT bound to CLI until the external physical release-owner
    evidence source and disabled Windows Task action have been accepted in the
    user-approved maintenance/final release. No caller-made JSON, environment
    boolean, temporary signature or Task hint becomes that provider here.
    This function registers no Tasks and performs no CAS, model or order itself.
    """
    # Never permit the local Windows diagnostic to stand in for external
    # release authority. On the current originalhost that provider does NOT
    # exist, so calls without it fail before even starting the PowerShell
    # read-only inspection.
    if sys.platform != "win32":
        raise ValueError("native V3 one-shot requires original Windows host")
    if not callable(originalhost_release_readback):
        raise ValueError("independent native originalhost release owner unavailable")
    # Exact source-only native phase parameters still must be screened before
    # any Windows process probe or potential Cloud work. The only actual
    # Cloud callback is installed by dispatch_after_originalhost_and_cloud_readback.
    if (phase_args.get("phase") not in PHASES
            or not isinstance(phase_args.get("series_id"), str)
            or SERIES.fullmatch(phase_args["series_id"]) is None
            or any(key in phase_args for key in (
                "read_active_series", "cloud_post", "relay_token",
                "clock_now", "model_client", "source_capture",
                "source_acquire", "source_fetch", "source_ticker"))):
        raise ValueError("native one-shot phase or injected source invalid")
    # A valid Task Action and on-disk launcher are insufficient if Python has
    # imported core modules from a different checkout or stale stage.
    _require_one_loaded_release_module_root()
    observed = read_originalhost_readonly()
    _require_running_originalhost_source_hint(observed)
    observed_parent = _observed_originalhost_parent_identity(observed)
    # The existing originalhost PowerShell inspector is a CHILD of the
    # current native launcher Python process. A separate Python process
    # can observe a genuine running V3 Task and reproduce the same source
    # hashes, but MUST NOT borrow that Task's PID/release identity. Bind
    # the independently re-read Windows parent PID to our actual OS PID
    # before requesting any external release approval, Cloud or Paper work.
    # This is process correlation ONLY, not the independent physical
    # release owner, actual loaded-byte proof or six real E2Es.
    if (type(observed_parent[0]) is not int
            or observed_parent[0] != os.getpid()):
        raise ValueError("native originalhost inspector parent is not invoking Python")
    # A local Task/source observation and a valid external release receipt
    # must refer to the SAME Task action and pinned on-disk launcher bytes.
    # Treating them as independent unrelated "green" checks would allow
    # two different source vintages to be combined for one release attempt.
    observed_now = _originalhost_wall_clock_utc()
    observed_stamp = _read_only_snapshot_time(
        observed.get("observed_at_utc"), source="original Windows Task",
        now=observed_now)
    if not 0 <= (observed_now - observed_stamp).total_seconds() <= 90:
        raise ValueError("native original Windows Task observation stale or future")

    def same_originalhost_release_readback() -> dict[str, Any]:
        independent = originalhost_release_readback()
        if not isinstance(independent, dict):
            raise ValueError("independent originalhost release readback missing")
        # Both fingerprints are supplied by the external release owner,
        # NOT copied into its dictionary from the local diagnostic.
        # The native release gate separately checks that owner's physical
        # authenticity, Task state, six proofs, maintenance and Cloud CAS.
        for key in ("native_task_action_sha256",
                    "native_task_launcher_file_sha256"):
            if (not isinstance(independent.get(key), str)
                    or FILE_SHA.fullmatch(independent[key]) is None
                    or independent[key] != observed.get(key)):
                raise ValueError("independent originalhost Task/source fingerprint mismatch")
        # A Task action and on-disk launcher can outlive a restarted Python
        # process. The external owner must independently observe the same
        # OS parent PID AND OS creation time (a PID by itself may be reused).
        if _observed_originalhost_parent_identity(independent) != observed_parent:
            raise ValueError("independent originalhost PID/creation identity mismatch")
        release_stamp = _read_only_snapshot_time(
            independent.get("observed_at_utc"), source="independent release",
            now=_originalhost_wall_clock_utc())
        if abs((release_stamp - observed_stamp).total_seconds()) > 90:
            raise ValueError("originalhost Task and release observations do not overlap")
        # Mandatory local stage-version byte check immediately before the
        # separately authenticated actual phase, not a new release owner.
        _require_staged_v3_source_manifest(repo_sha=phase_args["repo_sha"])
        return independent

    # The actual native release path independently enforces the stricter
    # current 90-second originalhost report at the worker boundary, including
    # after the single locked authenticated Cloud read (PR470). This wrapper
    # compares observations; it does NOT certify loaded PID/module identity
    # or mint an external release authority from local host flags.
    return dispatch_after_originalhost_and_cloud_readback(
        originalhost_readback=same_originalhost_release_readback,
        release_root=release_root, release_packet=release_packet,
        original_cloud_relay_token=original_cloud_relay_token,
        **phase_args)


def preflight_native_windows_one_shot(*,
        proposed_v3_series: str | None = None,
        expected_repo_sha: str | None = None) -> dict[str, Any]:
    """Join original Windows inventory and original Cloud relay read-only.

    The authenticated relay is queried ONLY when a specific exact future
    non-CANARY V3 series was supplied. Its token is read from an existing
    environment secret, NEVER a command-line argument or JSON report.
    Neither observation proves maintenance, loaded PID, committed CAS,
    six genuine E2E release proofs, or user approval. No worker is invoked.
    """
    if proposed_v3_series is not None and (
            not isinstance(proposed_v3_series, str)
            or SERIES.fullmatch(proposed_v3_series) is None):
        raise ValueError("exact non-CANARY proposed V3 Paper series required")
    # Bounded original source-only acceptance: same ONE manifest verifier as
    # the future released native phase. No CLI-supplied path or untrusted pin
    # is ever allowed to substitute for independently approved release SHA.
    if expected_repo_sha is not None:
        _require_staged_v3_source_manifest(repo_sha=expected_repo_sha)
    physical = read_originalhost_readonly()
    cloud = None
    if proposed_v3_series is not None:
        # Verify independently observed time BEFORE spending a relay call.
        # The existing real release owner still requires its stricter 90s
        # originalhost readback INSIDE the native phase boundary.
        physical_stamp = _read_only_snapshot_time(
            physical.get("observed_at_utc"), source="originalhost",
            now=_originalhost_wall_clock_utc())
        # Only the original installed running Task and its observed SYSTEM
        # parent/Action/current launcher SHA may participate in a paired
        # Cloud diagnostic. Caller-controlled reports and stale disabled
        # --read-only staging must not resemble a running native owner.
        _require_running_originalhost_source_hint(physical)
        token = os.environ.get("V3_PAPER_RELAY_TOKEN")
        if (not isinstance(token, str) or not 24 <= len(token) <= 512
                or any(ch.isspace() for ch in token)):
            raise ValueError("original V3 Cloud readback credential unavailable")
        # Reuse the ONE existing authenticated read-only relay; it requires
        # an active exact series. A denied/unknown Cloud state fails closed.
        # This is a POST transport but only its read_active_paper_series action.
        # Do not include the returned config, relay token or raw URL in output.
        reply = read_active_paper_series(series_id=proposed_v3_series,
                                         token=token)
        if (not isinstance(reply, dict)
                or reply.get("series_id") != proposed_v3_series
                or reply.get("status") != "active"
                or reply.get("strategy_revision") != REVISION
                or not isinstance(reply.get("observed_at_utc"), str)):
            raise ValueError("exact authenticated original Cloud series not accepted")
        # A slow relay may outlive a once-fresh originalhost sample.
        # Recheck BOTH observations against the SAME real post-relay UTC
        # instant, not just their mutual timestamps or pre-relay freshness.
        # This remains diagnostic only; real release still requires the
        # separate stricter 90-second native originalhost gate.
        relay_finished_at = _originalhost_wall_clock_utc()
        _read_only_snapshot_time(
            physical["observed_at_utc"], source="originalhost post-relay",
            now=relay_finished_at)
        cloud_stamp = _read_only_snapshot_time(
            reply["observed_at_utc"], source="authenticated Cloud",
            now=relay_finished_at)
        if abs((cloud_stamp - physical_stamp).total_seconds()) > 180:
            raise ValueError("originalhost and Cloud observations do not correlate")
        cloud = {
            "kind": "V3_ORIGINAL_RELAY_ACTIVE_SERIES_READONLY_OBSERVATION_V1",
            "series_id": proposed_v3_series,
            "strategy_revision": REVISION,
            "observed_at_utc": reply["observed_at_utc"],
            "authenticated_cloud_read_only_observed": True,
            "temporal_pair_checked_read_only": True,
            "cloud_cas_independently_proven": False,
            "physical_release_proofs_credited": 0,
        }
    # read_originalhost_readonly already rejects incorrectly shaped/unsafe
    # reports. Its factual hints cannot mint independent release authority.
    return {
        "kind": "V3_NATIVE_WINDOWS_ONE_SHOT_PREFLIGHT_V1",
        "status": "BLOCKED_PENDING_MAINTENANCE_AND_ORIGINAL_RELEASE",
        "diagnostic": physical,
        "cloud_readonly_observation": cloud,
        "cloud_readback_requested": proposed_v3_series is not None,
        "staged_source_manifest_sha256_rechecked_read_only":
            expected_repo_sha is not None,
        "staged_source_sha_is_only_local_source_identity": True,
        "actual_loaded_python_bytecode_independently_verified": False,
        "originalhost_task_process_source_correlated_read_only":
            proposed_v3_series is not None,
        "phase_names": list(PHASES),
        "existing_native_release_entrypoint":
            "dispatch_after_originalhost_and_cloud_readback",
        "premaintenance_activation_allowed": False,
        "independent_task_pid_and_source_ack": False,
        "six_real_technical_e2e_proofs_accepted": False,
        "physical_maintenance_and_script_ack_accepted": False,
        "actual_v3_cloud_cas_committed": False,
        "one_shot_worker_invoked": False,
        "model_http_calls": 0,
        "cloud_writes": 0,
        "windows_task_changes": False,
        "v2r4_changed": False,
        "v3_paper_activated": False,
        "orders": False,
        "real_money_actions": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inactive V3 Paper native-owner source -- no live execution")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--read-only", action="store_true")
    modes.add_argument("--originalhost-readonly", action="store_true")
    # This is executable on the original Windows host but NEVER live Paper.
    # The only released phase entry remains separately owner-authenticated.
    modes.add_argument("--one-shot-preflight", action="store_true")
    parser.add_argument("--proposed-v3-series", default=None)
    parser.add_argument("--expected-source-sha", default=None)
    args = parser.parse_args()
    if ((args.proposed_v3_series is not None or
         args.expected_source_sha is not None) and not args.one_shot_preflight):
        parser.error("--proposed-v3-series and --expected-source-sha require --one-shot-preflight")
    if args.one_shot_preflight:
        print(json.dumps(preflight_native_windows_one_shot(
            proposed_v3_series=args.proposed_v3_series,
            expected_repo_sha=args.expected_source_sha), sort_keys=True))
        return 0
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
