# Test Strategy & Execution Runbook

Status: **CANONICAL TEST TRIAGE / EXECUTION RULES**  
Scope: project `Aktien & Krypto Chancen`  
Master to-do authority: `PROJECT_BACKLOG.md`

## Purpose

This runbook prevents two opposite failure modes:

1. skipping tests that protect evidence quality, runtime safety or release integrity;
2. endlessly adding low-value tests that delay the project without changing a real decision.

It is **not** a second backlog. Open/blocked work remains only in
`PROJECT_BACKLOG.md`. This document defines which kinds of tests are worth doing,
when they are required, who should execute them and when a previous PASS may be reused.

## 1. Test-value gate — every new test must justify itself

A proposed test is executed only if it answers at least one concrete question:

- **Evidence validity:** can the data / label / known-at / PIT semantics be trusted?
- **Strategy decision:** can this result change whether a component is kept, rejected or promoted?
- **Runtime safety:** can a realistic failure produce stale, duplicate, missing or corrupted decisions?
- **Execution safety:** can a later order path cause unintended size, duplicate orders, stale fills, unreconciled state or unrecoverable behavior?
- **Release integrity:** can the exact code/config/artifact being promoted be reproduced, rolled back and distinguished from prior versions?

A test should normally be rejected or deferred when it merely:
- repeats an already-proven property with no changed code/config/environment;
- measures a metric that cannot change a current or later decision;
- adds a second source that provides no unique information;
- increases sample count without a preregistered sample/reliability gate;
- explores extra thresholds/variants only because earlier results were weak;
- requires substantial user time while the same question can be answered in CI, public APIs, Supabase or existing evidence.

## 2. Autonomy-first execution rule

Default executor is ChatGPT through existing GitHub/Supabase/public read-only tooling.

### A — fully autonomous
ChatGPT should execute without asking the user:
- repository/static validation;
- unit/self-tests;
- GitHub Actions CI;
- public REST/WS/API response-shape and bounded source smokes;
- Supabase read-only evidence/readiness checks;
- point-in-time/known-at validation using already available data;
- report parsing and effect-size reviews from supplied/persisted artifacts;
- backlog/documentation/reconciliation updates;
- issue/release evidence updates;
- bounded reruns after a technical fix.

### B — user only when physically unavoidable
Ask the user only when the proof depends on:
- the physical MINI-PC/Windows environment or home network;
- BIOS/power-loss/device/storage hardware;
- an account UI/login/secret that ChatGPT cannot access;
- a real externally transported event that cannot be generated safely in cloud CI;
- an account-specific private Kraken state/fee tier;
- a deliberately human release/live-activation decision.

User actions should be **batched** into the smallest safe command/run possible.
Before asking for a long physical run, first perform the shortest cloud/static smoke
that can catch implementation errors.

## 3. No-repeat rule

A previous PASS remains valid unless at least one of these is true:

- relevant code or configuration changed;
- data/source schema or API semantics changed;
- hardware/OS/network/runtime environment materially changed;
- the test has an explicit freshness/expiry requirement;
- an incident contradicts the prior evidence;
- the later gate requires a different scope (for example cloud PASS -> physical MINI-PC PASS).

Therefore:
- do **not** repeat reboot, internet-loss, recovery, backup, WS transport or source-shape
  tests just to “be extra sure” when their relevant system has not changed;
- after a bug fix, rerun the **smallest regression test that covers the bug**, then the
  next required real environment gate;
- a technical failure is never counted as strategy evidence.

## 4. Smoke-before-duration rule

Order of work:

1. static/contract guard;
2. deterministic self-test;
3. shortest bounded real-source/cloud smoke;
4. shortest required physical smoke, only if environment-specific;
5. long prospective collection / shadow run;
6. effect-size/performance review only after the preregistered collection gate.

A failed step blocks only its dependent branch. Work should continue on independent
open items rather than waiting.

## 5. Required test families by project phase

### Phase A — before the first serious V3 shadow candidate

Required only for components that may enter the candidate:

- exact input/provenance and PIT/known-at semantics;
- frozen hypothesis/trial contract and search accounting;
- component-specific minimum data/sample gate;
- no-threshold/no-midrun-tuning guard where applicable;
- exact report/effect-size review;
- one-change candidate contract;
- same candidate stream / same market clock comparison;
- candidate materialization self-test + smallest E2E shadow smoke;
- frozen baseline/config/code fingerprints.

Current practical implication:
- finish the already-running H3 collection gate;
- import/review exact H1/H6 reports;
- do **not** force H2/H4/H7/H8/H9/H10/H11 to completion merely to start a first
  V3 shadow candidate unless one of those components is actually selected for it.

### Phase B — before V3 component promotion

Required:
- enough prospective/OOS evidence under the frozen contract;
- realistic cost treatment where the component affects entries/exits;
- no unresolved PIT/data leakage issue;
- no technical-invalid sessions mixed into strategy evidence;
- migration-ledger classification;
- explicit promotion gate and rollback target.

Not automatically required:
- every research hypothesis in the project;
- every possible sensor/source;
- every parameter variant.

### Phase C — before paper release / runtime activation

Required:
- exact release/config freeze;
- CI/static guards;
- smallest real E2E paper smoke;
- persistence/restart/reconciliation appropriate to the changed component;
- stale/duplicate fail-closed behavior where the changed path can affect decisions;
- rollback proof/reference.

Do not repeat unrelated infrastructure tests if the changed release cannot affect them.

### Phase D — before any later live/private execution

Required separately and much later:
- account-specific current Kraken fee tier/state verification;
- least-privilege private API permissions, no withdrawal rights;
- startup account reconciliation;
- stale-data rejection;
- duplicate-order / position / size / price-deviation gates;
- order lifecycle + fill/cancel race handling;
- deadline/cleanup-taker contract;
- explicit, testable queue/fill assumption before maker modelling;
- persistent kill switch;
- circuit breaker;
- restart / network-loss / recovery proof for the **actual execution path**;
- controlled E2E execution smoke before broader activation.

These are not blockers for present V3 research/shadow work.

## 6. Deferred/data-maturity tests

Some tests are valuable but cannot be made meaningful by spending more time today.

Examples:
- H4 stop/TTL regime work waits for mature MAE/MFE / trade evidence;
- H7 meta TAKE/NO-TAKE waits for frozen labels and enough clean outcomes;
- H8 on-chain association waits for additional prospective known-at depth;
- H9 fill-probability work waits for the execution-stage data/assumptions;
- H10 smart-money quality needs a frozen unbiased public-address selection rule and
  a meaningful prospective observation window;
- H11 prediction-market predictive value needs longer-horizon prospective capture
  and an event-relevance contract.

These should remain open/deferred in `PROJECT_BACKLOG.md`, not be accelerated by
arbitrary extra smokes.

## 7. Physical/user test budget

Before requesting user involvement, ChatGPT must answer:

1. Why can this not be proven autonomously?
2. What exact gate will the result close?
3. What is the shortest safe run?
4. Can multiple physical checks be combined?
5. What output/evidence must the user return?

Long physical tests should not be repeated after technical failures until a short
regression smoke has passed. H3 ASSOC-001 -> ASSOC-002 is the canonical example.

## 8. Evidence retention

For every meaningful test:
- store compact canonical evidence or a reference/hash to the local report;
- record PASS/FAIL/INVALID_TECHNICAL explicitly;
- never convert technical FAIL into strategy FAIL;
- keep immutable trial/search-accounting history;
- avoid raw-data duplication where compact evidence is sufficient;
- update the relevant backlog item immediately.

## 9. Stop conditions

Stop expanding a branch when:
- the preregistered gate is met;
- the result is sufficient to make the intended decision;
- the source/component shows no incremental value under the frozen test;
- data maturity blocks further valid inference;
- a later project phase, not the current phase, is the proper place for the test.

Do not keep testing merely because another test is possible.

## 10. Current execution principle

For the present project stage the priority is:

**finish already-started high-value gates -> review exact evidence -> build the smallest
valid V3 shadow candidate -> collect prospective shadow evidence -> only then expand
additional research branches if they can materially improve the next decision.**

The project should prefer forward progress with bounded, decision-relevant evidence
over exhaustive completion of every research idea.

## 11. Fast-track strategy iteration — adopted 2026-10-03

Purpose: shorten calendar time to a decision without weakening evidence quality, safety,
or release integrity.

Binding rules:

- **Parallelize independent work.** While a frozen prospective series is collecting,
  successor implementation, inactive shadow preparation, component research and release
  plumbing may proceed in parallel, provided none of those changes mutate the active
  series or contaminate its evidence.
- **Do not serialize V2R4 and V3 unnecessarily.** After the V2R3 completion/release
  review, V2R4 paper evaluation and the smallest valid V3 shadow candidate may collect
  evidence concurrently because they answer different questions.
- **Use the smallest valid V3 candidate.** The first serious V3 shadow candidate does
  not wait for every H-component. Only components actually selected for that candidate
  must have their own required gate closed.
- **24h sanity gate:** verify mechanics, persistence, duplicate/stale behavior and obvious
  decision-path defects. This is not a performance-promotion gate.
- **72h early productivity gate:** review trade/candidate frequency, WAIT/REJECT structure,
  obvious pathological selectivity and technical validity. A clearly unproductive branch
  may be stopped early; no threshold is changed inside the running frozen version.
- **Evidence-diversity decision gate:** make the final continue/reject/promote/successor
  decision as soon as the preregistered sample, maturity, temporal-diversity and integrity
  gates are satisfied. Do not wait for day 7 merely because a week has not elapsed.
  Canonical policy: `docs/fasttrack-evidence-diversity-policy.md`.
- **No automatic long extension for low trade count.** If hundreds of valid candidate
  decisions again produce essentially no trades, low trade frequency is a strategy result,
  not a reason to keep the same version running indefinitely.
- **No mid-run tuning.** Any material strategy change creates a new version/series. Existing
  evidence remains attached to the old frozen version.
- **Reuse prior PASS evidence.** Infrastructure/source/recovery tests are not rerun merely
  because a strategy version changes when the tested path itself did not change.
- **Stop dead branches early.** Once a preregistered gate is sufficient to conclude that a
  component/branch lacks decision-relevant incremental value, stop expanding it and route
  effort to the next highest-value hypothesis.
- **Quality remains primary.** Fast-track means reducing idle/duplicate calendar time, not
  loosening cost, liquidity, stale-data, execution-safety or release-integrity controls.

Current calendar intent, subject to evidence maturity rather than date alone:

1. 2026-10-03 through V2R3 completion: keep V2R3 frozen while finalizing V2R4 readiness
   and preparing the smallest valid V3 shadow candidate in parallel.
2. At the V2R3 completion gate: perform the final evidence classification immediately;
   do not add an arbitrary extra waiting period.
3. After review: start the new homogeneous V2R4 paper series and the eligible V3 shadow
   candidate concurrently.
4. Apply the 24h / 72h early-review cadence, then decide at the earliest valid
   evidence-diversity gate rather than at a fixed day count.
5. Live/private execution remains a later, separate safety/release gate. During the later
   live phase, successor strategies use the same evidence-diversity fast-track for
   validation/promotion, but active live strategies never self-retune.

This section complements, and does not override, the smoke-before-duration, no-repeat,
freeze, holdout, and explicit release rules above.

## 11.1 Evidence-diversity timing rule — permanent from 2026-10-05

The fixed-duration interpretation of the former ~7-day gate is superseded by
`EVIDENCE_DIVERSITY_FASTTRACK_V1`.

Default for high-frequency candidate strategies:
- preregistered version-specific sample floor;
- observation span >= `max(48h, 2 × required follow-up horizon)`;
- >=3 distinct UTC observation dates;
- <=50% of qualifying observations from any single UTC date;
- <=60% of qualifying observations in any rolling 24h window;
- >=95% of the fixed qualifying cohort mature to the required follow-up horizon;
- >=95% complete follow-up coverage among mature qualifying observations;
- integrity/provenance gates healthy.

The earliest moment all required criteria are true is the review point. A longer fixed
duration is allowed only when a component-specific regime/maturity contract was
preregistered before results were inspected.

This rule applies to V2R4, V3 and every later strategy generation. It also applies to
successor validation after real-money trading begins. Execution safety, explicit live release,
kill-switch, reconciliation and other safety controls remain independent hard gates.

## 12. Mandatory analysis-to-action loop — adopted 2026-10-04

Every **substantive** targeted interim or final analysis is incomplete until its
decision-relevant consequences have been processed. The report itself is not the end
product.

After an analysis gate opens and real analysis is performed, execute this sequence
automatically within the existing autonomy/safety boundaries:

1. **Extract learnings.** Separate evidence-backed findings from speculation, outliers and
   unresolved confounders. Explicitly distinguish strategy/filter issues, timing/runtime
   issues, data/provenance issues, cost/execution issues and genuine no-change findings.
2. **Deduplicate against current design.** Check whether each learning is already covered
   by V2R4/V3, an existing hypothesis, research contract, backlog item or guardrail. If so,
   strengthen/link the existing item rather than creating duplicate machinery.
3. **Convert to consequences.** For each material learning choose the smallest appropriate
   downstream action:
   - update/create a versioned hypothesis/evidence/disposition artifact;
   - route the point to V2R4, V3 or the migration ledger;
   - update backlog/master status when materially changed;
   - prepare a bounded preregistered test/research contract or read-only analysis step when
     this is already within the approved project scope;
   - record explicitly that no action is warranted when evidence does not justify one.
4. **Execute safe follow-through immediately.** Documentation, deduplication, read-only
   checks, report linking, Ack-state updates, inactive research/test preparation and other
   reversible/documentable actions are performed without waiting for a separate user
   prompt when they are clearly inside the already approved scope.
5. **Preserve release boundaries.** Never turn an analysis result directly into a silent
   strategy/runtime/release change. No automatic threshold, entry, stop, sizing, scanner,
   frozen-series, V2R4 activation, V3 promotion or real-money/account/order change.
   Those remain subject to the existing version/freeze/release/user gates.
6. **Persist processing state.** Record which analysis/report was processed, what
   downstream artifacts/items were updated, and whether anything remains
   decision-gated. This prevents the same learning from consuming Work again.
7. **Notify only when useful.** Routine successful consequence-processing stays silent.
   Notify the user only for a material strategic conclusion, a meaningful closed gate,
   a required user/release decision, a manual MINI-PC action or a non-self-healable blocker.

A substantive analysis that merely writes a report but leaves obvious approved
consequence-processing for a later chat is therefore considered **incomplete**.

This rule applies equally to V2R3 intermediate/final reviews and later V2R4/V3
Work-level synthesis. It complements the fast-track rules and never weakens freeze,
holdout, no-midrun-tuning, cost, safety or release controls.

### 12.1 Gated-change escalation — mandatory user decision packet

If consequence-processing concludes that a currently gated change is **materially warranted**
(for example a strategy/threshold/entry/stop/sizing/scanner rule change, V2R4 activation,
V3 promotion, or another release-boundary change), the system must not merely leave it as
a passive note.

It must create a compact **DECISION REQUIRED** packet and notify the user at the next
meaningful analysis/gate completion. The packet must contain:

- **What should change** — exact component/rule/version.
- **Why now** — evidence and sample/gate that justify the change.
- **Expected benefit** — what problem the change is intended to solve.
- **Main risk / downside** — including overfitting, trade-frequency, cost or runtime risk.
- **Exact proposed implementation** — bounded diff/variant; no vague “optimize further”.
- **Validation plan** — which paper/shadow gate proves or rejects it.
- **Rollback** — explicit previous version / revert path.
- **Recommendation** — `APPROVE`, `REJECT`, or `MORE_TESTING` with a clear preferred choice.

The user notification must be action-oriented and clearly labeled **ENTSCHEIDUNG ERFORDERLICH**.
Routine findings that do not justify a gated change remain silent.

After user approval, execute the already-defined safe release/change workflow automatically
as far as possible, including versioning, tests, documentation, and rollback preparation.
Only stop again if a further genuine human/release gate is reached.

No gated change may be activated without the required explicit approval.

### 12.2 Mandatory V2R3 → V2R4 inheritance disposition

Every material V2R3 strategy learning produced by an interim or final analysis must receive
an explicit V2R4 inheritance disposition before V2R4 paper activation can be approved.
Allowed dispositions:

- `ALREADY_COVERED_V2R4` — the prepared V2R4 candidate already implements the intended behavior; link exact component/evidence.
- `PROPOSE_V2R4_CHANGE` — evidence supports a concrete change to the inactive V2R4 candidate; prepare the exact bounded diff and validation/rollback plan, then raise `ENTSCHEIDUNG ERFORDERLICH` before modifying strategy mechanics.
- `MORE_TESTING_BEFORE_V2R4` — potentially relevant but evidence is not mature enough; define the smallest required test/gate.
- `V3_ONLY` — structural/experimental change is deliberately not part of V2R4; route to V3 with rationale.
- `NO_V2R4_CHANGE` — evidence supports retaining current V2R4 behavior or no actionable change.
- `REJECTED` — hypothesis is contradicted or economically/operationally unjustified.

No material V2R3 finding may remain without one of these dispositions at the V2R3 final review.
The V2R4 release review must reconcile the complete disposition set against the exact
V2R4 behavior diff/spec. Any `PROPOSE_V2R4_CHANGE` without explicit user approval or any
unresolved material disposition blocks V2R4 activation.

After explicit approval of a proposed V2R4 change, implementation into the inactive V2R4
candidate, versioning, tests, documentation and rollback preparation should proceed
automatically as far as existing gates allow. Activation remains a separate explicit release gate.

### 12.3 Permanent strategy-lineage inheritance — all future versions

The inheritance rule is **not limited to V2R3 → V2R4 or V2/V2R4 → V3**.
It is a permanent project rule for every strategy generation and every successor version.

For each material finding from version `N`, the successor planning for `N+1` (or a deliberately
later generation) must assign one explicit lineage disposition before release:

- `INHERIT_UNCHANGED` — validated behavior remains part of the successor baseline.
- `INHERIT_MODIFIED` — validated learning is retained but implemented differently; exact diff and evidence required.
- `REPLACE_WITH_VALIDATED_SUCCESSOR` — old component is superseded by a tested alternative with stronger evidence.
- `DEFER_TO_LATER_GENERATION` — valid/interesting learning is intentionally not in the immediate successor; named future research/version destination required.
- `MORE_TESTING_REQUIRED` — evidence is insufficient for migration or rejection; smallest next gate required.
- `REJECT_WITH_EVIDENCE` — finding/hypothesis is contradicted or not economically/operationally justified.
- `NO_SUCCESSOR_CHANGE` — evidence supports keeping the successor design as-is.

Every new active strategy version must have a **lineage reconciliation** against the latest
relevant predecessor evidence and all unresolved inherited findings. A release is blocked if
a material predecessor finding has no disposition, or if an approved required change has not
been implemented/tested in the candidate.

When a new generation is created (for example V4 after V3), create or extend a migration ledger
for the predecessor→successor transition. Do not rely on chat memory or on an older generation's
ledger as the sole carrier of knowledge.

Validated improvements should therefore compound across generations: each successor starts from
the best-known validated baseline, not from a clean slate. A later version may still reject or
replace inherited logic, but only with explicit evidence and a recorded reason.

This permanent lineage rule does not authorize silent activation. Strategy mechanics still pass
through the gated-change decision packet, versioning, validation, rollback preparation and the
normal release gate.

### 12.4 Permanent live-learning loop — real-money strategies are not the endpoint

The automatic improvement process applies **without exception to the later real-money phase**.
Live trading creates additional high-value evidence and must feed the same strategy-lineage loop.

For every active real-money strategy/version, continuously retain and analyze at least:

- realized and unrealized outcome path after actual fees, spread and slippage;
- fill quality, partial fills, rejects, cancels, maker/taker behavior and execution latency;
- entry quality, stage-2 behavior, stop/exit/trailing behavior and re-entry outcomes;
- missed opportunities, false positives, false negatives and user/manual overrides;
- market regime, liquidity, volatility and event context known at decision time;
- scanner→decision→order→fill timing and stale-data/recovery incidents;
- infrastructure/execution failures separately from strategy failures;
- concentration, sizing, drawdown and portfolio interaction where applicable.

Every material live finding must enter the normal analysis-to-action and lineage process:
`live evidence → analysis → verified learning → consequence → successor disposition →
inactive candidate/test → validation → gated release`.

A live finding may strengthen, modify, replace, defer or reject a strategy component, but it
must not disappear merely because the strategy is already trading real money.

**No self-modifying live strategy:** live evidence must never silently retune thresholds, entries,
stops, sizing, scanner logic or model parameters inside the currently active real-money version.
Material strategy changes are built in an inactive successor/candidate, validated under the
appropriate shadow/paper/OOS gate, receive a decision packet when approval is required, and
only then may pass the separate live-release gate.

Protective runtime safety actions already covered by execution safeguards (for example stale-data
rejection, duplicate-order prevention, kill switch or circuit breaker) remain allowed according
to their safety contracts; they are not strategy learning/tuning.

The live phase therefore extends rather than ends the improvement loop. Each real-money version
must leave a complete evidence and migration trail for its successor.

### 12.5 Marktphasen-Lernen dauerhaft über alle Generationen (ab 2026-10-08)

**Ausgangsfall 2026-10-08:** `MARKET_REGIME_SEED_V1` in Issue #7
([kompakter Snapshot](https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/7#issuecomment-6066250115))
ist bereits persistiert und dient nur als dokumentierter, ab Erfassung
bekannter Startpunkt für spätere Abverkaufs-/Stabilisierungs-/Erholungs-
Analysen. Da seine Quelle CoinGecko/USD ist und keine geschlossene
Kraken-EUR-Regime-Episode belegt, darf er **nicht** als
`MARKET_REGIME_EPISODE_V1` für Entry- oder Outcome-Labels verwendet
werden. Erst die prospektiv nach Kraken-EUR-Daten bestätigte Folgeepisode
ist dafür zulässig. Seed, erste gültige Episode und möglicherweise
dazwischen liegende Datenlücke getrennt ausweisen; kein rückwirkendes
Markt-Timing, keine extra Work-Terminierung.



Der passive Forschungs-/Episodenvertrag
`research/v3/market-phase-reversal-observation-v1.md` gilt für **jeden
folgenden Marktzyklus und jede zukünftige Paper-, Shadow- und Echtgeldversion**,
nicht nur für V2R4/V3. Jede neue Strategiegeneration muss ihn in ihrer
predecessor→successor-Lineage explizit disponieren. Geerbt wird die
Beobachtungs-/Analysefähigkeit, **nicht** ein ungeprüfter Handelsvorteil.

Bei jeder **ohnehin ausgelösten** substanziellen Strategie-/Work-/Live-
Nachfolgeanalyse die vorhandenen `MARKET_REGIME_EPISODE_V1`-Belege aus dem
bestehenden V3-Research-Issue #7 (oder einem später offiziell migrierten,
versionierten Provenance-Nachfolger) dedupliziert berücksichtigen:
nur tatsächlich vor Entscheidung/Entry bekannte Phasen, spätere gereifte
Paper-/Live-Outcomes inklusive echter Fill-Kosten, Trade-Häufigkeit,
WAIT/REJECT, verpasste Chancen, Stop-/Risikoverhalten und potenziellem
Mehrwert gegenüber den bereits erfassten Kraken-Kontexten. Provenienz und
zeitliche Lücken offen ausweisen; `NOT_EVALUABLE` bei unzureichenden Daten,
`NO_ACTION_WARRANTED` ohne belegbaren Mehrwert.

Keine automatische neue Work-Analyse, keine Push-Nachricht, kein Raw-Marktarchiv
oder zusätzlicher Scanner. Keine H1-Standalone-Reaktivierung. Nie aufgrund
eines beobachteten Marktphasenwechsels aktive Entry-/Stop-/Sizing-/Scanner-
oder Echtgeldregeln ändern. Erst versionierter inaktiver Nachfolger,
prospektive Validierung, Kostenrechnung, Release-/Nutzerfreigabe; Live-
Trading/Orderrechte bleiben davon getrennt.

### 12.6 Automatischer Quellen-Erkenntnis-Transfer in geprüfte Nachfolger (ab 2026-10-08)

Dieser Abschnitt schließt die Lücke zwischen autonomem Quellen-Controlling
(`docs/market-source-autonomy-v1.md` / Kandidatenregister) und einem
tatsächlich **nützlichen Strategieergebnis**. Quellenauswahl und
Strategie-Einfluss sind zwei getrennte, verpflichtend verbundene Gates;
hohe Quellengüte allein beweist **keinen** profitablen Entry-Vorteil.

Bei jedem **ohnehin unabhängig geöffneten, substanziellen**
V2R4/V3/V4+/späteren Live-Analyse-Gate sind material neue
`MARKET_CONTEXT_EVENT_V1`-, `SOURCE_STEWARD_DECISION_V1`-
und `MARKET_REGIME_EPISODE_V1`-Erkenntnisse aus dem bisherigen
GitHub-Research-Issue #7 zu lesen und gegenüber bereits im
Strategiekontext enthaltenen Informationen **dedupliziert**
zu beurteilen, soweit zum konkreten Analysefenster relevant:
`known_at` VOR dem Candidate/Entry, Primärfakten, Reifegrad,
BUY/WAIT/REJECT, Trade-Konversion, verpasste Chancen, Kosten,
Kandidatenqualität, falsche Risikoblocks. Keine historische
Rückprojektion oder Datengleichheit zwischen CoinGecko/USD und
Kraken/EUR unterstellen.

Jeder **materiell bewertbare Quellen-Befund** erhält im normalen
Konsequenz-/Migrationspfad eine begründete Disposition
`NO_ACTION_WARRANTED`, `NOT_EVALUABLE` (mit präzisem kleinsten
nächsten Datengate), `PREPARE_ONE_CHANGE_TRIAL` (nur inaktiver,
vorregistrierter Shadow-Kandidat) oder
`REJECT_WITH_EVIDENCE`, mit `source_id`, Zeitfenster,
Evidenz und Ack/Dedupe im bestehenden `research/work-analysis-state.json`.
**Ein Quellen-Event öffnet niemals selbst das Analyse-Gate.**
Ein bereits geöffnetes Gate, das relevante bewertbare Erkenntnisse
bloß referiert, aber keine Disposition/erlaubte Konsequenz festhält,
ist noch nicht abgeschlossen. Nicht bewertbare Datensammlungen dürfen
V3 nicht künstlich blockieren; sie werden mit exaktem Evidenz-Gate
und Linienstammbaum nach V4+ weitergereicht. Kein zusätzlicher Work-
Lauf, keine neue Cron-/GitHub-Task, keine zusätzliche Scanner-Schleife.

Eine belegte neue Quellenwirkung kann innerhalb bestehender
Freigaben autonom bis zu einer **inaktiven** Hypothese oder einem
einzelnen V3-Vergleichstest vorbereitet werden. Für jede Änderung von
Entry/WAIT/REJECT/Stop/Sizing/Scanner/Live sind hingegen weiterhin
gesonderter Shadow/Paper-/Kosten- und Release-Gate sowie erforderliche
Nutzerfreigabe unverzichtbar. Keine eigenmächtige Anpassung der
aktiven V2R4-Strategie oder H3/H6-Sequenz; alte H1-Ablehnung bleibt
gültig.

### 12.7 Überwachungen dürfen sich nicht widersprechen (2026-10-08)

Kanonische Domänen-Zuordnung und verbindliche Schließstrecke:
`docs/unified-monitoring-learning-architecture-v1.md` /
`research/monitoring-evidence-routing-v1.json`.

**Jede sinnvolle Überwachung braucht einen adressierbaren
Ergebnis-Consumer, aber nicht jede Überwachung muss Handelsregeln
ändern:** Operations-Watchdogs → Auto-Heal/handlungsrelevante
Eskalation/HEALTHY-Ack; Quellenqualitätsprüfung → KEEP/QUARANTINE/
REPLACE/NOT_EVALUABLE; Markt-/News-/H-Komponenten → nur bereits
unabhängig geöffnete Strategieanalyse → reife `known_at`-Outcomes →
`NOT_EVALUABLE`/`NO_ACTION_WARRANTED`/
`REJECT_WITH_EVIDENCE`/`PREPARE_ONE_CHANGE_TRIAL`; gültige
inaktive Ein-Komponenten-V3-/Nachfolgerversion → separate Integrations-
und Release-/Freigabeprüfungen. Materiale Belege dürfen im Review
nicht folgenlos liegen bleiben. Kein neuer Task, Work-Gate, Scanner
oder Push für diese Zusammenführung.

**Dedup vor Bewertung:** Die gleiche Kraken-Bewegung darf über H1/
Regime/CoinGecko/CMC/H6 nicht als mehrfach unabhängige Zustimmung
zählen. Offizielles FOMC-Event = H5-Fakt; Redaktion/H11 liefern
allenfalls separaten Kontext. H3-Orderbuch ≠ H9-Fillmodell.
H8-Netzwerk-/H10-Traderaktivität mit getrennten Quellenzeiten;
H7 darf sie später nur nach eigenem Label-/Kosten-/One-change-Gate
kombinieren. Bereits verworfenes H1 nicht umbenannt reaktivieren.
Keine neue harte BUY-/WAIT-/REJECT-Sperre wegen zusätzlicher
optionaler Quellen oder deren Ausfall; Kraken-Execution-/Safety-
Gates bleiben unverändert.

**Release-Check:** Ein neuer Integrationskandidat muss
Funktionswechselwirkungen, Quellenkonflikt-/Missing-Mode, gleiche
Candidate-Clock, bewiesenen Netto-Effekt, vermiedene Verlusttrades,
False-REJECT/Missed-Move und Trade-Konversionsverlust gemeinsam
bewerten. Bei `NO_ACTION_WARRANTED` gilt die Überwachung
ausdrücklich als **ausgewertet**, nicht als nicht eingesetzt.
Bei E2E-Lücke `NOT_EVALUABLE` plus einen konkreten einmaligen
Akzeptanznachweis im bisherigen Backlog erhalten; keine
Scheinbestätigung aus einem aktivierten ChatGPT-Aufgabentext.

### 12.8 Eigenständig ausführbarer Safe-Work-Implementation-Pfad (2026-10-08)

Zusätzlich zu **bestehenden** Strategie-Reife-/Analyse-Gates darf
der täglich ohnehin angesetzte Work-Check **nur nach**
`tools/select-autonomous-implementation.py` `READY_SAFE_WORK`
auch eine kleine vorab klar autorisierte **Umsetzung** starten.
`docs/autonomous-followthrough-governance-v1.md` ist maßgeblich,
`research/autonomous-implementation-queue-v1.json` die
**einzige** zulässige Safe-Implementation-Allowlist.

Beispiel: H10-Erstreview belegt + H10-Kraken-EUR-`known_at`-
Join-Vertrag fehlt → autonom eng begrenzten **inaktiven**
Research-/Testvertrag und nötige Tests auf Branch/PR erstellen,
CI vollständig abwarten, bei grünen relevanten Guards
selbstständig mergen, danach Nachweis/Gate-Abschluss
idempotent registrieren. Bei neuem `next_control_decision`
nur den kleinsten Read-only-Adapter implementieren, nie
automatisch Strategy-Runtime/Schwellen/Orders schalten.

Ein Safe-Work-Gate gilt nur für die **vorgegebene konkrete
Aufgabe**, nicht als Freifahrtschein für Backlog-Vollauswertung,
H6-Shadow-Neustart, V3-Release, neue Automationsschleife
oder Echtgeldaktionen. Vor jedem Task: Source-of-truth-/PR-
Duplikate prüfen; höchstens ein Implementierungsbranch offen,
maximal zwei Tasks pro bestehendem Work-Turn. Nach jedem
tatsächlichen Bearbeitungsversuch in den vorhandenen
`research/work-analysis-state.json`-Ack `autonomy_task_attempts`
mit `task_id`, `gate_fingerprint`, `status` =
`BLOCKED`/`ACTIVE_PR`/`COMPLETED`, `evidence_url`
oder präzisem Blocker aufnehmen. Bei derselben blockierten
Evidenz keine Wiederholung. Nach PR-Merge auf `main`
erneut reinen Gate-Selektor prüfen. Veraltete, noch nicht
belegte automationsbedingte Source-E2E-Pfade werden nicht
als Erfolg gemeldet.

**Jede neue materielle Chat-Entscheidung** wird während der
Bearbeitung in kanonischer Form persistiert/zugeordnet.
Kann ein zukünftiger ungesichteter Chat nicht gelesen
werden, ist er aus Sicht des autonomen Runners nicht
automatisch bekannt; keine erfundene Allwissenheit.
