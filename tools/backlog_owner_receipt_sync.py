#!/usr/bin/env python3
"""Conservative, issue-comment-driven PROJECT_BACKLOG status proposal.

A single authenticated, explicitly formatted owner receipt generates a proposed
bounded edit. The protected main branch is never edited by this script.
"""
import json
import os
import re
from pathlib import Path

START = "<!-- OWNER_RECEIPT_SYNC_START -->"
END = "<!-- OWNER_RECEIPT_SYNC_END -->"
ALLOWED = {"SOURCE_DONE", "PHYSICAL_STAGED_DONE", "REAL_RUNTIME_ACK_PENDING", "REAL_RUNTIME_ACK_DONE", "BLOCKED"}
RECEIPT = re.compile(
    r"(?m)^PROJECT_BACKLOG_UPDATE_V1\s*\|\s*key=([A-Z0-9_]{5,80})"
    r"\s*\|\s*status=([A-Z_]+)\s*\|\s*evidence=(https://github\.com/hoffmannherdecke/kraken-eur-scanner/(?:issues|pull)/[0-9]+(?:#issuecomment-[0-9]+)?)\s*$"
)

def main():
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    issue = event["issue"]
    comment = event["comment"]
    if issue["number"] not in (99, 353) or comment.get("author_association") not in ("OWNER", "MEMBER", "COLLABORATOR"):
        raise SystemExit("Not an authorized project-owner comment")
    matches = RECEIPT.findall(comment["body"])
    if len(matches) != 1:
        raise SystemExit("No single, strictly formatted receipt")
    key, status, evidence = matches[0]
    if status not in ALLOWED:
        raise SystemExit("Invalid status")
    # A comment must prove itself: linking an unrelated owner note is not an ACK.
    if evidence != comment.get("html_url"):
        raise SystemExit("Receipt evidence must link to this exact authenticated comment")
    path = Path("PROJECT_BACKLOG.md")
    data = path.read_text(encoding="utf-8")
    if data.count(START) != 1 or data.count(END) != 1:
        raise SystemExit("Missing or ambiguous bounded synchronization section")
    start = data.index(START) + len(START)
    end = data.index(END, start)
    block = data[start:end]
    line = f"| `{key}` | `{status}` | [Owner receipt]({evidence}) |"
    lines = [x for x in block.splitlines() if x.startswith("| ") and not x.startswith("| Gate ") and not x.startswith("|---") and not x.startswith(f"| `{key}` |")]
    lines.append(line)
    lines = sorted(set(lines))
    newblock = "\n\n| Gate | Status | Latest owner receipt |\n|---|---|---|\n" + "\n".join(lines) + "\n\n"
    newdata = data[:start] + newblock + data[end:]
    if newdata == data:
        return
    path.write_text(newdata, encoding="utf-8")

if __name__ == "__main__":
    main()
