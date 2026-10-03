#!/usr/bin/env python3
"""Read-only OpenAI organization cost watcher for the MINI-PC.

This tool deliberately does NOT claim to know the remaining prepaid credit
balance. OpenAI's documented Administration API exposes usage/costs, while the
prepaid balance threshold is handled natively by API Billing auto-reload.

Safety:
- GET-only Administration API call
- no model request / no token spend caused by this watcher
- no billing mutation / no auto-reload mutation
- no strategy/trading/account action
- admin key is loaded only from environment or Trading\\Secrets
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

COSTS_ENDPOINT = "https://api.openai.com/v1/organization/costs"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")
    tmp.replace(path)


def load_admin_key(root: Path) -> str:
    env = os.environ.get("OPENAI_ADMIN_KEY", "").strip()
    if env:
        return env
    path = root / "Secrets" / "openai-admin-key.txt"
    return path.read_text("utf-8").strip() if path.exists() else ""


def month_start_epoch(now: datetime) -> int:
    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    return int(start.timestamp())


def _amount_value(result: dict[str, Any]) -> float:
    amount = result.get("amount")
    if isinstance(amount, dict):
        raw = amount.get("value")
    else:
        raw = amount
    try:
        return float(raw or 0.0)
    except (TypeError, ValueError):
        return 0.0


def sum_costs(payload: dict[str, Any]) -> float:
    total = 0.0
    for bucket in payload.get("data") or []:
        for result in bucket.get("results") or []:
            amount = result.get("amount")
            if isinstance(amount, dict):
                currency = str(amount.get("currency") or "usd").lower()
                if currency not in {"usd", "usd_cents"}:
                    raise RuntimeError(f"unexpected cost currency: {currency}")
                value = _amount_value(result)
                if currency == "usd_cents":
                    value /= 100.0
            else:
                value = _amount_value(result)
            total += value
    return round(total, 6)


def fetch_costs(admin_key: str, start_time: int, project_id: str | None = None) -> dict[str, Any]:
    params: list[tuple[str, str]] = [
        ("start_time", str(start_time)),
        ("bucket_width", "1d"),
        ("limit", "31"),
    ]
    if project_id:
        params.append(("project_ids[]", project_id))

    all_buckets: list[dict[str, Any]] = []
    page: str | None = None
    for _ in range(10):
        q = list(params)
        if page:
            q.append(("page", page))
        url = COSTS_ENDPOINT + "?" + urllib.parse.urlencode(q)
        req = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Authorization": "Bearer " + admin_key,
                "Accept": "application/json",
                "User-Agent": "minipc-openai-cost-watch/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", "replace")
            if resp.status != 200:
                raise RuntimeError(f"OpenAI costs HTTP {resp.status}")
            payload = json.loads(raw)
        all_buckets.extend(payload.get("data") or [])
        if not payload.get("has_more"):
            return {"data": all_buckets, "has_more": False}
        page = payload.get("next_page")
        if not page:
            raise RuntimeError("costs response has_more=true without next_page")
    raise RuntimeError("costs pagination exceeded safety bound")


def make_state(
    *,
    now: datetime,
    status: str,
    month_spend_usd: float | None,
    project_id: str | None,
    detail: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "OPENAI_API_COST_WATCH_V1",
        "checked_at_utc": now.isoformat().replace("+00:00", "Z"),
        "status": status,
        "month_spend_usd": month_spend_usd,
        "project_id_filter": project_id,
        "source": "OPENAI_ADMIN_ORGANIZATION_COSTS",
        "direct_prepaid_balance_supported": False,
        "prepaid_remaining_usd": None,
        "authoritative_low_balance_control": "OPENAI_NATIVE_PREPAID_AUTO_RELOAD",
        "model_request_made": False,
        "model_tokens_consumed_by_watch": 0,
        "http_method": "GET",
        "billing_mutation": False,
        "strategy_action": "NONE_OBSERVABILITY_ONLY",
        "real_money_actions": False,
        "detail": detail,
    }


def self_test() -> int:
    sample = {
        "data": [
            {"results": [{"amount": {"value": 1.25, "currency": "usd"}}]},
            {"results": [{"amount": {"value": 0.75, "currency": "usd"}}]},
        ]
    }
    assert sum_costs(sample) == 2.0
    assert month_start_epoch(datetime(2026, 10, 3, 12, tzinfo=timezone.utc)) == int(
        datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp()
    )
    state = make_state(
        now=datetime(2026, 10, 3, tzinfo=timezone.utc),
        status="HEALTHY",
        month_spend_usd=2.0,
        project_id=None,
        detail="self-test",
    )
    assert state["direct_prepaid_balance_supported"] is False
    assert state["prepaid_remaining_usd"] is None
    assert state["model_tokens_consumed_by_watch"] == 0
    assert state["billing_mutation"] is False
    print("OPENAI_COST_WATCH_SELFTEST PASS parser/no-balance-claim/no-model/no-mutation")
    return 0


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trading-root", type=Path, default=Path.home() / "Trading")
    ap.add_argument("--project-id", default=os.environ.get("OPENAI_PROJECT_ID", "").strip() or None)
    ap.add_argument("--self-test", action="store_true")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        return self_test()

    now = utc_now()
    state_path = args.trading_root / "State" / "openai-api-cost-watch.json"
    key = load_admin_key(args.trading_root)
    if not key:
        state = make_state(
            now=now,
            status="NOT_CONFIGURED",
            month_spend_usd=None,
            project_id=args.project_id,
            detail="OPENAI_ADMIN_KEY/openai-admin-key.txt missing; watcher intentionally not active",
        )
        atomic_json(state_path, state)
        print(json.dumps(state, sort_keys=True))
        return 3

    if not key.startswith("sk-admin-"):
        state = make_state(
            now=now,
            status="ERROR",
            month_spend_usd=None,
            project_id=args.project_id,
            detail="admin key has unexpected format; expected sk-admin-*",
        )
        atomic_json(state_path, state)
        print(json.dumps(state, sort_keys=True))
        return 2

    try:
        payload = fetch_costs(key, month_start_epoch(now), args.project_id)
        spend = sum_costs(payload)
        state = make_state(
            now=now,
            status="HEALTHY",
            month_spend_usd=spend,
            project_id=args.project_id,
            detail="read-only organization cost snapshot; not a prepaid-balance reading",
        )
        atomic_json(state_path, state)
        print(json.dumps(state, sort_keys=True))
        return 0
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", "replace")
        except Exception:
            body = ""
        detail = f"HTTP {exc.code}: {body[:220]}" if body else f"HTTP {exc.code}"
    except Exception as exc:
        detail = f"{type(exc).__name__}: {str(exc)[:240]}"

    state = make_state(
        now=now,
        status="ERROR",
        month_spend_usd=None,
        project_id=args.project_id,
        detail=detail,
    )
    atomic_json(state_path, state)
    print(json.dumps(state, sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
