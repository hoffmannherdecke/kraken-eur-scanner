-- SOURCE ONLY / NEVER MIGRATE OR EXECUTE AS A RELEASE.
-- All statements are within ONE PL/pgSQL DO with an unconditional first
-- RAISE EXCEPTION. This is a deliberately inert future schema *candidate*.
-- Reviewer must create a newly approved migration and separate credentialed
-- CAS caller / audit append-writer / independent reader under Issue #99.
-- No CAS RPC, grants or production schema change is made by this source.
do $v3_cas_ledger_inactive$
begin
  raise exception 'V3_CAS_AUDIT_LEDGER_SOURCE_INACTIVE_APPROVAL_REQUIRED';

  -- Intentionally unreachable. The dedicated audit schema is not a public
  -- Data API schema. Creation privilege / owners require security review.
  create schema if not exists v3_cas_audit;
  revoke all on schema v3_cas_audit
    from public, anon, authenticated, service_role;

  -- The exclusive append-writer must transact a locked increment and one
  -- intent INSERT together, and COMMIT this transaction BEFORE any CAS RPC.
  -- A SELECT/ACK from independent reader is required after commit; an ACK
  -- from uncommitted same transaction is insufficient. No automatic RPC.
  create table v3_cas_audit.epoch_v1 (
    epoch_id text primary key
      check (epoch_id ~ '^V3CAS-AUDIT-[a-f0-9]{32}$'),
    predecessor_series_id text not null
      check (predecessor_series_id = 'PAPER-V2R4-20261009T110135Z'),
    expected_rpc text not null
      check (expected_rpc = 'public.rotate_v2r4_to_v3_experimental_paper'),
    source_sha256 text not null check (source_sha256 ~ '^[a-f0-9]{64}$'),
    original_fence_sha256 text not null check (original_fence_sha256 ~ '^[a-f0-9]{64}$'),
    approved_caller_acl_sha256 text not null
      check (approved_caller_acl_sha256 ~ '^[a-f0-9]{64}$'),
    opened_at_utc timestamptz not null default clock_timestamp(),
    next_ordinal bigint not null default 1 check (next_ordinal >= 1),
    sealed boolean not null default false
  );

  create table v3_cas_audit.intent_v1 (
    epoch_id text not null references v3_cas_audit.epoch_v1(epoch_id),
    ordinal bigint not null check (ordinal >= 1),
    intent_id uuid not null unique,
    requested_rpc text not null
      check (requested_rpc = 'public.rotate_v2r4_to_v3_experimental_paper'),
    predecessor_series_id text not null
      check (predecessor_series_id = 'PAPER-V2R4-20261009T110135Z'),
    request_sha256 text not null check (request_sha256 ~ '^[a-f0-9]{64}$'),
    source_sha256 text not null check (source_sha256 ~ '^[a-f0-9]{64}$'),
    fence_sha256 text not null check (fence_sha256 ~ '^[a-f0-9]{64}$'),
    created_at_utc timestamptz not null default clock_timestamp(),
    state text not null default 'PREINVOKE_INTENT'
      check (state = 'PREINVOKE_INTENT'),
    primary key(epoch_id,ordinal)
  );

  -- RLS is defense in depth; explicit privileges and separation of owners
  -- are mandatory. Even 'service_role' bypasses RLS in Supabase, so DO NOT
  -- GRANT it read/write access to this audit schema or the future CAS RPC.
  alter table v3_cas_audit.epoch_v1 enable row level security;
  alter table v3_cas_audit.epoch_v1 force row level security;
  alter table v3_cas_audit.intent_v1 enable row level security;
  alter table v3_cas_audit.intent_v1 force row level security;
  revoke all on v3_cas_audit.epoch_v1, v3_cas_audit.intent_v1
    from public, anon, authenticated, service_role;

  -- PROPOSED INTERNAL NOLOGIN ROLE BOUNDARIES. Entire block is behind
  -- the unconditional first RAISE above and cannot run in production.
  -- NO LOGIN credentials, NO role memberships, NO executable CAS RPC.
  -- RLS without explicit role policies would block even a narrowly granted
  -- writer/reader; keep this complete role+policy candidate together.
  create role v3_cas_audit_writer nologin noinherit nobypassrls;
  create role v3_cas_audit_reader nologin noinherit nobypassrls;
  create role v3_cas_executor nologin noinherit nobypassrls;
  grant usage on schema v3_cas_audit
    to v3_cas_audit_writer, v3_cas_audit_reader;
  grant select(epoch_id,next_ordinal,sealed)
    on v3_cas_audit.epoch_v1 to v3_cas_audit_writer;
  grant update(next_ordinal)
    on v3_cas_audit.epoch_v1 to v3_cas_audit_writer;
  grant insert on v3_cas_audit.intent_v1 to v3_cas_audit_writer;
  grant select on v3_cas_audit.epoch_v1, v3_cas_audit.intent_v1
    to v3_cas_audit_reader;

  create policy v3_cas_epoch_writer_read_v1
    on v3_cas_audit.epoch_v1 for select
    to v3_cas_audit_writer using (not sealed);
  create policy v3_cas_epoch_writer_advance_v1
    on v3_cas_audit.epoch_v1 for update
    to v3_cas_audit_writer using (not sealed) with check (not sealed);
  create policy v3_cas_intent_writer_append_v1
    on v3_cas_audit.intent_v1 for insert
    to v3_cas_audit_writer with check (state = 'PREINVOKE_INTENT');
  create policy v3_cas_epoch_reader_v1
    on v3_cas_audit.epoch_v1 for select
    to v3_cas_audit_reader using (true);
  create policy v3_cas_intent_reader_v1
    on v3_cas_audit.intent_v1 for select
    to v3_cas_audit_reader using (true);

  -- LIMITS: These roles are not assigned credentials or executor EXECUTE.
  -- Writer may currently choose a nonconsecutive next_ordinal (column-level
  -- UPDATE permission alone cannot force +1) or fabricate hash inputs.
  -- Exact monotonic step enforcement, an exclusive lock-holding append API,
  -- independent signed/off-DB custody and owner-tamper resistance are
  -- future BLOCKING security gates before any migration/privilege activation.
  -- RLS cannot defend against the privileged table owner / superuser.
  -- Shared BYPASSRLS service_role and public/anon/authenticated are not
  -- granted anything in this schema. Executor has no usage or table grant.
  -- NO GRANT EXECUTE to V3 CAS function (it does not exist).

  -- NO GRANT, NO SECURITY DEFINER, NO CAS EXECUTE, NO PUBLIC FUNCTION.
  -- PostgreSQL table owner/admin can modify tables irrespective of these
  -- client ACLs. Independent off-DB append-only retention or independently
  -- signed custody is still required for strong tamper-evidence.
  -- The future audit writer must lock epoch_v1 FOR UPDATE and atomically
  -- increment next_ordinal plus insert intent_v1, COMMIT, then independently
  -- read back ACK in another connection. Any crash/unknown fences the RPC.
end;
$v3_cas_ledger_inactive$;
