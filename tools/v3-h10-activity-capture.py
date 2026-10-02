#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, urllib.parse, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
COHORT=ROOT/"research/v3/h10-trader-cohort-v1.json"
INFO="https://api.hyperliquid.xyz/info"
BUCKET_MS=5*60*1000
RAW_FILL_RETENTION_HOURS=48
COMPACT_RETENTION_DAYS=120

def num(x):
    try: return float(x)
    except Exception: return None

def post_info(payload,timeout=30):
    body=json.dumps(payload,separators=(",",":")).encode()
    req=urllib.request.Request(
        INFO,data=body,method="POST",
        headers={"Content-Type":"application/json","User-Agent":"kraken-eur-scanner-v3-h10/2"}
    )
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode())

def compact_positions(state):
    out=[]
    for row in state.get("assetPositions",[]) if isinstance(state,dict) else []:
        p=row.get("position",{}) if isinstance(row,dict) else {}
        coin=p.get("coin")
        szi=num(p.get("szi"))
        if not coin or szi is None or abs(szi)<1e-18:
            continue
        lev=p.get("leverage")
        out.append({
          "coin":coin,"szi":szi,"side":"LONG" if szi>0 else "SHORT",
          "entry_px":num(p.get("entryPx")),"position_value":num(p.get("positionValue")),
          "unrealized_pnl":num(p.get("unrealizedPnl")),
          "leverage":lev if isinstance(lev,(str,int,float,dict)) else None
        })
    return sorted(out,key=lambda x:x["coin"])

def event_id(address,f):
    s="|".join([
        address,str(f.get("time","")),str(f.get("coin","")),str(f.get("hash","")),
        str(f.get("oid","")),str(f.get("tid","")),str(f.get("px","")),
        str(f.get("sz","")),str(f.get("dir",""))
    ])
    return hashlib.sha256(s.encode()).hexdigest()

def _server_headers(upsert=False):
    key=(os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not key:
        raise RuntimeError("Supabase server credential missing")
    return {
        "apikey":key,
        "Authorization":"Bearer "+key,
        "Content-Type":"application/json",
        "Prefer":"resolution=merge-duplicates,return=minimal" if upsert else "return=minimal"
    }

def http_post_rows(table,rows,conflict=None):
    if not rows:
        return
    base=os.environ["SUPABASE_URL"].rstrip("/")+"/rest/v1/"+table
    params={}
    if conflict:
        params["on_conflict"]=conflict
    url=base+("?" + urllib.parse.urlencode(params) if params else "")
    req=urllib.request.Request(
        url,
        data=json.dumps(rows,separators=(",",":")).encode(),
        headers=_server_headers(upsert=bool(conflict)),
        method="POST"
    )
    with urllib.request.urlopen(req,timeout=45) as r:
        if r.status not in (200,201,204):
            raise RuntimeError(f"Supabase status {r.status}")

def http_delete_before(table,column,cutoff):
    base=os.environ["SUPABASE_URL"].rstrip("/")+"/rest/v1/"+table
    url=base+"?"+urllib.parse.urlencode({column:"lt."+cutoff.isoformat()})
    req=urllib.request.Request(url,headers=_server_headers(),method="DELETE")
    with urllib.request.urlopen(req,timeout=45) as r:
        if r.status not in (200,204):
            raise RuntimeError(f"Supabase delete status {r.status}")

def signed_notional(fill):
    px=fill.get("px") or 0.0
    sz=fill.get("sz") or 0.0
    notional=abs(px*sz)
    d=str(fill.get("direction") or "").lower()
    side=str(fill.get("side") or "").upper()
    if "open long" in d or "close short" in d:
        return notional
    if "open short" in d or "close long" in d:
        return -notional
    if side=="B":
        return notional
    if side=="A":
        return -notional
    return 0.0

def aggregate_5m(fills,start_ms,end_ms):
    # Only persist complete 5m buckets fully contained in the fetched window.
    first_full=((start_ms+BUCKET_MS-1)//BUCKET_MS)*BUCKET_MS
    buckets={}
    for f in fills:
        tm=int(f["fill_time_ms"])
        b=(tm//BUCKET_MS)*BUCKET_MS
        if b < first_full or b+BUCKET_MS > end_ms:
            continue
        key=(f["cohort_id"],f["address"],f["cohort_role"],f["coin"],b)
        x=buckets.setdefault(key,{
            "cohort_id":f["cohort_id"],"address":f["address"],"cohort_role":f["cohort_role"],
            "coin":f["coin"],"bucket_start":dt.datetime.fromtimestamp(b/1000,dt.timezone.utc).isoformat(),
            "fill_count":0,"first_fill_time":None,"last_fill_time":None,
            "net_exposure_change_quote":0.0,"gross_fill_notional_quote":0.0,
            "closed_pnl_sum":0.0,"fee_sum":0.0
        })
        ft=dt.datetime.fromtimestamp(tm/1000,dt.timezone.utc).isoformat()
        x["fill_count"]+=1
        x["first_fill_time"]=ft if x["first_fill_time"] is None or ft<x["first_fill_time"] else x["first_fill_time"]
        x["last_fill_time"]=ft if x["last_fill_time"] is None or ft>x["last_fill_time"] else x["last_fill_time"]
        px=f.get("px") or 0.0
        sz=f.get("sz") or 0.0
        x["gross_fill_notional_quote"]+=abs(px*sz)
        x["net_exposure_change_quote"]+=signed_notional(f)
        x["closed_pnl_sum"]+=f.get("closed_pnl") or 0.0
        x["fee_sum"]+=f.get("fee") or 0.0
    return list(buckets.values())

def retention_maintenance(now):
    # Exact fills are short-lived diagnostics. Long-term research uses compact 5m aggregates.
    http_delete_before(
        "v3_h10_fill_events","fill_time",
        now-dt.timedelta(hours=RAW_FILL_RETENTION_HOURS)
    )
    http_delete_before(
        "v3_h10_wallet_asset_5m","bucket_start",
        now-dt.timedelta(days=COMPACT_RETENTION_DAYS)
    )
    # Batch deletion cascades to wallet-state snapshots and capture errors.
    http_delete_before(
        "v3_h10_capture_batches","observed_at",
        now-dt.timedelta(days=COMPACT_RETENTION_DAYS)
    )

def capture(max_wallets=None,dry_run=False,path="GITHUB_BOOTSTRAP_30M"):
    cohort=json.loads(COHORT.read_text())
    traders=cohort["traders"][:max_wallets] if max_wallets else cohort["traders"]
    now=dt.datetime.now(dt.timezone.utc)
    observed=now.isoformat()
    start_ms=int((now-dt.timedelta(minutes=45)).timestamp()*1000)
    end_ms=int(now.timestamp()*1000)
    batch_id="h10-"+hashlib.sha256(f'{cohort["cohort_id"]}|{observed}|{path}'.encode()).hexdigest()[:24]
    states=[]; fills=[]; errors=[]
    for t in traders:
        a=t["address"]
        try:
            st=post_info({"type":"clearinghouseState","user":a})
            fs=post_info({
                "type":"userFillsByTime","user":a,
                "startTime":start_ms,"endTime":end_ms,"aggregateByTime":True
            })
            if not isinstance(st,dict):
                raise RuntimeError("clearinghouseState not dict")
            if not isinstance(fs,list):
                raise RuntimeError("userFillsByTime not list")
            m=st.get("marginSummary") or {}
            pos=compact_positions(st)
            states.append({
              "batch_id":batch_id,"cohort_id":cohort["cohort_id"],"observed_at":observed,
              "address":a,"cohort_role":t["role"],"account_value":num(m.get("accountValue")),
              "total_ntl_pos":num(m.get("totalNtlPos")),"total_margin_used":num(m.get("totalMarginUsed")),
              "withdrawable":num(st.get("withdrawable")),"source_time_ms":st.get("time"),
              "positions":pos,"position_count":len(pos)
            })
            for f in fs:
                if not isinstance(f,dict) or not f.get("coin") or not f.get("time"):
                    continue
                tm=int(f["time"])
                fills.append({
                  "event_id":event_id(a,f),"cohort_id":cohort["cohort_id"],"address":a,"cohort_role":t["role"],
                  "coin":str(f["coin"]),"fill_time":dt.datetime.fromtimestamp(tm/1000,dt.timezone.utc).isoformat(),
                  "fill_time_ms":tm,"direction":f.get("dir"),"side":f.get("side"),
                  "px":num(f.get("px")),"sz":num(f.get("sz")),"closed_pnl":num(f.get("closedPnl")),
                  "crossed":f.get("crossed"),"fee":num(f.get("fee")),"fee_token":f.get("feeToken"),
                  "tx_hash":f.get("hash"),
                  "oid":str(f.get("oid")) if f.get("oid") is not None else None,
                  "tid":str(f.get("tid")) if f.get("tid") is not None else None,
                  "first_seen_batch_id":batch_id,
                  "raw_compact":{"dir":f.get("dir"),"startPosition":f.get("startPosition")}
                })
        except Exception as e:
            errors.append({
                "batch_id":batch_id,"address":a,"cohort_role":t["role"],
                "error_class":type(e).__name__,"detail":str(e)[:300]
            })

    aggregates=aggregate_5m(fills,start_ms,end_ms)
    batch=[{
        "batch_id":batch_id,"cohort_id":cohort["cohort_id"],"observed_at":observed,
        "capture_path":path,"wallet_count":len(traders),"success_count":len(states),
        "error_count":len(errors),"fill_events_seen":len(fills),
        "public_read_only":True,"orders":False,"active_strategy_changed":False
    }]
    result={
        "batch_id":batch_id,"wallets":len(traders),"success":len(states),"errors":len(errors),
        "fills_seen":len(fills),"aggregates_5m":len(aggregates),
        "raw_fill_retention_hours":RAW_FILL_RETENTION_HOURS,
        "compact_retention_days":COMPACT_RETENTION_DAYS,
        "dry_run":dry_run
    }
    if not dry_run:
        http_post_rows("v3_h10_capture_batches",batch)
        http_post_rows("v3_h10_wallet_states",states)
        for i in range(0,len(fills),200):
            http_post_rows("v3_h10_fill_events",fills[i:i+200],conflict="event_id")
        for i in range(0,len(aggregates),200):
            http_post_rows(
                "v3_h10_wallet_asset_5m",aggregates[i:i+200],
                conflict="cohort_id,address,coin,bucket_start"
            )
        http_post_rows("v3_h10_capture_errors",errors)
        retention_maintenance(now)
    return result

def self_test():
    sample={"assetPositions":[
        {"position":{"coin":"BTC","szi":"1.5","entryPx":"100","positionValue":"150",
                     "unrealizedPnl":"5","leverage":{"type":"cross","value":3}}},
        {"position":{"coin":"ETH","szi":"0"}}
    ]}
    x=compact_positions(sample)
    assert len(x)==1 and x[0]["coin"]=="BTC" and x[0]["side"]=="LONG"
    assert len(event_id("0x"+"1"*40,{"time":1,"coin":"BTC","px":"1","sz":"2"}))==64
    cohort=json.loads(COHORT.read_text())
    assert cohort["primary_count"]==20 and cohort["control_count"]==6

    start=600000
    end=1200000
    fills=[
      {"cohort_id":"c","address":"a","cohort_role":"PRIMARY","coin":"BTC","fill_time_ms":610000,
       "fill_time":"","direction":"Open Long","side":"B","px":100.0,"sz":2.0,"closed_pnl":0.0,"fee":0.1},
      {"cohort_id":"c","address":"a","cohort_role":"PRIMARY","coin":"BTC","fill_time_ms":620000,
       "fill_time":"","direction":"Open Short","side":"A","px":100.0,"sz":1.0,"closed_pnl":0.0,"fee":0.1}
    ]
    agg=aggregate_5m(fills,start,end)
    assert len(agg)==1
    assert agg[0]["fill_count"]==2
    assert abs(agg[0]["gross_fill_notional_quote"]-300.0)<1e-9
    assert abs(agg[0]["net_exposure_change_quote"]-100.0)<1e-9
    print("V3_H10_CAPTURE_SELF_TEST PASS compact-5m/retention")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--self-test",action="store_true")
    ap.add_argument("--dry-run",action="store_true")
    ap.add_argument("--max-wallets",type=int)
    ap.add_argument("--path",default="GITHUB_BOOTSTRAP_30M")
    args=ap.parse_args()
    if args.self_test:
        self_test()
        return
    r=capture(args.max_wallets,args.dry_run,args.path)
    print(json.dumps(r,sort_keys=True))
    if r["success"] < max(1,int(r["wallets"]*0.8)):
        raise SystemExit("H10 capture below 80% wallet success")

if __name__=="__main__":
    main()
