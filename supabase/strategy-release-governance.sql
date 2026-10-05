-- V2R3 -> V2R4 explicit release governance.
-- Applied in production on 2026-10-05.
create table if not exists public.strategy_release_decisions (
  release_id text primary key,
  predecessor_series_id text not null,
  successor_revision text not null,
  status text not null check (status in ('PENDING','APPROVED_PAPER','REJECTED','DEFERRED')),
  decided_at timestamptz,
  decision_evidence jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  final_review_completed_at timestamptz,
  migration_review_completed_at timestamptz
);
alter table public.strategy_release_decisions enable row level security;
revoke all on public.strategy_release_decisions from anon, authenticated;
grant select,insert,update on public.strategy_release_decisions to service_role;

alter table public.strategy_release_decisions
  drop constraint if exists strategy_release_decisions_approval_prereq_chk;
alter table public.strategy_release_decisions
  add constraint strategy_release_decisions_approval_prereq_chk
  check (
    status <> 'APPROVED_PAPER'
    or (
      decided_at is not null
      and final_review_completed_at is not null
      and migration_review_completed_at is not null
    )
  );

insert into public.strategy_release_decisions(
  release_id,predecessor_series_id,successor_revision,status,decision_evidence
) values (
  'V2R3_TO_V2R4_20261005',
  'PAPER-V2R3-CLEAN-20261001T0925Z',
  'V2R4',
  'PENDING',
  jsonb_build_object(
    'automatic_activation_allowed',false,
    'required_sequence',jsonb_build_array(
      'V2R3_EVIDENCE_DIVERSITY_COMPLETION',
      'V2R3_INTEGRITY_HEALTHY',
      'V2R3_FINAL_CAUSAL_REVIEW',
      'VALIDATED_FINDINGS_MIGRATED',
      'V2R4_SHADOW_MATURE',
      'MINIPC_HEALTHY',
      'EXPLICIT_PAPER_RELEASE_DECISION'
    )
  )
) on conflict (release_id) do nothing;

-- NOTE: The production v2r4_activation_readiness view preserves its historical
-- first 29 columns for dependent consumers and appends the new governance fields.
-- It never authorizes activation automatically. See the live database definition
-- for the exact view text and docs/v2r4-release-readiness.md for semantics.
