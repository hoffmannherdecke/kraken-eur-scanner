# Project Control-Plane Governance

Status: **CANONICAL / ACTIVE**

## Purpose

The project previously allowed current status to be repeated in several documents. That was useful during rapid development but created a risk that an old sentence could later be mistaken for current authority.

The control plane is now deliberately split by responsibility:

1. `project-current-state.json` — single machine-readable declaration of the **current** strategy/research/control-plane state.
2. Live Supabase/MINI-PC evidence — authoritative for instantaneous runtime health, counters and evidence rows.
3. `docs/master-version-register.md` — version/component/history register.
4. `PROJECT_BACKLOG.md` — open work only; never runtime/status authority.
5. Strategy/research documents — methodology, contracts and dated evidence. Historical wording may remain only when explicitly historical.

## Transition rule

Every material activation, closure, rollback, baseline switch, promotion, strategy-changing Shadow start/stop or real-money release step must update `project-current-state.json` as part of the same bounded change sequence.

A transition is incomplete if runtime changed but the current-state file still declares the predecessor state.

## Strategy-changing Shadow WIP limit

At most **one** Shadow/Paper experiment that can alter a strategy decision may be active at a time.

Passive observational research may run in parallel only when it has no decision authority and cannot change the active strategy, order state, sizing, entry, exit, stop or risk gate.

This keeps causal attribution clean and prevents two successor branches from competing for the same baseline at once.

## Baseline replay rule

For every strategy-changing Shadow candidate, a claimed causal decision divergence is valid only when a same-snapshot baseline control replay reproduces the official baseline decision.

This rule generalizes the protection already used by H3 and is permanent for V3 and later generations. A model/evaluator instability must not be counted as candidate value.

## Integration rule

One-change testing remains mandatory for component attribution. After individual components are reviewed, any retained components must be tested again in a separately versioned **integration candidate** before promotion. Individually useful components are not assumed to be jointly useful.

## Status-document rule

Documents may describe historical states, but current status must not be inferred from them when they conflict with `project-current-state.json`.

New documents should reference the current-state file instead of copying active strategy IDs, active series IDs, active Shadow IDs or next-control decisions unless the duplicate is explicitly a dated release record.

## Workflow surface

`docs/workflow-registry.json` classifies every GitHub Actions workflow by lifecycle and role. The registry is audited by `tools/validate-workflow-registry.py`.

Historical/manual/validation workflows may remain in the repository for provenance and recovery without being part of the active runtime control surface.

## Safety boundary

Nothing in this governance file authorizes real-money trading, private order rights, leverage, automatic promotion or automatic strategy activation.

## Autonomous milestone controller (2026-10-08)

Workflow: `.github/workflows/autonomous-project-milestones.yml`; engine:
`tools/project_milestone_controller.py`. Runs once daily via GitHub Actions,
independent of ChatGPT Work. Manual dispatch inspects only; scheduled runs may
post *one* milestone receipt to the relevant existing GitHub issue and an
optional Slack signal. No new issue/backlog, Supabase schema, timer service,
Mini-PC task or recurring Work invocation is introduced.

- Current declared strategy/shadow authority: `project-current-state.json`.
  Live evidence authority: Supabase completion and H3 status views.
- The controller requires exact strategy, series, baseline and fixed policy
  matches, timely H3 evidence, immutable Paper rules and at most one active
  strategy-changing Shadow. Missing or contradictory inputs fail closed.
- V2R4 final review is surfaced only when the actual registered sample,
  temporal-diversity and maturity gate is complete. A distinct early
  **low-trade** review is raised once the series has >=72h, >=100 candidates,
  >=30 completed 24h follow-ups and still 0 completed Paper trades.
- H3 fixed review is surfaced only after its frozen sample/capture gate,
  stop condition and follow-up readiness. H6 remains queued pending H3
  review; never starts as a second strategy-changing Shadow.
- H10 first review is already complete; its next concrete research milestone
  is the preregistered point-in-time Kraken-EUR outcome/context join and
  false-positive label contract. Observation/capture continues independently.
- Each ready milestone carries a deterministic stable event key based on the
  milestone and frozen candidate/series identity; prior bot receipts in
  GitHub issue comments suppress duplicate notifications. These comments
  are receipt/history only, not a second task authority.
- Automatic work here is **evidence collection, eligibility checking,
  classification, review readiness and escalation**. A ready review must
  be conducted and its findings dispositioned under the existing
  analysis-to-consequence rule. This gate controller is *not* a trading,
  strategy-editing, PR-merging, shadow-starting or automatic release engine.
  Autonomous engineering may follow validated, low-risk plans separately;
  any material strategy promotion, new shadow activation, live/private
  exchange rights and sizing changes still require the existing release gates.
- The workflow has read-only repo contents and Supabase GET access. The
  only write permission is existing GitHub issue comments; the optional
  Slack notification is a one-way webhook. No secrets are emitted to
  diagnostics. Any absence of live evidence produces a failed control check,
  never a guessed pass.
- Changes to this controller use branch -> minimal tests -> validated PR ->
  merge; never mid-series tuning or direct runtime-to-main writes.
