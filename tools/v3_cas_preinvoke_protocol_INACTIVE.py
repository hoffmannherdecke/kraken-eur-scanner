"""INACTIVE V3 Paper CAS pre-invoke intent *review* protocol.

No Supabase connection, migrations, role issuance, order API, native host
actions or CAS execution. This source constructs deterministic unsigned audit
request digests and compares nonauthoritative readbacks for offline review.
Live CAS always raises; original credential/epoch/issuer/AUDIT ACK must be
separately audited and approved in the existing Cloud owner.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
from datetime import datetime, timezone, timedelta
import json
import re
import uuid
from typing import Any, Mapping

ORIGINAL_SERIES = "PAPER-V2R4-20261009T110135Z"
RPC = "public.rotate_v2r4_to_v3_experimental_paper"
HEX64 = re.compile(r"^[a-f0-9]{64}$")
EPOCH = re.compile(r"^V3CAS-AUDIT-[a-f0-9]{32}$")


class PreinvokeHold(RuntimeError):
    """Fail closed. Never treat review success as actual CAS permission."""


@dataclass(frozen=True)
class AuditIntent:
    epoch_id: str
    ordinal: int
    intent_id: str
    predecessor_series_id: str
    rpc: str
    request_sha256: str
    source_sha256: str
    fence_sha256: str
    digest: str


def build_unsigned_intent(
    *,
    epoch_id: str,
    ordinal: int,
    intent_id: str,
    predecessor_series_id: str,
    rpc: str,
    request_sha256: str,
    source_sha256: str,
    fence_sha256: str,
) -> AuditIntent:
    """Construct a canonical *unsigned* proposal, never persist or execute."""
    if not EPOCH.fullmatch(epoch_id):
        raise PreinvokeHold("BLOCK_BAD_AUDIT_EPOCH")
    if type(ordinal) is not int or ordinal < 1:
        raise PreinvokeHold("BLOCK_BAD_INTENT_ORDINAL")
    try:
        canonical_uuid = str(uuid.UUID(intent_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise PreinvokeHold("BLOCK_BAD_INTENT_ID") from exc
    if canonical_uuid != intent_id:
        raise PreinvokeHold("BLOCK_NONCANONICAL_INTENT_ID")
    if predecessor_series_id != ORIGINAL_SERIES or rpc != RPC:
        raise PreinvokeHold("BLOCK_FOREIGN_SERIES_OR_RPC")
    if not all(
        isinstance(v, str) and HEX64.fullmatch(v)
        for v in (request_sha256, source_sha256, fence_sha256)
    ):
        raise PreinvokeHold("BLOCK_BAD_SOURCE_DIGEST")
    body = {
        "audit_epoch": epoch_id,
        "ordinal": ordinal,
        "intent_id": intent_id,
        "predecessor_series_id": predecessor_series_id,
        "rpc": rpc,
        "request_sha256": request_sha256,
        "source_sha256": source_sha256,
        "fence_sha256": fence_sha256,
    }
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    ).hexdigest()
    return AuditIntent(
        epoch_id, ordinal, intent_id, predecessor_series_id, rpc,
        request_sha256, source_sha256, fence_sha256, digest
    )


def review_untrusted_audit_readback(intent: AuditIntent, row: Mapping[str, Any] | None) -> dict[str, Any]:
    """A *matching* row is evidence an attempt may exist, not a CAS green light.

    This deliberately never claims a durable commit, independent source issuer,
    complete epoch coverage, proof of actual RPC dispatch, or native recovery.
    """
    if not isinstance(row, Mapping):
        decision = "HOLD_NO_INDEPENDENT_DURABLE_ACK"
    elif any(
        (type(row.get(key)) is not int if key == "ordinal"
         else not isinstance(row.get(key), str))
        or row.get(key) != expected
        for key, expected in (
            ("epoch_id", intent.epoch_id),
            ("ordinal", intent.ordinal),
            ("intent_id", intent.intent_id),
            ("predecessor_series_id", intent.predecessor_series_id),
            ("requested_rpc", intent.rpc),
            ("request_sha256", intent.request_sha256),
            ("source_sha256", intent.source_sha256),
            ("fence_sha256", intent.fence_sha256),
        )
    ):
        decision = "HOLD_AUDIT_ACK_MISMATCH_OR_REPLAY"
    else:
        # A pre-invocation audit intent already exists; even if RPC dispatch
        # did not happen, old writer auto-rearm cannot be inferred as safe.
        decision = "HOLD_PERSISTED_INTENT_OR_UNKNOWN_DISPATCH"
    return {
        "kind": "V3_CAS_PREINVOKE_INTENT_LOCAL_REVIEW_V1",
        "disposition": decision,
        "caller_supplied_row_authenticated": False,
        "ack_durably_committed_independently_verified": False,
        "preinvoke_audit_epoch_complete": False,
        "historical_cas_never_invoked_proven": False,
        "cas_dispatch_authorized": False,
        "native_restore_authorized": False,
        "old_writer_auto_rearm_allowed": False,
        "v3_paper_release_authorized": False,
    }


def invoke_v3_paper_cas(*_args: Any, **_kwargs: Any) -> None:
    """Hard lock even if imported by a future caller."""
    raise PreinvokeHold("V3_CAS_PREINVOKE_PROTOCOL_SOURCE_UNCONDITIONALLY_LOCKED")

# SOURCE ONLY: an external HMAC packet cannot itself prove off-DB durability,
# key separation, complete CAS-attempt coverage or permission to release.
WITNESS_KIND = "V3_CAS_OFFDB_WITNESS_PACKET_V1"
WITNESS_DOMAIN = b"kraken-eur-scanner/V3-CAS/witness-review/v1\x00"
WITNESS_KEYS = ("kind", "witness_id", "epoch_id", "last_ordinal",
                "ordered_intent_sha256", "external_commit_sha256", "signed_at_utc")
MAX_WITNESSED_INTENTS = 64


def review_offdb_witness_hmac_packet(
    intent: AuditIntent, receipt: Mapping[str, Any] | None, *,
    expected_witness_id: str, verification_key: bytes, reviewed_at_utc: str,
) -> dict[str, Any]:
    """Pure bounded byte-authentication test, NEVER a CAS or restore gate.

    No key is loaded or issued here; the caller's claimed trusted key cannot
    be independently authenticated by this function. No external fetch/write.
    """
    result = {
        "kind": "V3_CAS_WITNESS_PACKET_LOCAL_REVIEW_V1",
        "disposition": "HOLD_WITNESS_UNVERIFIED",
        "mac_matches_supplied_key": False,
        "real_witness_issuer_authenticated": False,
        "independent_offdb_durable_storage_proven": False,
        "exclusive_cas_attempt_coverage_proven": False,
        "historical_cas_never_invoked_proven": False,
        "cas_dispatch_authorized": False,
        "native_restore_authorized": False,
        "old_writer_auto_rearm_allowed": False,
        "v3_paper_release_authorized": False,
    }
    if receipt is None:
        result["disposition"] = "HOLD_WITNESS_MISSING"
        return result
    try:
        if (not isinstance(intent, AuditIntent)
                or not isinstance(receipt, Mapping)
                or type(verification_key) is not bytes
                or not 32 <= len(verification_key) <= 128
                or not isinstance(expected_witness_id, str)
                or re.fullmatch(r"[A-Za-z0-9_.:-]{5,120}", expected_witness_id) is None
                or set(receipt) != set(WITNESS_KEYS) | {"hmac_sha256"}
                or receipt["kind"] != WITNESS_KIND
                or receipt["witness_id"] != expected_witness_id
                or receipt["epoch_id"] != intent.epoch_id):
            raise ValueError("bad witness scope")
        ordinal = receipt["last_ordinal"]
        digests = receipt["ordered_intent_sha256"]
        if (type(ordinal) is not int or not 1 <= ordinal <= MAX_WITNESSED_INTENTS
                or type(digests) is not list or len(digests) != ordinal
                or intent.ordinal < 1 or intent.ordinal > ordinal
                or not all(isinstance(d, str) and HEX64.fullmatch(d) for d in digests)
                or len(set(digests)) != len(digests)
                or digests[intent.ordinal - 1] != intent.digest
                or not isinstance(receipt["external_commit_sha256"], str)
                or not HEX64.fullmatch(receipt["external_commit_sha256"])
                or not isinstance(receipt["hmac_sha256"], str)
                or not HEX64.fullmatch(receipt["hmac_sha256"])):
            raise ValueError("bad sequence/claim")
        def parse_utc(value: Any) -> datetime:
            if not isinstance(value, str) or re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value
            ) is None:
                raise ValueError("noncanonical UTC")
            parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
            return parsed.replace(tzinfo=timezone.utc)
        signed_at = parse_utc(receipt["signed_at_utc"])
        now = parse_utc(reviewed_at_utc)
        if not timedelta(0) <= now - signed_at <= timedelta(minutes=5):
            raise ValueError("stale/future witness")
        payload = {key: receipt[key] for key in WITNESS_KEYS}
        raw = WITNESS_DOMAIN + json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        if len(raw) > 7000:
            raise ValueError("oversized packet")
        expected = hmac.new(verification_key, raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, receipt["hmac_sha256"]):
            raise ValueError("wrong HMAC")
    except (ValueError, TypeError, KeyError, IndexError, OverflowError, AttributeError):
        result["disposition"] = "HOLD_WITNESS_BINDING_OR_MAC_INVALID"
        return result
    result["mac_matches_supplied_key"] = True
    result["disposition"] = "REVIEW_ONLY_MAC_MATCH_CUSTODY_UNPROVEN"
    return result

