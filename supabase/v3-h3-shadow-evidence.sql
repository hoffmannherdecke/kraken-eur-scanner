-- V3-H3-SHADOW-001 evidence schema.
-- Applied to Supabase as migration: create_v3_h3_shadow_evidence
-- Service-role/Edge-relay only; anon/authenticated grants are explicitly revoked.

create table if not exists public.v3_h3_shadow_evidence (
  candidate_id text primary key,
  shadow_candidate_id text not null,
  baseline_series_id text not null,
  pair text not null,
  candidate_event_time timestamptz,
  context_status text not null,
  baseline_decision text not null,
  control_replay_decision text not null,
  shadow_decision text not null,
  baseline_replay_stable boolean not null,
  decision_diverged boolean not null,
  payload jsonb not null,
  source_commit text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint v3_h3_shadow_evidence_pair_chk check (pair in ('XBT/EUR','ETH/EUR','SOL/EUR')),
  constraint v3_h3_shadow_evidence_context_chk check (context_status in ('PASS','MISSING_FAIL_CLOSED')),
  constraint v3_h3_shadow_evidence_baseline_decision_chk check (baseline_decision in ('BUY_SCOUT','WAIT','REJECT')),
  constraint v3_h3_shadow_evidence_control_decision_chk check (control_replay_decision in ('BUY_SCOUT','WAIT','REJECT')),
  constraint v3_h3_shadow_evidence_shadow_decision_chk check (shadow_decision in ('BUY_SCOUT','WAIT','REJECT')),
  constraint v3_h3_shadow_evidence_guard_chk check (
    payload @> '{"guardrails":{"orders":false,"real_money_actions":false,"automatic_promotion":false}}'::jsonb
  )
);

create index if not exists v3_h3_shadow_evidence_series_time_idx
  on public.v3_h3_shadow_evidence (baseline_series_id, candidate_event_time);

create table if not exists public.v3_h3_shadow_status (
  shadow_candidate_id text primary key,
  generated_at timestamptz not null,
  payload jsonb not null,
  source_commit text,
  updated_at timestamptz not null default now(),
  constraint v3_h3_shadow_status_guard_chk check (
    payload @> '{"orders":false,"real_money_actions":false,"automatic_promotion":false}'::jsonb
  )
);

alter table public.v3_h3_shadow_evidence enable row level security;
alter table public.v3_h3_shadow_status enable row level security;
revoke all on public.v3_h3_shadow_evidence from anon, authenticated;
revoke all on public.v3_h3_shadow_status from anon, authenticated;
grant select, insert, update, delete on public.v3_h3_shadow_evidence to service_role;
grant select, insert, update, delete on public.v3_h3_shadow_status to service_role;
