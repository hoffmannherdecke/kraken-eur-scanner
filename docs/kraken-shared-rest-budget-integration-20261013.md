# Kraken public REST: single-host shared budget (inactive until physical enrollment)

## Source ownership / unchanged boundaries

Existing Mini-PC public REST call sites use the **one existing source policy** in
`market_data/kraken_public_budget.py`; no polling service, daemon, new cloud
table, login, or private Kraken/Trading endpoint is introduced.

| Existing caller | Public REST | Proposed role | Status |
| --- | --- | --- | --- |
| `paper_evaluator/v2r4_wait_watcher.py` (V2R4 WAIT original source module) | Fresh Ticker + closed OHLC 1/5/15 | bounded WAIT (instant budget refusal; paper fail-closed) | GitHub code only, requires new protected isolated package including the module |
| `tools/minipc-kraken-universe-feed.py` | AssetPairs refresh; WebSocket ticker feed untouched | operational universe (at most 1.5s admission wait) | GitHub code only, original task must be inventoried before enrollment |
| `paper_evaluator/v2r4_precandidate_watcher.py` | batched Ticker, conditional Depth, AssetPairs | discovery (at most 1.5s admission wait) | GitHub code only; task owner existence must be proven before enrollment |
| `market_data/rest.py` used by `paper_capture/market.py` | REST OHLC/Ticker context | research/fresh context (at most 1.5s admission wait) | GitHub code only; hosted GitHub runner is a **different IP** and must not assume MINI-PC enrollment |
| WS-only canary / WS-Shadow / scanner WebSocket | WebSocket | **not a REST consumer** | no change |

Additional scripts using direct Kraken REST, on/off-host deployments, and third
party clients must be separately inventoried. Until **all enabled consumers of
the MINI-PC outbound IP** use the same path, this is a PARTIAL rather than
complete shared rate budget.

## Semantics and resource bounds

The feature is **off by default**. For each verified owner, enroll through
the SAME absolute `KRAKEN_PUBLIC_BUDGET_DIR` in the task's actual execution
context (often SYSTEM, **not** the interactive ADMIN shell).

An OS file lock serializes short reservations into one tiny JSON state file:
- Public Ticker, Depth, AssetPairs, and other non-OHLC/Trades endpoints share
  one IP scope (conservative 1 request per 1.25 seconds).
- Public OHLC and Trades use separate scopes **per normalized Kraken pair**,
  matching Kraken's published IP+pair limit. Different pairs and the IP scope
  do not unnecessarily block each other.
- If the applicable budget is full, WAIT declines instantly (does not call
  Kraken), other existing helpers wait at most 1.5 seconds. All missing data
  remains fail-closed, never reuses a stale ticker or fabricates a receipt.
- A real `EGeneral:Too many requests`, `rate limit` error or HTTP 429
  records a 20-second scope-specific cooldown; the next call cannot bypass it.
  Each HTTP attempt reserves its slot **before** network activity.
- State is atomic, bounded and scrubbed after one hour; pair names are stored
  as truncated SHA-256 hashes, not raw candidate IDs or API keys. Corrupt
  or inaccessible state is a hard denial for enrolled clients.
- Future budget-driven WAIT `DEGRADED` heartbeats must be distinguished
  from process death by the **existing RuntimeSupervisor owner**; a separate
  tested policy guard is mandatory BEFORE activating admission limits on WAIT,
  otherwise expected budget deferrals could trigger pointless restarts.

Kraken Spot public REST limits by IP for most endpoints and IP+pair for
OHLC/Trades; their updated source is
https://support.kraken.com/de/articles/206548367-what-are-the-api-rate-limits- .

## Required physical acceptance (not yet executed)

1. Keep PR291 WAIT active without file/task modification. Freeze exact owner
   actions, single process tree, 19/19 prior tests, SHA/rollback and current
   series `PAPER-V2R4-20261009T110135Z`.
2. Run offline cross-process claim tests **on Windows** as SYSTEM-compatible
   isolated staging and verify same absolute root ACL and correct source
   module path for the PR291 isolated launcher. Do not assume ADMIN env reaches
   scheduled tasks running under SYSTEM.
3. Prove Supervisor does **not** restart an otherwise live WAIT due solely to
   budget deferral or Kraken source rate-limit; still restart stale/dead tasks.
   Keep task health, cloud sync, WS Shadow and Paper-Lifecycle visible.
4. Verify all true original public REST owners on the host and their actual
   startup/stage path; enroll only after shared-state and producer priorities
   are proven. Never use one automated restart loop to self-provoke an API ban.
5. Carry out explicit guarded host-only cutover with restore-on-error and
   exact original task XML/commit backup. Check no concurrent WAIT writer and
   fresh source/receipt/lifecycle/cloud ACKs. A GitHub CI PASS is NOT this gate.
6. Compare budget grants/refusals, rate-limit error classes, WAIT checks,
   Kraken HTTP request counts, missed signal windows and paper-only decisions
   over realistic 1m/5m/15m boundaries. Keep protection only if it reduces
   source load without unacceptably reducing fresh eligible opportunities.
7. Keep V3 paper six-proofs and exclusive single writer independent; the
   shared budget alone grants no V3 rollout and no real-money authorization.

Existing owner: GitHub Issue #99 and canonical
`V2R4_WAIT_INCIDENT_PHYSICAL_FOLLOWTHROUGH`. Do not close them on source-only
code merge.
