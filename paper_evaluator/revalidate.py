#!/usr/bin/env python3
"""One-shot TTL revalidation for frozen V2 WAIT decisions. Paper only."""
import json, os, time, urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from evaluate import http_json, kraken_ticker, call_evaluator, validate_decision, FEE_PCT

def zdt(s): return datetime.fromisoformat(s.replace("Z","+00:00"))
def nowz(): return datetime.now(timezone.utc)
def iso(d): return d.isoformat().replace("+00:00","Z")

def ohlc15(altname):
    q=urllib.parse.urlencode({"pair":altname,"interval":15})
    d=http_json("https://api.kraken.com/0/public/OHLC?"+q,headers={"User-Agent":"paper-revalidator/1.0"})
    if d.get("error"): raise RuntimeError("Kraken OHLC: "+repr(d["error"]))
    rows=next(v for k,v in d["result"].items() if k!="last")
    rows=rows[-5:]
    return [{"ts":int(r[0]),"open":float(r[1]),"high":float(r[2]),"low":float(r[3]),"close":float(r[4]),"vwap":float(r[5]),"volume":float(r[6]),"trades":int(r[7])} for r in rows]

def main():
    root=Path(__file__).resolve().parents[1]
    out=root/"paper_revalidations"; out.mkdir(exist_ok=True)
    due=[]
    for p in (root/"paper_decisions").glob("*.json"):
        d=json.loads(p.read_text())
        if d["decision"]["decision"]!="WAIT": continue
        if (out/p.name).exists(): continue
        ttl=int(d["decision"]["ttl_minutes"])
        if nowz() >= zdt(d["evaluated_at_utc"])+timedelta(minutes=ttl):
            due.append((p,d))
    print("REVALIDATION_DUE",len(due))
    for p,old in due[:5]:
        cp=root/"handoff_queue"/(old["candidate_id"]+".json")
        if not cp.exists(): raise RuntimeError("missing original candidate "+old["candidate_id"])
        c=json.loads(cp.read_text())
        ticker=kraken_ticker(c["altname"]); bars=ohlc15(c["altname"])
        enriched=dict(c)
        enriched["revalidation_context"]={
          "kind":"ONE_SHOT_TTL_REVALIDATION",
          "prior_decision":old["decision"],
          "prior_ticker":old["fresh_kraken_ticker"],
          "fresh_kraken_ticker":ticker,
          "kraken_15m_recent":bars,
          "instruction":"This is the single allowed TTL revalidation. Return BUY_SCOUT only if supplied evidence now supports it; otherwise return REJECT. Do not return WAIT."
        }
        d,api=call_evaluator(enriched,ticker); validate_decision(d,ticker)
        if d["decision"]=="WAIT":
            d={"decision":"REJECT","setup_lane":d.get("setup_lane","NONE"),"summary":"One-shot TTL expired without sufficient confirmation.","reason_codes":["TTL_EXPIRED_AFTER_REVALIDATION"]+list(d.get("reason_codes",[]))[:3],"missing_triggers":[],"stop_eur":None,"ttl_minutes":0,"expected_remaining_move_pct":d.get("expected_remaining_move_pct"),"risk_reward_after_costs":d.get("risk_reward_after_costs")}
        rec={"schema_version":1,"kind":"PAPER_V2_REVALIDATION_V1","test_id":"SHADOW-V2-20260924-01","candidate_id":c["candidate_id"],"pair":c["pair"],"revalidated_at_utc":iso(nowz()),"real_money_actions_enabled":False,"fee_assumption_pct_per_side":FEE_PCT,"prior_decision_file":str(p.relative_to(root)),"fresh_kraken_ticker":ticker,"kraken_15m_recent":bars,"decision":d,"evaluator":api,"paper_entry":None}
        if d["decision"]=="BUY_SCOUT":
            fill=ticker["ask"]; notional=50.0
            rec["paper_entry"]={"status":"FILLED_SIMULATED_AT_FRESH_ASK_AFTER_REVALIDATION","notional_eur":notional,"fill_price_eur":fill,"quantity":notional/fill,"entry_fee_eur":notional*FEE_PCT/100,"slippage_model":"fresh_best_ask_only; no extra invented slippage","stop_eur":d["stop_eur"],"opened_at_utc":rec["revalidated_at_utc"]}
        (out/p.name).write_text(json.dumps(rec,indent=2,sort_keys=True)+"\n")
        print("REVALIDATED",c["candidate_id"],d["decision"])
if __name__=="__main__": main()
