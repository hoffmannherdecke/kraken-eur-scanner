# V2R4 technical runtime recovery: explicit roll-over gate (08.10.2026)

Status: **PREPARATION ONLY, NO CLOUD ACTIVATION, NO LOCAL SERIES ROTATION.**
Operator approval: user authorized a controlled technical version change in the current conversation; this is **not** approval to bypass failed safety gates.

## Verified facts and hard boundaries

- Active Supabase PAPER series: `PAPER-V2R4-20261007T184255Z` (600 archived candidate outcomes at the 08.10. 21:56 UTC read; no V2R4 paper trade). It must remain available with its existing source IDs and its original code/runtime fingerprint.
- Active MINI-PC immutable local control pins `release_repo_sha=3c6729a6c548d169f56a97f07f75892f37211636`, and source `v2r4-paper-local-runtime.py` is different from GitHub/main alias-outage fix (PR #90).
- The public WS v2 `BTC/EUR`, `DOGE/EUR` alias error and restart loop are understood. Supervisor safeguard PR #91 physically confirmed `BACKOFF` 08.10. 21:49:57 UTC.
- Frozen H3-001 is pinned to the **old exact series ID**, baseline SHA, config checksum and decision stream. `v3_h3_shadow_evidence` had no cloud rows at audit time; current cloud H3 status still exists. No silent binding to a new series.
- Current Supabase `v2r4-paper-evidence-relay` deployment only accepts first-series activation, tied to V2R3 approval ID, and `sync_h3_shadow` only accepts H3-001 and the original baseline ID. **Do not use its `activate` action for a second series** and do not mutate its production Edge function in place before controlled validation.
- The existing `tools/install-minipc-v2r4-paper-runtime.ps1` is a **first-release installer**, not a recovery updater; it copies files before checking pinned control/runtime hashes. NEVER execute it with `-Execute` against the old live app as a migration shortcut.
- Existing `paper_candidate_outcomes` and `paper_trade_results` are immutable evidence; future replay/upsert must preserve series origin, event clocks and idempotent candidate IDs.

## Minimal release sequence and ownership

**A. Autonomous / remote, without mini-PC interaction:** Maintain this gate plus `tools/minipc-v2r4-technical-rollover-preflight.ps1`, review static CI/PowerShell parse, inspect current Supabase schema and first-series relay, document the exact technical fix vs unchanged strategy. Prepare *separately* a bounded second-series activation API/transaction with two-factor authorization, exact expected predecessor ID and previous active status, one-active-series guarantee, rollback/timeout idempotency and retirement state. Do not install/deploy untested new Edge authorization. Prepare the successor H3-002 configuration against the **new series** and immutable config checksum, preserving H3-001 data as closed/diagnostic evidence; same preregistered H3 features, no promotion, no increase in concurrent strategy-changing shadows.

**B. Exactly one planned MINI-PC read-only checkpoint:** Run
`& "$env:USERPROFILE\Trading\Repos\kraken-eur-scanner\tools\minipc-v2r4-technical-rollover-preflight.ps1"`
only after the merged tool exists locally (`git pull --ff-only origin main`). It checks original paper series/paper-only, frozen SHA, differences between installed paper and GitHub code, original H3 baseline, affected Windows Task Scheduler actions, repo cleanliness and local decision counts. No API keys read, no file or task changes, no artificial power/network outages.

**B.1 Non-disruptive successor staging after PASS:** `tools/minipc-v2r4-technical-rollover-stage.ps1` offers PLAN_ONLY by default, and a separately confirmed `-Stage -Confirm STAGE_TECHNICAL_PAPER_ONLY` that copies only bounded, hash-verified source files into a NEW unique `Runtime/v2r4-paper-stage-<new-sha>` directory. It writes **no** `paper_runtime_control.json` and therefore cannot start, trade, create a cloud series or alter old H3 or old PAPER runtime. It verifies original series pins and 50+50 spec fingerprint before copying. A second stage attempt is manifest-checked, never overwrites a conflicting manifest. Handoffs/decisions/positions/follow-ups/WAIT/sync cursors are never copied across versions. Stop here until the transactional cloud cutover and H3-002 migration are independently reviewed.

**C. One controlled physical activation gate, ONLY after all components pass:**
1. Quiesce the 4 old PAPER tasks and H3-001 at an explicit UTC boundary; establish a coherent cutover time. Preserve scanner, WS recording, H10 and unrelated health tasks.
2. Last old-series cloud sync, immutable local snapshot/manifest of exact control/source/H3 state/decision/position/followup/WAIT/TTL/cursor files, with SHA-256 and enough free disk, and independently confirm Supabase counts. Missing or mismatching records = BLOCKED; keep old series intact.
3. Build the successor in **a separate app directory** from pinned Git SHA. Same market/strategy/sizing/fees, no real orders; new versioned runtime fingerprint and new paper series ID; never overwrite the old `Runtime/v2r4-paper-app`. Restore only explicitly approved shared/static config, not old candidates/decisions/WAIT/alert/sync cursors.
4. Atomic authenticated cloud cutover (new explicitly approved technical release, not old V2R3 activation): exactly one new PAPER series active, old one marked `technical_closed`/appropriate diagnostic status, original provenance retained. No new historical paper entries. Any incomplete old-series 6h/24h evidence remains explicit `MISSING`/pending and can only mature under a separate evidence-only archive path.
5. Repoint/start PAPER scheduled tasks to successor app using the frozen new release bundle, isolating local lifecycle/sync cursors. H3-001 stays stopped, not silently rebound. H3-002 may start only when its **new** config/relay and unchanged H3 gates pass with that new baseline.
6. Exactly one post-switch normal healthy data/side-effect E2E: source fresh, candidate heartbeat, WAIT TTL, lifecycle/sync ACK, no duplicates/old BUY on stale events, Supabase one active series, real-money disabled. On failure, fail closed and preserve old plus new snapshots; never resurrect 2 active series or retry forever.
7. Update `project-current-state.json` **in the same explicit release sequence** and record exact predecessor/successor IDs, UTC cutover, SHA/hash, intentional H3-001 closure and H3-002 gate. Only then close GitHub Issue #89.

**D. Follow-through:** Continue ordinary H10 and public scanner during the bounded cutover; retain historical observations without inventing candles. Safety and data consistency outrank exact wall-clock convenience; no arbitrarily repeated stress tests or new Work/GitHub schedules.

## Bounded acceptance

- No real-money/order API, no new secret, no new Runner, no extra scheduler.
- Reproducible original evidence + clean technical continuity **with new series ID**.
- Immutable H3-001 and fresh H3 successor, if separately approved and tested.
- Paper data are trustworthy per fixed runtime version; outage gaps tagged, never backfilled with today's price.
- Physical gate and cloud cutover **NOT COMPLETE** at creation of this note.
