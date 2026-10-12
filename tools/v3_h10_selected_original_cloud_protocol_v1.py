#!/usr/bin/env python3
"""Pure H10 source-receipt write/readback contract; NO HTTP, DB, keys or runtime.

This helper belongs to the EXISTING GitHub H10 source owner; a future approved
owner may call it around its own direct Supabase INSERT/SELECT. No live
authorization, network transport, cloud ACK or Paper authority is provided here.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from tools.v3_h10_selected_original_receipt_v1 import (
    OriginalEvidenceBlocked, canonical, compare_replay, digest, insist, iso, utc,
)

RAW_TTL = dt.timedelta(hours=48)
CUSHION = dt.timedelta(minutes=5)


def prepare_source_only_insert(candidate: dict) -> dict:
    """Produce exactly the permitted INSERT column set from a qualified pure candidate."""
    compare_replay(candidate, candidate)  # recomputes both canonical fingerprints
    payload = candidate["payload"]
    start, evaluated = utc(payload["window_start_utc"]), utc(payload["evaluated_at_utc"])
    insist(start + dt.timedelta(minutes=30) <= evaluated
           <= start + RAW_TTL - CUSHION, "SOURCE_PROOF_TOO_OLD_FOR_INSERT")
    insist(payload["orders"] is False and payload["no_buy_authority"] is True
           and payload["source_owner_authenticated"] is False
           and payload["self_dealing_excluded"] is False,
           "SOURCE_ONLY_NONTRADEABLE_REQUIRED")
    original = canonical(payload)
    insist(len(original) <= 65536, "SOURCE_ORIGINAL_TOO_LARGE")
    return {
        "candidate_id": candidate["candidate_id"],
        "cohort_id": payload["cohort_id"],
        "cohort_role": payload["cohort_role"],
        "coin": payload["coin"],
        "window_start_utc": iso(start),
        "evaluated_at_utc": iso(evaluated),
        "content_sha256": candidate["content_sha256"],
        "original_payload_canonical": original.decode("utf-8"),
    }


def verify_persisted_readback(candidate: dict, row: dict) -> str:
    """Only compare untrusted readback to local plan; not a live cloud attestation."""
    insist(isinstance(row, dict), "MISSING_RECEIPT_READBACK")
    expected = prepare_source_only_insert(candidate)
    for key, value in expected.items():
        observed = row.get(key)
        if key in ("window_start_utc", "evaluated_at_utc"):
            insist(isinstance(observed, str) and iso(utc(observed)) == value,
                   "SOURCE_RECEIPT_READBACK_CONFLICT_" + key.upper())
        else:
            insist(observed == value,
                   "SOURCE_RECEIPT_READBACK_CONFLICT_" + key.upper())
    # Independent digest of the bytes we actually read, not the sender's claim.
    decoded = row["original_payload_canonical"]
    insist(isinstance(decoded, str)
           and digest(candidate["payload"]) == row["content_sha256"],
           "SOURCE_RECEIPT_READBACK_DIGEST_INVALID")
    received = utc(row.get("received_at_utc"))
    evaluated = utc(expected["evaluated_at_utc"])
    start = utc(expected["window_start_utc"])
    insist(received + dt.timedelta(seconds=5) >= evaluated,
           "DATABASE_RECEIVED_BEFORE_EVALUATION")
    insist(received <= start + RAW_TTL - CUSHION,
           "DATABASE_RECEIVED_AFTER_EARLIEST_RAW_EXPIRY")
    # Never output a 'real ACK' label from this pure offline comparator.
    return "SOURCE_ONLY_READBACK_MATCH_NOT_A_LIVE_CLOUD_ACK"


def classify_existing_without_writing(candidate: dict, existing_row: dict) -> str:
    """On a unique-key collision, only exact existing bytes may be a no-op."""
    verify_persisted_readback(candidate, existing_row)
    return "ALREADY_IDENTICAL_NO_UPDATE_NO_INSERT"
