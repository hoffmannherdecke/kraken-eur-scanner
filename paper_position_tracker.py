#!/usr/bin/env python3
"""Paper-only position lifecycle tracker using compact Kraken public 1m OHLC."""
from __future__ import annotations
import json, math, time, urllib.parse, urllib.request
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
    req=urllib.request.Request(url,headers={"User-Agent":"paper-position-tracker/1.0","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=30) as r:
        return json.loads(r.read().decode())

def ohlc1(altname,since):
    q=urllib.parse.urlencode({"pair":altname,"interval":1,"since":max(0,int(since))})
    d=http_json("https://api.kraken.com/0/public/OHLC?"+q)
    if d.get("error"):
        raise RuntimeError("Kraken OHLC: "+repr(d["error"]))
    rows=next(v for k,v in d["result"].items() if k!="last")
    now=time.time()
    out=[]
    for r in rows:
        start=int(float(r[0]))
        if start+60>now:
            continue
        out.append({
            "start":start,"open":float(r[1]),"high":float(r[2]),
            "low":float(r[3]),"close":float(r[4]),"volume":float(r[6])
        })
    return out

def trailing_rule(entry,peak):
    gain=(peak/entry-1.0)*100.0
    if gain>=15.0:
        return 2.0
    if gain>=12.0:
        return 3.0
    if gain>=7.0:
        return 4.0
    return None

def source_buys(control):
    start=zdt(control["series_started_at_utc"])
    found={}
    for dirname in ("paper_decisions","paper_revalidations"):
        d=ROOT/dirname
        if not d.exists():
            continue
        for p in d.glob("*.json"):
            try:
                rec=json.loads(p.read_text("utf-8"))
            except Exception:
                continue
            if rec.get("test_id")!=control.get("test_id"):
                continue
            if rec.get("decision",{}).get("decision")!="BUY_SCOUT" or not rec.get("paper_entry"):
                continue
            opened=zdt(rec["paper_entry"]["opened_at_utc"])
            if opened<start:
                continue
            cid=rec["candidate_id"]
            old=found.get(cid)
            if old is None or zdt(old["paper_entry"]["opened_at_utc"])<opened:
                found[cid]=rec
    return found

def candidate_altname(candidate_id,pair):
    p=ROOT/"handoff_queue"/(candidate_id+".json")
    if p.exists():
        try:
            return json.loads(p.read_text("utf-8")).get("altname") or pair.replace("/","")
        except Exception:
            pass
    return pair.replace("/","")

def new_state(rec):
    e=rec["paper_entry"]
    entry=float(e["fill_price_eur"])
    initial=float(e["stop_eur"])
    return {
        "schema_version":1,
        "kind":"PAPER_POSITION_V1",
        "test_id":rec["test_id"],
        "candidate_id":rec["candidate_id"],
        "pair":rec["pair"],
        "altname":candidate_altname(rec["candidate_id"],rec["pair"]),
        "source_kind":rec["kind"],
        "status":"OPEN",
        "real_money_actions_enabled":False,
        "fee_assumption_pct_per_side":FEE_PCT,
        "entry":{
            "opened_at_utc":e["opened_at_utc"],
            "fill_price_eur":entry,
            "quantity":float(e["quantity"]),
            "notional_eur":float(e["notional_eur"]),
            "entry_fee_eur":float(e["entry_fee_eur"]),
        },
        "initial_stop_eur":initial,
        "active_stop_eur":initial,
        "peak_price_eur":entry,
        "max_gain_pct":0.0,
        "min_seen_price_eur":entry,
        "trail_distance_pct":None,
        "last_processed_bar_start_utc":None,
        "events":[{"type":"OPENED","at_utc":e["opened_at_utc"],"price_eur":entry,"stop_eur":initial}],
        "exit":None,
    }

def process_state(state):
    if state["status"]!="OPEN":
        return False
    opened=zdt(state["entry"]["opened_at_utc"]).timestamp()
    first_start=math.ceil(opened/60.0)*60
    last=state.get("last_processed_bar_start_utc")
    last_ts=zdt(last).timestamp() if last else first_start-60
    rows=ohlc1(state["altname"],last_ts-60)
    rows=[r for r in rows if r["start"]>=first_start and r["start"]>last_ts]
    if not rows:
        return False

    changed=False
    entry=float(state["entry"]["fill_price_eur"])
    qty=float(state["entry"]["quantity"])
    initial=float(state["initial_stop_eur"])
    peak=float(state["peak_price_eur"])
    active=float(state["active_stop_eur"])
    min_seen=float(state.get("min_seen_price_eur",entry))
    tier=state.get("trail_distance_pct")

    for bar in rows:
        # Conservative intrabar ordering: an already-active stop is checked
        # before crediting a new high from the same 1m candle.
        min_seen=min(min_seen,bar["low"])
        if bar["low"]<=active:
            exit_price=bar["open"] if bar["open"]<active else active
            exit_notional=qty*exit_price
            exit_fee=exit_notional*FEE
            entry_notional=float(state["entry"]["notional_eur"])
            entry_fee=float(state["entry"]["entry_fee_eur"])
            gross=(exit_price-entry)*qty
            net=gross-entry_fee-exit_fee
            reason="TRAILING_STOP" if active>initial*(1+1e-12) else "INITIAL_STOP"
            closed_at=iso_ts(bar["start"]+60)
            state["status"]="CLOSED"
            state["exit"]={
                "reason":reason,
                "closed_at_utc":closed_at,
                "trigger_bar_start_utc":iso_ts(bar["start"]),
                "fill_price_eur":exit_price,
                "exit_fee_eur":exit_fee,
                "gross_pnl_eur":gross,
                "net_pnl_eur":net,
                "gross_return_pct":(exit_price/entry-1.0)*100.0,
                "net_return_pct":net/entry_notional*100.0,
                "fill_model":"active_stop_or_worse_bar_open_if_gapped; 1m Kraken public OHLC",
            }
            state["events"].append({"type":"CLOSED","at_utc":closed_at,"reason":reason,
                                    "fill_price_eur":exit_price,"net_pnl_eur":net})
            state["last_processed_bar_start_utc"]=iso_ts(bar["start"])
            changed=True
            break

        if bar["high"]>peak:
            peak=bar["high"]
            new_tier=trailing_rule(entry,peak)
            if new_tier is not None:
                candidate=peak*(1.0-new_tier/100.0)
                if candidate>active:
                    active=max(active,candidate)
                if new_tier!=tier:
                    tier=new_tier
                    state["events"].append({
                        "type":"TRAIL_TIER",
                        "at_utc":iso_ts(bar["start"]+60),
                        "peak_price_eur":peak,
                        "trail_distance_pct":tier,
                        "active_stop_eur":active,
                    })
            changed=True

        state["last_processed_bar_start_utc"]=iso_ts(bar["start"])

    state["peak_price_eur"]=peak
    state["max_gain_pct"]=(peak/entry-1.0)*100.0
    state["min_seen_price_eur"]=min_seen
    state["active_stop_eur"]=active
    state["trail_distance_pct"]=tier
    return True

def main():
    control=json.loads((ROOT/"paper_runtime_control.json").read_text("utf-8"))
    if control.get("enabled") is not True:
        print("PAPER_RUNTIME_DISABLED")
        return
    out=ROOT/"paper_positions"
    out.mkdir(exist_ok=True)
    buys=source_buys(control)
    changed=0
    for cid,rec in sorted(buys.items()):
        p=out/(cid+".json")
        if p.exists():
            state=json.loads(p.read_text("utf-8"))
        else:
            state=new_state(rec)
            changed+=1
        if process_state(state):
            changed+=1
        p.write_text(json.dumps(state,indent=2,sort_keys=True)+"\n","utf-8")

    closed=0
    opened=0
    pnl=0.0
    for p in out.glob("*.json"):
        try:
            s=json.loads(p.read_text("utf-8"))
        except Exception:
            continue
        if s.get("test_id")!=control.get("test_id"):
            continue
        if zdt(s["entry"]["opened_at_utc"])<zdt(control["series_started_at_utc"]):
            continue
        if s.get("status")=="CLOSED":
            closed+=1
            pnl+=float(s.get("exit",{}).get("net_pnl_eur") or 0)
        elif s.get("status")=="OPEN":
            opened+=1
    print("PAPER_POSITION_SUMMARY",json.dumps({
        "source_buys":len(buys),"open_positions":opened,"closed_trades":closed,
        "target_closed_trades":int(control.get("target_completed_paper_trades",20)),
        "net_pnl_eur":round(pnl,4),"files_changed_or_advanced":changed,
    },sort_keys=True))

if __name__=="__main__":
    main()
