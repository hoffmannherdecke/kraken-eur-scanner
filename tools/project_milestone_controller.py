#!/usr/bin/env python3
"""Bounded, read-only milestone gate evaluator with one-shot notifications.

Authoritative declared state: project-current-state.json.
Authoritative live evidence: Supabase views (GET only).
Allowed writes: one GitHub issue comment and optional Slack message per ready gate.
Never changes project state, release status, strategy, thresholds, orders or DB rows.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc
ISSUE_BY_KIND = {"H3_FIXED_REVIEW": 7, "PAPER_FINAL_REVIEW": 38,
                 "PAPER_LOW_TRADES": 38, "H10_CONTRACT": 7}
REQUIRED_DECISIONS = {"V3-H3-FIXED-REVIEW", "V2R4-PRODUCTIVITY-REVIEW"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError("FAIL_CLOSED: " + message)


def iso_time(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def load_local_state(root: Path) -> dict:
    state = json.loads((root / "project-current-state.json").read_text("utf-8"))
    require(state.get("kind") == "PROJECT_CURRENT_STATE_V1", "unknown state schema")
    active = state.get("active_strategy") or {}
    inv = state.get("permanent_invariants") or {}
    require(active.get("mode") == "PAPER", "current control supports PAPER only")
    require(active.get("automatic_activation_allowed") is False, "auto activation forbidden")
    require(active.get("real_money_actions") is False, "real money forbidden")
    require(active.get("mid_series_material_tuning_allowed") is False, "mid-series tuning forbidden")
    require(inv.get("automatic_strategy_promotion") is False, "auto promotion forbidden")
    require(inv.get("one_strategy_changing_shadow_at_a_time") is True, "shadow WIP rule missing")
    shadows = (state.get("strategy_changing_shadow_wip") or {}).get("active") or []
    require(len(shadows) <= 1, "more than one strategy-changing shadow")
    decision_ids = {x.get("id") for x in state.get("next_control_decisions") or []}
    require(REQUIRED_DECISIONS <= decision_ids, "canonical decisions missing")
    return state


def get_rows(base: str, key: str, view: str) -> list:
    require(re.fullmatch(r"https://[a-z0-9-]+[.]supabase[.]co", base.rstrip("/")) is not None,
            "unapproved Supabase host")
    require(view in {"paper_series_completion_readiness", "v3_h3_shadow_status"},
            "unapproved evidence view")
    url = base.rstrip("/") + "/rest/v1/" + view + "?select=*"
    req = urllib.request.Request(url, headers={
        "apikey": key, "Authorization": "Bearer " + key,
        "Accept": "application/json", "User-Agent": "project-milestone-controller/1",
    })
    with urllib.request.urlopen(req, timeout=15) as response:
        rows = json.load(response)
    require(isinstance(rows, list) and len(rows) == 1, view + " must return exactly one row")
    return rows


def event(kind: str, anchor: str, detail: str) -> dict:
    require(kind in ISSUE_BY_KIND, "unapproved event kind")
    require(bool(anchor) and len(anchor) < 180, "invalid event anchor")
    digest = hashlib.sha256((kind + "|" + anchor).encode("utf-8")).hexdigest()[:20]
    return {"kind": kind, "event_key": "PROJECT_MILESTONE_V1_" + digest,
            "issue": ISSUE_BY_KIND[kind], "detail": detail}


def evaluate(state: dict, paper: dict, h3: dict, now: dt.datetime, root: Path) -> dict:
    active = state["active_strategy"]
    series = active["series_id"]
    require(paper.get("series_id") == series, "paper series drift")
    require(paper.get("strategy_revision") == active["strategy_revision"],
            "paper revision drift")
    require(paper.get("fasttrack_policy_version") == "EVIDENCE_DIVERSITY_FASTTRACK_V2",
            "unknown paper completion policy")
    require(paper.get("candidate_outcomes") is not None, "missing paper outcomes")
    require(paper.get("completed_trades") is not None, "missing trade counts")
    notices = []
    statuses = []
    if paper.get("completion_ready") is True:
        require(paper.get("intake_should_stop") is True,
                "completion gate contradicts intake state")
        require(paper.get("temporal_diversity_ready") is True and
                paper.get("qualifying_maturity_ready") is True,
                "paper completion bypasses evidence maturity/diversity")
        statuses.append("V2R4:FINAL_REVIEW_READY")
        notices.append(event("PAPER_FINAL_REVIEW", series,
                             "Paper-Abschlussgate erreicht: finale Auswertung, "
                             "Erkenntnis-Migration und separate Release-Entscheidung vorbereiten. "
                             "KEINE automatische Strategieaktivierung."))
    else:
        statuses.append("V2R4:COLLECTING")
        if (float(paper.get("series_age_days") or 0) >= 3
                and int(paper["candidate_outcomes"]) >= 100
                and int(paper.get("complete_24h") or 0) >= 30
                and int(paper["completed_trades"]) == 0):
            statuses.append("V2R4:LOW_TRADE_REVIEW")
            notices.append(event("PAPER_LOW_TRADES", series,
                                 "72h-Frühreview: >100 Kandidaten, >=30 vollständige "
                                 "24h-Follow-ups und 0 Trades. Funnel, WAIT/TTL, "
                                 "Missed-Moves, Kosten und Datenqualität analysieren. "
                                 "Aktive Serie unverändert lassen."))

    shadows = (state.get("strategy_changing_shadow_wip") or {}).get("active") or []
    if shadows:
        sh = shadows[0]
        require(sh.get("candidate_id") == "V3-H3-SHADOW-001",
                "unknown active shadow needs controller update")
        require(h3.get("shadow_candidate_id") == sh["candidate_id"],
                "H3 status candidate drift")
        require(iso_time(h3["generated_at"]) >= now - dt.timedelta(hours=2),
                "H3 evidence stale")
        p = h3.get("payload") or {}
        require(p.get("baseline_series_id") == series, "H3 baseline series drift")
        require(p.get("baseline_strategy_revision") == active["strategy_revision"],
                "H3 baseline revision drift")
        for k in ("orders", "real_money_actions", "automatic_promotion",
                  "automatic_extension"):
            require(p.get(k) is False, "H3 safety invariant " + k)
        if p.get("minimum_gate_met") is True:
            dates = p.get("distinct_utc_dates") or []
            require(int(p.get("eligible_matched_candidates") or 0) >= 20
                    and len(set(dates)) >= 2
                    and float(p.get("capture_success_pct") or 0) >= 95,
                    "H3 claimed gate without preregistered sample/capture evidence")
            require(p.get("intake_should_stop") is True,
                    "H3 gate reached but no stop state")
            if p.get("outcome_review_ready") is True:
                statuses.append("H3:FIXED_REVIEW_READY")
                divergences = int(p.get("causal_decision_divergences") or 0)
                recommendation = ("INCONCLUSIVE_LOW_IMPACT"
                                  if divergences < 3 else "FORMAL_REVIEW_REQUIRED")
                notices.append(event("H3_FIXED_REVIEW",
                                     sh["candidate_id"] + "|" + series,
                                     "H3-Fixreview fällig: " + recommendation +
                                     "; Baseline-Replay, Kosten, Follow-ups und "
                                     "Preregistrierung überprüfen. H6 erst nach "
                                     "abgeschlossenem H3-Review / separatem Gate."))
            else:
                statuses.append("H3:WAIT_FOLLOWUPS")
        else:
            statuses.append("H3:COLLECTING")
    else:
        statuses.append("H3:NO_ACTIVE_SHADOW")

    h10 = next((x for x in state.get("observational_research_tracks") or []
                if x.get("id") == "V3-H10-CAPTURE-001"), None)
    if h10 and "FIRST_REVIEW_COMPLETE_MORE_TESTING_REQUIRED" in h10.get("status", ""):
        contract = root / "research/v3/h10-kraken-outcome-context-join-contract-v1.json"
        if not contract.exists():
            statuses.append("H10:NEXT_CONTRACT_DUE")
            notices.append(event("H10_CONTRACT", h10["id"],
                                 "H10-Erstreview abgeschlossen. Vor neuer "
                                 "Outcome-Analyse PIT-Kraken-EUR-Join, fixes "
                                 "False-Positive-Label und Konfliktregel "
                                 "preregistrieren. Capture läuft unverändert weiter."))
        else:
            statuses.append("H10:CONTRACT_PRESENT_REVIEW_NEEDED")
    queued = (state.get("strategy_changing_shadow_wip") or {}).get("queued") or []
    if any(x.get("candidate_id") == "V3-H6-NEXT" for x in queued):
        statuses.append("H6:WAIT_H3_REVIEW_NO_AUTO_START")
    return {"kind": "PROJECT_MILESTONE_CONTROL_V1", "series_id": series,
            "statuses": statuses, "events": notices,
            "strategy_changed": False, "orders": False,
            "real_money_actions": False}


def gh_request(url: str, token: str, method: str = "GET", payload=None):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "project-milestone-controller/1",
        **({"Content-Type": "application/json"} if payload is not None else {}),
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def publish_once(repo: str, token: str, note: dict, slack: str) -> str:
    require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) is not None,
            "invalid GitHub repository")
    require(repo == "hoffmannherdecke/kraken-eur-scanner", "unexpected repository")
    endpoint = "https://api.github.com/repos/" + repo + "/issues/" + str(note["issue"]) + "/comments"
    marker = "<!-- " + note["event_key"] + " -->"
    page = 1
    while True:
        comments = gh_request(endpoint + "?per_page=100&page=" + str(page), token)
        require(isinstance(comments, list), "GitHub comment list invalid")
        for comment in comments:
            if (marker in str(comment.get("body") or "") and
                    (comment.get("user") or {}).get("login") == "github-actions[bot]"):
                return "ALREADY_RECORDED"
        if len(comments) < 100:
            break
        page += 1
        require(page <= 20, "unbounded GitHub comment history")
    message = "Projekt-Controlling: " + note["detail"] + "\n\n" + marker
    # GitHub comment is the durable, deduplicated milestone receipt.
    gh_request(endpoint, token, "POST", {"body": message})
    if slack:
        req = urllib.request.Request(slack, data=json.dumps({
            "text": "PROJEKT-MEILENSTEIN: " + note["detail"] +
                    "\nGitHub Issue #" + str(note["issue"])
        }).encode("utf-8"), method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            require(200 <= resp.status < 300, "Slack notification rejected")
    return "CREATED"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path,
                        help="JSON fixture with paper and h3 rows; disables all writes")
    parser.add_argument("--publish", action="store_true",
                        help="explicitly post once-per-milestone notifications")
    args = parser.parse_args()
    require(not (args.fixture and args.publish), "fixture cannot publish")
    state = load_local_state(ROOT)
    if args.fixture:
        fixture = json.loads(args.fixture.read_text("utf-8"))
        paper, h3 = fixture["paper"], fixture["h3"]
        now = iso_time(fixture["now"])
    else:
        base = os.environ.get("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        require(bool(key), "missing Supabase evidence credential")
        paper = get_rows(base, key, "paper_series_completion_readiness")[0]
        h3 = get_rows(base, key, "v3_h3_shadow_status")[0]
        now = dt.datetime.now(UTC)
    result = evaluate(state, paper, h3, now, ROOT)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as out:
            out.write("## Autonomous milestone control\n\n")
            for status in result["statuses"]:
                out.write("- " + status + "\n")
            out.write("\nUpcoming notifications: " + str(len(result["events"])) + "\n")
    if args.publish:
        token, repo = os.environ.get("GITHUB_TOKEN", ""), os.environ.get("GITHUB_REPOSITORY", "")
        require(bool(token), "missing GitHub issue token")
        for note in result["events"]:
            status = publish_once(repo, token, note, os.getenv("SLACK_WEBHOOK_URL", ""))
            print("MILESTONE " + note["kind"] + ": " + status)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print("MILESTONE_CONTROL_BLOCKED " + str(exc), file=sys.stderr)
        sys.exit(2)
