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

  -- PROPOSED INTERNAL NOLOGIN ROLE BOUNDARIES. Entire block remains
  -- behind the unconditional FIRST RAISE; not a live migration.
  -- Reuse already-provisioned SAFE NOLOGIN roles rather than failing/adding
  -- another owner. PostgreSQL17 CREATEROLE may automatically assign only
  -- postgres ADMIN TRUE / SET FALSE / INHERIT FALSE; that is still a
  -- privileged administrator exception, not independently certified custody.
  -- Never silently accept a pre-existing role with LOGIN/BYPASSRLS or
  -- application member, and never grant a new LOGIN/role membership here.
  if pg_catalog.to_regrole('v3_cas_audit_writer') is null then
    create role v3_cas_audit_writer nologin noinherit nobypassrls;
  end if;
  if pg_catalog.to_regrole('v3_cas_audit_reader') is null then
    create role v3_cas_audit_reader nologin noinherit nobypassrls;
  end if;
  if pg_catalog.to_regrole('v3_cas_executor') is null then
    create role v3_cas_executor nologin noinherit nobypassrls;
  end if;
  if (
    select count(*) from pg_catalog.pg_roles r
    where r.rolname in
      ('v3_cas_audit_writer','v3_cas_audit_reader','v3_cas_executor')
      and not r.rolcanlogin and not r.rolinherit
      and not r.rolbypassrls and not r.rolsuper
      and not r.rolcreaterole and not r.rolcreatedb
      and not r.rolreplication
      and not exists (
        select 1 from pg_catalog.pg_auth_members m
        left join pg_catalog.pg_roles a on a.oid=m.member
        where (m.roleid=r.oid or m.member=r.oid)
          and not (
            m.roleid=r.oid and a.rolname='postgres'
            and m.admin_option and not m.set_option
            and not m.inherit_option
          )
      )
      and (
        select count(*) from pg_catalog.pg_auth_members m
        where m.roleid=r.oid
      ) <= 1
  ) <> 3 then
    raise exception 'V3_CAS_PREPROVISIONED_NOLOGIN_ROLES_UNSAFE';
  end if;
  -- Two separate, non-login object owners, distinct from the callable writer:
  -- the definer gets ONLY the table-column rights required by this append.
  -- Synthetic superuser DDL is used ONLY by offline PG17 CI; productive
  -- ownership, credentials and externally held audit proof remain unapproved.
  create role v3_cas_audit_table_owner nologin noinherit nobypassrls;
  create role v3_cas_audit_append_definer nologin noinherit nobypassrls;
  alter table v3_cas_audit.epoch_v1 owner to v3_cas_audit_table_owner;
  alter table v3_cas_audit.intent_v1 owner to v3_cas_audit_table_owner;
  -- PostgreSQL FK referential-integrity triggers run as the constrained
  -- table owner; this NOLOGIN table owner needs schema USAGE, not CREATE.
  grant usage on schema v3_cas_audit
    to v3_cas_audit_table_owner, v3_cas_audit_append_definer;
  grant select(epoch_id,next_ordinal,sealed,source_sha256,
               original_fence_sha256,predecessor_series_id,expected_rpc),
        update(next_ordinal)
    on v3_cas_audit.epoch_v1 to v3_cas_audit_append_definer;
  grant insert on v3_cas_audit.intent_v1
    to v3_cas_audit_append_definer;
  grant usage on schema v3_cas_audit
    to v3_cas_audit_writer, v3_cas_audit_reader;
  grant select(epoch_id,next_ordinal,sealed)
    on v3_cas_audit.epoch_v1 to v3_cas_audit_writer;
  grant select on v3_cas_audit.epoch_v1, v3_cas_audit.intent_v1
    to v3_cas_audit_reader;

  create policy v3_cas_epoch_writer_read_v1
    on v3_cas_audit.epoch_v1 for select
    to v3_cas_audit_writer using (not sealed);
  create policy v3_cas_epoch_reader_v1
    on v3_cas_audit.epoch_v1 for select
    to v3_cas_audit_reader using (true);
  create policy v3_cas_intent_reader_v1
    on v3_cas_audit.intent_v1 for select
    to v3_cas_audit_reader using (true);
  -- FORCE RLS also applies to the narrowly privileged append definer.
  -- The table owner receives NO usable DML policy in ordinary role context.
  create policy v3_cas_epoch_definer_read_v1
    on v3_cas_audit.epoch_v1 for select
    to v3_cas_audit_append_definer using (not sealed);
  create policy v3_cas_epoch_definer_update_v1
    on v3_cas_audit.epoch_v1 for update
    to v3_cas_audit_append_definer
    using (not sealed) with check (not sealed);
  create policy v3_cas_intent_definer_insert_v1
    on v3_cas_audit.intent_v1 for insert
    to v3_cas_audit_append_definer with check (true);

  -- The ONLY future audit mutation entrypoint: one SECURITY DEFINER
  -- append operation holding the bound epoch FOR UPDATE. Revoke all direct
  -- writer UPDATE/INSERT privileges. An ordinal is computed from the locked
  -- row, NOT supplied by any external caller. A failed INSERT rolls back
  -- the counter advance in the SAME transaction/statement.
  --
  -- SECURITY REVIEW BLOCKER: This inert DO runs under a synthetic CI admin,
  -- but object ownership below is reassigned to separate NOLOGIN roles.
  -- This does NOT attest production effective Supabase grants, role custody,
  -- exclusive invocation credentials, admin tamper resistance or off-DB logs.
  execute $v3_append_def$
    create function v3_cas_audit.append_intent_v1(
      p_epoch_id text,
      p_intent_id uuid,
      p_request_sha256 text,
      p_source_sha256 text,
      p_fence_sha256 text
    ) returns bigint
    language plpgsql
    security definer
    set search_path = pg_catalog, v3_cas_audit
    as $v3_append_body$
    declare
      v_ordinal bigint;
      v_source text;
      v_fence text;
      v_original text;
      v_rpc text;
    begin
      if p_epoch_id is null or p_intent_id is null or
         p_request_sha256 is null or p_request_sha256 !~ '^[a-f0-9]{64}$' or
         p_source_sha256 is null or p_source_sha256 !~ '^[a-f0-9]{64}$' or
         p_fence_sha256 is null or p_fence_sha256 !~ '^[a-f0-9]{64}$' then
        raise exception 'V3_CAS_AUDIT_APPEND_BAD_SOURCE_SCOPE';
      end if;
      select e.next_ordinal, e.source_sha256, e.original_fence_sha256,
             e.predecessor_series_id, e.expected_rpc
        into v_ordinal, v_source, v_fence, v_original, v_rpc
        from v3_cas_audit.epoch_v1 e
        where e.epoch_id = p_epoch_id and not e.sealed
        for update;
      if not found or
         v_original <> 'PAPER-V2R4-20261009T110135Z' or
         v_rpc <> 'public.rotate_v2r4_to_v3_experimental_paper' or
         v_source <> p_source_sha256 or v_fence <> p_fence_sha256 then
        raise exception 'V3_CAS_AUDIT_EPOCH_SEALED_OR_SOURCE_MISMATCH';
      end if;
      update v3_cas_audit.epoch_v1
        set next_ordinal = next_ordinal + 1
        where epoch_id = p_epoch_id;
      insert into v3_cas_audit.intent_v1
        (epoch_id, ordinal, intent_id, requested_rpc,
         predecessor_series_id, request_sha256, source_sha256, fence_sha256)
        values
        (p_epoch_id, v_ordinal, p_intent_id,
         'public.rotate_v2r4_to_v3_experimental_paper',
         'PAPER-V2R4-20261009T110135Z',
         p_request_sha256, p_source_sha256, p_fence_sha256);
      return v_ordinal;
    end
    $v3_append_body$;
  $v3_append_def$;

  -- Function EXECUTE defaults to PUBLIC in PostgreSQL. Revoke explicitly
  -- BEFORE granting only the internal NOLOGIN writer role. No CAS RPC.
  revoke all on function v3_cas_audit.append_intent_v1(
    text, uuid, text, text, text)
    from public, anon, authenticated, service_role,
         v3_cas_audit_reader, v3_cas_executor;
  grant execute on function v3_cas_audit.append_intent_v1(
    text, uuid, text, text, text) to v3_cas_audit_writer;
  -- Critical: no inherited postgres/admin owner on SECURITY DEFINER.
  -- The executable definer is NOLOGIN and cannot own/ALTER the tables.
  alter function v3_cas_audit.append_intent_v1(
    text, uuid, text, text, text) owner to v3_cas_audit_append_definer;

  -- LIMITS: These roles are not assigned credentials or executor EXECUTE.
  -- A caller cannot choose an ordinal or mutate tables directly; the
  -- one source-only append function obtains one FOR UPDATE row lock and
  -- assigns +1 while inserting the exact same ordinal atomically.
  -- However request hashes remain caller-asserted; original source/issuer
  -- authenticity, independently protected off-DB custody, role provisioning
  -- and privileged database administrator tamper resistance remain BLOCKING.
  -- RLS cannot defend against the privileged table owner / superuser.
  -- Shared BYPASSRLS service_role and public/anon/authenticated are not
  -- granted anything in this schema. Executor has no usage or table grant.
  -- NO GRANT EXECUTE to V3 CAS function (it does not exist).

  -- NO PUBLIC EXECUTE, NO CAS EXECUTE, NO LOGIN CREDENTIALS.
  -- PostgreSQL table owner/admin can modify tables irrespective of these
  -- client ACLs. Independent off-DB append-only retention or independently
  -- signed custody is still required for strong tamper-evidence.
  -- The restricted function locks epoch_v1 FOR UPDATE and atomically
  -- increments +1 while inserting intent_v1. CALLER must COMMIT before any
  -- CAS, then an independent reader must verify durable ACK from another
  -- connection. Crash/UNKNOWN fences the RPC; no CAS grant exists.
end;
$v3_cas_ledger_inactive$;
