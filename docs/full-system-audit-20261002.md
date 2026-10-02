# Full system / architecture / strategy audit — 2026-10-02

Status: **SYSTEM FUNCTIONAL / NO CURRENT CRITICAL INFRASTRUCTURE FAULT / ACTIVE V2R3 STRATEGY CONCERNS UNDER OBSERVATION**

Purpose: end-to-end verification after MINI-PC commissioning and recent infrastructure/documentation changes. This audit does **not** authorize a strategy change, V2R4 activation, orders or real-money action.

## Infrastructure and runtime

- MINI-PC central status: **HEALTHY / OK / issues=[]**.
- Latest verified local checks: Kraken DNS/TCP/HTTPS OK; C: ~177.6 GB free of 237.4 GB; backup fresh; status sync healthy.
- Kraken canary healthy; latest sample >206k events, 0 gaps.
- Kraken broad EUR universe healthy at **501/501 / 100% coverage**.
- V2R4 WS-shadow/outcome/cloud-sync and Altrady transport are healthy; runtime supervisor self-heal is active.
- Current MINI-PC Git head is behind cloud `main` only by documentation and paper-evidence/state commits; no newer runtime-code change is required locally at this audit point.
- Defender/firewall/app/reboot review is closed per MINI-PC runbook. Broad RDP Any/Any remains documented as optional hardening; external administration remains VPN-first and no direct WAN RDP port-forward is part of the approved architecture.

## GitHub / orchestration

- Current scanner, paper runtime, archive sync, timing sync, process health and MINI-PC cloud-watch runs are succeeding.
- The recent final-audit-guard failures were confined to intermediate commits while the audit script was being corrected; final fixed guard/smoke are green.
- Scanner declaration remains every 10 minutes, but recent observed GitHub scheduled-run start gaps ranged about **9.35–22.13 min**. This is real hosted-scheduler jitter, not a scanner rule change.
- Paper-runtime concurrency is serialized and state push/rebase retries are active.
- Stateful evidence commits continue to move `main`; this causes large draft-PR drift. PR #9 is currently **29 commits ahead / 651 behind** `main`, by design not rebased continuously. Final sync remains a release-boundary task.

## V2R3 clean paper series — current snapshot

Series: `PAPER-V2R3-CLEAN-20261001T0925Z`

- Candidate-Outcomes: **298**
- Final state: **290 REJECT / 8 WAIT / 0 BUY_SCOUT**
- Completed trades: **0**
- Integrity: **HEALTHY**
- Duplicate candidate IDs: **0**
- Duplicated queue IDs: **0**
- Missing mandatory timing/ticker/fingerprint provenance: **0**
- Distinct strategy fingerprints: **1**
- Distinct runtime-code fingerprints: **1**
- Revalidated candidates: **271**
- Completion state: **COLLECTING_AGE**
- Current age remaining to the 7-day alternate gate: about **139.3 h**
- 24h eligible/complete at latest snapshot: **43 / 39**. The four incomplete rows had only just crossed 24h and are current follow-up lag, not a stale-series fault.

Runtime timing for the clean series:
- REJECT p50 total ~**35.5 s**, p90 ~**59.5 s**, no >300 s cases.
- WAIT p50 total ~**42.6 s**, p90 ~**79.0 s**, no >120 s cases.
- The old persistence-driven multi-minute severe tail is absent in the clean series.

WAIT revalidation remains a weakness of V2R3:
- p50 TTL lag ~**259 s**
- p90 TTL lag ~**818 s**
- max observed ~**1401 s**
- This is operational timing evidence only; do not alter the active clean series. V2R4's local event-near WAIT watcher is the prepared architecture response.

## Strategy findings — do not change V2R3 mid-series

### 1. Very conservative terminal behavior

The clean series currently has **0 BUY_SCOUT** across 290 terminal REJECTs (plus 8 current WAITs).

Among the first **39 mature 24h REJECTs**:
- 29 / 39 reached at least +2% MFE (~74%)
- 18 / 39 reached at least +5% MFE (~46%)
- 8 / 39 reached at least +10% MFE (~21%)
- median 24h MFE ~**+4.19%**
- median 24h close ~**+2.24%**

This is an important strategy signal, not proof that all of those moves were safely tradable after fees/spread/slippage. The clean-series gate remains immature, so no threshold/entry/stop change is allowed yet.

### 2. Legacy static blocked-pair rule is still active in V2R3

`paper_evaluator/evaluate.py` still hard-blocks DUSK/EUR, QNT/EUR and TION/EUR. In the clean series, **6 QNT/EUR candidates** have already been forced to `REJECT / PAIR_BLOCKED`.

This is intentionally preserved for V2R3 methodological consistency, but it conflicts with the newer project-wide policy that live public Kraken `AssetPairs` online Spot-EUR status is the tradability truth. V2R4 already removes this legacy static-blocklist behavior.

### 3. Account-private tradability is a model-context confounder

The V2R3 spec says `account_private_tradability_required=false`, but the context still includes `account_specific_tradability.available=false`. The model has emitted `account_tradability_unavailable` in **31 / 298** initial clean-series reason sets (~10.4%) and in 21 revalidations.

This is not a data-integrity failure, but it can bias the evaluator despite public Kraken pair metadata being available. V2R4's policy explicitly prevents missing private-account evidence from becoming negative evidence when the public pair is online.

### 4. Actual hosted scanner cadence is slower/noisier than declarative 10-minute cadence

The scanner's cron contract is unchanged, but observed hosted start intervals are materially jittery. That limits V2R3's ability to test truly early detection and is one reason V2R4's MINI-PC realtime path exists.

## Freeze / methodology guard improvement made during this audit

A real methodological guard gap was found: the clean-series freeze validator pinned evaluator code, strategy spec and scanner rules, but did not protect behaviorally relevant semantics in `.github/workflows/paper-evaluator.yml` itself.

The freeze guard now also verifies:
- serialized paper-runtime concurrency;
- non-cancelling execution;
- evaluator model = `gpt-6-luna`;
- prospective candidate max age = 60 min;
- batch cap = 8;
- WAIT revalidation lifecycle invocation;
- position lifecycle invocation;
- follow-up lifecycle invocation.

The guard workflow now triggers when `paper-evaluator.yml` changes. **Post-fix freeze-guard CI: SUCCESS.**

No active strategy rule, model prompt, entry, stop, sizing, scanner threshold or cadence was changed by this safeguard.

## V2R4 control state

- Draft PR #9 remains **draft / not active**.
- Latest PR-head validation: **SUCCESS**.
- V2R4 shadow: >1,300 prospective events, due-6h coverage ~99.6%.
- MINI-PC health: **HEALTHY / OK**.
- `automatic_activation_allowed=false`.
- Activation review state: **BLOCKED_V2R3_COMPLETION**.
- Sizing remains unresolved at release boundary; do not silently combine timing and sizing changes.

## Audit conclusion

The current architecture is functioning end-to-end and the evidence/data-safety controls are working. There is no present critical infrastructure fault and no evidence of strategy/runtime fingerprint drift in the active clean series.

The important remaining issues are **strategy/research issues rather than broken infrastructure**:
1. zero BUYs and substantial missed upside among early mature REJECTs;
2. V2R3 WAIT revalidation lag;
3. hosted scanner schedule jitter;
4. legacy static blocked-pair behavior;
5. account-private tradability confounding;
6. V2R4 branch/state-commit drift to be reconciled only at release review.

The correct current action is to let V2R3 clean evidence continue unchanged, keep V2R4 shadow/realtime evidence collecting, and defer any strategy modification or V2R4 paper activation until the documented completion/release gate.
