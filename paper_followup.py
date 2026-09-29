#!/usr/bin/env python3
"""Compact missed-move follow-up plus post-detection opportunity audit for the active paper series."""
from __future__ import annotations
import json, math, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
HORIZONS=[30,60,120,360]
INTERVAL=1
OPPORTUNITY_HORIZONS={15:1,60:1,240:1,720:5,1440:5}

def zdt(s):
    return datetime.fromisoformat(str(s).replace("Z","+00:00"))

def zisots(ts):
    return datetime.fromtimestamp(float(ts),timezone.utc).isoformat().replace("+00:00","Z")

def pct(x,b):
    return (x/b-1.0)*100.0

def get_ohlc(pair,since,interval=INTERVAL):
    q=urllib.parse.urlencode({"pair":pair,"interval":interval,"since":int(since)})
    req=urllib.request.Request("https://api.kraken.com/0/public/OHLC?"+q,headers={"User-Agent":"paper-followup/3.0"})
    with urllib.request.urlopen(req,timeout=25) as r:
        d=json.loads(r.read().decode())
    if d.get("error"):
        raise RuntimeError(repr(d["error"]))
    rows=next(v for k,v in d["result"].items() if k!="last")
    now=time.time()
    bar_seconds=int(interval)*60
    return [
        {"start":int(x[0]),"high":float(x[2]),"low":float(x[3]),"close":float(x[4])}
        for x in rows if int(x[0])+bar_seconds<=now
    ]

def complete_window(rows,at,horizon_minutes,interval_minutes):
    bar_seconds=int(interval_minutes)*60
    first=math.ceil(at/bar_seconds)*bar_seconds
    end=at+horizon_minutes*60
    w=[r for r in rows if first<=r["start"]<end]
    expected=max(1,int(math.ceil((end-first)/bar_seconds)))
    complete=len(w)>=expected and all((b["start"]-a["start"])==bar_seconds for a,b in zip(w,w[1:]))
    return w,expected,complete

def horizon_record(rows,baseline,at,horizon_minutes,interval_minutes):
    w,expected,complete=complete_window(rows,at,horizon_minutes,interval_minutes)
    if not complete:
        return {
            "complete":False,"bars":len(w),"expected_bars":expected,
            "interval_minutes":interval_minutes,
            "mfe_pct":None,"mae_pct":None,"end_close_pct":None,
            "peak_at_utc":None,"trough_at_utc":None,
            "reason":"incomplete_ohlc_coverage"
        }
    peak_bar=max(w,key=lambda x:x["high"])
    trough_bar=min(w,key=lambda x:x["low"])
    close=w[-1]["close"]
    return {
        "complete":True,"bars":len(w),"expected_bars":expected,
        "interval_minutes":interval_minutes,
        "mfe_pct":round(pct(peak_bar["high"],baseline),3),
        "mae_pct":round(pct(trough_bar["low"],baseline),3),
        "end_close_pct":round(pct(close,baseline),3),
        "peak_at_utc":zisots(peak_bar["start"]),
        "trough_at_utc":zisots(trough_bar["start"])
    }

def ensure_opportunity_audit(rec,d,q,alt):
    timing=d.get("timing") or {}
    detected_at=timing.get("candidate_detected_at_utc") or d.get("candidate_event_time_utc") or d.get("evaluated_at_utc")
    detected_ts=zdt(detected_at).timestamp()

    scanner_candidate=(q or {}).get("scanner_candidate") or {}
    scanner_context=(q or {}).get("scanner_market_context") or {}
    detection_price=scanner_context.get("sensor_price_eur")
    if detection_price is None:
        detection_price=scanner_candidate.get("price")
    if detection_price is None:
        detection_price=d.get("fresh_kraken_ticker",{}).get("ask")
    detection_price=float(detection_price)

    audit=rec.get("opportunity_audit")
    if not audit:
        audit={
            "schema_version":1,
            "purpose":"measure whether 'already moved/too late' was truly untradeable after scanner detection",
            "candidate_detected_at_utc":detected_at,
            "detection_price_eur":detection_price,
            "evaluated_at_utc":d.get("evaluated_at_utc"),
            "evaluation_ask_eur":d.get("fresh_kraken_ticker",{}).get("ask"),
            "detected_to_evaluation_complete_seconds":timing.get("detected_to_evaluation_complete_seconds"),
            "scan_step_started_at_utc":timing.get("scan_step_started_at_utc"),
            "reason_codes":d.get("decision",{}).get("reason_codes",[]),
            "setup_lane":d.get("decision",{}).get("setup_lane"),
            "flagged_as_already_run":(
                "recent_move_already_run" in d.get("decision",{}).get("reason_codes",[])
                or d.get("decision",{}).get("setup_lane")=="EXTENDED"
            ),
            "scanner_snapshot":{
                "ret15_live_pct":scanner_candidate.get("ret15_live"),
                "ret1h_pct":scanner_candidate.get("ret1h"),
                "ret3h_pct":scanner_candidate.get("ret3h"),
                "fresh_move_3h_pct":scanner_candidate.get("fresh_move_3h"),
                "scanner_late_flag":scanner_candidate.get("late"),
                "score":scanner_candidate.get("score")
            },
            "horizons":{},
            "classification":"PENDING_REVIEW"
        }
        try:
            prior=get_ohlc(alt,detected_ts-3*3600-120,1)
            prior=[r for r in prior if detected_ts-3*3600<=r["start"]<detected_ts]
            if prior:
                low_bar=min(prior,key=lambda x:x["low"])
                audit["impulse_anchor_proxy"]={
                    "method":"lowest_1m_low_in_prior_3h",
                    "at_utc":zisots(low_bar["start"]),
                    "price_eur":low_bar["low"],
                    "move_to_detection_pct":round(pct(detection_price,low_bar["low"]),3)
                }
        except Exception as exc:
            audit["impulse_anchor_proxy"]={
                "method":"lowest_1m_low_in_prior_3h",
                "status":"UNAVAILABLE",
                "error_type":type(exc).__name__
            }

    now=time.time()
    for h,interval in OPPORTUNITY_HORIZONS.items():
        key=str(h)
        if audit["horizons"].get(key,{}).get("complete"):
            continue
        bar_seconds=interval*60
        if now < detected_ts+h*60+bar_seconds:
            continue
        try:
            rows=get_ohlc(alt,detected_ts-2*bar_seconds,interval)
            audit["horizons"][key]=horizon_record(rows,detection_price,detected_ts,h,interval)
        except Exception as exc:
            audit["horizons"][key]={
                "complete":False,
                "interval_minutes":interval,
                "mfe_pct":None,"mae_pct":None,"end_close_pct":None,
                "peak_at_utc":None,"trough_at_utc":None,
                "reason":"ohlc_fetch_failed",
                "error_type":type(exc).__name__
            }

    h24=audit["horizons"].get("1440",{})
    if h24.get("complete"):
        audit["objective_flags_24h"]={
            "continuation_ge_2pct":bool(h24.get("mfe_pct") is not None and h24["mfe_pct"]>=2),
            "continuation_ge_5pct":bool(h24.get("mfe_pct") is not None and h24["mfe_pct"]>=5),
            "drawdown_le_minus_2pct":bool(h24.get("mae_pct") is not None and h24["mae_pct"]<=-2)
        }
    audit["updated_at_utc"]=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
    rec["opportunity_audit"]=audit

def main():
    control=json.loads((ROOT/"paper_runtime_control.json").read_text("utf-8"))
    if control.get("enabled") is not True:
        print("PAPER_RUNTIME_DISABLED")
        return
    series_id=control["series_id"]
    outdir=ROOT/"paper_followups"
    outdir.mkdir(exist_ok=True)
    revaldir=ROOT/"paper_revalidations"
    now=time.time()
    changed=0
    considered=0

    for p in sorted((ROOT/"paper_decisions").glob("*.json")):
        try:
            d=json.loads(p.read_text("utf-8"))
        except Exception:
            continue
        if d.get("series_id")!=series_id:
            continue
        original=d.get("decision",{}).get("decision")
        if original not in {"REJECT","WAIT"}:
            continue

        considered+=1
        baseline=float(d["fresh_kraken_ticker"]["ask"])
        at=zdt(d["evaluated_at_utc"]).timestamp()
        target=outdir/p.name
        rec=json.loads(target.read_text("utf-8")) if target.exists() else {
            "schema_version":2,"kind":"PAPER_FOLLOWUP_V2","series_id":series_id,
            "test_id":d["test_id"],"candidate_id":d["candidate_id"],"pair":d["pair"],
            "original_decision":original,"baseline_ask_eur":baseline,
            "evaluated_at_utc":d["evaluated_at_utc"],"interval_minutes":INTERVAL,
            "horizons":{}
        }

        reval_path=revaldir/p.name
        reval=None
        if reval_path.exists():
            try:
                reval=json.loads(reval_path.read_text("utf-8"))
            except Exception:
                reval=None

        if original=="REJECT":
            role="REJECT"
        elif reval and reval.get("decision",{}).get("decision")=="BUY_SCOUT":
            role="WAIT_TO_BUY"
        elif reval and reval.get("decision",{}).get("decision")=="REJECT":
            role="WAIT_TO_REJECT"
        else:
            role="WAIT_PENDING"

        rec["path_classification"]=role
        rec["excluded_from_missed_move_stats"]=(role=="WAIT_TO_BUY")
        if reval:
            rec["revalidation_decision"]=reval.get("decision",{}).get("decision")
            rec["revalidated_at_utc"]=reval.get("revalidated_at_utc")

        qpath=ROOT/"handoff_queue"/p.name
        q=None
        if qpath.exists():
            try:
                q=json.loads(qpath.read_text("utf-8"))
            except Exception:
                q=None
        alt=(q or {}).get("altname") or d.get("altname") or d["pair"].replace("/","")

        # Measurement-only audit. It never changes evaluator decisions, revalidation, entries, stops or sizing.
        ensure_opportunity_audit(rec,d,q,alt)

        due=[
            h for h in HORIZONS
            if now>=at+h*60+60
            and not rec["horizons"].get(str(h),{}).get("complete")
        ]
        if not due:
            target.write_text(json.dumps(rec,indent=2,sort_keys=True)+"\n","utf-8")
            continue

        rows=get_ohlc(alt,at-120,INTERVAL)
        first=math.ceil(at/60.0)*60

        for h in due:
            end=at+h*60
            w=[r for r in rows if first<=r["start"]<end]
            expected=max(1,int(math.ceil((end-first)/60.0)))
            complete=len(w)>=expected and all((b["start"]-a["start"])==60 for a,b in zip(w,w[1:]))
            if not complete:
                rec["horizons"][str(h)]={
                    "complete":False,"bars":len(w),"expected_bars":expected,
                    "mfe_pct":None,"mae_pct":None,"end_close_pct":None,
                    "reason":"incomplete_1m_coverage"
                }
                continue
            peak=max(x["high"] for x in w); trough=min(x["low"] for x in w); close=w[-1]["close"]
            rec["horizons"][str(h)]={
                "complete":True,"bars":len(w),"expected_bars":expected,
                "mfe_pct":round(pct(peak,baseline),3),
                "mae_pct":round(pct(trough,baseline),3),
                "end_close_pct":round(pct(close,baseline),3)
            }

        h6=rec["horizons"].get("360")
        if h6 and h6.get("complete") and not rec["excluded_from_missed_move_stats"]:
            mfe=h6.get("mfe_pct")
            rec["six_hour_flags"]={
                "missed_5pct":bool(mfe is not None and mfe>=5),
                "missed_8pct":bool(mfe is not None and mfe>=8),
                "missed_10pct":bool(mfe is not None and mfe>=10),
                "missed_15pct":bool(mfe is not None and mfe>=15)
            }
        else:
            rec.pop("six_hour_flags",None)

        rec["updated_at_utc"]=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
        target.write_text(json.dumps(rec,indent=2,sort_keys=True)+"\n","utf-8")
        changed+=1
        time.sleep(0.2)

    print("PAPER_FOLLOWUP_SUMMARY",json.dumps({
        "series_id":series_id,"considered":considered,"files_changed":changed,
        "interval_minutes":INTERVAL,
        "opportunity_horizons_minutes":sorted(OPPORTUNITY_HORIZONS)
    },sort_keys=True))

if __name__=="__main__":
    main()
