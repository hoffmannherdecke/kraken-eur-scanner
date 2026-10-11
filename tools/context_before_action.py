#!/usr/bin/env python3
"""On-demand, read-only context preflight for material project decisions.

Reads the existing canonical sources. It does not mutate a strategy, invoke models,
make network calls, trigger a scheduler, or claim human/AI comprehension.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MAP = "research/context-before-action-routing-v1.json"


class ContextGateError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContextGateError("CONTEXT_GATE_BLOCKED: " + message)


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "expected JSON object: " + str(path))
    return value


def routed_sources(root: Path, scope: str) -> tuple[dict, list[dict]]:
    config = read_json(root / MAP)
    require(config.get("kind") == "CONTEXT_BEFORE_ACTION_ROUTING_V1"
            and config.get("schema_version") == 1, "unknown routing contract")
    for flag in ("no_new_scheduler", "no_runtime_mutation", "no_trading_authority"):
        require(config.get(flag) is True, "unsafe routing flag: " + flag)
    require(config.get("status_authority") == "project-current-state.json"
            and config.get("task_authority") == "PROJECT_BACKLOG.md",
            "authority replacement")
    require(scope in config.get("scopes", {}), "unsupported scope: " + scope)
    entries = config["common"] + config["scopes"][scope]
    paths = [item.get("path") for item in entries]
    require(len(paths) == len(set(paths)), "duplicate authority in retrieval")
    root_resolved = root.resolve()
    for item in entries:
        path, role = item.get("path"), item.get("role")
        require(isinstance(path, str) and isinstance(role, str) and role,
                "source missing path/role")
        require(not path.startswith("/") and ".." not in Path(path).parts,
                "unsafe source path")
        target = (root / path).resolve()
        require(target.is_relative_to(root_resolved) and target.is_file(),
                "required source unavailable: " + path)
    return config, entries


def review_receipts(root: Path, state: dict) -> list[dict]:
    ack = read_json(root / "research/work-analysis-state.json")
    reviews = ((ack.get("acknowledgements") or {})
               .get("control_decision_reviews") or {})
    result = []
    for decision in state.get("next_control_decisions") or []:
        identifier = decision.get("id")
        key = decision.get("followthrough_ack_key")
        due = decision.get("due_at_utc")
        receipt = reviews.get(key) if key else None
        completed = (receipt or {}).get("completed_at_utc")
        report = (receipt or {}).get("report")
        valid = False
        if (isinstance(due, str) and isinstance(completed, str)
                and isinstance(report, str)
                and report.startswith("research/work-analysis/")
                and ".." not in Path(report).parts
                and (root / report).is_file()):
            try:
                due_time = dt.datetime.fromisoformat(due.replace("Z", "+00:00"))
                done_time = dt.datetime.fromisoformat(completed.replace("Z", "+00:00"))
                valid = (done_time >= due_time and
                         (receipt or {}).get("status") in
                         {"COMPLETED", "DECISION_PACKET_READY", "BLOCKED_WITH_ACTION"})
            except ValueError:
                pass
        result.append({
            "id": identifier,
            "trigger": decision.get("trigger"),
            "due_at_utc": due,
            "review_ack": "EVIDENCED_" + receipt["status"] if valid
                          else "NO_VERIFIED_ACK",
            "review_report": report if valid else None,
            "warning": "DECLARED_NEXT_DECISION_HAS_REVIEW_ACK_CHECK_CURRENT_BACKLOG"
                       if valid else None,
        })
    return result


def build(root: Path, scope: str) -> dict:
    config, entries = routed_sources(root, scope)
    index = []
    for item in entries:
        blob = (root / item["path"]).read_bytes()
        index.append({
            "path": item["path"],
            "role": item["role"],
            "sha256": hashlib.sha256(blob).hexdigest(),
            "bytes": len(blob),
        })
    state = read_json(root / "project-current-state.json")
    require(state.get("kind") == "PROJECT_CURRENT_STATE_V1", "unknown current state")
    active = state.get("active_strategy") or {}
    shadows = state.get("strategy_changing_shadow_wip") or {}
    declared = {
        "as_of_utc": state.get("as_of_utc"),
        "strategy_revision": active.get("strategy_revision"),
        "declared_paper_status": active.get("release_status"),
        "strategy_epoch_anchor": active.get("series_id"),
        "technical_series_last_verified": (active.get("technical_rotation_runtime_last_verified") or {}).get("series_id"),
        "strategy_changing_shadows": [x.get("id") or x.get("candidate_id")
                                       for x in shadows.get("active", [])],
        "automatic_activation_allowed": active.get("automatic_activation_allowed"),
        "real_money_actions": active.get("real_money_actions"),
        "live_runtime_independently_checked": False,
    }
    payload = {
        "kind": "CONTEXT_BEFORE_ACTION_PACKET_V1",
        "scope": scope,
        "status": "SOURCE_ROUTING_PASS_NEEDS_SUBSTANTIVE_REVIEW",
        "source_index": index,
        "declared_status": declared,
        "control_decision_ack_reconciliation": review_receipts(root, state),
        "limitations": [
            "Source hashes attest presence/version, not reading, semantic understanding or correctness.",
            "GitHub current-state is declared/datable, not independent live Supabase/MINI-PC evidence.",
            "An ACK can close a review while its original next-control-decision remains on file.",
            "External ChatGPT Work/automation prompts and unseen conversations are not GitHub-readable.",
            "This packet grants no trading, strategy promotion, secrets, scheduling or release authority.",
        ],
        "required_next_step": "Read relevant source sections, reconcile prior user decisions and blockers; attach a truthful scoped receipt before a material change.",
    }
    if scope in ("strategy", "research"):
        plan = read_json(root / "research/v3/v3-consolidated-strategy-integration-plan-20261011.json")
        require(plan.get("kind") == "V3_STRATEGY_INHERITANCE_AND_EXECUTION_PLAN_V1",
                "V3 strategy plan contract drift")
        payload["strategy_learning_routes"] = {
            "evidence": [{"id": x.get("id"), "status": x.get("status")}
                         for x in plan.get("evidence_inventory", [])],
            "prioritized_packages": [{"id": x.get("id"), "order": x.get("order"),
                                       "status": x.get("status"), "owner": x.get("owner")}
                                      for x in plan.get("package_order", [])],
            "h_statuses": [{"id": x.get("id"), "status": x.get("status")}
                           for x in plan.get("h_components", [])],
            "scope_warning": "Not a new release. Read full migration ledger and current evidence before proposing change.",
        }
    fingerprint_input = {
        "scope": scope,
        "sources": [(x["path"], x["sha256"]) for x in index],
    }
    payload["fingerprint"] = hashlib.sha256(
        json.dumps(fingerprint_input, sort_keys=True).encode("utf-8")).hexdigest()
    payload["has_network_access"] = False
    payload["has_runtime_side_effects"] = False
    return payload


def verify_receipt(root: Path, packet: dict, receipt_path: Path) -> dict:
    config = read_json(root / MAP)
    receipt = read_json(receipt_path)
    require(receipt.get("kind") == "CONTEXT_REVIEW_RECEIPT_V1",
            "unsupported receipt kind")
    require(receipt.get("scope") == packet["scope"], "receipt scope mismatch")
    require(receipt.get("fingerprint") == packet["fingerprint"],
            "receipt stale against current canonical sources")
    for field in config["receipt_required_fields"]:
        require(isinstance(receipt.get(field), str)
                and len(receipt[field].strip()) >= 20,
                "missing specific decision field: " + field)
    permitted = set(config["receipt_statuses"])
    recorded = receipt.get("source_dispositions")
    require(isinstance(recorded, list), "missing source dispositions")
    expected = {x["path"] for x in packet["source_index"]}
    observed = []
    for item in recorded:
        require(isinstance(item, dict), "invalid disposition")
        path = item.get("path")
        observed.append(path)
        require(item.get("status") in permitted, "invalid disposition: " + str(path))
        require(isinstance(item.get("reason"), str)
                and len(item["reason"].strip()) >= 20,
                "unsubstantiated disposition: " + str(path))
    require(len(observed) == len(set(observed)) and set(observed) == expected,
            "missing/extra/duplicate required source dispositions")
    return {
        "kind": "CONTEXT_REVIEW_VERIFICATION_V1",
        "scope": packet["scope"],
        "fingerprint": packet["fingerprint"],
        "status": "RECEIPT_STRUCTURE_VERIFIED_NOT_SEMANTIC_PROOF",
        "source_count": len(expected),
        "no_runtime_actions_authorized": True,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--scope", required=True,
                   choices=("strategy", "architecture", "operations", "research"))
    p.add_argument("--receipt", type=Path,
                   help="Verify a reviewer-supplied, scope-specific disposition; does not prove comprehension.")
    args = p.parse_args()
    try:
        packet = build(args.root, args.scope)
        output = verify_receipt(args.root, packet, args.receipt) if args.receipt else packet
        print(json.dumps(output, sort_keys=True, ensure_ascii=False))
        return 0
    except (ContextGateError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "CONTEXT_GATE_BLOCKED", "reason": str(error)},
                         ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
