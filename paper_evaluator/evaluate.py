#!/usr/bin/env python3
"""Paper-only candidate evaluator. No private Kraken API and no order path."""
import argparse, json, os, time, urllib.request, urllib.parse
from datetime import datetime, timezone
from pathlib import Path

BLOCKED={"DUSK/EUR","QNT/EUR","TION/EUR"}
MODEL=os.getenv("OPENAI_MODEL","gpt-6-luna")
FEE_PCT=0.60

def utcnow(): return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def elapsed_seconds(start, end):
    if not start or not end:
        return None
    a=datetime.fromisoformat(str(start).replace("Z","+00:00"))
    b=datetime.fromisoformat(str(end).replace("Z","+00:00"))
    return round((b-a).total_seconds(),3)

def http_json(url, method="GET", headers=None, body=None, timeout=30):
    req=urllib.request.Request(url, data=body, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def kraken_ticker(altname):
    q=urllib.parse.urlencode({"pair":altname})
    data=http_json("https://api.kraken.com/0/public/Ticker?"+q, headers={"User-Agent":"paper-evaluator/1.0"})
    if data.get("error"): raise RuntimeError("Kraken ticker: "+repr(data["error"]))
    row=next(iter(data["result"].values()))
    bid=float(row["b"][0]); ask=float(row["a"][0]); last=float(row["c"][0])
    return {"bid":bid,"ask":ask,"last":last,"spread_pct":100*(ask-bid)/((ask+bid)/2)}

def validate_candidate(c, path):
    required=["candidate_id","queue_id","source_scanner_run_id","event_time_utc","event_ts","pair","altname","action","scanner_candidate","scanner_market_context"]
    miss=[k for k in required if k not in c]
    if miss: raise ValueError("missing candidate fields: "+",".join(miss))
    if c["action"]!="REVIEW_ONLY_NOT_ORDER": raise ValueError("unsafe candidate action")
    dt=datetime.fromisoformat(c["event_time_utc"].replace("Z","+00:00"))
    pair_tag=c["pair"].replace("/","-")
    expected=f'{dt.strftime("%Y%m%d-%H%M%S")}-{pair_tag}-r{int(c["source_scanner_run_id"])}'
    if c["candidate_id"]!=expected or Path(path).stem!=expected: raise ValueError("candidate identity mismatch")
    if int(dt.timestamp())!=int(c["event_ts"]): raise ValueError("candidate timestamp mismatch")
    if c["queue_id"]!=f'{int(c["source_scanner_run_id"])}:{pair_tag}:{int(c["event_ts"])}': raise ValueError("queue identity mismatch")

def extract_text(resp):
    for item in resp.get("output",[]):
        for part in item.get("content",[]):
            if part.get("type")=="output_text" and part.get("text"): return part["text"]
    raise RuntimeError("OpenAI response contains no output_text")

def parse_json_text(text):
    text=text.strip()
    if text.startswith("~~~") or text.startswith("```"):
        lines=text.splitlines(); text="\n".join(lines[1:-1]).strip()
    return json.loads(text)

def call_evaluator(candidate, current):
    api_key=os.environ["OPENAI_API_KEY"]
    f=candidate["scanner_candidate"]; ctx=candidate["scanner_market_context"]
    prompt=f"""You are the frozen V2 PAPER strategy evaluator for Kraken Spot EUR.
This is PAPER ONLY. Never place, request, or imply a real order.
Return ONLY one JSON object, no markdown.

Frozen principles:
- Scanner is only a sensor, never a direct entry generator.
- Evaluate in this order: tradability/liquidity/spread; market/regime evidence available; IGNITION/CONTINUITY/EXTENDED/REVERSAL; multi-period continuity/relative strength; volume/orderflow evidence; entry efficiency and distance already run; remaining potential versus all costs; structure/ATR stop; two-stage entry only if each stage retains attractive net reward/risk; TTL/revalidation.
- Kraken EUR execution reality controls. Round-trip taker fees are 1.20% before spread/slippage (0.60% each side).
- Plausible remaining movement around only 1-2% is normally insufficient; 2-3% is not automatically sufficient.
- Missing data must be treated as missing, not invented. Do not fabricate news, macro, breadth, orderflow or targets.
- Avoid FOMO/late chasing. A strong score alone is insufficient.
- BUY_SCOUT only when evidence supplied here is enough for a prospective paper entry. WAIT when 1-2 concrete confirmations could make it valid within 30-60 minutes. Otherwise REJECT.
- This frozen test is for measurement, not optimization. Do not invent new thresholds.
- DUSK/EUR, QNT/EUR and TION/EUR are blocked.
- If BUY_SCOUT, stop_eur must be a positive structural/ATR-based invalidation below current ask. If evidence is insufficient to define it, use WAIT instead.

Candidate:
{json.dumps(candidate,sort_keys=True,separators=(",",":"))}
Fresh Kraken ticker at evaluation:
{json.dumps(current,sort_keys=True,separators=(",",":"))}

Required JSON keys exactly:
decision: BUY_SCOUT | WAIT | REJECT
setup_lane: IGNITION | CONTINUITY | EXTENDED | REVERSAL | NONE
summary: short string
reason_codes: array of short strings
missing_triggers: array, maximum 2 strings
stop_eur: number or null
ttl_minutes: integer 0..60
expected_remaining_move_pct: number or null
risk_reward_after_costs: number or null
"""
    payload={"model":MODEL,"input":prompt,"max_output_tokens":1400}
    body=json.dumps(payload).encode()
    headers={"Authorization":"Bearer "+api_key,"Content-Type":"application/json","User-Agent":"kraken-paper-evaluator/1.0"}
    last=None
    for attempt in range(2):
        try:
            resp=http_json("https://api.openai.com/v1/responses","POST",headers,body,60)
            out=parse_json_text(extract_text(resp))
            return out, {"response_id":resp.get("id"),"model":resp.get("model",MODEL),"attempt":attempt+1}
        except Exception as e:
            last=e
            if attempt==0: time.sleep(2)
    raise RuntimeError("OpenAI evaluator failed after one retry: "+repr(last))

def validate_decision(d, current):
    allowed={"BUY_SCOUT","WAIT","REJECT"}
    if d.get("decision") not in allowed: raise ValueError("invalid decision")
    if d.get("setup_lane") not in {"IGNITION","CONTINUITY","EXTENDED","REVERSAL","NONE"}: raise ValueError("invalid setup lane")
    if not isinstance(d.get("reason_codes"),list): raise ValueError("reason_codes must be list")
    if not isinstance(d.get("missing_triggers"),list) or len(d["missing_triggers"])>2: raise ValueError("invalid missing_triggers")
    ttl=d.get("ttl_minutes")
    if not isinstance(ttl,int) or not 0<=ttl<=60: raise ValueError("invalid ttl")
    if d["decision"]=="BUY_SCOUT":
        stop=d.get("stop_eur")
        if not isinstance(stop,(int,float)) or stop<=0 or stop>=current["ask"]: raise ValueError("unsafe/missing paper stop")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("candidate"); ap.add_argument("--out",default="paper_decisions")
    a=ap.parse_args()
    c=json.loads(Path(a.candidate).read_text("utf-8")); validate_candidate(c,a.candidate)
    outdir=Path(a.out); outdir.mkdir(parents=True,exist_ok=True)
    target=outdir/(c["candidate_id"]+".json")
    if target.exists():
        print("PAPER_EVAL_IDEMPOTENT",c["candidate_id"]); return
    evaluation_started_at_utc=utcnow()
    current=kraken_ticker(c["altname"])
    age=max(0,int(time.time())-int(c["event_ts"]))
    if c["pair"] in BLOCKED:
        d={"decision":"REJECT","setup_lane":"NONE","summary":"Pair is blocked by frozen strategy.","reason_codes":["PAIR_BLOCKED"],"missing_triggers":[],"stop_eur":None,"ttl_minutes":0,"expected_remaining_move_pct":None,"risk_reward_after_costs":None}
        api={"response_id":None,"model":None,"attempt":0}
    elif age>3600:
        d={"decision":"REJECT","setup_lane":"NONE","summary":"Candidate is stale for prospective paper entry.","reason_codes":["STALE_OVER_60M"],"missing_triggers":[],"stop_eur":None,"ttl_minutes":0,"expected_remaining_move_pct":None,"risk_reward_after_costs":None}
        api={"response_id":None,"model":None,"attempt":0}
    else:
        d,api=call_evaluator(c,current); validate_decision(d,current)
    evaluation_completed_at_utc=utcnow()
    timing=dict(c.get("timing") or {})
    detected_at=timing.get("candidate_detected_at_utc") or c["event_time_utc"]
    timing.update({
        "evaluation_started_at_utc":evaluation_started_at_utc,
        "evaluation_completed_at_utc":evaluation_completed_at_utc,
        "detected_to_evaluation_start_seconds":elapsed_seconds(detected_at,evaluation_started_at_utc),
        "detected_to_evaluation_complete_seconds":elapsed_seconds(detected_at,evaluation_completed_at_utc),
        "handoff_to_evaluation_start_seconds":elapsed_seconds(timing.get("handoff_written_at_utc"),evaluation_started_at_utc),
        "evaluation_runtime_seconds":elapsed_seconds(evaluation_started_at_utc,evaluation_completed_at_utc),
    })
    record={"schema_version":1,"kind":"PAPER_V2_DECISION_V1","test_id":"SHADOW-V2-20260924-01","candidate_id":c["candidate_id"],"queue_id":c["queue_id"],"pair":c["pair"],"candidate_event_time_utc":c["event_time_utc"],"evaluated_at_utc":evaluation_completed_at_utc,"candidate_age_seconds":age,"timing":timing,"frozen_strategy":"V2-2026-09-24","real_money_actions_enabled":False,"fee_assumption_pct_per_side":FEE_PCT,"fresh_kraken_ticker":current,"decision":d,"evaluator":api}
    if d["decision"]=="BUY_SCOUT":
        paper_eur=50.0
        fill=current["ask"]
        qty=paper_eur/fill
        record["paper_entry"]={"status":"FILLED_SIMULATED_AT_FRESH_ASK","notional_eur":paper_eur,"fill_price_eur":fill,"quantity":qty,"entry_fee_eur":paper_eur*FEE_PCT/100,"slippage_model":"fresh_best_ask_only; no extra invented slippage","stop_eur":d["stop_eur"],"opened_at_utc":record["evaluated_at_utc"]}
    else: record["paper_entry"]=None
    target.write_text(json.dumps(record,indent=2,sort_keys=True)+"\n","utf-8")
    print("PAPER_EVAL_RESULT",json.dumps({"candidate_id":c["candidate_id"],"pair":c["pair"],"decision":d["decision"],"response_id":api["response_id"]},sort_keys=True))

if __name__=="__main__": main()
