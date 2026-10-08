#!/usr/bin/env python3
"""Validate the declared current project/control-plane state."""
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT/"project-current-state.json"

def load(path:Path):
    return json.loads(path.read_text("utf-8"))

def main()->int:
    data=load(STATE)
    errors=[]

    if data.get("kind")!="PROJECT_CURRENT_STATE_V1":
        errors.append("unexpected current-state kind")
    if data.get("status")!="ACTIVE_CONTROL_PLANE":
        errors.append("current-state must be ACTIVE_CONTROL_PLANE")

    active=data.get("active_strategy") or {}
    if active.get("mode")!="PAPER":
        errors.append("active strategy must remain PAPER in the current phase")
    if active.get("real_money_actions") is not False:
        errors.append("real_money_actions must be false")
    if active.get("automatic_activation_allowed") is not False:
        errors.append("automatic activation must remain false")
    if active.get("mid_series_material_tuning_allowed") is not False:
        errors.append("mid-series material tuning must remain false")
    if not active.get("series_id") or not active.get("strategy_revision"):
        errors.append("active strategy revision/series id required")

    predecessor=data.get("predecessor") or {}
    if predecessor.get("status")!="CLOSED_COMPLETE":
        errors.append("declared predecessor must be CLOSED_COMPLETE")
    if predecessor.get("final_review_complete") is not True:
        errors.append("predecessor final review must be complete")
    if predecessor.get("release_gate_final") is not True:
        errors.append("predecessor release gate must be final")

    wip=data.get("strategy_changing_shadow_wip") or {}
    maximum=wip.get("max_concurrent")
    active_shadows=wip.get("active") or []
    if not isinstance(maximum,int) or maximum<0:
        errors.append("invalid strategy-changing shadow WIP limit")
        maximum=0
    if len(active_shadows)>maximum:
        errors.append(f"strategy-changing shadow WIP exceeded: {len(active_shadows)} > {maximum}")
    if maximum!=1:
        errors.append("current governance requires exactly one strategy-changing shadow slot")

    ids=set()
    for shadow in active_shadows:
        cid=shadow.get("candidate_id")
        if cid in ids:
            errors.append(f"duplicate active shadow id: {cid}")
        ids.add(cid)
        if shadow.get("status")!="SHADOW_RUNNING":
            errors.append(f"active shadow must declare SHADOW_RUNNING: {cid}")
        if shadow.get("automatic_promotion") is not False:
            errors.append(f"automatic promotion must be false: {cid}")
        if shadow.get("baseline_strategy_revision")!=active.get("strategy_revision"):
            errors.append(f"active shadow baseline strategy mismatch: {cid}")
        if shadow.get("baseline_series_id")!=active.get("series_id"):
            errors.append(f"active shadow baseline series mismatch: {cid}")
        path=ROOT/str(shadow.get("candidate_file") or "")
        if not path.is_file():
            errors.append(f"active shadow candidate file missing: {cid}")
            continue
        cand=load(path)
        if cand.get("candidate_id")!=cid:
            errors.append(f"candidate file id mismatch: {cid}")
        if cand.get("status")!="SHADOW_RUNNING":
            errors.append(f"candidate file not SHADOW_RUNNING: {cid}")
        if cand.get("baseline_strategy_revision")!=active.get("strategy_revision"):
            errors.append(f"candidate baseline strategy mismatch: {cid}")
        if cand.get("baseline_series_id")!=active.get("series_id"):
            errors.append(f"candidate baseline series mismatch: {cid}")
        changed=cand.get("changed_components") or []
        if changed!=[shadow.get("changed_component")]:
            errors.append(f"candidate changed-component mismatch: {cid}")
        plan=cand.get("evidence_plan") or {}
        if plan.get("baseline_replay_required_for_causal_divergence") is not True:
            errors.append(f"baseline replay not mandatory: {cid}")
        if not str(plan.get("baseline_replay_stability_gate") or "").strip():
            errors.append(f"baseline replay stability gate missing: {cid}")
        if (cand.get("promotion_gate") or {}).get("automatic_promotion") is not False:
            errors.append(f"candidate automatic promotion must be false: {cid}")

    queued=wip.get("queued") or []
    for item in queued:
        if item.get("candidate_id") in ids:
            errors.append(f"candidate cannot be active and queued: {item.get('candidate_id')}")

    for track in data.get("observational_research_tracks") or []:
        if track.get("strategy_coupling")!="NONE":
            errors.append(f"parallel observational track has strategy coupling: {track.get('id')}")
        if track.get("automatic_promotion") is not False:
            errors.append(f"parallel observational track permits auto-promotion: {track.get('id')}")

    inv=data.get("permanent_invariants") or {}
    required_true=[
        "one_strategy_changing_shadow_at_a_time",
        "observational_tracks_may_run_in_parallel_only_without_strategy_coupling",
        "same_snapshot_baseline_replay_required_for_causal_shadow_divergence",
        "completed_release_gates_do_not_reopen_from_ordinary_new_evidence",
        "material_active_strategy_changes_require_new_version",
    ]
    for key in required_true:
        if inv.get(key) is not True:
            errors.append(f"required invariant must be true: {key}")
    if inv.get("automatic_strategy_promotion") is not False:
        errors.append("automatic_strategy_promotion must be false")
    if inv.get("automatic_real_money_activation") is not False:
        errors.append("automatic_real_money_activation must be false")

    forbidden=set(data.get("explicitly_not_authorized") or [])
    for required in {"REAL_MONEY_TRADING","AUTOMATIC_STRATEGY_PROMOTION","SECOND_CONCURRENT_STRATEGY_CHANGING_SHADOW"}:
        if required not in forbidden:
            errors.append(f"missing explicit prohibition: {required}")

    result={
        "kind":"PROJECT_CURRENT_STATE_VALIDATION_V1",
        "status":"PASS" if not errors else "FAIL",
        "active_strategy":active.get("strategy_revision"),
        "active_series":active.get("series_id"),
        "active_strategy_changing_shadows":[x.get("candidate_id") for x in active_shadows],
        "errors":errors,
    }
    print(json.dumps(result,sort_keys=True))
    return 0 if not errors else 2

if __name__=="__main__":
    raise SystemExit(main())
