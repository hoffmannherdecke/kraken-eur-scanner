"""Explicit V3 signed SOURCE owner -> existing immutable journal proof stage.

The general PR216/226 intake always persists SOURCE_INPUT:FIRST:UNKNOWN:
a plain preflight dict cannot authenticate an owner. This separate INACTIVE
stage validates the ORIGINAL signed packet again using caller-supplied secret
key bytes and links it to the actual source candidate selected/deferred/
coalesced by the canonical preflight. ONLY THEN write a SECOND immutable
SOURCE_INPUT:OWNERAUTH:PASS receipt.

This proves successful cryptographic checking at this function call, NOT
live key provisioning, a real source's factual truth, Kraken-P0, model budget,
an active Mini-PC writer, a BUY or independent Cloud ACK. No keys or raw
source packets go into journal receipts, files, logs or returned status.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from paper_evaluator.v3_experimental_paper_journal_v1 import (
    make_receipt,store_receipt_explicitly,
)
from paper_evaluator.v3_paper_cloud_receipt_sync_v1 import REVISION
from paper_evaluator.v3_paper_existing_owner_source_bridge_v1 import fingerprint
from paper_evaluator.v3_paper_positive_source_entry_v1 import make_source_candidate,STREAMS
from paper_evaluator.v3_paper_source_owner_hmac_v1 import (
    verify_owner_packet,validate_keyring,
)

KIND="V3_FUTURE_SINGLE_PAPER_WRITER_PRE_FLIGHT_PLAN_V1"
SOURCE="VERIFIED_POSITIVE_SOURCE_CATALYST"
PHASE="SOURCE_INPUT"
AUTH_EVENT="OWNERAUTH"
MAX_SIGNED_EVENTS=60


def prepare_signed_owner_receipts(*,preflight:dict[str,Any],
                                  signed_owner_packets:list[dict[str,Any]],
                                  trusted_owner_hmac_keys:dict[str,dict[str,bytes]])->list[dict[str,Any]]:
    """Pure plan with fresh independent MAC verification and exact PIT lineage."""
    if (not isinstance(preflight,dict) or preflight.get("kind")!=KIND
            or any(preflight.get(k) is not False for k in (
                "model_http_authorized","orders","real_money_actions",
                "paper_writer_active","cloud_active_series_changed","v2r4_changed"
            ))):
        raise ValueError("unsigned preflight or active strategy/spend attempt")
    if (not isinstance(signed_owner_packets,list)
            or len(signed_owner_packets)>MAX_SIGNED_EVENTS):
        raise ValueError("bounded owner signed original events required")
    keys=validate_keyring(trusted_owner_hmac_keys)
    series=preflight["series_id"]
    at=preflight["at_utc"]
    source=preflight.get("source_provenance")
    ingress=preflight.get("ingress")
    if not isinstance(source,dict) or not isinstance(ingress,dict):
        raise ValueError("actual canonical preflight source lineage required")
    accepted=source.get("owner_source_events")
    if not isinstance(accepted,list):
        raise ValueError("original accepted source event list missing")
    selected=preflight.get("selected_candidates")
    deferred=ingress.get("capacity_deferred_originals")
    coalesced=ingress.get("same_pair_coalesced_originals")
    if not all(isinstance(x,list) for x in (selected,deferred,coalesced)):
        raise ValueError("complete original source candidate disposition required")
    eligible={}
    for c in selected+deferred+coalesced:
        if not isinstance(c,dict):
            raise ValueError("source candidate must preserve identity")
        if c.get("entry_origin")!=SOURCE:
            continue
        cid=c.get("candidate_id")
        if not isinstance(cid,str) or cid in eligible:
            raise ValueError("ambiguous source original candidate identity")
        eligible[cid]=c
    expected={}
    for raw in accepted:
        if not isinstance(raw,dict):
            raise ValueError("untrusted accepted source row")
        name=raw.get("source_name")
        if name not in STREAMS:
            raise ValueError("unexpected accepted source stream")
        snapshot=raw.get("snapshot")
        if not isinstance(snapshot,dict):
            raise ValueError("source original payload absent")
        candidate=make_source_candidate(
            pair=raw["pair"],kraken_altname=raw["altname"],
            source_name=name,snapshot=snapshot,
            decision_at_utc=at,market_move=raw.get("market_move"))
        cid=candidate["candidate_id"]
        if cid not in eligible:  # Router rejection is instead audit-only.
            continue
        c=eligible[cid]
        if any(c.get(k)!=candidate[k] for k in
               ("candidate_id","pair","altname","event_time_utc","entry_origin")):
            raise ValueError("accepted source and router candidate disagree")
        if cid in expected:
            raise ValueError("duplicate signed accepted source candidate")
        expected[cid]=(raw,candidate)
    # Do not let a fabricated preflight introduce candidates without the
    # EXACT previously signed source row.
    if set(expected)!=set(eligible):
        raise ValueError("source proof would not cover every source intake original")
    results={}
    for packet in signed_owner_packets:
        if not isinstance(packet,dict):
            raise ValueError("source signature original missing")
        name=packet.get("source_name")
        if name not in STREAMS:
            raise ValueError("invalid signed packet stream")
        if verify_owner_packet(
                packet=packet,trusted_keys=keys,
                decision_at_utc=at)!="VERIFIED_OWNER_HMAC_PACKET_ONLY":
            raise ValueError("live source HMAC proof invalid, no source promotion")
        candidate=make_source_candidate(
            pair=packet["pair"],kraken_altname=packet["altname"],
            source_name=name,snapshot=packet["snapshot"],
            decision_at_utc=at,market_move=packet.get("market_move"))
        cid=candidate["candidate_id"]
        if cid not in expected:
            # No attestations for pre-router rejected inputs; those already
            # have a distinct SOURCE_OWNER ROUTERREJECT audit.
            raise ValueError("signed source packet absent from exact canonical intake")
        actual=expected[cid][0]
        if any(packet.get(k)!=actual.get(k) for k in
               ("source_name","pair","altname","snapshot","market_move")):
            raise ValueError("signed packet differs from original accepted packet")
        if cid in results:
            raise ValueError("duplicate source owner proof in same batch")
        snap=packet["snapshot"]
        results[cid]=make_receipt(
            series_id=series,revision=REVISION,candidate_id=cid,
            pair=candidate["pair"],event_time_utc=candidate["event_time_utc"],
            known_at_utc=at,phase=PHASE,result="PASS",event_key=AUTH_EVENT,
            data={
                "candidate_origin":SOURCE,
                "positive_source_name":name,
                "positive_source_event_id":snap["event_id"],
                "positive_source_owner":snap["source_owner"],
                "input_fingerprint_sha256":fingerprint(snap),
                "source_status":"VERIFIED_OWNER_HMAC_PACKET_ONLY_NO_MODEL_OR_BUY",
                "independent_source_entry":True,
                "source_pair_metadata_status":"REAL_KRAKEN_PAIR_NOT_CHECKED_BY_AUTH",
            })
    if set(results)!=set(expected):
        raise ValueError("missing authenticated original owner packet")
    return [results[cid] for cid in sorted(results)]


def stage_signed_owner_receipts_explicitly(*,preflight:dict[str,Any],
        signed_owner_packets:list[dict[str,Any]],
        trusted_owner_hmac_keys:dict[str,dict[str,bytes]],
        journal_directory:Path)->dict[str,Any]:
    """Require immutable UNKNOWN:FIRST intake and then append OWNEREAUTH.

    Function must be called by a separately authorized single Writer with
    physical trust+secret provision; no secret is persisted or returned.
    """
    planned=prepare_signed_owner_receipts(
        preflight=preflight,signed_owner_packets=signed_owner_packets,
        trusted_owner_hmac_keys=trusted_owner_hmac_keys)
    root=Path(journal_directory)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("existing isolated immutable journal directory required")
    prior={}
    for file in root.glob("*.json"):
        if not file.is_file() or file.is_symlink():
            raise ValueError("unsafe journal source path")
        old=json.loads(file.read_text("utf-8"))
        if old.get("series_id")!=preflight["series_id"]:
            raise ValueError("separate V3 research series journal required")
        cid=old.get("candidate_id")
        prior.setdefault(cid,[]).append(old)
    # No filesystem changes until ALL original UNKNOWN receipts are checked.
    for next_receipt in planned:
        records=prior.get(next_receipt["candidate_id"],[])
        first=[r for r in records
               if r.get("phase")==PHASE and r.get("event_key")=="FIRST"]
        if (len(first)!=1 or first[0].get("result")!="UNKNOWN"
                or first[0].get("pair")!=next_receipt["pair"]
                or first[0].get("event_time_utc")!=next_receipt["event_time_utc"]
                or first[0].get("revision")!=REVISION
                or first[0].get("data",{}).get("source_status")!=
                   "SOURCE_OWNER_RUNTIME_AUTH_NOT_PROVEN"):
            raise ValueError("original source FIRST UNKNOWN receipt missing or changed")
        for row in records:
            if row.get("phase") in ("MODEL_REQUEST","P4_VALIDATION","PAPER_FILL","PAPER_EXIT"):
                raise ValueError("source cannot retroactively authenticate completed model/trade")
    results=[]
    for receipt in planned:
        state,_=store_receipt_explicitly(root,receipt)
        results.append(state)
    return {
        "kind":"V3_SOURCE_OWNER_SIGNED_RECEIPT_STAGE_V1",
        "status":"ISOLATED_LOCAL_OWNER_HMAC_ATTESTATIONS_ONLY",
        "source_signed_origins_considered":len(planned),
        "immutable_new_auth_receipts":results.count("IMMUTABLE_NEW_RECEIPT"),
        "idempotent_replays":results.count("IDEMPOTENT_IDENTICAL"),
        "proof_key_bytes_persisted":False,
        "raw_source_packet_persisted":False,
        "real_owner_live_runtime_verified":False,
        "model_http_authorized":False,
        "orders":False,
        "cloud_ack_verified":False,
        "v2r4_unchanged":True,
        "v3_paper_activated":False,
    }
