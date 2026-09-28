#!/usr/bin/env python3
"""Send concise Slack mentions for new actionable PAPER decisions only."""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def fmt_num(value):
    if value is None:
        return "n/a"
    v = float(value)
    if abs(v) >= 100:
        return f"{v:.2f}"
    if abs(v) >= 1:
        return f"{v:.4f}".rstrip("0").rstrip(".")
    return f"{v:.6f}".rstrip("0").rstrip(".")


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def post_slack(text):
    webhook = os.environ["SLACK_WEBHOOK_URL"].strip()
    if not webhook:
        raise RuntimeError("missing SLACK_WEBHOOK_URL")
    req = urllib.request.Request(
        webhook,
        data=json.dumps({"text": text}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode("utf-8", "replace").strip()
        print(f"Slack response: {resp.status} {body}")
        if not 200 <= resp.status < 300:
            raise RuntimeError(f"Slack HTTP {resp.status}")
        return utcnow()


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: slack_action_push.py MANIFEST_JSON")
    manifest = Path(sys.argv[1])
    paths = json.loads(manifest.read_text("utf-8")) if manifest.exists() else []
    actionable = []

    for raw in paths:
        p = Path(raw)
        if not p.exists():
            raise RuntimeError(f"manifest path missing: {p}")
        record = json.loads(p.read_text("utf-8"))
        if record.get("decision", {}).get("decision") != "BUY_SCOUT":
            continue
        if record.get("real_money_actions_enabled") is not False:
            raise RuntimeError(f"unsafe real-money flag in {p}")
        entry = record.get("paper_entry")
        if not entry or "FILLED_SIMULATED" not in str(entry.get("status", "")):
            raise RuntimeError(f"BUY_SCOUT without simulated scout fill in {p}")
        actionable.append(record)

    if not actionable:
        print("SLACK_NO_ACTIONABLE_PAPER_DECISIONS")
        return

    user_id = os.environ.get("SLACK_USER_ID", "").strip()
    if not user_id:
        raise RuntimeError("missing SLACK_USER_ID")

    receipts = Path("paper_alerts")
    receipts.mkdir(exist_ok=True)

    for record in actionable:
        d = record["decision"]
        entry = record["paper_entry"]
        pair = record["pair"]
        receipt_path = receipts / f"{record['candidate_id']}.json"
        if receipt_path.exists():
            print("SLACK_ACTION_PUSH_IDEMPOTENT", pair, record.get("candidate_id"))
            continue
        text = (
            f"<@{user_id}> KRYPTOSIGNAL | {pair} | PAPER BUY_SCOUT\n"
            f"Entry ~{fmt_num(entry.get('fill_price_eur'))} EUR | "
            f"Stop {fmt_num(entry.get('stop_eur'))} EUR | "
            f"Scout {fmt_num(entry.get('scout_notional_eur'))} EUR (Simulation) | "
            f"Stage 2 Trigger {fmt_num((entry.get('stage2_plan') or {}).get('trigger_eur'))} EUR | "
            f"Stage 2 {fmt_num((entry.get('stage2_plan') or {}).get('notional_eur'))} EUR\n"
            f"Setup: {d.get('setup_lane', 'n/a')} | {d.get('summary', '').strip()}\n"
            "Nur Paper-Test – keine Echtgeldorder."
        )
        accepted_at_utc = post_slack(text)
        receipt = {
            "schema_version": 1,
            "kind": "PAPER_SLACK_ALERT_RECEIPT_V1",
            "candidate_id": record["candidate_id"],
            "series_id": record.get("series_id"),
            "pair": pair,
            "decision": d.get("decision"),
            "slack_webhook_accepted_at_utc": accepted_at_utc,
            "real_money_actions_enabled": False,
            "delivery_scope": "Slack webhook accepted; device delivery is not observable here",
        }
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", "utf-8")
        print("SLACK_ACTION_PUSH_SENT", pair, record.get("candidate_id"), accepted_at_utc)


if __name__ == "__main__":
    main()
