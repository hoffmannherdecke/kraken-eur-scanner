#!/usr/bin/env python3
"""Pure scanner job/run divergence diagnostics. No side effects or cancellation."""
from datetime import datetime, timezone

def _ts(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return None

def classify_active_run(run, jobs, now, stale_after=1200, job_timeout=720):
    age = int(now - (_ts(run.get("created_at")) or now))
    if run.get("status") not in ("queued", "in_progress"):
        return {"state": "NOT_ACTIVE", "age_seconds": age}
    if age <= stale_after:
        return {"state": "ACTIVE_RECENT", "age_seconds": age}
    if jobs is None:
        return {"state": "GITHUB_JOB_STATUS_UNKNOWN", "age_seconds": age}
    matches = [job for job in jobs if job.get("name") == "scan"]
    if len(matches) != 1:
        return {"state": "GITHUB_JOB_STATUS_UNKNOWN", "age_seconds": age}
    job = matches[0]
    steps = {step.get("name"): step for step in job.get("steps", [])}
    scan = steps.get("Scan Kraken EUR market") or {}
    handoff = steps.get("Upload compact ChatGPT handoff") or {}
    if (job.get("status") == "completed" and job.get("conclusion") == "success"
        and scan.get("conclusion") == "success" and handoff.get("conclusion") == "success"):
        return {"state": "JOB_DONE_RUN_ACK_DELAY", "age_seconds": age,
                "job_completed_at": job.get("completed_at"), "scan_completed_at": scan.get("completed_at")}
    if job.get("status") == "completed":
        return {"state": "JOB_TERMINAL_NOT_SUCCESS", "age_seconds": age}
    if job.get("status") == "queued" or run.get("status") == "queued":
        return {"state": "GITHUB_QUEUE_DELAY", "age_seconds": age}
    if job.get("status") == "in_progress":
        current = next((s for s in job.get("steps", []) if s.get("status") == "in_progress"), None)
        start = _ts(current.get("started_at")) if current else None
        if start is not None and now-start > job_timeout+300:
            return {"state": "JOB_PROGRESS_STALLED_UNVERIFIED", "age_seconds": age,
                    "step": current.get("name"), "step_age_seconds": int(now-start)}
        return {"state": "JOB_IN_PROGRESS_CADENCE_OVERDUE", "age_seconds": age}
    return {"state": "GITHUB_JOB_STATUS_UNKNOWN", "age_seconds": age}

def self_test():
    now = int(datetime(2026, 10, 22, 19, 30, tzinfo=timezone.utc).timestamp())
    def when(age):
        return datetime.fromtimestamp(now-age, timezone.utc).isoformat()
    run = {"status": "in_progress", "created_at": when(2266)}
    success = {"name": "scan", "status": "completed", "conclusion": "success",
               "completed_at": when(2200),
               "steps": [{"name": "Scan Kraken EUR market", "conclusion": "success", "completed_at": when(2230)},
                         {"name": "Upload compact ChatGPT handoff", "conclusion": "success"}]}
    def check(r, jobs, expected):
        actual = classify_active_run(r, jobs, now)["state"]
        assert actual == expected, (actual, expected)
    check(run, [success], "JOB_DONE_RUN_ACK_DELAY")
    check({**run, "created_at": when(150)}, [success], "ACTIVE_RECENT")
    check(run, None, "GITHUB_JOB_STATUS_UNKNOWN")
    check(run, [], "GITHUB_JOB_STATUS_UNKNOWN")
    check(run, [{**success, "conclusion": "failure"}], "JOB_TERMINAL_NOT_SUCCESS")
    check(run, [{**success, "steps": success["steps"][:1]}], "JOB_TERMINAL_NOT_SUCCESS")
    check({**run, "status": "queued"}, [{"name": "scan", "status": "queued"}], "GITHUB_QUEUE_DELAY")
    check(run, [{"name": "scan", "status": "in_progress",
                 "steps": [{"name": "Scan Kraken EUR market", "status": "in_progress", "started_at": when(1500)}]}],
          "JOB_PROGRESS_STALLED_UNVERIFIED")
    check(run, [{"name": "scan", "status": "in_progress",
                 "steps": [{"name": "Scan Kraken EUR market", "status": "in_progress", "started_at": when(80)}]}],
          "JOB_IN_PROGRESS_CADENCE_OVERDUE")
    check({"status": "completed", "created_at": when(100)}, None, "NOT_ACTIVE")
    print("WORKFLOW_RUN_HEALTH_SELFTEST PASS ten divergence/timeout/fail-closed cases")

if __name__ == "__main__":
    self_test()
