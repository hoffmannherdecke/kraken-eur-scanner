"""INACTIVE local off-database witness *candidate* for V3 CAS audit intents.

This is a bounded on-disk append/readback primitive, not an audit authority.
It is not wired to Windows tasks, CAS, Supabase, GitHub, Sigstore or a scheduler.
A passing local file readback NEVER proves independent custody, completeness
of attempted CAS calls, approved issuer identity, or V3 Paper release.

Tests use disposable directories. Deploying on the original Mini-PC requires
the existing Issue #99 owner's separate exact NTFS/credentials/backup/host
approval. Do not put private receipts or machine data in the public repo.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid
from typing import Any

from v3_cas_preinvoke_protocol_INACTIVE import (
    AuditIntent, EPOCH, HEX64, PreinvokeHold, build_unsigned_intent,
)

KIND = "V3_CAS_LOCAL_OFFDB_WITNESS_CANDIDATE_V1"
DOMAIN = b"kraken-eur-scanner/V3-CAS/local-witness/v1\x00"
MAX_FILES = 64
MAX_ENTRY_BYTES = 2048
NAMES = re.compile(r"^[0-9]{6}\.json$")
ENTRY_FIELDS = frozenset((
    "kind", "epoch_id", "ordinal", "intent_id", "intent_sha256",
    "previous_entry_sha256", "entry_sha256",
))
ZERO_DIGEST = "0" * 64


class LocalWitnessHold(PreinvokeHold):
    """Never repair, truncate, auto-retry CAS or silently skip a damaged file."""


def _canonical(data: dict[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _entry_hash(fields: dict[str, Any]) -> str:
    return hashlib.sha256(DOMAIN + _canonical(fields)).hexdigest()


def _reject_reparse(path: Path) -> None:
    """Best-effort source check; Windows owner ACL and reparse races still need host proof."""
    if not path.is_absolute() or ".." in path.parts:
        raise LocalWitnessHold("HOLD_LOCAL_WITNESS_UNSAFE_PATH")
    for candidate in (path, *path.parents):
        try:
            info = candidate.lstat()
        except OSError as exc:
            raise LocalWitnessHold("HOLD_LOCAL_WITNESS_UNAVAILABLE") from exc
        if (stat.S_ISLNK(info.st_mode)
                or bool(getattr(info, "st_file_attributes", 0)
                        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))):
            raise LocalWitnessHold("HOLD_LOCAL_WITNESS_REPARSE_DENIED")
    if not path.is_dir():
        raise LocalWitnessHold("HOLD_LOCAL_WITNESS_NOT_DIRECTORY")


def _read_records(root: Path) -> list[dict[str, Any]]:
    _reject_reparse(root)
    try:
        names = sorted(os.listdir(root))
    except OSError as exc:
        raise LocalWitnessHold("HOLD_LOCAL_WITNESS_LIST_DENIED") from exc
    if len(names) > MAX_FILES or any(not NAMES.fullmatch(n) for n in names):
        raise LocalWitnessHold("HOLD_LOCAL_WITNESS_UNKNOWN_OR_UNBOUNDED_ENTRY")
    records: list[dict[str, Any]] = []
    previous = ZERO_DIGEST
    seen_ids: set[str] = set()
    seen_digests: set[str] = set()
    epoch: str | None = None
    for ordinal, name in enumerate(names, start=1):
        if name != f"{ordinal:06d}.json":
            raise LocalWitnessHold("HOLD_LOCAL_WITNESS_GAPPED_ORDINAL")
        path = root / name
        try:
            file_stat = path.lstat()
            if (not stat.S_ISREG(file_stat.st_mode)
                    or getattr(file_stat, "st_nlink", 1) != 1
                    or bool(getattr(file_stat, "st_file_attributes", 0)
                            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))):
                raise LocalWitnessHold("HOLD_LOCAL_WITNESS_LINK_OR_FILETYPE")
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            with os.fdopen(os.open(path, flags), "rb") as stream:
                raw = stream.read(MAX_ENTRY_BYTES + 1)
            if len(raw) > MAX_ENTRY_BYTES:
                raise LocalWitnessHold("HOLD_LOCAL_WITNESS_OVERSIZED_ENTRY")
            data = json.loads(raw.decode("ascii"))
        except (OSError, ValueError, UnicodeError, TypeError) as exc:
            raise LocalWitnessHold("HOLD_LOCAL_WITNESS_MALFORMED_ENTRY") from exc
        if (type(data) is not dict or set(data) != ENTRY_FIELDS
                or data["kind"] != KIND
                or type(data["ordinal"]) is not int or data["ordinal"] != ordinal
                or not isinstance(data["epoch_id"], str)
                or not EPOCH.fullmatch(data["epoch_id"])
                or not isinstance(data["intent_id"], str)
                or not isinstance(data["intent_sha256"], str)
                or not HEX64.fullmatch(data["intent_sha256"])
                or not isinstance(data["previous_entry_sha256"], str)
                or data["previous_entry_sha256"] != previous
                or not isinstance(data["entry_sha256"], str)
                or not HEX64.fullmatch(data["entry_sha256"])):
            raise LocalWitnessHold("HOLD_LOCAL_WITNESS_BAD_ENTRY_SCOPE")
        try:
            if str(uuid.UUID(data["intent_id"])) != data["intent_id"]:
                raise ValueError("noncanonical")
        except (TypeError, ValueError, AttributeError) as exc:
            raise LocalWitnessHold("HOLD_LOCAL_WITNESS_BAD_ID") from exc
        if epoch is None:
            epoch = data["epoch_id"]
        if (data["epoch_id"] != epoch or data["intent_id"] in seen_ids
                or data["intent_sha256"] in seen_digests):
            raise LocalWitnessHold("HOLD_LOCAL_WITNESS_EPOCH_OR_REPLAY")
        unsigned = {key: val for key, val in data.items()
                    if key != "entry_sha256"}
        if (_canonical(data) != raw
                or data["entry_sha256"] != _entry_hash(unsigned)):
            raise LocalWitnessHold("HOLD_LOCAL_WITNESS_TAMPERED_OR_NONCANONICAL")
        records.append(data)
        previous = data["entry_sha256"]
        seen_ids.add(data["intent_id"])
        seen_digests.add(data["intent_sha256"])
    return records


def _no_authority(*, local_count: int, last_digest: str) -> dict[str, Any]:
    return {
        "kind": "V3_CAS_LOCAL_WITNESS_SOURCE_REVIEW_V1",
        "disposition": "REVIEW_ONLY_LOCAL_FILE_CHAIN_NOT_INDEPENDENT_CUSTODY",
        "local_records_checked": local_count,
        "last_entry_sha256": last_digest,
        "local_chain_consistent": True,
        "originalhost_identity_authenticated": False,
        "independent_offdb_durable_storage_proven": False,
        "exclusive_cas_attempt_coverage_proven": False,
        "historical_cas_never_invoked_proven": False,
        "cloud_cas_authorized": False,
        "old_writer_auto_rearm_allowed": False,
        "native_restore_authorized": False,
        "v3_paper_release_authorized": False,
    }


def review_local_witness_candidate(root: Path) -> dict[str, Any]:
    """Read only, no writes; zero files never means zero historical attempts."""
    records = _read_records(Path(root))
    last = records[-1]["entry_sha256"] if records else ZERO_DIGEST
    return _no_authority(local_count=len(records), last_digest=last)


def append_local_witness_candidate(root: Path, intent: AuditIntent) -> dict[str, Any]:
    """Disk implementation for disposable isolated tests; NOT wired to a CAS caller.

    Requires an existing dedicated directory. O_EXCL disallows replacement and
    concurrent same-ordinal creation. fsync flushes file content; actual NTFS
    ACL, directory metadata power-loss durability, backup, trusted signer and
    external anchoring require separate original-host evidence/approval.
    Any crash/partial file permanently holds this epoch pending independent
    reconciliation. The function NEVER invokes or grants CAS.
    """
    if not isinstance(intent, AuditIntent):
        raise LocalWitnessHold("HOLD_LOCAL_WITNESS_UNTRUSTED_INTENT")
    try:
        rebuilt = build_unsigned_intent(
            epoch_id=intent.epoch_id, ordinal=intent.ordinal,
            intent_id=intent.intent_id,
            predecessor_series_id=intent.predecessor_series_id,
            rpc=intent.rpc, request_sha256=intent.request_sha256,
            source_sha256=intent.source_sha256,
            fence_sha256=intent.fence_sha256,
        )
    except PreinvokeHold as exc:
        raise LocalWitnessHold("HOLD_LOCAL_WITNESS_BAD_INTENT") from exc
    if rebuilt.digest != intent.digest:
        raise LocalWitnessHold("HOLD_LOCAL_WITNESS_FORGED_INTENT_DIGEST")
    root = Path(root)
    records = _read_records(root)
    ordinal = len(records) + 1
    if (ordinal > MAX_FILES or intent.ordinal != ordinal
            or any(item["intent_id"] == intent.intent_id
                   or item["intent_sha256"] == intent.digest for item in records)
            or (records and records[-1]["epoch_id"] != intent.epoch_id)):
        raise LocalWitnessHold("HOLD_LOCAL_WITNESS_REPLAY_OR_WRONG_ORDER")
    fields = {
        "kind": KIND,
        "epoch_id": intent.epoch_id,
        "ordinal": ordinal,
        "intent_id": intent.intent_id,
        "intent_sha256": intent.digest,
        "previous_entry_sha256": records[-1]["entry_sha256"] if records
                                 else ZERO_DIGEST,
    }
    payload = _canonical({**fields, "entry_sha256": _entry_hash(fields)})
    if len(payload) > MAX_ENTRY_BYTES:
        raise LocalWitnessHold("HOLD_LOCAL_WITNESS_RECORD_TOO_LARGE")
    file_path = root / f"{ordinal:06d}.json"
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        fd = os.open(file_path, flags, 0o600)
    except OSError as exc:
        raise LocalWitnessHold("HOLD_LOCAL_WITNESS_EXCLUSIVE_CREATE_FAILED") from exc
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        # Deliberately retain an incomplete entry: never silently unlink it.
        raise LocalWitnessHold("HOLD_LOCAL_WITNESS_INCOMPLETE_WRITE") from exc
    checked = _read_records(root)
    if len(checked) != ordinal or checked[-1]["intent_sha256"] != intent.digest:
        raise LocalWitnessHold("HOLD_LOCAL_WITNESS_POSTWRITE_READBACK_MISMATCH")
    return _no_authority(local_count=ordinal,
                         last_digest=checked[-1]["entry_sha256"])
