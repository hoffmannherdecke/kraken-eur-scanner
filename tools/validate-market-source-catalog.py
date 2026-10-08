#!/usr/bin/env python3
"""Fail-closed validator for research-only crypto source discovery catalog.

No network, credentials, portfolio access, orders or runtime mutations.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
ROLES={"PRIMARY_LEAD_TO_VERIFY","INDEPENDENT_EDITORIAL_CROSSCHECK","AGGREGATE_CONTEXT_ONLY",
       "RESEARCH_ONLY","LEAD_REQUIRES_PRIMARY","RUMOR_DISCOVERY_ONLY","DO_NOT_USE_FOR_SIGNAL"}
STAGES={"PILOT_READ_ONLY","WATCHLIST","ACCESS_CHECK_REQUIRED","BUSINESS_MODEL_RECHECK",
        "DISCOVERY_ONLY","QUARANTINED","RETIRED_RESEARCH"}

def check(path:Path)->list[str]:
    issues=[]
    d=json.loads(path.read_text(encoding="utf-8"))
    if d.get("schema_version")!=1 or d.get("kind")!="CRYPTO_SOURCE_DISCOVERY_CATALOG_V1":
        issues.append("invalid catalog schema")
    if d.get("active_trade_authority") is not False or d.get("no_raw_news_storage") is not True:
        issues.append("catalog must remain research-only and raw-news-free")
    if d.get("canonical_sources")!="research/source-registry.json":
        issues.append("canonical registry changed")
    xs=d.get("candidates")
    if not isinstance(xs,list) or not xs:
        return issues+["missing candidates"]
    seen=set()
    for idx,x in enumerate(xs):
        sid=str(x.get("id") or "")
        if not re.fullmatch(r"[a-z0-9_]+",sid):
            issues.append(f"{idx}: invalid id")
        if sid in seen: issues.append(f"{idx}: duplicate {sid}")
        seen.add(sid)
        if x.get("stage") not in STAGES or x.get("role") not in ROLES:
            issues.append(f"{sid}: invalid stage/role")
        runtime_verified=x.get("automated_runtime_verified")
        if type(runtime_verified) is not bool:
            issues.append(f"{sid}: runtime_verified must be boolean")
        if runtime_verified is True:
            # A catalog record must not self-certify unattended operation.
            e=str(x.get("runtime_evidence_url") or "")
            when=str(x.get("runtime_verified_at_utc") or "")
            ep=urlparse(e)
            if ep.scheme!="https" or ep.netloc!="github.com" or "/hoffmannherdecke/kraken-eur-scanner/" not in ep.path or not when.endswith("Z"):
                issues.append(f"{sid}: unattended runtime claim requires canonical GitHub proof URL and UTC time")
            if x.get("stage") in {"ACCESS_CHECK_REQUIRED","DISCOVERY_ONLY","QUARANTINED","RETIRED_RESEARCH"}:
                issues.append(f"{sid}: runtime claim contradicts research stage")
        if not x.get("name") or not x.get("notes") or not x.get("last_reviewed_date"):
            issues.append(f"{sid}: missing provenance")
        u=urlparse(x.get("url",""))
        if u.scheme!="https" or not u.netloc or u.username or u.password:
            issues.append(f"{sid}: unsafe/invalid URL")
        if x.get("role")=="RUMOR_DISCOVERY_ONLY" and x.get("stage")=="PILOT_READ_ONLY":
            issues.append(f"{sid}: rumor feed cannot be promoted to editorial pilot")
    return issues

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--catalog",type=Path,default=ROOT/"research/market-source-candidates-v1.json")
    args=p.parse_args()
    issues=check(args.catalog)
    print(json.dumps({"kind":"CRYPTO_SOURCE_CATALOG_GUARD_V1","status":"PASS" if not issues else "FAIL",
                      "errors":issues},sort_keys=True))
    return 0 if not issues else 2

if __name__=="__main__":
    raise SystemExit(main())
