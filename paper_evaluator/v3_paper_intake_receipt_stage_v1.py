"""Explicit, inactive V3 intake -> existing immutable local receipt staging.

This is NOT the Mini-PC runtime, Cloud ACK, authentication authority, model
budget, trade writer, or V2R4 cutover. The caller must own one isolated V3
directory and separately establish physical source-owner identity. Until then
source-catalyst events are recorded UNKNOWN, never as verified positive buys.

Crash/replay safety uses the existing O_EXCL + content-identical journal.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from collections import Counter
import hashlib
import json
import re

from paper_evaluator.v3_experimental_paper_journal_v1 import (
    make_receipt, store_receipt_explicitly,
)
from paper_evaluator.v3_paper_cloud_receipt_sync_v1 import REVISION

KIND = "V3_FUTURE_SINGLE_PAPER_WRITER_PRE_FLIGHT_PLAN_V1"
ORIGIN_SCANNER = "SCANNER"
ORIGIN_SOURCE = "VERIFIED_POSITIVE_SOURCE_CATALYST"
AUDIT_KIND = "V3_ROUTER_REJECTED_ORIGINAL_AUDIT_V1"
AUDIT_ID = re.compile(r"^V3-INPUT-REJECT-[0-9a-f]{32}$")
REASONS = {
    "SELECTED": "ORIGINAL_SELECTED_FOR_PRE_MODEL_REVIEW_ONLY",
    "DEFERRED": "CAPACITY_DEFERRED_NOT_A_NEGATIVE_MARKET_DECISION",
    "COALESCED": "SAME_PAIR_CONCURRENT_REVIEW_COALESCED_NOT_LOST",
}


def prepare_receipts(preflight: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    """Pure stage plan. Never treat producer metadata as authentication."""
    if not isinstance(preflight, dict) or preflight.get("kind") != KIND:
        raise ValueError("only the canonical future single-writer preflight is accepted")
    if any(preflight.get(k) is not False for k in (
        "model_http_authorized", "paper_writer_active", "orders",
        "real_money_actions", "v2r4_changed", "cloud_active_series_changed"
    )):
        raise ValueError("intake staging has no spend/order/activation authority")
    series = preflight.get("series_id")
    at = preflight.get("at_utc")
    ingress = preflight.get("ingress")
    if not isinstance(ingress, dict):
        raise ValueError("canonical ingress is required")
    selected = preflight.get("selected_candidates")
    deferred = ingress.get("capacity_deferred_originals")
    coalesced = ingress.get("same_pair_coalesced_originals")
    rejected_originals = ingress.get("rejected_originals")
    reviews = preflight.get("review_preflights")
    if not all(isinstance(x, list) for x in
               (selected, deferred, coalesced, rejected_originals, reviews)):
        raise ValueError("complete original intake and rejected audit lists required")
    if sum(map(len, (selected, deferred, coalesced, rejected_originals))) > 4000:
        raise ValueError("too many original events in one bounded stage")
    counts = ingress.get("counts")
    reasons = ingress.get("dispositions")
    if not isinstance(counts, dict) or not isinstance(reasons, dict):
        raise ValueError("original disposition counts required")
    if counts.get("selected") != len(selected):
        raise ValueError("selected originals do not match intake count")
    if reasons.get(REASONS["DEFERRED"], 0) != len(deferred):
        raise ValueError("capacity deferral originals are missing")
    if reasons.get(REASONS["COALESCED"], 0) != len(coalesced):
        raise ValueError("coalesced originals are missing")
    if not all(isinstance(n, int) and n >= 0 for n in reasons.values()):
        raise ValueError("invalid rejection counts")
    if sum(reasons.values()) != counts.get("suppressed_or_deferred"):
        raise ValueError("unaccounted rejected/deferred originals")
    expected_rejected = Counter(reasons)
    for key, present in ((REASONS["DEFERRED"], len(deferred)),
                         (REASONS["COALESCED"], len(coalesced))):
        if present:
            expected_rejected[key] -= present
            if expected_rejected[key] == 0:
                del expected_rejected[key]
    observed_rejected = Counter()
    for audit in rejected_originals:
        if not isinstance(audit, dict) or audit.get("kind") != AUDIT_KIND:
            raise ValueError("rejected original audit envelope missing")
        observed_rejected[audit.get("reason")] += 1
    if observed_rejected != expected_rejected:
        raise ValueError("missing or conflicting individually identified router rejections")

    by_candidate: dict[str, dict[str, Any]] = {}
    result: list[dict[str, Any]] = []
    for group, rows in (("SELECTED", selected),
                        ("DEFERRED", deferred), ("COALESCED", coalesced)):
        for candidate in rows:
            if not isinstance(candidate, dict):
                raise ValueError("original candidate must be an object")
            cid = candidate.get("candidate_id")
            origin = candidate.get("entry_origin")
            if not isinstance(cid, str) or not cid or cid in by_candidate:
                raise ValueError("original identity missing, duplicated or conflicting")
            if origin not in (ORIGIN_SCANNER, ORIGIN_SOURCE):
                raise ValueError("untrusted candidate entry origin")
            if candidate.get("deferred_recheck") not in (None,False,True):
                raise ValueError("invalid original deferred recheck marker")
            if candidate.get("deferred_recheck") is True and origin!=ORIGIN_SCANNER:
                raise ValueError("only original Scanner capacity deferral may retry")
            by_candidate[cid] = candidate
            source_unverified = origin == ORIGIN_SOURCE
            if group=="DEFERRED" and candidate.get("deferred_recheck") is True:
                # The FIRST/SKIP historical original already exists.
                # Another cycle must not overwrite it with a later known_at.
                continue
            phase = "SOURCE_INPUT" if source_unverified else "SCANNER_CAPTURE"
            reason = REASONS[group]
            data = {
                "candidate_origin": origin,
                "source_status": ("SOURCE_OWNER_RUNTIME_AUTH_NOT_PROVEN"
                                  if source_unverified else reason),
                "phase_failure_stage": reason if group != "SELECTED" else None,
                "raw_reason_codes": [reason] if group != "SELECTED" else [],
            }
            result.append(make_receipt(
                series_id=series, revision=REVISION, candidate_id=cid,
                pair=candidate.get("pair"),
                event_time_utc=candidate.get("event_time_utc"),
                known_at_utc=at, phase=phase,
                result=("UNKNOWN" if source_unverified else
                        "SEEN" if group == "SELECTED" else "SKIP"),
                data=data, event_key=("DEFERREDRECHECK"
                      if group=="SELECTED" and candidate.get("deferred_recheck") is True
                      else "DEFERREDCOALESCED"
                      if group=="COALESCED" and candidate.get("deferred_recheck") is True
                      else "FIRST")
            ))

    # A source-positive pure plan is NOT a physically authenticated runtime.
    # Only actual scanner-selected candidates may additionally journal P0.
    if len(reviews) != len(selected):
        raise ValueError("preflight is missing candidate-level review decisions")
    for candidate, decision in zip(selected, reviews):
        if not isinstance(decision, dict) or (
                decision.get("candidate_id") != candidate["candidate_id"] or
                decision.get("pair") != candidate["pair"] or
                decision.get("model_review_authorized") is not False):
            raise ValueError("preflight review mismatch or unapproved model")
        if candidate["entry_origin"] == ORIGIN_SOURCE:
            continue
        status = decision.get("status")
        if not isinstance(status, str) or not status:
            raise ValueError("original scanner review status missing")
        result.append(make_receipt(
            series_id=series, revision=REVISION,
            candidate_id=candidate["candidate_id"], pair=candidate["pair"],
            event_time_utc=candidate["event_time_utc"],
            known_at_utc=at, phase="FULL_REVIEW_ELIGIBILITY",
            result="PASS" if decision.get("eligible_for_full_model_review") is True
                     else "UNKNOWN",
            data={"review_status": status,
                  "candidate_origin": ORIGIN_SCANNER},
            event_key=("DEFERREDRECHECK"
                       if candidate.get("deferred_recheck") is True else "FIRST")
        ))
    # Rejected inputs can have a nonexistent/bogus source ID, pair or clock.
    # These AUDIT identities are never market candidates, are never eligible
    # for paper/model decisions and can never be used to assert missed PnL.
    audit_seen = set()
    for audit in rejected_originals:
        synthetic = audit.get("audit_id")
        stream = audit.get("input_stream")
        ordinal = audit.get("input_index")
        reason = audit.get("reason")
        if (not isinstance(synthetic, str) or not AUDIT_ID.fullmatch(synthetic)
                or synthetic in audit_seen or stream not in ("SCANNER", "SOURCE_CATALYST", "SOURCE_OWNER")
                or type(ordinal) is not int or not 0 <= ordinal < 2000
                or not isinstance(reason, str) or not reason.isupper()
                or audit.get("original_untrusted_and_not_tradeable") is not True):
            raise ValueError("invalid untrusted original rejection audit identity")
        audit_seen.add(synthetic)
        def limited(key:str,limit:int=150)->str|None:
            value=audit.get(key)
            return value if isinstance(value,str) and 0<len(value)<=limit else None
        original_pair=limited("original_pair_if_safe",32)
        original_clock=limited("original_event_time_if_parseable",64)
        original_cid=limited("original_candidate_id_if_safe")
        original_source=limited("original_source_event_id_if_safe")
        result.append(make_receipt(
            series_id=series,revision=REVISION,candidate_id=synthetic,
            pair="UNMAPPED/EUR",event_time_utc=at,known_at_utc=at,
            phase="SCANNER_CAPTURE" if stream=="SCANNER" else "SOURCE_INPUT",
            result="UNKNOWN",event_key="ROUTERREJECT",
            data={"source_phase":"ROUTER_REJECTION_AUDIT_NOT_TRADEABLE",
                  "source_status":"INPUT_REJECTED_NO_MODEL_AUTHORITY",
                  "source_pair_metadata_status":"AUDIT_SENTINEL_NEVER_KRAKEN_PAIR",
                  "phase_failure_stage":reason,
                  "raw_reason_codes":[reason],
                  "review_checks":{"input_index":ordinal,"input_stream":stream,
                       "original_candidate_id_if_safe":original_cid,
                       "original_pair_if_safe":original_pair,
                       "original_event_time_if_parseable":original_clock,
                       "original_source_event_id_if_safe":original_source,
                       "original_clock_may_be_stale_or_future":True}}
        ))
    return result, 0


def stage_receipts_explicitly(*, preflight: dict[str, Any],
                              journal_directory: Path) -> dict[str, Any]:
    """Writes ONLY into a caller-created isolated directory; never syncs Cloud."""
    receipts, not_attributed = prepare_receipts(preflight)
    # A forged DEFERREDRECHECK flag must never create new usable scanner
    # evidence unless the exact original immutable capacity-SKIP exists.
    for candidate in preflight.get("selected_candidates",[]):
        if candidate.get("deferred_recheck") is not True:
            continue
        original_key="|".join((preflight["series_id"],candidate["candidate_id"],
                               "SCANNER_CAPTURE","FIRST"))
        original_path=journal_directory/( hashlib.sha256(
            original_key.encode("utf-8")).hexdigest()+".json")
        try:
            original=json.loads(original_path.read_text("utf-8"))
        except (OSError,ValueError):
            raise ValueError("capacity-deferred original FIRST receipt missing")
        if (original.get("candidate_id")!=candidate["candidate_id"]
                or original.get("series_id")!=preflight["series_id"]
                or original.get("pair")!=candidate.get("pair")
                or original.get("event_time_utc")!=candidate.get("event_time_utc")
                or original.get("phase")!="SCANNER_CAPTURE"
                or original.get("event_key")!="FIRST"
                or original.get("result")!="SKIP"
                or original.get("data",{}).get("candidate_origin")!="SCANNER"
                or original.get("data",{}).get("source_status")!=
                "CAPACITY_DEFERRED_NOT_A_NEGATIVE_MARKET_DECISION"):
            raise ValueError("unverified historical capacity-deferred source")
    states = []
    for row in receipts:
        status, _ = store_receipt_explicitly(journal_directory, row)
        states.append(status)
    return {
        "status": "LOCAL_IMMUTABLE_INTAKE_RECEIPTS_ONLY_NO_RUNTIME",
        "written": states.count("IMMUTABLE_NEW_RECEIPT"),
        "identical_replays": states.count("IDEMPOTENT_IDENTICAL"),
        "originals_with_receipt": sum(
            1 for row in receipts if row["phase"] in ("SCANNER_CAPTURE", "SOURCE_INPUT")
            and not row["candidate_id"].startswith("V3-INPUT-REJECT-")
        ),
        "router_rejection_audit_receipts": sum(
            1 for row in receipts if row["event_key"] == "ROUTERREJECT"
        ),
        "owner_pre_router_rejection_audit_receipts": sum(
            1 for row in receipts
            if row["event_key"] == "ROUTERREJECT"
            and row["data"].get("review_checks",{}).get("input_stream")=="SOURCE_OWNER"
        ),
        "unattributed_router_rejections": not_attributed,
        "all_original_decisions_durable": False,
        "cloud_ack_verified": False,
        "source_owner_runtime_authenticated": False,
        "model_http_authorized": False,
        "orders": False,
        "paper_writer_active": False,
        "v2r4_unchanged": True,
    }


def stage_and_witness_first_minute(*, preflight: dict[str, Any],
                                   journal_directory: Path,
                                   capture_directory: Path,
                                   observed_at_utc: str,
                                   capture=None) -> dict[str, Any]:
    """Existing-owner V3 source seam, not a writer, scheduler or release.

    Stage the immutable intake FIRST, then witness the initial closed minute
    prospectively for bounded original scanner inputs. The caller must supply
    an explicit source capture callback; there is deliberately no default
    Kraken HTTP, model call, Paper activation, cloud POST or background work.

    A later live owner must authenticate itself and its actual Kraken source
    independently. In particular, a locally computed first-bar match is NOT
    a physical originalhost/Cloud technical-release proof.
    """
    from datetime import timedelta
    from paper_evaluator.v3_paper_minipc_closed_1m_capture_v1 import (
        assemble, timestamp,
    )

    if not callable(capture):
        raise ValueError("explicit source-owned capture callback required")
    if (not journal_directory.is_dir() or journal_directory.is_symlink()
            or not capture_directory.is_dir() or capture_directory.is_symlink()
            or journal_directory.resolve() == capture_directory.resolve()):
        raise ValueError("separate existing real V3 journal and capture roots required")
    at = timestamp(observed_at_utc)
    if at < timestamp(preflight["at_utc"]):
        raise ValueError("witness clock cannot predate canonical preflight")
    originals = {
        c["candidate_id"]: c
        for group in (preflight["selected_candidates"],
                      preflight["ingress"]["capacity_deferred_originals"])
        for c in group
    }
    enrollment = preflight.get("prospective_first_1m_capture_enrollment")
    if (not isinstance(enrollment, list) or len(enrollment) != len(originals)
            or len(enrollment) > 8
            or {x.get("candidate_id") for x in enrollment} != set(originals)):
        raise ValueError("canonical bounded source enrollment must be complete")

    # Durable immutable intake comes before a public-source side effect.
    staged = stage_receipts_explicitly(
        preflight=preflight, journal_directory=journal_directory)
    outcomes = []
    calls = 0
    for item in enrollment:
        cid = item["candidate_id"]
        original = originals[cid]
        if (item.get("pair") != original["pair"]
                or item.get("original_at_utc") != timestamp(
                    original["event_time_utc"]).isoformat()):
            raise ValueError("original candidate identity/clock disagrees with witness plan")
        first = timestamp(item["first_expected_closed_1m_start_utc"])
        close = first + timedelta(minutes=1)
        deadline = timestamp(item["latest_first_bar_live_witness_utc"])
        if deadline != close + timedelta(minutes=15):
            raise ValueError("first source witness deadline contract mismatch")
        row = {"candidate_id": cid, "pair": original["pair"],
               "first_expected_utc": first.isoformat(),
               "last_live_witness_utc": deadline.isoformat(),
               "first_bar_physically_authenticated": False,
               "paper_buy_authorized": False, "model_http_authorized": False}
        # A research-positive event needs an independently authenticated
        # live source-owner path, NOT its caller-supplied entry_origin label.
        if original.get("entry_origin") != "SCANNER":
            row["status"] = "SOURCE_OWNER_RUNTIME_AUTH_NOT_PROVEN_NO_CAPTURE"
        elif at < close:
            row["status"] = "WAIT_FOR_FIRST_CLOSED_MINUTE_NO_CAPTURE"
        elif at > deadline:
            row["status"] = "FIRST_WITNESS_WINDOW_EXPIRED_NO_BACKFILL"
        else:
            if (not isinstance(original.get("altname"), str)
                    or not original["altname"].isalnum()):
                raise ValueError("confirmed original Kraken altname required")
            def first_present() -> bool:
                checked = assemble(
                    snapshots=capture_directory, pair=original["pair"],
                    entry_at_utc=original["event_time_utc"],
                    observed_at_utc=observed_at_utc,
                    max_live_capture_lag_minutes=15)
                return bool(checked["closed_bars"]) and timestamp(
                    checked["closed_bars"][0]["start_at_utc"]) == first

            if first_present():
                row["status"] = "FIRST_MINUTE_ALREADY_ARCHIVED_NO_DUPLICATE_GET"
                row["prospective_first_bar_verified"] = True
            else:
                # Exactly one explicit public source action per selected original.
                # It may fail; the original receipts remain durable for retry.
                calls += 1
                result = capture(pair=original["pair"],
                                 altname=original["altname"],
                                 outdir=capture_directory)
                if (not isinstance(result, dict)
                        or result.get("status") != "CLOSED_KRAKEN_1M_SNAPSHOT_SAVED"):
                    raise ValueError("no original source capture ACK")
                p = Path(result["file"])
                if (p.parent.resolve() != capture_directory.resolve()
                        or p.stem != result.get("sha256")):
                    raise ValueError("source capture not content-addressed under owner root")
                # Existing assembler enforces original SHA, closed exchange
                # clock, <=15m witness lag and no conflicting price copies.
                witnessed = first_present()
                row["prospective_first_bar_verified"] = witnessed
                row["status"] = (
                    "FIRST_CLOSED_MINUTE_WITNESSED_RESEARCH_ONLY"
                    if witnessed else "FIRST_MINUTE_MISSING_NO_ECONOMIC_CLAIM")
        outcomes.append(row)
    return {
        "kind": "V3_SAME_OWNER_FIRST_MINUTE_ENROLLMENT_V1",
        "series_id": preflight["series_id"], "staged": staged,
        "enrollment": outcomes, "source_capture_calls": calls,
        "model_http_calls": 0, "model_http_authorized": False,
        "cloud_ack_verified": False, "paper_writer_active": False,
        "real_money_actions": False, "orders": False,
        "v2r4_changed": False, "new_schedules": 0,
        "source_owner_runtime_authenticated": False,
        "full_physical_paper_release_proof": False,
    }
