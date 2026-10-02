# Change Gate / Smoke-before-Scale Policy

Status: **ACTIVE GOVERNANCE / FAIL-CLOSED**  
Date: 2026-10-01

This policy applies to material strategy, runtime, infrastructure, data-source,
storage, historical-research and release changes.

The governing rule is simple:

> **Do not scale a change before its smallest meaningful end-to-end path works.**

A larger sample, longer runtime, broader universe, full archive download, wider
automation or release activation is not a substitute for proving the core path
first.

## Change classes covered

A change is material when it can alter or materially affect any of:

- strategy mechanics, thresholds, sizing, stops, TTL/revalidation or exits;
- candidate/evaluator/revalidation/persistence behavior;
- realtime feeds, trigger paths, queueing, supervisor/watchdog or recovery;
- data-source authority, source timing or source failure behavior;
- stored data/provenance/retention semantics;
- external integrations, credentials or rights;
- historical parser/replay/fill/cost semantics;
- release/activation/rollback behavior;
- anything that could create stale, duplicated, lost or incorrectly attributed
  evidence.

Documentation-only wording changes and read-only status queries do not require a
new E2E gate unless they accompany a material implementation change.

## Required progression

### Gate A — static / plan-only

Before execution where applicable:

- compile/parse/schema validation;
- explicit guardrails and no-action defaults;
- plan-only path for destructive/network/large-data actions;
- exact source/version/provenance identity;
- fail-closed behavior for missing prerequisites.

### Gate B — smallest deterministic smoke

Prove the core transformation with one tiny synthetic/local case:

- input is known;
- output is deterministic enough to inspect;
- timestamp/provenance semantics are explicit;
- idempotency/dedup is checked when relevant;
- failure is visible;
- no large sample is started yet.

### Gate C — one bounded real end-to-end proof

Only when a real environment is necessary:

- one candidate/event/source window/task;
- minimum duration/data volume required to prove the path;
- real persistence/relay/restore/recovery boundary if that is the thing under test;
- no broad collection or production-scale loop until this passes.

### Gate D — scale / collect

Only after A–C as applicable:

- broaden sample/universe/runtime;
- collect prospective evidence;
- keep the version frozen while measuring;
- do not silently tune the same version after seeing results.

## Explicit anti-patterns

Do **not**:

- launch 50/500/1000 cases because one-case E2E was never proven;
- run a long Work/CI loop to discover a wiring error that a one-case smoke would
  have exposed;
- bulk-download a large archive before parser/storage/checksum value is proven;
- treat transport success as proof of strategy-condition truth;
- treat a healthy process heartbeat as proof of fresh underlying data;
- modify thresholds to make a technical smoke pass;
- use a failed smoke as justification to open a sealed holdout;
- activate a runtime merely because unit tests are green.

## Evidence to retain

For a material gate, retain enough evidence to answer:

- what exact version/commit/spec was tested;
- what one small path was exercised;
- what passed/failed;
- whether live state was modified;
- whether model/exchange/account/order paths were invoked;
- what the next allowed gate is.

Evidence can live in the relevant release/readiness document, Trial Ledger,
Supabase evidence surface, GitHub Actions run, or MINI-PC report. Do not create a
second competing project to-do list.

## Existing examples

This policy formalizes the pattern already used successfully in the project:

- V2R3 persistence repair: tiny prospective cohort + immediate repeat guard before
  trusting the clean series;
- V2R4: local/Windows-shaped WAIT runtime smoke and isolated trigger→fresh-recheck
  proof before any Paper activation;
- historical OHLCVT: parser/PIT methodology gates before performance replay;
- targeted Kraken Time & Sales: synthetic PIT/identifiability gate before any
  large archive download;
- Binance public access: plan-only CI before the later one-time physical network
  smoke;
- MINI-PC backup: immediate seed + non-destructive restore smoke before relying on
  scheduled backups.

## CI notification / guard-edit discipline

Guard failures must remain visible, but incomplete intermediate edits must not create a storm of false-actionable GitHub failure notifications.

Binding workflow for multi-step CI/guard/research-contract changes:

- Stage iterative edits on a temporary branch instead of committing incomplete states directly to `main`.
- Push-triggered validation guards should be scoped to `branches: [main]` unless there is an explicit reason to validate every development branch.
- Merge/squash only the coherent completed change into `main`; the resulting main update should trigger the relevant guard once against the complete state.
- Guard workflows that can be superseded by a newer run use a workflow-specific `concurrency` group with `cancel-in-progress: true` so stale overlapping validations do not accumulate.
- `[skip ci]` / equivalent skip markers are **not** the default mechanism. GitHub supports them for push/pull-request events, but skipped required checks may remain pending and the commit receives no validation evidence. Use only for an explicitly documented exceptional case, never to bypass a release/freeze/safety guard.
- Runtime evidence/state commits, scheduled scanner/paper execution and fail-closed strategy guards are not weakened by this policy. A genuinely failing final guard remains red and actionable.

Reason: on 2026-10-02, iterative direct-to-main development produced 20 failure runs across seven guards; every affected guard later passed. The problem was notification noise from intermediate states, not seven persistent production faults.

## Safety boundary

Passing a smoke authorizes only the **next documented gate**. It never implicitly
authorizes:

- strategy promotion;
- larger sizing/capital;
- private exchange rights;
- live orders;
- leverage;
- withdrawal rights;
- sealed holdout access;
- destructive cleanup outside its explicit scope.


## Test-value / autonomy overlay

Detailed test-selection rules are canonical in `docs/test-strategy-runbook.md`.

Additional binding rules:

- A new test must close or materially inform a named evidence, strategy, runtime,
  execution-safety or release-integrity question.
- A previous PASS is reused unless relevant code/config/source semantics/environment
  changed, an explicit freshness rule expired, or an incident contradicts it.
- Do not repeat long physical tests after a technical failure until a shorter regression
  smoke proves the fix.
- ChatGPT executes GitHub/Supabase/public-API/read-only/static/CI work autonomously
  inside the existing project guardrails.
- User involvement is reserved for genuinely physical MINI-PC/home-network/hardware
  proof, unavailable login/secret/account UI, account-specific private state, real
  external transport, or an explicit human release/live-activation decision.
- Physical user actions should be batched and minimized.
- Not every open research hypothesis is a blocker for the first V3 shadow candidate.
  Only components actually proposed for that candidate must close their component gate.
- Deferred/data-maturity branches remain open instead of being forced through low-value
  repeated smokes.
- When the preregistered gate is met and the intended decision can be made, stop expanding
  the branch merely because additional tests are possible.
