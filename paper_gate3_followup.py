#!/usr/bin/env python3
from __future__ import annotations
import json, math, os, statistics, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.kraken.com/0/public"
CASES = Path("docs/gate3-20-followup-cases.json")
OUT_JSON = Path("gate3_20_followup.json")
OUT_MD = Path("gate3_20_followup.md")
INTERVAL_MIN = 5
HORIZONS_MIN = [30,60,120,360]
UA = "gate3-20-followup-audit/1.0"

def ts(s):
    return datetime.fromisoformat(s.replace("Z","+00:00")).timestamp()

def iso(x):
    return datetime.fromtimestamp(x,tz=timezone.utc).isoformat()

def get_ohlc(pair, since):
    q=urllib.parse.urlencode({"pair":pair,"interval":INTERVAL_MIN,"since":int(since)})
    req=urllib.request.Request(API+"/OHLC?"+q,headers={"User-Agent":UA,"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=30) as resp:
        p=json.loads(resp.read().decode())
    if p.get("error"): raise RuntimeError("; ".join(p["error"]))
    result=p["result"]; keys=[k for k in result if k!="last"]
    if not keys: raise RuntimeError("no OHLC pair rows")
    rows=[]
    for c in result[keys[0]]:
        rows.append({"start":int(c[0]),"open":float(c[1]),"high":float(c[2]),"low":float(c[3]),"close":float(c[4])})
    return rows

def pct(x, base):
    return (x/base-1)*100

def analyze(case, rows, now):
    base=float(case["ask"]); at=ts(case["assessment_time_utc"])
    # Strictly post-decision complete 5m candles only: skip candle containing decision.
    first_start=math.ceil(at/(INTERVAL_MIN*60))*(INTERVAL_MIN*60)
    out={**case,"baseline_ask_eur":base,"post_bar_start_utc":iso(first_start),"horizons":{}}
    for h in HORIZONS_MIN:
        end=at+h*60
        complete=now >= end + INTERVAL_MIN*60
        w=[r for r in rows if first_start <= r["start"] < end]
        if not w:
            out["horizons"][str(h)]={"complete":complete,"bars":0,"mfe_pct":None,"mae_pct":None,"end_close_pct":None}
            continue
        peak_row=max(w,key=lambda r:r["high"]); trough_row=min(w,key=lambda r:r["low"]); close=w[-1]["close"]
        peak=peak_row["high"]; trough=trough_row["low"]
        out["horizons"][str(h)]={
          "complete":complete,"bars":len(w),
          "mfe_pct":round(pct(peak,base),3),
          "mae_pct":round(pct(trough,base),3),
          "end_close_pct":round(pct(close,base),3),
          "peak_eur":peak,"peak_bar_start_utc":iso(peak_row["start"]),
          "trough_eur":trough,"trough_bar_start_utc":iso(trough_row["start"]),
          "end_close_eur":close
        }
    h6=out["horizons"]["360"]
    out["six_hour_complete"]=h6["complete"]
    out["missed_5pct_6h"]=bool(h6["complete"] and h6["mfe_pct"] is not None and h6["mfe_pct"]>=5)
    out["missed_8pct_6h"]=bool(h6["complete"] and h6["mfe_pct"] is not None and h6["mfe_pct"]>=8)
    out["missed_10pct_6h"]=bool(h6["complete"] and h6["mfe_pct"] is not None and h6["mfe_pct"]>=10)
    out["missed_15pct_6h"]=bool(h6["complete"] and h6["mfe_pct"] is not None and h6["mfe_pct"]>=15)
    out["drawdown_ge_3pct_6h"]=bool(h6["complete"] and h6["mae_pct"] is not None and h6["mae_pct"]<=-3)
    out["drawdown_ge_5pct_6h"]=bool(h6["complete"] and h6["mae_pct"] is not None and h6["mae_pct"]<=-5)
    if h6["complete"]:
        six=[r for r in rows if first_start <= r["start"] < at+360*60]
        first_hits={}
        for threshold in (5,8,10,15):
            hit=next((r for r in six if pct(r["high"],base)>=threshold),None)
            first_hits[str(threshold)] = iso(hit["start"]) if hit else None
        out["first_mfe_threshold_bar_utc"]=first_hits
    else:
        out["first_mfe_threshold_bar_utc"]={"5":None,"8":None,"10":None,"15":None}
    return out

def main():
    doc=json.loads(CASES.read_text())
    now=time.time(); results=[]; errors={}
    cache={}
    for c in doc["cases"]:
        alt=c["altname"]
        if alt not in cache:
            try:
                cache[alt]=get_ohlc(alt, ts(c["assessment_time_utc"])-600)
            except Exception as e:
                errors[alt]=str(e); cache[alt]=[]
            time.sleep(1.05)
        results.append(analyze(c,cache[alt],now))
    mature=[r for r in results if r["six_hour_complete"] and r["horizons"]["360"]["mfe_pct"] is not None]
    summary={
      "generated_at_utc":iso(now),"case_count":len(results),
      "six_hour_mature_count":len(mature),"six_hour_pending_count":len(results)-len(mature),
      "missed_5pct_6h":sum(r["missed_5pct_6h"] for r in mature),
      "missed_8pct_6h":sum(r["missed_8pct_6h"] for r in mature),
      "missed_10pct_6h":sum(r["missed_10pct_6h"] for r in mature),
      "missed_15pct_6h":sum(r["missed_15pct_6h"] for r in mature),
      "drawdown_ge_3pct_6h":sum(r["drawdown_ge_3pct_6h"] for r in mature),
      "drawdown_ge_5pct_6h":sum(r["drawdown_ge_5pct_6h"] for r in mature),
      "median_mfe_6h_pct":round(statistics.median([r["horizons"]["360"]["mfe_pct"] for r in mature]),3) if mature else None,
      "median_mae_6h_pct":round(statistics.median([r["horizons"]["360"]["mae_pct"] for r in mature]),3) if mature else None,
      "all_six_hour_complete":len(mature)==len(results),
      "errors":errors
    }
    report={
      "schema_version":1,"test_id":doc["test_id"],
      "measurement":"Fixed 20-case rejection follow-up; no new strategy evaluation",
      "method":{
        "baseline":"actual evaluator-time Kraken EUR executable ask from persisted evidence bundle",
        "path_source":"Kraken public EUR OHLC",
        "interval_min":INTERVAL_MIN,
        "anti_backdating":"candle containing decision is excluded; first included bar starts at next 5-minute boundary",
        "horizons_min":HORIZONS_MIN,
        "note":"This conservative method may understate the first <=5 minutes of MFE/MAE."
      },
      "summary":summary,"cases":results
    }
    OUT_JSON.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    lines=["# Gate-3 20-case rejection follow-up","",f"Generated: {summary['generated_at_utc']}",
      f"6h mature: **{summary['six_hour_mature_count']}/20**",
      f"6h missed >=5%: **{summary['missed_5pct_6h']}**",
      f"6h missed >=8%: **{summary['missed_8pct_6h']}**",
      f"6h missed >=10%: **{summary['missed_10pct_6h']}**",
      f"6h missed >=15%: **{summary['missed_15pct_6h']}**",
      f"6h drawdown <=-3%: **{summary['drawdown_ge_3pct_6h']}**",
      f"6h drawdown <=-5%: **{summary['drawdown_ge_5pct_6h']}**","",
      "## Cases",""]
    for r in results:
        hs=[]
        for h in HORIZONS_MIN:
            q=r["horizons"][str(h)]
            hs.append(f"{h}m MFE/MAE {q['mfe_pct']}/{q['mae_pct']}% ({'complete' if q['complete'] else 'partial'})")
        lines.append(f"- **{r['label']} {r['pair']}** — "+" | ".join(hs))
    OUT_MD.write_text("\n".join(lines)+"\n")
    print(json.dumps(summary,sort_keys=True))

if __name__=="__main__":
    main()
