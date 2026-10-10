#!/usr/bin/env python3
"""Verify permanent V2R4 no-BUY / EXTENDED second-leg inheritance in the existing control plane.

No runtime/network writes. A successor can disposition the hypothesis with actual
proof, but never silently lose its ownership, predecessor evidence or release gates.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE_A = "V3_ENTRY_COIN_EVIDENCE_ONLY_PROSPECTIVE_SINGLE_CHANGE_GATE"
STAGE_B = "V3_EXTENDED_SECOND_LEG_REVIEW_ELIGIBILITY_SINGLE_POLICY_CHANGE_GATE"
OWNER = "late_chase_protection"
COMPANION = "coin_specific_entry_evidence_provenance"
DECISION_ID = "V3-EXTENDED-SECOND-LEG-LEARNING-GATE"
H3_ARCHIVE_GATE = "V3_H3_001_ARCHIVE_DISPOSITION_AND_V2R4_ECONOMIC_REVIEW"
H3_ARCHIVE_DECISION = "V3-H3-ARCHIVE-DISPOSITION"
COIN_PROVENANCE_GATE = "V3_ENTRY_EVIDENCE_POINT_IN_TIME_FEATURE_REUSE_DEDUP_AND_SINGLE_CHANGE_PROSPECTIVE_COMPARE_AFTER_H3_ARCHIVE_DISPOSITION_AND_V2R4_ECONOMIC_REVIEW"
CAUSAL_NEXT_ACTION = "AFTER_H3_ARCHIVE_DISPOSITION_AND_V2R4_ECONOMIC_REVIEW_PROSPECTIVE_ENTRY_EVIDENCE_ONLY_ONE_CHANGE_COMPARE_THEN_SEPARATE_TRIGGER_POLICY_HYPOTHESIS_IF_NEEDED"


def _load(root: Path, path: str) -> dict[str, Any]:
    value = json.loads((root / path).read_text("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: JSON object required")
    return value


def validate_documents(
    ledger: dict[str, Any],
    state: dict[str, Any],
    learning_gate: dict[str, Any],
    lineage: dict[str, Any],
    *,
    code_exists: bool = True,
) -> list[str]:
    errors: list[str] = []
    components = ledger.get("components")
    if not isinstance(components, list):
        return ["V3_SUCCESSOR_LINEAGE: migration components missing"]
    found: dict[str, list[dict]] = {
        name: [x for x in components if isinstance(x, dict) and x.get("id") == name]
        for name in (OWNER, COMPANION)
    }
    if any(len(rows) != 1 for rows in found.values()):
        return ["V3_SUCCESSOR_LINEAGE: existing late-chase and candidate evidence owners must be unique"]
    late, coin = found[OWNER][0], found[COMPANION][0]
    refinement = late.get("successor_refinement") or {}
    roadmap = coin.get("successor_roadmap_link") or {}
    allowed = set(refinement.get("allowed_dispositions") or [])

    if late.get("migration_status") != "INHERIT_UNCHANGED":
        errors.append("V3_SUCCESSOR_LINEAGE: existing safety/late-chase baseline must be inherited")
    if refinement.get("id") != "V3_EXTENDED_SECOND_LEG_ENTRY_REVIEW":
        errors.append("V3_SUCCESSOR_LINEAGE: EXTENDED second-leg finding silently lost")
    if refinement.get("permanent_generation_inheritance") != "MANDATORY_EXPLICIT_DISPOSITION_AT_EVERY_SUCCESSOR_VERSION_V3_V4_PLUS_LIVE_AFTER_SEPARATE_APPROVAL":
        errors.append("V3_SUCCESSOR_LINEAGE: finding not inherited by later generations")
    if not {"VERIFIED_INTEGRATE", "MORE_TESTING_REQUIRED", "DEFER_TO_LATER_GENERATION_WITH_OWNER_AND_GATE",
            "REJECT_WITH_EVIDENCE", "NO_SUCCESSOR_CHANGE_WITH_EVIDENCE"}.issubset(allowed):
        errors.append("V3_SUCCESSOR_LINEAGE: successor finding disposition must include negative results")
    for k in ("existing_component_only","not_a_new_reversal_or_h6_signal","promotion_prohibited_without_evidence"):
        if refinement.get(k) is not True:
            errors.append(f"V3_SUCCESSOR_LINEAGE: missing {k} guard")
    for k in ("active_v2r4_changed","active_h3_changed","real_money_actions","automatic_activation",
              "additional_scheduler"):
        if refinement.get(k) is not False:
            errors.append(f"V3_SUCCESSOR_LINEAGE: illegal active coupling {k}")
    if refinement.get("inactive_research_code") != "paper_evaluator/v3_extended_reentry_review_v1.py" or not code_exists:
        errors.append("V3_SUCCESSOR_LINEAGE: canonical inactive implementation missing")
    if refinement.get("existing_research_contract") != "research/v3/coin-entry-evidence-lineage-v1.json":
        errors.append("V3_SUCCESSOR_LINEAGE: canonical overlap/owner contract missing")

    stage_a = refinement.get("stage_A") or {}
    stage_b = refinement.get("stage_B") or {}
    if stage_a.get("id") != STAGE_A or stage_a.get("depends_on") != H3_ARCHIVE_GATE:
        errors.append("V3_SUCCESSOR_LINEAGE: prospective input-only A must follow H3 archive disposition and V2R4 economic review")
    if stage_b.get("id") != STAGE_B or stage_b.get("depends_on") != STAGE_A:
        errors.append("V3_SUCCESSOR_LINEAGE: separate EXTENDED policy B must follow A")
    if H3_ARCHIVE_GATE + " -> " + STAGE_A + " -> " + STAGE_B not in str(refinement.get("gate_sequence","")):
        errors.append("V3_SUCCESSOR_LINEAGE: trial sequence and explicit release not retained")
    for k in ("single_changed_input","result_required"):
        if not str(stage_a.get(k) or "").strip():
            errors.append("V3_SUCCESSOR_LINEAGE: missing A proof contract " + k)
    for k in ("single_changed_policy","result_required"):
        if not str(stage_b.get(k) or "").strip():
            errors.append("V3_SUCCESSOR_LINEAGE: missing B proof contract " + k)
    if roadmap.get("canonical_existing_component") != OWNER or roadmap.get("no_duplicate_component") is not True:
        errors.append("V3_SUCCESSOR_LINEAGE: companion evidence must not create another signal owner")
    if roadmap.get("first_stage") != STAGE_A or roadmap.get("second_separate_stage") != STAGE_B:
        errors.append("V3_SUCCESSOR_LINEAGE: coin input handoff does not route to separate EXTENDED trial")
    if roadmap.get("no_reversal_lane_replacement") is not True:
        errors.append("V3_SUCCESSOR_LINEAGE: existing REVERSAL category silently replaced")

    decisions = state.get("next_control_decisions") or []
    archive = [v for v in decisions if isinstance(v, dict) and v.get("id") == H3_ARCHIVE_DECISION]
    archived_tracks = [v for v in (state.get("closed_or_rejected_tracks") or [])
                       if isinstance(v, dict) and v.get("id") == "V3-H3-SHADOW-001"]
    h3_track = archived_tracks[0] if len(archived_tracks) == 1 else {}
    disposition = h3_track.get("archive_disposition")
    has_fixed_review = any(v.get("id") == "V3-H3-FIXED-REVIEW"
                           for v in decisions if isinstance(v, dict))
    if disposition is None:
        if (len(archive) != 1
                or archive[0].get("status") != "ARCHIVE_REVIEW_DUE_NOT_FIXED_REVIEW_READY"
                or has_fixed_review):
            errors.append("V3_SUCCESSOR_LINEAGE: archived H3 cannot retain obsolete fixed-review decision")
    elif (disposition not in {"DEFER_WITH_GATE", "REJECT_WITH_EVIDENCE"}
          or archive
          or has_fixed_review
          or h3_track.get("fixed_review_completed") is not False
          or not str(h3_track.get("archive_disposition_report") or "").strip()):
        errors.append("V3_SUCCESSOR_LINEAGE: closed H3 archive disposition is inconsistent")
    if coin.get("pending_gate") != COIN_PROVENANCE_GATE:
        errors.append("V3_SUCCESSOR_LINEAGE: coin provenance must follow H3 archive and V2R4 economic review")
    if ((learning_gate.get("incident") or {}).get("failure_classification") or {}).get("next_active_action") != CAUSAL_NEXT_ACTION:
        errors.append("V3_SUCCESSOR_LINEAGE: causal next action still depends on impossible H3 fixed review")
    next_steps = [v for v in decisions if isinstance(v, dict) and v.get("id")==DECISION_ID]
    if len(next_steps) != 1:
        errors.append("V3_SUCCESSOR_LINEAGE: control plane missing unique future review trigger")
    else:
        step=next_steps[0]
        if step.get("canonical_owner") != "research/v3-migration-ledger.json#late_chase_protection.successor_refinement":
            errors.append("V3_SUCCESSOR_LINEAGE: control plane points at wrong owner")
        if step.get("no_new_work_run") is not True or step.get("no_active_strategy_change") is not True:
            errors.append("V3_SUCCESSOR_LINEAGE: followup wrongly allowed new Work or live mutation")
        if step.get("applies_through") != "V3_V4_PLUS_AND_FUTURE_SEPARATELY_AUTHORIZED_REAL_MONEY_SUCCESSORS":
            errors.append("V3_SUCCESSOR_LINEAGE: future versions forgotten")
    if (state.get("permanent_invariants") or {}).get("material_no_buy_second_leg_findings_require_successor_disposition") is not True:
        errors.append("V3_SUCCESSOR_LINEAGE: permanent no-BUY learning invariant missing")

    incident = learning_gate.get("incident") or {}
    event = incident.get("retrospective_20261008_09_extended_reentry") or {}
    if event.get("screened_candidate_observations") != 27 or (event.get("original_setup_lanes") or {}).get("EXTENDED") != 20:
        errors.append("V3_SUCCESSOR_LINEAGE: Oct 08/09 causal source evidence missing")
    if event.get("status_for_release") != "NOT_CLEARED_WITHOUT_PROSPECTIVE_GAIN_AND_EXPLICIT_GATE":
        errors.append("V3_SUCCESSOR_LINEAGE: outcome-label study cannot be claimed as release proof")
    if event.get("roadmap_owner") != "research/v3-migration-ledger.json#late_chase_protection.successor_refinement":
        errors.append("V3_SUCCESSOR_LINEAGE: release gate did not retain canonical disposition owner")

    overlap = lineage.get("follow_on_late_chase_research") or {}
    if overlap.get("existing_component_owner") != OWNER or overlap.get("new_component_created") is not False:
        errors.append("V3_SUCCESSOR_LINEAGE: duplicate second-leg strategy signal")
    if overlap.get("precondition_first") != "V3_ENTRY_COIN_EVIDENCE_ONLY_PROSPECTIVE_SINGLE_CHANGE_GATE_AFTER_H3_ARCHIVE_DISPOSITION_AND_V2R4_ECONOMIC_REVIEW":
        errors.append("V3_SUCCESSOR_LINEAGE: H3 archive/V2R4 economic A gate missing in research lineage")
    if overlap.get("separate_policy_second") != STAGE_B:
        errors.append("V3_SUCCESSOR_LINEAGE: separate B review unreferenced")
    if overlap.get("no_automatic_buy_or_promotion") is not True:
        errors.append("V3_SUCCESSOR_LINEAGE: no automatic BUY/promotion override permitted")
    return errors


def validate(root: Path = ROOT) -> list[str]:
    try:
        return validate_documents(
            _load(root,"research/v3-migration-ledger.json"),
            _load(root,"project-current-state.json"),
            _load(root,"research/strategy-learning-causal-gate-v1.json"),
            _load(root,"research/v3/coin-entry-evidence-lineage-v1.json"),
            code_exists=(root/"paper_evaluator/v3_extended_reentry_review_v1.py").is_file(),
        )
    except (ValueError, KeyError, OSError, TypeError, json.JSONDecodeError) as exc:
        return ["V3_SUCCESSOR_LINEAGE: required canonical evidence file invalid: " + type(exc).__name__]


if __name__=="__main__":
    issues=validate()
    print(json.dumps({"kind":"V3_SECOND_LEG_SUCCESSOR_INHERITANCE_GUARD_V1",
                      "status":"PASS" if not issues else "FAIL",
                      "errors":issues},sort_keys=True))
    raise SystemExit(2 if issues else 0)
