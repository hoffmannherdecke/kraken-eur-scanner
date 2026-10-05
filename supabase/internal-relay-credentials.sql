-- Internal relay credential registry
-- Production migration: create_internal_relay_credentials (2026-10-05)
-- Token values and hashes are deliberately not committed to Git.

create table if not exists public.internal_relay_credentials (
  relay_id text primary key,
  token_sha256 text not null check (token_sha256 ~ '^[0-9a-f]{64}$'),
  enabled boolean not null default false,
  rotated_at timestamptz not null default now(),
  note text
);

alter table public.internal_relay_credentials enable row level security;
revoke all on public.internal_relay_credentials from anon, authenticated;

-- Required rows (hashes supplied only through secure operational migration):
-- minipc-status-relay
-- v2r4-shadow-evidence-relay
--
-- Edge Functions validate SHA-256(supplied dedicated token) against the enabled
-- row for their own relay_id. They do not reuse ALTRADY_WEBHOOK_TOKEN.
