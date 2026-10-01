#!/usr/bin/env python3
"""Render the single-row V2R3 release review snapshot as a fail-closed Markdown pack."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

def load(path: Path) -> dict[str,Any]:
    x=json.loads(path.read_text('utf-8'))
    if isinstance(x,list):
        if len(x)!=1: raise SystemExit('expected exactly one snapshot row')
        x=x[0]
    if not isinstance(x,dict): raise SystemExit('snapshot must be object or single-row list')
    return x

def val(x:Any)->str:
    if x is None: return '—'
    if isinstance(x,bool): return 'yes' if x else 'no'
    return str(x)

def table(rows:list[dict[str,Any]], keys:list[str], limit:int=25)->list[str]:
    if not rows: return ['_No rows._']
    rows=rows[:limit]
    out=['| '+' | '.join(keys)+' |','| '+' | '.join(['---']*len(keys))+' |']
    for r in rows:
        out.append('| '+' | '.join(val(r.get(k)).replace('|','\\|') for k in keys)+' |')
    return out

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('snapshot',type=Path)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--allow-blocked',action='store_true')
    args=ap.parse_args()
    s=load(args.snapshot)
    allowed=bool(s.get('final_review_allowed'))
    lines=[
      '# V2R3 Final Review Pack',
      '',
      f"- Series: `{val(s.get('series_id'))}`",
      f"- Strategy: `{val(s.get('strategy_revision'))}`",
      f"- Review state: **{val(s.get('review_state'))}**",
      f"- Final review allowed: **{val(allowed)}**",
      f"- Candidate outcomes: {val(s.get('candidate_outcomes'))}",
      f"- Completed trades: {val(s.get('completed_trades'))}",
      f"- 24h coverage: {val(s.get('coverage_24h_pct'))}%",
      f"- Integrity: **{val(s.get('integrity_state'))}**",
      '',
      '> This report is evidence/review only. It never authorizes automatic strategy changes, V2R4 activation or real-money action.',
      ''
    ]
    if not allowed:
        lines += [
          '## BLOCKED — final review gate not mature',
          '',
          f"Gate state: `{val(s.get('gate_state'))}`.",
          '',
          'No strategy-performance conclusion, promotion, parameter change or V2R4 release decision may be derived from this blocked pack.',
          ''
        ]
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text('\n'.join(lines)+'\n','utf-8')
        print(json.dumps({'kind':'V2R3_FINAL_REVIEW_RENDER_V1','status':'BLOCKED','review_state':s.get('review_state'),'output':str(args.output)},sort_keys=True))
        return 0 if args.allow_blocked else 2

    lines += ['## Gate / integrity','','Final review gate is mature and integrity is healthy. This permits the documented evidence review only.','']
    lines += ['## Runtime timing','']
    lines += table(s.get('runtime_timing') or [],['decision','candidates','p50_detect_to_eval_start_seconds','p90_detect_to_eval_start_seconds'],25)+['']
    lines += ['## WAIT revalidation timing','']
    rv=s.get('revalidation_timing')
    if isinstance(rv,dict):
        lines += [f"- Revalidated candidates: {val(rv.get('revalidated_candidates'))}",f"- Decision changes: {val(rv.get('decision_changes'))}",f"- TTL lag p50: {val(rv.get('p50_ttl_lag_seconds'))} s",f"- TTL lag p90: {val(rv.get('p90_ttl_lag_seconds'))} s",f"- TTL lag max: {val(rv.get('max_ttl_lag_seconds'))} s",'']
    else: lines += ['_No revalidation timing row._','']
    lines += ['## Mature outcome summary','']
    lines += table(s.get('outcome_summary') or [],['decision','candidates','mature_24h','p50_mfe_24h_pct','p50_mae_24h_pct'],25)+['']
    lines += ['## Horizon / post-detection summary','']
    lines += table(s.get('interim_horizons') or [],['decision','candidates','mature_30m','p50_mfe_30m_pct','mature_360m','p50_mfe_360m_pct','mature_post_detect_4h','p50_post_detect_mfe_4h_pct'],25)+['']
    lines += ['## Reason-family rollup (top persisted rows)','']
    lines += table(s.get('reason_family_rollup') or [],['decision','reason_family','reason_polarity','reason_instances','candidates','mature_post_detect_24h','p50_post_detect_mfe_24h_pct'],40)+['']
    lines += ['## Mature missed-move candidates','']
    lines += table(s.get('mature_missed_move_candidates') or [],['candidate_id','pair','initial_decision','mfe_24h_pct','mae_24h_pct','evaluation_latency_seconds'],30)+['']
    lines += [
      '## Required causal classification',
      '',
      'Every material finding must be classified before it can become a V3/V2R4 hypothesis:',
      '- Strategy problem / filter or entry logic',
      '- Timing / infrastructure',
      '- Data quality / source availability',
      '- Technical operating failure',
      '- Cost / spread / slippage / turnover',
      '- Correct no-trade / no change required',
      '',
      '## Release boundary',
      '',
      '- Do not alter the closed V2R3 artifacts.',
      '- Record findings in the V3 migration ledger / V2R4 release review as appropriate.',
      '- Any rule/mechanics change creates a new version.',
      '- V2R4 remains a separate explicit activation decision.',
      '- No real-money action is authorized by this pack.',
      ''
    ]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text('\n'.join(lines)+'\n','utf-8')
    print(json.dumps({'kind':'V2R3_FINAL_REVIEW_RENDER_V1','status':'PASS','review_state':s.get('review_state'),'output':str(args.output),'automatic_strategy_change_allowed':False},sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
