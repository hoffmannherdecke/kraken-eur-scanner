#!/usr/bin/env python3
"""Read-only audit of the repository-side payload that supabase_sync.py would archive.

No network access, no secrets, no writes. Intended for CI and diagnostics.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(path: Path):
    return json.loads(path.read_text("utf-8"))

control = load(ROOT / "paper_runtime_control.json")
series_id = control["series_id"]

revals = {}
for p in (ROOT / "paper_revalidations").glob("*.json") if (ROOT / "paper_revalidations").exists() else []:
    try:
        r = load(p)
        if r.get("series_id") == series_id:
            revals[p.name] = r
    except Exception:
        pass

decisions = []
for p in (ROOT / "paper_decisions").glob("*.json") if (ROOT / "paper_decisions").exists() else []:
    try:
        d = load(p)
    except Exception:
        continue
    if d.get("series_id") != series_id:
        continue
    terminal = revals.get(p.name) or d
    decisions.append({
        "candidate_id": d.get("candidate_id"),
        "pair": d.get("pair"),
        "decision": terminal.get("decision", {}).get("decision", d.get("decision", {}).get("decision")),
        "evaluated_at": d.get("evaluated_at_utc"),
    })

positions = []
for p in (ROOT / "paper_positions").glob("*.json") if (ROOT / "paper_positions").exists() else []:
    try:
        s = load(p)
    except Exception:
        continue
    if s.get("series_id") == series_id:
        positions.append({
            "candidate_id": s.get("candidate_id"),
            "pair": s.get("pair"),
            "status": s.get("status"),
        })

counts = {}
for d in decisions:
    counts[d["decision"]] = counts.get(d["decision"], 0) + 1

result = {
    "kind": "SUPABASE_SYNC_AUDIT_V1",
    "series_id": series_id,
    "enabled": bool(control.get("enabled")),
    "repo_candidate_rows": len(decisions),
    "repo_trade_rows": len(positions),
    "decision_counts": counts,
    "first_candidate": decisions[0]["candidate_id"] if decisions else None,
    "last_candidate": decisions[-1]["candidate_id"] if decisions else None,
}
print(json.dumps(result, sort_keys=True))
