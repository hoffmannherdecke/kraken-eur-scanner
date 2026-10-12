#!/usr/bin/env python3
"""One-shot V3 Paper append-only Mini-PC -> Supabase relay. No service key.

No activation endpoint, no orders, no V2R4 runtime modifications, no schedule.
Only push bytes already durably journalled on the isolated V3 host directory.
"""
from __future__ import annotations
import argparse,hashlib,json,os,urllib.request,urllib.error,uuid
from pathlib import Path
from typing import Any

ENDPOINT="https://nlgzjmqgwueojlyqmoru.supabase.co/functions/v1/v3-paper-evidence-relay"
REVISION="V3-EXPERIMENTAL-PAPER-20261011-ALL-LESSONS-001"

def batch(journal:Path,series_id:str,acked:set[str],limit:int=30)->list[dict[str,Any]]:
    rows=[]
    if not journal.is_dir() or journal.is_symlink():
        raise ValueError("separate existing V3 host journal required")
    for p in sorted(journal.glob("*.json")):
        raw=p.read_bytes()
        if len(raw)>16000:raise ValueError("too large receipt")
        r=json.loads(raw)
        if r.get("series_id")!=series_id:continue
        if r.get("revision")!=REVISION or r.get("real_money_actions") is not False:
            raise ValueError("unsafe V3 receipt")
        event_id=hashlib.sha256("|".join(str(r[k]) for k in
            ("series_id","candidate_id","phase","event_key")).encode()).hexdigest()
        if p.stem!=event_id:raise ValueError("local filename/canonical event identity conflict")
        content_sha=hashlib.sha256(raw).hexdigest()
        if event_id in acked:continue
        rows.append({"event_id":event_id,"sha256":content_sha,
                     "canonical_json":raw.decode("utf-8")})
        if len(rows)>=limit:break
    return rows

def sync_once(*,journal:Path,series_id:str,ack_file:Path,token:str,
              relay_url:str=ENDPOINT,
              post=None)->dict[str,Any]:
    if not series_id.startswith("PAPER-V3-") or len(token)<24:
        raise ValueError("V3 identity or relay token missing")
    if ack_file.exists():
        state=json.loads(ack_file.read_text("utf-8"))
        if state.get("series_id")!=series_id or state.get("revision")!=REVISION:
            raise ValueError("cloud acknowledgement from another series")
    else:
        state={"schema":1,"series_id":series_id,"revision":REVISION,"acked":[]}
    if not ack_file.parent.is_dir():
        raise ValueError("ACK root missing, no implicit runtime directory")
    acked=set(state["acked"])
    out=batch(journal,series_id,acked)
    if not out:return {"status":"NO_UNSYNCED_V3_RECEIPTS","count":0,"paper_only":True}
    payload={"action":"sync_paper_receipts","series_id":series_id,
             "strategy_revision":REVISION,"receipts":out}
    if post is None:
        def post(url,token,payload):
            request=urllib.request.Request(url,data=json.dumps(payload).encode("utf-8"),
                method="POST",headers={"Content-Type":"application/json",
                "X-V3-Paper-Evidence-Token":token,"User-Agent":"minipc-v3-paper-cloud/1"})
            with urllib.request.urlopen(request,timeout=25) as response:
                return json.loads(response.read(50000).decode("utf-8"))
    response=post(relay_url,token,payload)
    if (not isinstance(response,dict) or response.get("ok") is not True
            or response.get("accepted_receipts")!=len(out)
            or response.get("series_id")!=series_id):
        raise ValueError("no exact cloud V3 journal acknowledgement")
    state["acked"]=sorted(acked|{r["event_id"] for r in out})
    # A crash after a successful Cloud POST must NOT let one abandoned
    # fixed-name .tmp file block every future 5-minute synchronization.
    # Unique sibling temp + atomic replacement also preserves the older ACK
    # until the new bytes are durable; the actual cloud write is idempotent.
    tmp=ack_file.with_name(ack_file.name+"."+uuid.uuid4().hex+".tmp")
    try:
        with tmp.open("x",encoding="utf-8") as f:
            json.dump(state,f,sort_keys=True);f.flush();os.fsync(f.fileno())
        os.replace(tmp,ack_file)
    finally:
        tmp.unlink(missing_ok=True)
    return {"status":"V3_RECEIPTS_CLOUD_ACK_VERIFIED","count":len(out),
            "total_acked":len(state["acked"]),"paper_only":True,"orders":False}

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--journal",type=Path,required=True)
    p.add_argument("--series",required=True)
    p.add_argument("--ack-file",type=Path,required=True)
    p.add_argument("--relay-secret-file",type=Path,required=True)
    p.add_argument("--execute-cloud-sync",action="store_true")
    a=p.parse_args()
    if not a.execute_cloud_sync:
        print(json.dumps({"status":"PREFLIGHT_ONLY_NO_CLOUD_WRITE",
                          "local_receipts":len(list(a.journal.glob("*.json")))}))
        return 0
    token=a.relay_secret_file.read_text("utf-8").strip()
    print(json.dumps(sync_once(journal=a.journal,series_id=a.series,
                               ack_file=a.ack_file,token=token),sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
