#!/usr/bin/env python3
"""Wait for a real Altrady alert to arrive on the MINI-PC and report transport timing.

Transport-only proof. No exchange account, no orders, no strategy action.
"""
from __future__ import annotations
import argparse, json, time
from datetime import datetime, timezone
from pathlib import Path

MARKER = "LIVE_ALTRADY_TIME_TEST"

def parse_dt(value):
    if not value:
        return None
    s = str(value).strip()
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--trading-root", default=str(Path.home()/"Trading"))
    ap.add_argument("--timeout-seconds", type=int, default=300)
    a=ap.parse_args()
    root=Path(a.trading_root)
    log=root/"Logs"/"altrady-trigger-events.jsonl"
    start=datetime.now(timezone.utc)

    print("Waiting for real Altrady alert marker:", MARKER, flush=True)
    deadline=time.monotonic()+max(30,min(600,a.timeout_seconds))
    seen=set()

    while time.monotonic()<deadline:
        if log.exists():
            lines=log.read_text("utf-8",errors="replace").splitlines()[-500:]
            for line in reversed(lines):
                try: row=json.loads(line)
                except Exception: continue
                event=row.get("event") if isinstance(row,dict) else None
                if not isinstance(event,dict): continue
                if event.get("direction")!=MARKER: continue
                eid=str(event.get("id") or "")
                if eid in seen: continue
                seen.add(eid)
                mini=parse_dt(row.get("received_by_minipc_at_utc"))
                relay=parse_dt(event.get("received_at"))
                if mini and mini < start:
                    continue
                relay_to_minipc=(mini-relay).total_seconds() if mini and relay else None
                out={
                    "kind":"ALTRADY_REAL_ALERT_E2E_PROOF_V1",
                    "status":"PASS",
                    "symbol":event.get("symbol"),
                    "exchange":event.get("exchange"),
                    "altrady_event_time_raw":event.get("event_time"),
                    "relay_received_at_utc":event.get("received_at"),
                    "minipc_received_at_utc":row.get("received_by_minipc_at_utc"),
                    "relay_to_minipc_seconds":round(relay_to_minipc,3) if relay_to_minipc is not None else None,
                    "acknowledged_by_transport":True,
                    "strategy_action":row.get("strategy_action"),
                    "real_money_actions":False,
                    "order_api":False,
                }
                print(json.dumps(out,sort_keys=True))
                return 0
        time.sleep(1)

    print("No real Altrady time-test alert observed before timeout.")
    return 2

if __name__=="__main__":
    raise SystemExit(main())
