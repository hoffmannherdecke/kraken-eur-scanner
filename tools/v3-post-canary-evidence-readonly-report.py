#!/usr/bin/env python3
"""One-shot READ-ONLY V3 post-28h evidence report from a trusted Cloud export.

Accepts a finite JSON envelope via stdin ONLY (no API key, network, files,
new scheduler or cloud writes). The caller must retrieve the true Supabase
rows and physically establish any stated Windows Task end acknowledgement.
A green observation report NEVER authorizes a strategy or real-money change.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Exact repository root is required when invoked via `python tools/...`,
# not a guessed user PYTHONPATH or a network/package installation.
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from paper_evaluator.v3_paper_post_canary_evidence_verdict_v1 import verdict

MAX_STDIN_BYTES=12_000_000
EXPECTED_KIND="V3_READONLY_SUPABASE_RECEIPTS_FOR_VERDICT_V1"
FIXED_DEADLINE="2026-10-13T12:00:12.2795431Z"


def report_once(document:dict)->dict:
    if not isinstance(document,dict) or document.get("kind")!=EXPECTED_KIND:
        raise ValueError("requires explicit independent Supabase snapshot envelope")
    if document.get("mode")!="READ_ONLY_NO_ACTIVATION":
        raise ValueError("read-only execution mode required")
    if document.get("cloud_source_verified_by_caller") is not True:
        raise ValueError("Supabase source provenance not attested by caller")
    if document.get("new_model_budget") is not False:
        raise ValueError("report can never grant model budget")
    active=document.get("active_paper_series")
    rows=document.get("cloud_rows")
    if not isinstance(rows,list) or not isinstance(active,list):
        raise ValueError("all original cloud rows and active series must be provided")
    output=verdict(
        cloud_rows=rows,as_of_utc=document["as_of_utc"],
        observer_deadline_utc=FIXED_DEADLINE,
        active_paper_series=active,
        physical_observer_end_ack=document.get("physical_observer_end_ack",False))
    output["cloud_snapshot_provenance"]="CALLER_ATTESTED_READONLY_EXPORT_NOT_INDEPENDENTLY_AUTHENTICATED_BY_CLI"
    output["cli_does_not_contact_supabase"]=True
    output["cli_does_not_start_windows_task"]=True
    output["existing_10_15_work_or_controller_only"]=True
    return output


def main()->int:
    if sys.stdin.isatty():
        raise ValueError("JSON stdin required: no implicit Supabase network access")
    raw=sys.stdin.buffer.read(MAX_STDIN_BYTES+1)
    if len(raw)>MAX_STDIN_BYTES:
        raise ValueError("read-only snapshot exceeds bounded input")
    if not raw.strip():
        raise ValueError("empty snapshot is not valid evidence")
    doc=json.loads(raw)
    result=report_once(doc)
    sys.stdout.write(json.dumps(result,sort_keys=True,ensure_ascii=True)+"\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
