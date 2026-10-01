#!/usr/bin/env python3
"""Fail-closed reconciliation between open GitHub issues and PROJECT_BACKLOG.md.

Open issues are allowed as focused discussion/research containers, but they must
not become a second competing to-do list. Every open issue must be referenced by
number in the canonical PROJECT_BACKLOG.md.

Read-only: no issue mutation, no repository mutation, no strategy/runtime action.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_fixture(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text("utf-8"))
    if isinstance(data, dict):
        data = data.get("issues", [])
    if not isinstance(data, list):
        raise ValueError("issues fixture must be a list or {issues:[...]}")
    return [x for x in data if isinstance(x, dict) and "pull_request" not in x]


def fetch_open_issues(repo: str, token: str) -> list[dict[str, Any]]:
    if not re.fullmatch(r"[^/\s]+/[^/\s]+", repo):
        raise ValueError("repository must be owner/name")
    issues: list[dict[str, Any]] = []
    page = 1
    while True:
        query = urllib.parse.urlencode(
            {"state": "open", "per_page": 100, "page": page}
        )
        url = f"https://api.github.com/repos/{repo}/issues?{query}"
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "backlog-issue-reconciliation/1.0",
                **({"Authorization": f"Bearer {token}"} if token else {}),
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            rows = json.loads(resp.read().decode("utf-8"))
        if not isinstance(rows, list):
            raise RuntimeError("unexpected GitHub issues response")
        for row in rows:
            if isinstance(row, dict) and "pull_request" not in row:
                issues.append(row)
        if len(rows) < 100:
            break
        page += 1
    return issues


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--backlog",
        type=Path,
        default=ROOT / "PROJECT_BACKLOG.md",
    )
    ap.add_argument("--repository", default=os.getenv("GITHUB_REPOSITORY", ""))
    ap.add_argument("--token", default=os.getenv("GITHUB_TOKEN", ""))
    ap.add_argument("--issues-json", type=Path)
    args = ap.parse_args()

    backlog = args.backlog.read_text("utf-8")

    if args.issues_json:
        issues = load_fixture(args.issues_json)
        source = f"fixture:{args.issues_json}"
    else:
        if not args.repository:
            raise SystemExit("GITHUB_REPOSITORY/--repository is required without --issues-json")
        issues = fetch_open_issues(args.repository, args.token)
        source = f"github:{args.repository}"

    rows = []
    missing = []
    for issue in sorted(issues, key=lambda x: int(x.get("number", 0))):
        number = int(issue["number"])
        title = str(issue.get("title") or "")
        marker = f"#{number}"
        # Require the literal issue marker. Do not rely on title text, which may
        # change and can create accidental matches.
        referenced = marker in backlog
        row = {
            "number": number,
            "title": title,
            "marker": marker,
            "referenced_in_master_backlog": referenced,
        }
        rows.append(row)
        if not referenced:
            missing.append(row)

    result = {
        "kind": "BACKLOG_ISSUE_RECONCILIATION_V1",
        "status": "PASS" if not missing else "FAIL",
        "source": source,
        "open_issue_count": len(rows),
        "open_issues": rows,
        "unreferenced_open_issue_count": len(missing),
        "unreferenced_open_issues": missing,
        "canonical_todo_source": "PROJECT_BACKLOG.md",
        "guardrails": {
            "issues_mutated": False,
            "repository_mutated": False,
            "strategy_changed": False,
            "runtime_changed": False,
            "orders": False,
            "real_money_actions": False,
        },
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
