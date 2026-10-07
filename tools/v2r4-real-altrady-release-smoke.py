#!/usr/bin/env python3
"""Prepare/verify an isolated V2R4 release smoke using a real Altrady transport event.

The real event is used only as a wake-up hint. Kraken public data remains the
condition truth. All candidate/decision/recheck state is created under an
isolated temporary directory; no active paper series is mutated.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


def canon(value: object) -> str:
    return "".join(ch for ch in str(value).upper() if ch.isalnum())


def utc(value: object) -> datetime:
    dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)


def read_latest_real_event(path: Path, max_age_minutes: float) -> tuple[dict,datetime,float]:
    rows=[]
    for line in path.read_text("utf-8",errors="replace").splitlines():
        try:
            obj=json.loads(line)
        except Exception:
            continue
        if not isinstance(obj,dict):
            continue
        event=obj.get("event")
        if not isinstance(event,dict) or not event.get("symbol"):
            continue
        stamp=(
            obj.get("received_by_minipc_at_utc")
            or obj.get("received_at_utc")
            or event.get("received_at_utc")
        )
        if not stamp:
            continue
        try:
            when=utc(stamp)
        except Exception:
            continue
        rows.append((when,obj))
    if not rows:
        raise SystemExit("no real Altrady event with symbol/timestamp found")
    when,obj=max(rows,key=lambda x:x[0])
    age=(datetime.now(timezone.utc)-when).total_seconds()/60.0
    if age < -1 or age > max_age_minutes:
        raise SystemExit(
            f"latest real Altrady event too old/future: age_minutes={age:.3f}, "
            f"max={max_age_minutes}"
        )
    return obj,when,age


def get_json(url: str, agent: str) -> dict:
    req=urllib.request.Request(url,headers={"User-Agent":agent})
    with urllib.request.urlopen(req,timeout=20) as resp:
        obj=json.loads(resp.read().decode())
    if obj.get("error"):
        raise RuntimeError(obj["error"])
    return obj


def map_symbol(symbol: str) -> tuple[str,str,str]:
    pairs=get_json(
        "https://api.kraken.com/0/public/AssetPairs",
        "minipc-v2r4-real-altrady-release-smoke/1.0",
    )["result"]
    target=canon(symbol)
    for key,meta in pairs.items():
        if meta.get("status")!="online":
            continue
        ws=str(meta.get("wsname") or "")
        alt=str(meta.get("altname") or key)
        if target in {canon(key),canon(alt),canon(ws)}:
            if not ws.endswith("/EUR"):
                raise SystemExit(
                    f"real Altrady event maps to non-EUR Kraken pair: {symbol} -> {ws}"
                )
            return key,alt,ws
    raise SystemExit(f"real Altrady symbol not mapped to an online Kraken pair: {symbol}")


def prepare(args: argparse.Namespace) -> int:
    row,received_at,age=read_latest_real_event(args.real_log,args.max_age_minutes)
    event=row["event"]
    key,alt,pair=map_symbol(str(event["symbol"]))
    ticker=get_json(
        "https://api.kraken.com/0/public/Ticker?pair="+alt,
        "minipc-v2r4-real-altrady-release-smoke/1.0",
    )["result"]
    trow=next(iter(ticker.values()))
    price=float(trow["c"][0])

    sys.path.insert(0,str(args.code_root))
    from paper_evaluator.evaluate import validate_candidate
    from paper_evaluator.v2r4_trigger_plan import build_wait_trigger_plan

    root=args.root
    for name in ("decisions","candidates","rechecks","receipts","state","logs"):
        (root/name).mkdir(parents=True,exist_ok=True)

    now=datetime.now(timezone.utc)
    ts=int(now.timestamp())
    tag=pair.replace("/","-")
    source_run_id=0
    cid=f"{now.strftime('%Y%m%d-%H%M%S')}-{tag}-r{source_run_id}"

    candidate={
        "schema_version":1,
        "kind":"CANONICAL_CANDIDATE_HANDOFF_V1",
        "candidate_id":cid,
        "queue_id":f"{source_run_id}:{tag}:{ts}",
        "source_scanner_run_id":source_run_id,
        "event_time_utc":now.isoformat().replace("+00:00","Z"),
        "event_ts":ts,
        "pair":pair,
        "altname":alt,
        "action":"REVIEW_ONLY_NOT_ORDER",
        "scanner_candidate":{
            "pair":pair,"altname":alt,"price":price,"score":8.0,
            "ret15_live":0.0,"ret1h":0.0,"ret3h":0.0,"ret24h":0.0,
            "volume_ratio_closed":1.0,"volume_ratio_live":1.0,
            "late":False,"fresh_move_3h":0.0,"spread_pct":0.1,
            "turnover24h":1000000000.0,
        },
        "scanner_market_context":{
            "schema_version":1,
            "pair":pair,
            "altname":alt,
            "sensor_price_eur":price,
            "source":"isolated_release_smoke_from_real_altrady_transport",
        },
        "scanner_market_breadth":{"positive_1h_count":1,"positive_3h_count":1},
        "timing":{
            "candidate_detected_at_utc":now.isoformat().replace("+00:00","Z"),
            "candidate_detected_ts":ts,
            "candidate_snapshot_at_utc":now.isoformat().replace("+00:00","Z"),
            "handoff_written_at_utc":now.isoformat().replace("+00:00","Z"),
            "scan_step_started_at_utc":now.isoformat().replace("+00:00","Z"),
        },
    }

    candidate_file=root/"candidates"/f"{cid}.json"
    validate_candidate(candidate,candidate_file)

    decision={
        "decision":"WAIT",
        "ttl_minutes":10,
        "watch_conditions":[{"metric":"spread_pct","op":"<=","value":100.0}],
    }
    plan=build_wait_trigger_plan(candidate,decision,now)

    candidate_file.write_text(
        json.dumps(candidate,indent=2,sort_keys=True)+"\n","utf-8"
    )
    (root/"decisions"/f"{cid}.json").write_text(
        json.dumps({"v2r4_trigger_plan":plan},indent=2,sort_keys=True)+"\n","utf-8"
    )
    (root/"logs"/"altrady-trigger-events.jsonl").write_text(
        json.dumps(row,separators=(",",":"),sort_keys=True)+"\n","utf-8"
    )
    control={
        "enabled":True,
        "test_id":"V2R4-REAL-ALTRADY-RELEASE-SMOKE",
        "series_id":"PAPER-V2R4-REAL-ALTRADY-RELEASE-SMOKE",
        "strategy_revision":"V2R4-PROPOSED-2026-09-30-PRECANDIDATE",
        "series_started_at_utc":(now-timedelta(minutes=2)).isoformat().replace("+00:00","Z"),
        "target_completed_paper_trades":1,
        "real_money_actions_enabled":False,
    }
    (root/"control.json").write_text(
        json.dumps(control,indent=2,sort_keys=True)+"\n","utf-8"
    )

    print(json.dumps({
        "status":"PREPARED",
        "candidate_id":cid,
        "pair":pair,
        "altname":alt,
        "kraken_pair_key":key,
        "price":price,
        "real_event_id":event.get("id"),
        "real_event_symbol":event.get("symbol"),
        "real_event_received_at_utc":received_at.isoformat().replace("+00:00","Z"),
        "real_event_age_minutes":round(age,3),
    },sort_keys=True))
    return 0


def verify(args: argparse.Namespace) -> int:
    root=args.root
    heartbeat=json.loads((root/"state"/"wait-runtime-heartbeat.json").read_text("utf-8"))
    state=json.loads((root/"state"/"wait-runtime-state.json").read_text("utf-8"))
    assert heartbeat["status"]=="HEALTHY",heartbeat
    assert heartbeat["paper_only"] is True
    assert heartbeat["kraken_public_is_condition_truth"] is True
    assert heartbeat["altrady_role"]=="WAKEUP_HINT_ONLY"
    assert heartbeat["order_api"] is False
    assert heartbeat["real_money_actions"] is False
    counters=heartbeat["counters"]
    assert counters["altrady_records_seen"]==1,counters
    assert counters["altrady_wakeup_checks"]==1,counters
    assert counters["condition_matches"]==1,counters
    assert counters["fresh_rechecks"]==1,counters
    assert counters["fresh_recheck_failures"]==0,counters
    handled=list(state["handled"].values())
    assert len(handled)==1 and handled[0]["status"]=="FRESH_PAPER_RECHECK_COMPLETE",handled
    receipts=glob.glob(str(root/"receipts"/"*.json"))
    rechecks=glob.glob(str(root/"rechecks"/"*.json"))
    assert len(receipts)==1 and len(rechecks)==1,(receipts,rechecks)
    record=json.loads(Path(rechecks[0]).read_text("utf-8"))
    assert record["paper_only"] is True
    assert record["real_money_actions_enabled"] is False
    assert record["order_api"] is False
    t0=utc(record["trigger_observed_at_utc"])
    t1=utc(record["recheck_started_at_utc"])
    delay=(t1-t0).total_seconds()
    assert 0 <= delay <= 20,delay
    print(json.dumps({
        "status":"PASS",
        "decision":record["decision"]["decision"],
        "trigger_to_recheck_start_s":round(delay,3),
        "paper_only":True,
        "order_api":False,
        "real_money_actions":False,
    },sort_keys=True))
    return 0


def verify_idempotent(args: argparse.Namespace) -> int:
    root=args.root
    heartbeat=json.loads((root/"state"/"wait-runtime-heartbeat.json").read_text("utf-8"))
    assert heartbeat["counters"]["fresh_rechecks"]==0,heartbeat
    assert len(glob.glob(str(root/"rechecks"/"*.json")))==1
    assert len(glob.glob(str(root/"receipts"/"*.json")))==1
    print("IDEMPOTENT_PASS")
    return 0


def main() -> int:
    ap=argparse.ArgumentParser()
    sub=ap.add_subparsers(dest="command",required=True)

    p=sub.add_parser("prepare")
    p.add_argument("--real-log",type=Path,required=True)
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--code-root",type=Path,required=True)
    p.add_argument("--max-age-minutes",type=float,default=30.0)
    p.set_defaults(func=prepare)

    v=sub.add_parser("verify")
    v.add_argument("--root",type=Path,required=True)
    v.set_defaults(func=verify)

    i=sub.add_parser("verify-idempotent")
    i.add_argument("--root",type=Path,required=True)
    i.set_defaults(func=verify_idempotent)

    args=ap.parse_args()
    return args.func(args)


if __name__=="__main__":
    raise SystemExit(main())
