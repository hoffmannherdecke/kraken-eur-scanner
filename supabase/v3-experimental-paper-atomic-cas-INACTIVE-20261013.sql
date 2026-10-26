-- V3 EXPERIMENTAL PAPER / REVIEW DRAFT ONLY (2026-10-13).
-- DO NOT deploy, GRANT EXECUTE, call, migrate or schedule before:
--   original 28h Canary physical stop + 9 pinned SHA readback,
--   independent physical old writer + supervisor rearm fence,
--   preserved original WAIT/STOP and 6h/24h followup owner,
--   six source-authentic physical/Cloud E2E release proofs,
--   reviewed V3 operator/Edge dual credentials and explicit user approval.
--   separated existing NOLOGIN CAS executor/audit writer/reader roles and
--   independent durable PREINVOKE intent and external signed ACK before invocation.
-- This is not the V2R4-only technical rotation and MUST NOT use its RPC.
-- Designed against the read-only live public.paper_series schema on 13 Oct.
-- Include the last original trade updated_at in the SAME atomic CAS as the
-- existing candidate last update; closing a trade does not alter its count.
-- A predecessor with 0 trades must report a NULL max(updated_at).
-- No trigger/table/extra writer is installed by merely storing this draft.
--
-- ORIGINAL FOLLOWUPS: old-series paper_candidate_outcomes/paper_trade_results
-- remain in place; only the series status is changed in this transaction.
-- Dedicated old followup writer and all downstream consumers of the new
-- 'strategy_cutover_closed' status MUST pass separate integration review.
-- NEVER claim this SQL alone proves the physical writer is stopped.
--
-- On any exception PostgreSQL rolls back BOTH original series update and
-- new V3 insertion. On unknown commit result the host operator MUST fence
-- BOTH writers and independently READ BACK the active series; no auto retry.

-- DDL ATTEMPT BOUNDARY (SOURCE ONLY; not approved to install):
-- PostgreSQL grants EXECUTE on newly created functions to PUBLIC by default;
-- Supabase may additionally grant anon/authenticated/service_role defaults.
-- A standalone CREATE followed by a standalone REVOKE is NOT failclosed if
-- an operator stops or a client commits between statements. Keep creation
-- and REVOKE inside ONE server-side DO statement/one transaction. No one
-- can observe the callable public SECURITY DEFINER function before the
-- matching REVOKE commits. If an object already exists, abort rather than
-- silently replace a possibly privileged endpoint or altering its grants.
-- This is only a prospective installation safety improvement; no deployed
-- CAS, no privilege, no originalhost signer and NO V3 Paper release.
do $v3_cas_install_locked$
begin
  if pg_catalog.to_regprocedure(
    'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
  ) is not null then
    raise exception 'V3_CAS_INSTALL_EXISTING_SIGNATURE_HOLD';
  end if;

  -- PostgreSQL 17 creates a non-removable ADMIN-only grant for the
  -- non-superuser CREATEROLE creator: postgres / SET FALSE / INHERIT FALSE.
  -- This is privileged DBA administration, NOT an independently authorized
  -- CAS service actor. It cannot immediately SET ROLE or inherit executor
  -- rights. This cannot defend against deliberate privileged DBA alteration.
  -- Deny ALL other grant relationships, LOGIN, BYPASSRLS and role membership.
  -- No password, Cloud credential, service membership or CAS audit is issued.
  if (
    select count(*) from pg_catalog.pg_roles r
    where r.rolname in (
      'v3_cas_executor','v3_cas_audit_writer','v3_cas_audit_reader')
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
    raise exception 'V3_CAS_EXECUTOR_OR_AUDIT_ROLE_SCOPE_UNSAFE';
  end if;

  execute $v3_cas_create_locked$
create or replace function public.rotate_v2r4_to_v3_experimental_paper(
    p_expected_old_series_id text,
    p_expected_old_release_sha text,
    p_expected_old_strategy_sha256 text,
    p_expected_old_runtime_sha256 text,
    p_expected_old_candidate_count bigint,
    p_expected_old_trade_count bigint,
    p_expected_old_last_outcome_updated_at timestamptz,
    p_expected_old_last_trade_updated_at timestamptz,
    p_proposed_v3_series_id text,
    p_proposed_v3_test_id text,
    p_proposed_v3_revision text,
    p_cutover_at_utc timestamptz,
    p_new_v3_config jsonb,
    p_reviewed_new_repo_sha text,
    p_reviewed_new_bundle_sha256 text,
    p_reviewed_new_strategy_sha256 text
) returns jsonb
language plpgsql
security definer
set search_path = ''
as $v3_atomic_cas$
declare
    old_row public.paper_series%rowtype;
    outcome_count bigint;
    trade_count bigint;
    last_outcome timestamptz;
    last_trade timestamptz;
    v_actual_request_sha256 text;
begin
    -- Same one-owner Paper series table and EXISTING unique active index.
    -- This lock is distinct from the past V2R4-only technical rotate RPC;
    -- actual concurrent races are also serialized by the old-series row
    -- and the single-active partial unique index.
    perform pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended('PAPER_STRATEGY_EXPERIMENTAL_CUTOVER', 0));

    if pg_catalog.to_regclass('public.paper_series') is null
       or pg_catalog.to_regclass('public.paper_candidate_outcomes') is null
       or pg_catalog.to_regclass('public.paper_trade_results') is null then
        raise exception 'V3 CAS required existing original schema missing';
    end if;

    -- A same-named but invalid, non-unique or wrong-predicate index MUST NOT
    -- count as an atomic one-active-series fence. These exact catalog values
    -- were read independently from production (19 Oct 2026); this check is
    -- still a source-only draft, not an installed CAS or independent proof of
    -- native Windows fencing. Fail closed on any future schema/index drift.
    if not exists (
        select 1
          from pg_catalog.pg_index ix
          join pg_catalog.pg_class idx on idx.oid=ix.indexrelid
          join pg_catalog.pg_namespace ns on ns.oid=idx.relnamespace
         where ns.nspname='public'
           and idx.relname='paper_series_single_active_idx'
           and ix.indrelid=pg_catalog.to_regclass('public.paper_series')
           and ix.indisunique is true
           and ix.indisvalid is true
           and ix.indisready is true
           and ix.indislive is true
           and ix.indnkeyatts=1
           and ix.indnatts=1
           and pg_catalog.pg_get_indexdef(ix.indexrelid,1,true)='status'
           and pg_catalog.pg_get_expr(ix.indpred,ix.indrelid)
               ='(status = ''active''::text)'
    ) then
        raise exception 'V3 CAS missing exact valid unique single-active Paper index';
    end if;

    if p_expected_old_series_id is null
       or p_expected_old_series_id !~ '^PAPER-V2R4-[0-9]{8}T[0-9]{6}Z$'
       or p_proposed_v3_series_id is null
       or p_proposed_v3_series_id !~ '^PAPER-V3-[0-9]{8}T[0-9]{6}Z$'
       or p_proposed_v3_revision is null
       or p_proposed_v3_revision !~ '^V3-[A-Za-z0-9_.-]{8,95}$'
       or p_proposed_v3_test_id is null
       or p_proposed_v3_test_id !~ '^PAPER-V3-[A-Za-z0-9_.-]{8,95}$'
       or p_expected_old_series_id = p_proposed_v3_series_id then
        raise exception 'V3 CAS invalid distinct exact predecessor or successor';
    end if;

    if p_cutover_at_utc is null
       or p_cutover_at_utc is distinct from
          pg_catalog.date_trunc('second', p_cutover_at_utc)
       or p_proposed_v3_series_id is distinct from (
          'PAPER-V3-' || pg_catalog.to_char(
              p_cutover_at_utc at time zone 'UTC','YYYYMMDD"T"HH24MISS"Z"'))
       or p_cutover_at_utc > pg_catalog.clock_timestamp()
       or p_cutover_at_utc < pg_catalog.clock_timestamp()-interval '10 minutes' then
        raise exception 'V3 CAS cutover timestamp outside exact bounded window';
    end if;

    if p_expected_old_release_sha is null
       or p_expected_old_release_sha !~ '^[0-9a-f]{40}$'
       or p_expected_old_strategy_sha256 is null
       or p_expected_old_strategy_sha256 !~ '^[0-9a-f]{64}$'
       or p_expected_old_runtime_sha256 is null
       or p_expected_old_runtime_sha256 !~ '^[0-9a-f]{64}$'
       or p_reviewed_new_repo_sha is null
       or p_reviewed_new_repo_sha !~ '^[0-9a-f]{40}$'
       or p_reviewed_new_bundle_sha256 is null
       or p_reviewed_new_bundle_sha256 !~ '^[0-9a-f]{64}$'
       or p_reviewed_new_strategy_sha256 is null
       or p_reviewed_new_strategy_sha256 !~ '^[0-9a-f]{64}$' then
        raise exception 'V3 CAS release code/strategy SHA not individually pinned';
    end if;

    if p_expected_old_candidate_count is null
       or p_expected_old_candidate_count < 0
       or p_expected_old_trade_count is null
       or p_expected_old_trade_count < 0
       or (p_expected_old_candidate_count > 0 and
           p_expected_old_last_outcome_updated_at is null)
       or (p_expected_old_trade_count > 0 and
           p_expected_old_last_trade_updated_at is null)
       or p_new_v3_config is null
       or pg_catalog.jsonb_typeof(p_new_v3_config) is distinct from 'object' then
        raise exception 'V3 CAS missing original outcome snapshot or config';
    end if;

    -- SOURCE-ONLY CAS fence: no self-certified JSON proof or uncommitted
    -- intent is authority. The real original Cloud currently has no audit
    -- schema; a prematurely installed CAS must HOLD before Paper mutation.
    -- An independent authenticated Reader, external signature/custody and
    -- complete CAS-attempt coverage remain additional hard release gates.
    if pg_catalog.to_regclass('v3_cas_audit.epoch_v1') is null
       or pg_catalog.to_regclass('v3_cas_audit.intent_v1') is null then
        raise exception 'V3_CAS_PREINVOKE_AUDIT_SCHEMA_ABSENT_HOLD';
    end if;

    if coalesce(p_new_v3_config->>'preinvoke_epoch_id','') !~
          '^V3CAS-AUDIT-[a-f0-9]{32}$'
       or coalesce(p_new_v3_config->>'preinvoke_intent_id','') !~
          '^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
       or coalesce(p_new_v3_config->>'preinvoke_request_sha256','') !~
          '^[a-f0-9]{64}$'
       or coalesce(p_new_v3_config->>'preinvoke_source_sha256','') !~
          '^[a-f0-9]{64}$'
       or coalesce(p_new_v3_config->>'preinvoke_fence_sha256','') !~
          '^[a-f0-9]{64}$'
       or coalesce(p_new_v3_config->>'preinvoke_caller_acl_sha256','') !~
          '^[a-f0-9]{64}$' then
        raise exception 'V3_CAS_PREINVOKE_REFERENCE_INVALID_HOLD';
    end if;

    -- A source-bound, committed, sealed, exactly one-intent epoch must
    -- actually exist in the protected audit store. The CAS executor has no
    -- direct writer/reader access. A SQL row-lock is NOT irreversible:
    -- rollback loses it, and no pure SQL observation certifies TPM origin.
    perform 1 from v3_cas_audit.epoch_v1 e
      join v3_cas_audit.intent_v1 i on i.epoch_id=e.epoch_id
     where e.epoch_id=p_new_v3_config->>'preinvoke_epoch_id'
       and e.predecessor_series_id=p_expected_old_series_id
       and e.expected_rpc='public.rotate_v2r4_to_v3_experimental_paper'
       and e.source_sha256=p_new_v3_config->>'preinvoke_source_sha256'
       and e.original_fence_sha256=p_new_v3_config->>'preinvoke_fence_sha256'
       and e.approved_caller_acl_sha256=p_new_v3_config->>'preinvoke_caller_acl_sha256'
       and e.sealed is true and e.next_ordinal=2 and i.ordinal=1
       and i.intent_id=(p_new_v3_config->>'preinvoke_intent_id')::uuid
       and i.predecessor_series_id=e.predecessor_series_id
       and i.requested_rpc=e.expected_rpc
       and i.request_sha256=p_new_v3_config->>'preinvoke_request_sha256'
       and i.source_sha256=e.source_sha256
       and i.fence_sha256=e.original_fence_sha256
       and i.state='PREINVOKE_INTENT'
       and i.created_at_utc>=e.opened_at_utc
       and i.created_at_utc<=pg_catalog.clock_timestamp()
       and i.created_at_utc>pg_catalog.clock_timestamp()-interval '5 minutes'
      for update of e,i;
    if not found then
        raise exception 'V3_CAS_PREINVOKE_INTENT_NOT_PERSISTED_OR_BOUND';
    end if;
    -- The stored digest is only a required audit-row match here. Later,
    -- before Paper mutation, the independently typed 16-argument request
    -- digest is recalculated and MUST equal this already matched value.
    -- The reader-after-COMMIT, signer and irrevocable attempt fence remain
    -- OPEN; source-only matching cannot authorize real CAS dispatch.

    -- Locked actual CURRENT active predecessor; never use a stale config
    -- file/old V2R4 paper series as implicit current authority.
    select * into old_row
      from public.paper_series
     where series_id=p_expected_old_series_id
     for update;
    if not found
       or old_row.status is distinct from 'active'
       or old_row.strategy_revision not like 'V2R4-%'
       or old_row.config->>'release_repo_sha'
          is distinct from p_expected_old_release_sha
       or old_row.config->>'strategy_fingerprint_sha256'
          is distinct from p_expected_old_strategy_sha256
       or old_row.config->>'runtime_bundle_fingerprint_sha256'
          is distinct from p_expected_old_runtime_sha256
       or old_row.config->>'paper_only' is distinct from 'true'
       or old_row.config->>'real_money_actions_enabled' is distinct from 'false'
       or old_row.config->>'automatic_activation_allowed' is distinct from 'false' then
        raise exception 'V3 CAS predecessor not exact active SAFE V2R4 original';
    end if;

    if exists(select 1 from public.paper_series
              where status='active'
                and series_id <> p_expected_old_series_id)
       or exists(select 1 from public.paper_series
                 where series_id = p_proposed_v3_series_id) then
        raise exception 'V3 CAS wrong single-active or duplicate successor';
    end if;

    -- A release must include an explicitly reviewed unique successor
    -- fingerprint/strategy. No V2R4 strategy clone or real-money actions.
    if p_new_v3_config->>'series_id' is distinct from p_proposed_v3_series_id
       or p_new_v3_config->>'test_id' is distinct from p_proposed_v3_test_id
       or p_new_v3_config->>'strategy_revision' is distinct from p_proposed_v3_revision
       or p_new_v3_config->>'predecessor_series_id' is distinct from p_expected_old_series_id
       or p_new_v3_config->>'release_repo_sha' is distinct from p_reviewed_new_repo_sha
       or p_new_v3_config->>'runtime_bundle_fingerprint_sha256'
          is distinct from p_reviewed_new_bundle_sha256
       or p_new_v3_config->>'strategy_fingerprint_sha256'
          is distinct from p_reviewed_new_strategy_sha256
       or p_reviewed_new_strategy_sha256 = p_expected_old_strategy_sha256
       or p_new_v3_config->>'series_started_at_utc' is distinct from
           pg_catalog.to_char(p_cutover_at_utc at time zone 'UTC',
                               'YYYY-MM-DD"T"HH24:MI:SS"Z"')
       or p_new_v3_config->>'paper_phase' is distinct from 'EXPERIMENTAL_PAPER_ONLY'
       or p_new_v3_config->>'explicit_human_release_decision'
          is distinct from 'APPROVED_EXPERIMENTAL_PAPER'
       or p_new_v3_config->>'real_money_actions_enabled' is distinct from 'false'
       or p_new_v3_config->>'automatic_activation_allowed' is distinct from 'false'
       or p_new_v3_config->>'paper_only' is distinct from 'true'
       or p_new_v3_config->>'enabled' is distinct from 'true'
       or p_new_v3_config->>'scout_notional_eur' is distinct from '50'
       or p_new_v3_config->>'stage2_notional_eur' is distinct from '50'
       or p_new_v3_config->>'target_completed_paper_trades' is distinct from '20'
       or p_new_v3_config->>'old_followup_owner_preserved' is distinct from 'true'
       or p_new_v3_config->>'physical_v2r4_writer_fence_verified' is distinct from 'true'
       or p_new_v3_config->>'supervisor_old_intake_rearm_blocked' is distinct from 'true'
       or p_new_v3_config->>'independent_six_e2e_proofs_verified' is distinct from 'true' then
        raise exception 'V3 CAS proposed successor fails explicit bounded Paper-only release contract';
    end if;

    -- Physical boolean declarations in client JSON are NOT proof of
    -- Windows stop, source authenticity, model cost or external approval.
    -- The separate credentialed Edge/physical operator MUST validate all
    -- six independently before EVER granting execution of this RPC.

    -- Quiesce and independently snapshot old evidence FIRST. This lock
    -- prevents concurrent cloud followup updates from changing the
    -- checkpoint in the middle of an atomic conditional rotation.
    lock table public.paper_candidate_outcomes, public.paper_trade_results
      in share row exclusive mode;
    select count(*),max(updated_at)
      into outcome_count,last_outcome
      from public.paper_candidate_outcomes
     where series_id=p_expected_old_series_id;
    -- Original trades can close/change PnL without changing the row count.
    -- Bind a fresh Cloud version check to the original trade snapshot.
    select count(*),max(updated_at)
      into trade_count,last_trade
      from public.paper_trade_results
     where series_id=p_expected_old_series_id;

    if outcome_count is distinct from p_expected_old_candidate_count
       or trade_count is distinct from p_expected_old_trade_count
       or last_outcome is distinct from p_expected_old_last_outcome_updated_at
       or last_trade is distinct from p_expected_old_last_trade_updated_at then
        raise exception 'V3 CAS fresh old Cloud outcome/trade checkpoint drift';
    end if;

    v_actual_request_sha256 := pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
        pg_catalog.jsonb_build_array(
          'V3_CAS_FULL_REQUEST_PG17_JSONB_SHA256_V1',
          p_expected_old_series_id,
          p_expected_old_release_sha,
          p_expected_old_strategy_sha256,
          p_expected_old_runtime_sha256,
          p_expected_old_candidate_count,
          p_expected_old_trade_count,
          case when p_expected_old_last_outcome_updated_at is null then null
            else pg_catalog.to_char(
              p_expected_old_last_outcome_updated_at at time zone 'UTC',
              'YYYY-MM-DD"T"HH24:MI:SS.US"Z"') end,
          case when p_expected_old_last_trade_updated_at is null then null
            else pg_catalog.to_char(
              p_expected_old_last_trade_updated_at at time zone 'UTC',
              'YYYY-MM-DD"T"HH24:MI:SS.US"Z"') end,
          p_proposed_v3_series_id,
          p_proposed_v3_test_id,
          p_proposed_v3_revision,
          pg_catalog.to_char(p_cutover_at_utc at time zone 'UTC',
                             'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
          p_new_v3_config - 'preinvoke_request_sha256',
          p_reviewed_new_repo_sha,
          p_reviewed_new_bundle_sha256,
          p_reviewed_new_strategy_sha256
        )::text, 'UTF8'
      )), 'hex');
    -- Exact PostgreSQL 17 wire contract: 16 actual RPC parameters, typed
    -- JSONB array in argument order with an explicit domain separator.
    -- Timestamps are normalized to UTC microseconds (including NULL).
    -- Canonicalized JSONB successor config is hashed EXCEPT the one field
    -- carrying this very digest, preventing self-reference. No caller can
    -- reuse the approved epoch/intent hash for altered RPC args or unknown
    -- extra successor config properties. No pgcrypto extension or new RPC.
    -- The same PG17 canonical formula must be used by the separately
    -- authorized PREINVOKE append step, not taken from the client claim.
    -- A SQL SHA match does NOT attest independently COMMITTED external audit,
    -- TPM signer, reader identity or immutable complete attempt custody.
    if v_actual_request_sha256 is distinct from
       p_new_v3_config->>'preinvoke_request_sha256' then
      raise exception 'V3_CAS_FULL_REQUEST_MISMATCH_HOLD';
    end if;

    update public.paper_series
       set status='strategy_cutover_closed',
           updated_at=pg_catalog.clock_timestamp()
     where series_id=p_expected_old_series_id
       and status='active';
    if not found then raise exception 'V3 CAS predecessor close lost race'; end if;

    -- The existing partial unique index prevents a second active Paper
    -- even if an independently invoked writer/race tries to create one.
    insert into public.paper_series(
        series_id,test_id,strategy_revision,started_at,
        target_completed_trades,status,config
    ) values (
        p_proposed_v3_series_id,p_proposed_v3_test_id,p_proposed_v3_revision,
        p_cutover_at_utc,20,'active',p_new_v3_config
    );

    -- One Postgres transaction commits both rows or neither.
    -- The old candidate, fill and followup rows are never moved/edited.
    return pg_catalog.jsonb_build_object(
        'ok',true,'kind','V3_EXPERIMENTAL_PAPER_ATOMIC_CAS_V1',
        'predecessor_series_id',p_expected_old_series_id,
        'successor_series_id',p_proposed_v3_series_id,
        'strategy_revision',p_proposed_v3_revision,
        'cutover_at_utc',p_cutover_at_utc,
        'paper_only',true,'real_money_actions',false,
        'automatic_activation',false,
        'predecessor_outcome_count',outcome_count,
        'predecessor_trade_count',trade_count
    );
end;
$v3_atomic_cas$;

  $v3_cas_create_locked$;

  -- Still within this same DO statement: do not allow any PUBLIC endpoint
  -- to become observable if client/operator crashes before grants are revoked.
  execute $v3_cas_revoke_locked$
revoke all on function public.rotate_v2r4_to_v3_experimental_paper(
    text,text,text,text,bigint,bigint,timestamptz,timestamptz,
    text,text,text,timestamptz,jsonb,text,text,text)
    from public, anon, authenticated, service_role;

  $v3_cas_revoke_locked$;

  -- Only the existing distinct NOLOGIN executor gets EXECUTE. Since it has
  -- ZERO role members and cannot log in, this GRANT alone cannot dispatch
  -- CAS. Do NOT provision a LOGIN or membership here. A later restricted
  -- independent caller and cryptographically bound pre-CAS intent/ACK need
  -- the original Issue #99 production security and source-origin approval.
  execute $v3_cas_executor_only$
grant execute on function public.rotate_v2r4_to_v3_experimental_paper(
    text,text,text,text,bigint,bigint,timestamptz,timestamptz,
    text,text,text,timestamptz,jsonb,text,text,text)
    to v3_cas_executor;
  $v3_cas_executor_only$;

  if pg_catalog.has_function_privilege(
       'anon',
       'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)',
       'EXECUTE')
    or pg_catalog.has_function_privilege(
       'authenticated',
       'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)',
       'EXECUTE')
    or pg_catalog.has_function_privilege(
       'service_role',
       'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)',
       'EXECUTE')
    or pg_catalog.has_function_privilege(
       'v3_cas_audit_writer',
       'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)',
       'EXECUTE')
    or pg_catalog.has_function_privilege(
       'v3_cas_audit_reader',
       'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)',
       'EXECUTE')
    or not pg_catalog.has_function_privilege(
       'v3_cas_executor',
       'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)',
       'EXECUTE') then
    raise exception 'V3_CAS_EFFECTIVE_EXECUTE_PRIVILEGE_NOT_EXCLUSIVE';
  end if;
end;
$v3_cas_install_locked$;
