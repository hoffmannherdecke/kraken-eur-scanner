-- Persistent transition/dedupe state for the crypto process-health Slack router.
-- Applied to production Supabase on 2026-10-03 as migration add_process_health_alert_state.
create table if not exists public.process_health_alert_state (
  watch_id text primary key,
  last_condition text not null default 'UNKNOWN',
  last_fingerprint text,
  last_issue_codes jsonb not null default '[]'::jsonb,
  last_alert_at timestamptz,
  last_recovery_at timestamptz,
  updated_at timestamptz not null default now()
);

alter table public.process_health_alert_state enable row level security;

comment on table public.process_health_alert_state is
'Persistent dedupe/transition state for the crypto process-health Slack router. Service-role only; no strategy or trading authority.';
