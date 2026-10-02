#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,urllib.request,urllib.parse
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
UA="kraken-eur-scanner-v3-h11-state-capture/1.0"
DISCOVERY="https://gamma-api.polymarket.com/markets/keyset?closed=false&limit=5"

def now()->str:return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def get(url:str,timeout:float=20.0)->Any:
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))
def toks(m:dict[str,Any])->list[str]:
    raw=m.get("clobTokenIds")
    if isinstance(raw,str):
        try: raw=json.loads(raw)
        except Exception:return []
    return [str(x) for x in raw] if isinstance(raw,list) else []
def best(levels:list[dict[str,Any]],side:str)->float|None:
    vals=[]
    for x in levels:
        try: vals.append(float(x["price"]))
        except Exception: pass
    if not vals:return None
    return max(vals) if side=="bid" else min(vals)
def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--output",type=Path);a=ap.parse_args()
    t=now();page=get(DISCOVERY)
    ms=(page.get("markets") if isinstance(page,dict) else None) or (page.get("items") if isinstance(page,dict) else None)
    if not isinstance(ms,list) or not ms:raise SystemExit("market discovery empty/unexpected")
    out_rows=[]
    for x in ms[:5]:
        if not isinstance(x,dict):continue
        mid=str(x.get("id") or "")
        if not mid:continue
        try:m=get("https://gamma-api.polymarket.com/markets/"+urllib.parse.quote(mid,safe=""))
        except Exception as e:
            out_rows.append({"market_id":mid,"retrieved_at_utc":t,"status":"MARKET_DETAIL_ERROR","missing_reason":type(e).__name__});continue
        ids=toks(m)
        row={"market_id":mid,"market_slug":m.get("slug"),"question":m.get("question"),"condition_id":m.get("conditionId"),
             "retrieved_at_utc":t,"yes_token_id":ids[0] if len(ids)>0 else None,"no_token_id":ids[1] if len(ids)>1 else None,
             "tokens":[]}
        for token in ids[:2]:
            q=urllib.parse.urlencode({"token_id":token})
            tr={"token_id":token}
            try:
                b=get("https://clob.polymarket.com/book?"+q);mp=get("https://clob.polymarket.com/midpoint?"+q);sp=get("https://clob.polymarket.com/spread?"+q)
                bids=b.get("bids") if isinstance(b,dict) else None;asks=b.get("asks") if isinstance(b,dict) else None
                if not isinstance(bids,list) or not isinstance(asks,list):raise RuntimeError("book_shape")
                tr.update({"status":"CAPTURED","book_timestamp":b.get("timestamp"),"book_hash":b.get("hash"),
                    "best_bid":best(bids,"bid"),"best_ask":best(asks,"ask"),
                    "midpoint":float(mp.get("mid") if "mid" in mp else mp.get("midpoint") if "midpoint" in mp else mp.get("price")),
                    "spread":float(sp["spread"]),"bid_level_count":len(bids),"ask_level_count":len(asks),"missing_reason":None})
            except Exception as e:
                tr.update({"status":"MISSING_OR_ERROR","missing_reason":type(e).__name__})
            row["tokens"].append(tr)
        if not ids:row["missing_reason"]="NO_CLOB_TOKEN_IDS"
        out_rows.append(row)
    captured=sum(1 for r in out_rows for tkn in r.get("tokens",[]) if tkn.get("status")=="CAPTURED")
    out={"schema_version":1,"kind":"V3_H11_POLYMARKET_PROSPECTIVE_STATE_CAPTURE_V1","status":"PASS" if out_rows else "FAIL",
         "retrieved_at_utc":t,"selection_rule":"FIRST_5_ACTIVE_GAMMA_KEYSET_RESPONSE_ORDER","market_count":len(out_rows),
         "captured_token_states":captured,"rows":out_rows,
         "interpretation":{"source_data_quality_only":True,"outcome_joined":False,"surprise_score_created":False,"predictive_conclusion_allowed":False},
         "guardrails":{"public_read_only":True,"authentication_used":False,"wallet_used":False,"orders":False,"automatic_schedule_enabled":False,
                       "active_v2r3_changed":False,"v2r4_changed":False,"real_money_actions":False}}
    raw=json.dumps(out,indent=2,sort_keys=True)+"\n"
    if a.output:a.output.write_text(raw,"utf-8")
    print("V3_H11_STATE_CAPTURE "+json.dumps({"status":out["status"],"market_count":out["market_count"],"captured_token_states":captured},sort_keys=True))
    return 0 if out["status"]=="PASS" else 2
if __name__=="__main__":raise SystemExit(main())
