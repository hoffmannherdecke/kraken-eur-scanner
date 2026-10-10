#!/usr/bin/env python3
"""Fail-closed successor learning and trade-decision sufficiency release gate.

Called by the EXISTING project control-plane validator; no new runtime task.
The already-active frozen V2R4 is historically grandfathered for analysis only.
Every genuinely new strategy revision is blocked until evidence is produced.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GATE_FILE = "research/strategy-learning-causal-gate-v1.json"
SUCCESS = "VERIFIED_PIT_E2E_PASS"


def _read(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        value = json.load(fh)
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def validate_learning_gate(root: Path = ROOT,
                           active_revision: str | None = None,
                           release_evidence: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    try:
        gate = _read(root / GATE_FILE)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return ["successor learning gate unavailable/invalid: " + type(exc).__name__]
    if gate.get("kind") != "STRATEGY_LEARNING_CAUSAL_COMPLETENESS_GATE_V1":
        errors.append("unexpected learning gate schema")
    if gate.get("status") != "ACTIVE_GOVERNANCE_OPEN_FINDING":
        errors.append("learning gate must remain active while incident unresolved")
    requirements = gate.get("checks_before_any_successor_paper_release")
    ids = gate.get("required_release_evidence_ids")
    if not isinstance(requirements, list) or not isinstance(ids, list) or len(ids) != 5 or len(set(ids)) != len(ids):
        return errors + ["missing, duplicate or malformed five mandatory successor requirements"]
    by_id = {x.get("id"): x for x in requirements if isinstance(x, dict)}
    if set(by_id) != set(ids) or len(requirements) != len(ids):
        errors.append("successor requirement list does not match gate identity")
    if any(not str(by_id.get(k, {}).get("must_prove") or "").strip() for k in ids):
        errors.append("incomplete mandatory causal requirement")
    if gate.get("source_vs_quality_semantics", {}).get("transport_status_not_equivalent_to_decision_input_sufficiency") is not True:
        errors.append("input sufficiency must be distinguished from transport health")
    if gate.get("source_vs_quality_semantics", {}).get("unit_tests_not_equivalent_to_real_path_e2e") is not True:
        errors.append("unit tests cannot substitute for decision-chain E2E")
    priority = gate.get("outcome_first_priority_policy") or {}
    if priority.get("id") != "OUTCOME_FIRST_ECONOMIC_STRATEGY_LEARNING_V1" or priority.get("status") != "ACTIVE_PERMANENT":
        errors.append("economic strategy learning priority contract missing")
    if priority.get("original_v2r4_strategy_epoch_start_utc") != "2026-10-07T18:42:55Z" or priority.get("original_v2r4_72h_review_due_utc") != "2026-10-10T18:42:55Z":
        errors.append("wrong V2R4 original productivity clock; technical rollover may not reset")
    if priority.get("technical_rotation_same_strategy_no_clock_reset") is not True:
        errors.append("economic review clock may not reset on technical rotation")
    for flag in ("no_new_work_schedule", "active_v2r4_change", "active_h3_change",
                 "automatic_release", "real_money_actions"):
        if priority.get(flag) is not False and flag != "no_new_work_schedule":
            errors.append("outcome-first priority may not mutate live strategy/release: " + flag)
        if flag == "no_new_work_schedule" and priority.get(flag) is not True:
            errors.append("outcome-first priority must not add Work schedule")
    precedence = priority.get("precedence") or []
    if not isinstance(precedence, list) or len(precedence) < 5 or not any("TECHNICAL_RUNTIME_HEALTH" in str(x) for x in precedence):
        errors.append("economic decision quality must outrank system health badges")
    if len(priority.get("release_outcomes") or []) < 5:
        errors.append("successor must measure actual BUY, net costs, risk and missed moves")
    if "NO_BUY" not in str(priority.get("no_buy_disposition") or ""):
        errors.append("zero BUY cohort must force a real strategy decision, not indefinite Paper extension")
    # An opportunity-oriented V3 successor is a research objective, not a
    # permission to loosen the existing live risk / Paper-release boundary.
    v3 = gate.get("v3_opportunity_first_research") or {}
    if v3.get("id") != "V3_OPPORTUNITY_FIRST_RISK_UNCHANGED_20261010" or v3.get("status") != "APPROVED_RESEARCH_ONLY_NOT_RELEASED":
        errors.append("V3 opportunity-first research contract missing or falsely released")
    required_sequence = [
        "A_COIN_ENTRY_PROVENANCE_ONLY_BASELINE_EVALUATOR_AND_WAIT_UNCHANGED",
        "B_ONE_SEPARATE_WAIT_OR_EXTENDED_RECHECK_POLICY_ONLY_AFTER_A_DISPOSITION",
        "C_ONE_PROSPECTIVE_SHADOW_ONLY_AFTER_SEPARATE_RELEASE_APPROVAL",
        "D_V3_PAPER_RELEASE_ONLY_AFTER_FULL_CAUSAL_GATE",
    ]
    if v3.get("single_change_order") != required_sequence:
        errors.append("V3 input A must precede separate policy B and gated Shadow/Paper release")
    first = v3.get("stage_A") or {}
    if any(first.get(k) is not True for k in (
            "reuse_existing_kraken_and_wait_data", "baseline_evaluator_unchanged",
            "wait_trigger_ttl_unchanged", "cost_risk_stop_sizing_unchanged",
            "physical_real_candidate_e2e_required")):
        errors.append("V3 A may change only point-in-time candidate evidence, not evaluator/WAIT/risk")
    second = v3.get("stage_B") or {}
    if (second.get("only_after_stage_A_result") is not True
            or second.get("one_policy_change_at_a_time") is not True
            or second.get("no_auto_buy") is not True
            or second.get("no_blind_trigger_or_ttl_relaxation") is not True
            or set(second.get("select_one_policy_hypothesis_from_evidence") or ()) != {
                "EXISTING_EXTENDED_SECOND_LEG_REVIEW_ELIGIBILITY",
                "WAIT_EXPIRED_WITHOUT_TRIGGER_FRESH_REVIEW_ELIGIBILITY"}):
        errors.append("V3 policy B may not mix WAIT and EXTENDED or bypass causal A review")
    outcomes = v3.get("evidence_success") or {}
    if (len(set(outcomes.get("must_measure") or [])) != 5
            or outcomes.get("zero_buy_requires_disposition_not_indefinite_run") is not True
            or outcomes.get("retrospective_mfe_not_profit") is not True):
        errors.append("V3 must prove executable risk-adjusted trade quality, not raw BUY/MFE")
    guard = v3.get("fixed_guards") or {}
    if (guard.get("scout_eur") != 50 or guard.get("stage2_eur") != 50
            or guard.get("taker_fee_pct_per_side") != 0.6
            or guard.get("one_active_strategy_changing_shadow_max") != 1
            or any(guard.get(k) is not True for k in (
                "do_not_modify_frozen_v2r4", "preserve_anti_chase",
                "preserve_existing_stop_and_two_stage_risk",
                "h3_h6_remain_separately_gated"))
            or any(guard.get(k) is not False for k in (
                "new_scheduler", "extra_work_run", "automatic_shadow_start",
                "automatic_paper_release", "live_orders", "real_money_actions"))):
        errors.append("V3 offensive entry research cannot weaken risk, permissions or resources")
    incident = gate.get("incident") or {}
    if incident.get("classification") != "UNRESOLVED_DECISION_PRODUCTIVITY_NOT_CLEARED_BY_V2R4_TIMING_ONLY":
        errors.append("recurring no-trade incident must not be silently declared resolved")
    path = gate.get("release_evidence_file")
    if not isinstance(path, str) or path != "research/successor-strategy-release-evidence-v1.json":
        errors.append("invalid canonical successor release evidence destination")
    if any(gate.get("runtime_guardrails", {}).get(k) is not False for k in
           ("active_v2r4_strategy_change", "active_h3_shadow_change", "new_schedule",
            "real_money_actions", "automatic_release")):
        errors.append("learning release guardrails weakened")
    if active_revision is None:
        return errors
    legacy = (gate.get("legacy_series_exception") or {}).get("allowed_active_strategy_revision")
    if active_revision == legacy:
        return errors  # Existing V2R4 is not retroactively mutated or re-released.

    # A new or rolled-back non-legacy strategy must supply its own verifiable
    # release-level evidence. Its predecessor's test PASS alone is not enough.
    if release_evidence is None:
        try:
            release_evidence = _read(root / path)
        except (OSError, ValueError, json.JSONDecodeError, TypeError) as exc:
            return errors + ["NEW_STRATEGY_BLOCKED: missing/invalid real decision-chain release evidence: " + type(exc).__name__]
    if release_evidence.get("kind") != "SUCCESSOR_STRATEGY_CAUSAL_RELEASE_EVIDENCE_V1":
        errors.append("NEW_STRATEGY_BLOCKED: wrong successor evidence kind")
    if release_evidence.get("strategy_revision") != active_revision:
        errors.append("NEW_STRATEGY_BLOCKED: evidence bound to wrong strategy revision")
    if release_evidence.get("status") != "READY_WITH_EXPLICIT_PAPER_APPROVAL":
        errors.append("NEW_STRATEGY_BLOCKED: no verified explicit paper release approval")
    if release_evidence.get("real_money_actions") is not False:
        errors.append("NEW_STRATEGY_BLOCKED: real money must remain separately gated")
    if not release_evidence.get("code_fingerprint_sha256"):
        errors.append("NEW_STRATEGY_BLOCKED: missing implementation fingerprint")
    if not release_evidence.get("strategy_fingerprint_sha256"):
        errors.append("NEW_STRATEGY_BLOCKED: missing strategy fingerprint")

    proof_rows = release_evidence.get("requirement_proofs")
    proof_by_id = {x.get("id"): x for x in proof_rows if isinstance(x, dict)} if isinstance(proof_rows, list) else {}
    if set(proof_by_id) != set(ids) or len(proof_rows or []) != len(ids):
        errors.append("NEW_STRATEGY_BLOCKED: missing unique predecessor-finding closure evidence")
    for k in ids:
        row = proof_by_id.get(k) or {}
        contract_row = by_id.get(k) or {}
        if contract_row.get("current_status") != SUCCESS:
            errors.append(f"NEW_STRATEGY_BLOCKED: {k} not verified in canonical gate")
        if row.get("status") != SUCCESS:
            errors.append(f"NEW_STRATEGY_BLOCKED: {k} lacks proven point-in-time E2E")
        if not isinstance(row.get("evidence_path"), str) or not (root / row.get("evidence_path", "")).is_file():
            errors.append(f"NEW_STRATEGY_BLOCKED: {k} evidence artifact absent")

    metrics = release_evidence.get("prospective_feasibility") or {}
    if not isinstance(metrics.get("evaluated_candidates"), int) or metrics.get("evaluated_candidates") <= 0:
        errors.append("NEW_STRATEGY_BLOCKED: no prospective candidate cohort")
    if not isinstance(metrics.get("valid_buy_scouts"), int) or metrics.get("valid_buy_scouts") < 1:
        errors.append("NEW_STRATEGY_BLOCKED: no evidence any viable BUY_SCOUT can be produced")
    if metrics.get("matched_baseline_and_successor_clock") is not True:
        errors.append("NEW_STRATEGY_BLOCKED: missing same-snapshot baseline replay")
    if metrics.get("pair_time_clustered") is not True:
        errors.append("NEW_STRATEGY_BLOCKED: opportunity episodes not deduplicated")
    if metrics.get("risk_and_net_cost_review_complete") is not True:
        errors.append("NEW_STRATEGY_BLOCKED: net-cost and adverse-path review missing")
    if release_evidence.get("explicit_human_release_decision") != "APPROVED_PAPER":
        errors.append("NEW_STRATEGY_BLOCKED: no explicit user paper release gate")
    return errors
