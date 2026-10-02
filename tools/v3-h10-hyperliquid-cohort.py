#!/usr/bin/env python3
"""
V3 H10 Hyperliquid public trader cohort selector.

Research-only / public-read-only.
No auth, signer, wallet key, orders, Kraken outcomes or strategy mutation.

Modes:
  --self-test
  --mode smoke   : fetch leaderboard + verify a few deterministic addresses
  --mode select  : execute frozen selection contract and write cohort evidence
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, math, sys, time, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_SPEC=ROOT/"research/v3/h10-trader-cohort-selection-contract-v1.json"
LEADERBOARD="https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
INFO="https://api.hyperliquid.xyz/info"

def fnum(x, default=None):
    try:
        v=float(x)
        return v if math.isfinite(v) else default
    except Exception:
        return default

def perf_map(row):
    out={}
    for item in row.get("windowPerformances",[]) or []:
        if isinstance(item,list) and len(item)==2 and isinstance(item[0],str) and isinstance(item[1],dict):
            out[item[0]]=item[1]
    return out

def metric(row, window, key):
    p=perf_map(row).get(window,{})
    return fnum(p.get(key),0.0)

def addr(row):
    a=str(row.get("ethAddress","")).lower()
    if len(a)==42 and a.startswith("0x"):
        try: int(a[2:],16)
        except Exception: return None
        return a
    return None

def stable_hash(seed,address,control=False):
    s=f"{seed}:{'CONTROL:' if control else ''}{address}".encode()
    return hashlib.sha256(s).hexdigest()

def get_json(url, timeout=75):
    req=urllib.request.Request(url,headers={"User-Agent":"kraken-eur-scanner-v3-h10-research/1"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def post_info(payload, timeout=30):
    body=json.dumps(payload,separators=(",",":")).encode()
    req=urllib.request.Request(INFO,data=body,headers={"Content-Type":"application/json","User-Agent":"kraken-eur-scanner-v3-h10-research/1"},method="POST")
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def parse_rows(blob):
    rows=blob.get("leaderboardRows") if isinstance(blob,dict) else None
    if not isinstance(rows,list):
        raise RuntimeError("leaderboardRows missing/not-list")
    needed={"ethAddress","accountValue","windowPerformances"}
    clean=[]
    for r in rows:
        if isinstance(r,dict) and needed.issubset(r) and addr(r):
            clean.append(r)
    if not clean:
        raise RuntimeError("no valid leaderboard rows")
    return clean

def base_eligible(row,spec):
    b=spec["base_eligibility"]
    av=fnum(row.get("accountValue"),0) or 0
    wv=metric(row,"week","vlm")
    mv=metric(row,"month","vlm")
    mroi=metric(row,"month","roi")
    if av < b["min_account_value_usd"]: return False
    if wv < b["min_week_volume_usd"]: return False
    if mv < b["min_month_volume_usd"]: return False
    if av <= 0 or mv/av > b["max_month_turnover_to_equity"]: return False
    if abs(mroi) > b["max_abs_month_roi_decimal"]: return False
    return True

def positive_count(row):
    return sum(metric(row,w,"pnl")>0 for w in ("week","month","allTime"))

def primary_eligible(row,spec):
    return base_eligible(row,spec) and all(metric(row,w,"pnl")>0 for w in spec["primary_rule"]["required_positive_pnl_windows"])

def control_eligible(row,spec):
    if not base_eligible(row,spec): return False
    n=positive_count(row)
    c=spec["control_rule"]
    return c["positive_window_count_min"] <= n <= c["positive_window_count_max"]

def role_name(x):
    if isinstance(x,dict): return x.get("role")
    if isinstance(x,str): return x
    return None

def portfolio_windows(x):
    if not isinstance(x,list): return set()
    out=set()
    for item in x:
        if isinstance(item,list) and len(item)==2 and isinstance(item[0],str):
            out.add(item[0])
    return out

def verify_address(address,spec, now_ms=None):
    now_ms=now_ms or int(time.time()*1000)
    start=now_ms-int(spec["verification"]["fills_lookback_days"]*86400*1000)
    role=post_info({"type":"userRole","user":address})
    role=role_name(role)
    if role not in spec["base_eligibility"]["allowed_user_roles"]:
        return {"ok":False,"role":role,"reason":"ROLE_NOT_ALLOWED"}
    portfolio=post_info({"type":"portfolio","user":address})
    pwin=sorted(portfolio_windows(portfolio))
    fills=post_info({"type":"userFillsByTime","user":address,"startTime":start,"endTime":now_ms,"aggregateByTime":True})
    if not isinstance(fills,list):
        return {"ok":False,"role":role,"reason":"FILLS_NOT_LIST","portfolio_windows":pwin}
    coins=sorted({str(x.get("coin")) for x in fills if isinstance(x,dict) and x.get("coin")})
    if len(fills) < spec["base_eligibility"]["min_recent_30d_fills"]:
        return {"ok":False,"role":role,"reason":"TOO_FEW_RECENT_FILLS","fills_30d":len(fills),"distinct_coins_30d":len(coins),"portfolio_windows":pwin}
    if len(coins) < spec["base_eligibility"]["min_recent_30d_distinct_coins"]:
        return {"ok":False,"role":role,"reason":"TOO_FEW_DISTINCT_COINS","fills_30d":len(fills),"distinct_coins_30d":len(coins),"portfolio_windows":pwin}
    return {"ok":True,"role":role,"fills_30d":len(fills),"distinct_coins_30d":len(coins),"coins_30d":coins[:50],"portfolio_windows":pwin}

def compact_row(r):
    return {
      "address":addr(r),
      "display_name":r.get("displayName"),
      "account_value_usd":fnum(r.get("accountValue"),0),
      "week":{"pnl":metric(r,"week","pnl"),"roi":metric(r,"week","roi"),"volume":metric(r,"week","vlm")},
      "month":{"pnl":metric(r,"month","pnl"),"roi":metric(r,"month","roi"),"volume":metric(r,"month","vlm")},
      "allTime":{"pnl":metric(r,"allTime","pnl"),"roi":metric(r,"allTime","roi"),"volume":metric(r,"allTime","vlm")},
      "positive_window_count":positive_count(r),
    }

def strata_for(row,spec):
    av=fnum(row.get("accountValue"),0) or 0
    for s in spec["primary_rule"]["account_value_strata"]:
        if av>=s["min"] and (s["max_exclusive"] is None or av<s["max_exclusive"]):
            return s["name"]
    return None

def execute_select(spec, rows):
    seed=spec["selection_seed"]
    primary_candidates=[r for r in rows if primary_eligible(r,spec)]
    control_candidates=[r for r in rows if control_eligible(r,spec)]
    selected=[]
    seen=set()
    verification_log=[]

    # Primary: deterministic within account-value strata, no PnL sorting.
    for st in spec["primary_rule"]["account_value_strata"]:
        pool=[r for r in primary_candidates if strata_for(r,spec)==st["name"]]
        pool.sort(key=lambda r:stable_hash(seed,addr(r)))
        attempts=0
        got=0
        for r in pool:
            if got>=st["quota"] or attempts>=spec["verification"]["max_verification_attempts_per_primary_stratum"]: break
            a=addr(r); attempts+=1
            try: v=verify_address(a,spec)
            except Exception as e: v={"ok":False,"reason":"VERIFY_EXCEPTION","error":type(e).__name__}
            verification_log.append({"address":a,"candidate_role":"PRIMARY","stratum":st["name"],"verification":v})
            if v.get("ok"):
                selected.append({"cohort_role":"PRIMARY","stratum":st["name"],"selection_hash":stable_hash(seed,a),"leaderboard":compact_row(r),"verification":v})
                seen.add(a); got+=1

    # Deterministic global backfill if a stratum did not fill.
    need=spec["target"]["primary_traders"]-sum(x["cohort_role"]=="PRIMARY" for x in selected)
    if need>0:
        pool=[r for r in primary_candidates if addr(r) not in seen]
        pool.sort(key=lambda r:stable_hash(seed,addr(r)))
        for r in pool:
            if need<=0: break
            a=addr(r)
            try: v=verify_address(a,spec)
            except Exception as e: v={"ok":False,"reason":"VERIFY_EXCEPTION","error":type(e).__name__}
            verification_log.append({"address":a,"candidate_role":"PRIMARY_BACKFILL","stratum":strata_for(r,spec),"verification":v})
            if v.get("ok"):
                selected.append({"cohort_role":"PRIMARY","stratum":strata_for(r,spec),"selection_hash":stable_hash(seed,a),"leaderboard":compact_row(r),"verification":v})
                seen.add(a); need-=1

    # Controls: same base activity constraints, not all-three-positive, deterministic hash.
    controls=sorted((r for r in control_candidates if addr(r) not in seen),key=lambda r:stable_hash(seed,addr(r),True))
    cneed=spec["target"]["active_controls"]
    attempts=0
    for r in controls:
        if cneed<=0 or attempts>=spec["verification"]["max_control_verification_attempts"]: break
        a=addr(r); attempts+=1
        try: v=verify_address(a,spec)
        except Exception as e: v={"ok":False,"reason":"VERIFY_EXCEPTION","error":type(e).__name__}
        verification_log.append({"address":a,"candidate_role":"CONTROL","stratum":strata_for(r,spec),"verification":v})
        if v.get("ok"):
            selected.append({"cohort_role":"CONTROL","stratum":strata_for(r,spec),"selection_hash":stable_hash(seed,a,True),"leaderboard":compact_row(r),"verification":v})
            seen.add(a); cneed-=1

    primary=[x for x in selected if x["cohort_role"]=="PRIMARY"]
    ctrl=[x for x in selected if x["cohort_role"]=="CONTROL"]
    status="PASS" if len(primary)==spec["target"]["primary_traders"] and len(ctrl)==spec["target"]["active_controls"] else "INCOMPLETE"
    return {
      "schema_version":1,
      "kind":"V3_H10_TRADER_COHORT_SELECTION_EVIDENCE_V1",
      "trial_id":spec["trial_id"],
      "status":status,
      "generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "selection_seed":seed,
      "leaderboard_rows_total":len(rows),
      "base_eligible_count":sum(base_eligible(r,spec) for r in rows),
      "primary_candidate_count_before_official_verification":len(primary_candidates),
      "control_candidate_count_before_official_verification":len(control_candidates),
      "selected_primary_count":len(primary),
      "selected_control_count":len(ctrl),
      "selected":selected,
      "verification_attempts":len(verification_log),
      "verification_log":verification_log,
      "guardrails":{
        "kraken_outcomes_used_for_selection":False,
        "manual_post_outcome_cherry_pick":False,
        "authentication_used":False,
        "wallet_key_used":False,
        "orders":False,
        "real_money_actions":False,
        "v2r3_changed":False,
        "v2r4_changed":False,
        "active_v3_feature_authorized":False
      }
    }

def self_test():
    def row(a,av,w,m,at,mroi=0.1):
        return {"ethAddress":a,"accountValue":str(av),"windowPerformances":[
          ["week",{"pnl":str(w),"roi":"0.1","vlm":"200000"}],
          ["month",{"pnl":str(m),"roi":str(mroi),"vlm":"2000000"}],
          ["allTime",{"pnl":str(at),"roi":"0.5","vlm":"10000000"}],
        ]}
    spec=json.loads(DEFAULT_SPEC.read_text())
    r1=row("0x"+"1"*40,100000,1,1,1)
    r2=row("0x"+"2"*40,100000,-1,1,1)
    assert primary_eligible(r1,spec)
    assert not control_eligible(r1,spec)
    assert control_eligible(r2,spec)
    assert compact_row(r1)["positive_window_count"]==3
    assert stable_hash("x",addr(r1))==stable_hash("x",addr(r1))
    print("V3_H10_COHORT_SELF_TEST PASS")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--spec",default=str(DEFAULT_SPEC))
    ap.add_argument("--mode",choices=["smoke","select"])
    ap.add_argument("--smoke-count",type=int,default=3)
    ap.add_argument("--output")
    ap.add_argument("--self-test",action="store_true")
    args=ap.parse_args()
    if args.self_test:
        self_test(); return
    if not args.mode or not args.output:
        ap.error("--mode and --output required unless --self-test")
    spec=json.load(open(args.spec,encoding="utf-8"))
    blob=get_json(LEADERBOARD)
    rows=parse_rows(blob)
    if args.mode=="smoke":
        pool=sorted((r for r in rows if base_eligible(r,spec)),key=lambda r:stable_hash(spec["selection_seed"],addr(r)))
        checks=[]
        for r in pool[:max(1,args.smoke_count)]:
            a=addr(r)
            try: v=verify_address(a,spec)
            except Exception as e: v={"ok":False,"reason":"VERIFY_EXCEPTION","error":type(e).__name__,"detail":str(e)[:200]}
            checks.append({"address":a,"leaderboard":compact_row(r),"verification":v})
        out={"schema_version":1,"kind":"V3_H10_PUBLIC_DISCOVERY_VERIFICATION_SMOKE_V1","status":"PASS" if checks and any(x["verification"].get("ok") for x in checks) else "FAIL","leaderboard_rows":len(rows),"checks":checks,
             "guardrails":{"public_read_only":True,"authentication_used":False,"orders":False,"kraken_outcomes_used":False}}
    else:
        out=execute_select(spec,rows)
    Path(args.output).write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:out.get(k) for k in ("kind","status","leaderboard_rows","leaderboard_rows_total","selected_primary_count","selected_control_count","verification_attempts")},sort_keys=True))
    if out.get("status") not in {"PASS","INCOMPLETE"}:
        raise SystemExit(1)
    if args.mode=="select" and out.get("status")!="PASS":
        raise SystemExit("cohort selection incomplete")

if __name__=="__main__":
    main()
