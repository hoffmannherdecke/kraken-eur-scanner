#!/usr/bin/env python3
"""Project-wide, read-only Work handoff: route every registered stream and due decision.

No network calls, no state mutation, no strategy execution and no task scheduling.
Run in the EXISTING daily Work phase 1; scheduled GitHub controller stays the watchdog.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc
SAFE_STATUSES = {"COMPLETED", "DECISION_PACKET_READY", "BLOCKED_WITH_ACTION"}
RELEASE_DENY = {"ACTIVE_STRATEGY_OR_EXECUTION", "PAPER_OR_SHADOW_ACTIVATION",
                "H3_H6_PROMOTION", "KRAKEN_ORDER_PERMISSION_OR_REAL_MONEY",
                "SECRETS_OR_NEW_PRIVILEGES", "PAID_SERVICE_OR_BUDGET",
                "IRREVERSIBLE_CHANGE"}


def require(value: bool, reason: str) -> None:
    if not value:
        raise ValueError("FAIL_CLOSED: " + reason)


def read_json(root: Path, name: str) -> dict:
    return json.loads((root / name).read_text(encoding="utf-8"))


def utc(value: str) -> dt.datetime:
    stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(stamp.tzinfo is not None, "timestamp must carry offset")
    return stamp.astimezone(UTC)


def valid_receipt(root: Path, reviews: dict, key: str, due: dt.datetime, now: dt.datetime) -> bool:
    receipt = reviews.get(key)
    if not isinstance(receipt, dict) or receipt.get("status") not in SAFE_STATUSES:
        return False
    report = receipt.get("report")
    completed = receipt.get("completed_at_utc")
    if not (isinstance(report, str)
            and re.fullmatch(r"research/work-analysis/[A-Za-z0-9_.-]+[.]md", report)
            and isinstance(completed, str)):
        return False
    try:
        completion = utc(completed)
    except (ValueError, TypeError):
        return False
    return due <= completion <= now and (root / report).is_file()


def route(root: Path, now: dt.datetime) -> dict:
    manifest = read_json(root, "research/project-followthrough-routing-v1.json")
    routing = read_json(root, "research/monitoring-evidence-routing-v1.json")
    state = read_json(root, "project-current-state.json")
    ack = read_json(root, "research/work-analysis-state.json")
    require(manifest.get("kind") == "PROJECT_WIDE_FOLLOWTHROUGH_ROUTING_V1"
            and manifest.get("schema_version") == 1, "followthrough schema changed")
    require(manifest.get("stream_coverage") ==
            "ALL_MONITORING_EVIDENCE_ROUTING_STREAMS_DYNAMIC", "partial stream coverage")
    require(manifest.get("stream_source") ==
            "research/monitoring-evidence-routing-v1.json", "routing source mismatch")
    require(manifest.get("executor") == "EXISTING_DAILY_1015_WORK_ONCE_PER_GATE",
            "wrong executor")
    require(manifest.get("watcher") ==
            "EXISTING_AUTONOMOUS_PROJECT_MILESTONE_CONTROLLER", "wrong watcher")
    safe = manifest.get("safety") or {}
    for flag in ("no_new_scheduler", "no_runtime_mutation", "no_trade_or_orders",
                 "no_auto_activation", "no_unverified_chat_ingestion", "no_fake_completion"):
        require(safe.get(flag) is True, "unsafe policy: " + flag)
    require(set(manifest.get("user_release_required") or []) == RELEASE_DENY,
            "release boundaries differ")
    require(state.get("kind") == "PROJECT_CURRENT_STATE_V1"
            and state.get("active_strategy", {}).get("real_money_actions") is False
            and state.get("active_strategy", {}).get("automatic_activation_allowed") is False,
            "current-state activation boundary changed")
    streams = routing.get("streams") or []
    stream_ids = [s.get("id") for s in streams]
    required_stream_ids = manifest.get("required_stream_ids") or []
    require(len(required_stream_ids) == len(set(required_stream_ids))
            and len(required_stream_ids) >= 26
            and set(required_stream_ids).issubset(set(stream_ids))
            and len(stream_ids) == len(set(stream_ids)),
            "missing/duplicate monitoring route")
    for stream in streams:
        require(all(isinstance(stream.get(k), str) and stream[k]
                    for k in ("id", "canonical_owner", "consumer", "next_gate")),
                "stream without owner/consumer/next gate")
    extra = manifest.get("extra_project_areas") or []
    extra_ids = [e.get("id") for e in extra]
    require(len(extra) >= 8 and len(extra_ids) == len(set(extra_ids)),
            "missing/duplicate cross-cutting workstream")
    for area in extra:
        name = area.get("owner")
        require(isinstance(name, str) and re.fullmatch(r"[a-zA-Z0-9_./-]+", name)
                and ".." not in name and (root / name).is_file()
                and isinstance(area.get("gate"), str) and len(area["gate"]) > 5,
                "cross-cutting area without real canonical owner/gate")
    decisions = state.get("next_control_decisions") or []
    decision_ids = [d.get("id") for d in decisions]
    require(len(decision_ids) == len(set(decision_ids)), "duplicate control decisions")
    reviews = ((ack.get("acknowledgements") or {}).get("control_decision_reviews") or {})
    ready, gated, closed = [], [], []
    for task in decisions:
        task_id = task.get("id")
        require(isinstance(task_id, str) and task_id and task.get("trigger")
                and task.get("action"), "control decision has no trigger/action")
        due_str, key, lag = (task.get("due_at_utc"),
                             task.get("followthrough_ack_key"),
                             task.get("followthrough_max_lag_hours"))
        if any(x is not None for x in (due_str, key, lag)):
            require(isinstance(due_str, str) and isinstance(key, str)
                    and re.fullmatch(r"[A-Za-z0-9_.-]{5,120}", key)
                    and type(lag) is int and 1 <= lag <= 168,
                    "incomplete timed-gate contract")
            due = utc(due_str)
            if now < due:
                gated.append({"id": task_id, "gate": "WAIT_FOR_DUE_TIME", "due_at_utc": due_str})
            elif valid_receipt(root, reviews, key, due, now):
                closed.append(task_id)
            else:
                ready.append({"id": task_id, "gate": "DUE_REVIEW",
                              "ack_key": key, "owner": "EXISTING_DAILY_1015_WORK",
                              "release": "SEPARATE_USER_APPROVAL_FOR_MATERIAL_CHANGE"})
        elif "REVIEW_DUE" in str(task.get("status", "")):
            ready.append({"id": task_id, "gate": "DECLARED_REVIEW_DUE",
                          "owner": "EXISTING_DAILY_1015_WORK",
                          "release": "SEPARATE_USER_APPROVAL_FOR_MATERIAL_CHANGE"})
        else:
            gated.append({"id": task_id, "gate": "CHECK_DECLARED_TRIGGER_NO_AUTO_START"})
    return {
        "kind": "PROJECT_WIDE_WORK_HANDOFF_V1",
        "status": "REVIEW_DUE" if ready else "NO_DUE_CONTROL_GATE",
        "stream_coverage_count": len(streams),
        "crosscut_coverage_count": len(extra),
        "covered_stream_ids": stream_ids,
        "ready_control_decisions": ready,
        "gated_control_decisions": gated,
        "previously_acknowledged": closed,
        "backlog_owner": "PROJECT_BACKLOG.md",
        "safe_work_selector": "tools/select-autonomous-implementation.py",
        "executor": "EXISTING_DAILY_1015_WORK_ONCE_PER_GATE",
        "may_change_strategy": False, "may_execute_orders": False,
        "may_start_shadow_or_live": False, "may_schedule_new_runs": False,
        "unregistered_conversations_are_not_automatically_imported": True,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--at-utc", type=str)
    args = p.parse_args()
    now = utc(args.at_utc) if args.at_utc else dt.datetime.now(UTC)
    print(json.dumps(route(args.root, now), sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
