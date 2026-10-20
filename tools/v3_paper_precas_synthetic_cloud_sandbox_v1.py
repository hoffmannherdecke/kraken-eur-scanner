#!/usr/bin/env python3
"""Isolated V3 synthetic originalhost journal -> existing Edge relay.

TEST ONLY. Deliberately locks URL to a different Supabase project. No
production or real market/model evidence can be transmitted by this tool.
Requires human-supplied distinct ephemeral token in process environment.
No new service, Task, scheduler, database or model/market HTTP requests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re

SANDBOX_PROJECT = "zxyhunwpviafyxyqysne"
PRODUCTION_PROJECT = "nlgzjmqgwueojlyqmoru"
SANDBOX_RELAY_URL = (
    f"https://{SANDBOX_PROJECT}.supabase.co/functions/v1/v3-paper-evidence-relay"
)
SERIES = "PAPER-V3-CANARY-PRECAS-OFFLINE-C0D55C6C07B2"
STAGE_SHA = "c0d55c6c07b21efbbd6ce2a5f2d1e7f8efb5a039"
CASE_TO_DECISION = {
    "POSITIVE_BUY_SCOUT": ("V3-OFFLINE-HOST-BUY", "BUY_SCOUT", 1),
    "NEGATIVE_REJECT": ("V3-OFFLINE-HOST-REJECT", "REJECT", 0),
}
REVISION = "V3-EXPERIMENTAL-PAPER-20261011-ALL-LESSONS-001"


def audit_offline_witness(root: Path, *, stage_sha: str = STAGE_SHA) -> dict:
    """Read-only hash audit for an exact, isolated stage; Cloud URL stays fixed.

    Only the original historical stage is eligible for the existing sandbox
    CLI's transport. A new stage may be audited but cannot be sent by this
    CLI to any Cloud endpoint or interpreted as a released Paper series.
    """
    if not isinstance(stage_sha, str) or re.fullmatch(r"[0-9a-f]{40}", stage_sha) is None:
        raise ValueError("exact synthetic stage SHA required")
    series = "PAPER-V3-CANARY-PRECAS-OFFLINE-" + stage_sha[:12].upper()
    root = Path(root).absolute()
    if (root.name != "PRECAS-OFFLINE-ORIGINALHOST-" + stage_sha[:12]
            or root.parent.name != "V3Paper"
            or root.parent.parent.name != "Research"
            or not root.is_dir() or root.is_symlink()):
        raise ValueError("bounded originalhost research witness root required")
    witness_path, journal = root / "offline-model-stub-witness.json", root / "journal"
    if (witness_path.is_symlink() or not witness_path.is_file()
            or journal.is_symlink() or not journal.is_dir()):
        raise ValueError("physical originalhost synthetic journal missing")
    witness = json.loads(witness_path.read_text("utf-8"))
    if (witness.get("status") != "HOST_LOCAL_OFFLINE_MODEL_STUB_ONLY"
            or witness.get("kind") != "V3_PRECAS_PHYSICAL_OFFLINE_DUAL_CASE_WITNESS_V1"
            or witness.get("series_id") != series
            or witness.get("stage_source_sha") != stage_sha
            or witness.get("source_fixture") != "SYNTHETIC_20261009_NOT_LIVE_KRAKEN"
            or witness.get("no_real_model_http") is not True
            or witness.get("simulated_model_approval_not_user_approval") is not True
            or witness.get("paper_release_authorized") is not False
            or witness.get("technical_release_proofs_credited") != 0
            or witness.get("orders") is not False
            or witness.get("real_money_actions") is not False
            or witness.get("native_owner_lock_used") is not True
            or len(witness.get("cases", [])) != 2):
        raise ValueError("witness not an explicit two-case offline-only model stub")
    from paper_evaluator.v3_paper_cloud_receipt_sync_v1 import batch
    rows = batch(journal, series, set(), limit=30)
    expected = {}
    phases_by_candidate: dict[str,list[tuple[str,str]]] = {}
    for case in witness["cases"]:
        label = case.get("case")
        if label not in CASE_TO_DECISION or label in expected:
            raise ValueError("missing or repeated synthetic case label")
        cid, decision, fills = CASE_TO_DECISION[label]
        if (case.get("candidate_id") != cid or
                case.get("p4_decision") != decision or
                case.get("paper_fill_count") != fills or
                case.get("paper_fill_result") != (
                    "PAPER_FILLED" if fills else "NO_PAPER_FILL")):
            raise ValueError("synthetic test case result differs from original fixture")
        expected[label] = case
        phases_by_candidate[cid] = []
    if set(expected) != set(CASE_TO_DECISION):
        raise ValueError("strict positive and negative case required")
    original_ids = set()
    for row in rows:
        payload = json.loads(row["canonical_json"])
        cid, event_id = payload.get("candidate_id"), row["event_id"]
        if (cid not in phases_by_candidate or payload.get("series_id") != series
                or payload.get("revision") != REVISION
                or payload.get("orders") is not False
                or payload.get("real_money_actions") is not False
                or payload.get("known_at_utc") is None):
            raise ValueError("unrecognized or unsafe original synthetic event")
        native_path = journal / (event_id + ".json")
        if native_path.is_symlink() or not native_path.is_file():
            raise ValueError("missing original file, or symlink")
        native = native_path.read_bytes()
        if (hashlib.sha256(native).hexdigest() != row["sha256"] or
                event_id in original_ids):
            raise ValueError("synthetic original file SHA mismatch or duplicate")
        phases_by_candidate[cid].append((payload["phase"], payload["result"]))
        original_ids.add(event_id)
    for label, (cid, decision, fills) in CASE_TO_DECISION.items():
        phases = phases_by_candidate[cid]
        if phases.count(("P4_VALIDATION",decision)) != 1:
            raise ValueError("one P4 decision required per candidate")
        if phases.count(("PAPER_FILL","PAPER_FILLED")) != fills:
            raise ValueError("synthetic BUY must have one fill, REJECT zero")
        case_events = expected[label].get("receipts")
        if not isinstance(case_events,list) or len(case_events) != len(phases):
            raise ValueError("witness/journal record count disagreement")
        for proof in case_events:
            if (proof.get("event_id") not in original_ids or
                    proof.get("content_sha256") != next(
                        (x["sha256"] for x in rows
                         if x["event_id"] == proof.get("event_id")), None)):
                raise ValueError("independent original event hash no longer matches witness")
    if len(rows) != 16 or len(original_ids) != 16:
        raise ValueError("expected exactly 16 original synthetic event receipts")
    joined = "\n".join(
        row["event_id"] + ":" + row["sha256"]
        for row in sorted(rows,key=lambda x:x["event_id"])
    )
    return {"journal": journal, "root": root, "rows": rows,
            "count": len(rows),
            "joined_sha256": hashlib.sha256(joined.encode()).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--witness-root",required=True,type=Path)
    parser.add_argument("--execute-isolated-cloud-sync",action="store_true")
    args = parser.parse_args()
    result = audit_offline_witness(args.witness_root)
    response = {
        "kind": "V3_PRECAS_SYNTHETIC_CLOUD_SANDBOX_BOUND_V1",
        "target_project_ref": SANDBOX_PROJECT,
        "target_series": SERIES,
        "events": result["count"],
        "canonical_event_hashes_joined_sha256": result["joined_sha256"],
        "fixture_only": True,
        "real_model_response": False,
        "new_paper_series_started": False,
        "release_gates_credited": 0,
        "orders": False,
        "production_target_allowed": False,
    }
    if PRODUCTION_PROJECT in SANDBOX_RELAY_URL:
        raise ValueError("production target invariant violated")
    if not args.execute_isolated_cloud_sync:
        response["status"] = "PREVIEW_ONLY_NO_NETWORK_NO_CLOUD_WRITE"
        print(json.dumps(response,sort_keys=True))
        return 0
    token = os.getenv("V3_PRECAS_ISOLATED_RELAY_TOKEN","")
    if re.fullmatch("[0-9a-f]{64}",token) is None:
        raise ValueError("separate 256-bit sandbox-only session token required")
    ack = result["root"] / "isolated-test-project-only-ack.json"
    if ack.is_symlink():
        raise ValueError("symlink ACK not allowed")
    from paper_evaluator.v3_paper_cloud_receipt_sync_v1 import sync_once
    outcome = sync_once(
        journal=result["journal"],series_id=SERIES,ack_file=ack,
        token=token,relay_url=SANDBOX_RELAY_URL)
    if outcome.get("status") != "V3_RECEIPTS_CLOUD_ACK_VERIFIED":
        raise ValueError("no exact original sandbox relay acceptance")
    response["status"] = "ISOLATED_SANDBOX_RELAY_ACK_NOT_INDEPENDENT_SQL_READBACK"
    response["relay_accepted"] = outcome.get("count")
    response["independent_cloud_readback"] = False
    print(json.dumps(response,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
