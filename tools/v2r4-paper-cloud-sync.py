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
def post(endpoint,token,payload,*,second_token=None):
    headers={'Content-Type':'application/json','User-Agent':'minipc-v2r4-paper-cloud-sync/1.0','X-Shadow-Evidence-Token':token}
    if second_token is not None:
        if len(second_token)<24: raise RuntimeError('Closed aftercare requires second credential')
        headers['X-MiniPC-Status-Token']=second_token
    req=urllib.request.Request(endpoint,data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers=headers)
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

def closed_original_readonly_preview(control,candidates,trades,*,old_series_id,
                                     future_v3_series_id,old_release_sha,
                                     cutover_at_utc):
    """Construct ONLY an in-memory preview for the existing old Cloud relay.

    Never submit requests, reserve orders, send alerts or touch state. This
    is NOT a physical/Cloud authorization; the original owner must
    independently prove series/fence/credential/Cloud original existence.
    """
    import re
    def clock(value):
        if not isinstance(value,str) or not value:
            raise ValueError('missing original UTC timestamp')
        return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)
    if (not isinstance(control,dict)
            or not re.fullmatch(r'PAPER-V2R4-[0-9]{8}T[0-9]{6}Z',old_series_id)
            or not re.fullmatch(r'PAPER-V3-[0-9]{8}T[0-9]{6}Z',future_v3_series_id)
            or not re.fullmatch(r'[0-9a-f]{40}',old_release_sha)
            or control.get('series_id')!=old_series_id
            or control.get('strategy_revision')!='V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION'
            or control.get('paper_only') is not True
            or control.get('real_money_actions_enabled') is not False):
        raise ValueError('closed original preview has wrong pinned paper identity')
    cutoff=clock(cutover_at_utc)
    old_candidates=[]
    old_trades=[]
    pending_unstamped=0
    for row in candidates:
        if not isinstance(row,dict) or row.get('series_id')!=old_series_id:
            continue
        fup=row.get('followup')
        decision=(row.get('payload') or {}).get('decision') or {}
        if (not isinstance(fup,dict) or fup.get('kind')!='PAPER_FOLLOWUP_V2'
                or fup.get('series_id')!=old_series_id
                or fup.get('candidate_id')!=row.get('candidate_id')
                or fup.get('pair')!=row.get('pair')
                or decision.get('real_money_actions_enabled') is not False
                or clock(row.get('evaluated_at'))>=cutoff):
            continue
        if not fup.get('updated_at_utc'):
            # Original prospective followup is still waiting for real 1m
            # horizon evidence: do NOT turn missing time into mature PnL
            # or abort all other valid historical candidates.
            horizons=fup.get('horizons')
            if horizons is None or horizons=={}:
                pending_unstamped+=1
                continue
            raise ValueError('unstamped nonempty original horizons need source review')
        clock(fup.get('updated_at_utc'))
        old_candidates.append(row)
    for row in trades:
        if not isinstance(row,dict) or row.get('series_id')!=old_series_id:
            continue
        opened=clock(row.get('opened_at'))
        if (row.get('status')!='CLOSED'
                or opened>=cutoff
                or (row.get('payload') or {}).get('real_money_actions_enabled') is not False
                or not (row.get('payload') or {}).get('exit')):
            continue
        if clock(row.get('closed_at'))<opened:
            raise ValueError('closed original exit precedes its entry')
        old_trades.append(row)
    meta={'action':'sync_closed_original_followups',
          'series_id':old_series_id,
          'strategy_revision':control['strategy_revision'],
          'expected_old_release_sha':old_release_sha,
          'expected_active_v3_series_id':future_v3_series_id}
    batches=[{**meta,'candidates':chunk,'trades':[]}
             for chunk in _chunks(old_candidates,20)]
    batches += [{**meta,'candidates':[],'trades':chunk}
                for chunk in _chunks(old_trades,20)]
    return {'kind':'CLOSED_ORIGINAL_RELAY_PREVIEW_NO_NETWORK_V1',
            'status':'REVIEW_ONLY_NOT_ACTIVATED',
            'candidate_followup_count':len(old_candidates),
            'pending_unstamped_followups_not_promoted':pending_unstamped,
            'old_terminal_trade_count':len(old_trades),
            'bounded_batches':len(batches),
            'physical_old_writer_fence_verified':False,
            'cloud_preexisting_originals_verified':False,
            'edge_credential_proof_verified':False,
            'cloud_updated':False,
            'batches':batches}


def closed_aftercare_authority(root,control):
    """Fail closed on a PR309 marker until original CAS is committed.
    This is only a local prerequisite. The Edge must independently verify CAS.
    """
    import re
    path=root/'State/v3-experimental-paper-old-intake-fence.json'
    marker=load_json(path)
    expected=['CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait']
    old='PAPER-V2R4-20261009T110135Z'
    new=marker.get('proposed_successor_series_id')
    sha=control.get('release_repo_sha')
    if (marker.get('kind')!='V3_EXPERIMENTAL_OLD_INTAKE_FENCE_V1'
            or marker.get('phase')!='CLOUD_COMMITTED'
            or marker.get('predecessor_series_id')!=old
            or not isinstance(new,str)
            or not re.fullmatch(r'PAPER-V3-[0-9]{8}T[0-9]{6}Z',new)
            or not isinstance(sha,str)
            or not re.fullmatch(r'[0-9a-f]{40}',sha)
            or not re.fullmatch(r'[0-9a-f]{40}',str(marker.get('proposed_v3_repo_sha','')))
            or not re.fullmatch(r'[0-9a-f]{64}',str(marker.get('proposed_v3_bundle_sha256','')))
            or not re.fullmatch(r'[0-9a-f]{64}',str(marker.get('proposed_v3_strategy_sha256','')))
            or sorted(marker.get('task_names') or [])!=expected
            or marker.get('paper_only') is not True
            or marker.get('orders_enabled') is not False
            or marker.get('real_money_actions') is not False
            or marker.get('persistent_until_explicit_owner_release') is not True
            or control.get('series_id')!=old
            or control.get('strategy_revision')!='V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION'
            or control.get('paper_only') is not True
            or control.get('real_money_actions_enabled') is not False):
        raise ValueError('closed-original source identity or committed fence unverified')
    cutoff=datetime.strptime(new.removeprefix('PAPER-V3-'),'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
    if cutoff>datetime.now(timezone.utc):
        raise ValueError('V3 successor cutover time in future')
    return old,new,sha,cutoff.isoformat().replace('+00:00','Z')


def closed_aftercare_batches(preview,active_sent,aftercare_sent):
    """Bounded, retryable packets; never replay unchanged cloud-ACKed rows."""
    for batch in preview['batches']:
        result={k:v for k,v in batch.items() if k not in ('candidates','trades')}
        result.update(candidates=[],trades=[])
        marks={}
        for field,prefix in (('candidates','candidate'),('trades','trade')):
            for row in batch[field]:
                key=f"{prefix}:{row['candidate_id']}"
                value=row_hash(row)
                if aftercare_sent.get(key)==value or active_sent.get(key)==value:
                    continue
                result[field].append(row)
                marks[key]=value
        if marks:
            yield result,marks


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

def run_closed_aftercare_once(args):
    """Same original Task/owner, but never use active sync after V3 CAS."""
    hb=args.trading_root/'State/v2r4-paper-cloud-sync-heartbeat.json'
    result={'schema_version':1,'kind':'V2R4_PAPER_CLOUD_SYNC_HEARTBEAT_V1',
            'checked_at_utc':iso(),'status':'UNKNOWN',
            'mode':'CLOSED_ORIGINAL_AFTERCARE','paper_only':True,
            'order_api':False,'real_money_actions':False}
    try:
        control,candidates,trades=collect(args.app_root)
        old,new,release_sha,cutoff_iso=closed_aftercare_authority(args.trading_root,control)
        cutoff=datetime.fromisoformat(cutoff_iso.replace('Z','+00:00'))
        # A running old intake writer after CAS is a release-blocking defect.
        for row in candidates:
            when=datetime.fromisoformat(row['evaluated_at'].replace('Z','+00:00'))
            if when>=cutoff: raise ValueError('new old-series candidate after V3 cutoff')
        for row in trades:
            when=datetime.fromisoformat(row['opened_at'].replace('Z','+00:00'))
            if when>=cutoff: raise ValueError('new old-series paper entry after V3 cutoff')
        preview=closed_original_readonly_preview(
            control,candidates,trades,old_series_id=old,future_v3_series_id=new,
            old_release_sha=release_sha,cutover_at_utc=cutoff_iso)
        # Never send on a mere preview or during ARMED/QUIESCED.
        token=load_token(args.trading_root)
        status_file=args.trading_root/'Secrets/minipc-status-token.txt'
        second=status_file.read_text('utf-8').strip() if status_file.is_file() else ''
        if len(token)<24 or len(second)<24:
            raise RuntimeError('closed-original dual credentials unavailable')
        state_dir=getattr(args,'paper_state_dir',None) or args.trading_root/'State'
        active_sent=load_sync_state(state_dir/'v2r4-paper-cloud-sync-state.json')['sent']
        aftercare_path=state_dir/'v2r4-paper-closed-aftercare-state.json'
        aftercare=load_sync_state(aftercare_path)
        accepted=0
        unchanged=0
        batches=0
        for packet,marks in closed_aftercare_batches(
                preview,active_sent,aftercare['sent']):
            if batches>=10: break  # at most 200 historical records per cycle
            ack=post(args.endpoint,token,packet,second_token=second)
            count=len(packet['candidates'])+len(packet['trades'])
            applied=int(ack.get('accepted_candidates',-1))+int(ack.get('accepted_trades',-1))
            identical=int(ack.get('unchanged_replays',-1))
            if (ack.get('action')!='sync_closed_original_followups'
                    or ack.get('paper_only') is not True
                    or ack.get('real_money_actions') is not False
                    or ack.get('new_v2r4_intake_allowed') is not False
                    or applied<0 or identical<0 or applied+identical!=count):
                raise RuntimeError('closed-original cloud ACK incomplete or unsafe')
            # Crash before this commit is safe: old Edge retries are idempotent.
            aftercare['sent'].update(marks)
            atomic_json(aftercare_path,aftercare)
            batches+=1
            accepted+=applied
            unchanged+=identical
        result.update(status='HEALTHY',series_id=old,successor_series_id=new,
                      accepted_original_updates=accepted,
                      unchanged_replays=unchanged,batches=batches,
                      pending_unstamped_followups=preview['pending_unstamped_followups_not_promoted'],
                      detail='original aftercare synced; separate live CAS proof required')
    except Exception as exc:
        result.update(status='DEGRADED',
                      detail=f'{type(exc).__name__}: {str(exc)[:200]}')
    atomic_json(hb,result)
    return result


def run_once(args):
    hb=args.trading_root/'State/v2r4-paper-cloud-sync-heartbeat.json'
    state_path=(getattr(args,'paper_state_dir',None) or (args.trading_root/'State'))/'v2r4-paper-cloud-sync-state.json'
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

        alert_state=dispatch_alerts_if_needed(args.trading_root,control,candidates,trades,getattr(args,'paper_state_dir',None))
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
    ap=argparse.ArgumentParser(); ap.add_argument('--app-root',type=Path,required=True); ap.add_argument('--trading-root',type=Path,default=Path.home()/'Trading'); ap.add_argument('--endpoint',default=DEFAULT_ENDPOINT); ap.add_argument('--paper-state-dir',type=Path,default=None); ap.add_argument('--interval-seconds',type=int,default=60); ap.add_argument('--once',action='store_true'); ap.add_argument('--preview-closed-original',action='store_true'); ap.add_argument('--preview-old-series-id',default=''); ap.add_argument('--preview-new-v3-series-id',default=''); ap.add_argument('--preview-old-release-sha',default=''); ap.add_argument('--preview-cutover-at-utc',default=''); return ap.parse_args()
if __name__=='__main__':
    a=parse_args()
    if a.preview_closed_original:
        # Never read a credential or make a network request in preview.
        control,candidates,trades=collect(a.app_root)
        preview=closed_original_readonly_preview(
            control,candidates,trades,old_series_id=a.preview_old_series_id,
            future_v3_series_id=a.preview_new_v3_series_id,
            old_release_sha=a.preview_old_release_sha,
            cutover_at_utc=a.preview_cutover_at_utc)
        print(json.dumps({k:v for k,v in preview.items() if k!='batches'},
                         sort_keys=True),flush=True)
        raise SystemExit(0)
    while True:
        r=run_once(a); print(json.dumps(r,sort_keys=True),flush=True)
        if a.once: raise SystemExit(0 if r['status']=='HEALTHY' else 2)
        time.sleep(a.interval_seconds)
