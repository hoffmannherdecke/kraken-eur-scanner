#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from paper_evaluator.v2r4_precandidate_discovery import MICROSTRUCTURE_EXCEPTION_SHADOW, STANDARD_EXECUTION_GATE, classify_liquidity
    from paper_evaluator.v2r4_precandidate_watcher import depth_1pct_eur, eur_pairs
except ImportError:
    from v2r4_precandidate_discovery import MICROSTRUCTURE_EXCEPTION_SHADOW, STANDARD_EXECUTION_GATE, classify_liquidity
    from v2r4_precandidate_watcher import depth_1pct_eur, eur_pairs

SCHEMA=1

def utcnow(): return datetime.now(timezone.utc)
def iso(dt=None): return (dt or utcnow()).astimezone(timezone.utc).isoformat().replace('+00:00','Z')
def parse_utc(v): return datetime.fromisoformat(str(v).replace('Z','+00:00')).astimezone(timezone.utc)
def atomic_json(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n','utf-8'); os.replace(tmp,path)
def load_json(path): return json.loads(path.read_text('utf-8'))

def event_id(e:dict[str,Any])->str:
    material='|'.join([str(e.get('pair') or ''),str(e.get('observed_at_utc') or ''),str(e.get('source_pair_received_at_utc') or ''),str(e.get('last_eur') or '')])
    return hashlib.sha256(material.encode()).hexdigest()[:24]

def load_state(path:Path)->dict[str,Any]:
    if not path.exists(): return {'schema_version':SCHEMA,'processed':{},'attempts':{},'altname_cache':{},'altname_cache_at_utc':None}
    try:
        s=load_json(path); s.setdefault('processed',{}); s.setdefault('attempts',{}); s.setdefault('altname_cache',{}); return s
    except Exception: return {'schema_version':SCHEMA,'processed':{},'attempts':{},'altname_cache':{},'altname_cache_at_utc':None}

def refresh_altname_cache(state):
    last=state.get('altname_cache_at_utc')
    if last:
        try:
            if (utcnow()-parse_utc(last)).total_seconds()<3600 and state.get('altname_cache'): return
        except Exception: pass
    rows=eur_pairs(); state['altname_cache']={r['pair']:r['altname'] for r in rows}; state['altname_cache_at_utc']=iso()

def build_candidate(event, altname, eid):
    observed=parse_utc(event['observed_at_utc']); ts=int(observed.timestamp()); run_id=int(hashlib.sha256(eid.encode()).hexdigest()[:12],16)
    pair=event['pair']; tag=pair.replace('/','-'); cid=f"{observed.strftime('%Y%m%d-%H%M%S')}-{tag}-r{run_id}"
    returns=event.get('returns') or {}
    return {
      'schema_version':1,'kind':'CANONICAL_CANDIDATE_HANDOFF_V1','candidate_id':cid,'queue_id':f'{run_id}:{tag}:{ts}',
      'source_repo':'hoffmannherdecke/kraken-eur-scanner','source_scanner_run_id':run_id,'source_scanner_run_attempt':1,'source_scanner_sha':None,
      'scanner_package_sha256':None,'scanner_runtime_settings':{'source':'MINIPC_V2R4_WS_SHADOW_BRIDGE'},
      'event_time_utc':observed.isoformat().replace('+00:00','Z'),'event_ts':ts,
      'timing':{'scan_step_started_at_utc':event.get('source_snapshot_written_at_utc'),'candidate_detected_at_utc':event['observed_at_utc'],'candidate_detected_ts':ts,'candidate_snapshot_at_utc':event['observed_at_utc'],'handoff_written_at_utc':iso(),'altrady_detected_at_utc':None},
      'pair':pair,'altname':altname,'action':'REVIEW_ONLY_NOT_ORDER',
      'scanner_candidate':{'pair':pair,'altname':altname,'price':event.get('last_eur'),'score':None,'ret10m':returns.get('ret10m'),'ret30m':returns.get('ret30m'),'ret1h':returns.get('ret1h'),'ret3h':returns.get('ret3h'),'ret6h':returns.get('ret6h'),'ret12h':returns.get('ret12h'),'ret_day_open':returns.get('ret_day_open'),'reasons':event.get('reasons') or []},
      'scanner_market_context':{'source':'MINIPC_V2R4_WS_SHADOW_DISCOVERY','sensor_price_eur':event.get('last_eur'),'spread_pct':event.get('spread_pct'),'turnover24h_eur':event.get('turnover24h_eur'),'source_event_id':eid,'source_event':event},
      'scanner_market_breadth':None,'review_message':'V2R4 local discovery review; paper only.'
    }

def classify_event(event,state):
    liq=str(event.get('liquidity_class_without_depth') or '')
    alt=state['altname_cache'].get(event.get('pair'))
    if liq==STANDARD_EXECUTION_GATE and bool(event.get('would_request_fresh_recheck')): return True,liq,alt,None
    turnover=float(event.get('turnover24h_eur') or 0); spread=float(event.get('spread_pct') or 999)
    if 50000<=turnover<150000 and spread<=0.60 and alt:
        try: depth=depth_1pct_eur(alt,float(event['last_eur']))
        except Exception: depth=None
        classified=classify_liquidity(turnover24h_eur=turnover,spread_pct=spread,depth_1pct_eur=depth,intended_notional_eur=100.0)
        return classified==MICROSTRUCTURE_EXCEPTION_SHADOW,classified,alt,depth
    return False,liq or 'WATCH_ONLY',alt,None

def run_candidates(args):
    app=args.app_root; trading=args.trading_root; state_path=trading/'State/v2r4-paper-candidate-runtime-state.json'; hb_path=trading/'State/v2r4-paper-candidate-runtime-heartbeat.json'; events=trading/'State/v2r4-ws-shadow-events'; qdir=app/'handoff_queue'; ddir=app/'paper_decisions'; qdir.mkdir(parents=True,exist_ok=True); ddir.mkdir(parents=True,exist_ok=True)
    state=load_state(state_path); key=args.api_key_file.read_text('utf-8').strip() if args.api_key_file.exists() else ''
    while True:
      counters={'events_seen':0,'watch_only':0,'reviewable':0,'evaluated':0,'failures':0}
      errors=[]
      try:
        control=load_json(app/'paper_runtime_control.json'); start=parse_utc(control['series_started_at_utc']); refresh_altname_cache(state)
        for p in sorted(events.glob('*.json')):
          try: e=load_json(p)
          except Exception: continue
          if e.get('kind')!='V2R4_WS_SHADOW_DISCOVERY': continue
          try: obs=parse_utc(e.get('observed_at_utc'))
          except Exception: continue
          if obs<start: continue
          eid=event_id(e); counters['events_seen']+=1
          if eid in state['processed']: continue
          reviewable,liq,alt,depth=classify_event(e,state)
          if not reviewable:
            state['processed'][eid]={'status':'WATCH_ONLY','at_utc':iso(),'pair':e.get('pair'),'liquidity_class':liq}; counters['watch_only']+=1; continue
          counters['reviewable']+=1
          if not alt:
            errors.append(f'{eid}:ALTNAME_UNAVAILABLE'); counters['failures']+=1; continue
          c=build_candidate(e,alt,eid); c['scanner_market_context']['liquidity_class']=liq; c['scanner_market_context']['depth_1pct_eur']=depth
          cp=qdir/f"{c['candidate_id']}.json"
          if not cp.exists(): cp.write_text(json.dumps(c,indent=2,sort_keys=True)+'\n','utf-8')
          env=os.environ.copy(); env['OPENAI_API_KEY']=key; env.setdefault('OPENAI_MODEL','gpt-6-luna')
          if len(key)<20: raise RuntimeError('OpenAI API key missing/too short')
          proc=subprocess.run([sys.executable,str(app/'paper_evaluator/evaluate.py'),str(cp),'--out',str(ddir)],cwd=str(app),env=env,text=True,capture_output=True,timeout=150)
          if proc.returncode!=0:
            attempts=int(state['attempts'].get(eid,0))+1; state['attempts'][eid]=attempts; counters['failures']+=1; errors.append(f'{eid}:EVAL_FAILED:{proc.stderr[-180:]}')
            if attempts>=3: state['processed'][eid]={'status':'EVALUATION_FAILED_TERMINAL','at_utc':iso(),'pair':e.get('pair'),'attempts':attempts}
            continue
          state['processed'][eid]={'status':'EVALUATED','at_utc':iso(),'pair':e.get('pair'),'candidate_id':c['candidate_id'],'liquidity_class':liq}; state['attempts'].pop(eid,None); counters['evaluated']+=1
        if len(state['processed'])>10000:
          keys=list(state['processed'].keys())[-10000:]; state['processed']={k:state['processed'][k] for k in keys}
        atomic_json(state_path,state)
        hb={'schema_version':1,'kind':'V2R4_PAPER_CANDIDATE_RUNTIME_HEARTBEAT_V1','checked_at_utc':iso(),'status':'HEALTHY' if not errors else 'DEGRADED','series_id':control.get('series_id'),'counters':counters,'errors':errors[-10:],'paper_only':True,'order_api':False,'real_money_actions':False}
        atomic_json(hb_path,hb)
      except Exception as exc:
        atomic_json(hb_path,{'schema_version':1,'kind':'V2R4_PAPER_CANDIDATE_RUNTIME_HEARTBEAT_V1','checked_at_utc':iso(),'status':'DEGRADED','detail':f'{type(exc).__name__}: {str(exc)[:250]}','paper_only':True,'order_api':False,'real_money_actions':False})
      if args.once: return 0
      time.sleep(args.interval_seconds)

def reconcile_rechecks_and_expiry(app:Path):
    control=load_json(app/'paper_runtime_control.json'); series_id=control['series_id']
    rdir=app/'paper_rechecks'; legacy=app/'paper_revalidations'; rdir.mkdir(exist_ok=True); legacy.mkdir(exist_ok=True)
    latest={}
    for rp in rdir.glob('*.json'):
        try: rr=load_json(rp)
        except Exception: continue
        if rr.get('series_id')!=series_id or not rr.get('candidate_id'): continue
        when=rr.get('recheck_completed_at_utc') or rr.get('completed_at_utc') or rr.get('revalidated_at_utc') or ''
        if rr['candidate_id'] not in latest or when>latest[rr['candidate_id']][0]: latest[rr['candidate_id']]=(when,rr)
    now=utcnow()
    for dp in (app/'paper_decisions').glob('*.json'):
        try: d=load_json(dp)
        except Exception: continue
        if d.get('series_id')!=series_id or (d.get('decision') or {}).get('decision')!='WAIT': continue
        cid=d.get('candidate_id'); rr=latest.get(cid,(None,None))[1]
        if rr is None:
            ttl=int((d.get('decision') or {}).get('ttl_minutes') or 0)
            due=parse_utc(d['evaluated_at_utc']).timestamp()+ttl*60
            if ttl>0 and now.timestamp()>=due:
                rr={'schema_version':1,'kind':'V2R4_WAIT_EXPIRY_V1','test_id':control['test_id'],'series_id':series_id,'strategy_revision':control['strategy_revision'],'candidate_id':cid,'pair':d['pair'],'recheck_started_at_utc':iso(now),'recheck_completed_at_utc':iso(now),'decision':{'decision':'REJECT','setup_lane':'NONE','summary':'WAIT expired without a deterministic trigger match.','reason_codes':['TTL_EXPIRED_NO_TRIGGER'],'missing_triggers':[],'stop_eur':None,'ttl_minutes':0,'expected_remaining_move_pct':None,'risk_reward_after_costs':None,'stage2_trigger_eur':None,'stage2_ttl_minutes':0,'watch_conditions':[]},'paper_entry':None,'next_wait_trigger_plan':None,'evaluator':{'response_id':None,'model':None,'attempt':0},'paper_only':True,'real_money_actions_enabled':False,'order_api':False}
                target=rdir/f"{now.strftime('%Y%m%dT%H%M%SZ')}-{cid}-ttl-expired.json"
                if not target.exists(): target.write_text(json.dumps(rr,indent=2,sort_keys=True)+'\n','utf-8')
        if rr is not None:
            mirror=legacy/dp.name
            mirror.write_text(json.dumps(rr,indent=2,sort_keys=True)+'\n','utf-8')

def run_lifecycle(args):
    app=args.app_root; trading=args.trading_root; hb=trading/'State/v2r4-paper-lifecycle-heartbeat.json'
    while True:
      errors=[]; ran=[]
      try:
        reconcile_rechecks_and_expiry(app); ran.append('recheck_reconciliation')
      except Exception as exc:
        errors.append(f'recheck_reconciliation:{type(exc).__name__}:{exc}')
      for script in ('paper_position_tracker.py','paper_followup.py'):
        try:
          p=subprocess.run([sys.executable,str(app/script)],cwd=str(app),text=True,capture_output=True,timeout=180)
          if p.returncode!=0: errors.append(f'{script}:{p.stderr[-200:]}')
          else: ran.append(script)
        except Exception as exc: errors.append(f'{script}:{type(exc).__name__}:{exc}')
      atomic_json(hb,{'schema_version':1,'kind':'V2R4_PAPER_LIFECYCLE_HEARTBEAT_V1','checked_at_utc':iso(),'status':'HEALTHY' if not errors else 'DEGRADED','ran':ran,'errors':errors[-10:],'paper_only':True,'order_api':False,'real_money_actions':False})
      if args.once: return 0
      time.sleep(args.interval_seconds)

def parse_args():
    ap=argparse.ArgumentParser(); ap.add_argument('--mode',choices=['candidates','lifecycle'],required=True); ap.add_argument('--app-root',type=Path,required=True); ap.add_argument('--trading-root',type=Path,default=Path.home()/'Trading'); ap.add_argument('--api-key-file',type=Path,default=Path.home()/'Trading/Secrets/openai-api-key.txt'); ap.add_argument('--interval-seconds',type=float,default=2.0); ap.add_argument('--once',action='store_true'); return ap.parse_args()
if __name__=='__main__':
    a=parse_args(); raise SystemExit(run_candidates(a) if a.mode=='candidates' else run_lifecycle(a))
