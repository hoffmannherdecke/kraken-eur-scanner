# AI / API Cost Guardrails

Status: **CALL-LEVEL MONITORING ACTIVE / TOKEN+EUR ACCOUNTING DEFERRED TO VERSION BOUNDARY**  
Date: 2026-10-01

This project uses model calls only for candidate evaluation and one-shot WAIT
revalidation. Health, archive, timing, completion and most infrastructure checks
remain deterministic and model-free.

## Current call-level observability

Supabase read-only views:

- `public.paper_model_invocation_events` — one row per persisted successful model
  response, split into INITIAL and REVALIDATION;
- `public.paper_model_usage_daily` — daily call/attempt/retry counts;
- `public.paper_model_usage_guard` — per-series structural anomaly guard.

Current clean V2R3 snapshot at activation of these views:

- Candidate-Outcomes: **78**;
- initial model calls: **77**;
- revalidation model calls: **64**;
- logical model calls: **141**;
- estimated HTTP attempts: **141**;
- retry overhead requests: **0**;
- duplicate response IDs: **0**;
- revalidation-without-initial-model: **0**;
- max attempt: **1**;
- model: `gpt-6-luna`;
- structural usage state: **HEALTHY**.

These counts are derived from existing immutable Paper payloads and therefore do
not change the active evaluator/runtime fingerprint.

## Structural cost guardrails

The active architecture deliberately limits model usage:

1. no continuous AI polling;
2. initial evaluator runs only for new unseen candidates that meet the runtime
   selection contract;
3. WAIT gets at most one one-shot TTL revalidation;
4. model API code retries at most once;
5. follow-up, health, archive, completion and most research bookkeeping do not
   invoke the model;
6. duplicate persisted response IDs or revalidation without an initial model
   response are treated as anomalies;
7. no budget/usage observation may automatically loosen strategy thresholds,
   increase sizing, or activate a different model.

## What is **not** currently measurable exactly

The frozen V2R3 evaluator persists:

- response ID;
- model;
- successful attempt number.

It does **not** persist the Responses API token `usage` object. Therefore the
current database can count logical model calls and retry overhead but cannot
reconstruct exact input/output/cached tokens or exact API currency cost.

Do not estimate a precise euro/dollar spend from call count alone.

Changing `paper_evaluator/evaluate.py` now merely to add token accounting would
change the frozen V2R3 runtime fingerprint and contaminate the clean prospective
series. That instrumentation is therefore deferred to the next explicit runtime
version boundary.

## Next runtime-version requirement

Before a later Paper version is activated, add versioned non-decision-affecting
usage provenance to model-backed records:

- input tokens;
- output tokens;
- cached/reused tokens when exposed by the API;
- model identifier;
- API attempt count;
- response ID;
- optional versioned price-table reference for cost calculation.

The usage fields must be observational only and must not alter the model prompt,
strategy decision or sizing.

## ChatGPT Work credits are separate

ChatGPT Work usage/credits are not the same accounting surface as project
OpenAI API calls. This repository currently has no authoritative connector or
ledger for Work-credit balances.

Rules:

- do not infer Work credits from API call counts;
- do not buy/add Work credits pre-emptively just because the project is active;
- continue moving routine work to GitHub/MINI-PC/Supabase as already done;
- use Work only for tasks where its desktop/browser execution adds material value;
- if an authoritative Work-credit usage source becomes available, add it as a
  separate source through the normal Source Intake Policy rather than mixing it
  into API call accounting.

## Budget decisions

No automatic monetary budget change is authorized by the usage views.

A future hard currency cap requires:

1. exact token usage in a new runtime version;
2. a versioned price table/source;
3. a user-approved budget threshold;
4. fail-soft alerting that does not mutate strategy behavior.

Until then, the reliable control is structural: event-driven calls, one-shot
revalidation, retry bounds, duplicate detection, and no AI polling.
