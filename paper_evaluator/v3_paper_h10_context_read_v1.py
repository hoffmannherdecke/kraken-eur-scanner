#!/usr/bin/env python3
"""Mini-PC candidate-clock on-demand read of the *existing* H10 Cloud research.

No wallet collection, new schedule, service-role key, paper writer, model
request, Order or fake source-catalyst confirmation. Unknown source is soft.
"""
from __future__ import annotations
import argparse,json,os,urllib.request
from pathlib import Path
from typing import Any

ENDPOINT="https://nlgzjmqgwueojlyqmoru.supabase.co/functions/v1/v3-paper-h10-context-read"
ALLOWED_CONTEXT_KEYS={
    "market_phase_radar","source_stewardship","news_sentiment",
    "dynamic_move_radar","missed_opportunity_learning","economic_learning",
    "minipc_reliability","smart_money_h10","polymarket_h11",
}

def fetch_h10(*,pair:str,token:str,post=None)->dict[str,Any]:
    if not isinstance(pair,str) or not pair.endswith("/EUR") or len(pair)>18:
        raise ValueError("only exact Kraken Spot EUR pair")
    if len(token)<24:raise ValueError("existing V3 Paper relay token required")
    payload={"action":"read_existing_h10_optional_context","pair":pair}
    if post is None:
        def post(url:str,secret:str,payload:dict)->dict:
            req=urllib.request.Request(url,method="POST",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type":"application/json",
                         "X-V3-Paper-Evidence-Token":secret,
                         "User-Agent":"minipc-v3-paper-h10-read/1"})
            with urllib.request.urlopen(req,timeout=12) as resp:
                return json.loads(resp.read(12000).decode("utf-8"))
    result=post(ENDPOINT,token,payload)
    if not isinstance(result,dict) or result.get("ok") is not True or result.get("pair")!=pair:
        raise ValueError("cloud source context read has no exact ACK")
    sources=result.get("sources")
    if not isinstance(sources,dict) or not set(sources).issubset({"smart_money_h10"}):
        raise ValueError("unexpected source context provenance")
    if "smart_money_h10" in sources:
        row=sources["smart_money_h10"]
        if (not isinstance(row,dict) or row.get("source_verified") is not True
                or row.get("pair")!=pair
                or row.get("source_owner")!="EXISTING_H10_HYPERLIQUID_PROSPECTIVE_CAPTURE"):
            raise ValueError("invalid or mixed H10 provenance")
    return {"status":result.get("status"),"sources":sources}

def merge_context_file(*,path:Path,pair:str,live:dict[str,Any])->dict:
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise ValueError("isolated V3 context directory must already exist")
    if path.exists():
        content=path.read_bytes()
        if len(content)>50000:raise ValueError("overlarge old context")
        old=json.loads(content)
        if not isinstance(old,dict):raise ValueError("invalid existing source context")
    else:old={}
    if not set(old).issubset(ALLOWED_CONTEXT_KEYS):
        raise ValueError("unexpected source owner keys")
    result={}
    for k,v in old.items():
        if isinstance(v,dict) and v.get("pair") not in (None,pair):
            continue
        # Old H10 for another or expired Coin must NEVER be passed forward.
        if k!="smart_money_h10":result[k]=v
    h10=live.get("sources",{}).get("smart_money_h10")
    if h10 is not None:result["smart_money_h10"]=h10
    tmp=path.with_suffix(".new")
    fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as out:
            json.dump(result,out,sort_keys=True,allow_nan=False)
            out.write("\n");out.flush();os.fsync(out.fileno())
        os.replace(tmp,path)
    except Exception:
        try:tmp.unlink(missing_ok=True)
        except OSError:pass
        raise
    return {"status":"H10_LIVE_CONTEXT_SNAPSHOT_WRITTEN" if h10 else
                  "H10_NOT_AVAILABLE_OTHER_OWNER_CONTEXT_PRESERVED",
            "pair":pair,"h10_available":h10 is not None,
            "other_sources_preserved":len(result)-(1 if h10 else 0),
            "model_called":False,"orders":False}

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--pair",required=True)
    p.add_argument("--relay-secret-file",type=Path,required=True)
    p.add_argument("--output-context",type=Path,required=True)
    p.add_argument("--execute-live-read",action="store_true")
    args=p.parse_args()
    if not args.execute_live_read:
        print(json.dumps({"status":"PLAN_ONLY_NO_NETWORK"}));return 0
    token=args.relay_secret_file.read_text("utf-8").strip()
    remote=fetch_h10(pair=args.pair,token=token)
    result=merge_context_file(path=args.output_context,pair=args.pair,live=remote)
    print(json.dumps(result,sort_keys=True))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
