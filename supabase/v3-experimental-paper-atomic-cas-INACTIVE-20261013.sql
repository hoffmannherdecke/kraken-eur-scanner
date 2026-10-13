-- V3 EXPERIMENTAL PAPER / REVIEW DRAFT ONLY (2026-10-13).
-- DO NOT deploy, GRANT EXECUTE, call, migrate or schedule before:
--   original 28h Canary physical stop + 9 pinned SHA readback,
--   independent physical old writer + supervisor rearm fence,
--   preserved original WAIT/STOP and 6h/24h followup owner,
--   six source-authentic physical/Cloud E2E release proofs,
--   reviewed V3 operator/Edge dual credentials and explicit user approval.
-- This is not the V2R4-only technical rotation and MUST NOT use its RPC.
-- Designed against the read-only live public.paper_series schema on 13 Oct.
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

create or replace function public.rotate_v2r4_to_v3_experimental_paper(
    p_expected_old_series_id text,
    p_expected_old_release_sha text,
    p_expected_old_strategy_sha256 text,
    p_expected_old_runtime_sha256 text,
    p_expected_old_candidate_count bigint,
    p_expected_old_trade_count bigint,
    p_expected_old_last_outcome_updated_at timestamptz,
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
begin
    -- Same one-owner Paper series table and EXISTING unique active index.
    -- This lock is distinct from the past V2R4-only technical rotate RPC;
    -- actual concurrent races are also serialized by the old-series row
    -- and the single-active partial unique index.
    perform pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended('PAPER_STRATEGY_EXPERIMENTAL_CUTOVER', 0));

    if pg_catalog.to_regclass('public.paper_series_single_active_idx') is null
       or pg_catalog.to_regclass('public.paper_candidate_outcomes') is null
       or pg_catalog.to_regclass('public.paper_trade_results') is null then
        raise exception 'V3 CAS required existing original schema/index missing';
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
       or p_new_v3_config is null
       or pg_catalog.jsonb_typeof(p_new_v3_config) is distinct from 'object' then
        raise exception 'V3 CAS missing original outcome snapshot or config';
    end if;

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
    select count(*) into trade_count
      from public.paper_trade_results
     where series_id=p_expected_old_series_id;

    if outcome_count is distinct from p_expected_old_candidate_count
       or trade_count is distinct from p_expected_old_trade_count
       or last_outcome is distinct from p_expected_old_last_outcome_updated_at then
        raise exception 'V3 CAS fresh old Cloud outcome/trade checkpoint drift';
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

-- INERT EVEN IF ACCIDENTALLY MIGRATED:
-- DO NOT grant EXECUTE to service_role until external Edge dual-token,
-- physical supervisor disable/stop/backup/rollback, old-followup owner,
-- freeze status compatibility and six E2E gates are independently signed.
revoke all on function public.rotate_v2r4_to_v3_experimental_paper(
    text,text,text,text,bigint,bigint,timestamptz,
    text,text,text,timestamptz,jsonb,text,text,text)
    from public, anon, authenticated, service_role;
