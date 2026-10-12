#!/usr/bin/env python3
"""One inexpensive, read-only whole-project context gate for material GitHub PRs.

A PR receipt is an accountable claim by its author, NEVER proof that an LLM
understood the sources. Existing context_before_action is the one source router.
No network, orders, schedules, write operations or live-state assumptions.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    from tools.context_before_action import build, ContextGateError
except ModuleNotFoundError:  # CLI invocation
    from context_before_action import build, ContextGateError

ROOT = Path(__file__).resolve().parents[1]
START = "<!-- PROJECT_CONTEXT_REVIEW_V1"
END = "END_PROJECT_CONTEXT_REVIEW_V1 -->"
SCOPES = ("strategy", "architecture", "operations", "research")
FIELDS = ("prior_decisions", "reused_components", "no_duplicate_reason",
          "change_and_evidence", "existing_owner", "approval_boundary",
          "followthrough_and_ack", "remaining_unknowns")
MIN_WORDS = 6


class ChangeGateError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ChangeGateError("PROJECT_CONTEXT_CHANGE_BLOCKED: " + message)


def classify(paths: list[str]) -> set[str]:
    """Every changed path must map to a project scope; unknown paths default to architecture."""
    result = set()
    for path in paths:
        require(isinstance(path, str) and path and not path.startswith("/")
                and ".." not in Path(path).parts, "invalid changed path")
        low = path.lower()
        if path in ("AGENTS.md", "project-current-state.json", "PROJECT_BACKLOG.md") or (
                low.startswith("docs/project-") or "context" in low and "change_guard" not in low):
            result.update(SCOPES)
            continue
        assigned = set()
        if (low.startswith(("paper_evaluator/", "research/v2", "research/v3", "strategy/"))
                or any(x in low for x in ("strategy", "paper_", "scanner", "scan", "trade", "entry", "buy_", "sell_", "shadow"))):
            assigned.add("strategy")
        if (low.startswith(("tools/", ".github/", "tests/", "supabase/", "docs/"))
                or low.endswith((".py", ".ps1", ".sh", ".sql", ".yml", ".yaml", ".toml"))):
            assigned.add("architecture")
        if (low.startswith((".github/", "supabase/"))
                or any(x in low for x in ("runtime", "minipc", "mini-pc", "health", "capacity", "recovery", "security", "cost"))):
            assigned.add("operations")
        if (low.startswith("research/")
                or any(x in low for x in ("source", "market", "research", "h10", "h11", "h5"))):
            assigned.add("research")
        result.update(assigned or {"architecture"})
    return result


def read_pr_review(body: str) -> dict:
    require(isinstance(body, str) and body.count(START) == 1
            and body.count(END) == 1, "PR description needs one PROJECT_CONTEXT_REVIEW_V1 JSON block")
    start = body.index(START) + len(START)
    end = body.index(END)
    require(start < end, "invalid review block order")
    try:
        data = json.loads(body[start:end].strip())
    except (ValueError, TypeError) as error:
        raise ChangeGateError("PROJECT_CONTEXT_CHANGE_BLOCKED: invalid review JSON") from error
    require(isinstance(data, dict) and data.get("kind") == "PROJECT_CONTEXT_REVIEW_V1",
            "unknown PR review schema")
    return data


def meaningful(value: object) -> bool:
    return isinstance(value, str) and len(value.strip().split()) >= MIN_WORDS


def check(root: Path, paths: list[str], receipt: dict) -> dict:
    scopes = classify(paths)
    if not paths:
        return {"status": "NO_CHANGES", "scopes": []}
    require(receipt.get("kind") == "PROJECT_CONTEXT_REVIEW_V1", "wrong receipt kind")
    for field in FIELDS:
        require(meaningful(receipt.get(field)), "missing meaningful review: " + field)
    review = receipt.get("scope_reviews")
    require(isinstance(review, list) and len(review) == len(scopes),
            "missing or extra scope reviews")
    actual = [x.get("scope") for x in review if isinstance(x, dict)]
    require(len(actual) == len(review) and len(actual) == len(set(actual))
            and set(actual) == scopes, "scope mismatch; all affected areas must be reviewed")
    counts = {}
    for item in review:
        scope = item["scope"]
        packet = build(root, scope)  # validation and source hashes from canonical original
        authorized = {x["path"] for x in packet["source_index"]}
        common = {"project-current-state.json", "PROJECT_BACKLOG.md"}
        cited = item.get("source_paths")
        require(isinstance(cited, list) and len(cited) == len(set(cited))
                and common.issubset(set(cited)) and set(cited).issubset(authorized)
                and len(set(cited) - common) >= 1,
                "scope " + scope + " missing canonical source references")
        for field in ("decision_applied", "existing_implementation", "conflicts_and_gates"):
            require(meaningful(item.get(field)), scope + " missing substantive " + field)
        require(item.get("source_fingerprint") == packet["fingerprint"],
                scope + " fingerprint stale; rerun context_before_action.py on PR HEAD")
        counts[scope] = len(packet["source_index"])
    return {
        "kind": "PROJECT_CONTEXT_CHANGE_VERIFICATION_V1",
        "status": "RECEIPT_AND_SOURCE_ROUTING_VERIFIED_NOT_SEMANTIC_OR_RUNTIME_PROOF",
        "scopes": sorted(scopes),
        "source_counts": counts,
        "changed_files": len(paths),
        "chat_import_claimed": False,
        "model_understanding_proven": False,
        "runtime_or_trading_authorized": False,
    }


def template(root: Path, paths: list[str]) -> dict:
    """Convenient scaffold only. Placeholders MUST be replaced with real review."""
    return {
        "kind": "PROJECT_CONTEXT_REVIEW_V1",
        **{field: "REPLACE with concrete actual review, evidence and owner before PR" for field in FIELDS},
        "scope_reviews": [{
            "scope": scope,
            "source_fingerprint": (packet := build(root, scope))["fingerprint"],
            "source_paths": ["project-current-state.json", "PROJECT_BACKLOG.md",
                             next(x["path"] for x in packet["source_index"]
                                  if x["path"] not in ("project-current-state.json", "PROJECT_BACKLOG.md"))],
            "decision_applied": "REPLACE with exact previous user decision and how it affects this PR",
            "existing_implementation": "REPLACE with original implemented component used instead of duplicate",
            "conflicts_and_gates": "REPLACE with actual check for contradictions and approval boundary",
        } for scope in sorted(classify(paths))],
    }


def git_paths(root: Path, base: str, head: str) -> list[str]:
    proc = subprocess.run(["git", "diff", "--name-only", "--diff-filter=ACMR",
                           base, head], cwd=root, capture_output=True, text=True, check=False)
    require(proc.returncode == 0, "cannot determine PR changed files; fail closed")
    return sorted(set(proc.stdout.splitlines()))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--diff-root", type=Path, default=None,
                        help="Checkout whose HEAD diff is inspected; defaults to --root. Satellite repos use this while canonical source routing remains in --root.")
    parser.add_argument("--base", default="HEAD^1")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--event", type=Path)
    parser.add_argument("--template", action="store_true")
    args = parser.parse_args()
    try:
        paths = git_paths(args.diff_root or args.root, args.base, args.head)
        if args.template:
            print(START)
            print(json.dumps(template(args.root, paths), ensure_ascii=False, indent=2))
            print(END)
            return 0
        require(args.event is not None and args.event.is_file(), "real PR event is required")
        event = json.loads(args.event.read_text(encoding="utf-8"))
        pr = event.get("pull_request")
        require(isinstance(pr, dict), "not an authenticated PR event")
        report = check(args.root, paths, read_pr_review(pr.get("body") or ""))
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except (ChangeGateError, ContextGateError, OSError, ValueError, StopIteration) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
