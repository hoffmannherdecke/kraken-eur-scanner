# V3 successor: coin-specific entry evidence v1 — inactive (2026-10-09)

## Verified root cause

Active `tools/v2r4-paper-local-runtime.py` builds a scanner handoff with percent returns, price, spread and turnover. Active `paper_context.build_context()` enriches with fresh Kraken ticker, AssetPairs, a **BTC/ETH/SOL** OHLC market proxy, derivatives and official headline context. **It does not supply candidate-specific closed 1m/5m/15m OHLC, volume ratios or ATR/structural stop features**. Yet `paper_evaluator/evaluate.py` requires confirmation and a defensible ATR/structural stop for BUY_SCOUT. This is a verified feature-provenance gap, not proof that rejected trades were profitable.

## Frozen prospective V2R4 evidence

As of 2026-10-09 ~17:15 UTC, Supabase had 1,163 decisions across two technically rotated V2R4 series with the same strategy fingerprint: 403 initial REJECT, 760 initial WAIT, zero initial BUY_SCOUT, zero V2R4 paper trades; 738 WAIT had ended REJECT. 768 valid 6h follow-ups contained 186 observations with MFE >=5%; 155 of those had initial spread <=0.5%, representing 31 different pairs. Observations overlap by asset and hour. MFE is NOT an executable profit, and ex-post OHLC must never be imported as known-at entry evidence. Actual liquidity/depth, stop feasibility, MAE, fees 0.60% each way, spread, slippage and pair/6h episode clustering remain required.

Technical series cutover at 2026-10-09 11:01 UTC does NOT restart the strategy observation age from the original 2026-10-07 18:42 UTC.

## Implemented research adapter (not attached)

`paper_evaluator/successor_coin_entry_evidence_v1.py` exposes an offline-pure entry feature builder plus an *optional manually invoked* Kraken public OHLC collector (exactly 1/5/15m reads). Data: most recent fully **closed** candle close/high/low, last volume vs prior five contiguous closed candles, 15m ATR(14) and last-eight-closed-bars low when derivable. Every output distinguishes `observed_at_utc` and `known_at_utc`; never treated as known before the latter. Last mutable bar discarded; gaps, stale data, zero denominator, invalid data and source failure yield explicit missing/incomplete indicators, not a bearish veto. No raw archive, database change, model request, trade authority, order or schedule.

Deterministic local tests (7): `python -m unittest tests.test_successor_coin_entry_evidence_v1 -v` — verified PASS in isolated local environment.

## V3 canonical inheritance and duplicate-prevention (2026-10-09)

This work is now **strategically routed into V3 research governance**, not wired into any current V3 decision runtime: `research/v3-migration-ledger.json` component `coin_specific_entry_evidence_provenance` and machine-checkable `research/v3/coin-entry-evidence-lineage-v1.json`; ownership details `docs/v3-research-framework.md`.

**Reuse before rebuilding:** Historical H6 already computes 15m Kraken-EUR price and normalized volume features. The new adapter has a distinct narrow purpose: point-in-time compact 1m/5m/15m candidate-specific *closed* OHLC availability, descriptive volume/ATR/swing-low provenance. It is neither a second independent H6 prediction nor proof of H6's incremental alpha. Do not multiply same-bar information into two separate confirmation votes or mix different H6-vs-entry volume-ratio definitions. H6's review remains on its existing sequence after H3.

**Independent neighboring responsibilities:** H3=order-book/depth/imbalance; H4=stop/trailing/TTL parameter changes (new ATR/low may be input only); H7=future trained TAKE/NO-TAKE (no automatic promotion); H1 standalone decision authority rejected; V2R4 WAIT/trigger and fee/anti-chase unchanged. One strategy-changing shadow at a time.

**Runtime and storage:** Registered Kraken public Spot-EUR OHLC source and already existing market-data infrastructure should be reused whenever feasible, not replaced by a duplicate live collector; no new scheduled task, model inference, endless raw-bar retention, additional GitHub/Work cadence, real-money path or unreviewed Mini-PC deployment.

**Important existing state discrepancy:** Live Supabase showed the 2026-10-09 technical V2R4 rotation to `PAPER-V2R4-20261009T110135Z`, whereas some static state/version documents still reference the former `PAPER-V2R4-20261007T184255Z`. Do not silently rebind frozen H3 cohorts; separately reconcile the declared control-plane metadata with the authorized technical rotation before materializing any new strategy-changing candidate. The unchanged V2R4 strategy fingerprint connects the two series for *descriptive productivity research* only.

## Existing next gate / decision rule

1. At the existing V2R4 24h/72h/productivity review, use a small fixed, time-clustered positive and negative control cohort. Inspect each originally available decision input. Distinguish feature-delivery omission, legitimate risk veto, premature/late detection, WAIT expiry and data uncertainty. Do not claim the module fixes low BUY conversion before this validation.
2. Freeze **one** inactive successor hypothesis using these point-in-time features and otherwise unchanged fees, stop, timing and risk controls. Compare same-snapshot baseline vs successor prospectively. Count BUY/WAIT/REJECT, net-cost trade feasibility, false positives, false REJECT, true rejections and missed second legs.
3. An independent Mini-PC **small smoke**, source cost/budget gate, consistent sample, rollback and existing separate user/release approval are mandatory before changing live PAPER. No changes to active V2R4, H3, scanner, runner, Work, Supabase, secrets or real-money paths.

Status: **INACTIVE_IMPLEMENTED_NOT_VALIDATED_IN_REAL_RUNTIME**. Research/test contract only. No autonomous deployment.

## E2E delivery gap and bounded public-data probe — 2026-10-09

A second code inspection confirmed **existing** `paper_evaluator/v2r4_wait_watcher.py:market_metrics` already fetches the candidate coin's fully closed Kraken 1m/5m/15m OHLC values and volume ratios, but only to evaluate deterministic WAIT trigger thresholds. When the trigger matches, `v2r4_wait_runtime.py:run_cycle` persists a trigger receipt containing those metrics. **`v2r4_local_recheck.py:run_recheck` then rebuilds `paper_context.build_context` from scratch; it carries the receipt to the LLM in `v2r4_fresh_recheck_context` but does not promote validated per-coin OHLC/volume/ATR into the standard `external` decision context.** The initial `evaluate.py:main` path also does not supply those coin-specific features. Importantly, the receipt is embedded in a candidate field on recheck, so **not all** OHLC details are entirely absent from the LLM prompt; what is missing is an authoritative candidate-specific structured evidence interface with explicit closure, freshness, ATR and provenance semantics.

Minimal prepared, **inactive** proof implementation: `paper_evaluator/v3_entry_handoff_probe.py`, which accepts either a real canonical existing V2R4 candidate path or a public pair sensor-only sample, fetches only one public Kraken 1m/5m/15m snapshot plus one ticker, checks bar closure, volume, ATR and known-at versus decision time, and attaches the resulting canonical `candidate_entry_evidence` once to a copied context. No duplicate H6 independent signal, no recheck-trigger change or model vote, no raw archive/persistence/order. `tests/test_v2r4_v3_entry_handoff_probe.py` proves in one offline stubbed `evaluate.call_evaluator` that all those fields *actually appear in the existing evaluator input*, and explicitly tests missingness, future data, pair mismatch and duplication; a canned BUY normalization check is **NOT** a real AI decision, paper trade or approval proof.

Existing V2R4 PR-validation workflow now runs **one** bounded live Kraken public source/handoff smoke on `XBT/EUR` and the offline tests, with no API key, actual LLM call, paper order, private account, Mini-PC change, production schedule, or additional workflow. Live smoke only establishes publicly obtainable real OHLC + safely constructed future evaluator input; it does not assert a genuine historical candidate, AI BUY conversion, risk-adjusted positive expectancy or a correct future stop.

For a real production-cohort proof the next physical/connected execution gate still requires one existing canonical Mini-PC handoff, full standard market context, real isolated AI evaluator with fee/stop validation, and same-candidate frozen V2R4 baseline comparison. The decision-clock must be prospective: a current live Kraken OHLC recheck cannot be retroactively injected into 2026-10-07/09 historical V2R4 inputs. Existing H3 one-change Shadow must not be silently rebound or bypassed. The last-confirmed technical runtime series is recorded as a **dated snapshot** in `project-current-state.json`, while the original 2026-10-07 series remains the frozen H3 lineage anchor; real-time Supabase/Mini-PC takes precedence.


## Prepared next physical gate: exactly one fresh candidate / two real model decisions

`paper_evaluator/v3_one_shot_model_compare.py` and the PLAN_ONLY-by-default `tools/run-minipc-v3-entry-model-compare.ps1` form a **manual research-only probe** for the already-running Mini-PC. They are neither installed into `Runtime/v2r4-paper-app` nor scheduled.

The PowerShell runner uses `%USERPROFILE%\\Trading\\Repos\\kraken-eur-scanner`, verifies the existing runtime app/venv/key file, fetches the current GitHub `main` into a **new disposable detached worktree under TEMP** without pulling/changing the active local repo or installed Paper runtime, runs the Python module once and removes its own worktree. It never writes to Supabase, active candidate/decision/recheck directories, Paper results, Windows tasks or Git runtime evidence.

The Python probe selects **one already-generated, still-fresh (<=15m), canonical V2R4 handoff** under the existing runtime app; rejects older/future/foreign-series cases and source-code drift between active frozen evaluator/context and its isolated checkout. It builds **one** fresh Kraken execution ticker + usual public base market context; collects **one** validated candidate-specific 1m/5m/15m closed OHLC/volume/ATR snapshot; then requests exactly **two** actual paper-only model decisions with the **same candidate, ticker, existing V2R4 spec and base context** (without vs with the one new canonical entry-evidence input). The existing `evaluate.call_evaluator`, `fail_safe_normalize` and public Kraken tradability gate are used; **no** paper entry simulator, stage2 watcher, account/private trade endpoints or original `evaluate.py:main` output path are invoked. The model may internally retry failed calls once per branch; no loop/candidate sweep.

**Interpretation:** Single same-input decision-sensitivity experiment only, NOT an official original historical baseline replay, NOT a V3 paper trade, NOT a validated net expectancy, and never a basis for automatic activation. If input is missing, source is stale, version differs, API key is unavailable or no recent candidate exists, fail closed with a compact failure code; do not fabricate a comparison or retrospectively attach today's bars to yesterday's decisions. A real model BUY suggestion in this dry-run does not satisfy the permanent release requirement of prospective **filled Paper** entry and followups.

When physical access is available, launch the reviewed plan/safe execution wrapper once and retain the compact stdout report, with private API key never displayed. Subsequent broader controlled trials remain behind H3 fixed review, frozen single-change/prospective net-cost cohort and explicit separate Paper release gate. Physical step has not yet been performed as of this preparation.

## Physical series verification after 20:29 CEST operator screenshot (2026-10-09)

PowerShell read-only evidence confirmed actual technical successor `Runtime/v2r4-paper-stage-d8b35a8ec2e6`, `PAPER-V2R4-20261009T110135Z`, 164 local candidate handoffs, newest file observed 2026-10-09 20:28:47 local, all four V2R4 paper scheduled tasks in `Running` and all four candidate/cloud-sync/lifecycle/WAIT heartbeats `HEALTHY` at ~18:29 UTC. The previously inspected frozen predecessor `Runtime/v2r4-paper-app` contained 1,011 historical candidates and is not the active writer; its last file at 13:00 local was expected after technical cutover, **not evidence of stopped production**.

`paper_evaluator/v3_one_shot_model_compare.py` and its launcher now require an explicit pinned `PAPER-V2R4-20261009T110135Z` and discover exactly one valid `v2r4-paper-stage-<release-sha-prefix>` control with matching release SHA, `paper_only=true`, `enabled=true`, `real_money_actions_enabled=false`. They never fall back to `v2r4-paper-app`, silently change H3 frozen lineage or assume the file modification time equals the candidate's event clock. Before any model call a fresh canonical candidate `event_time_utc` and closed-bar timestamps must pass; a subsequent technical rollover blocks this pinned one-shot and requires another explicit review. Tests include frozen-app exclusion, stale/foreign series, mismatched release SHA and ambiguous simultaneous stage controls.

## First genuine Mini-PC model-pair run — 2026-10-09 18:37 UTC

Operator's PowerShell screenshot confirms **one** bounded one-candidate real OpenAI inference pair, using the reviewed `paper_evaluator/v3_one_shot_model_compare.py` wrapper from PR #119, with live technical-series selector safety added in PR #120. All model calls returned and the wrapper reported `FINISHED_PAPER_UNCHANGED`.

- Source: **real canonical STRK/EUR** handoff, candidate `20261009-182844-STRK-EUR-r69055421619246`; event 18:28:44 UTC; same snapshot measured 18:37:04 UTC, still within the established 15-minute candidate-age bound.
- Series: `PAPER-V2R4-20261009T110135Z`, runtime `v2r4-paper-stage-d8b35a8ec2e6`; **not** the old 7 October frozen app. Existing on-device evaluator/context fingerprints matched reviewed GitHub main for this probe.
- **Baseline model response:** `WAIT`, setup `EXTENDED`; reason codes included `NO_SPOT_VOLUME_OR_ATR_DATA`, `12H_ADVANCE_EXTENDED`, `30M_PULLBACK`, `MAJOR_MARKET_MIXED_TO_WEAK`, `REMAINING_MOVE_UNVERIFIED`.
- **With one per-coin canonical closed OHLC/volume/ATR feature object:** `WAIT`, setup `REVERSAL`; reason codes included `LOW_5M_VOLUME`, `PRICE_BELOW_RECENT_STRUCTURE`, `MAJOR_MARKET_MIXED`, `NO_CONFIRMED_REVERSAL`.
- Both `valid_stop_below_ask=false`, `valid_stage2_above_ask=false`, `risk_reward_after_costs=null`, no simulated paper fill. Output marked `model_calls=2`, `candidate_specific_features_ready=true`, `valid_paper_trade_proven=false`, `economic_edge_proven=false`, `active_v2r4_changed=false`, `active_h3_changed=false`, `real_orders=0`.

**Finding:** Candidate-specific data can be delivered end-to-end into **real model evaluation**; the model's reasons changed from an evidence-missing objection to concrete observed volume/structure caution. Crucially **both results remain WAIT**, so there is **no BUY conversion evidence and no claimed trading-performance improvement**. Two individual model outputs are also susceptible to inference variance; do not over-attribute reason changes to data without paired replicated or deterministic control evidence. Costs/stops/unknown path remain unresolved.

**Explicit status progression (research only):** `REAL_INPUT_AND_MODEL_PAIR_PROVEN`, **not** `SUCCESSOR_RELEASE_READY`, **not** `VALID_PAPER_BUY_PROVEN`. The permanent five-gate successor learning contract remains unmet. Next efficient check is one read-only aggregation of the actual 9 October active-series initial `paper_decisions` and recheck `paper_rechecks` by `reason_codes`, WAIT expiry, BUY rate and pair/time clusters. Prioritize this measured bottleneck over new indicators, repeating ad hoc model calls, expanding storage or extending a barren Paper version without a decision.


## Entire active V2R4 first-decision cohort: operator screenshot, 2026-10-09 ~20:40 CEST

Operator read-only on-device sample (active `PAPER-V2R4-20261009T110135Z`, `v2r4-paper-stage-d8b35a8ec2e6`) showed **168 initial decisions: 116 WAIT / 52 REJECT / 0 BUY_SCOUT**. The same local sample had **123 recheck EVENT FILES: 110 REJECT / 13 WAIT / 0 BUY_SCOUT**. The 123 records are events, *not necessarily 123 distinct WAIT candidates or terminal outcomes*; any repetition/ordering must be deduplicated by `candidate_id` before calculating conversion. These numbers may grow as the series runs.

Top codes across all 168 original decisions, irrespective of outcome: `SPREAD_ACCEPTABLE` 48, `PAIR_ONLINE` 46, `REMAINING_MOVE_UNVERIFIED` 17, `PAIR_ONLINE_MINIMUMS_PASS` 13, `EXTENDED_MOVE` 12, `EXTENDED_12H_MOVE` 10, `REMAINING_MOVE_UNCONFIRMED` 10, `INSUFFICIENT_REMAINING_MOVE_EVIDENCE` 10, `SHORT_TERM_MOMENTUM_WEAK` 9, `VOLUME_CONFIRMATION_MISSING` 9, `spread_too_wide` 9, `SHORT_TERM_MOMENTUM_NEGATIVE` 8, `12H_MOVE_EXTENDED` 7, `COSTS_MATERIAL` 7, `MAJOR_MARKETS_WEAK` 6. **Positive statements `SPREAD_ACCEPTABLE`, `PAIR_ONLINE`, `PAIR_ONLINE_MINIMUMS_PASS` are NOT rejection reasons.** A model may output several correlated codes for one candidate, so code counts are not distinct cases and `REMAINING_MOVE_UNVERIFIED` alone is not a proven causal veto.

Next **single source-of-truth on-device cohort diagnostic**, prepared with no model/remote queries, writes or running-series mutation: `tools/v2r4-readonly-decision-funnel.py`. It reads only current technical-stage `paper_decisions` and `paper_rechecks`, enforces exact series/PAPER control, deduplicates candidate identity and each candidate's *latest* recheck, separates `V2R4_WAIT_EXPIRY_V1` from real `V2R4_LOCAL_TRIGGER_RECHECK_V1`, reports latest WAIT final states, overdue missing rechecks, outcome-specific top evidence codes, currently absent canonical per-coin structured evidence and repeated pair/6h episodes. This will distinguish WAIT TTL/no trigger versus fresh model/risk veto versus source/data limitation. No claims about counterfactual profitability, pair/time independence or strategy improvement before a prospective risk/cost follow-up; do not loosen buying criteria on aggregate reason-code frequency alone.


## ROOT-CAUSE funnel cross-check: original V2R4 → WAIT → real model recheck, 2026-10-09 18:44 UTC

**Direct cloud versus Mini-PC event reconciliation:** For frozen research sampling of `PAPER-V2R4-20261009T110135Z`, Supabase held 168 unique initial decisions (`116 WAIT, 52 REJECT, 0 BUY_SCOUT`). Original `paper_decisions` contained **no canonical structured candidate-specific closed OHLC/volume/15m ATR risk provenance in any of 168 evaluator contexts**. Each `WAIT` had deterministic `ALL` condition logic, 109 two-condition plans and 7 three-condition plans. **110 of 116** explicitly demanded both a fully closed 5m price and a fully closed 5m relative-volume threshold. The common 5m volume-ratio threshold was `1.2`; expired plans' price targets were a median **0.784% above original decision-time last**, triggered plans' median **0.577%**, mean TTL roughly **32 minutes**. Price/volume cross-condition availability is observed; what prevented each plan from matching is **not** separately recorded per polling cycle (nonmatch/missing metric telemetry not retained). A generic cloud status `HEALTHY` doesn't prove condition feasibility.

**Distinct outcome funnel as of query:**

| Cohort state (by unique candidate) | Cases |
|---|---:|
| Initial WAIT | 116 |
| Latest outcome `V2R4_WAIT_EXPIRY_V1` (no complete trigger → **no new model decision**) | 93 |
| Latest outcome `V2R4_LOCAL_TRIGGER_RECHECK_V1` | 22 |
| Still without a terminal/current recheck record | 1 |
| Among 22 real triggered rechecks, final `REJECT` | 19 |
| Among 22 real triggered rechecks, final `WAIT` | 3 |
| BUY_SCOUT | **0** |

Separate local file snapshot showed 124 *recheck EVENTS* (91 `WAIT_EXPIRY` + 33 `LOCAL_TRIGGER_RECHECK`) but only 113 distinct recheck candidate identities. This is **not a contradiction**: the local folder includes chained/superseded events while Supabase `paper_candidate_outcomes.payload.recheck` holds the latest synced per-candidate outcome and may advance between snapshots. Do NOT report 110 local `REJECT` events as 110 failed model evaluations.

**Reasons after actual triggers**: For 19 latest model `REJECT` outcomes, non-exclusive raw code-family flags included structural stop/stage2 plan 15, late chase/extension 18, cost/remaining potential 19, market/momentum 14. One case can hit several; reason-code labels are **not** individual causal proofs. The unchanged evaluator may still have valid risk-based reasons to abstain even after complete per-coin data is supplied.

**Quality countercheck rather than mechanically loosening gates:** Among independently *complete* post-original-decision 60m follow-ups, later price MFE >=3% was observed in **8/89** of expired-WAIT cases versus **8/19** of actual-triggered cases (>=5%: **1/89** vs **4/19**). Episodes overlap by pair/time; follow-up horizons are measured from initial candidate, may include movement before a model could react; observed MFE is retrospective and **not directly tradeable positive after 0.60%/side taker fees + spread/slippage or stop/MAE**. This is at least consistent with the existing ALL trigger providing useful quality selection. Removing or relaxing it simply to raise BUY counts is **not supported** by these data.

**Strategic design/gate**, exact owner `research/strategy-learning-causal-gate-v1.json.incident.latest_diagnostic_snapshot`:
1. Keep V2R4, its H3-frozen lineage, H6 volume ownership and fee/stop/50+50 gates unchanged. No runtime change, extra scheduled job, new Work run or hidden auto-trade.
2. First prospective one-change **candidate-specific entry data delivery** (fully closed 1m/5m/15m, volume and ATR/local low, point-in-time freshness); otherwise identical reference strategy and original WAIT filters. Prove at least one genuine viable BUY and net-fee/MAE path, measure missed quality opportunities, compare using the *same fresh candidate and decision clock* and clustered pair/time cohort. Previous STRK two-model `WAIT` input test proves interface, not economic gain.
3. Only **if** post-data evaluation still blocks justified opportunities, study WAIT conditions in a **separate** H4/TTL controlled research hypothesis with measured real-trigger, missing-metric, no-trigger, and post-trigger conversion. Never combine a WAIT relaxation and new per-coin inputs in one supposed single-change test. Do not invent unlogged past trigger metrics.
4. Respect fixed H3 one-strategy-changing-shadow gate and existing strategy-72h productivity review anchored to the original 2026-10-07 18:42 UTC first epoch, not the Oct-09 technical rotation. No paper/live promotion without separately verified evidence and user decision.

**Bottom line:** Technical pipeline healthy, meaningful no-buy productivity failure persistent. Most WAITs end without a real second model evaluation; when a trigger occurs, evidence/edge/stop guardrails still cause no BUY. The added data interface is required for sufficiency but *not proven sufficient* for fixing this decision funnel.

