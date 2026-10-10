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

try:
    from tools.strategy_epoch_lineage import summarize_epoch
except ModuleNotFoundError:
    from strategy_epoch_lineage import summarize_epoch

ROOT = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc
ISSUE_BY_KIND = {"H3_FIXED_REVIEW": 7, "H3_STALE_EVIDENCE": 7,
                 "H3_ARCHIVED_INCOMPLETE_REVIEW": 7, "PAPER_FINAL_REVIEW": 38,
                 "PAPER_LOW_TRADES": 38, "CONTROL_FOLLOWTHROUGH_MISSED": 38, "H10_CONTRACT": 7,
                 "NEW_SHADOW_ADAPTER": 7, "NEW_CONTROL_DECISION": 7}
SUPPORTED_DECISIONS = {"V3-H3-ARCHIVE-DISPOSITION", "V2R4-PRODUCTIVITY-REVIEW",
                       "V3-EXTENDED-SECOND-LEG-LEARNING-GATE"}


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
    decisions = state.get("next_control_decisions") or []
    ids = [x.get("id") for x in decisions]
    require(len(ids) == len(set(ids)) and all(ids), "duplicate/invalid control decisions")
    return state


def get_rows(base: str, key: str, view: str) -> list:
    require(re.fullmatch(r"https://[a-z0-9-]+[.]supabase[.]co", base.rstrip("/")) is not None,
            "unapproved Supabase host")
    require(view in {"paper_series_completion_readiness", "v3_h3_shadow_status"},
            "unapproved evidence view")
    url = base.rstrip("/") + "/rest/v1/" + view + "?select=*"
    headers = {"apikey": key, "Accept": "application/json",
               "User-Agent": "project-milestone-controller/1"}
    if not key.startswith("sb_secret_"):
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(url, headers=headers)
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
    # Supabase readiness follows the currently active technical series, while
    # project-current-state holds the ORIGINAL frozen H3/strategy epoch lineage.
    # Explicitly bind a verified technical successor; never silently accept a
    # foreign/released strategy or reset the economic review clock on rotation.
    live_series = paper.get("series_id")
    technical = active.get("technical_rotation_runtime_last_verified") or {}
    if live_series != series:
        require(live_series == technical.get("series_id")
                and technical.get("original_strategy_epoch_series_id") == series
                and technical.get("relation") ==
                    "TECHNICAL_ROTATION_SAME_STRATEGY_FINGERPRINT_NOT_STRATEGY_RELEASE"
                and technical.get("frozen_h3_baseline_changed") is False
                and technical.get("productivity_clock_reset") is False,
                "unapproved technical series rotation / strategy epoch drift")
    require(paper.get("strategy_revision") == active["strategy_revision"],
            "paper revision drift")
    require(paper.get("fasttrack_policy_version") == "EVIDENCE_DIVERSITY_FASTTRACK_V2",
            "unknown paper completion policy")
    require(paper.get("candidate_outcomes") is not None, "missing paper outcomes")
    require(paper.get("completed_trades") is not None, "missing trade counts")
    epoch_stamp = active.get("original_strategy_epoch_started_at_utc")
    require(epoch_stamp == "2026-10-07T18:42:55Z",
            "V2R4 original activation epoch missing or unexpectedly moved")
    epoch_start = iso_time(epoch_stamp)
    require(now >= epoch_start, "review clock before original strategy epoch")
    strategy_epoch_age_days = (now - epoch_start).total_seconds() / 86400.0
    # Single shared economic/lineage contract also enforced by control plane.
    aggregate=summarize_epoch(active,paper)
    epoch_min_outcomes=int(aggregate["epoch_minimum_candidate_outcomes"])
    epoch_min_trades=int(aggregate["epoch_minimum_completed_trades"])
    epoch_min_mature24=int(aggregate["epoch_minimum_complete_24h"])
    notices = []
    statuses = []
    # Generic fail-safe: a duly reached control gate must have a documented
    # Work receipt, not merely a GitHub notice or a chat promise.
    for decision_id, note in due_followthrough_events(state, now, root):
        statuses.append("FOLLOWTHROUGH:ACK_OVERDUE:" + decision_id)
        notices.append(note)
    for task in state.get("next_control_decisions") or []:
        if task["id"] not in SUPPORTED_DECISIONS:
            statuses.append("CONTROL:ADAPTER_REQUIRED:" + task["id"])
            notices.append(event("NEW_CONTROL_DECISION", task["id"],
                                 "Neue kanonische Projektentscheidung braucht ein "
                                 "versioniertes Gate/Read-only-Adapter. Keine stille "
                                 "Überspringung und keine ungeprüfte Aktivierung."))
    # A known, governance-only V3 followup; no new active trial or schedule.
    v3_next = next((task for task in state.get("next_control_decisions") or []
                    if task.get("id") == "V3-EXTENDED-SECOND-LEG-LEARNING-GATE"), None)
    if v3_next is not None:
        require(
            v3_next.get("canonical_owner") ==
            "research/v3-migration-ledger.json#late_chase_protection.successor_refinement",
            "V3 second-leg research decision must retain canonical migration owner")
        require(v3_next.get("no_new_work_run") is True
                and v3_next.get("no_active_strategy_change") is True,
                "V3 second-leg finding cannot initiate Work or alter active paper")
        statuses.append("V3:EXTENDED_SECOND_LEG_STAGED_FOR_NEXT_REVIEW_NO_AUTO_START")
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
                             "KEINE automatische Strategieaktivierung. "
                             "Offenes V3-EXTENDED-Zweite-Welle-0-BUY-Finding "
                             "aus dem Migrationsledger zwingend disponieren: "
                             "erst Coin-Evidence-A, dann getrennt Review-B."))
    else:
        statuses.append("V2R4:COLLECTING")
        # The append-only archive preserves *all* closed segments' verified
        # mature evidence and the live segment's Supabase counters exactly once.
        # No technical rotation resets the strategic productivity clock.
        # This is an EARLY pathology review, never the 1000-outcome release gate.
        if (strategy_epoch_age_days >= 3
                and epoch_min_outcomes >= 100
                and epoch_min_mature24 >= 30
                and epoch_min_trades == 0):
            statuses.append("V2R4:LOW_TRADE_REVIEW")
            notices.append(event("PAPER_LOW_TRADES", series,
                                 "72h-STRATEGIEEPOCHEN-FRÜHREVIEW (Uhr ab 07.10. "
                                 "20:42:55 MESZ; technische Serienrotation KEIN RESET): "
                                 "beide nachprüfbaren technischen Teilserien "
                                 "gemeinsam betrachten: alte abgeschlossene Serie "
                                 "1011 Outcomes, 260 vollständige 24h-Verläufe, "
                                 "0 Trades; aktuelle Serie liefert weitere "
                                 "tagesaktuelle Daten. Wirtschaftliche Null-BUY- "
                                 "Konversion ist ein zwingender REVIEW, nicht "
                                 "gleichbedeutend mit freigegebenem Abschluss. "
                                 "Funnel, WAIT/TTL, "
                                 "Missed-Moves, Kosten und Datenqualität analysieren. "
                                 "Aktive Serie unverändert lassen. "
                                 "Das V3-EXTENDED-Zweite-Welle-Finding mit "
                                 "separater Coin-Evidence-Stufe A und späterer "
                                 "Neubewertung-Stufe B im Review disponieren; "
                                 "MFE im Rückblick ist kein Handelsgewinn."))

    shadows = (state.get("strategy_changing_shadow_wip") or {}).get("active") or []
    if shadows:
        sh = shadows[0]
        if sh.get("candidate_id") != "V3-H3-SHADOW-001":
            statuses.append("SHADOW:ADAPTER_REQUIRED")
            notices.append(event("NEW_SHADOW_ADAPTER", sh.get("candidate_id") or "UNKNOWN",
                                 "Neue aktive Shadow-Version erkannt: separaten "
                                 "Evidence-/Review-Adapter hinzufügen und die "
                                 "Baseline-/Freeze-Gates prüfen. Keine Promotion."))
        else:
            require(h3 is not None, "H3 live evidence unavailable")
            require(h3.get("shadow_candidate_id") == sh["candidate_id"],
                    "H3 status candidate drift")
            p = h3.get("payload") or {}
            require(p.get("baseline_series_id") == series, "H3 baseline series drift")
            require(p.get("baseline_strategy_revision") == active["strategy_revision"],
                    "H3 baseline revision drift")
            for k in ("orders", "real_money_actions", "automatic_promotion",
                      "automatic_extension"):
                require(p.get(k) is False, "H3 safety invariant " + k)
            # Keep hard safety and baseline checks even when H3 is stale.
            # Stale H3 cannot signal FIXED_REVIEW_READY, but MUST NOT prevent
            # independent V2R4 economic productivity notices from completing.
            if iso_time(h3["generated_at"]) < now - dt.timedelta(hours=2):
                statuses.append("H3:EVIDENCE_STALE_FIXED_REVIEW_BLOCKED")
                notices.append(event("H3_STALE_EVIDENCE",
                                     sh["candidate_id"] + "|" + series,
                                     "H3-Shadow-Status veraltet: keine H3-Fixreview "
                                     "oder neue Strategie/zweiten Shadow freigeben. "
                                     "Eigenen H3-Datenpfad separat prüfen; "
                                     "V2R4-Trading-Produktivitätsreview bleibt "
                                     "unabhängig davon fällig. Keine Live-Änderung."))
            else:
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
                                             "abgeschlossenem H3-Review / separatem Gate. "
                                             "Danach offenes EXTENDED-Zweite-Welle-Finding "
                                             "verbindlich prüfen: zuerst Kraken-Coin-Daten "
                                             "als einziger geänderter A-Input, danach "
                                             "separate B-Neubewertung nur mit Kosten/Stop "
                                             "und ohne automatische Promotion."))
                    else:
                        statuses.append("H3:WAIT_FOLLOWUPS")
                else:
                    statuses.append("H3:COLLECTING")
    else:
        archived = [x for x in (state.get("closed_or_rejected_tracks") or [])
                    if x.get("id") == "V3-H3-SHADOW-001"]
        if archived:
            require(len(archived)==1, "H3 archived more than once")
            h3_archive=archived[0]
            require(h3_archive.get("status")=="ARCHIVED_INCOMPLETE_NOT_FIXED_REVIEWED"
                    and h3_archive.get("fixed_review_completed") is False
                    and h3_archive.get("promotion_eligible") is False
                    and h3_archive.get("cloud_causal_evidence_rows_at_review")==0
                    and h3_archive.get("former_frozen_baseline_series_id")==series,
                    "H3 archive incorrectly claims full evidence or a passed fixed review")
            statuses.append("H3:ARCHIVED_INCOMPLETE_NO_FIXED_REVIEW")
            if h3_archive.get("archive_disposition")=="DEFER_WITH_GATE":
                statuses.append("H3:ARCHIVE_DISPOSITION_DEFER_WITH_GATE")
            else:
                notices.append(event("H3_ARCHIVED_INCOMPLETE_REVIEW",
                                     h3_archive["id"]+"|"+series,
                                     "H3-001 wurde beim technischen Cutover archiviert; "
                                     "0 prospektive Cloud-Schattenbelege. Die alte "
                                     "SHADOW_RUNNING-Angabe ist beendet. Kein H3-Fixed-"
                                     "Review bestanden, H6 bleibt bis zur gesonderten "
                                     "Archiv-/Kausalitätsentscheidung gesperrt. "
                                     "V2R4-Handelsbewertung läuft weiter."))
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
    if any(x.get("candidate_id")=="V3-H6-NEXT" for x in queued):
        if any(x.get("status")=="WAIT_FOR_H3_ARCHIVED_INCOMPLETE_EXPLICIT_DISPOSITION"
               for x in queued if x.get("candidate_id")=="V3-H6-NEXT"):
            statuses.append("H6:BLOCKED_H3_ARCHIVED_INCOMPLETE_NO_AUTO_START")
        elif any(x.get("status")=="WAIT_FOR_V2R4_ECONOMIC_REVIEW_AND_SEPARATE_EXPLICIT_APPROVAL"
                 for x in queued if x.get("candidate_id")=="V3-H6-NEXT"):
            statuses.append("H6:BLOCKED_V2R4_REVIEW_AND_EXPLICIT_APPROVAL_NO_AUTO_START")
        else:
            statuses.append("H6:WAIT_H3_REVIEW_NO_AUTO_START")
    return {"kind": "PROJECT_MILESTONE_CONTROL_V1", "series_id": series,
            "live_technical_series_id": live_series,
            "epoch_minimum_candidate_outcomes": epoch_min_outcomes,
            "epoch_minimum_completed_trades": epoch_min_trades,
            "epoch_minimum_complete_24h": epoch_min_mature24,
            "epoch_combines_verified_technical_segments": live_series!=series,
            "strategy_epoch_started_at_utc": epoch_stamp,
            "strategy_epoch_age_days": round(strategy_epoch_age_days, 4),
            "statuses": statuses, "events": notices,
            "strategy_changed": False, "orders": False,
            "real_money_actions": False}



def due_followthrough_events(state: dict, now: dt.datetime, root: Path) -> list:
    """Independent of Supabase liveness: overdue work receipts still escalate."""
    return [(decision_id, event(
        "CONTROL_FOLLOWTHROUGH_MISSED", ack_key,
        "Autonomie-Übergabe überfällig: " + decision_id +
        ". Trotz abgelaufenem Gate und Nachfrist fehlt ein belegter "
        "Work-Abschluss/Entscheidungsbeleg. Bestehenden 10:15-Work-Pfad "
        "gezielt reparieren oder konkreten Nutzer-Blocker melden; "
        "kein zweiter Work-Lauf, keine automatische Strategieänderung."))
        for decision_id, ack_key in unacknowledged_control_decisions(state, now, root)]


def unacknowledged_control_decisions(state: dict, now: dt.datetime, root: Path) -> list:
    """Detect silent due-gate handoff failures without modifying any runtime."""
    path = root / "research/work-analysis-state.json"
    try:
        work = json.loads(path.read_text("utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        work = {}
    reviews = ((work.get("acknowledgements") or {}).get("control_decision_reviews") or {})
    unacknowledged = []
    for decision in state.get("next_control_decisions") or []:
        due = decision.get("due_at_utc")
        ack_key = decision.get("followthrough_ack_key")
        lag = decision.get("followthrough_max_lag_hours")
        if due is None and ack_key is None and lag is None:
            continue
        require(isinstance(due, str) and isinstance(ack_key, str)
                and re.fullmatch(r"[A-Za-z0-9_.-]{5,120}", ack_key) is not None
                and type(lag) is int and 1 <= lag <= 168,
                "invalid followthrough contract")
        due_time = iso_time(due)
        if now < due_time + dt.timedelta(hours=lag):
            continue
        record = reviews.get(ack_key)
        if isinstance(record, dict) and record.get("status") in {
                "COMPLETED", "DECISION_PACKET_READY", "BLOCKED_WITH_ACTION"}:
            report = record.get("report")
            completed = record.get("completed_at_utc")
            if (isinstance(report, str)
                    and re.fullmatch(r"research/work-analysis/[A-Za-z0-9_.-]+[.]md", report)
                    and isinstance(completed, str) and (root / report).is_file()):
                try:
                    completed_time = iso_time(completed)
                    if due_time <= completed_time <= now:
                        continue
                except (ValueError, TypeError):
                    pass  # Invalid evidence is missing evidence, not a controller crash.
        unacknowledged.append((decision["id"], ack_key))
    return unacknowledged

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
        try:
            paper = get_rows(base, key, "paper_series_completion_readiness")[0]
            shadows = (state.get("strategy_changing_shadow_wip") or {}).get("active") or []
            h3 = (get_rows(base, key, "v3_h3_shadow_status")[0]
                  if shadows and shadows[0].get("candidate_id") == "V3-H3-SHADOW-001"
                  else None)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            # Critical control-plane independence: Supabase downtime must not
            # suppress an already-overdue, locally evidenced Work handoff.
            # Never invent trading readiness or claim HEALTHY in degraded mode.
            now = dt.datetime.now(UTC)
            overdue = due_followthrough_events(state, now, ROOT)
            print(json.dumps({"kind": "PROJECT_MILESTONE_CONTROL_DEGRADED_V1",
                              "status": "SUPABASE_EVIDENCE_UNAVAILABLE",
                              "overdue_followthrough_only": [decision for decision, _ in overdue],
                              "strategy_changed": False, "orders": False,
                              "real_money_actions": False}, sort_keys=True))
            if args.publish:
                token, repo = os.environ.get("GITHUB_TOKEN", ""), os.environ.get("GITHUB_REPOSITORY", "")
                if overdue:
                    require(bool(token), "missing GitHub token for overdue fallback")
                for _, note in overdue:
                    publish_once(repo, token, note, os.getenv("SLACK_WEBHOOK_URL", ""))
            print("MILESTONE_CONTROL_BLOCKED Supabase read-only evidence unavailable: " +
                  str(exc), file=sys.stderr)
            return 2
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
