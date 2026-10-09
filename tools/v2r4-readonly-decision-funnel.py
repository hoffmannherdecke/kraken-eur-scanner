#!/usr/bin/env python3
"""One-shot local V2R4 first-decision -> WAIT/recheck cohort diagnostic.

Read-only. No model, exchange, Supabase, disk writes, tasks, API secrets or network.
Rechecks are EVENTS, not distinct trades or independent candidates.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

EXPECTED_SERIES = "PAPER-V2R4-20261009T110135Z"
EXPECTED_APP = "v2r4-paper-stage-d8b35a8ec2e6"
POSITIVE_CODES = frozenset({
    "SPREAD_ACCEPTABLE", "PAIR_ONLINE", "PAIR_ONLINE_MINIMUMS_PASS",
})
# This is an exhaustive *literal* affirmative set for the current observed
# screenshots. Other codes are evidence observations, NOT automatically vetoes.


def dt(s: str) -> datetime:
    value = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("naive timestamp")
    return value.astimezone(timezone.utc)


def read_snapshots(folder: Path, expected: str) -> tuple[list[dict], int]:
    records, corrupt = [], 0
    if not folder.is_dir():
        return records, 0
    for file in folder.glob("*.json"):
        try:
            row = json.loads(file.read_text("utf-8"))
            if not isinstance(row, dict):
                raise ValueError("not object")
            if row.get("series_id") == expected:
                records.append(row)
        except (ValueError, OSError, UnicodeError, TypeError):
            corrupt += 1
    return records, corrupt


def latest_ts(record: dict) -> datetime:
    for key in ("recheck_completed_at_utc", "completed_at_utc",
                "revalidated_at_utc", "recheck_started_at_utc"):
        if record.get(key):
            try:
                return dt(record[key])
            except (ValueError, TypeError):
                continue
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def describe_cohort(
    initial: list[dict], rechecks: list[dict], *,
    now: datetime,
) -> dict[str, Any]:
    """Count initial candidates once and recheck event + final state separately."""
    initial_by_id: dict[str, dict] = {}
    bad_initial = 0
    for item in initial:
        cid = item.get("candidate_id")
        if not isinstance(cid, str) or not cid or not isinstance(item.get("decision"), dict):
            bad_initial += 1
            continue
        if cid in initial_by_id:
            bad_initial += 1
            continue
        initial_by_id[cid] = item

    decision_counts = Counter()
    reasons_by_decision: dict[str, Counter] = defaultdict(Counter)
    wait_conditions: Counter = Counter()
    youngest = None
    for item in initial_by_id.values():
        d = item["decision"]
        typ = str(d.get("decision") or "UNKNOWN")
        decision_counts[typ] += 1
        for code in set(str(x) for x in (d.get("reason_codes") or []) if isinstance(x, str)):
            reasons_by_decision[typ][code] += 1
        if typ == "WAIT":
            plan = item.get("v2r4_trigger_plan") or {}
            for entry in (plan.get("conditions") or []):
                if isinstance(entry, dict):
                    wait_conditions[str(entry.get("metric") or "UNKNOWN")] += 1
        stamp = item.get("candidate_event_time_utc") or item.get("evaluated_at_utc")
        if stamp:
            try:
                t = dt(stamp)
                youngest = max(t, youngest) if youngest else t
            except (ValueError, TypeError):
                pass

    by_id: dict[str, list[dict]] = defaultdict(list)
    invalid_rechecks = 0
    types: Counter = Counter()
    outcomes: Counter = Counter()
    for item in rechecks:
        cid = item.get("candidate_id")
        decision = item.get("decision") or {}
        if not isinstance(cid, str) or not cid or not isinstance(decision, dict):
            invalid_rechecks += 1
            continue
        types[str(item.get("kind") or "UNKNOWN")] += 1
        outcomes[str(decision.get("decision") or "UNKNOWN")] += 1
        by_id[cid].append(item)

    last = {cid: max(rows, key=latest_ts) for cid, rows in by_id.items()}
    final_codes: Counter = Counter()
    last_outcomes: Counter = Counter()
    matched = 0
    matched_wait = 0
    for cid, row in last.items():
        if cid not in initial_by_id:
            continue
        matched += 1
        if initial_by_id[cid]["decision"].get("decision") != "WAIT":
            continue
        matched_wait += 1
        d = row["decision"]
        last_outcomes[str(d.get("decision") or "UNKNOWN")] += 1
        for code in set(str(x) for x in (d.get("reason_codes") or []) if isinstance(x, str)):
            final_codes[code] += 1

    wait_without_recheck = 0
    wait_without_recheck_mature = 0
    wait_without_recheck_not_due = 0
    for cid, item in initial_by_id.items():
        d = item["decision"]
        if d.get("decision") != "WAIT" or cid in by_id:
            continue
        wait_without_recheck += 1
        ttl = d.get("ttl_minutes")
        completed = item.get("evaluated_at_utc")
        try:
            deadline = dt(completed) + timedelta(minutes=int(ttl))
            if 0 < int(ttl) <= 60 and deadline < now:
                wait_without_recheck_mature += 1
            else:
                wait_without_recheck_not_due += 1
        except (ValueError, TypeError, OverflowError):
            wait_without_recheck_not_due += 1

    episode_counts = Counter()
    for item in initial_by_id.values():
        stamp = item.get("candidate_event_time_utc")
        pair = item.get("pair")
        if not stamp or not pair:
            continue
        try:
            when = dt(stamp)
            episode_counts[(str(pair), when.strftime("%Y-%m-%d"),
                            when.hour // 6)] += 1
        except (ValueError, TypeError):
            continue

    observed_gap = 0
    for item in initial_by_id.values():
        ctx = item.get("decision_context") or {}
        if "candidate_entry_evidence" not in ctx:
            observed_gap += 1

    return {
        "unique_initial": len(initial_by_id),
        "invalid_or_duplicate_initial": bad_initial,
        "initial_counts": decision_counts,
        "initial_codes": reasons_by_decision,
        "positive_reason_codes": POSITIVE_CODES,
        "WAIT_watch_metrics": wait_conditions,
        "missing_structured_entry_provenance": observed_gap,
        "latest_candidate_event": youngest,
        "recheck_event_count": sum(outcomes.values()),
        "invalid_recheck_events": invalid_rechecks,
        "recheck_events_by_decision": outcomes,
        "recheck_events_by_kind": types,
        "distinct_recheck_candidate_ids": len(last),
        "matched_initial_ids_with_recheck": matched,
        "orphan_recheck_ids": len(last) - matched,
        "matched_initial_WAIT_ids_with_recheck": matched_wait,
        "latest_matched_WAIT_states": last_outcomes,
        "latest_matched_WAIT_codes": final_codes,
        "WAIT_ids_without_recheck": wait_without_recheck,
        "WAIT_due_no_recheck": wait_without_recheck_mature,
        "WAIT_not_yet_due_or_unparseable": wait_without_recheck_not_due,
        "pair_6h_episodes": len(episode_counts),
        "repeat_events_inside_pair_6h": sum(n-1 for n in episode_counts.values() if n>1),
    }


def print_counter(label: str, counter: Counter, limit: int=12) -> None:
    print(label + ":", sum(counter.values()), "occurrences")
    for key, n in counter.most_common(limit):
        print(" ", n, str(key))


def run(app: Path, expected: str=EXPECTED_SERIES) -> int:
    if expected != EXPECTED_SERIES or app.name != EXPECTED_APP:
        raise ValueError("wrong pinned technical V2R4 series or stage")
    control = json.loads((app/"paper_runtime_control.json").read_text("utf-8"))
    if control.get("series_id") != expected or control.get("paper_only") is not True:
        raise ValueError("wrong active technical series / unsafe control")
    if control.get("real_money_actions_enabled") is not False:
        raise ValueError("real money flag must be false")
    decisions, d_bad = read_snapshots(app/"paper_decisions",expected)
    rechecks, r_bad = read_snapshots(app/"paper_rechecks",expected)
    m = describe_cohort(decisions,rechecks,now=datetime.now(timezone.utc))
    print("V2R4_INITIAL_RECHECK_COHORT_ONE_SHOT_READ_ONLY")
    print("SERIES:", expected)
    print("INITIAL_UNIQUE:",m["unique_initial"],"BAD_OR_DUPLICATE:",m["invalid_or_duplicate_initial"],"UNREADABLE:",d_bad)
    print_counter("INITIAL_DECISIONS",m["initial_counts"])
    print("INITIAL_BUY:",m["initial_counts"].get("BUY_SCOUT",0))
    print("COIN_ENTRY_PROVENANCE_ABSENT:",m["missing_structured_entry_provenance"],"of",m["unique_initial"])
    print("LATEST_CANDIDATE_EVENT_UTC:", m["latest_candidate_event"].isoformat() if m["latest_candidate_event"] else "UNKNOWN")
    for typ in ("WAIT","REJECT","BUY_SCOUT"):
        codes=m["initial_codes"].get(typ,Counter())
        positives=Counter({k:v for k,v in codes.items() if k in POSITIVE_CODES})
        other=Counter({k:v for k,v in codes.items() if k not in POSITIVE_CODES})
        print_counter(f"INITIAL_{typ}_AFFIRMATIVE_CODES",positives,8)
        print_counter(f"INITIAL_{typ}_OTHER_EVIDENCE_CODES_NOT_AUTOMATICALLY_CAUSAL_VETO",other,14)
    print_counter("WAIT_WATCH_METRICS_NOT_UNIQUE_CANDIDATES",m["WAIT_watch_metrics"],9)
    print("RECHECK_EVENTS:",m["recheck_event_count"],"UNREADABLE:",r_bad)
    print_counter("RECHECK_EVENT_DECISIONS",m["recheck_events_by_decision"])
    print_counter("RECHECK_EVENT_KINDS",m["recheck_events_by_kind"])
    print("RECHECK_UNIQUE_IDS:",m["distinct_recheck_candidate_ids"],
          "MATCHED_INITIAL_IDS:",m["matched_initial_ids_with_recheck"],
          "ORPHAN_IDS:",m["orphan_recheck_ids"])
    print("INITIAL_WAIT_IDS_WITH_RECHECK:",m["matched_initial_WAIT_ids_with_recheck"])
    print_counter("LATEST_RECHECK_STATE_PER_INITIAL_WAIT_ID",m["latest_matched_WAIT_states"])
    print_counter("LATEST_RECHECK_REASON_CODES_PER_INITIAL_WAIT_ID",m["latest_matched_WAIT_codes"],14)
    print("INITIAL_WAIT_NO_RECHECK:",m["WAIT_ids_without_recheck"],
          "PAST_TTL_WITHOUT_RECHECK:",m["WAIT_due_no_recheck"],
          "PENDING_OR_UNKNOWN:",m["WAIT_not_yet_due_or_unparseable"])
    print("PAIR_6H_EPISODES:",m["pair_6h_episodes"],
          "EXTRA_SIGNALS_SAME_PAIR_6H:",m["repeat_events_inside_pair_6h"])
    print("INTERPRETATION: RECHECK events can repeat; supportive codes are not rejection reasons;")
    print("NO_INFERENCE_ON_PROFITABILITY_OR_WHETHER_ANY_REJECT_WAS_INCORRECT")
    print("SOURCE_ONLY_NO_MODEL_NO_NETWORK_NO_WRITES_NO_STRATEGY_CHANGE")
    return 0


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--app",required=True,type=Path)
    p.add_argument("--series",default=EXPECTED_SERIES)
    a=p.parse_args()
    try:
        return run(a.app,a.series)
    except (OSError,ValueError,TypeError,KeyError,json.JSONDecodeError) as e:
        print("BLOCKED_READ_ONLY_COHORT_DIAGNOSTIC:",type(e).__name__)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
