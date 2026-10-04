-- Persistent transition/dedupe state for the crypto process-health Slack router.
-- Applied to production Supabase on 2026-10-03 as migration add_process_health_alert_state.
-- Incident-grace fields added on 2026-10-04 as migration harden_process_health_incident_grace.
create table if not exists public.process_health_alert_state (
  watch_id text primary key,
  last_condition text not null default 'UNKNOWN',
  last_fingerprint text,
  last_issue_codes jsonb not null default '[]'::jsonb,
  last_alert_at timestamptz,
  last_recovery_at timestamptz,
  incident_started_at timestamptz,
  current_incident_alerted boolean not null default false,
  updated_at timestamptz not null default now()
);

alter table public.process_health_alert_state
  add column if not exists incident_started_at timestamptz;

alter table public.process_health_alert_state
  add column if not exists current_incident_alerted boolean not null default false;

alter table public.process_health_alert_state enable row level security;

comment on table public.process_health_alert_state is
'Persistent dedupe/transition state for the crypto process-health Slack router. Service-role only; no strategy or trading authority.';

comment on column public.process_health_alert_state.incident_started_at is
'UTC start time of the currently observed critical incident fingerprint; reset on recovery or fingerprint change.';

comment on column public.process_health_alert_state.current_incident_alerted is
'Whether the currently observed critical incident has already produced a user-facing Slack alert.';
