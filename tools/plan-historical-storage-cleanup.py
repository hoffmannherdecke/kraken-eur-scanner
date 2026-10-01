#!/usr/bin/env python3
"""Read-only historical storage lifecycle planner.

Classifies files under a Historical root. It never deletes or modifies files.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


KEEP_TOP = {'normalized','derived','catalog','trials','reports'}


def classify(rel: Path, age_hours: float, staging_age: float, tmp_age: float) -> str:
    parts = rel.parts
    if not parts:
        return 'HOLD_UNKNOWN'
    top = parts[0].lower()
    name = rel.name.lower()
    if top == 'raw':
        if name.endswith('.zip'):
            return 'KEEP_PROVENANCE_ROOT'
        if '.zip.part' in name:
            return 'REVIEW_REDUNDANT_PART'
        return 'KEEP_RAW_PROVENANCE_REVIEW'
    if top == 'staging':
        return 'DELETE_CANDIDATE' if age_hours >= staging_age else 'KEEP_FRESH_WORKSPACE'
    if top == 'tmp':
        return 'DELETE_CANDIDATE' if age_hours >= tmp_age else 'KEEP_FRESH_WORKSPACE'
    if top in KEEP_TOP:
        return 'KEEP_RESEARCH_EVIDENCE_OR_DERIVATIVE'
    return 'HOLD_UNKNOWN'


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('root', type=Path)
    ap.add_argument('--staging-min-age-hours', type=float, default=24.0)
    ap.add_argument('--tmp-min-age-hours', type=float, default=48.0)
    ap.add_argument('--now-epoch', type=float, default=None)
    ap.add_argument('--output', type=Path)
    args=ap.parse_args()

    root=args.root.resolve()
    if not root.is_dir():
        raise SystemExit(f'Historical root missing: {root}')
    now=time.time() if args.now_epoch is None else args.now_epoch
    rows=[]
    totals={}
    for p in sorted((x for x in root.rglob('*') if x.is_file()), key=lambda x: str(x).lower()):
        st=p.stat()
        rel=p.relative_to(root)
        age=max(0.0,(now-st.st_mtime)/3600.0)
        cls=classify(rel,age,args.staging_min_age_hours,args.tmp_min_age_hours)
        row={'path':rel.as_posix(),'bytes':st.st_size,'age_hours':round(age,3),'classification':cls}
        rows.append(row)
        agg=totals.setdefault(cls,{'files':0,'bytes':0})
        agg['files']+=1; agg['bytes']+=st.st_size

    delete_bytes=totals.get('DELETE_CANDIDATE',{}).get('bytes',0)
    result={
      'kind':'HISTORICAL_STORAGE_LIFECYCLE_PLAN_V1',
      'status':'PLAN_ONLY',
      'root':str(root),
      'staging_min_age_hours':args.staging_min_age_hours,
      'tmp_min_age_hours':args.tmp_min_age_hours,
      'file_count':len(rows),
      'candidate_reclaim_bytes':delete_bytes,
      'summary':totals,
      'files':rows,
      'guardrails':{
        'files_deleted':False,
        'unknown_files_auto_deleted':False,
        'provenance_archives_auto_deleted':False,
        'normalized_data_auto_deleted':False,
        'trial_evidence_auto_deleted':False,
        'active_strategy_changed':False,
        'real_money_actions':False
      }
    }
    raw=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(raw,'utf-8')
    print(raw,end='')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
