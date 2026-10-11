#!/usr/bin/env python3
"""Validate PR161's optional V3 source lanes and classify *passive* PIT research refs.

Local/offline, no network, no data capture, no trading actions, no release powers.
Never outputs a BUY/WAIT/REJECT or prospective edge claim.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PLAN = "research/v3/v3-consolidated-strategy-integration-plan-20261011.json"
ROUTING = "research/monitoring-evidence-routing-v1.json"
REGISTRY = "research/source-registry.json"

EXPECTED = {
    "market_regime", "global_market_crosscheck", "news_event_context",
    "source_quality", "derivatives_h2", "macro_h5", "onchain_h8",
    "smartmoney_h10", "prediction_h11",
}
MAPPINGS = {"GLOBAL_RESEARCH", "EVENT_PREREGISTERED",
            "PAIR_KRAKEN_PIT", "NOT_A_CANDIDATE_FEATURE"}
RESTRICTIONS = {
    "v2r4_frozen", "h3_archived_no_auto_restart",
    "h6_inactive", "h1_standalone_rejected",
    "polymarket_not_direct_entry_signal", "hyperliquid_no_copied_trades",
    "source_research_changes_do_not_mutate_runtime",
}
REQUIRED_GATES = {
    "optional_missing_is_neutral", "no_signal_votes_or_optional_buy_vetos",
    "no_auto_order_buy_wait_reject_or_sizing", "no_new_capture_or_scheduler",
    "no_new_paid_source_or_model_calls",
}


class GateError(ValueError):
    pass


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise GateError("V3_CONTEXT_FUSION_BLOCKED: " + reason)


def read(root: Path, path: str) -> dict:
    value = json.loads((root / path).read_text(encoding="utf-8"))
    require(isinstance(value, dict), "JSON object required: " + path)
    return value


def validate(root: Path) -> dict:
    plan, routing, registry = read(root, PLAN), read(root, ROUTING), read(root, REGISTRY)
    require(plan.get("kind") == "V3_STRATEGY_INHERITANCE_AND_EXECUTION_PLAN_V1",
            "V3 plan not the PR161 authority")
    cfg = plan.get("optional_context_fusion") or {}
    require(cfg.get("kind") == "V3_OPTIONAL_KNOWN_AT_CONTEXT_FUSION_V1"
            and cfg.get("status") == "PASSIVE_RESEARCH_INTEGRATION_PREP_NO_STRATEGY_RELEASE",
            "missing/inconsistent context integration")
    for flag in REQUIRED_GATES:
        require(cfg.get(flag) is True, "unsafe optional data policy: " + flag)
    restrictions = cfg.get("restrictions") or {}
    for flag in RESTRICTIONS:
        require(restrictions.get(flag) is True,
                "frozen component or read-only rule changed: " + flag)
    require(restrictions.get("one_strategy_changing_shadow_max") == 1
            and restrictions.get("real_money_actions") is False,
            "unsafe shadow/release boundary")
    require(cfg.get("use_when") == "EXISTING_DUE_V3_RESEARCH_OR_SUCCESSOR_DECISION_ONLY"
            and cfg.get("dynamic_status_authority") and
            cfg.get("input_contract") == "docs/v3-context-fusion-research-v1.md",
            "new schedule/status owner or missing contract")
    require(routing.get("kind") == "MONITORING_EVIDENCE_ROUTING_V1"
            and registry.get("kind") == "EXTERNAL_SOURCE_REGISTRY_V1",
            "canonical source authority changed")
    known = {s["id"]: s for s in routing.get("streams") or []}
    sources = {s["id"]: s for s in registry.get("sources") or []}
    require({"hyperliquid_public_info", "polymarket_public_market_data",
             "kraken_spot_assetpairs_public"}.issubset(sources),
            "H10/H11/Kraken authority missing from source registry")
    lanes = cfg.get("lanes") or []
    ids = [item.get("stream_id") for item in lanes]
    require(len(ids) == len(set(ids)) and set(ids) == EXPECTED,
            "missing or duplicate existing context stream")
    allowed_root = root.resolve()
    for lane in lanes:
        stream_id = lane["stream_id"]
        owner, mode, group = lane.get("owner"), lane.get("mapping"), lane.get("group")
        require(stream_id in known and known[stream_id].get("optional_research") is True
                and known[stream_id].get("source_known_at_required") is True,
                "nonoptional/unknown research stream: " + stream_id)
        require(isinstance(owner, str) and owner and
                mode in MAPPINGS and isinstance(group, str) and group and
                isinstance(lane.get("use"), str) and
                isinstance(lane.get("gate"), str) and
                len(lane["gate"]) > 12,
                "incomplete lane contract: " + stream_id)
        # File pointers never override canonical status. Fragment refs are not paths.
        local = owner.split("#", 1)[0]
        require(".." not in Path(local).parts and not Path(local).is_absolute()
                and (root / local).resolve().is_relative_to(allowed_root)
                and (root / local).is_file(),
                "missing/unsafe canonical owner: " + owner)
    lane_by_id = {x["stream_id"]: x for x in lanes}
    require(lane_by_id["source_quality"]["mapping"] == "NOT_A_CANDIDATE_FEATURE"
            and lane_by_id["smartmoney_h10"]["mapping"] == "PAIR_KRAKEN_PIT"
            and lane_by_id["prediction_h11"]["mapping"] == "EVENT_PREREGISTERED",
            "H10/H11/source stewardship role confusion")
    h = {item["id"]: item for item in plan.get("h_components") or []}
    require("ARCHIVED" in h["H3"]["status"] and
            "NOT_ENABLED" in h["H6"]["status"] and
            "REJECTED" in h["H1"]["status"],
            "historically blocked H1/H3/H6 incorrectly promoted")
    return {
        "kind": "V3_CONTEXT_FUSION_PREFLIGHT_V1",
        "status": "PASSIVE_RESEARCH_ROUTES_VERIFIED_NO_STRATEGY_INTEGRATION",
        "lanes": [{
            "stream_id": item["stream_id"],
            "group": item["group"],
            "mapping": item["mapping"],
            "owner": item["owner"],
            "research_gate": item["gate"],
            "current_evidence_classification": known[item["stream_id"]].get("evidence_status"),
        } for item in lanes],
        "frozen_policy_preserved": True,
        "added_schedules": False,
        "permission_to_trade": False,
    }


def parse_utc(value: object) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(dt.timezone.utc)
    except ValueError:
        return None


def classify_snapshot(preflight: dict, payload: dict) -> dict:
    require(payload.get("kind") == "V3_OPTIONAL_CONTEXT_PROBE_V1",
            "invalid candidate context probe")
    decision = parse_utc(payload.get("decision_at_utc"))
    pair = payload.get("pair")
    require(decision is not None and isinstance(pair, str) and
            pair.upper().endswith("/EUR") and len(pair) >= 7,
            "missing timezone-aware decision/pair; Kraken Spot EUR required")
    rows = payload.get("evidence_refs") or []
    require(isinstance(rows, list) and len(rows) <= 64,
            "evidence refs must be bounded list <=64")
    lanes = {item["stream_id"]: item for item in preflight["lanes"]}
    outcomes, duplicates = [], set()
    for index, record in enumerate(rows):
        require(isinstance(record, dict), "evidence ref must be object")
        sid = record.get("stream_id")
        require(sid in lanes, "unregistered candidate context stream: " + str(sid))
        lane = lanes[sid]
        status = "NOT_EVALUABLE"
        reason = "PROVENANCE_REQUIRED"
        ref = record.get("evidence_ref")
        dedupe = (sid, ref)
        if (not isinstance(ref, str) or len(ref.strip()) < 8):
            status, reason = "NOT_EVALUABLE", "MISSING_EVIDENCE_REFERENCE"
        elif dedupe in duplicates:
            status, reason = "RESEARCH_DUPLICATE", "SAME_STREAM_AND_EVIDENCE_REFERENCE"
        else:
            duplicates.add(dedupe)
            times = [parse_utc(record.get(key)) for key in
                     ("source_event_at_utc", "first_seen_at_utc",
                      "retrieved_at_utc", "known_at_utc")]
            if any(t is None for t in times):
                status, reason = "NOT_EVALUABLE", "INCOMPLETE_KNOWN_AT_TIMESTAMPS"
            elif times[3] < max(times[:3]):
                status, reason = "NOT_EVALUABLE", "KNOWN_AT_PRECEDES_SOURCE_OR_OBSERVATION"
            elif times[3] > decision:
                status, reason = "NOT_EVALUABLE", "FUTURE_INFORMATION_LEAKAGE"
            elif lane["mapping"] == "NOT_A_CANDIDATE_FEATURE":
                status, reason = "STEWARDSHIP_ONLY", "SOURCE_QUALITY_NOT_TRADE_SIGNAL"
            elif lane["mapping"] == "PAIR_KRAKEN_PIT" and (
                    record.get("pair") != pair or
                    record.get("kraken_pit_mapping_verified") is not True):
                status, reason = "NOT_ASSOCIABLE", "MISSING_SAME_CLOCK_KRAKEN_EUR_MAPPING"
            elif lane["mapping"] == "EVENT_PREREGISTERED" and (
                    record.get("event_pair_link_preregistered") is not True or
                    record.get("pair") != pair):
                status, reason = "NOT_ASSOCIABLE", "NO_PREDECLARED_EVENT_TO_PAIR_LINK"
            else:
                status, reason = ("PIT_TIME_ADMISSIBLE_RESEARCH_ONLY",
                                  "UNVERIFIED_REFERENCE_NEEDS_MATURE_OUTCOME_AND_ONE_CHANGE_GATE")
        outcomes.append({
            "index": index, "stream_id": sid, "group": lane["group"],
            "status": status, "reason": reason,
            "evidence_ref": ref if isinstance(ref, str) else None,
            "research_gate": lane["research_gate"],
        })
    return {
        "kind": "V3_OPTIONAL_RESEARCH_CONTEXT_CLASSIFICATION_V1",
        "status": "READ_ONLY_CLASSIFICATION_NOT_PROSPECTIVE_ALPHA",
        "pair": pair, "decision_at_utc": payload["decision_at_utc"],
        "records": outcomes,
        "no_buy_wait_reject_stop_sizing_decision": True,
        "no_trade_or_order_permission": True,
        "no_shadow_or_paper_activation": True,
        "no_new_schedules": True,
        "source_claims_are_not_independently_verified": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--input", type=Path,
                        help="Optional local bounded evidence-ref JSON; never downloads anything")
    args = parser.parse_args()
    try:
        packet = validate(args.root)
        if args.input:
            payload = json.loads(args.input.read_text(encoding="utf-8"))
            packet = classify_snapshot(packet, payload)
        print(json.dumps(packet, sort_keys=True, ensure_ascii=False))
        return 0
    except (GateError, OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({"status": "V3_CONTEXT_FUSION_BLOCKED", "reason": str(error)},
                         ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
