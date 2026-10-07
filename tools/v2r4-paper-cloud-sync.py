#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, time, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_ENDPOINT='https://nlgzjmqgwueojlyqmoru.supabase.co/functions/v1/v2r4-paper-evidence-relay'
PUBLISHABLE_KEY='sb_publishable_SaoibLcejS6rJDLg-lS3jw_IfSfi-ad'

def iso(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def load_json(p): return json.loads(p.read_text('utf-8'))
def atomic_json(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n','utf-8'); os.replace(tmp,path)
def load_token(root):
    p=root/'Secrets/shadow-evidence-token.txt'
    return p.read_text('utf-8').strip() if p.exists() else os.environ.get('SHADOW_EVIDENCE_TOKEN','').strip()
def post(endpoint,token,payload):
    req=urllib.request.Request(endpoint,data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'Content-Type':'application/json','User-Agent':'minipc-v2r4-paper-cloud-sync/1.0','apikey':PUBLISHABLE_KEY,'X-Shadow-Evidence-Token':token})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            body=json.loads(r.read().decode())
            if r.status!=200 or not body.get('ok'): raise RuntimeError(f'relay HTTP {r.status}: {body}')
            return body
    except urllib.error.HTTPError as exc:
        detail=exc.read().decode('utf-8','replace')[:400]; raise RuntimeError(f'relay HTTP {exc.code}: {detail}') from exc

def latest_rechecks(app,series_id):
    out={}
    for p in (app/'paper_rechecks').glob('*.json') if (app/'paper_rechecks').exists() else []:
        try:r=load_json(p)
        except Exception:continue
        if r.get('series_id')!=series_id: continue
        cid=r.get('candidate_id'); when=r.get('recheck_completed_at_utc') or r.get('completed_at_utc') or r.get('revalidated_at_utc') or ''
        if cid and (cid not in out or when>out[cid][0]): out[cid]=(when,r)
    return {k:v[1] for k,v in out.items()}

def followups(app,series_id):
    out={}
    for p in (app/'paper_followups').glob('*.json') if (app/'paper_followups').exists() else []:
        try:r=load_json(p)
        except Exception:continue
        if r.get('series_id')==series_id and r.get('candidate_id'): out[r['candidate_id']]=r
    return out

def collect(app):
    control=load_json(app/'paper_runtime_control.json'); series_id=control['series_id']; rechecks=latest_rechecks(app,series_id); fups=followups(app,series_id)
    candidates=[]
    for p in (app/'paper_decisions').glob('*.json') if (app/'paper_decisions').exists() else []:
        try:d=load_json(p)
        except Exception:continue
        if d.get('series_id')!=series_id: continue
        term=rechecks.get(d.get('candidate_id')) or d
        candidates.append({'candidate_id':d['candidate_id'],'series_id':series_id,'pair':d['pair'],'decision':(term.get('decision') or {}).get('decision',(d.get('decision') or {}).get('decision')),'evaluated_at':d['evaluated_at_utc'],'followup':fups.get(d['candidate_id']),'payload':{'decision':d,'recheck':rechecks.get(d['candidate_id']),'followup':fups.get(d['candidate_id'])}})
    trades=[]
    for p in (app/'paper_positions').glob('*.json') if (app/'paper_positions').exists() else []:
        try:s=load_json(p)
        except Exception:continue
        if s.get('series_id')!=series_id: continue
        ex=s.get('exit') or {}
        trades.append({'candidate_id':s['candidate_id'],'series_id':series_id,'pair':s['pair'],'status':s['status'],'opened_at':s['opened_at_utc'],'closed_at':ex.get('closed_at_utc'),'net_pnl_eur':ex.get('net_pnl_eur'),'net_return_pct':ex.get('net_return_pct'),'payload':s})
    return control,candidates,trades

def run_once(args):
    hb=args.trading_root/'State/v2r4-paper-cloud-sync-heartbeat.json'; token=load_token(args.trading_root)
    result={'schema_version':1,'kind':'V2R4_PAPER_CLOUD_SYNC_HEARTBEAT_V1','checked_at_utc':iso(),'status':'UNKNOWN','paper_only':True,'order_api':False,'real_money_actions':False}
    if len(token)<24:
        result.update(status='DEGRADED',detail='archive token missing/too short'); atomic_json(hb,result); return result
    try:
        control,candidates,trades=collect(args.app_root)
        payload={'action':'sync','series_id':control['series_id'],'strategy_revision':control['strategy_revision'],'candidates':candidates,'trades':trades}
        resp=post(args.endpoint,token,payload)
        result.update(status='HEALTHY',series_id=control['series_id'],candidates=len(candidates),trades=len(trades),accepted_candidates=resp.get('accepted_candidates'),accepted_trades=resp.get('accepted_trades'),detail='paper evidence relay reachable')
    except Exception as exc: result.update(status='DEGRADED',detail=f'{type(exc).__name__}: {str(exc)[:300]}')
    atomic_json(hb,result); return result

def parse_args():
    ap=argparse.ArgumentParser(); ap.add_argument('--app-root',type=Path,required=True); ap.add_argument('--trading-root',type=Path,default=Path.home()/'Trading'); ap.add_argument('--endpoint',default=DEFAULT_ENDPOINT); ap.add_argument('--interval-seconds',type=int,default=60); ap.add_argument('--once',action='store_true'); return ap.parse_args()
if __name__=='__main__':
    a=parse_args()
    while True:
        r=run_once(a); print(json.dumps(r,sort_keys=True),flush=True)
        if a.once: raise SystemExit(0 if r['status']=='HEALTHY' else 2)
        time.sleep(a.interval_seconds)
