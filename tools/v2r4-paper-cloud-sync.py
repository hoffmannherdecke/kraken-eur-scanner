#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, time, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_ENDPOINT='https://nlgzjmqgwueojlyqmoru.supabase.co/functions/v1/v2r4-paper-evidence-relay'

def iso(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def load_json(p): return json.loads(p.read_text('utf-8'))
def atomic_json(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n','utf-8'); os.replace(tmp,path)
def load_token(root):
    p=root/'Secrets/shadow-evidence-token.txt'
    return p.read_text('utf-8').strip() if p.exists() else os.environ.get('SHADOW_EVIDENCE_TOKEN','').strip()
def post(endpoint,token,payload):
    req=urllib.request.Request(endpoint,data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'Content-Type':'application/json','User-Agent':'minipc-v2r4-paper-cloud-sync/1.0','X-Shadow-Evidence-Token':token})
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

def _chunks(rows,size):
    for i in range(0,len(rows),size):
        yield rows[i:i+size]

def row_hash(row):
    body=json.dumps(row,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(body).hexdigest()

def load_sync_state(path):
    if not path.exists(): return {'schema_version':1,'sent':{}}
    try:
        state=load_json(path)
        if int(state.get('schema_version',0))!=1: raise ValueError('schema')
        state.setdefault('sent',{})
        return state
    except Exception:
        return {'schema_version':1,'sent':{}}

def changed_rows(rows,prefix,sent):
    out=[]; marks={}
    for row in rows:
        key=f"{prefix}:{row.get('candidate_id')}"
        h=row_hash(row)
        if sent.get(key)==h: continue
        out.append(row); marks[key]=h
    return out,marks

def actionable_keys(control,candidates,trades):
    sid=control['series_id']; keys=set()
    for row in candidates:
        payload=row.get('payload') or {}
        term=payload.get('recheck') or payload.get('decision') or {}
        if (term.get('decision') or {}).get('decision')=='BUY_SCOUT' and term.get('paper_entry'):
            stamp=term.get('recheck_completed_at_utc') or term.get('revalidated_at_utc') or term.get('evaluated_at_utc') or ''
            keys.add(f"{sid}|{row.get('candidate_id')}|BUY_SCOUT|{stamp}")
    important={'STAGE2_FILLED','TRAIL_TIER','CLOSED','DATA_GAP_UNVERIFIED'}
    for row in trades:
        pos=row.get('payload') or {}
        for idx,event in enumerate(pos.get('events') or []):
            typ=event.get('type')
            if typ in important:
                keys.add(f"{sid}|{row.get('candidate_id')}|{idx}|{typ}|{event.get('at_utc') or ''}")
    return keys

def dispatch_alerts_if_needed(root,control,candidates,trades,paper_state_dir=None):
    state_path=(paper_state_dir or (root/'State'))/'v2r4-paper-alert-dispatch-state.json'
    state=load_json(state_path) if state_path.exists() else {'schema_version':1,'dispatched':[]}
    dispatched=set(state.get('dispatched') or [])
    current=actionable_keys(control,candidates,trades)
    pending=sorted(current-dispatched)
    if not pending:
        return {'status':'NONE_PENDING','new_actionable':0}
    token_path=root/'Secrets/github-actions-dispatch-token.txt'
    token=token_path.read_text('utf-8').strip() if token_path.exists() else ''
    if len(token)<20:
        raise RuntimeError('GitHub Actions dispatch token missing/too short for actionable V2R4 PAPER alert')
    url='https://api.github.com/repos/hoffmannherdecke/kraken-eur-scanner/actions/workflows/v2r4-paper-alerts.yml/dispatches'
    req=urllib.request.Request(
        url,data=b'{"ref":"main"}',method='POST',
        headers={
            'Authorization':'Bearer '+token,
            'Accept':'application/vnd.github+json',
            'X-GitHub-Api-Version':'2022-11-28',
            'Content-Type':'application/json',
            'User-Agent':'minipc-v2r4-paper-alert-dispatch/1.0',
        },
    )
    with urllib.request.urlopen(req,timeout=20) as resp:
        if resp.status!=204:
            raise RuntimeError(f'alert workflow dispatch HTTP {resp.status}')
    state['dispatched']=sorted((dispatched|set(pending)))[-2000:]
    state['updated_at_utc']=iso()
    atomic_json(state_path,state)
    return {'status':'DISPATCHED','new_actionable':len(pending)}

def run_once(args):
    hb=args.trading_root/'State/v2r4-paper-cloud-sync-heartbeat.json'
    state_path=(args.paper_state_dir or (args.trading_root/'State'))/'v2r4-paper-cloud-sync-state.json'
    token=load_token(args.trading_root)
    result={'schema_version':1,'kind':'V2R4_PAPER_CLOUD_SYNC_HEARTBEAT_V1','checked_at_utc':iso(),'status':'UNKNOWN','paper_only':True,'order_api':False,'real_money_actions':False}
    if len(token)<24:
        result.update(status='DEGRADED',detail='archive token missing/too short'); atomic_json(hb,result); return result
    try:
        control,candidates,trades=collect(args.app_root)
        state=load_sync_state(state_path); sent=state['sent']
        pending_candidates,candidate_marks=changed_rows(candidates,'candidate',sent)
        pending_trades,trade_marks=changed_rows(trades,'trade',sent)
        accepted_candidates=0; accepted_trades=0; batches=0

        # Incremental, idempotent archive. A large fixed cohort must not be
        # re-uploaded every minute once unchanged. Each successful batch advances
        # only its own local hash marks so a later failure remains retryable.
        for batch in _chunks(pending_candidates,200):
            resp=post(args.endpoint,token,{'action':'sync','series_id':control['series_id'],'strategy_revision':control['strategy_revision'],'candidates':batch,'trades':[]})
            accepted_candidates+=int(resp.get('accepted_candidates') or 0); batches+=1
            for row in batch:
                key=f"candidate:{row.get('candidate_id')}"; sent[key]=candidate_marks[key]
            atomic_json(state_path,state)
        for batch in _chunks(pending_trades,50):
            resp=post(args.endpoint,token,{'action':'sync','series_id':control['series_id'],'strategy_revision':control['strategy_revision'],'candidates':[],'trades':batch})
            accepted_trades+=int(resp.get('accepted_trades') or 0); batches+=1
            for row in batch:
                key=f"trade:{row.get('candidate_id')}"; sent[key]=trade_marks[key]
            atomic_json(state_path,state)

        if len(sent)>5000:
            keys=list(sent.keys())[-5000:]
            state['sent']={k:sent[k] for k in keys}
            atomic_json(state_path,state)

        alert_state=dispatch_alerts_if_needed(args.trading_root,control,candidates,trades,args.paper_state_dir)
        result.update(
            status='HEALTHY',series_id=control['series_id'],candidates=len(candidates),trades=len(trades),
            pending_candidates=len(pending_candidates),pending_trades=len(pending_trades),
            accepted_candidates=accepted_candidates,accepted_trades=accepted_trades,batches=batches,
            alert_dispatch=alert_state,
            detail=('paper evidence relay sync complete' if batches else 'no changed paper evidence pending')
        )
    except Exception as exc: result.update(status='DEGRADED',detail=f'{type(exc).__name__}: {str(exc)[:300]}')
    atomic_json(hb,result); return result

def parse_args():
    ap=argparse.ArgumentParser(); ap.add_argument('--app-root',type=Path,required=True); ap.add_argument('--trading-root',type=Path,default=Path.home()/'Trading'); ap.add_argument('--endpoint',default=DEFAULT_ENDPOINT); ap.add_argument('--paper-state-dir',type=Path,default=None); ap.add_argument('--interval-seconds',type=int,default=60); ap.add_argument('--once',action='store_true'); return ap.parse_args()
if __name__=='__main__':
    a=parse_args()
    while True:
        r=run_once(a); print(json.dumps(r,sort_keys=True),flush=True)
        if a.once: raise SystemExit(0 if r['status']=='HEALTHY' else 2)
        time.sleep(a.interval_seconds)
