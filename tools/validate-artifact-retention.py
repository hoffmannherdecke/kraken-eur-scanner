#!/usr/bin/env python3
"""Fail closed when GitHub Actions uploads artifacts without bounded retention."""
from __future__ import annotations
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WF=ROOT/'.github'/'workflows'
MAX_DAYS=30

def main()->int:
    errors=[]
    uploads=0
    for path in sorted(list(WF.glob('*.yml'))+list(WF.glob('*.yaml'))):
        lines=path.read_text('utf-8').splitlines()
        for i,line in enumerate(lines):
            if 'uses:' not in line or 'actions/upload-artifact@' not in line:
                continue
            uploads+=1
            indent=len(line)-len(line.lstrip())
            block=[]
            for nxt in lines[i+1:]:
                nxt_indent=len(nxt)-len(nxt.lstrip())
                if nxt.strip().startswith('- ') and nxt_indent<=indent:
                    break
                block.append(nxt)
            text='\n'.join(block)
            m=re.search(r'^\s*retention-days\s*:\s*([0-9]+)\s*(?:#.*)?$',text,re.M)
            if not m:
                errors.append(f'{path.relative_to(ROOT)}:{i+1}: upload-artifact missing retention-days')
                continue
            days=int(m.group(1))
            if days<1 or days>MAX_DAYS:
                errors.append(f'{path.relative_to(ROOT)}:{i+1}: retention-days={days} outside 1..{MAX_DAYS}')
    if errors:
        for e in errors: print('ARTIFACT_RETENTION_ERROR',e)
        return 2
    print(f'ARTIFACT_RETENTION_GUARD_PASS uploads={uploads} max_days={MAX_DAYS}')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
