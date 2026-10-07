-- Idempotent alert receipts for the V2R4 PAPER-only runtime.
create table if not exists public.v2r4_paper_alert_receipts (
  event_key text primary key,
  series_id text not null,
  candidate_id text not null,
  pair text not null,
  event_type text not null,
  event_at timestamptz,
  slack_webhook_accepted_at timestamptz not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists v2r4_paper_alert_receipts_series_idx
  on public.v2r4_paper_alert_receipts(series_id, created_at);

alter table public.v2r4_paper_alert_receipts enable row level security;
revoke all on public.v2r4_paper_alert_receipts from anon, authenticated;
