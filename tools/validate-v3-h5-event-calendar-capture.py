#!/usr/bin/env python3
"""Validate a prospective official macro-event calendar capture."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

def parse_utc(s:str)->datetime:
    d=datetime.fromisoformat(s.replace("Z","+00:00"))
    if d.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return d.astimezone(timezone.utc)

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("capture",type=Path)
    args=ap.parse_args()
    j=json.loads(args.capture.read_text("utf-8"))
    errors=[]
    if j.get("kind")!="V3_H5_OFFICIAL_EVENT_CALENDAR_CAPTURE_V1":
        errors.append("kind mismatch")
    if j.get("status")!="PROSPECTIVE_CAPTURE":
        errors.append("status mismatch")
    captured=parse_utc(j["captured_at_utc"])
    tz=ZoneInfo(j["timezone"])
    source_ids={x.get("id") for x in (j.get("sources") or [])}
    if not source_ids:
        errors.append("sources required")
    ids=[]
    for e in j.get("events") or []:
        eid=e.get("event_id"); ids.append(eid)
        local=datetime.fromisoformat(e["scheduled_local"])
        if local.tzinfo is not None:
            errors.append(f"{eid}: scheduled_local must be naive")
            continue
        resolved=local.replace(tzinfo=tz).astimezone(timezone.utc)
        stated=parse_utc(e["scheduled_utc"])
        known=parse_utc(e["known_at_utc"])
        if resolved!=stated:
            errors.append(f"{eid}: UTC conversion mismatch {resolved} != {stated}")
        if known!=captured:
            errors.append(f"{eid}: known_at must equal prospective capture timestamp")
        if known>=stated:
            errors.append(f"{eid}: event must be future relative to capture")
        refs=set(e.get("source_ids") or [])
        if not refs or not refs.issubset(source_ids):
            errors.append(f"{eid}: invalid source references")
    if len(ids)!=len(set(ids)):
        errors.append("duplicate event_id")
    g=j.get("guardrails") or {}
    if g.get("retroactive_use_before_capture_allowed") is not False:
        errors.append("retroactive use must be false")
    if g.get("event_outcome_or_statement_content_included") is not False:
        errors.append("outcome/content must not be included")
    if g.get("market_direction_label_included") is not False:
        errors.append("direction label must not be included")
    if g.get("automatic_trade_gate_enabled") is not False:
        errors.append("automatic trade gate must be false")
    if g.get("real_money_actions") is not False:
        errors.append("real-money actions must be false")

    out={
      "kind":"V3_H5_EVENT_CALENDAR_CAPTURE_VALIDATION_V1",
      "status":"PASS" if not errors else "FAIL",
      "captured_at_utc":j.get("captured_at_utc"),
      "event_count":len(j.get("events") or []),
      "event_ids":ids,
      "errors":errors,
      "guardrails":{
        "retroactive_backfill_allowed":False,
        "strategy_changed":False,
        "orders":False,
        "real_money_actions":False
      }
    }
    print(json.dumps(out,sort_keys=True))
    return 0 if not errors else 2

if __name__=="__main__":
    raise SystemExit(main())
