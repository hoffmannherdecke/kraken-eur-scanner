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



# Immutable PR #161 history anchors: new generations may ADD items, but must not
# silently forget the 11 H components, ten rollout packages or 19 source lessons.
V3_LESSON_IDS = frozenset((
    "NULL_BUY_ECONOMIC", "EXTENDED_LATE_CHASE", "SECOND_LEG",
    "BAD_NOW_NOT_DEAD", "BREAKOUT_RESISTANCE", "WAIT_TTL_NEVER_RECHECK",
    "OVERSTRICT_ENTRY_MODEL", "COIN_ENTRY_FEATURE_GAP", "COIN_ATTACH_2_OF_4",
    "OPTIONAL_SOURCE_NEUTRAL", "SOFT_FACTORS_COMPENSATE",
    "TRADABILITY_KRAKEN_LIVE", "FEES_AND_EXECUTION", "STOP_STAGE2",
    "SCANNER_SCORE", "CHRONOLOGY_MFE_MAE", "REGIME_HETEROGENEITY",
    "SOURCES_H2_H11", "ACTIVATION_SAFE",
))
V3_CONFLICT_KEYS = frozenset((
    "OLD_LIBRARY_VS_2026_OCT_RISK", "H1_H2_H3_SEQUENCE_NOT_SAME",
    "SOURCE_REGISTERED_VS_ACTIVE", "INPUT_ONLY_VS_NEW_POLICY",
    "LEGACY_PR157_SUPERSEDED", "ECONOMIC_FREEZE_VS_PARALLEL_RESEARCH",
    "SMART_MONEY_VS_H8", "REAL_TRADING_VS_SEPARATE_AUTONOMOUS_AI_PROJECT",
))


def v3_decision_inheritance(root: Path) -> dict:
    """Cross-validate PR #161 and the original 19-lesson implementation matrix.

    This proves structural coverage and supplies the actual reasons, not that a
    future agent has read/understood every source. It preserves historical IDs
    while permitting later status transitions and new research hypotheses.
    """
    plan = read_json(root / "research/v3/v3-consolidated-strategy-integration-plan-20261011.json")
    matrix = read_json(root / "research/v3/v3-buy-decision-lessons-implementation-matrix-20261011.json")
    require(plan.get("kind") == "V3_STRATEGY_INHERITANCE_AND_EXECUTION_PLAN_V1",
            "V3 PR161 consolidated plan missing or changed")
    require(matrix.get("kind") == "V3_NO_BUY_LESSONS_IMPLEMENTATION_MATRIX_V1",
            "V3 19-lesson source changed")
    require(all(matrix.get(flag) is True for flag in
                ("no_activation", "no_buys_authorized", "no_real_money")),
            "V3 source unexpectedly authorizes trading")
    items = matrix.get("lessons") or []
    ids = [item.get("id") for item in items]
    require(len(ids) == len(set(ids)) and V3_LESSON_IDS.issubset(set(ids)),
            "original 19 V3 findings incomplete/duplicated")
    for item in items:
        require(all(isinstance(item.get(k), str) and item[k].strip()
                    for k in ("id", "finding", "disposition", "implementation", "stage")),
                "finding has no original cause/disposition/next action")
    packages = plan.get("package_order") or []
    orders = [item.get("order") for item in packages]
    package_ids = [item.get("id") for item in packages]
    require(len(package_ids) == len(set(package_ids)) and
            len(orders) == len(set(orders)) and
            {f"P{x}" for x in range(10)}.issubset(
                {x.split("_", 1)[0] for x in package_ids if isinstance(x, str)}),
            "V3 P0-P9 implementation order missing/duplicated")
    for item in packages:
        require(all(isinstance(item.get(k), str) and item[k].strip()
                    for k in ("id", "status", "owner", "work", "exit")),
                "V3 work package lacks status/owner/action/exit")
    h = plan.get("h_components") or []
    hids = [item.get("id") for item in h]
    require(len(hids) == len(set(hids)) and
            {f"H{x}" for x in range(1, 12)}.issubset(set(hids)),
            "H1-H11 status/history omitted or duplicated")
    for item in h:
        require(all(isinstance(item.get(k), str) and item[k].strip()
                    for k in ("id", "status", "role")),
                "H component not fully routed")
    conflicts = plan.get("consistency_findings") or []
    keys = [item.get("key") for item in conflicts]
    require(len(keys) == len(set(keys)) and V3_CONFLICT_KEYS.issubset(set(keys)),
            "eight explicit PR161 contradiction resolutions incomplete")
    for item in conflicts:
        require(isinstance(item.get("resolution"), str) and
                len(item["resolution"].strip()) >= 20,
                "historical user-decision conflict lacks resolution")
    guard = plan.get("global_gates") or {}
    for flag in ("single_change_before_integration", "same_candidate_pair_event_market_clock_and_baseline_replay_required",
                 "missing_core_data_fail_closed_and_report_unknown",
                 "user_approval_needed_for_new_strategy_changing_shadow_or_new_model_budget",
                 "paper_and_real_money_releases_separate_explicit",
                 "no_new_h3_or_h6_auto_enable", "no_additional_work_or_scheduler"):
        require(guard.get(flag) is True, "V3 safety/learning invariant absent: " + flag)
    for flag in ("orders", "real_money_actions", "automatic_strategy_promotion"):
        require(guard.get(flag) is False, "V3 automatic trading authority drift: " + flag)
    require(guard.get("max_concurrent_strategy_changing_shadows") == 1,
            "V3 parallel strategy changing shadows")
    require(guard.get("entry_cost_model_frozen_taker_each_side_pct") == 0.6 and
            guard.get("scout_and_stage2_eur") == [50, 50],
            "original V3 paper cost/sizing agreement changed")
    next_action = plan.get("immediate_action") or {}
    require(all(isinstance(next_action.get(k), str) and next_action[k].strip()
                for k in ("next", "avoid", "handoff_owner", "autonomy")),
            "no actionable V3 handoff or forbidden-change boundary")
    return {
        "baseline": "MERGED_PR161_ORIGINAL_USER_AGREEMENTS",
        "learning_status": "HISTORICAL_COVERAGE_VERIFIED_NOT_TRADING_OUTCOME",
        "prioritized_packages": [
            {k: x[k] for k in ("id", "order", "priority", "status", "owner")}
            for x in packages
        ],
        "h_statuses": [
            {"id": x["id"], "status": x["status"], "role": x["role"],
             "rule": x.get("rule")}
            for x in h
        ],
        "original_lessons": [
            {k: x[k] for k in ("id", "finding", "disposition", "implementation", "stage")}
            for x in items
        ],
        "historical_conflict_resolutions": [
            {"key": x["key"], "resolution": x["resolution"]} for x in conflicts
        ],
        "evidence": [
            {"id": x.get("id"), "status": x.get("status")}
            for x in plan.get("evidence_inventory", [])
        ],
        "next_action": next_action,
        "safety_gates": guard,
        "optional_context_fusion": {
            "status": (plan.get("optional_context_fusion") or {}).get("status"),
            "source_lanes": [
                {"stream_id": x.get("stream_id"), "group": x.get("group"),
                 "research_gate": x.get("gate"), "owner": x.get("owner")}
                for x in (plan.get("optional_context_fusion") or {}).get("lanes", [])
            ],
            "optional_data_neutral": (plan.get("optional_context_fusion") or {}).get("optional_missing_is_neutral"),
            "not_a_trading_authorization": True,
        },
        "not_a_runtime_or_economic_success_assertion": True,
    }


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
        payload["strategy_learning_routes"] = v3_decision_inheritance(root)
        payload["strategy_learning_routes"]["scope_warning"] = (
            "Original PR161 historical context; resolve future changes against "
            "current canonical ledger and live evidence, never release automatically."
        )
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
