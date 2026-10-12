#!/usr/bin/env python3
"""Pure H10 selected-window original-evidence candidate. NOT a sender or archive.

This module has no network, file/database writes, signing or trading operations.
A future trusted H10 owner must independently query the full source population,
verify source provenance and persist/ACK the immutable candidate BEFORE 48h expiry.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation

UTC = dt.timezone.utc
WINDOW = dt.timedelta(minutes=30)
LOOKBACK = dt.timedelta(minutes=45)
RAW_TTL = dt.timedelta(hours=48)
MAX_EVENTS = 128
MAX_PAYLOAD_BYTES = 65536
MIN_WALLETS = 3
POSITIVE_RAW_NOTIONAL = Decimal("10000")
EVENT_ID_RE = re.compile(r"^[0-9a-f]{64}$")
ADDRESS_RE = re.compile(r"^0x[0-9a-f]{40}$")
COIN_RE = re.compile(r"^[A-Za-z0-9:_-]{2,40}$")
SOURCE_DIRECTIONS = {
    "Open Long": ("B", 1),
    "Close Short": ("B", 1),
    "Open Short": ("A", -1),
    "Close Long": ("A", -1),
}


class OriginalEvidenceBlocked(ValueError):
    """No trustworthy source receipt can be produced from supplied facts."""


def insist(ok: bool, reason: str) -> None:
    if not ok:
        raise OriginalEvidenceBlocked(reason)


def utc(value: str) -> dt.datetime:
    insist(isinstance(value, str), "MISSING_OR_INVALID_UTC")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OriginalEvidenceBlocked("MISSING_OR_INVALID_UTC") from exc
    insist(parsed.tzinfo is not None and parsed.utcoffset() == dt.timedelta(0),
           "NON_UTC_SOURCE_CLOCK")
    return parsed.astimezone(UTC)


def iso(value: dt.datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def positive_decimal(value: object, name: str) -> Decimal:
    insist(isinstance(value, (str, int, float, Decimal)) and not isinstance(value, bool),
           "MISSING_" + name)
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise OriginalEvidenceBlocked("INVALID_" + name) from exc
    insist(result.is_finite() and result > 0, "INVALID_" + name)
    return result


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: dict) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def build_selected_window_receipt(*, cohort: dict, batch_rows: list[dict],
                                  fill_rows: list[dict], coin: str, role: str,
                                  window_start_utc: str, evaluated_at_utc: str) -> dict:
    """Create a bounded OFFLINE research plan from complete authoritative SELECT rows.

    The caller is responsible for a complete point-in-time database read, no later
    than the source 48h TTL. This pure builder cannot prove that completeness,
    source endpoint authenticity, wallet beneficial ownership or cloud ACK.
    """
    insist(isinstance(cohort, dict) and cohort.get("kind") == "V3_H10_FROZEN_TRADER_COHORT_V1",
           "FROZEN_COHORT_REQUIRED")
    cohort_id = cohort.get("cohort_id")
    insist(cohort_id == "V3-H10-COHORT-001", "FROZEN_COHORT_ID_MISMATCH")
    insist(role in ("PRIMARY", "CONTROL"), "INVALID_COHORT_ROLE")
    insist(isinstance(coin, str) and COIN_RE.fullmatch(coin) is not None,
           "INVALID_SOURCE_COIN")
    start = utc(window_start_utc)
    end = start + WINDOW
    asof = utc(evaluated_at_utc)
    insist(start.minute in (0, 30) and start.second == 0 and start.microsecond == 0,
           "UNALIGNED_30M_WINDOW")
    insist(asof >= end, "OPEN_WINDOW_LOOKAHEAD")
    insist(asof <= end + RAW_TTL - dt.timedelta(minutes=5),
           "ORIGINAL_FILL_TTL_EXPIRED")
    insist(isinstance(batch_rows, list) and isinstance(fill_rows, list),
           "COMPLETE_SOURCE_ROWS_REQUIRED")
    insist(len(fill_rows) <= MAX_EVENTS, "EVENT_CAP_NO_SILENT_TRUNCATION")
    insist(isinstance(cohort.get("traders"), list), "FROZEN_COHORT_ROWS_MISSING")

    wallet_roles = {}
    for row in cohort["traders"]:
        addr = row.get("address")
        insist(isinstance(addr, str) and ADDRESS_RE.fullmatch(addr) is not None
               and addr not in wallet_roles, "INVALID_FROZEN_WALLET_ROSTER")
        insist(row.get("role") in ("PRIMARY", "CONTROL"), "INVALID_FROZEN_WALLET_ROLE")
        wallet_roles[addr] = row["role"]
    insist(len(wallet_roles) == 26
           and sum(x == "PRIMARY" for x in wallet_roles.values()) == 20
           and sum(x == "CONTROL" for x in wallet_roles.values()) == 6,
           "FROZEN_COHORT_SIZE_CHANGED")

    batches = {}
    successful_intervals = []
    for batch in batch_rows:
        ident = batch.get("batch_id")
        insist(isinstance(ident, str) and ident and ident not in batches,
               "MISSING_OR_DUPLICATE_BATCH")
        insist(batch.get("cohort_id") == cohort_id
               and batch.get("capture_path") == "GITHUB_BOOTSTRAP_30M",
               "UNTRUSTED_BATCH_OWNER")
        observed, created = utc(batch.get("observed_at")), utc(batch.get("created_at"))
        insist(observed <= created <= asof, "BATCH_NOT_AVAILABLE_AT_EVALUATION")
        batches[ident] = (batch, observed, created)
        # The existing 17/47 cron 45m reads overlap: two healthy reads can
        # cover a complete 30m source window without either doing so alone.
        if (batch.get("wallet_count") == 26
                and batch.get("success_count") == 26 and batch.get("error_count") == 0):
            left, right = max(start, observed - LOOKBACK), min(end, observed)
            if left < right:
                successful_intervals.append((left, right, ident))
    cursor = start
    proof_batches = []
    for left, right, ident in sorted(successful_intervals):
        if left > cursor:
            break
        if right > cursor:
            cursor = right
            proof_batches.append(ident)
    insist(cursor >= end, "NO_FULL_WINDOW_SUCCESSFUL_CAPTURE_COVERAGE")

    originals = {}
    exposure = defaultdict(lambda: Decimal("0"))
    for row in fill_rows:
        insist(isinstance(row, dict), "INVALID_FILL_ROW")
        eid, address = row.get("event_id"), row.get("address")
        insist(isinstance(eid, str) and EVENT_ID_RE.fullmatch(eid) is not None,
               "INVALID_ORIGINAL_EVENT_ID")
        insist(isinstance(address, str) and wallet_roles.get(address) == role,
               "UNREGISTERED_OR_WRONG_ROLE_WALLET")
        insist(row.get("cohort_id") == cohort_id and row.get("cohort_role") == role
               and row.get("coin") == coin, "FOREIGN_WINDOW_OR_SOURCE_ROW")
        fill_at, first_seen = utc(row.get("fill_time")), utc(row.get("first_seen_at"))
        insist(start <= fill_at < end, "FILL_OUTSIDE_SOURCE_WINDOW")
        insist(fill_at <= first_seen <= asof, "SOURCE_LOOKAHEAD_OR_CLOCK_REVERSAL")
        insist(first_seen <= fill_at + RAW_TTL, "LATE_FIRST_SOURCE_CAPTURE")
        batch_id = row.get("first_seen_batch_id")
        insist(batch_id in batches, "ORIGINAL_BATCH_JOIN_MISSING")
        batch, observed, created = batches[batch_id]
        insist(observed <= created <= first_seen, "ORIGINAL_BATCH_TIMESTAMP_REVERSED")
        direction = row.get("direction")
        insist(direction in SOURCE_DIRECTIONS, "UNKNOWN_SOURCE_DIRECTION")
        side, sign = SOURCE_DIRECTIONS[direction]
        insist(row.get("side") == side, "SOURCE_SIDE_DIRECTION_CONFLICT")
        tx_hash = row.get("tx_hash")
        insist(isinstance(tx_hash, str) and re.fullmatch(r"0x[0-9a-fA-F]{64}", tx_hash),
               "SOURCE_TX_HASH_REQUIRED")
        px, sz = positive_decimal(row.get("px"), "PRICE"), positive_decimal(row.get("sz"), "SIZE")
        notional = px * sz * sign
        original = {
            "event_id": eid, "wallet_address": address,
            "source_tx_hash": tx_hash.lower(), "source_oid": row.get("oid"),
            "source_tid": row.get("tid"), "direction": direction, "side": side,
            "source_fill_at_utc": iso(fill_at), "database_first_seen_at_utc": iso(first_seen),
            "original_batch_id": batch_id,
            "batch_observed_at_utc": iso(observed), "batch_created_at_utc": iso(created),
            "price_quote": format(px, "f"), "size_base": format(sz, "f"),
            "signed_quote_notional": format(notional, "f")
        }
        if eid in originals:
            insist(originals[eid] == original, "ORIGINAL_EVENT_ID_COLLISION")
            raise OriginalEvidenceBlocked("DUPLICATE_EVENT_INPUT_NOT_DEDUPED")
        originals[eid] = original
        exposure[address] += notional

    wallets = sorted(exposure)
    if len(wallets) < MIN_WALLETS:
        return {
            "status": "NOT_SELECTED_RESEARCH_ONLY", "reason": "FEWER_THAN_THREE_DISTINCT_WALLETS",
            "cohort_id": cohort_id, "role": role, "coin": coin,
            "window_start_utc": iso(start), "distinct_wallets": len(wallets),
            "orders": False, "no_buy_authority": True
        }
    positive = sum(v > 0 for v in exposure.values())
    negative = sum(v < 0 for v in exposure.values())
    total_quote = sum(exposure.values(), Decimal("0"))
    content = {
        "kind": "V3_H10_SELECTED_ORIGINAL_SOURCE_RECEIPT_CANDIDATE_V1",
        "cohort_id": cohort_id, "cohort_role": role, "coin": coin,
        "window_start_utc": iso(start), "window_end_utc": iso(end),
        "evaluated_at_utc": iso(asof),
        "first_qualifiable_known_at_utc": iso(max([asof, end])),
        "wallet_address_count": len(wallets),
        "positive_wallet_count": positive, "negative_wallet_count": negative,
        "net_quote_change": format(total_quote, "f"),
        "matches_pr230_descriptive_positive_raw_filter": (
            positive >= 3 and negative == 0 and total_quote >= POSITIVE_RAW_NOTIONAL),
        "source_event_count": len(originals),
        "original_events": [originals[k] for k in sorted(originals)],
        "complete_window_capture_batch_ids": sorted(proof_batches),
        "point_in_time_scope": "DB_ORIGINALS_AT_EXPLICIT_ASOF_NOT_CLOUD_ACK",
        "beneficial_owner_independence_verified": False,
        "self_dealing_excluded": False,
        "source_owner_authenticated": False,
        "kraken_eur_tradability_verified": False,
        "orders": False, "no_buy_authority": True,
    }
    blob = canonical(content)
    insist(len(blob) <= MAX_PAYLOAD_BYTES, "ORIGINAL_PROOF_PAYLOAD_TOO_LARGE")
    identity = {"cohort_id": cohort_id, "role": role, "coin": coin,
                "window_start_utc": iso(start)}
    return {
        "status": "SELECTED_INACTIVE_OFFLINE_NOT_PERSISTED",
        "candidate_id": digest(identity),
        "content_sha256": hashlib.sha256(blob).hexdigest(),
        "payload_bytes": len(blob),
        "payload": content,
        "cloud_original_receipt_ack": None,
        "signature": None,
        "live_source_verified": False,
    }


def compare_replay(existing: dict, candidate: dict) -> str:
    """Offline duplicate check. Never overwrite original receipt on collision."""
    insist(existing.get("candidate_id") == candidate.get("candidate_id"),
           "REPLAY_IDENTITY_MISMATCH")
    insist(existing.get("content_sha256") == candidate.get("content_sha256"),
           "REPLAY_CONTENT_CONFLICT_KEEP_ORIGINAL")
    return "IDENTICAL_REPLAY_NO_WRITE"
