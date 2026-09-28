#!/usr/bin/env python3
"""Compact missed-move follow-up for current paper series using Kraken 5m OHLC."""
from __future__ import annotations
import json, math, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
HORIZONS=[30,60,120,360]
INTERVAL=5

def zdt(s):
    return datetime.fromisoformat(str(s).replace("Z","+00:00"))

def iso(ts):
    return datetime.fromtimestamp(ts,tz=timezone.utc).isoformat().replace("+00:00","Z")

def get_ohlc(pair,since):
    q=urllib.parse.urlencode({"pair":pair,"interval":INTERVAL,"since":int(since)})
    req=urllib.request.Request("https://api.kraken.com/0/public/OHLC?"+q,headers={"User-Agent":"paper-followup/1.0"})
    with urllib.request.urlopen(req,timeout=25) as r:
        d=json.loads(r.read().decode())
    if d.get("error"):
        raise RuntimeError(repr(d["error"]))
    rows=next(v for k,v in d["result"].items() if k!="last")
    return [{"start":int(x[0]),"high":float(x[2]),"low":float(x[3]),"close":float(x[4])} for x in rows]

def pct(x,b):
    return (x/b-1.0)*100.0

def main():
    control=json.loads((ROOT/"paper_runtime_control.json").read_text("utf-8"))
    if control.get("enabled") is not True:
        print("PAPER_RUNTIME_DISABLED")
        return
    series_id=control["series_id"]
    outdir=ROOT/"paper_followups"
    outdir.mkdir(exist_ok=True)
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
        if d.get("decision",{}).get("decision") not in {"REJECT","WAIT"}:
            continue
        considered+=1
        baseline=float(d["fresh_kraken_ticker"]["ask"])
        at=zdt(d["evaluated_at_utc"]).timestamp()
        target=outdir/p.name
        if target.exists():
            rec=json.loads(target.read_text("utf-8"))
        else:
            rec={
                "schema_version":1,"kind":"PAPER_FOLLOWUP_V1","series_id":series_id,
                "test_id":d["test_id"],"candidate_id":d["candidate_id"],"pair":d["pair"],
                "decision":d["decision"]["decision"],"baseline_ask_eur":baseline,
                "evaluated_at_utc":d["evaluated_at_utc"],"horizons":{}
            }
        due=[h for h in HORIZONS if str(h) not in rec["horizons"] and now>=at+h*60+INTERVAL*60]
        if not due:
            continue
        q=ROOT/"handoff_queue"/p.name
        alt=json.loads(q.read_text("utf-8")).get("altname") if q.exists() else d["pair"].replace("/","")
        rows=get_ohlc(alt,at-600)
        first=math.ceil(at/(INTERVAL*60))*(INTERVAL*60)
        for h in due:
            end=at+h*60
            w=[r for r in rows if first<=r["start"]<end]
            if not w:
                rec["horizons"][str(h)]={"complete":False,"bars":0,"mfe_pct":None,"mae_pct":None,"end_close_pct":None}
                continue
            peak=max(x["high"] for x in w); trough=min(x["low"] for x in w); close=w[-1]["close"]
            rec["horizons"][str(h)]={
                "complete":True,"bars":len(w),
                "mfe_pct":round(pct(peak,baseline),3),
                "mae_pct":round(pct(trough,baseline),3),
                "end_close_pct":round(pct(close,baseline),3)
            }
        h6=rec["horizons"].get("360")
        if h6 and h6.get("complete"):
            mfe=h6.get("mfe_pct")
            rec["six_hour_flags"]={
                "missed_5pct":bool(mfe is not None and mfe>=5),
                "missed_8pct":bool(mfe is not None and mfe>=8),
                "missed_10pct":bool(mfe is not None and mfe>=10),
                "missed_15pct":bool(mfe is not None and mfe>=15)
            }
        rec["updated_at_utc"]=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
        target.write_text(json.dumps(rec,indent=2,sort_keys=True)+"\n","utf-8")
        changed+=1
        time.sleep(0.35)

    print("PAPER_FOLLOWUP_SUMMARY",json.dumps({"series_id":series_id,"considered":considered,"files_changed":changed},sort_keys=True))

if __name__=="__main__":
    main()
