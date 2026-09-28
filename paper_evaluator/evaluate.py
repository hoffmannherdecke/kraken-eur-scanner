#!/usr/bin/env python3
"""Paper-only candidate evaluator. No private Kraken API and no order path."""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from paper_context import build_context

BLOCKED={"DUSK/EUR","QNT/EUR","TION/EUR"}
MODEL=os.getenv("OPENAI_MODEL","gpt-6-luna")
FEE_PCT=0.60
PROMPT_SCHEMA_VERSION=2

def utcnow():
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def zdt(s):
    return datetime.fromisoformat(str(s).replace("Z","+00:00"))

def elapsed_seconds(start, end):
    if not start or not end:
        return None
    return round((zdt(end)-zdt(start)).total_seconds(),3)

def load_runtime():
    control=json.loads((ROOT/"paper_runtime_control.json").read_text("utf-8"))
    spec_bytes=(ROOT/"paper_strategy_spec.json").read_bytes()
    spec=json.loads(spec_bytes)
    fingerprint=hashlib.sha256(spec_bytes).hexdigest()
    return control,spec,fingerprint

def http_json(url, method="GET", headers=None, body=None, timeout=30):
    req=urllib.request.Request(url,data=body,method=method,headers=headers or {})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode())

def kraken_ticker(altname):
    q=urllib.parse.urlencode({"pair":altname})
    data=http_json("https://api.kraken.com/0/public/Ticker?"+q,headers={"User-Agent":"paper-evaluator/2.0"})
    if data.get("error"):
        raise RuntimeError("Kraken ticker: "+repr(data["error"]))
    row=next(iter(data["result"].values()))
    bid=float(row["b"][0]); ask=float(row["a"][0]); last=float(row["c"][0])
    return {"bid":bid,"ask":ask,"last":last,"spread_pct":100*(ask-bid)/((ask+bid)/2)}

def validate_candidate(c,path):
    required=["candidate_id","queue_id","source_scanner_run_id","event_time_utc","event_ts",
              "pair","altname","action","scanner_candidate","scanner_market_context"]
    miss=[k for k in required if k not in c]
    if miss:
        raise ValueError("missing candidate fields: "+",".join(miss))
    if c["action"]!="REVIEW_ONLY_NOT_ORDER":
        raise ValueError("unsafe candidate action")
    dt=zdt(c["event_time_utc"])
    pair_tag=c["pair"].replace("/","-")
    expected=f'{dt.strftime("%Y%m%d-%H%M%S")}-{pair_tag}-r{int(c["source_scanner_run_id"])}'
    if c["candidate_id"]!=expected or Path(path).stem!=expected:
        raise ValueError("candidate identity mismatch")
    if int(dt.timestamp())!=int(c["event_ts"]):
        raise ValueError("candidate timestamp mismatch")
    if c["queue_id"]!=f'{int(c["source_scanner_run_id"])}:{pair_tag}:{int(c["event_ts"])}':
        raise ValueError("queue identity mismatch")

def extract_text(resp):
    for item in resp.get("output",[]):
        for part in item.get("content",[]):
            if part.get("type")=="output_text" and part.get("text"):
                return part["text"]
    raise RuntimeError("OpenAI response contains no output_text")

def parse_json_text(text):
    text=text.strip()
    if text.startswith("~~~") or text.startswith("```"):
        lines=text.splitlines()
        text="\n".join(lines[1:-1]).strip()
    return json.loads(text)

def call_evaluator(candidate,current,external,spec,control):
    api_key=os.environ["OPENAI_API_KEY"]
    prompt=f"""You are the PAPER strategy evaluator for Kraken Spot EUR.
This is PAPER ONLY. Never place, request, or imply a real order.
Return ONLY one JSON object, no markdown.

Strategy revision: {spec["strategy_revision"]}
Series: {control["series_id"]}

Principles:
- Scanner is only a sensor, never a direct entry generator.
- Evaluate in this order: tradability/liquidity/spread; market/regime and event evidence actually supplied; IGNITION/CONTINUITY/EXTENDED/REVERSAL; multi-period continuity/relative strength; volume/orderflow/derivatives evidence actually supplied; entry efficiency and distance already run; remaining potential versus all costs; structural/ATR stop; two-stage entry; TTL/revalidation.
- Kraken EUR execution reality controls. Round-trip taker fees are 1.20% before spread/slippage (0.60% each side).
- Plausible remaining movement around only 1-2% is normally insufficient; 2-3% is not automatically sufficient.
- Missing data must remain missing. Do not fabricate news, macro, breadth, orderflow, on-chain facts, targets or account tradability.
- Binance derivatives, when available, are cross-market context only and never Kraken EUR execution prices.
- Official Fed/SEC headlines are context, not proof of a coin-specific catalyst.
- Avoid FOMO/late chasing. A strong scanner score alone is insufficient.
- BUY_SCOUT only when evidence supplied is enough for a prospective scout entry AND a concrete second-stage confirmation trigger can be defined above the current ask.
- The second stage is a confirmation stop-buy simulation, not an automatic immediate fill.
- WAIT when 1-2 concrete confirmations could make the setup valid within 30-60 minutes. Otherwise REJECT.
- DUSK/EUR, QNT/EUR and TION/EUR are blocked.
- If BUY_SCOUT, stop_eur must be a positive structural/ATR-based invalidation below current ask.
- If BUY_SCOUT, stage2_trigger_eur must be strictly above current ask and represent confirmation, not arbitrary distance.
- If evidence is insufficient to define either the stop or stage2 confirmation, use WAIT instead.

Candidate:
{json.dumps(candidate,sort_keys=True,separators=(",",":"))}

Fresh Kraken EUR ticker:
{json.dumps(current,sort_keys=True,separators=(",",":"))}

Additional public context:
{json.dumps(external,sort_keys=True,separators=(",",":"))}

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
stage2_trigger_eur: number or null
stage2_ttl_minutes: integer 0..60
"""
    payload={"model":MODEL,"input":prompt,"max_output_tokens":1700}
    body=json.dumps(payload).encode()
    headers={"Authorization":"Bearer "+api_key,"Content-Type":"application/json","User-Agent":"kraken-paper-evaluator/2.0"}
    last=None
    for attempt in range(2):
        try:
            resp=http_json("https://api.openai.com/v1/responses","POST",headers,body,70)
            out=parse_json_text(extract_text(resp))
            return out,{"response_id":resp.get("id"),"model":resp.get("model",MODEL),"attempt":attempt+1}
        except Exception as exc:
            last=exc
            if attempt==0:
                time.sleep(2)
    raise RuntimeError("OpenAI evaluator failed after one retry: "+repr(last))

def common_validate(d):
    if d.get("decision") not in {"BUY_SCOUT","WAIT","REJECT"}:
        raise ValueError("invalid decision")
    if d.get("setup_lane") not in {"IGNITION","CONTINUITY","EXTENDED","REVERSAL","NONE"}:
        raise ValueError("invalid setup lane")
    if not isinstance(d.get("reason_codes"),list):
        raise ValueError("reason_codes must be list")
    if not isinstance(d.get("missing_triggers"),list) or len(d["missing_triggers"])>2:
        raise ValueError("invalid missing_triggers")
    ttl=d.get("ttl_minutes")
    if not isinstance(ttl,int) or not 0<=ttl<=60:
        raise ValueError("invalid ttl")
    s2ttl=d.get("stage2_ttl_minutes")
    if not isinstance(s2ttl,int) or not 0<=s2ttl<=60:
        raise ValueError("invalid stage2 ttl")

def fail_safe_normalize(d,current):
    common_validate(d)
    d=dict(d)
    if d["decision"]=="BUY_SCOUT":
        stop=d.get("stop_eur")
        trigger=d.get("stage2_trigger_eur")
        s2ttl=d.get("stage2_ttl_minutes")
        valid_stop=isinstance(stop,(int,float)) and 0<stop<current["ask"]
        valid_s2=isinstance(trigger,(int,float)) and trigger>current["ask"] and isinstance(s2ttl,int) and 1<=s2ttl<=60
        if not (valid_stop and valid_s2):
            reasons=list(d.get("reason_codes") or [])
            reasons.append("INVALID_OR_MISSING_TWO_STAGE_PLAN")
            d.update({
                "decision":"WAIT",
                "summary":str(d.get("summary") or "")[:220]+" | Fail-safe WAIT: stop/stage-2 plan incomplete.",
                "reason_codes":reasons[:8],
                "missing_triggers":["Valid structural stop and second-stage confirmation plan"],
                "stop_eur":None,
                "ttl_minutes":max(15,min(60,int(d.get("ttl_minutes") or 30))),
                "stage2_trigger_eur":None,
                "stage2_ttl_minutes":0,
            })
    else:
        d["stop_eur"]=None
        d["stage2_trigger_eur"]=None
        d["stage2_ttl_minutes"]=0
        if d["decision"]=="REJECT":
            d["ttl_minutes"]=0
    return d

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--out",default="paper_decisions")
    a=ap.parse_args()

    control,spec,fingerprint=load_runtime()
    c=json.loads(Path(a.candidate).read_text("utf-8"))
    validate_candidate(c,a.candidate)
    if control.get("enabled") is not True:
        print("PAPER_RUNTIME_DISABLED")
        return
    if int(c["event_ts"]) < int(zdt(control["series_started_at_utc"]).timestamp()):
        print("PAPER_CANDIDATE_BEFORE_ACTIVE_SERIES",c["candidate_id"])
        return

    outdir=Path(a.out)
    outdir.mkdir(parents=True,exist_ok=True)
    target=outdir/(c["candidate_id"]+".json")
    if target.exists():
        print("PAPER_EVAL_IDEMPOTENT",c["candidate_id"])
        return

    evaluation_started_at_utc=utcnow()
    current=kraken_ticker(c["altname"])
    age=max(0,int(time.time())-int(c["event_ts"]))
    external={"not_collected":True}

    if c["pair"] in BLOCKED:
        d={"decision":"REJECT","setup_lane":"NONE","summary":"Pair is blocked by strategy.",
           "reason_codes":["PAIR_BLOCKED"],"missing_triggers":[],"stop_eur":None,"ttl_minutes":0,
           "expected_remaining_move_pct":None,"risk_reward_after_costs":None,
           "stage2_trigger_eur":None,"stage2_ttl_minutes":0}
        api={"response_id":None,"model":None,"attempt":0}
    elif age>3600:
        d={"decision":"REJECT","setup_lane":"NONE","summary":"Candidate is stale for prospective paper entry.",
           "reason_codes":["STALE_OVER_60M"],"missing_triggers":[],"stop_eur":None,"ttl_minutes":0,
           "expected_remaining_move_pct":None,"risk_reward_after_costs":None,
           "stage2_trigger_eur":None,"stage2_ttl_minutes":0}
        api={"response_id":None,"model":None,"attempt":0}
    else:
        external=build_context(c,current)
        raw,api=call_evaluator(c,current,external,spec,control)
        d=fail_safe_normalize(raw,current)

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

    record={
        "schema_version":2,
        "kind":"PAPER_V2_DECISION_V2",
        "test_id":control["test_id"],
        "series_id":control["series_id"],
        "candidate_id":c["candidate_id"],
        "queue_id":c["queue_id"],
        "pair":c["pair"],
        "altname":c["altname"],
        "candidate_event_time_utc":c["event_time_utc"],
        "evaluated_at_utc":evaluation_completed_at_utc,
        "candidate_age_seconds":age,
        "timing":timing,
        "strategy_revision":spec["strategy_revision"],
        "strategy_fingerprint_sha256":fingerprint,
        "prompt_schema_version":PROMPT_SCHEMA_VERSION,
        "real_money_actions_enabled":False,
        "fee_assumption_pct_per_side":FEE_PCT,
        "fresh_kraken_ticker":current,
        "decision_context":external,
        "decision":d,
        "evaluator":api,
        "paper_entry":None,
    }

    if d["decision"]=="BUY_SCOUT":
        paper_eur=float(spec["entry"]["scout_notional_eur"])
        fill=current["ask"]
        qty=paper_eur/fill
        opened=zdt(record["evaluated_at_utc"])
        s2ttl=int(d["stage2_ttl_minutes"])
        record["paper_entry"]={
            "status":"SCOUT_FILLED_SIMULATED_AT_FRESH_ASK",
            "scout_notional_eur":paper_eur,
            "fill_price_eur":fill,
            "quantity":qty,
            "entry_fee_eur":paper_eur*FEE_PCT/100,
            "entry_spread_pct":current["spread_pct"],
            "slippage_model":"fresh best ask; historical spread-aware model applied to later stage/exit where available",
            "stop_eur":d["stop_eur"],
            "opened_at_utc":record["evaluated_at_utc"],
            "stage2_plan":{
                "status":"PENDING",
                "trigger_eur":float(d["stage2_trigger_eur"]),
                "notional_eur":float(spec["entry"]["stage2_notional_eur"]),
                "ttl_minutes":s2ttl,
                "expires_at_utc":(opened+timedelta(minutes=s2ttl)).isoformat().replace("+00:00","Z"),
                "execution_type":"SIMULATED_STOP_BUY_CONFIRMATION"
            }
        }

    target.write_text(json.dumps(record,indent=2,sort_keys=True)+"\n","utf-8")
    print("PAPER_EVAL_RESULT",json.dumps({
        "candidate_id":c["candidate_id"],"series_id":control["series_id"],
        "pair":c["pair"],"decision":d["decision"],
        "response_id":api["response_id"]
    },sort_keys=True))

if __name__=="__main__":
    main()
