#!/usr/bin/env python3
"""One-shot TTL revalidation for active-series WAIT decisions. Paper only."""
from __future__ import annotations
import hashlib, json, sys, time, urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from paper_context import build_context
from evaluate import (
    http_json, kraken_ticker, call_evaluator, fail_safe_normalize, apply_sample_cap,
    FEE_PCT, zdt, utcnow
)

def ohlc15(altname):
    q=urllib.parse.urlencode({"pair":altname,"interval":15})
    d=http_json("https://api.kraken.com/0/public/OHLC?"+q,headers={"User-Agent":"paper-revalidator/2.0"})
    if d.get("error"):
        raise RuntimeError("Kraken OHLC: "+repr(d["error"]))
    rows=next(v for k,v in d["result"].items() if k!="last")[-5:]
    return [{"ts":int(r[0]),"open":float(r[1]),"high":float(r[2]),"low":float(r[3]),
             "close":float(r[4]),"vwap":float(r[5]),"volume":float(r[6]),"trades":int(r[7])}
            for r in rows]

def main():
    control=json.loads((ROOT/"paper_runtime_control.json").read_text("utf-8"))
    if control.get("enabled") is not True:
        print("PAPER_RUNTIME_DISABLED")
        return
    spec_bytes=(ROOT/"paper_strategy_spec.json").read_bytes()
    spec=json.loads(spec_bytes)
    fingerprint=hashlib.sha256(spec_bytes).hexdigest()
    series_id=control["series_id"]

    out=ROOT/"paper_revalidations"
    out.mkdir(exist_ok=True)
    due=[]
    now=datetime.now(timezone.utc)

    for p in (ROOT/"paper_decisions").glob("*.json"):
        try:
            d=json.loads(p.read_text("utf-8"))
        except Exception:
            continue
        if d.get("series_id")!=series_id:
            continue
        if d.get("decision",{}).get("decision")!="WAIT":
            continue
        if (out/p.name).exists():
            continue
        ttl=int(d["decision"].get("ttl_minutes",0))
        due_at=zdt(d["evaluated_at_utc"])+timedelta(minutes=ttl)
        if now>=due_at:
            due.append((due_at,p,d))

    due.sort(key=lambda x:x[0])
    print("REVALIDATION_DUE",len(due))

    for due_at,p,old in due[:20]:
        cp=ROOT/"handoff_queue"/(old["candidate_id"]+".json")
        if not cp.exists():
            raise RuntimeError("missing original candidate "+old["candidate_id"])
        c=json.loads(cp.read_text("utf-8"))
        started=utcnow()
        ticker=kraken_ticker(c["altname"])
        bars=ohlc15(c["altname"])
        external=build_context(c,ticker)

        enriched=dict(c)
        enriched["revalidation_context"]={
            "kind":"ONE_SHOT_TTL_REVALIDATION",
            "prior_decision":old["decision"],
            "prior_ticker":old["fresh_kraken_ticker"],
            "fresh_kraken_ticker":ticker,
            "kraken_15m_recent":bars,
            "due_at_utc":due_at.isoformat().replace("+00:00","Z"),
            "instruction":"This is the single allowed TTL revalidation. Return BUY_SCOUT only if supplied evidence now supports a scout plus explicit second-stage confirmation plan; otherwise return REJECT. Do not return WAIT."
        }
        raw,api=call_evaluator(enriched,ticker,external,spec,control)
        d=apply_sample_cap(fail_safe_normalize(raw,ticker),control)
        if d["decision"]=="WAIT":
            d={
                "decision":"REJECT","setup_lane":d.get("setup_lane","NONE"),
                "summary":"One-shot TTL expired without sufficient confirmation.",
                "reason_codes":["TTL_EXPIRED_AFTER_REVALIDATION"]+list(d.get("reason_codes",[]))[:5],
                "missing_triggers":[],"stop_eur":None,"ttl_minutes":0,
                "expected_remaining_move_pct":d.get("expected_remaining_move_pct"),
                "risk_reward_after_costs":d.get("risk_reward_after_costs"),
                "stage2_trigger_eur":None,"stage2_ttl_minutes":0
            }

        completed=utcnow()
        rec={
            "schema_version":2,"kind":"PAPER_V2_REVALIDATION_V2",
            "test_id":control["test_id"],"series_id":series_id,
            "candidate_id":c["candidate_id"],"pair":c["pair"],"altname":c["altname"],
            "revalidated_at_utc":completed,
            "timing":{
                "ttl_due_at_utc":due_at.isoformat().replace("+00:00","Z"),
                "revalidation_started_at_utc":started,
                "revalidation_completed_at_utc":completed,
                "ttl_lag_seconds":round((zdt(started)-due_at).total_seconds(),3)
            },
            "strategy_revision":spec["strategy_revision"],
            "strategy_fingerprint_sha256":fingerprint,
            "runtime_code_sha":__import__("os").getenv("GITHUB_SHA"),
            "real_money_actions_enabled":False,
            "fee_assumption_pct_per_side":FEE_PCT,
            "prior_decision_file":str(p.relative_to(ROOT)),
            "fresh_kraken_ticker":ticker,
            "kraken_15m_recent":bars,
            "decision_context":external,
            "decision":d,"evaluator":api,"paper_entry":None
        }

        if d["decision"]=="BUY_SCOUT":
            notional=float(spec["entry"]["scout_notional_eur"])
            fill=ticker["ask"]
            opened=zdt(rec["revalidated_at_utc"])
            s2ttl=int(d["stage2_ttl_minutes"])
            rec["paper_entry"]={
                "status":"SCOUT_FILLED_SIMULATED_AT_FRESH_ASK_AFTER_REVALIDATION",
                "scout_notional_eur":notional,
                "fill_price_eur":fill,
                "quantity":notional/fill,
                "entry_fee_eur":notional*FEE_PCT/100,
                "entry_spread_pct":ticker["spread_pct"],
                "slippage_model":"fresh best ask; historical spread-aware model applied to later stage/exit where available",
                "stop_eur":d["stop_eur"],
                "opened_at_utc":rec["revalidated_at_utc"],
                "stage2_plan":{
                    "status":"PENDING",
                    "trigger_eur":float(d["stage2_trigger_eur"]),
                    "notional_eur":float(spec["entry"]["stage2_notional_eur"]),
                    "ttl_minutes":s2ttl,
                    "expires_at_utc":(opened+timedelta(minutes=s2ttl)).isoformat().replace("+00:00","Z"),
                    "execution_type":"SIMULATED_STOP_BUY_CONFIRMATION"
                }
            }

        (out/p.name).write_text(json.dumps(rec,indent=2,sort_keys=True)+"\n","utf-8")
        print("REVALIDATED",c["candidate_id"],d["decision"],"lag_s",rec["timing"]["ttl_lag_seconds"])
        time.sleep(0.25)

if __name__=="__main__":
    main()
