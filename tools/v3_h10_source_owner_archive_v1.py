#!/usr/bin/env python3
"""Selective original-evidence archival INSIDE the already scheduled H10 source owner.

No independent scheduler, no source discovery, no keys on MINI-PC, no strategy
or order routing. Called only after the existing full 26-wallet cloud capture.
A real ACK requires a successful server INSERT followed by exact SELECT readback.
"""
from __future__ import annotations
import datetime as dt
import json
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict

from tools.v3_h10_selected_original_receipt_v1 import (
    OriginalEvidenceBlocked, build_selected_window_receipt, insist, iso, utc
)
from tools.v3_h10_selected_original_cloud_protocol_v1 import (
    prepare_source_only_insert, verify_persisted_readback
)

TABLE="v3_h10_selected_source_receipts"
SOURCE_CUTOFF=utc("2026-10-12T13:30:00Z")  # strictly prospective after PR240
MAX_SOURCE_ROWS=5000
PAGE_SIZE=500


def get_rows(base: str, headers: dict, table: str,
             filters: dict, *, max_rows: int=MAX_SOURCE_ROWS) -> list[dict]:
    """Explicitly paginate: never treat PostgREST's default row limit as a full population."""
    results=[]
    params=urllib.parse.urlencode(filters)
    for start in range(0, max_rows+1, PAGE_SIZE):
        h=dict(headers)
        h["Range-Unit"]="items"
        h["Range"]=f"{start}-{start+PAGE_SIZE-1}"
        url=base.rstrip("/")+"/rest/v1/"+table+"?"+params
        req=urllib.request.Request(url,headers=h,method="GET")
        with urllib.request.urlopen(req,timeout=45) as response:
            page=json.loads(response.read().decode("utf-8"))
        insist(isinstance(page,list), "INVALID_SOURCE_REST_RESULT")
        results.extend(page)
        insist(len(results)<=max_rows, "SOURCE_POPULATION_EXCEEDS_SAFE_CAP")
        if len(page)<PAGE_SIZE:
            return results
    raise OriginalEvidenceBlocked("SOURCE_PAGINATION_LIMIT_UNPROVEN")


def first_complete_known_at(batches: list[dict], events: list[dict],
                            start: dt.datetime, end: dt.datetime) -> dt.datetime:
    """Earliest successful 26-wallet union proving source window coverage."""
    candidates=[]
    for b in batches:
        if (b.get("capture_path")!="GITHUB_BOOTSTRAP_30M"
            or b.get("wallet_count")!=26 or b.get("success_count")!=26
            or b.get("error_count")!=0):
            continue
        ob=utc(b["observed_at"])
        left,right=max(start,ob-dt.timedelta(minutes=45)),min(end,ob)
        if left<right:
            candidates.append((left,right,b))
    cursor=start
    needed=[]
    for left,right,b in sorted(candidates,key=lambda x:(x[0],x[1],x[2]["batch_id"])):
        if left>cursor:
            break
        if right>cursor:
            cursor=right
            needed.append(b)
    insist(cursor>=end, "NO_COMPLETE_ORIGINAL_WINDOW_COVERAGE")
    return max([end]+[utc(b["created_at"]) for b in needed]
               +[utc(e["first_seen_at"]) for e in events])


def archive_selected_recent_windows(*, base: str, headers: dict,
                                    cohort: dict, observed_now: dt.datetime) -> dict:
    """Two completed windows for bounded retry; never fetch the past 08 October samples."""
    now=observed_now.astimezone(dt.timezone.utc)
    closed=now.replace(minute=(now.minute//30)*30,second=0,microsecond=0)
    tally={"candidate_windows":0,"stored":0,"idempotent":0,"insufficient_wallets":0}
    for ordinal in (2,1):  # one retry window plus the newly closed 30m window
        start=closed-dt.timedelta(minutes=30*ordinal)
        if start<SOURCE_CUTOFF:
            continue
        end=start+dt.timedelta(minutes=30)
        if now>end+dt.timedelta(hours=47,minutes=25):
            raise OriginalEvidenceBlocked("RAW_48H_FIRST_FILL_WINDOW_EXPIRING")
        fills=get_rows(base,headers,"v3_h10_fill_events",{
            "select":"event_id,cohort_id,cohort_role,address,coin,fill_time,first_seen_at,first_seen_batch_id,tx_hash,oid,tid,direction,side,px,sz",
            "and":f"(fill_time.gte.{iso(start)},fill_time.lt.{iso(end)})",
            "order":"event_id.asc"
        })
        grouped=defaultdict(list)
        for item in fills:
            insist(isinstance(item,dict) and item.get("coin") and item.get("cohort_role"),
                   "SOURCE_COIN_ROLE_MISSING")
            grouped[(item["coin"],item["cohort_role"])].append(item)
        eligible={(coin,role):items for (coin,role),items in grouped.items()
                  if len({x["address"] for x in items})>=3}
        if not eligible:
            tally["insufficient_wallets"]+=len(grouped)
            continue
        batches=get_rows(base,headers,"v3_h10_capture_batches",{
            "select":"batch_id,cohort_id,capture_path,observed_at,created_at,wallet_count,success_count,error_count",
            "and":f"(observed_at.gte.{iso(start)},observed_at.lte.{iso(now)})",
            "order":"observed_at.asc"
        },max_rows=1000)
        for coin,role in sorted(eligible):
            items=eligible[(coin,role)]
            insist(len(items)<=128,"EVENT_CAP_NO_SILENT_TRUNCATION")
            asof=first_complete_known_at(batches,items,start,end)
            insist(asof<=now,"SOURCE_FUTURE_ASOF")
            prior=[b for b in batches if utc(b["created_at"])<=asof]
            proof=build_selected_window_receipt(
                cohort=cohort,batch_rows=prior,fill_rows=items,coin=coin,role=role,
                window_start_utc=iso(start),evaluated_at_utc=iso(asof)
            )
            insist(proof["status"]=="SELECTED_INACTIVE_OFFLINE_NOT_PERSISTED",
                   "UNEXPECTED_UNSELECTED_RECEIPT")
            candidate=prepare_source_only_insert(proof)
            tally["candidate_windows"]+=1
            existing=get_rows(base,headers,TABLE,{
                "select":"candidate_id,cohort_id,cohort_role,coin,window_start_utc,evaluated_at_utc,content_sha256,original_payload_canonical,received_at_utc",
                "candidate_id":"eq."+candidate["candidate_id"]
            },max_rows=5)
            insist(len(existing)<=1,"DUPLICATE_EXISTING_ID")
            if existing:
                verify_persisted_readback(proof,existing[0])
                tally["idempotent"]+=1
                continue
            url=base.rstrip("/")+"/rest/v1/"+TABLE
            req=urllib.request.Request(url,
                data=json.dumps(candidate,separators=(",",":")).encode("utf-8"),
                headers={**headers,"Content-Type":"application/json","Prefer":"return=minimal"},
                method="POST")
            try:
                with urllib.request.urlopen(req,timeout=45) as response:
                    insist(response.status in (200,201,204),"ORIGINAL_RECEIPT_INSERT_REJECTED")
            except urllib.error.HTTPError as exc:
                if exc.code!=409:
                    raise
                # Competing identical insertion only counts after exact readback.
            verified=get_rows(base,headers,TABLE,{
                "select":"candidate_id,cohort_id,cohort_role,coin,window_start_utc,evaluated_at_utc,content_sha256,original_payload_canonical,received_at_utc",
                "candidate_id":"eq."+candidate["candidate_id"]
            },max_rows=5)
            insist(len(verified)==1,"MISSING_POST_INSERT_CLOUD_ACK")
            verify_persisted_readback(proof,verified[0])
            tally["stored"]+=1
            # Only the actual existing source-owner readback can state this.
            print("H10_LIVE_ORIGINAL_SOURCE_RECEIPT_ACK_VERIFIED",
                  coin,role,iso(start),candidate["candidate_id"][:12])
    return tally
