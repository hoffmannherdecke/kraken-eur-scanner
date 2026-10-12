"""Fail-closed H5/H10/H11 trusted owner proof for future V3 Paper sources.

A SHA-256 of an event, a boolean 'trusted caller' flag, or a registry name
alone are NOT authentication. A positive source event must have a real HMAC
signature from the holder of a per-source/per-owner high-entropy runtime key.

No key files, environment-variable reads, network, scheduler, Cloud writes,
model calls, orders or Paper activation. Keys must be provisioned by a
separate approved physical owner security boundary; repository contains NONE.
HMAC authenticates the packet holder, NOT truth of reported market claims.
"""
from __future__ import annotations

from datetime import timedelta
from copy import deepcopy
import hashlib
import hmac
import json
import re
from typing import Any

from paper_evaluator.v3_paper_positive_source_entry_v1 import STREAMS,utc,assess_positive_source,ELIGIBLE

KIND="V3_POSITIVE_OWNER_HMAC_BOUNDARY_V1"
DOMAIN=b"kraken-eur-scanner/V3-PAPER/positive-owner/v1\x00"
HEX=re.compile(r"^[0-9a-f]{64}$")
ID=re.compile(r"^[A-Za-z0-9_.:-]{5,150}$")
PAIR=re.compile(r"^[A-Z0-9]{2,20}/EUR$")
MAX_PACKET_BYTES=24_000
MAX_SIGNED_AGE_SECONDS=900


def validate_keyring(keys:dict[str,dict[str,bytes]]|None)->dict[str,dict[str,bytes]]:
    """Validate no plaintext string secrets or cross-source identity mapping."""
    if keys is None:
        return {source:{} for source in STREAMS}
    if not isinstance(keys,dict) or set(keys)!=set(STREAMS):
        raise ValueError("exact owner source keyring required")
    result={}
    for source, owners in keys.items():
        if not isinstance(owners,dict) or len(owners)>20:
            raise ValueError("invalid source owner key capacity")
        safe={}
        for owner,key in owners.items():
            if (not isinstance(owner,str) or not ID.fullmatch(owner)
                    or not isinstance(key,bytes) or len(key)<32 or len(key)>128):
                raise ValueError("owner key must be preprovisioned high-entropy bytes")
            safe[owner]=key
        result[source]=safe
    return result


def canonical_owner_message(packet:dict[str,Any])->bytes:
    """The signed bytes bind the entire original event, source, pair and clock."""
    if not isinstance(packet,dict):
        raise ValueError("source packet must be an object")
    proof=packet.get("owner_integrity")
    snap=packet.get("snapshot")
    if not isinstance(proof,dict) or not isinstance(snap,dict):
        raise ValueError("source packet proof/snapshot missing")
    source=packet.get("source_name")
    pair=packet.get("pair")
    altname=packet.get("altname")
    owner=proof.get("authenticated_owner_id")
    signed=proof.get("signed_at_utc")
    if (source not in STREAMS
            or not isinstance(pair,str) or not PAIR.fullmatch(pair)
            or not isinstance(altname,str) or not re.fullmatch(r"[A-Za-z0-9]{3,30}",altname)
            or not isinstance(owner,str) or not ID.fullmatch(owner)
            or snap.get("source_owner")!=owner or snap.get("pair")!=pair
            or not isinstance(signed,str)):
        raise ValueError("original owner/pair source attribution incomplete")
    body={"kind":KIND,"source_name":source,"pair":pair,
          "altname":altname,"source_owner":owner,
          "signed_at_utc":signed,
          "snapshot":snap,
          "market_move":packet.get("market_move")}
    try:
        raw=json.dumps(body,sort_keys=True,separators=(",",":"),
                       ensure_ascii=False,allow_nan=False).encode("utf-8")
    except (TypeError,ValueError,OverflowError) as exc:
        raise ValueError("noncanonical source packet") from exc
    if len(raw)>MAX_PACKET_BYTES:
        raise ValueError("source owner packet too large")
    return DOMAIN+raw


def verify_owner_packet(*,packet:dict[str,Any],
                        trusted_keys:dict[str,dict[str,bytes]],
                        decision_at_utc:str)->str:
    """Return stable denial code or VERIFIED_OWNER_HMAC_PACKET_ONLY.

    Does NOT replace independent H5/H10/H11 signal/economic checks; caller
    must still evaluate news primary source, wallet fills, H11 delta etc.
    """
    try:
        proof=packet["owner_integrity"]
        if not isinstance(proof,dict) or proof.get("proof_version")!=KIND:
            return "OWNER_HMAC_REQUIRED_NOT_BOOLEAN_ATTESTATION"
        owner=proof.get("authenticated_owner_id")
        source=packet.get("source_name")
        if (source not in STREAMS or not isinstance(owner,str)
                or owner not in trusted_keys.get(source,{})):
            return "NO_TRUSTED_RUNTIME_SOURCE_OWNER_KEY"
        digest=proof.get("canonical_payload_sha256")
        snap=packet.get("snapshot")
        if not isinstance(snap,dict) or not isinstance(digest,str) or not HEX.fullmatch(digest):
            return "SOURCE_PAYLOAD_SHA256_INVALID"
        expected=hashlib.sha256(json.dumps(
            snap,sort_keys=True,separators=(",",":"),ensure_ascii=False,
            allow_nan=False).encode("utf-8")).hexdigest()
        if not hmac.compare_digest(digest,expected):
            return "SOURCE_PAYLOAD_SHA256_MISMATCH"
        signed=utc(proof["signed_at_utc"])
        known=utc(snap["known_at_utc"])
        observed=utc(snap["observed_at_utc"])
        decision=utc(decision_at_utc)
        if (not observed<=known<=signed<=decision
                or decision-signed>timedelta(seconds=MAX_SIGNED_AGE_SECONDS)):
            return "OWNER_SIGNATURE_EXPIRED_OR_CAUSALLY_INVALID"
        signature=proof.get("owner_hmac_sha256")
        if not isinstance(signature,str) or not HEX.fullmatch(signature):
            return "OWNER_HMAC_SIGNATURE_MISSING"
        computed=hmac.new(
            trusted_keys[source][owner],
            canonical_owner_message(packet),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(computed,signature):
            return "OWNER_HMAC_CONTENT_OR_IDENTITY_MISMATCH"
        return "VERIFIED_OWNER_HMAC_PACKET_ONLY"
    except (ValueError,TypeError,KeyError,OverflowError,AttributeError):
        return "INVALID_OWNER_PROVENANCE_ENVELOPE"


def sign_qualified_owner_event_explicitly(*,source_name:str,pair:str,
        kraken_altname:str,snapshot:dict[str,Any],
        signed_at_utc:str,owner_id:str,owner_hmac_key:bytes,
        market_move:dict[str,Any]|None=None)->dict[str,Any]:
    """Pure source-OWNER outbound packet, requires caller-held preprovisioned key.

    Never derive a positive H5/H10/H11 event from raw context/books/calendar.
    Never create, load, store or return owner secret bytes; HMAC generation is
    not physical source authentication or proof the event occurred in reality.
    """
    if (source_name not in STREAMS
            or not isinstance(owner_id,str) or not ID.fullmatch(owner_id)
            or type(owner_hmac_key) is not bytes
            or not 32<=len(owner_hmac_key)<=128
            or not isinstance(snapshot,dict)
            or snapshot.get("source_owner")!=owner_id):
        raise ValueError("preprovisioned exact qualified source owner is required")
    # Honest source labels are checked before any MAC. This prevents accidentally
    # turning existing H10 context, H11 top-five raw books, or H5 macro calendar
    # into standalone BUY-review signals by merely adding a signature.
    qualified=assess_positive_source(
        pair=pair,source_name=source_name,snapshot=snapshot,
        decision_at_utc=signed_at_utc,market_move=market_move)
    if qualified["status"]!=ELIGIBLE:
        raise ValueError("raw source context is not a verified positive catalyst")
    original=deepcopy(snapshot)
    move=deepcopy(market_move)
    digest=hashlib.sha256(json.dumps(
        original,sort_keys=True,separators=(",",":"),ensure_ascii=False,
        allow_nan=False).encode("utf-8")).hexdigest()
    packet={
        "source_name":source_name,"pair":pair,
        "altname":kraken_altname,"snapshot":original,
        "market_move":move,
        "owner_integrity":{
            "proof_version":KIND,
            "authenticated_owner_id":owner_id,
            "authentication_checked_by_trusted_caller":True,
            "canonical_payload_sha256":digest,
            "signed_at_utc":signed_at_utc,
        },
    }
    mac=hmac.new(owner_hmac_key,canonical_owner_message(packet),
                 hashlib.sha256).hexdigest()
    packet["owner_integrity"]["owner_hmac_sha256"]=mac
    verification=verify_owner_packet(
        packet=packet,
        trusted_keys={source_name:{owner_id:owner_hmac_key}},
        decision_at_utc=signed_at_utc)
    if verification!="VERIFIED_OWNER_HMAC_PACKET_ONLY":
        raise ValueError("own signed source packet fails verifier contract")
    return packet
