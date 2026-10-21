#!/usr/bin/env python3
"""One-shot PRE-CAS originalhost offline BUY/REJECT witness; never a Paper release.

This is a narrowly scoped proof adapter for the EXISTING V3 one_candidate,
native owner lock, immutable journal, and existing Cloud relay. It is neither
a second writer nor a task/runner/daemon. Model, Kraken and HTTP are all stubs.
The output is a *test fixture*, NOT a genuine market entry or six-gate proof.
An independent authenticated relay sync + readback remains a separate step.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
from datetime import datetime
import re
import socket
import subprocess
import sys
from unittest import mock
from urllib import request

HEX40 = re.compile(r"[0-9a-f]{40}\Z")
REVISION = "V3-EXPERIMENTAL-PAPER-20261011-ALL-LESSONS-001"


def _git(source: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(source), *args],
                          capture_output=True, text=True, timeout=20, check=True)
    return proc.stdout.strip()


def _historical_git_bytes(source: Path, sha: str, relative: str) -> bytes:
    """Read exact historical Git *blob*, not the newer checked-out source.

    The clean source HEAD must independently contain this original ancestor.
    Git content retrieval is read-only and does not run, checkout or stage code.
    """
    result = subprocess.run(
        ["git", "-C", str(source), "cat-file", "blob", f"{sha}:{relative}"],
        capture_output=True, timeout=20, check=True)
    return result.stdout


def _regular_tree(path: Path) -> Path:
    path = Path(path).absolute()
    if not path.is_dir() or any(part.is_symlink()
                                for part in (path, *path.parents)):
        raise ValueError("originalhost regular directory required (no links)")
    return path.resolve(strict=True)


def inspect(*, source: Path, stage: Path, stage_sha: str) -> dict:
    """Read-only: bind the old physical stage to unchanged committed source.

    The source checkout may advance safely. Compare immutable staged bytes
    with their actual historical ancestor Git blobs, never the later worktree
    bytes. No checkout, synthetic writer replay, Cloud write or new release.
    """
    if not HEX40.fullmatch(stage_sha):
        raise ValueError("exact lowercase stage SHA required")
    src = _regular_tree(source)
    staged = _regular_tree(stage)
    if staged.name != "V3Paper-INACTIVE-" + stage_sha[:12]:
        raise ValueError("unexpected inactive source stage")
    trading = staged.parent.parent
    if staged.parent.name != "Staging" or src.is_relative_to(trading):
        raise ValueError("source must be separate from protected Trading root")
    if _git(src, "status", "--porcelain", "--untracked-files=normal"):
        raise ValueError("source tree dirty; no original source attribution")
    head = _git(src, "rev-parse", "HEAD")
    if not HEX40.fullmatch(head):
        raise ValueError("unrecognized independent Git source")
    if subprocess.run(["git", "-C", str(src), "merge-base", "--is-ancestor",
                       stage_sha, head], timeout=20).returncode != 0:
        raise ValueError("stage SHA not ancestor of independent source HEAD")
    manifest_path = staged / "v3-paper-inactive-source-manifest.json"
    if (manifest_path.is_symlink() or not manifest_path.is_file()
            or manifest_path.stat().st_size > 131072):
        raise ValueError("source-only staging manifest missing or oversized")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = manifest.get("source_manifest")
    if (manifest.get("kind") != "V3_PAPER_INACTIVE_ISOLATED_SOURCE_STAGE_V1"
            or manifest.get("status") != "STAGED_INACTIVE_CODE_ONLY_NOT_INSTALLED"
            or manifest.get("source_git_sha") != stage_sha
            or manifest.get("v3_paper_activated") is not False
            or manifest.get("task_changes") is not False
            or not isinstance(rows, list) or len(rows) < 60 or len(rows) > 100):
        raise ValueError("inactive source manifest not trustworthy")
    verified = set()
    for row in rows:
        rel, expected = row.get("relative_path"), row.get("sha256")
        if (not isinstance(rel, str) or
                not re.fullmatch(r"[A-Za-z0-9_./-]{4,180}", rel) or
                ".." in Path(rel).parts or rel.startswith("/") or
                not isinstance(expected, str) or
                re.fullmatch(r"[0-9a-f]{64}", expected) is None or rel in verified):
            raise ValueError("unsafe or duplicate source manifest entry")
        here = staged / rel
        if (here.is_symlink() or not here.is_file()
                or any(parent.is_symlink() for parent in here.parents
                       if parent == staged or staged in parent.parents)):
            raise ValueError("pinned stage file absent or linked")
        staged_bytes = here.read_bytes()
        if len(staged_bytes) > 2_000_000:
            raise ValueError("oversized original stage source file")
        try:
            git_bytes = _historical_git_bytes(src, stage_sha, rel)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise ValueError("historical original Git blob missing") from exc
        if (hashlib.sha256(staged_bytes).hexdigest() != expected
                or staged_bytes != git_bytes):
            raise ValueError("stage and original historical Git bytes differ")
        verified.add(rel)
    must = {"paper_evaluator/v3_paper_minipc_one_candidate_v1.py",
            "paper_evaluator/v3_paper_minipc_selective_tick_v1.py",
            "paper_evaluator/v3_experimental_paper_journal_v1.py",
            "paper_evaluator/v3_paper_cloud_receipt_sync_v1.py",
            "paper_evaluator/v3_paper_minipc_native_launcher_v1.py",
            "tools/v3_experimental_paper_technical_gate.py",
            "tools/paper_series_transition_guard.py"}
    if not must.issubset(verified):
        raise ValueError("physical writer/lock/journal/Cloud module not in stage")
    parent = trading / "Research" / "V3Paper"
    if not parent.is_dir() or parent.is_symlink():
        raise ValueError("pre-existing separate V3 Research parent required")
    target = parent / ("PRECAS-OFFLINE-ORIGINALHOST-" + stage_sha[:12])
    return {"source": src, "stage": staged, "stage_sha": stage_sha,
            "source_head": head, "target": target, "verified_files": len(verified),
            "series_id": "PAPER-V3-CANARY-PRECAS-OFFLINE-" + stage_sha[:12].upper()}


def _receipt_files(journal: Path, series: str, candidate_id: str) -> list:
    records = []
    for f in sorted(journal.glob("*.json")):
        if f.is_symlink() or not f.is_file():
            raise ValueError("linked or missing original receipt forbidden")
        raw = f.read_bytes()
        row = json.loads(raw)
        if row.get("series_id") == series and row.get("candidate_id") == candidate_id:
            event_key = "|".join(str(row[k]) for k in
                                 ("series_id", "candidate_id", "phase", "event_key"))
            eid = hashlib.sha256(event_key.encode("utf-8")).hexdigest()
            if (f.name != eid + ".json" or row.get("orders") is not False
                    or row.get("real_money_actions") is not False):
                raise ValueError("incorrect immutable native receipt identity")
            records.append({"phase": row["phase"], "result": row["result"],
                            "event_key": row["event_key"], "event_id": eid,
                            "known_at_utc": row["known_at_utc"],
                            "content_sha256": hashlib.sha256(raw).hexdigest()})
    return records


def _original_case_receipt(journal: Path, indexed: dict, *,
                           series_id: str, candidate_id: str) -> dict:
    """Re-read the actual immutable bytes; no projected fixture may impersonate disk.

    Only data from these files may become economic or chronological dry-run
    evidence. True host and independent Cloud authentication remain EXTERNAL.
    """
    f = journal / (indexed["event_id"] + ".json")
    if f.is_symlink() or not f.is_file():
        raise ValueError("original receipt missing or symlink")
    raw = f.read_bytes()
    if hashlib.sha256(raw).hexdigest() != indexed["content_sha256"]:
        raise ValueError("original receipt changed since journal indexing")
    row = json.loads(raw)
    if (row.get("series_id") != series_id or row.get("candidate_id") != candidate_id
            or row.get("phase") != indexed["phase"]
            or row.get("result") != indexed["result"]
            or row.get("orders") is not False
            or row.get("real_money_actions") is not False
            or not isinstance(row.get("data"), dict)):
        raise ValueError("original disk receipt identity changed")
    stamp = row.get("known_at_utc")
    try:
        moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if moment.utcoffset() is None:
            raise ValueError("naive original clock")
    except (TypeError, AttributeError, ValueError) as exc:
        raise ValueError("original journal lacks known-at clock") from exc
    return row


def _case_economic_proof(journal: Path, series_id: str, candidate_id: str,
                         p4: dict, fill: dict | None) -> dict:
    """Read positive economics and P4/fill timing, not a Release PASS flag."""
    original_p4 = _original_case_receipt(
        journal, p4, series_id=series_id, candidate_id=candidate_id)
    answer = {"p4_known_at_utc": original_p4["known_at_utc"],
              "paper_fill_known_at_utc": None,
              "native_journal_record_sha256": p4["content_sha256"],
              "paper_scout_eur": None,
              "paper_entry_taker_fee_eur": None}
    if fill is None:
        return answer
    original_fill = _original_case_receipt(
        journal, fill, series_id=series_id, candidate_id=candidate_id)
    p = original_p4["data"]
    f = original_fill["data"]
    ask, qty, fee = (f.get(k) for k in (
        "paper_entry_ask_eur", "paper_entry_qty", "paper_entry_fee_eur"))
    if (any(type(v) not in (int, float) or not math.isfinite(v)
            for v in (ask, qty, fee, p.get("ask_eur"),
                      p.get("validated_stop_eur"), p.get("validated_stage2_eur")))
            or not 0 < p["validated_stop_eur"] < ask < p["validated_stage2_eur"]
            or not math.isclose(ask, p["ask_eur"], rel_tol=1e-7)
            or not math.isclose(qty*ask, 50.0, rel_tol=1e-6, abs_tol=1e-5)
            or not math.isclose(fee, 0.3, rel_tol=0, abs_tol=1e-8)
            or f.get("validated_stop_eur") != p["validated_stop_eur"]
            or f.get("validated_stage2_eur") != p["validated_stage2_eur"]):
        raise ValueError("original Paper fill/P4 ask-stop-stage2-fee inconsistent")
    p4_at = datetime.fromisoformat(
        original_p4["known_at_utc"].replace("Z", "+00:00"))
    fill_at = datetime.fromisoformat(
        original_fill["known_at_utc"].replace("Z", "+00:00"))
    if fill_at < p4_at:
        raise ValueError("Paper fill chronologically before original P4")
    answer.update(paper_fill_known_at_utc=original_fill["known_at_utc"],
                  native_journal_record_sha256=fill["content_sha256"],
                  paper_scout_eur=round(ask*qty, 2),
                  paper_entry_taker_fee_eur=fee)
    return answer


def run_offline_cases(root: Path, series_id: str, *, stage: Path | None = None,
                      source: Path | None = None) -> dict:
    """Exactly two actual disk-writer calls under the EXISTING native OS lock.

    Test imports are from the clean reviewed Git checkout, and runtime imports
    from the 67-file original host stage. No real model/key or Kraken calls.
    """
    if not series_id.startswith("PAPER-V3-CANARY-PRECAS-OFFLINE-"):
        raise ValueError("strict synthetic CANARY namespace required")
    if stage is not None and source is not None:
        # -I excludes the user site and CWD; explicit verified paths only.
        sys.path.insert(0, str(stage))
        sys.path.insert(1, str(source))
    from paper_evaluator.v3_paper_minipc_one_candidate_v1 import one_candidate
    from paper_evaluator.v3_paper_minipc_selective_tick_v1 import _one_canary_owner
    from tests.test_v3_experimental_paper_initial_review_v1 import fixture
    from tests.test_v3_full_entry_decision_candidate_v1 import fixture as model_fixture
    from tests.test_v2r4_v3_entry_handoff_probe import dt
    from tests.test_v3_paper_minipc_one_candidate_v1 import valid_approval

    journal = root / "journal"
    budgets = root / "model-stub-reservations"
    for path in (journal, budgets):
        path.mkdir(mode=0o700)
    evidence = []
    # Throw on any accidental network fallback; all callbacks MUST be stubbed.
    def blocked(*_args, **_kwargs):
        raise AssertionError("OFFLINE_ONLY_NO_NETWORK_API_KRAKEN")
    with (_one_canary_owner(journal),
          mock.patch.object(socket, "create_connection", side_effect=blocked),
          mock.patch.object(socket.socket, "connect", side_effect=blocked),
          mock.patch.object(request, "urlopen", side_effect=blocked),
          mock.patch("paper_evaluator.evaluate.http_json", side_effect=blocked)):
        for label in ("POSITIVE_BUY_SCOUT", "NEGATIVE_REJECT"):
            candidate, coin, quote, metadata = fixture()
            cid = "V3-OFFLINE-HOST-" + ("BUY" if label.startswith("POSITIVE") else "REJECT")
            candidate = dict(candidate, candidate_id=cid)
            coin, quote, metadata = (copy.deepcopy(x) for x in (coin, quote, metadata))
            assessment = copy.deepcopy(model_fixture()[-1])
            assessment.update(candidate_id=cid, decision_at_utc=dt(12),
                              setup_lane="IGNITION")
            if label == "NEGATIVE_REJECT":
                assessment["stop_eur"] = 999.0  # P4 fail-closed, never fill
            approval = valid_approval()
            approval.update(series_id=series_id,
                            unique_approval_id="OFFLINE_STUB_NOT_USER_APPROVAL_" + label)
            def acquire(_candidate):
                return coin, quote, metadata
            def fake_model(_prompt, _key):
                return assessment, {"response_id": "STUB_NO_PROVIDER_HTTP_" + label,
                                    "model": "LOCAL_OFFLINE_MODEL_STUB"}
            result = one_candidate(
                candidate=candidate, series_id=series_id,
                local_receipts=journal, model_reservations=budgets,
                approval=approval, model_key="NOT_A_REAL_API_KEY_OFFLINE_STUB",
                allow_model=True, acquire=acquire, model_client=fake_model,
                clock=lambda: dt(12))
            expected = "BUY_SCOUT" if label == "POSITIVE_BUY_SCOUT" else "REJECT"
            if (result.get("p4_decision") != expected
                    or result.get("orders") is not False
                    or result.get("model_http_attempts_reserved") != 1):
                raise ValueError("model-stub P4 outcome not fail-closed")
            rows = _receipt_files(journal, series_id, cid)
            p4s = [x for x in rows if x["phase"] == "P4_VALIDATION"]
            fills = [x for x in rows if x["phase"] == "PAPER_FILL"]
            if (len(p4s) != 1 or p4s[0]["result"] != expected
                    or len(fills) != (1 if expected == "BUY_SCOUT" else 0)
                    or any(f["result"] != "PAPER_FILLED" for f in fills)):
                raise ValueError("native immutable Paper ledger P4/fill disagreement")
            # This is LOCAL synthetic model-stub disk evidence, never itself
            # an independent physical host/Cloud proof or trading permit.
            observed = _case_economic_proof(
                journal, series_id, cid, p4s[0], fills[0] if fills else None)
            evidence.append({"case": label, "series_id": series_id,
                             "candidate_id": cid,
                             "p4_decision": expected,
                             "paper_fill_count": len(fills),
                             "paper_fill_result": "PAPER_FILLED" if fills else "NO_PAPER_FILL",
                             "p4_record_sha256": p4s[0]["content_sha256"],
                             "paper_fill_record_sha256": fills[0]["content_sha256"] if fills else None,
                             **observed,
                             "physical_host_attested": False,
                             "cloud_originals_independently_verified": False,
                             "receipts": rows})
    if len(list(budgets.glob("*.reserved.json"))) != 2:
        raise ValueError("each stub candidate needs a separate single-use reservation")
    return {"kind": "V3_PRECAS_PHYSICAL_OFFLINE_DUAL_CASE_WITNESS_V1",
            "status": "HOST_LOCAL_OFFLINE_MODEL_STUB_ONLY",
            "series_id": series_id, "source_fixture": "SYNTHETIC_20261009_NOT_LIVE_KRAKEN",
            "physical_host_readback_independently_verified": False,
            "cloud_receipts_independently_verified": False,
            "native_owner_lock_used": True, "no_real_model_http": True,
            "simulated_model_approval_not_user_approval": True,
            "real_money_actions": False, "orders": False,
            "paper_release_authorized": False, "technical_release_proofs_credited": 0,
            "cases": evidence}



def inspect_existing_offline_originals(root: Path, series_id: str,
                                       expected_cloud_digest: str | None = None,
                                       *, stage_sha: str | None = None) -> dict:
    """Read ONLY the one earlier isolated BUY/REJECT Host journal.

    No second writer run, test scenario, Task, Cloud POST, or release ACK.
    The historical Cloud digest, if provided, is only a previously observed
    external reference -- this method cannot independently query Cloud.
    """
    from tools.v3_paper_precas_synthetic_cloud_sandbox_v1 import (
        STAGE_SHA as KNOWN_STAGE, audit_offline_witness,
    )
    actual_sha = KNOWN_STAGE if stage_sha is None else stage_sha
    if (not isinstance(actual_sha, str) or HEX40.fullmatch(actual_sha) is None
            or series_id !=
            "PAPER-V3-CANARY-PRECAS-OFFLINE-" + actual_sha[:12].upper()
            or root.name != "PRECAS-OFFLINE-ORIGINALHOST-" + actual_sha[:12]):
        raise ValueError("unknown originalhost synthetic witness series")
    if root.is_symlink() or not root.is_dir():
        raise ValueError("original physical research journal unavailable")
    checked = audit_offline_witness(root, stage_sha=actual_sha)
    journal = checked["journal"]
    report_path = root / "offline-model-stub-witness.json"
    if report_path.is_symlink() or not report_path.is_file():
        raise ValueError("original witness file unavailable")
    report = json.loads(report_path.read_text("utf-8"))
    if report.get("series_id") != series_id or len(report.get("cases", [])) != 2:
        raise ValueError("original host witness identity invalid")
    cases = []
    for case in report["cases"]:
        cid = case["candidate_id"]
        rows = _receipt_files(journal, series_id, cid)
        if (len(rows) != len(case["receipts"])
                or {x["event_id"]: x["content_sha256"] for x in rows} !=
                {x["event_id"]: x["content_sha256"] for x in case["receipts"]}):
            raise ValueError("original witness receipts mismatch existing files")
        p4 = [r for r in rows if r["phase"] == "P4_VALIDATION"]
        fill = [r for r in rows if r["phase"] == "PAPER_FILL"]
        if (len(p4) != 1 or len(fill) != case["paper_fill_count"]
                or case["p4_decision"] != p4[0]["result"]
                or (case["case"] == "POSITIVE_BUY_SCOUT" and
                    (len(fill) != 1 or fill[0]["result"] != "PAPER_FILLED"))
                or (case["case"] == "NEGATIVE_REJECT" and
                    (len(fill) != 0 or p4[0]["result"] != "REJECT"))):
            raise ValueError("original host BUY/REJECT evidence disagreement")
        economics = _case_economic_proof(
            journal, series_id, cid, p4[0], fill[0] if fill else None)
        cases.append({"case": case["case"], "series_id": series_id,
                      "candidate_id": cid, "p4_decision": p4[0]["result"],
                      "paper_fill_count": len(fill),
                      "p4_record_sha256": p4[0]["content_sha256"],
                      "paper_fill_record_sha256": (
                          fill[0]["content_sha256"] if fill else None),
                      **economics})
    if set(x["case"] for x in cases) != {
            "POSITIVE_BUY_SCOUT", "NEGATIVE_REJECT"}:
        raise ValueError("two distinct synthetic test cases required")
    historical_match = None
    if expected_cloud_digest is not None:
        if re.fullmatch(r"[0-9a-f]{64}", expected_cloud_digest) is None:
            raise ValueError("historical Cloud reference must be exact sha256")
        if checked["joined_sha256"] != expected_cloud_digest:
            raise ValueError("historical sandbox Cloud digest reference differs")
        historical_match = True
    return {
        "status": "EXISTING_HOST_ORIGINALS_REANALYZED_READ_ONLY",
        "series_id": series_id,
        "event_count": checked["count"],
        "event_digest_join_sha256": checked["joined_sha256"],
        "prior_independent_cloud_digest_reference_matched": historical_match,
        "fresh_independent_cloud_readback_performed": False,
        "native_writer_reexecuted": False,
        "physical_host_attestation_automatically_granted": False,
        "real_model_or_market_evidence": False,
        "v3_paper_release_authorized": False,
        "technical_release_proofs_credited": 0,
        "orders": False,
        "cases": cases,
    }


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--source", type=Path, required=True)
    cli.add_argument("--stage", type=Path, required=True)
    cli.add_argument("--expected-stage-sha", required=True)
    cli.add_argument("--execute-host-offline", action="store_true")
    cli.add_argument("--readback-existing", action="store_true")
    cli.add_argument("--expected-isolated-cloud-digest", default=None)
    a = cli.parse_args()
    if a.execute_host_offline and a.readback_existing:
        raise ValueError("cannot reexecute writer during existing journal readback")
    if a.expected_isolated_cloud_digest is not None and not a.readback_existing:
        raise ValueError("historical Cloud digest is readback-only")
    p = inspect(source=a.source, stage=a.stage, stage_sha=a.expected_stage_sha)
    output = p["target"]
    if a.readback_existing:
        # -I removes current working directory AND script directory from
        # import search. Reintroduce only the independently verified,
        # SHA-pinned stage plus the clean Git source required for the
        # original read-only journal auditor. Do not reexecute its writer.
        sys.path.insert(0, str(p["stage"]))
        sys.path.insert(1, str(p["source"]))
        print(json.dumps(inspect_existing_offline_originals(
            output, p["series_id"], a.expected_isolated_cloud_digest,
            stage_sha=p["stage_sha"]), sort_keys=True))
        return 0
    if output.exists():
        raise ValueError("ONE_SHOT_WITNESS_TARGET_ALREADY_EXISTS_NO_RETRY")
    if not a.execute_host_offline:
        print(json.dumps({"status": "READ_ONLY_PREVIEW_NO_WRITES",
                          "stage_sha": p["stage_sha"],
                          "source_head": p["source_head"],
                          "files_verified": p["verified_files"],
                          "target": str(output),
                          "model_http": 0, "orders": False,
                          "paper_release_authorized": False}, sort_keys=True))
        return 0
    # Only approved isolated Research target is created. On error leave partial
    # files intact for owner review; never silently retry and overwrite.
    output.mkdir(mode=0o700)
    report = run_offline_cases(output, p["series_id"],
                               stage=p["stage"], source=p["source"])
    report["stage_source_sha"] = p["stage_sha"]
    report["independent_source_git_sha"] = p["source_head"]
    report["journal_path"] = str(output / "journal")
    report["ack_path_planned_only"] = str(output / "cloud-ack.json")
    path = output / "offline-model-stub-witness.json"
    with path.open("x", encoding="utf-8") as fh:
        json.dump(report, fh, sort_keys=True, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    # No relay call here. Existing v3_paper_cloud_receipt_sync_v1.py is the
    # separately user-authorized transport; independent SQL query after that.
    print(json.dumps({"status": report["status"], "series_id": p["series_id"],
                      "witness_file": str(path), "journal_path": report["journal_path"],
                      "cases": [{"case": x["case"], "decision": x["p4_decision"],
                                 "paper_fills": x["paper_fill_count"]}
                                for x in report["cases"]],
                      "cloud_ack": False, "orders": False,
                      "technical_release_proofs_credited": 0},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
