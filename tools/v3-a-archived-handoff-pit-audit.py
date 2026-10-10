#!/usr/bin/env python3
"""Read-only audit of 12 historical V2R4 scanner handoffs for V3-A research.

Standard library only; no HTTP, model, credentials, trading state changes or writes.
Outcome labels in the casepack are never used to evaluate a candidate.
Historical market-bar availability *outside* each original handoff is NOT implied.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


def clock(value: str) -> datetime:
    d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("timezone required")
    return d.astimezone(timezone.utc)


def verify_handoff(row: dict, expected: dict, filename: str) -> dict:
    """Check identity and source completeness; never consume retrospective labels."""
    cid = expected["candidate_id"]
    pair = expected["pair"]
    if not isinstance(row, dict) or row.get("candidate_id") != cid or row.get("pair") != pair:
        return {"status": "IDENTITY_MISMATCH"}
    # The Mini-PC stores handoffs with wrappers/prefixes in the filename.
    # Trust the validated canonical identity in the JSON, never a filename-only hit.
    if cid not in Path(filename).stem or row.get("action") != "REVIEW_ONLY_NOT_ORDER":
        return {"status": "IDENTITY_MISMATCH"}
    try:
        event = clock(row["event_time_utc"])
        t0 = clock(expected["original_evaluation_utc"])
        if event > t0 or (t0 - event).total_seconds() > 3600:
            return {"status": "EVENT_CLOCK_INVALID"}
        if int(row["event_ts"]) != int(event.timestamp()):
            return {"status": "EVENT_CLOCK_INVALID"}
        run = int(row["source_scanner_run_id"])
        tag = pair.replace("/", "-")
        if cid != event.strftime("%Y%m%d-%H%M%S") + "-" + tag + "-r" + str(run):
            return {"status": "IDENTITY_MISMATCH"}
        if row.get("queue_id") != f"{run}:{tag}:{int(event.timestamp())}":
            return {"status": "IDENTITY_MISMATCH"}
    except (KeyError, ValueError, TypeError, OverflowError):
        return {"status": "EVENT_CLOCK_INVALID"}

    has_candidate = isinstance(row.get("scanner_candidate"), dict) and bool(row["scanner_candidate"])
    has_market_context = (isinstance(row.get("scanner_market_context"), dict)
                          and bool(row["scanner_market_context"]))
    evidence = row.get("candidate_entry_evidence")
    if not isinstance(evidence, dict):
        context = row.get("scanner_market_context")
        evidence = context.get("candidate_entry_evidence") if isinstance(context, dict) else None
    pit_claim = False
    if isinstance(evidence, dict):
        try:
            times = [clock(evidence[k]) for k in ("observed_at_utc", "known_at_utc")]
            frames = evidence["frames"]
            if (times[0] <= times[1] <= event
                    and evidence.get("pair") == pair
                    and evidence.get("status") == "COMPLETE"
                    and isinstance(frames, dict)
                    and all(str(k) in frames and frames[str(k)].get("status") == "VALID"
                            and clock(frames[str(k)]["last_closed_bar_end_utc"]) <= times[0]
                            for k in (1, 5, 15))
                    and "atr14_eur" in frames["15"]):
                pit_claim = True
        except (KeyError, ValueError, TypeError, AttributeError):
            pass
    return {
        "status": "ORIGINAL_HANDOFF_VALID",
        "scanner_candidate_present": has_candidate,
        "scanner_market_context_present": has_market_context,
        "historical_coin_pit_claim_in_handoff": pit_claim,
        "historical_coin_pit_authoritatively_proven": False,  # needs separately frozen as-of source
    }


def audit(casepack: dict, runtime_root: Path) -> dict:
    cases = casepack.get("cases")
    if (casepack.get("kind") != "V3_A_RETROSPECTIVE_MATCHED_NO_BUY_CASEPACK_V1"
            or not isinstance(cases, list) or len(cases) != 12
            or len(set(c.get("candidate_id") for c in cases)) != 12):
        raise ValueError("Unexpected fixed twelve-case research manifest")

    dirs = sorted(p / "handoff_queue" for p in runtime_root.glob("v2r4-paper*")
                  if p.is_dir() and (p / "handoff_queue").is_dir())
    results = []
    for case in cases:
        cid = case["candidate_id"]
        matched = []
        # Match the filename convention actually used on the Mini-PC, identical
        # to the previously successful read-only presence check. A filename
        # hit alone proves nothing; verify_handoff checks the JSON identity.
        for folder in dirs:
            for file in sorted(folder.glob("*" + cid + "*.json")):
                if not file.is_file():
                    continue
                try:
                    candidate = json.loads(file.read_text("utf-8"))
                    matched.append(verify_handoff(candidate, case, file.name))
                except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
                    matched.append({"status": "INVALID_JSON"})
        if not matched:
            result = {"status": "MISSING_ORIGINAL"}
        elif len(matched) != 1:
            result = {"status": "AMBIGUOUS_MULTIPLE_COPIES"}
        else:
            result = matched[0]
        results.append({"pair": case["pair"], "candidate_id": cid, **result})

    statuses = Counter(x["status"] for x in results)
    # An absent/corrupt identity lacks those fields. Never sum None or fail
    # the entire bounded audit because one historical handoff is missing.
    complete = sum(1 for x in results if
                   x.get("scanner_candidate_present") is True
                   and x.get("scanner_market_context_present") is True)
    claims = sum(x.get("historical_coin_pit_claim_in_handoff", False) for x in results)
    return {
        "kind": "V3_A_HISTORICAL_HANDOFF_READONLY_PIT_AUDIT_V1",
        "status": "HANDOFF_AUDIT_COMPLETE_NOT_A_MODEL_REPLAY",
        "cases": results,
        "case_count": len(results),
        "valid_handoff_count": statuses["ORIGINAL_HANDOFF_VALID"],
        "missing_original_count": statuses["MISSING_ORIGINAL"],
        "ambiguous_original_count": statuses["AMBIGUOUS_MULTIPLE_COPIES"],
        "invalid_original_count": sum(v for k, v in statuses.items()
                                      if k not in ("ORIGINAL_HANDOFF_VALID",
                                                   "MISSING_ORIGINAL",
                                                   "AMBIGUOUS_MULTIPLE_COPIES")),
        "original_scanner_context_count": complete,
        "coin_pit_claims_inside_handoff": claims,
        "historical_coin_pit_authoritatively_proven_count": 0,
        "other_local_candle_archives_checked": False,
        "model_calls": 0,
        "secrets_read": False,
        "orders": False,
        "paper_state_changed": False,
        "retrospective_outcomes_used_as_model_features": False,
        "next_gate": "HISTORICAL_PIT_SOURCE_ARCHIVE_PROVENANCE_OR_PROSPECTIVE_MATCHED_INPUT_ONLY",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--casepack", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.casepack.read_text("utf-8"))
        result = audit(manifest, args.runtime_root)
        for case in result["cases"]:
            print(f"{case['pair']:<12} {case['status']:<28} "
                  f"scanner={int(bool(case.get('scanner_candidate_present')))} "
                  f"context={int(bool(case.get('scanner_market_context_present')))} "
                  f"coin_pit_claim={int(bool(case.get('historical_coin_pit_claim_in_handoff')))}")
        print("SUMMARY " + json.dumps({k: v for k, v in result.items() if k != "cases"}, sort_keys=True))
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        print("BLOCKED_LOCAL_INPUT_OR_MANIFEST", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
