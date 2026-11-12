#!/usr/bin/env python3
"""Read-only GitHub self-hosted runner status for the existing CryptoSupport bridge.

No new runner, scheduler or credential is created. Use a short-lived caller-supplied
token with the private repository's Administration:read permission. The token is
never logged or stored. Insufficient permission returns UNAVAILABLE, not OFFLINE.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

REPOSITORY = "hoffmannherdecke/kraken-readonly-bridge"
RUNNER_NAME = "MINI-PC-CryptoSupport"
ENDPOINT = f"https://api.github.com/repos/{REPOSITORY}/actions/runners?per_page=100"
MAX_PAGES = 4


def classify_runner_payload(payload: dict, runner_name: str = RUNNER_NAME) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("runners"), list):
        return {"state": "UNAVAILABLE", "online": None, "busy": None, "reason": "SCHEMA"}
    matches = [runner for runner in payload["runners"]
               if isinstance(runner, dict) and runner.get("name") == runner_name]
    if len(matches) != 1:
        return {"state": "UNAVAILABLE", "online": None, "busy": None,
                "reason": "MISSING_OR_AMBIGUOUS"}
    runner = matches[0]
    status = runner.get("status")
    busy = runner.get("busy")
    if status not in ("online", "offline") or type(busy) is not bool:
        return {"state": "UNAVAILABLE", "online": None, "busy": None, "reason": "INVALID_STATE"}
    if status == "offline":
        return {"state": "OFFLINE", "online": False, "busy": False, "reason": "GITHUB_RUNNER_API"}
    return {"state": "BUSY" if busy else "IDLE",
            "online": True, "busy": busy, "reason": "GITHUB_RUNNER_API"}


def query_runner_status(token: str) -> dict:
    if not token or len(token) > 500 or "\n" in token or "\r" in token:
        return {"state": "UNAVAILABLE", "online": None, "busy": None, "reason": "TOKEN_NOT_AVAILABLE"}
    runners = []
    total = None
    try:
        for page in range(1, MAX_PAGES + 1):
            url = ENDPOINT + f"&page={page}"
            req = urllib.request.Request(url, headers={
                "Accept": "application/vnd.github+json",
                "Authorization": "Bearer " + token,
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "CryptoSupport-ReadOnly-Runner-Status/1",
            })
            with urllib.request.urlopen(req, timeout=8) as response:
                if response.status != 200:
                    raise ValueError("invalid response")
                raw = response.read(131073)
            if len(raw) > 131072:
                raise ValueError("response too large")
            body = json.loads(raw)
            if not isinstance(body, dict) or not isinstance(body.get("runners"), list):
                raise ValueError("invalid response schema")
            if not isinstance(body.get("total_count"), int) or body["total_count"] < 0:
                raise ValueError("invalid runner count")
            if total is None:
                total = body["total_count"]
            runners.extend(body["runners"])
            if len(runners) >= total or len(body["runners"]) < 100:
                break
        else:
            return {"state": "UNAVAILABLE", "online": None, "busy": None, "reason": "PAGE_LIMIT"}
        return classify_runner_payload({"runners": runners})
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
            ValueError, json.JSONDecodeError, OSError):
        # Avoid leaking HTTP error body, URI internals, token, or even auth headers.
        return {"state": "UNAVAILABLE", "online": None, "busy": None, "reason": "API_UNAVAILABLE"}



def authorized_file_handoff(state: str, approved: bool) -> dict:
    """A dispatch decision, not a dispatch. The existing GitHub connector posts.

    An explicit per-file owner approval and pre-observed SHA256 are mandatory.
    GitHub Actions' existing single-worker queue and TTL remain unchanged.
    """
    if not approved:
        return {"action": "HOLD", "reason": "OWNER_FILE_APPROVAL_REQUIRED"}
    if state == "IDLE":
        return {"action": "DISPATCH_EXISTING_EXPORT", "reason": "RUNNER_IDLE"}
    if state == "BUSY":
        return {"action": "HOLD", "reason": "RUNNER_BUSY"}
    if state == "OFFLINE":
        return {"action": "START_EXISTING_BOUNDED_WINDOW", "reason": "RUNNER_OFFLINE"}
    return {"action": "HOLD", "reason": "RUNNER_STATUS_NOT_VERIFIED"}


def main() -> int:
    status = query_runner_status(os.environ.get("MINIPC_RUNNER_STATUS_TOKEN", ""))
    print(json.dumps({"kind": "MINIPC_RUNNER_STATUS_V1", **status},
                     separators=(",", ":"), sort_keys=True))
    return 0 if status["state"] != "UNAVAILABLE" else 2


if __name__ == "__main__":
    sys.exit(main())
