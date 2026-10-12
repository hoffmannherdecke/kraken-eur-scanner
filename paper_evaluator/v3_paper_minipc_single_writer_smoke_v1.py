"""ONE explicit physical V3 scanner -> immutable stage -> public Kraken -> Cloud ACK.

This is a bounded canary proof, NOT a long-running V3 writer, new scheduler,
OpenAI invocation, Paper activation, H5/H10/H11 authenticator or order writer.
Use an isolated canary-series directory, never the ongoing 28h task's journal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from market_data.universe import online_eur_universe
from paper_evaluator.v3_paper_positive_source_entry_v1 import STREAMS, utc
from paper_evaluator.v3_paper_single_writer_preflight_v1 import plan_writer_preflight
from paper_evaluator.v3_paper_intake_receipt_stage_v1 import stage_receipts_explicitly
from paper_evaluator.v3_paper_minipc_one_candidate_v1 import one_candidate, REVISION
from paper_evaluator.v3_paper_cloud_receipt_sync_v1 import sync_once

SERIES = "PAPER-V3-CANARY-WRITER-SMOKE-20261012"
OLD_SERIES = "PAPER-V2R4-20261009T110135Z"
TASK = "CryptoMiniPC-V3CanaryObservation28h"
PIN_COUNT = 9
_MAX_HANDOFFS = 100


def now() -> datetime:
    return datetime.now(timezone.utc)


def _json(path: Path, *, max_bytes: int = 200_000) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > max_bytes:
        raise ValueError("required canonical local evidence missing/invalid")
    out = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(out, dict):
        raise ValueError("canonical JSON object required")
    return out


def _canary_safety(root: Path, repo: Path, moment: datetime) -> None:
    manifest = _json(root / "State" / "v3-canary-observer-28h-plan.json")
    heartbeat = _json(root / "State" / "v3-canary-observer-28h-heartbeat.json")
    pins = manifest.get("pinned_file_hashes")
    if (manifest.get("kind") != "V3_LOCAL_READONLY_CANARY_28H_PLAN_V1"
            or manifest.get("task_name") != TASK
            or manifest.get("v2r4_unchanged") is not True
            or manifest.get("model_http_calls_authorized") != 0
            or manifest.get("orders") is not False
            or utc(manifest["until_utc"]) <= moment
            or not isinstance(pins, list) or len(pins) != PIN_COUNT):
        raise ValueError("original SHA-pinned 28h observer manifest not safe")
    if (heartbeat.get("status") not in
            ("HEALTHY_CLOUD_ACK", "HEALTHY_NO_NEW_CLOUD_EVENTS")
            or heartbeat.get("v2r4_unchanged") is not True
            or heartbeat.get("model_http_calls") != 0
            or not 0 <= (moment-utc(heartbeat["checked_at_utc"])).total_seconds() <= 1200):
        raise ValueError("physical 28h heartbeat not recently healthy")
    for pin in pins:
        rel, digest = pin.get("relative_path"), pin.get("sha256")
        if (not isinstance(rel, str) or not isinstance(digest, str)
                or not re.fullmatch(r"[a-fA-F0-9]{64}", digest)
                or not rel or rel.startswith(("/", "\\"))
                or ":" in rel or ".." in rel):
            raise ValueError("invalid pinned original V3 observer path/hash")
        path = repo.joinpath(*re.split(r"[/\\]", rel))
        if not path.is_file() or path.is_symlink():
            raise ValueError("original V3 task file absent")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest.lower():
            raise ValueError("original V3 task file hash mismatch")


def _source_queue(root: Path) -> Path:
    runtime = root / "Runtime"
    if not runtime.is_dir() or runtime.is_symlink():
        raise ValueError("V2R4 owner runtime root missing")
    found = []
    for app in runtime.iterdir():
        if not app.is_dir() or app.is_symlink():
            continue
        control = app / "paper_runtime_control.json"
        if not control.is_file():
            continue
        data = _json(control)
        if data.get("series_id") != OLD_SERIES:
            continue
        if data.get("paper_only") is not True or data.get("real_money_actions_enabled") is not False:
            raise ValueError("legacy V2R4 runtime must remain paper-only")
        found.append(app / "handoff_queue")
    if len(found) != 1 or not found[0].is_dir() or found[0].is_symlink():
        raise ValueError("not exactly one existing read-only V2R4 original source")
    return found[0]


def _fresh_original(queue: Path, moment: datetime) -> dict[str, Any] | None:
    handoffs = sorted(queue.glob("*.json"),
                      key=lambda p: p.stat().st_mtime, reverse=True)[:_MAX_HANDOFFS]
    valid = []
    for path in handoffs:
        try:
            c = _json(path)
            if (c.get("kind") != "CANONICAL_CANDIDATE_HANDOFF_V1"
                    or c.get("action") != "REVIEW_ONLY_NOT_ORDER"
                    or c.get("entry_origin") not in (None, "SCANNER")
                    or not isinstance(c.get("candidate_id"), str)
                    or not 1 <= len(c["candidate_id"]) <= 150
                    or c["candidate_id"].startswith("V3-INPUT-REJECT-")
                    or not isinstance(c.get("pair"), str)
                    or not re.fullmatch(r"[A-Z0-9]{2,20}/EUR", c["pair"])
                    or not isinstance(c.get("altname"), str)
                    or not c["altname"].isalnum()):
                continue
            event_at = utc(c["event_time_utc"])
            if not 0 <= (moment-event_at).total_seconds() <= 600:
                continue
            valid.append((event_at, c["candidate_id"], c))
        except (ValueError, TypeError, KeyError, OverflowError, OSError, json.JSONDecodeError):
            continue
    if not valid:
        return None
    # No retrospective selection using prices; just newest already-issued handoff.
    return dict(max(valid, key=lambda item: (item[0], item[1]))[2],
                entry_origin="SCANNER")


def _public_pairs() -> list[dict[str, str]]:
    request = urllib.request.Request(
        "https://api.kraken.com/0/public/AssetPairs",
        headers={"User-Agent": "v3-minipc-one-shot-writer-smoke-public-only/1"})
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read(8_000_000))
    if not isinstance(data, dict) or data.get("error") or not isinstance(data.get("result"), dict):
        raise ValueError("live public Kraken EUR AssetPairs proof missing")
    return online_eur_universe(data["result"])


def run_one_shot(*, trading_root: Path, repository: Path,
                 execute: bool = False, cloud_ack: bool = False,
                 pair_loader: Callable[[], list[dict[str, str]]] = _public_pairs,
                 acquire: Callable | None = None,
                 clock: Callable[[], datetime] = now,
                 cloud_post: Callable | None = None) -> dict[str, Any]:
    """Physical boundary checks precede EVERY write, including one-shot guard."""
    if cloud_ack and not execute:
        raise ValueError("Cloud ACK requires explicit one-shot execution")
    t = clock().astimezone(timezone.utc)
    root = Path(trading_root)
    repo = Path(repository)
    if not repo.is_dir() or repo.is_symlink():
        raise ValueError("canonical Mini-PC Git repository missing")
    _canary_safety(root, repo, t)
    queue = _source_queue(root)
    candidate = _fresh_original(queue, t)
    if candidate is None:
        return {"status": "NO_FRESH_UNPROCESSED_10M_ORIGINAL_NO_WRITES",
                "model_http_calls": 0, "orders": False, "v2r4_unchanged": True,
                "cloud_ack_verified": False}
    ctime = candidate["event_time_utc"]
    ident = candidate["candidate_id"]
    pair = candidate["pair"]
    if not execute:
        return {"status": "ONE_FRESH_V2R4_ORIGINAL_PLAN_ONLY",
                "candidate_id": ident, "pair": pair,
                "model_http_calls": 0, "orders": False,
                "v2r4_unchanged": True, "cloud_ack_verified": False}
    # Authoritative ONLINE Spot-EUR metadata is public Kraken, not a local map.
    pairs = pair_loader()
    matches = [m for m in pairs if m.get("symbol") == pair
               and m.get("altname") == candidate["altname"]
               and m.get("status") == "online"]
    if len(matches) != 1:
        return {"status": "KRAKEN_SPOT_EUR_PAIR_NOT_VERIFIED_NO_WRITES",
                "candidate_id": ident, "pair": pair,
                "model_http_calls": 0, "orders": False,
                "v2r4_unchanged": True, "cloud_ack_verified": False}
    decision = clock().astimezone(timezone.utc)
    if not 0 <= (decision-utc(ctime)).total_seconds() <= 600:
        return {"status": "ORIGINAL_EXPIRED_DURING_PUBLIC_METADATA_NO_WRITES",
                "model_http_calls": 0, "orders": False,
                "v2r4_unchanged": True, "cloud_ack_verified": False}
    # Physical PIN still required immediately before any filesystem mutation.
    _canary_safety(root, repo, decision)
    isolated = root / "Research" / "V3Paper" / "writer-smoke-20261012"
    if isolated.exists() or isolated.is_symlink():
        raise ValueError("one-shot writer smoke already reserved, no automatic replay")
    parent = isolated.parent
    if not parent.is_dir() or parent.is_symlink():
        raise ValueError("existing independent V3 research root required")
    isolated.mkdir(mode=0o700)
    journal = isolated / "journal"
    budget = isolated / "budgets"
    journal.mkdir(mode=0o700)
    budget.mkdir(mode=0o700)
    # There is no background scheduler: this isolated root is the irreversible
    # at-most-once marker even if Cloud ACK or public Kraken later fails.
    preflight = plan_writer_preflight(
        scanner_events=[candidate], owner_event_packets=[],
        h10_context=None, h11_market_capture=None, h5_macro_calendar=None,
        authenticated_owner_ids={name: [] for name in STREAMS},
        journal_receipts=[], known_pairs={
            pair: {"pair": pair, "altname": candidate["altname"],
                   "status": "online", "spot": True, "quote": "EUR"}},
        market_observations={}, series_id=SERIES,
        decision_at_utc=decision.isoformat(), max_reviews=1)
    if (preflight["ingress"]["counts"]["selected"] != 1 or
            preflight["selected_candidates"][0]["candidate_id"] != ident or
            preflight["model_http_authorized"] is not False):
        raise ValueError("canonical one-original, zero-spend intake not proven")
    stage = stage_receipts_explicitly(preflight=preflight, journal_directory=journal)
    if stage["originals_with_receipt"] != 1 or stage["written"] != 2:
        raise ValueError("original immutable intake stage did not ACK exactly two receipts")
    worker = one_candidate(
        candidate=preflight["selected_candidates"][0],
        series_id=SERIES, local_receipts=journal, model_reservations=budget,
        allow_model=False, approval=None, model_key=None, existing_context=None,
        admit_staged_scanner_no_model=True, acquire=acquire,
        clock=lambda: clock().astimezone(timezone.utc).isoformat())
    cloud = None
    if cloud_ack:
        secret = root / "Secrets" / "v3-paper-relay-token.txt"
        if not secret.is_file() or secret.is_symlink():
            raise ValueError("isolated V3 receipts saved, cloud token missing; no ACK claimed")
        token = secret.read_text("utf-8").strip()
        cloud = sync_once(journal=journal, series_id=SERIES,
                          ack_file=isolated/"cloud-ack.json", token=token,
                          post=cloud_post)
    return {
        "status": "ONE_REAL_ORIGINAL_STAGED_AND_KRAKEN_REVIEWED_CANARY_ONLY",
        "series_id": SERIES, "candidate_id": ident, "pair": pair,
        "staged_immutable_receipts": stage["written"],
        "real_kraken_worker_status": worker["status"],
        "cloud_status": cloud["status"] if cloud else "CLOUD_NOT_REQUESTED",
        "cloud_ack_verified": bool(cloud and
                                   cloud["status"] == "V3_RECEIPTS_CLOUD_ACK_VERIFIED"),
        "cloud_receipts_accepted": cloud.get("count", 0) if cloud else 0,
        "model_http_calls": 0, "model_http_authorized": False,
        "orders": False, "v2r4_unchanged": True,
        "new_schedules": 0, "v3_paper_activated": False,
        "source_owner_runtime_authenticated": False,
        "economic_6h24h_proven": False,
        "existing_28h_canary_journal_unchanged_by_this_smoke": True,
    }


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--trading-root", type=Path, required=True)
    cli.add_argument("--execute-once", action="store_true")
    cli.add_argument("--cloud-ack", action="store_true")
    a = cli.parse_args()
    repo = Path(__file__).resolve().parents[1]
    result = run_one_shot(trading_root=a.trading_root, repository=repo,
                          execute=a.execute_once, cloud_ack=a.cloud_ack)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
