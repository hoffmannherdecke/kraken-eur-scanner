#!/usr/bin/env python3
"""Compact 1m missed-move follow-up for the active paper series."""
from __future__ import annotations
import json, math, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
HORIZONS=[30,60,120,360]
INTERVAL=1

def zdt(s):
    return datetime.fromisoformat(str(s).replace("Z","+00:00"))

def pct(x,b):
    return (x/b-1.0)*100.0

def get_ohlc(pair,since):
    q=urllib.parse.urlencode({"pair":pair,"interval":INTERVAL,"since":int(since)})
    req=urllib.request.Request("https://api.kraken.com/0/public/OHLC?"+q,headers={"User-Agent":"paper-followup/2.0"})
    with urllib.request.urlopen(req,timeout=25) as r:
        d=json.loads(r.read().decode())
    if d.get("error"):
        raise RuntimeError(repr(d["error"]))
    rows=next(v for k,v in d["result"].items() if k!="last")
    now=time.time()
    return [
        {"start":int(x[0]),"high":float(x[2]),"low":float(x[3]),"close":float(x[4])}
        for x in rows if int(x[0])+60<=now
    ]

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

        due=[
            h for h in HORIZONS
            if now>=at+h*60+60
            and not rec["horizons"].get(str(h),{}).get("complete")
        ]
        if not due:
            if target.exists():
                # Persist classification changes such as WAIT -> BUY even if no new horizon is due.
                target.write_text(json.dumps(rec,indent=2,sort_keys=True)+"\n","utf-8")
            continue

        q=ROOT/"handoff_queue"/p.name
        alt=json.loads(q.read_text("utf-8")).get("altname") if q.exists() else d["pair"].replace("/","")
        rows=get_ohlc(alt,at-120)
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
        "interval_minutes":INTERVAL
    },sort_keys=True))

if __name__=="__main__":
    main()
