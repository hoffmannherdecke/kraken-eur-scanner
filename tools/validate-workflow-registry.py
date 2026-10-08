#!/usr/bin/env python3
"""Fail closed if workflow/control-plane classification drifts."""
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/"docs/workflow-registry.json"
WORKFLOWS=ROOT/".github/workflows"
ALLOWED={"ACTIVE_RUNTIME","ACTIVE_MAINTENANCE","ACTIVE_VALIDATION","RESEARCH_VALIDATION","MANUAL_OR_CHANGE_VALIDATION","HISTORICAL_REFERENCE"}

def main()->int:
    data=json.loads(REGISTRY.read_text("utf-8"))
    errors=[]
    entries=data.get("entries")
    if not isinstance(entries,list):
        entries=[]
        errors.append("entries must be a list")
    names=[x.get("workflow") for x in entries if isinstance(x,dict)]
    if len(names)!=len(set(names)):
        errors.append("duplicate workflow registry entry")
    disk=sorted(p.name for p in WORKFLOWS.glob("*.yml"))
    reg=sorted(x for x in names if isinstance(x,str))
    missing=sorted(set(disk)-set(reg))
    extra=sorted(set(reg)-set(disk))
    if missing: errors.append("unregistered workflows: "+", ".join(missing))
    if extra: errors.append("registry points to missing workflows: "+", ".join(extra))
    for x in entries:
        if not isinstance(x,dict):
            errors.append("non-object registry entry")
            continue
        if x.get("lifecycle") not in ALLOWED:
            errors.append(f"invalid lifecycle for {x.get('workflow')}: {x.get('lifecycle')}")
        active=x.get("active_control_surface")
        if not isinstance(active,bool):
            errors.append(f"active_control_surface must be bool: {x.get('workflow')}")
        if active and x.get("lifecycle")!="ACTIVE_RUNTIME":
            errors.append(f"only ACTIVE_RUNTIME may be active control surface: {x.get('workflow')}")
    result={"kind":"WORKFLOW_REGISTRY_VALIDATION_V1","status":"PASS" if not errors else "FAIL","disk_count":len(disk),"registry_count":len(reg),"active_runtime":[x["workflow"] for x in entries if isinstance(x,dict) and x.get("active_control_surface")],"errors":errors}
    print(json.dumps(result,sort_keys=True))
    return 0 if not errors else 2

if __name__=="__main__":
    raise SystemExit(main())
