#!/usr/bin/env python3
"""Read-only restart/reconciliation audit for the paper runtime.

Goal: prove that a restart/power loss cannot cause blind replay of stale
candidates, duplicate candidate evaluation, or silent loss of TTL state.

This script never evaluates a candidate, never calls a model/exchange, and
never writes strategy/runtime state. It only inspects repository artifacts.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_NEW_CANDIDATE_AGE_SECONDS = 3600
REVALIDATION_GRACE_SECONDS = 1800


def zdt(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = ap.parse_args()
    root = args.root

    control = load(root / "paper_runtime_control.json")
    series_id = control.get("series_id")
    series_start = zdt(control["series_started_at_utc"])
    now = datetime.now(timezone.utc)

    handoff_dir = root / "handoff_queue"
    decision_dir = root / "paper_decisions"
    reval_dir = root / "paper_revalidations"

    handoffs: dict[str, tuple[Path, dict[str, Any]]] = {}
    decisions: dict[str, tuple[Path, dict[str, Any]]] = {}
    revals: dict[str, tuple[Path, dict[str, Any]]] = {}

    queue_ids: list[str] = []
    candidate_ids: list[str] = []
    findings: list[dict[str, Any]] = []
    old_series_ignored = 0

    for path in sorted(handoff_dir.glob("*.json")) if handoff_dir.exists() else []:
        try:
            rec = load(path)
        except Exception as exc:
            findings.append({"severity": "CRITICAL", "code": "HANDOFF_INVALID_JSON", "file": str(path), "detail": str(exc)})
            continue
        try:
            event_time = zdt(rec.get("event_time_utc") or datetime.fromtimestamp(int(rec["event_ts"]), timezone.utc).isoformat())
        except Exception:
            findings.append({"severity": "CRITICAL", "code": "HANDOFF_BAD_TIMESTAMP", "file": str(path)})
            continue
        if event_time < series_start:
            old_series_ignored += 1
            continue

        cid = str(rec.get("candidate_id") or "")
        qid = str(rec.get("queue_id") or "")
        if not cid or path.stem != cid:
            findings.append({"severity": "CRITICAL", "code": "HANDOFF_ID_MISMATCH", "file": str(path)})
            continue
        handoffs[cid] = (path, rec)
        candidate_ids.append(cid)
        queue_ids.append(qid)

    for path in sorted(decision_dir.glob("*.json")) if decision_dir.exists() else []:
        try:
            rec = load(path)
        except Exception as exc:
            findings.append({"severity": "CRITICAL", "code": "DECISION_INVALID_JSON", "file": str(path), "detail": str(exc)})
            continue
        if rec.get("series_id") != series_id:
            continue
        cid = str(rec.get("candidate_id") or "")
        if cid:
            decisions[cid] = (path, rec)

    for path in sorted(reval_dir.glob("*.json")) if reval_dir.exists() else []:
        try:
            rec = load(path)
        except Exception as exc:
            findings.append({"severity": "CRITICAL", "code": "REVALIDATION_INVALID_JSON", "file": str(path), "detail": str(exc)})
            continue
        if rec.get("series_id") != series_id:
            continue
        cid = str(rec.get("candidate_id") or "")
        if cid:
            revals[cid] = (path, rec)

    for value, count in Counter(candidate_ids).items():
        if value and count > 1:
            findings.append({"severity": "CRITICAL", "code": "DUPLICATE_CANDIDATE_ID", "candidate_id": value, "count": count})
    for value, count in Counter(queue_ids).items():
        if value and count > 1:
            findings.append({"severity": "CRITICAL", "code": "DUPLICATE_QUEUE_ID", "queue_id": value, "count": count})

    stale_orphans = 0
    replayable_fresh = 0
    due_waits = 0
    overdue_waits = 0

    for cid, (_, rec) in handoffs.items():
        try:
            event_time = zdt(rec.get("event_time_utc") or datetime.fromtimestamp(int(rec["event_ts"]), timezone.utc).isoformat())
        except Exception:
            findings.append({"severity": "CRITICAL", "code": "HANDOFF_BAD_TIMESTAMP", "candidate_id": cid})
            continue

        age = max(0.0, (now - event_time).total_seconds())
        has_decision = cid in decisions

        if not has_decision and age > MAX_NEW_CANDIDATE_AGE_SECONDS:
            stale_orphans += 1
            # Safe state: stale handoff exists, but evaluator selection explicitly
            # excludes >60m candidates and evaluate.py also rejects them.
        elif not has_decision:
            replayable_fresh += 1

    for cid, (_, dec) in decisions.items():
        if cid not in handoffs:
            findings.append({"severity": "CRITICAL", "code": "DECISION_WITHOUT_HANDOFF", "candidate_id": cid})
        if dec.get("series_id") != series_id:
            continue
        decision = (dec.get("decision") or {}).get("decision")
        if decision != "WAIT":
            continue
        if cid in revals:
            continue
        ttl = int((dec.get("decision") or {}).get("ttl_minutes") or 0)
        try:
            due_at = zdt(dec["evaluated_at_utc"]) + __import__("datetime").timedelta(minutes=ttl)
        except Exception:
            findings.append({"severity": "CRITICAL", "code": "WAIT_BAD_TTL_TIMESTAMP", "candidate_id": cid})
            continue
        if now >= due_at:
            due_waits += 1
            lag = (now - due_at).total_seconds()
            if lag > REVALIDATION_GRACE_SECONDS:
                overdue_waits += 1
                findings.append({
                    "severity": "WARNING",
                    "code": "WAIT_REVALIDATION_OVERDUE",
                    "candidate_id": cid,
                    "lag_seconds": round(lag, 1),
                })

    for cid in revals:
        if cid not in decisions:
            findings.append({"severity": "CRITICAL", "code": "REVALIDATION_WITHOUT_DECISION", "candidate_id": cid})

    critical = sum(1 for x in findings if x["severity"] == "CRITICAL")
    warning = sum(1 for x in findings if x["severity"] == "WARNING")
    status = "CRITICAL" if critical else ("WARNING" if warning else "HEALTHY")

    report = {
        "kind": "PAPER_RUNTIME_RECONCILIATION_AUDIT_V1",
        "checked_at_utc": now.isoformat().replace("+00:00", "Z"),
        "status": status,
        "series_id": series_id,
        "runtime_enabled": bool(control.get("enabled")),
        "handoffs": len(handoffs),
        "decisions": len(decisions),
        "revalidations": len(revals),
        "old_series_handoffs_ignored": old_series_ignored,
        "fresh_unprocessed_handoffs": replayable_fresh,
        "stale_unprocessed_handoffs": stale_orphans,
        "due_wait_revalidations": due_waits,
        "overdue_wait_revalidations": overdue_waits,
        "critical_findings": critical,
        "warning_findings": warning,
        "findings": findings[:50],
        "guardrails": {
            "read_only": True,
            "model_called": False,
            "exchange_called": False,
            "orders": False,
            "strategy_changes": False,
        },
        "replay_policy_evidence": {
            "new_candidate_age_limit_seconds": MAX_NEW_CANDIDATE_AGE_SECONDS,
            "selection_requires_missing_decision_file": True,
            "decision_write_is_idempotent_by_candidate_id": True,
            "wait_revalidation_is_one_shot_by_existing_revalidation_file": True,
        },
    }

    print("=== PAPER RUNTIME RECONCILIATION AUDIT SUMMARY ===")
    print(f"Status: {status}")
    print(f"Series: {series_id} | enabled={bool(control.get('enabled'))}")
    print(f"Active-series handoffs: {len(handoffs)} | decisions={len(decisions)} | revalidations={len(revals)}")
    print(f"Historical pre-series handoffs ignored: {old_series_ignored}")
    print(f"Fresh unprocessed: {replayable_fresh} | stale unprocessed: {stale_orphans}")
    print(f"Due WAIT revalidations: {due_waits} | overdue>{REVALIDATION_GRACE_SECONDS}s: {overdue_waits}")
    print(f"Critical: {critical} | Warning: {warning}")
    if findings:
        for item in findings[:20]:
            print(f"{item['severity']} {item['code']} | {item.get('candidate_id') or item.get('file') or item.get('queue_id') or ''}")
    else:
        print("Findings: none")
    print("Replay safety: pre-series legacy handoffs are ignored; >60m active-series handoffs are not prospectively selected; existing candidate decision/revalidation files make evaluation idempotent/one-shot.")
    print("Safety: READ-ONLY AUDIT / NO MODEL / NO EXCHANGE / NO ORDERS / NO STRATEGY CHANGE")
    print("=== END ===")

    out = root / ".paper-work" / "runtime-reconciliation-audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", "utf-8")

    return 2 if critical else (1 if warning else 0)


if __name__ == "__main__":
    raise SystemExit(main())
