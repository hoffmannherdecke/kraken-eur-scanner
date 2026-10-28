#!/usr/bin/env python3
"""On-demand, read-only context preflight for material project decisions.

Reads the existing canonical sources by default without network. An explicit
--live-brief fetches the current GitHub owner read-only and fails closed if
unavailable. No strategy mutation, scheduler or human/AI comprehension claim.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
from urllib import request
from urllib.error import URLError
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



# Existing canonical project; GitHub HTTP is opt-in and read-only. A GitHub
# statement about a Windows/Cloud ACK is not itself a fresh physical ACK.
CANONICAL_GITHUB_REPO = "hoffmannherdecke/kraken-eur-scanner"
GITHUB_API_BASE = "https://api.github.com/repos/" + CANONICAL_GITHUB_REPO


def _github_api_read(url: str) -> tuple[object, str]:
    require(url.startswith(GITHUB_API_BASE + "/"),
            "unapproved live owner API destination")
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "project-context-owner-readback"}
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    with request.urlopen(request.Request(url, headers=headers), timeout=12) as response:
        return json.loads(response.read().decode("utf-8")), response.headers.get("Link", "")


def live_owner_readback(work_domain: str, strategy_version: str | None,
                        fetcher=None, expected_main: str | None = None,
                        candidate_id: str | None = None) -> dict:
    """Fresh *GitHub-only* owner readback, not a release/Windows/Cloud proof.

    No cached PR number, secondary status database, schedule or mutation. If
    GitHub is unavailable or its shape is unexpected: fail CLOSED, never turn
    the previous Markdown snapshot into a new development task.
    """
    require(work_domain in {"project_general", "infrastructure", "operations",
                            "strategy_development", "strategy_release", "research"},
            "invalid live owner domain")
    require(not (work_domain == "strategy_release" and not strategy_version),
            "live strategy release requires named version")
    require(candidate_id is None or (work_domain == "strategy_release" and strategy_version == "V3"),
            "proposed gate is only valid for its named V3 release owner")
    getter = fetcher or _github_api_read
    head, _ = getter(GITHUB_API_BASE + "/commits/main")
    sha = head.get("sha") if isinstance(head, dict) else None
    require(isinstance(sha, str) and bool(re.fullmatch(r"[a-f0-9]{40}", sha)),
            "missing authenticated GitHub main SHA")
    if expected_main is not None:
        require(expected_main == sha, "GitHub main moved; re-read before action")
    owner_numbers = [353]
    if work_domain == "strategy_release" and strategy_version == "V3":
        owner_numbers.append(99)
    owners = []
    issue_versions = {}
    release_view = None
    for number in owner_numbers:
        issue, _ = getter(GITHUB_API_BASE + f"/issues/{number}")
        require(isinstance(issue, dict) and issue.get("number") == number
                and issue.get("state") == "open"
                and isinstance(issue.get("body"), str),
                f"issue #{number} owner unavailable; do not use historical headings")
        comments_url = GITHUB_API_BASE + f"/issues/{number}/comments?per_page=10"
        comments, link = getter(comments_url)
        require(isinstance(comments, list),
                f"issue #{number} comments unavailable")
        # GitHub returns comments oldest-first; use the last page, not the first
        # ten historical comments of a long-running owner.
        last = re.search(r'<([^<>]+)>;\s*rel="last"', link)
        if last:
            last_url = last.group(1)
            require(last_url.startswith(GITHUB_API_BASE + f"/issues/{number}/comments?"),
                    "unexpected GitHub owner pagination link")
            comments, _ = getter(last_url)
            require(isinstance(comments, list), "latest owner comments unavailable")
        recent = comments[-3:]
        require(all(isinstance(x, dict) and isinstance(x.get("body"), str)
                    and isinstance(x.get("html_url"), str) for x in recent),
                f"issue #{number} latest comment shape invalid")
        issue_versions[number] = (issue.get("updated_at"), hashlib.sha256(
            issue["body"].encode("utf-8")).hexdigest())
        if number == 99:
            release_view = existing_owner_gate_decision(issue["body"], candidate_id)
            if release_view["status"] == "OWNER_DECLARED_VIEW_CHECKED_NOT_ORIGINAL_RUNTIME_PROOF":
                last_id = recent[-1].get("id") if recent else None
                if last_id != release_view["last_owner_comment_id"]:
                    release_view = {
                        **release_view,
                        "status": "OWNER_ACTION_VIEW_STALE_HOLD_NEEDS_LATEST_ACK_RECONCILIATION",
                        "next_open_gate": None,
                        "candidate_verdict": "STALE_OWNER_VIEW_HOLD_NO_REWORK",
                        "ready_to_execute": False,
                    }
        owners.append({
            "issue": number,
            "url": issue.get("html_url"),
            "issue_updated_at": issue.get("updated_at"),
            "current_owner_header_excerpt": issue["body"][:4500],
            "latest_comments": [
                {"url": x["html_url"], "created_at": x.get("created_at"),
                 "excerpt": x["body"][:1800]} for x in recent
            ],
            "comments_are_not_independent_runtime_proof": True,
        })
    for number, version in issue_versions.items():
        repeat, _ = getter(GITHUB_API_BASE + f"/issues/{number}")
        require(isinstance(repeat, dict) and isinstance(repeat.get("body"), str)
                and (repeat.get("updated_at"), hashlib.sha256(
                    repeat["body"].encode("utf-8")).hexdigest()) == version,
                f"issue #{number} changed during owner readback; retry with fresh original")
    after, _ = getter(GITHUB_API_BASE + "/commits/main")
    require(isinstance(after, dict) and after.get("sha") == sha,
            "GitHub main changed during owner readback; retry before action")
    return {
        "kind": "PROJECT_EXISTING_OWNER_LIVE_GITHUB_READBACK_V1",
        "status": "CURRENT_GITHUB_OWNER_READBACK_ONLY_NOT_HOST_OR_CLOUD_ACK",
        "main_sha": sha,
        "work_domain": work_domain,
        "strategy_version": strategy_version or "UNSPECIFIED",
        "owners": owners,
        "named_release_gate": release_view,
        "source_and_staging_done_must_not_be_reopened_by_pending_runtime": True,
        "no_new_development_without_specific_new_defect_evidence": True,
        "next_gate_requires_original_proof_and_applicable_approval": True,
        "on_conflict": "UNKNOWN_NEEDS_TARGETED_ORIGINAL_ACK_NO_REWORK",
        "no_trading_or_release_authority": True,
    }



V3_GATE_START = "<!-- V3_EXISTING_OWNER_ACTION_VIEW_V1"
V3_GATE_END = "END_V3_EXISTING_OWNER_ACTION_VIEW_V1 -->"
GATE_LAYERS = ("SOURCE", "PHYSICAL_STAGING", "REAL_RUNTIME")
GATE_STATES = ("DONE", "BLOCKED", "PENDING")


def existing_owner_gate_decision(owner_body: str, candidate_id: str | None = None) -> dict:
    """Classify one proposed step using Issue #99's *existing* release owner.

    This is an anti-duplicate work-selection view, NOT a new authority, proof
    database, release approval, historical uptime claim or autonomous caller.
    A DONE runtime step must point to an actual original runtime ACK, but the
    owner link cannot substitute for independently checking that original.
    """
    require(isinstance(owner_body, str), "owner body missing for gate check")
    if owner_body.count(V3_GATE_START) != 1 or owner_body.count(V3_GATE_END) != 1:
        return {
            "status": "NO_CURRENT_STRUCTURED_OWNER_VIEW_HOLD",
            "next_open_gate": None,
            "candidate_verdict": "NO_ACTION_ALLOWED",
            "reason": "Read actual latest owner and original ACK; no fallback to historical checklist.",
            "ready_to_execute": False,
            "runtime_verified_independently": False,
        }
    raw = owner_body.split(V3_GATE_START, 1)[1].split(V3_GATE_END, 1)[0]
    try:
        view = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ContextGateError("CONTEXT_GATE_BLOCKED: malformed owner action view") from exc
    require(isinstance(view, dict)
            and view.get("kind") == "V3_EXISTING_RELEASE_OWNER_ACTION_VIEW_V1"
            and view.get("owner_issue") == 99
            and view.get("scope") == "V3_PAPER"
            and view.get("no_runtime_authority") is True
            and isinstance(view.get("as_of_utc"), str)
            and isinstance(view.get("last_owner_comment_id"), int)
            and view.get("last_owner_comment_id") > 0,
            "invalid release owner view identity or safety boundary")
    items = view.get("steps")
    require(isinstance(items, list) and 3 <= len(items) <= 30,
            "missing/oversized release owner action steps")
    ids = [item.get("id") for item in items if isinstance(item, dict)]
    require(len(ids) == len(items) == len(set(ids)), "duplicate/malformed release gate ID")
    first_open = None
    counts = {layer: {"done": 0, "open": 0} for layer in GATE_LAYERS}
    for item in items:
        require(isinstance(item.get("id"), str)
                and bool(re.fullmatch(r"[A-Z][A-Z0-9_]{3,70}", item["id"]))
                and item.get("layer") in GATE_LAYERS
                and item.get("state") in GATE_STATES
                and isinstance(item.get("evidence_url"), str)
                and bool(re.fullmatch(
                    r"https://github\.com/hoffmannherdecke/kraken-eur-scanner/issues/99#issuecomment-[0-9]+",
                    item["evidence_url"])),
                "release gate has missing or ungrounded owner evidence link")
        done = item["state"] == "DONE"
        if done:
            require(item.get("evidence_class") == (
                "ORIGINAL_RUNTIME_ACK" if item["layer"] == "REAL_RUNTIME"
                else "PHYSICAL_ACK" if item["layer"] == "PHYSICAL_STAGING"
                else "SOURCE_CI_ACK"),
                "release gate DONE without correct original evidence class")
        else:
            require(item.get("evidence_class") == "OWNER_BLOCKER",
                    "unclosed release gate cannot assert completed proof")
        counts[item["layer"]]["done" if done else "open"] += 1
        if not done and first_open is None:
            first_open = item
        if done and first_open is not None:
            raise ContextGateError(
                "CONTEXT_GATE_BLOCKED: owner view reopens completed stages out of order"
            )
    require(counts["REAL_RUNTIME"]["open"] >= 1,
            "owner view must not auto-declare V3 release complete")
    verdict = "NO_CANDIDATE_SUBMITTED"
    if candidate_id is not None:
        matched = next((x for x in items if x["id"] == candidate_id), None)
        if matched is None:
            verdict = "UNREGISTERED_WORK_HOLD_NEEDS_ORIGINAL_DEFECT_EVIDENCE"
        elif matched["state"] == "DONE":
            verdict = "REWORK_BLOCKED_ALREADY_EVIDENCED_DONE"
        elif first_open is None or candidate_id != first_open["id"]:
            verdict = "NOT_NEXT_OPEN_GATE_HOLD"
        else:
            verdict = "NEXT_GATE_BLOCKED_PENDING_REAL_ACK_AND_APPROVAL"
    return {
        "status": "OWNER_DECLARED_VIEW_CHECKED_NOT_ORIGINAL_RUNTIME_PROOF",
        "as_of_utc": view["as_of_utc"],
        "last_owner_comment_id": view["last_owner_comment_id"],
        "next_open_gate": (
            {"id": first_open["id"], "layer": first_open["layer"],
             "state": first_open["state"],
             "blocker_evidence_url": first_open["evidence_url"]}
            if first_open else None),
        "candidate_id": candidate_id,
        "candidate_verdict": verdict,
        "counts_from_declared_owner_view": counts,
        "rework_detected_this_query": int(
            verdict == "REWORK_BLOCKED_ALREADY_EVIDENCED_DONE"),
        "ready_to_execute": False,
        "runtime_verified_independently": False,
        "real_progress_requires_original_ack_not_pr": True,
        "past_duplicate_work_count": "UNKNOWN_NOT_COLLECTED",
        "historical_manual_corrections": "UNKNOWN_NOT_COLLECTED",
        "owner_issue_url": "https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/99",
    }


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
    runner = contract.get("projectwide_reviewed_runner")
    require(isinstance(runner, dict)
            and runner.get("kind") == "PROJECTWIDE_REVIEWED_MINIPC_RUNNER_HANDOFF_V1",
            "projectwide existing reviewed runner handoff missing")
    runbook = "docs/minipc-runner-bounded-windows-v1.md"
    require(runner.get("canonical_runbook") == runbook
            and runbook in sources
            and len(sources[runbook]["sha256"]) == 64,
            "reviewed runner source not present in every context packet")
    require(runner.get("github_issue") == 353
            and runner.get("private_issue") == 13
            and runner.get("private_repository") ==
                "hoffmannherdecke/kraken-readonly-bridge"
            and runner.get("windows_task_name") ==
                "CryptoSupport - Bounded Runner Window",
            "original reviewed runner ownership drift")
    require(runner.get("windows_task_schedule_enabled_host_confirmed") is True
            and runner.get("first_unattended_periodic_window_e2e") ==
                "PASS_ONE_UNATTENDED_NATURAL_WINDOW_ORIGINAL_HOST_20261019"
            and runner.get("no_unreviewed_powershell_or_elevated_host_access") is True
            and runner.get("no_trading_paper_cloud_order_or_budget_authority") is True
            and runner.get("no_paid_github_upgrade") is True
            and runner.get("no_new_project_manager_or_schedule") is True
            and runner.get("new_chat_auto_import_guaranteed") is False,
            "reviewed runner safety and evidence boundary drift")

    diag = runner.get("reviewed_readonly_log_diagnostics")
    diag_script = "tools/minipc_runner_tasks/log_status_summary.ps1"
    require(isinstance(diag, dict)
            and diag.get("task_name") == "log_status_summary"
            and diag.get("source_script") == diag_script
            and diag_script in sources
            and len(sources[diag_script]["sha256"]) == 64,
            "reviewed reusable log diagnostics source not present in context packet")
    require(diag.get("reviewed_public_main_merge_sha") ==
                "5e6e822d54e42359665a949e04d6d0cf9b64ffbe"
            and diag.get("source_ci_status") == "MERGED_SOURCE_AND_REVIEW_PASS"
            and diag.get("actual_windows_task_e2e") == "PENDING_ORIGINAL_HOST_ACK"
            and diag.get("actual_source_file_acl") == "UNKNOWN_UNTIL_RUNNER_READBACK"
            and diag.get("original_private_issue") == 13
            and diag.get("max_files_per_root") == 5
            and diag.get("max_tail_lines_per_file") == 4000
            and set(diag.get("all_project_scopes", [])) ==
                {"strategy", "architecture", "operations", "research"},
            "reviewed log diagnostics recorded evidence or scope drift")
    diag_boundaries = (
        "request_via_existing_workflow_only",
        "no_raw_log_lines_or_filenames",
        "no_user_pasted_shellcode",
        "no_windows_acl_changes",
        "prefer_before_manual_powershell_for_applicable_tasks",
        "no_repeated_already_completed_example",
        "no_new_workflow_runner_scheduler_subscription",
        "no_trading_cloud_model_budget_release",
    )
    require(all(diag.get(flag) is True for flag in diag_boundaries),
            "reviewed log diagnostics permission boundary drift")
    require(diag.get("approved_log_roots") == [
                r"C:\Users\ADMIN\Trading\Logs",
                r"C:\CryptoSupport\Logs"],
            "reviewed log diagnostics roots drift")

    maintenance = runner.get("reviewed_windows_maintenance_diagnostics")
    maintenance_script = "tools/minipc_runner_tasks/windows_maintenance_snapshot.ps1"
    require(isinstance(maintenance, dict)
            and maintenance.get("task_name") == "windows_maintenance_snapshot"
            and maintenance.get("source_script") == maintenance_script
            and maintenance_script in sources
            and len(sources[maintenance_script]["sha256"]) == 64
            and maintenance.get("actual_windows_task_e2e") ==
                "PASS_RESTRICTED_HOST_RUN_AND_SANITIZED_GITHUB_STATUS"
            and maintenance.get("request_via_existing_workflow_only") is True
            and maintenance.get("no_arbitrary_shell_or_admin") is True
            and maintenance.get("no_service_task_update_or_restart") is True
            and maintenance.get("no_cpu_or_v3_release_authority") is True
            and maintenance.get("no_new_scheduler_or_work") is True
            and maintenance.get("safe_github_job_log_marker") ==
                "MINIPC_MAINTENANCE_SAFE_SUMMARY_V1"
            and maintenance.get("no_raw_log_or_unbounded_output") is True
            and maintenance.get("host_original_ack_still_required") is False
            and maintenance.get("post_window_safe_pause_original_ack_pending") is False
            and maintenance.get("no_acl_elevation_for_missing_scheduler_readback") is True
            and maintenance.get("no_broad_or_admin_acl_grant") is True
            and runner.get("first_unattended_periodic_window_evidence", {}).get("safe_pause") == "PASS"
            and maintenance.get("original_host_evidence", {}).get("task_readback") == "READ_OK"
            and maintenance.get("original_host_evidence", {}).get("task_read_method") == "CMDLET"
            and maintenance.get("original_host_evidence", {}).get("task_cmdlet_probe") == "READ_OK"
            and maintenance.get("target_task_read_access_original_host") ==
                "PASS_NATIVE_CMDLET_AFTER_SINGLE_TASK_READ_ACE"
            and maintenance.get("original_host_evidence", {}).get("original_workflow_run_id") == 39257496377
            and maintenance.get("original_host_evidence", {}).get("bounded_scheduler_task_metadata") ==
                "READ_OK_RESTRICTED_ACCOUNT"
            and maintenance.get("original_host_evidence", {}).get("post_window_safe_pause") ==
                "PENDING_ORIGINAL_HOST_READBACK"
            and set(maintenance.get("all_project_scopes", [])) ==
                {"strategy", "architecture", "operations", "research"},
            "reviewed Windows maintenance source or original-host gate drift")

    reuse = runner.get("capability_reuse_policy")
    reuse_doc = "docs/minipc-powershell-capability-reuse-v1.md"
    bundle_script = "tools/minipc_runner_tasks/operations_readonly_bundle.ps1"
    require(isinstance(reuse, dict)
            and reuse.get("kind") == "MINIPC_REUSE_FIRST_POLICY_V1"
            and reuse.get("canonical_policy") == reuse_doc
            and reuse.get("source_bundle") == bundle_script
            and reuse_doc in sources
            and bundle_script in sources
            and len(sources[reuse_doc]["sha256"]) == 64
            and len(sources[bundle_script]["sha256"]) == 64
            and reuse.get("source_task_name") == "operations_readonly_bundle"
            and reuse.get("child_source_tasks") ==
                ["host_safety_probe", "windows_maintenance_snapshot", "log_status_summary"]
            and reuse.get("safe_result_marker") ==
                "MINIPC_OPERATIONS_BATCH_SAFE_SUMMARY_V1"
            and reuse.get("no_repeat_runner_e2e_without_changed_boundary") is True
            and reuse.get("existing_request_and_single_ack_only_for_previously_approved_tasks") is True
            and reuse.get("new_capabilities_one_review_and_targeted_test") is True
            and reuse.get("new_acl_or_write_rights_require_separate_permission") is True
            and reuse.get("no_new_workflow_scheduler_or_manager") is True
            and reuse.get("no_arbitrary_powershell_or_parameters") is True
            and reuse.get("no_admin_trading_writer_or_budget_authority") is True
            and reuse.get("runtime_evidence_not_established_by_context_packet") is True
            and reuse.get("original_host_receipt_must_be_independently_observed") is True
            and reuse.get("bundle_original_host_status") ==
                "PASS_ONE_RESTRICTED_SOURCE_PINNED_WINDOWS_RUN"
            and reuse.get("bundle_original_host_evidence", {}).get("private_original_workflow_run_id") == 39269905027
            and reuse.get("bundle_original_host_evidence", {}).get("overall_task_execution") == "COMPLETE"
            and reuse.get("bundle_original_host_evidence", {}).get("log_sources_readback") == "PARTIAL_OR_UNAVAILABLE"
            and reuse.get("future_write_acl_currently_granted") is True
            and reuse.get("write_scope_is_only_approved_workspace") is True
            and reuse.get("next_permission_stage") ==
                "SCOPED_WORKSPACE_HOST_PASS_NO_ADDITIONAL_PERMISSIONS"
            and set(reuse.get("all_project_scopes", [])) ==
                {"strategy", "architecture", "operations", "research"},
            "projectwide reusable PowerShell capability policy or permission boundary drift")

    workspace = runner.get("scoped_workspace") or {}
    fixed_v3 = runner.get("reviewed_v3_fixed_paths") or {}
    ws_script = "tools/minipc_runner_tasks/workspace_report.ps1"
    v3_script = "tools/minipc_runner_tasks/v3_fixed_paths_readonly.ps1"
    require(workspace.get("kind") == "SCOPED_WORKSPACE_ONE_DIR_V1"
            and workspace.get("approved_directory") == r"C:\CryptoSupport\Workspace"
            and workspace.get("reviewed_task") == ws_script
            and workspace.get("user_scope_approved") is True
            and workspace.get("source_review_pass") is True
            and workspace.get("restricted_task_write_ack") == "PASS_ORIGINAL_JOB_39283677017"
            and workspace.get("original_host_evidence", {}).get("write_read_delete_probe") == "PASS"
            and workspace.get("original_host_evidence", {}).get("dated_not_live") is True
            and workspace.get("no_administrator_role_for_runner") is True
            and ws_script in sources and len(sources[ws_script]["sha256"]) == 64,
            "scoped Workspace source/host evidence drift")
    require(fixed_v3.get("task_name") == "v3_fixed_paths_readonly"
            and fixed_v3.get("source_script") == v3_script
            and fixed_v3.get("source_review_status") == "MERGED_SOURCE_PR443_AND_PR444"
            and fixed_v3.get("original_host_status") == "PASS_ORIGINAL_JOB_39313293207"
            and fixed_v3.get("original_host_evidence", {}).get("staging_nested_scan") == "TOO_MANY_CHILDREN"
            and fixed_v3.get("original_host_evidence", {}).get("dated_not_live") is True
            and fixed_v3.get("no_runtime_mutation") is True
            and fixed_v3.get("no_free_shell_or_arbitrary_paths") is True
            and ws_script in sources and v3_script in sources
            and len(sources[v3_script]["sha256"]) == 64,
            "V3 fixed-paths source/host evidence drift")

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
        "projectwide_reviewed_runner": {
            "kind": runner["kind"],
            "status": "FIRST_NATURAL_SAFE_PAUSE_HOST_PASS_CPU_MAINTENANCE_REQUIRES_FRESH_GATE",
            "canonical_runbook": runbook,
            "source_fingerprint": sources[runbook]["sha256"],
            "owner_issue": runner["github_issue"],
            "private_runner_issue": runner["private_issue"],
            "private_runner_repository": runner["private_repository"],
            "private_approved_workflow_file": runner["private_approved_workflow_file"],
            "private_approved_workflow_sha": runner["private_approved_workflow_sha"],
            "task_source": runner["public_reviewed_task_dir"],
            "capability_reuse_policy": {
                "kind": reuse["kind"],
                "canonical_policy": reuse_doc,
                "policy_source_fingerprint": sources[reuse_doc]["sha256"],
                "source_bundle": bundle_script,
                "bundle_source_fingerprint": sources[bundle_script]["sha256"],
                "source_task_name": reuse["source_task_name"],
                "child_source_tasks": list(reuse["child_source_tasks"]),
                "safe_result_marker": reuse["safe_result_marker"],
                "no_repeat_runner_e2e_without_changed_boundary": True,
                "existing_request_and_single_ack_only_for_previously_approved_tasks": True,
                "new_capabilities_one_review_and_targeted_test": True,
                "new_acl_or_write_rights_require_separate_permission": True,
                "no_new_workflow_scheduler_or_manager": True,
                "no_arbitrary_powershell_or_parameters": True,
                "runtime_evidence_not_established_by_context_packet": True,
                "original_host_receipt_must_be_independently_observed": True,
                "bundle_original_host_status": reuse["bundle_original_host_status"],
                "bundle_original_host_evidence": dict(reuse["bundle_original_host_evidence"]),
                "next_permission_stage": reuse["next_permission_stage"],
                "future_write_acl_currently_granted": True,
                "workspace_only": True,
            },
            "reviewed_readonly_log_diagnostics": {
                "task": diag["task_name"],
                "source_script": diag_script,
                "source_fingerprint": sources[diag_script]["sha256"],
                "source_review_commit": diag["reviewed_public_main_merge_sha"],
                "source_ci_status": diag["source_ci_status"],
                "actual_windows_task_e2e": diag["actual_windows_task_e2e"],
                "actual_source_file_acl": diag["actual_source_file_acl"],
                "original_private_issue": diag["original_private_issue"],
                "use_existing_runner_only": True,
                "prefer_before_manual_powershell": True,
                "no_user_supplied_shellcode_or_acl_changes": True,
            },

            "reviewed_windows_maintenance_diagnostics": {
                "task": maintenance["task_name"],
                "source_script": maintenance_script,
                "source_fingerprint": sources[maintenance_script]["sha256"],
                "source_ci_status": maintenance["source_ci_status"],
                "actual_windows_task_e2e": maintenance["actual_windows_task_e2e"],
                "use_existing_runner_only": True,
                "no_arbitrary_shell_or_admin": True,
                "no_runtime_or_reboot_authority": True,
                "safe_github_job_log_marker": maintenance["safe_github_job_log_marker"],
                "original_host_evidence": dict(maintenance["original_host_evidence"]),
                "host_original_ack_still_required": False,
                "post_window_safe_pause_original_ack_pending": False,
                "first_window_host_evidence": dict(runner["first_unattended_periodic_window_evidence"]),
                "no_acl_elevation_for_missing_scheduler_readback": True,
                "no_broad_or_admin_acl_grant": True,
                "target_task_read_access_original_host": maintenance["target_task_read_access_original_host"],
            },
            "scoped_workspace": {
                "task": workspace["source_task_name"],
                "source_script": ws_script,
                "source_fingerprint": sources[ws_script]["sha256"],
                "approved_directory": workspace["approved_directory"],
                "source_review_pass": workspace["source_review_pass"],
                "restricted_task_write_ack": workspace["restricted_task_write_ack"],
                "original_host_evidence": dict(workspace["original_host_evidence"]),
                "live_write_access_reverified_by_this_packet": False,
                "no_unscoped_writes": True,
            },
            "reviewed_v3_fixed_paths": {
                "task": fixed_v3["task_name"],
                "source_script": v3_script,
                "source_fingerprint": sources[v3_script]["sha256"],
                "source_review_status": fixed_v3["source_review_status"],
                "original_host_status": fixed_v3["original_host_status"],
                "original_host_evidence": dict(fixed_v3["original_host_evidence"]),
                "live_v3_paths_reverified_by_this_packet": False,
                "no_arbitrary_path_query": True,
            },
            "request_format": runner["request_format"],
            "windows_task_name": runner["windows_task_name"],
            "windows_schedule_enabled_at_original_user_photo":
                runner["windows_task_schedule_enabled_host_confirmed"],
            "manual_one_off_task_result":
                runner["manual_one_off_e2e"]["last_task_result"],
            "first_unattended_periodic_window_e2e":
                runner["first_unattended_periodic_window_e2e"],
            "live_host_status_independently_verified_by_this_packet": False,
            "no_arbitrary_shell_or_trading_authority": True,
            "no_paid_github_upgrade": True,
            "new_chat_auto_import_guaranteed": False,
        },
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


def interactive_chat_goal_handoff(root: Path, source_index: list[dict]) -> dict:
    """Carry the *original* AGENTS.md chat goal rule in every context packet.

    Keep the policy in its existing canonical file, not a second competing
    conversation manager or a copy of the rule in JSON config.
    """
    path = "AGENTS.md"
    source = next((item for item in source_index if item["path"] == path), None)
    require(source is not None, "canonical interactive chat rule not indexed")
    text = (root / path).read_text(encoding="utf-8")
    heading = "## Dialog-Arbeitsmodus: vereinbartes Ziel statt einzelner Arbeitsblock"
    require(text.count(heading) == 1, "canonical interactive chat rule missing or duplicated")
    section = text.split(heading, 1)[1].split("\n## ", 1)[0].strip()
    required = (
        "normale interaktive Chat-Arbeit",
        "vereinbarte, tatsächlich prüfbare Zielzustand",
        "selben laufenden Antwort-/Tool-Durchgang",
        "ohne neue Nutzerantwort weiterarbeiten",
        "Eine abschließende Antwort erst",
        "Eine finale Chat-Antwort startet keine heimliche asynchrone Weiterarbeit",
        "Freigaben unverändert",
    )
    require(all(term in section for term in required),
            "canonical interactive chat rule incomplete")
    return {
        "kind": "INTERACTIVE_CHAT_GOAL_CONTINUATION_HANDOFF_V1",
        "canonical_source": path,
        "source_sha256": source["sha256"],
        "applies_to": "ALL_PROJECT_SCOPES_NORMAL_CHATS_NOT_ONLY_WORK",
        "instruction_from_original": heading + "\n\n" + section,
        "progress_note_is_not_a_stop": True,
        "finish_at_verified_goal_or_real_blocker": True,
        "new_chat_must_actively_load_context": True,
        "automatic_new_chat_bootstrap_guaranteed": False,
        "no_new_scheduler_or_execution_authority": True,
    }


def existing_minipc_task_source_names(root: Path) -> list[str]:
    """Discover source filenames only, without inventing Windows host permission.

    Executability still requires a protected-main merge, the existing CI task
    allowlist and the unchanged pinned private/Windows pre-job gate.
    """
    folder = root / "tools/minipc_runner_tasks"
    require(folder.is_dir() and not folder.is_symlink(),
            "reviewed Mini-PC source directory missing or unsafe")
    candidates = sorted(folder.glob("*.ps1"))
    require(bool(candidates), "no reviewed Mini-PC task source files found")
    for path in candidates:
        require(path.is_file() and not path.is_symlink()
                and re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", path.stem) is not None,
                "invalid Mini-PC source entry")
    return [path.stem for path in candidates]


def context_reading_plan(config: dict, index: list[dict],
                         work_domain: str, strategy_version: str | None) -> dict:
    """Task-specific reading order; retain full source index for integrity gates."""
    policy = config.get("context_priority_policy")
    require(isinstance(policy, dict)
            and policy.get("kind") == "PROJECT_CONTEXT_RELEVANCE_AND_STATUS_PRECEDENCE_V1",
            "missing evidence-priority contract")
    for flag in ("date_alone_does_not_prove_active_state",
                 "completed_maintenance_not_reopened_by_older_checkbox",
                 "no_old_v3_history_as_generic_gate",
                 "incomplete_or_conflicting_evidence_requires_targeted_readback",
                 "full_source_index_and_pr_fingerprints_unchanged",
                 "no_runtime_or_release_authority"):
        require((policy.get("rules") or {}).get(flag) is True,
                "weakened current-status safeguard: " + flag)
    paths = {x["path"] for x in index}
    always = policy.get("always_read")
    focus = policy.get("domain_focus")
    require(isinstance(always, list) and len(always) == len(set(always))
            and set(always).issubset(paths)
            and isinstance(focus, dict)
            and set(focus) == {"project_general", "infrastructure", "operations",
                               "strategy_development", "strategy_release", "research"},
            "bad source priority registry")
    targets = focus[work_domain]
    require(isinstance(targets, list) and len(targets) == len(set(targets)),
            "duplicated source priorities")
    preferred = [x for x in targets if x in paths]
    if strategy_version != "V3":
        preferred = [x for x in preferred
                     if not x.startswith(("research/v3/", "docs/v3-"))]
    if strategy_version == "V3" and work_domain in ("strategy_release", "strategy_development"):
        preferred.extend(x for x in (
            "docs/v3-controlled-paper-cutover-20261011.md",
            "research/v3/v3-consolidated-strategy-integration-plan-20261011.json"
        ) if x in paths)
    priority = list(dict.fromkeys(always + preferred))
    return {
        "kind": policy["kind"],
        "work_domain": work_domain,
        "strategy_version": strategy_version or "UNSPECIFIED",
        "priority_source_paths": priority,
        "integrity_only_source_count": len(index) - len(priority),
        "complete_source_index_preserved": True,
        "historical_plans_not_open_tasks": True,
        "evidence_precedence": list(policy["proof_first_order"]),
        "live_status": policy["live_evidence"],
        "conflict_resolution": "UNKNOWN_NEEDS_TARGETED_OWNER_READBACK",
    }


def project_work_domain_boundary(root: Path, config: dict, work_domain: str, strategy_version: str | None = None) -> dict:
    """Project-wide intent routing is independent of any strategy version.

    Scope chooses which sources are read. A work domain chooses the applicable
    owner/gate family. Neither a hardware change nor a source reference to V3
    grants or demands a V3 strategy release.
    """
    policy = config.get("work_domain_policy")
    require(isinstance(policy, dict) and
            policy.get("kind") == "PROJECTWIDE_WORK_DOMAIN_BOUNDARY_V1"
            and policy.get("default_domain") == "project_general"
            and policy.get("scope_is_knowledge_index_not_release_authority") is True
            and policy.get("hardware_upgrade_alone_never_creates_strategy_gate") is True
            and policy.get("named_strategy_release_requires_specific_owner_and_actual_dependencies") is True
            and policy.get("v3_histories_are_context_only_unless_v3_is_the_named_subject") is True
            and policy.get("future_strategy_versions_inherit_projectwide_collaboration_rules") is True
            and policy.get("no_new_manager_scheduler_or_approval") is True,
            "project-wide work-domain isolation policy missing or weakened")
    domains = policy.get("domains")
    expected = {
        "project_general": ("PROJECT_COORDINATION", False),
        "infrastructure": ("HARDWARE_AND_MINIPC_CAPABILITIES", False),
        "operations": ("OPERATIONS_AND_RECOVERY", False),
        "strategy_development": ("VERSIONED_STRATEGY_RESEARCH_AND_IMPLEMENTATION", False),
        "strategy_release": ("EXPLICIT_NAMED_STRATEGY_RELEASE_OWNER", True),
        "research": ("RESEARCH_SOURCE_AND_EVIDENCE_OWNER", False),
    }
    require(isinstance(domains, dict) and set(domains) == set(expected)
            and all(isinstance(domains[key], dict)
                    and domains[key].get("owner_lane") == lane
                    and domains[key].get("requires_strategy_release") is release
                    for key, (lane, release) in expected.items()),
            "project-wide work-domain definitions changed")
    follow = read_json(root / "research/project-followthrough-routing-v1.json")
    follow_ctx = follow.get("context_preflight") or {}
    require(follow_ctx.get("work_domain_policy") ==
            "research/context-before-action-routing-v1.json#work_domain_policy"
            and follow_ctx.get("release_routing") ==
            "EXPLICIT_NAMED_STRATEGY_RELEASE_ONLY_NOT_GENERAL_HARDWARE_OR_PROJECT_WORK"
            and follow_ctx.get("scope_is_not_release_approval") is True,
            "project manager does not inherit central project work domains")
    require(work_domain in expected, "unknown project work domain: " + str(work_domain))
    if strategy_version is not None:
        require(bool(re.fullmatch(r"V[1-9][0-9]*(?:R[1-9][0-9]*)?", strategy_version)),
                "invalid named strategy version")
    lane, release = expected[work_domain]
    return {
        "kind": policy["kind"],
        "work_domain": work_domain,
        "strategy_version": strategy_version or "UNSPECIFIED",
        "named_strategy_version_required_for_release": release and strategy_version is None,
        "owner_lane": lane,
        "requires_named_strategy_release_owner": release,
        "strategy_specific_release_gates_applicable": release,
        "v3_specific_history_is_nonbinding_for_this_task": work_domain not in (
            "strategy_development", "strategy_release"),
        "hardware_change_is_not_a_strategy_milestone": work_domain == "infrastructure",
        "scope_is_not_a_task_dependency": True,
        "project_rules_survive_v3_and_future_strategy_transitions": True,
        "only_existing_owner_and_task_specific_original_evidence_can_create_a_dependency": True,
        "not_a_runtime_or_release_authorization": True,
    }


def project_next_action_selector(operational: dict, root: Path, work_domain: str = "project_general", strategy_version: str | None = None) -> dict:
    """Route self-service before manual steps; no automatic tool availability claims."""
    runner = operational["projectwide_reviewed_runner"]
    reuse = runner["capability_reuse_policy"]
    workspace = runner["scoped_workspace"]
    v3 = runner["reviewed_v3_fixed_paths"]
    return {
        "kind": "PROJECT_NEXT_ACTION_SELECTOR_V1",
        "decision_order": [
            "USE_AVAILABLE_CONNECTED_GITHUB_OR_CLOUD_READBACK_FIRST",
            "REUSE_EXISTING_SOURCE_REVIEWED_MINIPC_TASK_IF_RELEVANT",
            "ASK_USER_FOR_SMALLEST_SAFE_PHYSICAL_STEP_ONLY_IF_NEEDED",
        ],
        "bounded_capabilities": [
            {"task": reuse["source_task_name"], "prior_host_ack": reuse["bundle_original_host_status"],
             "purpose": "BOUNDED_OPERATIONS_READONLY", "source": reuse["source_bundle"]},
            {"task": workspace["task"], "prior_host_ack": workspace["restricted_task_write_ack"],
             "purpose": "FIXED_APPROVED_WORKSPACE_ONLY", "source": workspace["source_script"]},
            {"task": v3["task"], "prior_host_ack": v3["original_host_status"],
             "purpose": "FIXED_V3_PATH_MARKERS_ONLY", "source": v3["source_script"],
             "applicable_to_current_work_domain": (work_domain in ("strategy_development", "strategy_release") and strategy_version == "V3"),
             "catalogue_entry_is_not_a_recommendation": True},
        ],
        "repository_task_source_names": existing_minipc_task_source_names(root),
        "repository_inventory_is_not_host_approval": True,
        "connected_tool_availability": "MUST_CHECK_IN_CURRENT_CHAT",
        "work_domain": work_domain,
        "strategy_version": strategy_version or "UNSPECIFIED",
        "no_automatic_v3_task_selection_for_project_or_infrastructure": True,
        "host_online_now": "NOT_CHECKED_BY_SOURCE_PACKET",
        "before_manual_request": "STATE_WHICH_EXISTING_SAFE_TOOL_WAS_CHECKED_AND_WHY_IT_CANNOT_FINISH",
        "historical_ack_not_live_proof": True,
        "no_arbitrary_shell_or_admin_rights": True,
        "no_new_scheduler_or_runtime_execution": True,
    }


def build(root: Path, scope: str, work_domain: str = "project_general", strategy_version: str | None = None) -> dict:
    config, entries = routed_sources(root, scope)
    boundary = project_work_domain_boundary(root, config, work_domain, strategy_version)
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
    operational = existing_operational_evidence_handoff(config, index)
    payload = {
        "kind": "CONTEXT_BEFORE_ACTION_PACKET_V1",
        "scope": scope,
        "work_domain_boundary": boundary,
        "status": "SOURCE_ROUTING_PASS_NEEDS_SUBSTANTIVE_REVIEW",
        "source_index": index,
        "current_reading_plan": context_reading_plan(config, index, work_domain, strategy_version),
        "declared_status": declared,
        "control_decision_ack_reconciliation": review_receipts(root, state),
        "project_component_owners": project_component_owner_handoff(root),
        "interactive_chat_goal": interactive_chat_goal_handoff(root, index),
        "operational_evidence_handoff": operational,
        "next_action_selector": project_next_action_selector(operational, root, work_domain, strategy_version),
        "limitations": [
            "Source hashes attest presence/version, not reading, semantic understanding or correctness.",
            "GitHub current-state is declared/datable, not independent live Supabase/MINI-PC evidence.",
            "An ACK can close a review while its original next-control-decision remains on file.",
            "External ChatGPT Work/automation prompts and unseen conversations are not GitHub-readable.",
            "This packet grants no trading, strategy promotion, secrets, scheduling or release authority.",
        ],
        "required_next_step": "Use connected GitHub/Cloud first; then check reviewed bounded Mini-PC tasks. Read original decisions and request manual user action only after documenting a concrete blocker.",
    }
    if scope in ("strategy", "research") and work_domain in ("strategy_development", "strategy_release") and strategy_version == "V3":
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


def compact_decision_brief(packet: dict) -> dict:
    """Fast human/agent orientation; never replaces original source review.

    All fields are derived from the already validated full packet, not a second
    registry, cache, status authority or external request.
    """
    selector = packet["next_action_selector"]
    plan = packet["current_reading_plan"]
    routed = [item["path"] for item in packet["source_index"]]
    priority = [path for path in (
        "AGENTS.md", "project-current-state.json",
        "PROJECT_BACKLOG.md", "docs/project-control-plane-governance.md"
    ) if path in routed]
    return {
        "kind": "CONTEXT_BEFORE_ACTION_DECISION_BRIEF_V1",
        "scope": packet["scope"],
        "work_domain": packet["work_domain_boundary"]["work_domain"],
        "named_strategy_release_owner_required": packet["work_domain_boundary"]["requires_named_strategy_release_owner"],
        "status": packet["status"],
        "fingerprint": packet["fingerprint"],
        "declared_as_of_utc": packet["declared_status"]["as_of_utc"],
        "owner": "PROJECT_BACKLOG.md / Issue #353 for project-wide execution",
        "decision_order": list(selector["decision_order"]),
        "bounded_capabilities": list(selector["bounded_capabilities"]),
        "repository_task_source_names": list(selector["repository_task_source_names"]),
        "repository_inventory_is_not_host_approval": True,
        "manual_user_action_only_after": selector["before_manual_request"],
        "connected_tools": selector["connected_tool_availability"],
        "live_host": selector["host_online_now"],
        "priority_sources_to_read": plan["priority_source_paths"],
        "historical_plans_not_open_tasks": plan["historical_plans_not_open_tasks"],
        "evidence_precedence": plan["evidence_precedence"],
        "strategy_version": plan["strategy_version"],
        "routed_source_count": len(routed),
        "full_packet_required_before_material_change": True,
        "full_packet_command": ("python tools/context_before_action.py --scope " + packet["scope"]
                                + " --work-domain " + plan["work_domain"]
                                + ("" if plan["strategy_version"] == "UNSPECIFIED"
                                   else " --strategy-version " + plan["strategy_version"])),
        "no_live_runtime_or_trading_authority": True,
        "history_or_hash_is_not_live_proof": True,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--scope", required=True,
                   choices=("strategy", "architecture", "operations", "research"))
    p.add_argument("--work-domain", default="project_general",
                   choices=("project_general", "infrastructure", "operations",
                            "strategy_development", "strategy_release", "research"),
                   help="Task area independent from source scope; only named strategy_release uses a strategy release owner.")
    p.add_argument("--strategy-version", default=None,
                   help="Explicit target like V3 or V2R4; scope alone never selects a strategy.")
    p.add_argument("--brief", action="store_true",
                   help="Print one short validated action/owner guide, not the full source packet.")
    p.add_argument("--live-brief", action="store_true",
                   help="Read current canonical GitHub main and existing owner(s) online; fail closed if unavailable.")
    p.add_argument("--expect-main", default=None,
                   help="Optional SHA pin for --live-brief to detect drift across chats or tool calls.")
    p.add_argument("--candidate-id", default=None,
                   help="Optional V3 owner gate ID: BLOCK already done or out-of-order work. Only with --live-brief and V3 release.")
    p.add_argument("--receipt", type=Path,
                   help="Verify a reviewer-supplied, scope-specific disposition; does not prove comprehension.")
    args = p.parse_args()
    try:
        require(sum(bool(x) for x in (args.brief, args.live_brief, args.receipt)) <= 1,
                "choose exactly one output mode")
        require(not args.expect_main or args.live_brief,
                "--expect-main only applies to live owner readback")
        require(not args.candidate_id or args.live_brief,
                "--candidate-id requires current live owner readback")
        packet = build(args.root, args.scope, args.work_domain, args.strategy_version)
        output = (verify_receipt(args.root, packet, args.receipt) if args.receipt
                  else {"source_brief": compact_decision_brief(packet),
                        "live_owner": live_owner_readback(args.work_domain, args.strategy_version,
                                                         expected_main=args.expect_main,
                                                         candidate_id=args.candidate_id)}
                       if args.live_brief
                  else compact_decision_brief(packet) if args.brief else packet)
        print(json.dumps(output, sort_keys=True, ensure_ascii=False))
        return 0
    except (ContextGateError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "CONTEXT_GATE_BLOCKED", "reason": str(error)},
                         ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
