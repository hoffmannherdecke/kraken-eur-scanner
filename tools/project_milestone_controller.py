#!/usr/bin/env python3
"""Bounded, read-only milestone gate evaluator with one-shot notifications.

Authoritative declared state: project-current-state.json.
Authoritative live evidence: Supabase views (GET only).
Allowed writes: one GitHub issue comment and optional Slack message per ready gate.
Never changes project state, release status, strategy, thresholds, orders or DB rows.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request

try:
    from tools.strategy_epoch_lineage import summarize_epoch
    from tools.project_followthrough_router import (v3_five_source_followthrough,
        project_implementation_commitments, operational_release_snapshot)
    from tools.context_before_action import live_owner_readback, ContextGateError, _github_api_read, GITHUB_API_BASE
    from tools.paper_series_transition_guard import select_current_readiness
except ModuleNotFoundError:
    from strategy_epoch_lineage import summarize_epoch
    from project_followthrough_router import (v3_five_source_followthrough,
        project_implementation_commitments, operational_release_snapshot)
    from context_before_action import live_owner_readback, ContextGateError, _github_api_read, GITHUB_API_BASE
    from paper_series_transition_guard import select_current_readiness

ROOT = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc
ISSUE_BY_KIND = {"H3_FIXED_REVIEW": 7, "H3_STALE_EVIDENCE": 7,
                 "H3_ARCHIVED_INCOMPLETE_REVIEW": 7, "PAPER_FINAL_REVIEW": 38,
                 "PAPER_LOW_TRADES": 38, "CONTROL_FOLLOWTHROUGH_MISSED": 38, "H10_CONTRACT": 7,
                 "NEW_SHADOW_ADAPTER": 7, "NEW_CONTROL_DECISION": 7,
                 "H10_FIRST_SOURCE_RECEIPT_REVIEW": 7,
                 "H10_SOURCE_RECEIPT_INTEGRITY": 7,
                 "V3_PAPER_FIVE_SOURCE_FOLLOWTHROUGH_DUE": 7,
                 "PROJECT_IMPLEMENTATION_COMMITMENT_REVIEW": 7,
                 "V2R4_WAIT_INCIDENT_FOLLOWTHROUGH_DUE": 99,
                 "PAPER_RUNTIME_LEASE_REVIEW": 99,
                 "PAPER_NATIVE_HEALTH_REVIEW": 353}
SUPPORTED_DECISIONS = {"V3-H3-ARCHIVE-DISPOSITION", "V2R4-PRODUCTIVITY-REVIEW",
                       "V3-EXTENDED-SECOND-LEG-LEARNING-GATE"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError("FAIL_CLOSED: " + message)


def iso_time(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def load_local_state(root: Path) -> dict:
    state = json.loads((root / "project-current-state.json").read_text("utf-8"))
    require(state.get("kind") == "PROJECT_CURRENT_STATE_V1", "unknown state schema")
    active = state.get("active_strategy") or {}
    inv = state.get("permanent_invariants") or {}
    require(active.get("mode") == "PAPER", "current control supports PAPER only")
    require(active.get("automatic_activation_allowed") is False, "auto activation forbidden")
    require(active.get("real_money_actions") is False, "real money forbidden")
    require(active.get("mid_series_material_tuning_allowed") is False, "mid-series tuning forbidden")
    require(inv.get("automatic_strategy_promotion") is False, "auto promotion forbidden")
    require(inv.get("one_strategy_changing_shadow_at_a_time") is True, "shadow WIP rule missing")
    shadows = (state.get("strategy_changing_shadow_wip") or {}).get("active") or []
    require(len(shadows) <= 1, "more than one strategy-changing shadow")
    decisions = state.get("next_control_decisions") or []
    ids = [x.get("id") for x in decisions]
    require(len(ids) == len(set(ids)) and all(ids), "duplicate/invalid control decisions")
    return state


def get_rows(base: str, key: str, view: str) -> list:
    """Read only the existing Cloud authority; never pick a stale first row.

    The historical V2R4 readiness view used to have one row. After a real
    V3 cutover an archived V2R4 readiness can coexist with the current V3
    readiness. The original pure routing guard decides which one is active.
    """
    require(re.fullmatch(r"https://[a-z0-9-]+[.]supabase[.]co", base.rstrip("/")) is not None,
            "unapproved Supabase host")
    allowed = {
        "paper_series": ("series_id,strategy_revision,status",
                         "status=eq.active&limit=2", 2),
        "paper_series_completion_readiness": ("*", "limit=101", 100),
        "v3_h3_shadow_status": ("*", "", 1),
        "paper_series_runtime_identity": (
            "series_id,strategy_revision,status,release_repo_sha:config->>release_repo_sha,"
            "runtime_bundle_sha256:config->>runtime_bundle_fingerprint_sha256,"
            "strategy_sha256:config->>strategy_fingerprint_sha256",
            "status=eq.active&limit=2", 2),
    }
    require(view in allowed, "unapproved evidence view")
    projection, options, max_rows = allowed[view]
    # Preserve explicit bounded GET only. No scripts, service calls, RPCs,
    # Paper mutation, model spend or alternate Work schedule.
    table = "paper_series" if view=="paper_series_runtime_identity" else view
    url = base.rstrip("/") + "/rest/v1/" + table + "?select=" + projection
    if options:
        url += "&" + options
    headers = {"apikey": key, "Accept": "application/json",
               "User-Agent": "project-milestone-controller/1"}
    if not key.startswith("sb_secret_"):
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as response:
        rows = json.load(response)
    require(isinstance(rows, list) and len(rows) <= max_rows,
            view + " Cloud rows missing bounded cardinality")
    if view == "v3_h3_shadow_status":
        require(len(rows) == 1, "H3 status must return exactly one row")
    return rows


def current_active_paper_readiness(base: str, key: str) -> dict:
    """Existing single-live-series guard shared with the daily report.

    Source is live Cloud paper_series, NOT frozen declared V2R4 epoch and
    NOT the first arbitrary historical readiness row.
    """
    active = get_rows(base, key, "paper_series")
    readiness = get_rows(base, key, "paper_series_completion_readiness")
    return select_current_readiness(active, readiness)


def resolve_current_paper_owner(state: dict, owner: dict, now: dt.datetime,
                                fetcher=None) -> tuple[dict, dict]:
    """Use the existing #99 current evidence reference, never release authority."""
    prior = operational_release_snapshot(state, now)
    require(prior is not None, "no declared historical Paper release")
    require(owner.get("no_trading_or_release_authority") is True,
            "unexpected owner readback authority")
    fach = [x for x in owner["owners"] if x.get("issue") == 99]
    require(len(fach) == 1 and not fach[0].get("current_owner_header_truncated"),
            "current Paper fachowner unavailable")
    head = fach[0]["current_owner_header_excerpt"]
    blocks = re.findall(r"<!-- CURRENT_PAPER_OPERATIONAL_STATUS_V1\s*\n(.*?)\nEND_CURRENT_PAPER_OPERATIONAL_STATUS_V1 -->", head, re.S)
    require(len(blocks) == 1, "current Paper original reference missing or ambiguous")
    record = json.loads(blocks[0])
    keys = {"series_id", "strategy_revision", "strategy_version", "source",
            "observed_at_utc", "lease_expires_at_utc", "lease_source", "review_requests"}
    require(isinstance(record, dict) and set(record) == keys,
            "invalid current Paper original reference")
    require(isinstance(record["strategy_version"],str) and re.fullmatch(r"V[0-9]+",record["strategy_version"]) is not None,
            "unsupported strategy version identity")
    current = dict(prior, **{k: record[k] for k in keys - {"lease_expires_at_utc", "lease_source", "review_requests"}},
                   release_milestone=record["strategy_version"] + "_PAPER_OPERATIONAL")
    require(operational_release_snapshot({"operational_release_snapshot": current}, now) is not None,
            "future operational evidence timestamp")
    require(iso_time(current["observed_at_utc"]) >= iso_time(prior["observed_at_utc"]),
            "owner attempted rollback to older Paper evidence")
    getter = fetcher or _github_api_read
    def original(url):
        match = re.fullmatch(r"https://github[.]com/hoffmannherdecke/kraken-eur-scanner/issues/99#issuecomment-([0-9]+)", url)
        require(match is not None, "not an existing #99 original")
        item, _ = getter(GITHUB_API_BASE + "/issues/comments/" + match.group(1))
        require(isinstance(item, dict) and str(item.get("id")) == match.group(1)
                and item.get("html_url") == url
                and isinstance(item.get("body"), str)
                and current["series_id"] in item["body"],
                "current original receipt/series mismatch")
        return item["body"]
    proof = original(record["source"])
    require(current["release_milestone"] in proof, "current original lacks operating milestone")
    if current["series_id"] != prior["series_id"] or current["strategy_revision"] != prior["strategy_revision"]:
        require(current["strategy_revision"] in proof, "successor original lacks exact revision")
    lease = proof if record["lease_source"] == record["source"] else original(record["lease_source"])
    if record["lease_expires_at_utc"] is None:
        require("V3_PAPER_RUNTIME_UNTIL_REVOKED" in lease,
                "unbounded runtime scope not present in original")
    else:
        expiry = iso_time(record["lease_expires_at_utc"])
        require(expiry > iso_time(record["observed_at_utc"]), "invalid last recorded lease")
        require("lease" in lease.lower() and expiry.strftime("%H:%M:%S") in lease
                and (expiry.strftime("%d.%m.%Y") in lease or expiry.strftime("%Y-%m-%d") in lease),
                "last recorded lease expiry not present in original")
    requests=record["review_requests"]
    require(isinstance(requests,dict) and len(requests)<=16
            and all(isinstance(x,str) for x in requests), "invalid current owner review list")
    for ident, url in requests.items():
        require(ident in original(url), "current review request lacks exact registered obligation")
    return dict(state, operational_release_snapshot=current), record


def native_paper_evidence(base: str, key: str, paper: dict, now: dt.datetime) -> dict:
    """Exact native journal receipt counts at one UTC cutoff, no payload scan.

    Receipt counts are neither closed positions nor profitability. Unknown
    future journal contracts remain explicit, never mapped to V3 by guess.
    """
    require(re.fullmatch(r"https://[a-z0-9-]+[.]supabase[.]co", base.rstrip("/")) is not None,
            "unapproved evidence host")
    sid, rev = paper["series_id"], paper["strategy_revision"]
    if not rev.startswith("V3-"):
        return {"status": "NATIVE_JOURNAL_ADAPTER_REQUIRES_VERSION_REVIEW",
                "series_id": sid, "strategy_revision": rev, "native_journal_checked": False}
    headers = {"apikey": key, "Accept": "application/json",
               "User-Agent": "project-milestone-controller/1", "Prefer": "count=exact"}
    if not key.startswith("sb_secret_"):
        headers["Authorization"] = "Bearer " + key
    def read(phase=None, result=None, foreign=False):
        params = {"select": "event_id,series_id,revision,phase,result,received_at",
                  "series_id": "eq." + sid, "revision": ("neq." if foreign else "eq.")+rev,
                  "received_at":"lte."+now.isoformat(),
                  "order": "received_at.desc,event_id.desc", "limit": "1"}
        if phase: params["phase"] = "eq." + phase
        if result: params["result"] = "eq." + result
        url = base.rstrip("/") + "/rest/v1/v3_paper_event_receipts?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=15) as response:
            rows = json.load(response)
            total = response.headers.get("Content-Range", "").rsplit("/",1)[-1]
        require(isinstance(rows,list) and len(rows)<=1 and total.isdigit()
                and (int(total)>0)==bool(rows), "native journal exact count unavailable")
        if rows:
            row=rows[0]
            require(row.get("series_id")==sid and ((row.get("revision")!=rev) if foreign else (row.get("revision")==rev))
                    and (not phase or row.get("phase")==phase)
                    and (not result or row.get("result")==result)
                    and iso_time(row["received_at"])<=now,
                    "foreign or future native journal receipt")
        return int(total), rows[0] if rows else None
    require(read(foreign=True)[0]==0,"native journal contains foreign revision")
    total, last = read()
    filters = {"scanner":("SCANNER_CAPTURE","SEEN"),"wait":("P4_VALIDATION","WAIT"),
               "reject":("P4_VALIDATION","REJECT"),"buy":("P4_VALIDATION","BUY_SCOUT"),
               "fill":("PAPER_FILL","PAPER_FILLED"),"exit":("PAPER_EXIT","CLOSED"),
               "mature_6h":("FOLLOWUP_6H","MATURE_COMPLETE"),
               "mature_24h":("FOLLOWUP_24H","MATURE_COMPLETE"),
               "mature_72h":("FOLLOWUP_72H","MATURE_COMPLETE")}
    counts = {k: read(*v)[0] for k,v in filters.items()}
    require(sum(counts.values())<=total, "inconsistent native journal counts; reconcile originals")
    return {"status":"NATIVE_V3_RECEIPT_COUNTS_NOT_PROFITABILITY",
            "series_id":sid,"strategy_revision":rev,"native_journal_checked":True,
            "observed_at_utc":now.isoformat(),"receipt_count":total,
            "latest_received_at":last["received_at"] if last else None,
            "phase_receipt_counts":counts,"realized_net_pnl_eur":None,
            "economic_qualification_verified":False,"host_health_verified":False}


def current_host_report(base: str, key: str, paper: dict, now: dt.datetime,
                        runtime_identity: dict, lease_expires_at_utc: str | None) -> dict:
    """Read existing host-relay report, not a direct physical health proof."""
    require(re.fullmatch(r"https://[a-z0-9-]+[.]supabase[.]co", base.rstrip("/")) is not None,
            "unapproved evidence host")
    url=base.rstrip("/")+"/rest/v1/minipc_status_current?select=node_id,observed_at,status,payload&node_id=eq.MINI-PC&limit=2"
    headers={"apikey":key,"Accept":"application/json","User-Agent":"project-milestone-controller/1"}
    if not key.startswith("sb_secret_"): headers["Authorization"]="Bearer "+key
    with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=15) as response:
        rows=json.load(response)
    if not isinstance(rows,list) or len(rows)!=1:
        return {"status":"UNKNOWN_HOST_REPORT","host_health_verified":False}
    row=rows[0]; payload=row.get("payload") or {}
    age=(now-iso_time(row["observed_at"])).total_seconds()
    writer=(payload.get("checks") or {}).get("v3_paper_single_writer") or {}
    native=((payload.get("native_task_readback") or {}).get("observations") or {}).get("v3_paper_single_writer") or {}
    identity=payload.get("paper_successor_observation") or {}
    fresh= -30<=age<=1200
    pins=("release_repo_sha","runtime_bundle_sha256","strategy_sha256")
    pins_match=all(isinstance(runtime_identity.get(k),str)
                   and re.fullmatch(r"[a-f0-9]{40}" if k=="release_repo_sha" else r"[a-f0-9]{64}",runtime_identity[k])
                   and identity.get(k)==runtime_identity[k] for k in pins)
    try:
        reported_clock=iso_time(identity["observed_at_utc"])
        if lease_expires_at_utc is None:
            lease_matches = (identity["expires_at_utc"] is None
                             and identity.get("runtime_scope") == "V3_PAPER_RUNTIME_UNTIL_REVOKED")
        else:
            reported_expiry = iso_time(identity["expires_at_utc"])
            lease_matches = reported_expiry == iso_time(lease_expires_at_utc) and reported_expiry > now
        clock_and_lease_match = (
            -30 <= (iso_time(row["observed_at"]) - reported_clock).total_seconds() <= 180
            and lease_matches
        )
    except (KeyError,ValueError,TypeError):
        clock_and_lease_match=False
    reported_ok=(fresh and writer.get("ok") is True and native.get("task_state")=="Running"
                 and identity.get("series_id")==paper["series_id"]
                 and identity.get("host_report_only") is True
                 and identity.get("independent_runtime_proof") is False
                 and pins_match and clock_and_lease_match)
    return {"status":("HOST_REPORT_V3_MATCH_NOT_INDEPENDENT_PROOF" if reported_ok else
                      "HOST_REPORT_STALE" if not fresh else "V3_HEARTBEAT_NOT_PROVEN_BY_HOST_REPORT"),
            "host_reported_status":row.get("status"),"observed_at":row["observed_at"],
            "issue_codes":[x.get("check") for x in (payload.get("issues") or []) if isinstance(x,dict)],
            "writer_reported_ok":reported_ok,"host_health_verified":False}


def current_review_basis(record: dict, journal: dict) -> dict:
    """Only current material evidence triggers a registered review; no tuning."""
    due={k:"OWNER_ORIGINAL:"+v for k,v in record["review_requests"].items()}
    counts=journal.get("phase_receipt_counts") or {}
    # First maturity for each horizon/exit is a distinct review stage.
    maturity=[k for k in ("mature_6h","mature_24h","mature_72h","exit") if counts.get(k,0)>0]
    if maturity:
        key="V3_PAPER_NET_ECONOMIC_REVIEW"
        due[key]="|".join(filter(None,(due.get(key),"NATIVE:"+",".join(maturity))))
    if counts.get("fill",0)>0 and counts.get("exit",0)>0:
        key="V3_H4_H7_H9_EXITS_AND_EXECUTION"
        due[key]="|".join(filter(None,(due.get(key),"NATIVE_FILL_AND_EXIT")))
    return due


def read_operational_evidence(state: dict, base: str, key: str, now: dt.datetime,
                              expected_main: str | None = None) -> tuple[dict, dict, dict]:
    # Reuse #99, the existing Paper fachowner. The historical AP dashboard
    # is not the current-version authority or a successor release gate.
    owner=live_owner_readback("operations","V3",expected_main=expected_main)
    state, record=resolve_current_paper_owner(state,owner,now)
    paper=current_active_paper_readiness(base,key)
    current=operational_release_snapshot(state,now)
    require(paper["series_id"]==current["series_id"] and paper["strategy_revision"]==current["strategy_revision"],
            "CURRENT_CLOUD_IDENTITY_DIFFERS_FROM_OWNER_ORIGINAL")
    journal=native_paper_evidence(base,key,paper,now)
    runtime=get_rows(base,key,"paper_series_runtime_identity")
    require(len(runtime)==1 and runtime[0].get("series_id")==paper["series_id"]
            and runtime[0].get("strategy_revision")==paper["strategy_revision"],
            "Cloud runtime identity changed during operational read")
    host=current_host_report(base,key,paper,dt.datetime.now(UTC),runtime[0],record["lease_expires_at_utc"])
    due=current_review_basis(record,journal)
    repeated=live_owner_readback("operations","V3",expected_main=owner["main_sha"])
    require(repeated["owners"]==owner["owners"],"owner changed during operational read")
    # Check the same Cloud active identity after the bounded original reads.
    active=get_rows(base,key,"paper_series_runtime_identity")
    require(active==runtime,
            "Cloud identity changed during operational read")
    evidence={"kind":"CURRENT_OPERATIONAL_REVIEW_EVIDENCE_V1","main_sha":owner["main_sha"],
              "series_id":paper["series_id"],"strategy_revision":paper["strategy_revision"],
              "source":current["source"],"observed_at_utc":now.isoformat(),
              "review_basis":due,"journal":journal,"host":host,
              "lease_expires_at_utc":record["lease_expires_at_utc"],
              "lease_source":record["lease_source"],"no_release_or_runtime_authority":True}
    return state,paper,evidence


def first_h10_source_receipt_review(base: str, key: str) -> tuple[str, dict | None]:
    """Single SELECT in existing milestone run; a stored source row is NOT a BUY."""
    require(re.fullmatch(r"https://[a-z0-9-]+[.]supabase[.]co", base.rstrip("/"))
            is not None, "unapproved H10 evidence host")
    fields=("candidate_id,cohort_id,cohort_role,coin,window_start_utc,"
            "content_sha256,original_payload_canonical,received_at_utc")
    query=urllib.parse.urlencode({"select":fields,
                                   "order":"received_at_utc.asc","limit":"1"})
    url=base.rstrip("/")+"/rest/v1/v3_h10_selected_source_receipts?"+query
    headers={"apikey":key, "Accept":"application/json",
             "User-Agent":"project-milestone-controller/1"}
    if not key.startswith("sb_secret_"):
        headers["Authorization"]="Bearer "+key
    with urllib.request.urlopen(urllib.request.Request(url,headers=headers),
                                timeout=15) as response:
        rows=json.load(response)
    require(isinstance(rows,list) and len(rows)<=1,"invalid H10 selected source query")
    if not rows:
        return "H10:ORIGINAL_SOURCE_RECEIPT_PENDING",None

    row=rows[0]
    require(isinstance(row,dict),"invalid H10 receipt")
    raw=row.get("original_payload_canonical")
    require(isinstance(raw,str) and len(raw.encode("utf-8"))<=65536,
            "invalid H10 canonical bytes")
    payload=json.loads(raw)
    canonical=json.dumps(payload,sort_keys=True,ensure_ascii=True,
                         separators=(",",":"),allow_nan=False)
    require(canonical==raw and
            hashlib.sha256(raw.encode("utf-8")).hexdigest()==row.get("content_sha256"),
            "H10 receipt content not canonical or digest mismatch")
    identity={"cohort_id":row.get("cohort_id"),"role":row.get("cohort_role"),
              "coin":row.get("coin"),"window_start_utc":payload.get("window_start_utc")}
    identity_sha=hashlib.sha256(json.dumps(identity,sort_keys=True,
                    ensure_ascii=True,separators=(",",":")).encode("utf-8")).hexdigest()
    require(identity_sha==row.get("candidate_id"),"invalid H10 receipt identity")
    require(payload.get("cohort_id")==row.get("cohort_id") and
            payload.get("cohort_role")==row.get("cohort_role") and
            payload.get("coin")==row.get("coin"),"unbound H10 source row")
    require(iso_time(row["window_start_utc"])==
            iso_time(payload["window_start_utc"]),"H10 source window mismatch")
    require(payload.get("orders") is False and
            payload.get("no_buy_authority") is True,"H10 receipt trading flag")
    events=payload.get("original_events") or []
    require(3<=len(events)<=128 and
            len({e["wallet_address"] for e in events})>=3,
            "H10 stored proof lacks distinct wallets")
    start=iso_time(row["window_start_utc"])
    received=iso_time(row["received_at_utc"])
    require(start+dt.timedelta(minutes=30)<=received<=
            start+dt.timedelta(hours=47,minutes=55),
            "H10 receipt server time invalid")
    return "H10:FIRST_STORED_SOURCE_RECEIPT_REVIEW_DUE",event(
        "H10_FIRST_SOURCE_RECEIPT_REVIEW",
        "H10-FIRST-STORED-ORIGINAL-RECEIPT",
        "Erster selektiver H10-Originalquellbeleg wurde in Supabase gefunden "
        "und per kanonischem SHA, Zeitfenster und Wallet-Adressen vorgeprüft. "
        "Echter Erstfall muss fachlich (Originalbatch, unabhängige Wallets, "
        "Self-Dealing, Quelle und P0) geprüft werden. Kein BUY, keine Aktivierung. "
        "Quittung: "+str(row["candidate_id"])[:16])


def event(kind: str, anchor: str, detail: str) -> dict:
    require(kind in ISSUE_BY_KIND, "unapproved event kind")
    require(bool(anchor) and len(anchor) < 180, "invalid event anchor")
    digest = hashlib.sha256((kind + "|" + anchor).encode("utf-8")).hexdigest()[:20]
    return {"kind": kind, "event_key": "PROJECT_MILESTONE_V1_" + digest,
            "issue": ISSUE_BY_KIND[kind], "detail": detail}


def evaluate_verified_v3_paper(state: dict, paper: dict, now: dt.datetime, root: Path) -> dict:
    """Version-aware successor milestone readout; no V2R4-era false alarms.

    The series must have been physically proven active *before* state switches.
    Never use a PR merge, a read-only V3 draft or a missing cloud view as proof.
    """
    active = state["active_strategy"]
    revision = active["strategy_revision"]
    transition = state.get("pending_strategy_transition") or {}
    require(revision.startswith("V3-") and
            transition.get("kind") == "CONTROLLED_V2R4_TO_V3_PAPER_TRANSITION_INTENT_V1" and
            transition.get("status") == "V3_PAPER_ACTIVE_VERIFIED",
            "V3 milestone controller cannot infer activation from plans")
    ack = transition.get("verified_cutover_evidence") or {}
    require(ack.get("mini_pc_and_single_active_supabase_series_ack") is True,
            "V3 milestone controller needs physical/cloud single-writer ACK")
    series = active.get("series_id")
    require(series and paper.get("series_id") == series,
            "V3 paper status from wrong/stale active series")
    require(paper.get("strategy_revision") == revision,
            "V3 paper strategy revision drift")
    require(paper.get("candidate_outcomes") is not None
            and paper.get("completed_trades") is not None,
            "V3 paper readiness missing trade/candidate evidence")
    require(paper.get("fasttrack_policy_version") == "EVIDENCE_DIVERSITY_FASTTRACK_V2",
            "V3 paper evidence-diversity gate must remain valid")
    statuses = ["V3:PAPER_ACTIVE_CLOUD_VERIFIED",
                "V2R4:RETIRED_NEW_INTAKE_FOLLOWUPS_RETAINED"]
    notices = []
    for decision_id, note in due_followthrough_events(state, now, root):
        statuses.append("FOLLOWTHROUGH:ACK_OVERDUE:" + decision_id)
        notices.append(note)
    # Reuse the sole daily milestone watcher: remind Work only after
    # an authentically verified V3 Paper cutover, never just a merged PR.
    try:
        work_ack=json.loads((root/"research/work-analysis-state.json").read_text("utf-8"))
        source_route=v3_five_source_followthrough(root,state,work_ack,now)
    except (OSError,ValueError,TypeError) as exc:
        source_route={"status":"SOURCE_FOLLOWTHROUGH_OWNER_OR_ACK_UNAVAILABLE",
                      "open_roles":[]}
    if source_route["status"]=="SOURCE_WORK_OPEN":
        statuses.append("V3:POST_CUTOVER_OPTIONAL_SOURCE_E2E_OPEN")
        notices.append(event("V3_PAPER_FIVE_SOURCE_FOLLOWTHROUGH_DUE",
                             series,
            "V3 PAPER ist physisch/cloudseitig bestätigt, aber die fünf "
            "optional-quellenbezogenen End-to-End-ACKs sind weiter offen: "
            +", ".join(source_route["open_roles"])+
            ". Vorhandenes tägliches 10:15-Work wählt maximal zwei sichere "
            "Arbeiten aus, führt konkrete Quellen-/Modell-/Quittungs-Prüfungen "
            "mit PR/CI aus; nicht durch GitHub-Notiz als fertig markieren. "
            "Kein neuer Watcher und keine automatische BUY-/Runtime-Freigabe."))
    elif source_route["status"]!="FIVE_SOURCE_DOCUMENTARY_ACKS_RECORDED_LIVE_RECHECK_STILL_REQUIRED":
        statuses.append("V3:POST_CUTOVER_SOURCE_FOLLOWTHROUGH_REVIEW_REQUIRED")
    else:
        statuses.append("V3:POST_CUTOVER_FIVE_SOURCE_ACK_RECORDED_INDEPENDENT_REVIEW_REMAINS")
    if paper.get("completion_ready") is True:
        require(paper.get("intake_should_stop") is True and
                paper.get("temporal_diversity_ready") is True and
                paper.get("qualifying_maturity_ready") is True,
                "V3 paper completion gate bypasses diversity/mature outcomes")
        statuses.append("V3:PAPER_COMPLETION_READY")
        notices.append(event("PAPER_FINAL_REVIEW", series,
            "V3-Paper-Serie hat das belegte Abschlussgate erreicht: "
            "vollständige wirtschaftliche Auswertung und separate Strategie-"
            "Entscheidung nötig; alte V2R4-24h-Followups unverändert bewahren; "
            "kein H3/H6- oder Echtgeld-Autostart."))
    else:
        statuses.append("V3:PAPER_COLLECTING")
    return {"kind": "PROJECT_MILESTONE_CONTROL_V1",
            "series_id": series, "live_technical_series_id": series,
            "statuses": statuses, "events": notices,
            "strategy_changed": False, "orders": False,
            "real_money_actions": False}


def evaluate_operational_paper(milestone: dict, paper: dict) -> dict:
    """Cloud readiness is current evidence only for the matching series/revision.

    Release history is not a heartbeat. The compatibility view is not the
    V3 journal; zero view rows cannot prove zero candidate decisions.
    """
    require(paper.get("series_id") == milestone["series_id"]
            and paper.get("strategy_revision") == milestone["strategy_revision"],
            "CURRENT_CLOUD_IDENTITY_DIFFERS_FROM_LAST_AUTHORIZED_RELEASE_NEEDS_OWNER_ACK: "
            + str(paper.get("series_id")) + " / " + str(paper.get("strategy_revision")))
    for field in ("candidate_outcomes", "completed_trades"):
        require(type(paper.get(field)) is int and paper[field] >= 0,
                "missing or invalid readiness view count: " + field)
    require(paper.get("fasttrack_policy_version") == "EVIDENCE_DIVERSITY_FASTTRACK_V2",
            "paper evidence-diversity contract changed; current owner review required")
    version = milestone["strategy_version"]
    statuses = [version + ":PAPER_ACTIVE_CLOUD_IDENTITY_VERIFIED",
                "RELEASE_COMPLETED_HISTORICAL_NOT_LIVE_HOST_HEALTH",
                "READINESS_VIEW_COUNTS_ONLY_NOT_NATIVE_JOURNAL",
                "ECONOMIC_QUALIFICATION_NOT_PROVEN_BY_RELEASE"]
    notices = []
    if paper.get("completion_ready") is True:
        require(paper.get("intake_should_stop") is True
                and paper.get("temporal_diversity_ready") is True
                and paper.get("qualifying_maturity_ready") is True,
                "paper completion gate bypasses diversity/mature outcomes")
        statuses.append(version + ":PAPER_ECONOMIC_REVIEW_DUE")
        notices.append(event("PAPER_FINAL_REVIEW", paper["series_id"],
                             version + " Readiness-View meldet reifes Abschlussgate; "
                             "Originaljournal und wirtschaftliche Ergebnisse abgleichen. "
                             "Keine automatische Strategie- oder Echtgeldfreigabe."))
    else:
        statuses.append(version + ":PAPER_COLLECTING_OR_NATIVE_ECONOMICS_NOT_EVALUATED")
    return {"kind": "PROJECT_MILESTONE_CONTROL_V1",
            "series_id": paper["series_id"],
            "live_technical_series_id": paper["series_id"],
            "strategy_revision": paper["strategy_revision"],
            "last_verified_release_source": milestone["source"],
            "readiness_view_counts": {k: paper[k] for k in ("candidate_outcomes", "completed_trades")},
            "host_health_verified": False, "native_journal_checked": False,
            "economic_qualification_verified": False,
            "statuses": statuses, "events": notices,
            "strategy_changed": False, "orders": False, "real_money_actions": False}


def evaluate(state: dict, paper: dict, h3: dict, now: dt.datetime, root: Path) -> dict:
    milestone = operational_release_snapshot(state, now)
    if milestone is not None:
        return evaluate_operational_paper(milestone, paper)
    active = state["active_strategy"]
    if str(active.get("strategy_revision") or "").startswith("V3-"):
        return evaluate_verified_v3_paper(state, paper, now, root)
    series = active["series_id"]
    # Supabase readiness follows the currently active technical series, while
    # project-current-state holds the ORIGINAL frozen H3/strategy epoch lineage.
    # Explicitly bind a verified technical successor; never silently accept a
    # foreign/released strategy or reset the economic review clock on rotation.
    live_series = paper.get("series_id")
    technical = active.get("technical_rotation_runtime_last_verified") or {}
    if live_series != series:
        require(live_series == technical.get("series_id")
                and technical.get("original_strategy_epoch_series_id") == series
                and technical.get("relation") ==
                    "TECHNICAL_ROTATION_SAME_STRATEGY_FINGERPRINT_NOT_STRATEGY_RELEASE"
                and technical.get("frozen_h3_baseline_changed") is False
                and technical.get("productivity_clock_reset") is False,
                "unapproved technical series rotation / strategy epoch drift")
    require(paper.get("strategy_revision") == active["strategy_revision"],
            "paper revision drift")
    require(paper.get("fasttrack_policy_version") == "EVIDENCE_DIVERSITY_FASTTRACK_V2",
            "unknown paper completion policy")
    require(paper.get("candidate_outcomes") is not None, "missing paper outcomes")
    require(paper.get("completed_trades") is not None, "missing trade counts")
    epoch_stamp = active.get("original_strategy_epoch_started_at_utc")
    require(epoch_stamp == "2026-10-07T18:42:55Z",
            "V2R4 original activation epoch missing or unexpectedly moved")
    epoch_start = iso_time(epoch_stamp)
    require(now >= epoch_start, "review clock before original strategy epoch")
    strategy_epoch_age_days = (now - epoch_start).total_seconds() / 86400.0
    # Single shared economic/lineage contract also enforced by control plane.
    aggregate=summarize_epoch(active,paper)
    epoch_min_outcomes=int(aggregate["epoch_minimum_candidate_outcomes"])
    epoch_min_trades=int(aggregate["epoch_minimum_completed_trades"])
    epoch_min_mature24=int(aggregate["epoch_minimum_complete_24h"])
    notices = []
    statuses = []
    # Generic fail-safe: a duly reached control gate must have a documented
    # Work receipt, not merely a GitHub notice or a chat promise.
    for decision_id, note in due_followthrough_events(state, now, root):
        statuses.append("FOLLOWTHROUGH:ACK_OVERDUE:" + decision_id)
        notices.append(note)
    for task in state.get("next_control_decisions") or []:
        if task["id"] not in SUPPORTED_DECISIONS:
            statuses.append("CONTROL:ADAPTER_REQUIRED:" + task["id"])
            notices.append(event("NEW_CONTROL_DECISION", task["id"],
                                 "Neue kanonische Projektentscheidung braucht ein "
                                 "versioniertes Gate/Read-only-Adapter. Keine stille "
                                 "Überspringung und keine ungeprüfte Aktivierung."))
    # A known, governance-only V3 followup; no new active trial or schedule.
    v3_next = next((task for task in state.get("next_control_decisions") or []
                    if task.get("id") == "V3-EXTENDED-SECOND-LEG-LEARNING-GATE"), None)
    if v3_next is not None:
        require(
            v3_next.get("canonical_owner") ==
            "research/v3-migration-ledger.json#late_chase_protection.successor_refinement",
            "V3 second-leg research decision must retain canonical migration owner")
        require(v3_next.get("no_new_work_run") is True
                and v3_next.get("no_active_strategy_change") is True,
                "V3 second-leg finding cannot initiate Work or alter active paper")
        statuses.append("V3:EXTENDED_SECOND_LEG_STAGED_FOR_NEXT_REVIEW_NO_AUTO_START")
    if paper.get("completion_ready") is True:
        require(paper.get("intake_should_stop") is True,
                "completion gate contradicts intake state")
        require(paper.get("temporal_diversity_ready") is True and
                paper.get("qualifying_maturity_ready") is True,
                "paper completion bypasses evidence maturity/diversity")
        statuses.append("V2R4:FINAL_REVIEW_READY")
        notices.append(event("PAPER_FINAL_REVIEW", series,
                             "Paper-Abschlussgate erreicht: finale Auswertung, "
                             "Erkenntnis-Migration und separate Release-Entscheidung vorbereiten. "
                             "KEINE automatische Strategieaktivierung. "
                             "Offenes V3-EXTENDED-Zweite-Welle-0-BUY-Finding "
                             "aus dem Migrationsledger zwingend disponieren: "
                             "erst Coin-Evidence-A, dann getrennt Review-B."))
    else:
        statuses.append("V2R4:COLLECTING")
        # The append-only archive preserves *all* closed segments' verified
        # mature evidence and the live segment's Supabase counters exactly once.
        # No technical rotation resets the strategic productivity clock.
        # This is an EARLY pathology review, never the 1000-outcome release gate.
        if (strategy_epoch_age_days >= 3
                and epoch_min_outcomes >= 100
                and epoch_min_mature24 >= 30
                and epoch_min_trades == 0):
            if control_review_acknowledged(
                    state, "V2R4-PRODUCTIVITY-REVIEW", now, root):
                # A true 0-BUY problem remains, but the reviewed same cohort
                # must not generate another GitHub comment/email.
                statuses.append("V2R4:LOW_TRADE_REVIEW_ACKNOWLEDGED_NO_REPEAT")
            else:
                statuses.append("V2R4:LOW_TRADE_REVIEW")
                notices.append(event("PAPER_LOW_TRADES", series,
                                 "72h-STRATEGIEEPOCHEN-FRÜHREVIEW (Uhr ab 07.10. "
                                 "20:42:55 MESZ; technische Serienrotation KEIN RESET): "
                                 "beide nachprüfbaren technischen Teilserien "
                                 "gemeinsam betrachten: alte abgeschlossene Serie "
                                 "1011 Outcomes, 260 vollständige 24h-Verläufe, "
                                 "0 Trades; aktuelle Serie liefert weitere "
                                 "tagesaktuelle Daten. Wirtschaftliche Null-BUY- "
                                 "Konversion ist ein zwingender REVIEW, nicht "
                                 "gleichbedeutend mit freigegebenem Abschluss. "
                                 "Funnel, WAIT/TTL, "
                                 "Missed-Moves, Kosten und Datenqualität analysieren. "
                                 "Aktive Serie unverändert lassen. "
                                 "Das V3-EXTENDED-Zweite-Welle-Finding mit "
                                 "separater Coin-Evidence-Stufe A und späterer "
                                 "Neubewertung-Stufe B im Review disponieren; "
                                 "MFE im Rückblick ist kein Handelsgewinn."))

    shadows = (state.get("strategy_changing_shadow_wip") or {}).get("active") or []
    if shadows:
        sh = shadows[0]
        if sh.get("candidate_id") != "V3-H3-SHADOW-001":
            statuses.append("SHADOW:ADAPTER_REQUIRED")
            notices.append(event("NEW_SHADOW_ADAPTER", sh.get("candidate_id") or "UNKNOWN",
                                 "Neue aktive Shadow-Version erkannt: separaten "
                                 "Evidence-/Review-Adapter hinzufügen und die "
                                 "Baseline-/Freeze-Gates prüfen. Keine Promotion."))
        else:
            require(h3 is not None, "H3 live evidence unavailable")
            require(h3.get("shadow_candidate_id") == sh["candidate_id"],
                    "H3 status candidate drift")
            p = h3.get("payload") or {}
            require(p.get("baseline_series_id") == series, "H3 baseline series drift")
            require(p.get("baseline_strategy_revision") == active["strategy_revision"],
                    "H3 baseline revision drift")
            for k in ("orders", "real_money_actions", "automatic_promotion",
                      "automatic_extension"):
                require(p.get(k) is False, "H3 safety invariant " + k)
            # Keep hard safety and baseline checks even when H3 is stale.
            # Stale H3 cannot signal FIXED_REVIEW_READY, but MUST NOT prevent
            # independent V2R4 economic productivity notices from completing.
            if iso_time(h3["generated_at"]) < now - dt.timedelta(hours=2):
                statuses.append("H3:EVIDENCE_STALE_FIXED_REVIEW_BLOCKED")
                notices.append(event("H3_STALE_EVIDENCE",
                                     sh["candidate_id"] + "|" + series,
                                     "H3-Shadow-Status veraltet: keine H3-Fixreview "
                                     "oder neue Strategie/zweiten Shadow freigeben. "
                                     "Eigenen H3-Datenpfad separat prüfen; "
                                     "V2R4-Trading-Produktivitätsreview bleibt "
                                     "unabhängig davon fällig. Keine Live-Änderung."))
            else:
                if p.get("minimum_gate_met") is True:
                    dates = p.get("distinct_utc_dates") or []
                    require(int(p.get("eligible_matched_candidates") or 0) >= 20
                            and len(set(dates)) >= 2
                            and float(p.get("capture_success_pct") or 0) >= 95,
                            "H3 claimed gate without preregistered sample/capture evidence")
                    require(p.get("intake_should_stop") is True,
                            "H3 gate reached but no stop state")
                    if p.get("outcome_review_ready") is True:
                        statuses.append("H3:FIXED_REVIEW_READY")
                        divergences = int(p.get("causal_decision_divergences") or 0)
                        recommendation = ("INCONCLUSIVE_LOW_IMPACT"
                                          if divergences < 3 else "FORMAL_REVIEW_REQUIRED")
                        notices.append(event("H3_FIXED_REVIEW",
                                             sh["candidate_id"] + "|" + series,
                                             "H3-Fixreview fällig: " + recommendation +
                                             "; Baseline-Replay, Kosten, Follow-ups und "
                                             "Preregistrierung überprüfen. H6 erst nach "
                                             "abgeschlossenem H3-Review / separatem Gate. "
                                             "Danach offenes EXTENDED-Zweite-Welle-Finding "
                                             "verbindlich prüfen: zuerst Kraken-Coin-Daten "
                                             "als einziger geänderter A-Input, danach "
                                             "separate B-Neubewertung nur mit Kosten/Stop "
                                             "und ohne automatische Promotion."))
                    else:
                        statuses.append("H3:WAIT_FOLLOWUPS")
                else:
                    statuses.append("H3:COLLECTING")
    else:
        archived = [x for x in (state.get("closed_or_rejected_tracks") or [])
                    if x.get("id") == "V3-H3-SHADOW-001"]
        if archived:
            require(len(archived)==1, "H3 archived more than once")
            h3_archive=archived[0]
            require(h3_archive.get("status")=="ARCHIVED_INCOMPLETE_NOT_FIXED_REVIEWED"
                    and h3_archive.get("fixed_review_completed") is False
                    and h3_archive.get("promotion_eligible") is False
                    and h3_archive.get("cloud_causal_evidence_rows_at_review")==0
                    and h3_archive.get("former_frozen_baseline_series_id")==series,
                    "H3 archive incorrectly claims full evidence or a passed fixed review")
            statuses.append("H3:ARCHIVED_INCOMPLETE_NO_FIXED_REVIEW")
            if h3_archive.get("archive_disposition")=="DEFER_WITH_GATE":
                statuses.append("H3:ARCHIVE_DISPOSITION_DEFER_WITH_GATE")
            else:
                notices.append(event("H3_ARCHIVED_INCOMPLETE_REVIEW",
                                     h3_archive["id"]+"|"+series,
                                     "H3-001 wurde beim technischen Cutover archiviert; "
                                     "0 prospektive Cloud-Schattenbelege. Die alte "
                                     "SHADOW_RUNNING-Angabe ist beendet. Kein H3-Fixed-"
                                     "Review bestanden, H6 bleibt bis zur gesonderten "
                                     "Archiv-/Kausalitätsentscheidung gesperrt. "
                                     "V2R4-Handelsbewertung läuft weiter."))
        else:
            statuses.append("H3:NO_ACTIVE_SHADOW")

    h10 = next((x for x in state.get("observational_research_tracks") or []
                if x.get("id") == "V3-H10-CAPTURE-001"), None)
    if h10 and "FIRST_REVIEW_COMPLETE_MORE_TESTING_REQUIRED" in h10.get("status", ""):
        contract = root / "research/v3/h10-kraken-outcome-context-join-contract-v1.json"
        if not contract.exists():
            statuses.append("H10:NEXT_CONTRACT_DUE")
            notices.append(event("H10_CONTRACT", h10["id"],
                                 "H10-Erstreview abgeschlossen. Vor neuer "
                                 "Outcome-Analyse PIT-Kraken-EUR-Join, fixes "
                                 "False-Positive-Label und Konfliktregel "
                                 "preregistrieren. Capture läuft unverändert weiter."))
        else:
            statuses.append("H10:CONTRACT_PRESENT_REVIEW_NEEDED")
    queued = (state.get("strategy_changing_shadow_wip") or {}).get("queued") or []
    if any(x.get("candidate_id")=="V3-H6-NEXT" for x in queued):
        if any(x.get("status")=="WAIT_FOR_H3_ARCHIVED_INCOMPLETE_EXPLICIT_DISPOSITION"
               for x in queued if x.get("candidate_id")=="V3-H6-NEXT"):
            statuses.append("H6:BLOCKED_H3_ARCHIVED_INCOMPLETE_NO_AUTO_START")
        elif any(x.get("status")=="WAIT_FOR_V2R4_ECONOMIC_REVIEW_AND_SEPARATE_EXPLICIT_APPROVAL"
                 for x in queued if x.get("candidate_id")=="V3-H6-NEXT"):
            statuses.append("H6:BLOCKED_V2R4_REVIEW_AND_EXPLICIT_APPROVAL_NO_AUTO_START")
        else:
            statuses.append("H6:WAIT_H3_REVIEW_NO_AUTO_START")
    return {"kind": "PROJECT_MILESTONE_CONTROL_V1", "series_id": series,
            "live_technical_series_id": live_series,
            "epoch_minimum_candidate_outcomes": epoch_min_outcomes,
            "epoch_minimum_completed_trades": epoch_min_trades,
            "epoch_minimum_complete_24h": epoch_min_mature24,
            "epoch_combines_verified_technical_segments": live_series!=series,
            "strategy_epoch_started_at_utc": epoch_stamp,
            "strategy_epoch_age_days": round(strategy_epoch_age_days, 4),
            "statuses": statuses, "events": notices,
            "strategy_changed": False, "orders": False,
            "real_money_actions": False}



def control_review_acknowledged(state: dict, decision_id: str,
                                now: dt.datetime, root: Path) -> bool:
    """A real dated Work receipt closes this *review*, never the Paper series.

    A completed economic 72h review must not create a new GitHub comment/email
    at the next schedule; 0-BUY remains an economic status and successor blocker.
    Unlike the overdue check, this receipt check works within the 24h grace.
    """
    task = next((d for d in state.get("next_control_decisions") or []
                 if d.get("id") == decision_id), None)
    if task is None:
        return False
    due, ack_key = task.get("due_at_utc"), task.get("followthrough_ack_key")
    if not isinstance(due, str) or not isinstance(ack_key, str):
        return False
    try:
        due_time = iso_time(due)
        raw = json.loads((root / "research/work-analysis-state.json").read_text("utf-8"))
        receipt = (((raw.get("acknowledgements") or {}).get("control_decision_reviews")
                    or {}).get(ack_key) or {})
        if not isinstance(receipt, dict) or receipt.get("status") not in {
                "COMPLETED", "DECISION_PACKET_READY"}:
            return False
        report, stamp = receipt.get("report"), receipt.get("completed_at_utc")
        if not isinstance(report, str) or not re.fullmatch(
                r"research/work-analysis/[A-Za-z0-9_.-]+[.]md", report):
            return False
        if not isinstance(stamp, str) or not (root / report).is_file():
            return False
        return due_time <= iso_time(stamp) <= now
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return False


def due_followthrough_events(state: dict, now: dt.datetime, root: Path) -> list:
    """Independent of Supabase liveness: overdue work receipts still escalate."""
    return [(decision_id, event(
        "CONTROL_FOLLOWTHROUGH_MISSED", ack_key,
        "Autonomie-Übergabe überfällig: " + decision_id +
        ". Trotz abgelaufenem Gate und Nachfrist fehlt ein belegter "
        "Work-Abschluss/Entscheidungsbeleg. Bestehenden 10:15-Work-Pfad "
        "gezielt reparieren oder konkreten Nutzer-Blocker melden; "
        "kein zweiter Work-Lauf, keine automatische Strategieänderung."))
        for decision_id, ack_key in unacknowledged_control_decisions(state, now, root)]


def unacknowledged_control_decisions(state: dict, now: dt.datetime, root: Path) -> list:
    """Detect silent due-gate handoff failures without modifying any runtime."""
    path = root / "research/work-analysis-state.json"
    try:
        work = json.loads(path.read_text("utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        work = {}
    reviews = ((work.get("acknowledgements") or {}).get("control_decision_reviews") or {})
    unacknowledged = []
    for decision in state.get("next_control_decisions") or []:
        due = decision.get("due_at_utc")
        ack_key = decision.get("followthrough_ack_key")
        lag = decision.get("followthrough_max_lag_hours")
        if due is None and ack_key is None and lag is None:
            continue
        require(isinstance(due, str) and isinstance(ack_key, str)
                and re.fullmatch(r"[A-Za-z0-9_.-]{5,120}", ack_key) is not None
                and type(lag) is int and 1 <= lag <= 168,
                "invalid followthrough contract")
        due_time = iso_time(due)
        if now < due_time + dt.timedelta(hours=lag):
            continue
        record = reviews.get(ack_key)
        if isinstance(record, dict) and record.get("status") in {
                "COMPLETED", "DECISION_PACKET_READY", "BLOCKED_WITH_ACTION"}:
            report = record.get("report")
            completed = record.get("completed_at_utc")
            if (isinstance(report, str)
                    and re.fullmatch(r"research/work-analysis/[A-Za-z0-9_.-]+[.]md", report)
                    and isinstance(completed, str) and (root / report).is_file()):
                try:
                    completed_time = iso_time(completed)
                    if due_time <= completed_time <= now:
                        continue
                except (ValueError, TypeError):
                    pass  # Invalid evidence is missing evidence, not a controller crash.
        unacknowledged.append((decision["id"], ack_key))
    return unacknowledged

def gh_request(url: str, token: str, method: str = "GET", payload=None):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "project-milestone-controller/1",
        **({"Content-Type": "application/json"} if payload is not None else {}),
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def publish_once(repo: str, token: str, note: dict, slack: str) -> str:
    require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) is not None,
            "invalid GitHub repository")
    require(repo == "hoffmannherdecke/kraken-eur-scanner", "unexpected repository")
    endpoint = "https://api.github.com/repos/" + repo + "/issues/" + str(note["issue"]) + "/comments"
    marker = "<!-- " + note["event_key"] + " -->"
    page = 1
    while True:
        comments = gh_request(endpoint + "?per_page=100&page=" + str(page), token)
        require(isinstance(comments, list), "GitHub comment list invalid")
        for comment in comments:
            if (marker in str(comment.get("body") or "") and
                    (comment.get("user") or {}).get("login") == "github-actions[bot]"):
                return "ALREADY_RECORDED"
        if len(comments) < 100:
            break
        page += 1
        require(page <= 20, "unbounded GitHub comment history")
    message = "Projekt-Controlling: " + note["detail"] + "\n\n" + marker
    # GitHub comment is the durable, deduplicated milestone receipt.
    gh_request(endpoint, token, "POST", {"body": message})
    if slack:
        req = urllib.request.Request(slack, data=json.dumps({
            "text": "PROJEKT-MEILENSTEIN: " + note["detail"] +
                    "\nGitHub Issue #" + str(note["issue"])
        }).encode("utf-8"), method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            require(200 <= resp.status < 300, "Slack notification rejected")
    return "CREATED"



def registered_commitment_milestone(state:dict,now:dt.datetime,root:Path,operational_evidence=None)->tuple[list[str],list[dict]]:
    """One bounded evidence-only grouped notice; Work stays the sole executor."""
    ack_path=root/"research/work-analysis-state.json"
    ack=json.loads(ack_path.read_text("utf-8")) if ack_path.is_file() else {}
    report=project_implementation_commitments(root,state,ack,now,operational_evidence)
    waiting=report["ready_release_reviews"]
    safe=report["ready_safe_actions"]
    statuses=["PROJECT:REGISTERED_IMPLEMENTATION_OPEN:"+str(report["open_count"])]
    if waiting:
        statuses.append("PROJECT:IMPLEMENTATION_REVIEW_REQUIRES_USER_GATE")
    notices=[]
    if waiting or safe:
        # Fixed anchor for each materially distinct list of ready items.
        membership="|".join(sorted(x["id"] for x in waiting+safe))
        if operational_evidence is not None:
            membership=operational_evidence["series_id"]+"|"+"|".join(sorted(x["gate_fingerprint"] for x in waiting+safe))
        anchor="COMMITMENT-GROUP-"+hashlib.sha256(membership.encode("utf-8")).hexdigest()[:24]
        details=", ".join(x["id"] for x in waiting+safe)
        notices.append(event("PROJECT_IMPLEMENTATION_COMMITMENT_REVIEW",
                             anchor,
            "Projektweiter Umsetzungsgate fällig: "+details+
            ". Bestehender 10:15-Work-Owner prüft das reale Quellen-/Host-Gate, "
            "bearbeitet höchstens zwei reversible sichere Arbeitspakete gleichzeitig; "
            "nach belegtem Abschluss kann im selben regulären Lauf weitere "
            "fällige sichere Arbeit nachrücken. Nicht ausführbare "
            "Release-/Budget-Entscheidungen bleiben sichtbar OFFEN. "
            "Nicht als erledigt zählen ohne Original-/Consumer-Beleg; "
            "keine automatischen Paper-/H3-/H6-/Echtgeld-Änderungen."))
    # Distinct immutable incident owner: alert the ORIGINAL #99 thread once
    # after the protected Canary clock, even when V3 work has filled both
    # daily implementation slots. This reminder is NOT an executor.
    incident_id="V2R4_WAIT_INCIDENT_PHYSICAL_FOLLOWTHROUGH"
    incident=next((x for x in report["items"] if x["id"]==incident_id),None)
    if incident and incident["state"] in (
            "READY_SAFE_IMPLEMENTATION","READY_REVIEW_RELEASE_GATED"):
        statuses.append("PROJECT:V2R4_WAIT_PHYSICAL_FOLLOWTHROUGH_OPEN")
        notices.append(event("V2R4_WAIT_INCIDENT_FOLLOWTHROUGH_DUE",
                             incident_id,
            "Offenes eigenständiges V2R4-WAIT-Folgegate Issue #99: vor "
            "neuer Quellprüfung den aktuellen Original-PR326-Work-ACK "
            "und die realen Mini-PC-/Cloud-Belege abgleichen. Schon "
            "abgeschlossene PR326-Quellarbeit nicht erneut vergeben; "
            "nur tatsächlich fehlende Kraken-, WAIT-, Supervisor-, "
            "Rollback-/Single-Writer- und Cloud-Consumer-Gates prüfen. "
            "Keine neue Runtime ohne getrennte Benutzerfreigabe, "
            "kein bloßes CI/Heartbeat/Work-ACK als physischer Abschluss."))
    return statuses,notices


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path,
                        help="JSON fixture with paper and h3 rows; disables all writes")
    parser.add_argument("--publish", action="store_true",
                        help="explicitly post once-per-milestone notifications")
    args = parser.parse_args()
    require(not (args.fixture and args.publish), "fixture cannot publish")
    state = load_local_state(ROOT)
    milestone = None
    operational_evidence = None
    if args.fixture:
        fixture = json.loads(args.fixture.read_text("utf-8"))
        paper, h3 = fixture["paper"], fixture["h3"]
        now = iso_time(fixture["now"])
    else:
        base = os.environ.get("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        require(bool(key), "missing Supabase evidence credential")
        now = dt.datetime.now(UTC)
        milestone = operational_release_snapshot(state, now)
        try:
            if milestone is not None:
                state,paper,operational_evidence=read_operational_evidence(
                    state,base,key,now,os.getenv("GITHUB_SHA") or None)
                milestone=operational_release_snapshot(state,now)
            else:
                paper = current_active_paper_readiness(base, key)
            shadows = (state.get("strategy_changing_shadow_wip") or {}).get("active") or []
            h3 = (get_rows(base, key, "v3_h3_shadow_status")[0]
                  if milestone is None and shadows and shadows[0].get("candidate_id") == "V3-H3-SHADOW-001"
                  else None)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            # Critical control-plane independence: Supabase downtime must not
            # suppress an already-overdue, locally evidenced Work handoff.
            # Never invent trading readiness or claim HEALTHY in degraded mode.
            now = dt.datetime.now(UTC)
            overdue = [] if milestone is not None else due_followthrough_events(state, now, ROOT)
            print(json.dumps({"kind": "PROJECT_MILESTONE_CONTROL_DEGRADED_V1",
                              "status": "SUPABASE_EVIDENCE_UNAVAILABLE",
                              "overdue_followthrough_only": [decision for decision, _ in overdue],
                              "strategy_changed": False, "orders": False,
                              "real_money_actions": False}, sort_keys=True))
            if args.publish:
                token, repo = os.environ.get("GITHUB_TOKEN", ""), os.environ.get("GITHUB_REPOSITORY", "")
                if overdue:
                    require(bool(token), "missing GitHub token for overdue fallback")
                for _, note in overdue:
                    publish_once(repo, token, note, os.getenv("SLACK_WEBHOOK_URL", ""))
            print("MILESTONE_CONTROL_BLOCKED Supabase read-only evidence unavailable: " +
                  str(exc), file=sys.stderr)
            return 2
        now = dt.datetime.now(UTC)
    result = evaluate(state, paper, h3, now, ROOT)
    # General commitments use the same existing daily GitHub watcher.
    # It only reports/alerts and never mutates strategy or source systems.
    if operational_evidence is not None:
        result["current_operational_evidence"]=operational_evidence
        result["native_journal_checked"]=operational_evidence["journal"]["native_journal_checked"]
        result["statuses"].append(operational_evidence["journal"]["status"])
        result["statuses"].append(operational_evidence["host"]["status"])
        if operational_evidence["host"]["status"]!="HOST_REPORT_V3_MATCH_NOT_INDEPENDENT_PROOF":
            result["events"].append(event("PAPER_NATIVE_HEALTH_REVIEW",paper["series_id"],
                "Aktuelle Host-Relay-Evidenz belegt den Paper-Writer nicht; gezielt Originalheartbeat/Task prüfen. Kein Neustart oder erneuter Release."))
        recorded_expiry = operational_evidence["lease_expires_at_utc"]
        expiry = iso_time(recorded_expiry) if recorded_expiry is not None else None
        if expiry is not None and expiry-now <= dt.timedelta(hours=72):
            result["statuses"].append("PAPER:LAST_RECORDED_LEASE_REVIEW_DUE")
            result["events"].append(event("PAPER_RUNTIME_LEASE_REVIEW",paper["series_id"]+"|"+expiry.isoformat(),
                "Zuletzt belegte Lease endet "+expiry.isoformat()+". Aktuellen Originalhost/CMS-Vertrag prüfen und persönliche Verlängerungsfreigabe rechtzeitig vorbereiten. Keine automatische Verlängerung."))
    extra_status,extra_events=registered_commitment_milestone(state,now,ROOT,operational_evidence)
    result["statuses"].extend(extra_status)
    result["events"].extend(extra_events)
    # Reuse the EXISTING scheduled controller for the first qualified H10
    # source receipt. Optional source failure never blocks Paper control.
    if not args.fixture:
        proof = ((state.get("pending_strategy_transition") or {})
                 .get("v3_original_intake_e2e_gate") or {})
        if milestone is None and proof.get("h10_pit_receipt_schema_applied") is True:
            try:
                status, milestone = first_h10_source_receipt_review(base,key)
                result["statuses"].append(status)
                if milestone:
                    result["events"].append(milestone)
            except (OSError,ValueError,KeyError,TypeError) as exc:
                result["statuses"].append("H10:SOURCE_RECEIPT_CHECK_NEEDS_REVIEW")
                # Single deduplicated integrity review, never source BUY.
                if not isinstance(exc,OSError):
                    result["events"].append(event(
                        "H10_SOURCE_RECEIPT_INTEGRITY",
                        "H10-ORIGINAL-RECEIPT-INTEGRITY",
                        "H10-Quittungs-Integritätsprüfung meldet fehlgeschlagene "
                        "Validierung. Separat prüfen; keine Quelle aktivieren."))
                print("H10_SOURCE_RECEIPT_REVIEW_REQUIRED "+type(exc).__name__,
                      file=sys.stderr)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as out:
            out.write("## Autonomous milestone control\n\n")
            for status in result["statuses"]:
                out.write("- " + status + "\n")
            out.write("\nUpcoming notifications: " + str(len(result["events"])) + "\n")
    if args.publish:
        token, repo = os.environ.get("GITHUB_TOKEN", ""), os.environ.get("GITHUB_REPOSITORY", "")
        require(bool(token), "missing GitHub issue token")
        for note in result["events"]:
            status = publish_once(repo, token, note, os.getenv("SLACK_WEBHOOK_URL", ""))
            print("MILESTONE " + note["kind"] + ": " + status)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print("MILESTONE_CONTROL_BLOCKED " + str(exc), file=sys.stderr)
        sys.exit(2)
