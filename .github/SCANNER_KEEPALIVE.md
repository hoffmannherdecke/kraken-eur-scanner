# Scanner keep-alive and external watchdog contract

Purpose: keep the GitHub fallback scanner schedulable and define the independent
health checks that the Mini-PC watchdog must implement later.

## Current GitHub fallback targets

- Scanner schedule target: every 10 minutes.
- Scanner stale threshold: 25 minutes.
- Unified Paper runtime is dispatched after every successful scan.
- Paper runtime stale threshold: 30 minutes while enabled.
- Watchdog schedule target: every 10 minutes.
- Real-money actions remain disabled.

GitHub Actions is still a common failure domain for scanner + watchdog. Therefore
"GitHub watchdog healthy" does **not** prove that GitHub scheduling itself is healthy.

## Mini-PC independent watchdog contract

When the Mini-PC is commissioned, its local watchdog must run independently of
GitHub Actions and check at least:

1. local internet/Kraken public API reachability;
2. local scanner heartbeat and last completed scan age;
3. GitHub fallback scanner last successful run age;
4. Paper runtime last successful run age;
5. queued candidate age / orphan candidates;
6. due WAIT TTL lag;
7. BUY without Slack receipt;
8. open position lifecycle age and any UNVERIFIED data-gap state;
9. local/Supabase archive sync age;
10. disk space, process restart count and clock drift.

If GitHub is unavailable, local scanner/data logging must continue. If local
components fail, GitHub remains the fallback. Neither side may enable real-money
orders merely because the other side is unavailable.

This file is documentation only; it must never contain API keys or secrets.
