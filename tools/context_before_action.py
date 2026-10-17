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



# Permanent IDs of observed and historically reviewed Paper strategy-learning
# themes, not a second policy version and not additional BUY filters.
PAPER_PHASE_LEARNING_IDS = frozenset((
    "V2_EARLY_DECISION_QUALITY_NOT_PERF_PROOF",
    "V2R3_TRADE_N1_DOES_NOT_CALIBRATE_RISK",
    "V2R3_LOW_CONVERSION_IS_DECISION_SELECTIVITY",
    "V2R3_WAIT_WATCH_NOT_IDEA_DEATH",
    "V2R3_CONTINUITY_INITIAL_SMALL_SAMPLE_OPTIMISM",
    "V2R3_RESISTANCE_CONFIRMATION_NOT_GLOBAL_LOOSENING",
    "V2R3_ALREADY_RUN_HAS_ADVERSE_PATH",
    "V2R3_SCANNER_SCORE_IS_NOT_PROFIT_RANK",
    "V2R3_RETRIGGERS_NOT_INDEPENDENT_WINNERS",
    "V2R3_MARKET_TIME_COHORTS_DIVERGE",
    "V2R3_LATE_MATURING_LOSERS_NOT_SILENTLY_DROPPED",
    "V2R4_TRIGGER_AND_MODEL_DECISION_SEPARATE",
    "V2R4_HIGH_UPSIDE_COINCIDES_WITH_BIG_DRAWDOWN",
    "V2R4_RETRO_PROXY_IS_NOT_REAL_MISSED_PROFIT",
    "V2R4_MATCHED_GOOD_AND_BAD_SETUP_FAMILIES",
    "V2R4_EXTENDED_REENTRY_VERSUS_BLANKET_PERMISSION",
    "V2R4_ORIGINAL_SETUP_TYPES_REQUIRE_DIFFERENT_CONTROL_CASES",
))



# Binding *cross-chat* infrastructure, research and Mini-PC commitments.
# Do not create a parallel development queue; protect the existing P0-P9 owners.
CROSS_CHAT_COMMITMENT_IDS = frozenset((
    "MINIPC_ENTRY_PIT_OHLC", "MINIPC_MISSED_MOVE_FUNNEL",
    "MINIPC_EXECUTION_COST_RESEARCH", "MINIPC_BOUNDED_LOCAL_REPLAY",
    "MINIPC_OUTAGE_DELAY_DIAGNOSTICS", "MINIPC_CAPACITY_GITHUB_OFFLOAD",
    "MINIPC_RAM_UPGRADE_GATE", "MINIPC_OPTIONAL_AI_DIAGNOSTICS",
    "SEPARATE_AUTONOMOUS_AI_TRADING_PROJECT", "FULL_DYNAMIC_KRAKEN_SPOT_EUR",
    "V2_HISTORY_AND_PAPER_LEARNING", "ENTRY_P1_P2_P3_EXPERIMENT_ONE_MODEL",
    "MARKET_PHASES_AND_SENTIMENT", "SOURCE_MANAGER_AUTONOMOUS_ACTIVE",
    "H2_H5_H8_H10_H11_OPTIONAL_CONTEXT", "H1_H3_H6_SHADOW_DISPOSITION",
    "H4_H7_H9_EXECUTION_META", "JANSEN_HISTORICAL_WALKFORWARD_TRIAL_LEDGER",
    "RESILIENCE_AND_FUTURE_REAL_MONEY_INHERITANCE",
    "CONTINUOUS_PROJECT_AUTONOMY_AND_CONTEXT",
))


def cross_chat_commitment_inheritance(root: Path, plan: dict,
                                      package_ids: set[str]) -> dict:
    """Prove major earlier user decisions remain routed, not executed."""
    x = plan.get("prior_cross_chat_commitments") or {}
    require(x.get("kind") == "V3_CROSS_CHAT_COMMITMENT_INHERITANCE_V1"
            and x.get("status") == "SOURCE_ROUTED_AND_EVIDENCE_GATED_NOT_ALL_LIVE",
            "cross-chat Mini-PC/V3 inheritance contract lost")
    for flag in ("no_new_task_queue", "no_new_scheduler", "no_new_runner",
                 "no_model_calls", "no_paper_activation", "no_real_money"):
        require(x.get(flag) is True, "cross-chat work changed authority: " + flag)
    require(x.get("owner") == "PROJECT_BACKLOG.md plus existing research/project-followthrough-routing-v1.json"
            and x.get("routing") == MAP,
            "cross-chat project owner/routing drift")
    rows = x.get("commitments") or []
    ids = [row.get("id") for row in rows if isinstance(row, dict)]
    require(len(ids) == len(rows) == len(set(ids))
            and CROSS_CHAT_COMMITMENT_IDS.issubset(set(ids)),
            "cross-chat/Mini-PC user commitment missing or duplicated")
    for row in rows:
        require(row.get("package_id") in package_ids
                and all(isinstance(row.get(key), str) and row[key].strip()
                        for key in ("source_path", "status", "next_gate")),
                "cross-chat commitment without actionable existing P0-P9 owner")
        path = row["source_path"]
        require(".." not in Path(path).parts and not Path(path).is_absolute()
                and (root / path).resolve().is_relative_to(root.resolve())
                and (root / path).is_file(),
                "cross-chat original source missing: " + path)
    require(any(row["id"] == "MINIPC_ENTRY_PIT_OHLC"
                and row["source_path"] == x.get("required_minipc_dependency")
                for row in rows),
            "Mini-PC analytics original strategy link lost")
    return {
        "kind": x["kind"], "coverage_count": len(rows),
        "commitments": rows,
        "routed_not_all_operational": True,
        "no_new_scheduler_or_second_strategy": True,
    }


def paper_phase_strategy_inheritance(root: Path, plan: dict, matrix: dict) -> dict:
    """Check 2026 V2/V2R3/V2R4 original Paper findings *by lineage*.

    Explicitly excludes technical-only incidents from PAPER-STRATEGY coverage.
    Structural checks cannot prove numerical correctness or successful trading.
    """
    x = plan.get("paper_phase_learning_crosswalk") or {}
    require(x.get("kind") == "V3_PREDECESSOR_PAPER_STRATEGIC_LEARNING_CROSSWALK_V1"
            and x.get("excludes_technical_diagnostics") is True
            and x.get("auto_activation") is False
            and x.get("model_calls_executed") == 0,
            "no separate technical-free Paper-learning inheritance contract")
    rows = x.get("findings") or []
    ids = [row.get("id") for row in rows if isinstance(row, dict)]
    require(len(ids) == len(rows) == len(set(ids)) and
            PAPER_PHASE_LEARNING_IDS.issubset(set(ids)),
            "original V2/V2R3/V2R4 Paper learning ID lost or duplicated")
    packages = {item["id"] for item in plan["package_order"]}
    lessons = {item["id"] for item in matrix["lessons"]}
    allowed_classes = {
        "QUALITATIVE_DECISION_ONLY", "PROSPECTIVE_CLEAN_PAPER",
        "PROSPECTIVE_PAPER_ZERO_BUY", "RETROSPECTIVE_OUTCOME_SELECTED_HYPOTHESIS",
    }
    project = root.resolve()
    for row in rows:
        require(row.get("evidence_class") in allowed_classes,
                "unknown Paper evidence status: " + str(row.get("id")))
        for field, min_chars in (("observed_finding", 20),
                                 ("strategic_disposition", 6),
                                 ("next_evidence_gate", 20)):
            require(isinstance(row.get(field), str) and len(row[field].strip()) >= min_chars,
                    "Paper finding lacks cause/disposition/next gate: " + str(row.get("id")))
        for field, known in (("v3_package_ids", packages),
                             ("matrix_lesson_ids", lessons)):
            values = row.get(field) or []
            require(isinstance(values, list) and bool(values)
                    and len(values) == len(set(values)) and set(values).issubset(known),
                    "Paper learning unlinked to existing V3 owner: " + str(row.get("id")))
        sources = row.get("source_paths") or []
        require(isinstance(sources, list) and bool(sources) and
                len(sources) == len(set(sources)),
                "Paper finding has no original evidence sources: " + str(row.get("id")))
        for source in sources:
            require(isinstance(source, str) and source
                    and not source.startswith("/") and ".." not in Path(source).parts
                    and (root / source).resolve().is_relative_to(project)
                    and (root / source).is_file(),
                    "original Paper source unavailable: " + str(source))
    final = read_json(root / "research/v2r3/strategy-adjustment-hypotheses-final-20261007.json")
    require(final.get("kind") == "V2R3_FINAL_HYPOTHESIS_DISPOSITIONS_V1"
            and final.get("status") == "FINAL_REVIEW_COMPLETE_NOT_ACTIVE",
            "final clean V2R3 paper dispositions not available")
    actual = {item.get("id") for item in final.get("dispositions", [])}
    strategic = set(x.get("v2r3_final_strategy_disposition_ids") or [])
    excluded = set(x.get("excluded_nontrading_final_disposition_ids") or [])
    require(bool(strategic) and not strategic.intersection(excluded)
            and strategic.union(excluded) == actual and
            excluded == {"HYP-06", "REVALIDATION_DELAY"},
            "V2R3 final strategy lesson or technical-only exclusion missing")
    return {
        "status": "ALL_HISTORICAL_PAPER_LEARNING_THEMES_ROUTED_NOT_ECONOMIC_PROOF",
        "coverage_count": len(rows),
        "original_final_v2r3_strategic_dispositions": sorted(strategic),
        "technical_only_exclusions": sorted(excluded),
        "findings": [
            {k: row[k] for k in
             ("id", "evidence_class", "source_paths", "observed_finding",
              "strategic_disposition", "v3_package_ids",
              "matrix_lesson_ids", "next_evidence_gate")}
            for row in rows
        ],
        "does_not_change_runtime_or_strategic_rules": True,
        "does_not_claim_validated_net_positive_trades": True,
    }


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
        "paper_phase_learning": paper_phase_strategy_inheritance(root, plan, matrix),
        "prior_cross_chat_commitments": cross_chat_commitment_inheritance(root, plan, set(package_ids)),
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




def project_component_owner_handoff(root: Path) -> dict:
    """Return every EXISTING registered project owner; not a runtime discovery claim.

    The monitoring registry owns functional streams and the already existing
    followthrough registry owns cross-cutting project areas. Never invent a
    physical deployment site from a Python module or a dated GitHub document.
    """
    streams_source = read_json(root / "research/monitoring-evidence-routing-v1.json")
    followthrough = read_json(root / "research/project-followthrough-routing-v1.json")
    require(streams_source.get("kind") == "MONITORING_EVIDENCE_ROUTING_V1",
            "missing canonical project stream register")
    require(followthrough.get("kind") == "PROJECT_WIDE_FOLLOWTHROUGH_ROUTING_V1",
            "missing canonical crosscut owner register")
    streams = streams_source.get("streams") or []
    areas = followthrough.get("extra_project_areas") or []
    stream_ids = [x.get("id") for x in streams]
    area_ids = [x.get("id") for x in areas]
    required = set(followthrough.get("required_stream_ids") or [])
    require(len(streams) == len(set(stream_ids))
            and required.issubset(set(stream_ids)) and len(required) >= 26,
            "stream owner coverage lost")
    require(len(areas) >= 9 and len(areas) == len(set(area_ids)),
            "crosscut owner coverage lost")
    results = []
    for item in streams:
        require(all(isinstance(item.get(field), str) and item[field].strip()
                    for field in ("id", "canonical_owner", "consumer", "next_gate")),
                "stream has no canonical owner or successor")
        results.append({
            "id": item["id"],
            "owner_type": "EXISTING_FUNCTIONAL_STREAM",
            "canonical_owner": item["canonical_owner"],
            "consumer": item["consumer"],
            "next_gate": item["next_gate"],
            "recorded_evidence_status": item.get("evidence_status"),
            "overlapping_domains": item.get("overlaps", []),
            "actual_runtime_location": "REQUIRES_ORIGINAL_DEPLOYMENT_EVIDENCE",
            "historical_status_is_not_live_proof": True,
        })
    for item in areas:
        require(all(isinstance(item.get(field), str) and item[field].strip()
                    for field in ("id", "owner", "gate"))
                and (root / item["owner"]).is_file(),
                "crosscut owner original evidence missing")
        results.append({
            "id": item["id"],
            "owner_type": "EXISTING_CROSSCUT_PROJECT_AREA",
            "canonical_owner": item["owner"],
            "consumer": "PROJECT_FOLLOWTHROUGH",
            "next_gate": item["gate"],
            "actual_runtime_location": "REQUIRES_ORIGINAL_DEPLOYMENT_EVIDENCE",
            "historical_status_is_not_live_proof": True,
        })
    return {
        "kind": "PROJECT_COMPONENT_OWNER_HANDOFF_V1",
        "status": "DECLARED_OWNERS_AND_GATES_NOT_INDEPENDENT_LIVE_DEPLOYMENT_PROOF",
        "functional_stream_count": len(streams),
        "crosscut_project_area_count": len(areas),
        "components": results,
        "runtime_owner_proof_rule": (
            "Before changing or installing anything, open the exact recorded "
            "technical source/deployment evidence, reconcile dated GitHub "
            "revisions with actual Mini-PC/GitHub/Supabase/Work execution, "
            "and only then perform the smallest TARGETED read-only validation. "
            "Never infer a Windows task merely from an H-component ID."
        ),
        "no_new_database_or_work_or_scheduler": True,
    }

def existing_operational_evidence_handoff(config: dict, source_index: list[dict]) -> dict:
    """Link existing MINI-PC evidence sources to on-demand preflights.

    This is strictly a source *routing* contract; this offline script cannot
    establish live host state, scheduled report persistence, GitHub upsert
    freshness, a Slack device notification or any trading authorization.
    """
    contract = config.get("existing_operational_evidence_handoff")
    require(isinstance(contract, dict) and
            contract.get("kind") == "EXISTING_OPERATIONAL_EVIDENCE_HANDOFF_V1",
            "original MINI-PC operational evidence route missing")
    fixed = {
        "owner": "PROJECT_BACKLOG.md#ENTWICKLUNGSLOOP_AUTOMATION_20261016",
        "issue_number": 353,
        "node_id": "MINI-PC",
        "cloud_current_table": "public.minipc_status_current",
        "cloud_alert_table": "public.minipc_status_alert_state",
        "cloud_daily_table": "public.minipc_daily_status",
        "native_task_key": "payload.native_task_readback",
        "daily_native_diagnostics_key": "payload.native_task_diagnostics",
        "daily_metric_provenance_key": "payload.metric_provenance",
        "github_original_watch_workflow_id": 371909131,
        "scope": "READ_ONLY_OPERATIONS_DIAGNOSTICS_NOT_TRADING_OR_V3_MODEL_PROOF",
    }
    for key, expected in fixed.items():
        require(contract.get(key) == expected,
                "original MINI-PC readback route drift: " + key)
    required_files = (
        "tools/minipc_cloud_evidence.py",
        "tools/minipc-watchdog.ps1",
        ".github/workflows/minipc-daily-status.yml",
    )
    require(contract.get("source_files") == list(required_files),
            "missing or substituted original MINI-PC source files")
    sources = {item["path"]: item for item in source_index}
    require(all(path in sources and len(sources[path]["sha256"]) == 64
                for path in required_files),
            "MINI-PC evidence sources not covered by canonical preflight fingerprint")
    flags = (
        "fresh_original_evidence_required",
        "reconcile_live_source_timestamps",
        "original_windows_deployment_separately_required",
        "github_schedule_best_effort",
        "no_live_cloud_query_in_context_packet",
        "no_slack_delivery_ack_in_context_packet",
        "no_paper_or_real_money_release",
        "no_new_scheduler_or_status_authority",
    )
    require(all(contract.get(key) is True for key in flags),
            "original MINI-PC evidence safety boundary changed")

    scan = contract.get("scanner_handoff")
    require(isinstance(scan, dict)
            and scan.get("kind") == "ORIGINAL_SCANNER_ARTIFACT_READBACK_ROUTE_V1",
            "original scanner handoff route missing")
    scan_fixed = {
        "source_workflow_file": ".github/workflows/scan.yml",
        "github_workflow_id_source": "GITHUB_API_ACTUAL_WORKFLOW_RUN_MATCH_REQUIRED",
        "latest_run_source": "EXISTING_GITHUB_ACTIONS_SCHEDULED_RUNS_NOT_GITHUB_SOURCE_FILE_DATE",
        "artifact_name_template": "chat-handoff-{run_id}-{run_attempt}",
        "artifact_payload_file": "candidates.jsonl",
        "artifact_retention_days": 7,
        "jsonl_schema_version": 1,
        "expected_event_kinds": [
            "scan_run_meta", "review_candidate_message", "candidate_snapshot",
            "market_context", "market_breadth",
        ],
        "review_action": "REVIEW_ONLY_NOT_ORDER",
    }
    for key, expected in scan_fixed.items():
        require(scan.get(key) == expected,
                "original scanner handoff route drift: " + key)
    scan_flags = (
        "read_via_original_artifact_download",
        "run_id_and_attempt_must_match_actual_run",
        "expires_after_retention",
        "no_implicit_delivery_to_scanner_detection_cloud",
        "no_implicit_v2r4_v3_model_consumption",
        "no_live_market_quote_or_trade_proof",
        "no_live_github_api_call_in_context_packet",
        "no_work_or_new_scheduler",
        "no_orders_or_strategy_release",
    )
    require(all(scan.get(key) is True for key in scan_flags),
            "original scanner handoff safety boundary changed")
    scan_path = scan_fixed["source_workflow_file"]
    require(scan_path in sources and len(sources[scan_path]["sha256"]) == 64,
            "original scanner workflow source not fingerprinted")
    return {
        "kind": contract["kind"],
        "status": "SOURCE_ROUTES_REGISTERED_LIVE_DATA_NOT_QUERIED",
        "owner": contract["owner"],
        "issue_number": contract["issue_number"],
        "source_paths": list(required_files),
        "source_fingerprints": {
            path: sources[path]["sha256"] for path in required_files
        },
        "node_id": contract["node_id"],
        "original_cloud_sources": {
            "current": contract["cloud_current_table"],
            "alert": contract["cloud_alert_table"],
            "daily": contract["cloud_daily_table"],
        },
        "existing_fields": {
            "native_task_readback": contract["native_task_key"],
            "daily_native_diagnostics": contract["daily_native_diagnostics_key"],
            "daily_metric_provenance": contract["daily_metric_provenance_key"],
        },
        "github_original_watch_workflow_id":
            contract["github_original_watch_workflow_id"],
        "scanner_artifact_handoff": {
            "kind": scan["kind"],
            "status": "SOURCE_ROUTE_ONLY_ACTUAL_RUN_ARTIFACT_NOT_FETCHED",
            "source_workflow_file": scan_path,
            "source_fingerprint": sources[scan_path]["sha256"],
            "artifact_name_template": scan["artifact_name_template"],
            "payload_file": scan["artifact_payload_file"],
            "retention_days": scan["artifact_retention_days"],
            "expected_event_kinds": list(scan["expected_event_kinds"]),
            "action": scan["review_action"],
            "actual_run_artifact_independently_verified": False,
            "scan_candidate_sent_to_evaluator_verified": False,
            "scan_candidate_written_to_cloud_verified": False,
            "v3_model_decision_verified": False,
            "trade_or_order_authorized": False,
            "no_new_scheduler_or_data_collector": True,
        },
        "fresh_original_host_cloud_evidence_required": True,
        "separate_github_schedule_run_and_cloud_alert_ack_required": True,
        "live_windows_deployment_independently_verified": False,
        "host_health_independently_verified": False,
        "v3_model_decision_or_trade_verified": False,
        "daily_scheduled_delivery_verified": False,
        "slack_device_push_ack_verified": False,
        "has_network_access": False,
        "no_new_scheduler_or_status_authority": True,
        "no_trading_or_release_authority": True,
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
        "project_component_owners": project_component_owner_handoff(root),
        "operational_evidence_handoff": existing_operational_evidence_handoff(config, index),
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
