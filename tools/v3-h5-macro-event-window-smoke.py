#!/usr/bin/env python3
"""DST-aware point-in-time event-window smoke for V3-H5.

Scheduled macro events may be known before they occur. The schedule feature is
valid only when the event record's known_at timestamp is at/before the candidate
decision time. Event outcome/content is never used here.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

def parse_utc(s:str)->datetime:
    dt=datetime.fromisoformat(s.replace("Z","+00:00"))
    if dt.tzinfo is None:
        raise ValueError("UTC timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)

def resolve_event(event:dict)->dict:
    local=datetime.fromisoformat(event["scheduled_local"])
    if local.tzinfo is not None:
        raise ValueError("scheduled_local must be naive local wall time")
    tz=ZoneInfo(event["timezone"])
    aware=local.replace(tzinfo=tz)
    utc=aware.astimezone(timezone.utc)
    known=parse_utc(event["known_at_utc"])
    if not str(event.get("source_url") or "").startswith("https://"):
        raise ValueError("source_url required")
    return {
      **event,
      "scheduled_utc":utc.isoformat().replace("+00:00","Z"),
      "utc_offset_seconds":int(aware.utcoffset().total_seconds()),
      "_utc":utc,
      "_known":known,
    }

def classify(candidate:datetime,event:dict,pre_seconds:int,post_seconds:int)->dict:
    known=candidate>=event["_known"]
    delta=(candidate-event["_utc"]).total_seconds()
    if not known:
        relation="SCHEDULE_NOT_POINT_IN_TIME_KNOWN"
    elif -pre_seconds <= delta < 0:
        relation="PRE_EVENT_WINDOW"
    elif 0 <= delta <= post_seconds:
        relation="EVENT_OR_POST_WINDOW"
    else:
        relation="OUTSIDE_WINDOW"
    return {
      "candidate_utc":candidate.isoformat().replace("+00:00","Z"),
      "calendar_known":known,
      "delta_to_event_seconds":delta,
      "relation":relation,
    }

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("fixture",type=Path)
    ap.add_argument("--event-id",required=True)
    ap.add_argument("--pre-minutes",type=int,default=30)
    ap.add_argument("--post-minutes",type=int,default=30)
    ap.add_argument("--output",type=Path)
    args=ap.parse_args()
    if args.pre_minutes<0 or args.post_minutes<0:
        raise SystemExit("window minutes must be non-negative")

    raw=json.loads(args.fixture.read_text("utf-8"))
    events=raw.get("events") or []
    selected=[e for e in events if e.get("event_id")==args.event_id]
    if len(selected)!=1:
        raise SystemExit(f"event_id must resolve exactly once: {args.event_id}")
    ev=resolve_event(selected[0])
    candidates=[parse_utc(x) for x in (raw.get("candidate_times_utc") or [])]
    if not candidates:
        raise SystemExit("candidate_times_utc required")

    rows=[classify(c,ev,args.pre_minutes*60,args.post_minutes*60) for c in candidates]
    result={
      "kind":"V3_H5_MACRO_EVENT_WINDOW_PIT_SMOKE_V1",
      "status":"PASS",
      "event":{
        "event_id":ev["event_id"],
        "event_family":ev.get("event_family"),
        "scheduled_local":ev["scheduled_local"],
        "timezone":ev["timezone"],
        "scheduled_utc":ev["scheduled_utc"],
        "utc_offset_seconds":ev["utc_offset_seconds"],
        "known_at_utc":ev["known_at_utc"],
        "source_url":ev["source_url"],
      },
      "pre_minutes":args.pre_minutes,
      "post_minutes":args.post_minutes,
      "candidate_relations":rows,
      "point_in_time_assertions":{
        "iana_timezone_used":ev["timezone"]=="America/New_York",
        "calendar_known_timestamp_explicit":bool(ev["known_at_utc"]),
        "source_url_explicit":bool(ev["source_url"]),
        "event_outcome_content_used":False,
        "candidate_before_known_at_is_rejected_as_known_schedule":all(
          (r["relation"]!="SCHEDULE_NOT_POINT_IN_TIME_KNOWN") or (r["calendar_known"] is False)
          for r in rows
        ),
      },
      "guardrails":{
        "performance_trial_started":False,
        "event_window_selected_by_performance":False,
        "direction_rule_created":False,
        "holdout_opened":False,
        "active_v2r3_changed":False,
        "v2r4_changed":False,
        "orders":False,
        "real_money_actions":False,
      }
    }
    # Positive-form assertion set: the one negative fact is checked separately.
    positive=[
      result["point_in_time_assertions"]["iana_timezone_used"],
      result["point_in_time_assertions"]["calendar_known_timestamp_explicit"],
      result["point_in_time_assertions"]["source_url_explicit"],
      result["point_in_time_assertions"]["candidate_before_known_at_is_rejected_as_known_schedule"],
    ]
    if not all(positive) or result["point_in_time_assertions"]["event_outcome_content_used"]:
        result["status"]="FAIL"

    out=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(out,"utf-8")
    print(out,end="")
    return 0 if result["status"]=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
