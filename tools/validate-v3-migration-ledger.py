#!/usr/bin/env python3
"""Validate the living V2/V2R4 -> V3 migration ledger."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT/'research/v3-migration-ledger.json'

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--ledger',type=Path,default=DEFAULT)
    args=ap.parse_args()
    j=json.loads(args.ledger.read_text('utf-8'))
    errors=[]
    allowed=set(j.get('allowed_migration_statuses') or [])
    required_allowed={
      'INHERIT_UNCHANGED','INHERIT_MODIFIED','REPLACE_WITH_VALIDATED_SUCCESSOR',
      'DEFER_TO_LATER_GENERATION','MORE_TESTING_REQUIRED','REJECT_WITH_EVIDENCE',
      'NO_SUCCESSOR_CHANGE'
    }
    if allowed!=required_allowed:
        errors.append('allowed_migration_statuses mismatch')
    comps=j.get('components')
    if not isinstance(comps,list) or not comps:
        errors.append('components must be non-empty list'); comps=[]
    ids=[]
    for i,c in enumerate(comps):
        if not isinstance(c,dict):
            errors.append(f'component {i} not object'); continue
        cid=str(c.get('id') or '')
        ids.append(cid)
        if not re.fullmatch(r'[a-z0-9_]+',cid): errors.append(f'invalid id {cid!r}')
        st=c.get('migration_status')
        if st not in allowed: errors.append(f'{cid}: invalid migration_status {st!r}')
        if not str(c.get('category') or '').strip(): errors.append(f'{cid}: missing category')
        if len(str(c.get('rationale') or '').strip())<20: errors.append(f'{cid}: rationale too short')
        ev=c.get('evidence')
        if not isinstance(ev,list) or not ev: errors.append(f'{cid}: evidence required')
        if st=='MORE_TESTING_REQUIRED' and not str(c.get('pending_gate') or '').strip():
            errors.append(f'{cid}: MORE_TESTING_REQUIRED requires pending_gate')
        if st=='DEFER_TO_LATER_GENERATION' and not str(c.get('pending_gate') or '').strip():
            errors.append(f'{cid}: DEFER_TO_LATER_GENERATION requires a named future gate')
        if st in {'INHERIT_UNCHANGED','REJECT_WITH_EVIDENCE','NO_SUCCESSOR_CHANGE'} and c.get('pending_gate') not in (None,''):
            errors.append(f'{cid}: closed migration status must not retain pending_gate')
    dups=sorted({x for x in ids if x and ids.count(x)>1})
    if dups: errors.append('duplicate ids: '+','.join(dups))
    counts={s:sum(1 for c in comps if isinstance(c,dict) and c.get('migration_status')==s) for s in sorted(allowed)}
    result={
      'kind':'V3_MIGRATION_LEDGER_VALIDATION_V2',
      'status':'PASS' if not errors else 'FAIL',
      'component_count':len(comps),
      'status_counts':counts,
      'more_testing_required_count':counts.get('MORE_TESTING_REQUIRED',0),
      'deferred_count':counts.get('DEFER_TO_LATER_GENERATION',0),
      'errors':errors,
      'guardrails':{
        'active_v2r3_changed':False,
        'v2r4_activated':False,
        'strategy_promoted':False,
        'orders':False,
        'real_money_actions':False
      }
    }
    print(json.dumps(result,sort_keys=True))
    return 0 if not errors else 2

if __name__=='__main__':
    raise SystemExit(main())
