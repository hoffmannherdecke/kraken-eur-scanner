-- Internal relay credential domains and backend-only grants.
-- Applied in production on 2026-10-05.
create table if not exists public.internal_relay_credentials (
  relay_id text primary key,
  token_sha256 text not null check (token_sha256 ~ '^[0-9a-f]{64}$'),
  enabled boolean not null default false,
  rotated_at timestamptz not null default now(),
  note text
);
alter table public.internal_relay_credentials enable row level security;
revoke all on public.internal_relay_credentials from anon, authenticated;
grant select on public.internal_relay_credentials to service_role;

insert into public.internal_relay_credentials(relay_id,token_sha256,enabled,note)
values
  ('v2r4-shadow-evidence-relay', repeat('0',64), false, 'pending dedicated MINI-PC token'),
  ('minipc-status-relay', repeat('0',64), false, 'pending dedicated MINI-PC token')
on conflict (relay_id) do nothing;

-- Rotation protocol:
-- 1. Generate token only on MINI-PC.
-- 2. Store only SHA-256 here.
-- 3. Verify client is using dedicated token.
-- 4. enable=true.
-- 5. Verify relay E2E.
-- 6. remove legacy client fallback in the next maintenance change.
