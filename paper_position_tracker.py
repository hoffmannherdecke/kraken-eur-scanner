#!/usr/bin/env python3
"""Paper-only position lifecycle tracker with explicit market-data quality gates."""
from __future__ import annotations
import hashlib, json, math, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
FEE_PCT=0.60
FEE=FEE_PCT/100.0

def zdt(s):
    return datetime.fromisoformat(str(s).replace("Z","+00:00"))

def iso_ts(ts):
    return datetime.fromtimestamp(ts,tz=timezone.utc).isoformat().replace("+00:00","Z")

def http_json(url):
    req=urllib.request.Request(url,headers={"User-Agent":"paper-position-tracker/3.0","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=30) as r:
        return json.loads(r.read().decode())

def ohlc1(altname,since):
    q=urllib.parse.urlencode({"pair":altname,"interval":1,"since":max(0,int(since))})
    d=http_json("https://api.kraken.com/0/public/OHLC?"+q)
    if d.get("error"):
        raise RuntimeError("Kraken OHLC: "+repr(d["error"]))
    rows=next(v for k,v in d["result"].items() if k!="last")
    now=time.time()
    return [
        {"start":int(float(r[0])),"open":float(r[1]),"high":float(r[2]),
         "low":float(r[3]),"close":float(r[4]),"volume":float(r[6])}
        for r in rows if int(float(r[0]))+60<=now
    ]

def spreads(altname,since):
    q=urllib.parse.urlencode({"pair":altname,"since":max(0,int(since))})
    try:
        d=http_json("https://api.kraken.com/0/public/Spread?"+q)
        if d.get("error"):
            return []
        rows=next(v for k,v in d["result"].items() if k!="last")
        return [{"ts":float(r[0]),"bid":float(r[1]),"ask":float(r[2])} for r in rows]
    except Exception:
        return []

def nearest_spread(rows,ts,max_distance=90):
    if not rows:
        return None
    row=min(rows,key=lambda x:abs(x["ts"]-ts))
    return row if abs(row["ts"]-ts)<=max_distance else None

def trailing_rule(entry,peak):
    gain=(peak/entry-1.0)*100.0
    eps=1e-9
    if gain>=15.0-eps: return 2.0
    if gain>=12.0-eps: return 3.0
    if gain>=7.0-eps: return 4.0
    return None

def lifecycle_code_fingerprint():
    h=hashlib.sha256()
    for rel in ("paper_position_tracker.py","paper_strategy_spec.json"):
        p=ROOT/rel
        h.update(rel.encode("utf-8")+b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()

def source_buys(control):
    series_id=control["series_id"]
    found={}
    for dirname in ("paper_decisions","paper_revalidations"):
        d=ROOT/dirname
        if not d.exists():
            continue
        for p in d.glob("*.json"):
            try: rec=json.loads(p.read_text("utf-8"))
            except Exception: continue
            if rec.get("series_id")!=series_id: continue
            if rec.get("decision",{}).get("decision")!="BUY_SCOUT" or not rec.get("paper_entry"): continue
            cid=rec["candidate_id"]
            old=found.get(cid)
            opened=zdt(rec["paper_entry"]["opened_at_utc"])
            if old is None or zdt(old["paper_entry"]["opened_at_utc"])<opened:
                found[cid]=rec
    return found

def aggregate(state):
    legs=[x for x in state["legs"] if x.get("status")=="FILLED"]
    qty=sum(float(x["quantity"]) for x in legs)
    notional=sum(float(x["notional_eur"]) for x in legs)
    fees=sum(float(x["fee_eur"]) for x in legs)
    weighted=(sum(float(x["fill_price_eur"])*float(x["quantity"]) for x in legs)/qty) if qty else None
    state["position_quantity"]=qty
    state["entry_notional_eur"]=notional
    state["entry_fee_total_eur"]=fees
    state["weighted_entry_eur"]=weighted
    return qty,notional,fees,weighted

def new_state(rec,max_hold_hours):
    e=rec["paper_entry"]
    entry=float(e["fill_price_eur"])
    initial=float(e["stop_eur"])
    opened=zdt(e["opened_at_utc"])
    stage2=dict(e.get("stage2_plan") or {})
    if stage2: stage2.setdefault("status","PENDING")
    state={
        "schema_version":3,"kind":"PAPER_POSITION_V3",
        "test_id":rec["test_id"],"series_id":rec["series_id"],
        "candidate_id":rec["candidate_id"],"pair":rec["pair"],
        "altname":rec.get("altname") or rec["pair"].replace("/",""),
        "source_kind":rec["kind"],"strategy_revision":rec.get("strategy_revision"),
        "strategy_fingerprint_sha256":rec.get("strategy_fingerprint_sha256"),
        "runtime_code_sha":rec.get("runtime_code_sha"),
        "runtime_code_fingerprint_sha256":rec.get("runtime_code_fingerprint_sha256"),
        "lifecycle_code_fingerprint_sha256":lifecycle_code_fingerprint(),
        "status":"OPEN","real_money_actions_enabled":False,
        "fee_assumption_pct_per_side":FEE_PCT,
        "opened_at_utc":e["opened_at_utc"],
        "max_hold_hours":max_hold_hours,
        "max_hold_at_utc":iso_ts(opened.timestamp()+max_hold_hours*3600),
        "legs":[{
            "kind":"SCOUT","status":"FILLED","filled_at_utc":e["opened_at_utc"],
            "fill_price_eur":entry,"quantity":float(e["quantity"]),
            "notional_eur":float(e["scout_notional_eur"]),"fee_eur":float(e["entry_fee_eur"]),
            "execution_quality":"FRESH_KRAKEN_BEST_ASK","spread_pct":e.get("entry_spread_pct")
        }],
        "stage2_plan":stage2 or None,
        "initial_stop_eur":initial,"active_stop_eur":initial,
        "peak_price_eur":entry,"max_gain_pct":0.0,"min_seen_price_eur":entry,
        "trail_distance_pct":None,"last_processed_bar_start_utc":None,
        "stale_position_review_due":False,
        "data_quality":{"status":"VERIFIED","reason":None,"gap":None},
        "events":[{"type":"SCOUT_OPENED","at_utc":e["opened_at_utc"],"price_eur":entry,"stop_eur":initial}],
        "exit":None,
    }
    aggregate(state)
    return state

def mark_unverified(state,expected,observed,reason):
    state["status"]="UNVERIFIED"
    state["data_quality"]={
        "status":"UNVERIFIED_DATA_GAP","reason":reason,
        "gap":{"expected_bar_start_utc":iso_ts(expected) if expected else None,
               "observed_bar_start_utc":iso_ts(observed) if observed else None}
    }
    state["events"].append({
        "type":"DATA_GAP_UNVERIFIED","at_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "reason":reason,"expected_bar_start_utc":iso_ts(expected) if expected else None,
        "observed_bar_start_utc":iso_ts(observed) if observed else None,
    })

def close_state(state,bar,fill,spread,reason,fill_model):
    qty,entry_notional,entry_fees,weighted=aggregate(state)
    exit_notional=qty*fill
    exit_fee=exit_notional*FEE
    net=exit_notional-entry_notional-entry_fees-exit_fee
    closed_at=iso_ts(bar["start"]+60)
    state["status"]="CLOSED"
    state["exit"]={
        "reason":reason,"closed_at_utc":closed_at,
        "trigger_bar_start_utc":iso_ts(bar["start"]),
        "fill_price_eur":fill,"exit_fee_eur":exit_fee,
        "entry_notional_eur":entry_notional,"entry_fee_total_eur":entry_fees,
        "gross_pnl_eur":exit_notional-entry_notional,"net_pnl_eur":net,
        "gross_return_pct":((fill/weighted)-1.0)*100.0 if weighted else None,
        "net_return_pct":net/entry_notional*100.0 if entry_notional else None,
        "execution_quality":"HISTORICAL_KRAKEN_BID" if spread else "CONSERVATIVE_OHLC_FALLBACK",
        "spread_observation":spread,"fill_model":fill_model,
    }
    state["events"].append({"type":"CLOSED","at_utc":closed_at,"reason":reason,
                            "fill_price_eur":fill,"net_pnl_eur":net})

def process_state(state,stale_hours,max_hold_hours):
    if state["status"]!="OPEN":
        return False
    opened=zdt(state["opened_at_utc"]).timestamp()
    first_start=math.ceil(opened/60.0)*60
    last=state.get("last_processed_bar_start_utc")
    last_ts=zdt(last).timestamp() if last else first_start-60
    rows=ohlc1(state["altname"],last_ts-60)
    rows=[r for r in rows if r["start"]>=first_start and r["start"]>last_ts]
    expected_first=int(max(first_start,last_ts+60))

    if not rows:
        state["stale_position_review_due"]=(time.time()-opened)>=stale_hours*3600
        return False

    if rows[0]["start"]!=expected_first:
        mark_unverified(state,expected_first,rows[0]["start"],"missing first expected 1m bar")
        return True
    for a,b in zip(rows,rows[1:]):
        if b["start"]-a["start"]!=60:
            mark_unverified(state,a["start"]+60,b["start"],"non-contiguous 1m OHLC coverage")
            return True

    spread_rows=spreads(state["altname"],last_ts-120)
    changed=False
    active=float(state["active_stop_eur"])
    peak=float(state["peak_price_eur"])
    min_seen=float(state.get("min_seen_price_eur",state["weighted_entry_eur"]))
    tier=state.get("trail_distance_pct")
    max_hold_ts=opened+max_hold_hours*3600

    for bar in rows:
        qty,entry_notional,entry_fees,weighted=aggregate(state)
        min_seen=min(min_seen,bar["low"])

        # Conservative ordering: an already-active stop wins before any same-bar
        # stage-2 trigger, time exit or new trailing high.
        if qty>0 and bar["low"]<=active:
            spread=nearest_spread(spread_rows,bar["start"]+30)
            fallback=min(active,bar["open"])
            fill=min(fallback,spread["bid"]) if spread else fallback
            reason="TRAILING_STOP" if active>float(state["initial_stop_eur"])*(1+1e-12) else "INITIAL_STOP"
            close_state(state,bar,fill,spread,reason,
                        "stop market; worse of active stop/bar open and no better than historical bid when available")
            state["last_processed_bar_start_utc"]=iso_ts(bar["start"])
            changed=True
            break

        s2=state.get("stage2_plan")
        if s2 and s2.get("status")=="PENDING":
            expiry=zdt(s2["expires_at_utc"]).timestamp()
            trigger=float(s2["trigger_eur"])
            if bar["start"]>=expiry:
                s2["status"]="EXPIRED"; s2["expired_at_utc"]=iso_ts(expiry)
                state["events"].append({"type":"STAGE2_EXPIRED","at_utc":iso_ts(expiry)})
                changed=True
            elif bar["start"]<expiry<bar["start"]+60 and bar["high"]>=trigger:
                # Trigger-vs-expiry ordering is unknowable from a 1m candle.
                # Never assume the favorable ordering.
                s2["status"]="EXPIRED_AMBIGUOUS"
                s2["expired_at_utc"]=iso_ts(expiry)
                state["events"].append({
                    "type":"STAGE2_EXPIRED_AMBIGUOUS","at_utc":iso_ts(expiry),
                    "trigger_eur":trigger,"bar_start_utc":iso_ts(bar["start"])
                })
                changed=True
            elif bar["start"]+60<=expiry and bar["high"]>=trigger:
                spread=nearest_spread(spread_rows,bar["start"]+30)
                fill=max(trigger,bar["open"],spread["ask"] if spread else 0.0)
                notional=float(s2["notional_eur"]); qty2=notional/fill; fee=notional*FEE
                state["legs"].append({
                    "kind":"STAGE2","status":"FILLED","filled_at_utc":iso_ts(bar["start"]+60),
                    "fill_price_eur":fill,"quantity":qty2,"notional_eur":notional,"fee_eur":fee,
                    "execution_quality":"HISTORICAL_KRAKEN_ASK" if spread else "CONSERVATIVE_OHLC_FALLBACK",
                    "spread_observation":spread
                })
                s2.update({"status":"FILLED","filled_at_utc":iso_ts(bar["start"]+60),"fill_price_eur":fill})
                state["events"].append({"type":"STAGE2_FILLED","at_utc":s2["filled_at_utc"],
                                        "fill_price_eur":fill,"notional_eur":notional})
                aggregate(state); changed=True

        # Finite paper sample: exit at the first complete minute ending at/after
        # the 72h (configurable) hard horizon if no stop closed the trade first.
        if bar["start"]+60>=max_hold_ts:
            spread=nearest_spread(spread_rows,bar["start"]+60)
            fill=min(bar["close"],spread["bid"]) if spread else bar["close"]
            close_state(state,bar,fill,spread,f"TIME_EXIT_{int(max_hold_hours)}H",
                        "time exit at complete 1m close, no better than historical bid when available")
            state["last_processed_bar_start_utc"]=iso_ts(bar["start"])
            changed=True
            break

        qty,entry_notional,entry_fees,weighted=aggregate(state)
        if bar["high"]>peak:
            peak=bar["high"]
            new_tier=trailing_rule(weighted,peak) if weighted else None
            if new_tier is not None:
                candidate=peak*(1.0-new_tier/100.0)
                if candidate>active: active=candidate
                if new_tier!=tier:
                    tier=new_tier
                    state["events"].append({
                        "type":"TRAIL_TIER","at_utc":iso_ts(bar["start"]+60),
                        "peak_price_eur":peak,"trail_distance_pct":tier,"active_stop_eur":active
                    })
            changed=True
        state["last_processed_bar_start_utc"]=iso_ts(bar["start"])

    qty,entry_notional,entry_fees,weighted=aggregate(state)
    state["peak_price_eur"]=peak
    state["max_gain_pct"]=((peak/weighted)-1.0)*100.0 if weighted else None
    state["min_seen_price_eur"]=min_seen
    state["active_stop_eur"]=active
    state["trail_distance_pct"]=tier
    state["open_age_hours"]=round((time.time()-opened)/3600.0,3)
    state["stale_position_review_due"]=state["status"]=="OPEN" and state["open_age_hours"]>=stale_hours
    if state["status"]=="OPEN":
        state["data_quality"]={"status":"VERIFIED","reason":None,"gap":None}
    return changed

def main():
    control=json.loads((ROOT/"paper_runtime_control.json").read_text("utf-8"))
    if control.get("enabled") is not True:
        print("PAPER_RUNTIME_DISABLED"); return
    spec=json.loads((ROOT/"paper_strategy_spec.json").read_text("utf-8"))
    stale_hours=float(spec["exit"].get("stale_position_review_hours",24))
    max_hold_hours=float(spec["exit"].get("max_hold_hours",72))
    out=ROOT/"paper_positions"; out.mkdir(exist_ok=True)
    buys=source_buys(control); changed=0

    for cid,rec in sorted(buys.items()):
        p=out/(cid+".json")
        state=json.loads(p.read_text("utf-8")) if p.exists() else new_state(rec,max_hold_hours)
        if not p.exists(): changed+=1
        if process_state(state,stale_hours,max_hold_hours): changed+=1
        p.write_text(json.dumps(state,indent=2,sort_keys=True)+"\n","utf-8")

    closed=open_count=stale=unverified=0; pnl=0.0
    for p in out.glob("*.json"):
        try: s=json.loads(p.read_text("utf-8"))
        except Exception: continue
        if s.get("series_id")!=control["series_id"]: continue
        if s.get("status")=="CLOSED":
            closed+=1; pnl+=float(s.get("exit",{}).get("net_pnl_eur") or 0)
        elif s.get("status")=="OPEN":
            open_count+=1; stale+=1 if s.get("stale_position_review_due") else 0
        elif s.get("status")=="UNVERIFIED":
            unverified+=1

    print("PAPER_POSITION_SUMMARY",json.dumps({
        "series_id":control["series_id"],"source_buys":len(buys),
        "open_positions":open_count,"closed_trades":closed,"unverified_positions":unverified,
        "stale_open_positions":stale,
        "target_closed_trades":int(control.get("target_completed_paper_trades",20)),
        "net_pnl_eur":round(pnl,4),"files_changed_or_advanced":changed
    },sort_keys=True))

if __name__=="__main__":
    main()
