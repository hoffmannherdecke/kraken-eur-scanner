-- PREPARATION ONLY. NOT APPLIED TO PRODUCTION.
-- Dedicated atomic technical V2R4 successor transaction.
-- Invocation requires a separately reviewed dual-token Edge Function and
-- a quiesced/snapshotted MINI-PC. This file does NOT install or run itself.

-- The candidate_id primary keys are global, not composite (series_id,id).
-- Reject any cross-series UPDATE/UPSERT that would overwrite historical evidence.
create or replace function public.guard_paper_evidence_series_immutability()
returns trigger language plpgsql security invoker set search_path = ''
as $guard$
begin
  if new.series_id IS DISTINCT FROM old.series_id
     or new.candidate_id IS DISTINCT FROM old.candidate_id then
    raise exception 'paper evidence candidate identity cannot change series';
  end if;
  return new;
end;
$guard$;
revoke all on function public.guard_paper_evidence_series_immutability()
  from public, anon, authenticated;
grant execute on function public.guard_paper_evidence_series_immutability()
  to service_role;

drop trigger if exists paper_candidate_series_immutable_guard
  on public.paper_candidate_outcomes;
create trigger paper_candidate_series_immutable_guard
before update on public.paper_candidate_outcomes
for each row execute function public.guard_paper_evidence_series_immutability();

drop trigger if exists paper_trade_series_immutable_guard
  on public.paper_trade_results;
create trigger paper_trade_series_immutable_guard
before update on public.paper_trade_results
for each row execute function public.guard_paper_evidence_series_immutability();

-- Freeze H3-001 at the database boundary after the predecessor closes:
-- a delayed authenticated H3 upsert must never reactivate the archived status.
create or replace function public.guard_frozen_h3_001_status()
returns trigger language plpgsql security invoker set search_path = ''
as $h3$
begin
  if old.shadow_candidate_id = 'V3-H3-SHADOW-001'
     and old.payload->>'status' = 'FROZEN_TECHNICAL_CUTOVER' then
    raise exception 'frozen H3-001 baseline status is immutable';
  end if;
  if new.shadow_candidate_id is distinct from old.shadow_candidate_id then
    raise exception 'H3 status identity is immutable';
  end if;
  return new;
end;
$h3$;
revoke all on function public.guard_frozen_h3_001_status()
  from public, anon, authenticated;
grant execute on function public.guard_frozen_h3_001_status()
  to service_role;
drop trigger if exists v3_h3_001_frozen_status_guard
  on public.v3_h3_shadow_status;
create trigger v3_h3_001_frozen_status_guard
before update on public.v3_h3_shadow_status
for each row execute function public.guard_frozen_h3_001_status();

create table if not exists public.paper_technical_rotations (
  predecessor_series_id text primary key references public.paper_series(series_id),
  successor_series_id text not null unique references public.paper_series(series_id),
  cutover_at_utc timestamptz not null,
  predecessor_release_repo_sha text not null,
  successor_release_repo_sha text not null,
  predecessor_runtime_sha256 text not null,
  successor_runtime_sha256 text not null,
  strategy_fingerprint_sha256 text not null,
  predecessor_outcomes bigint not null,
  predecessor_trades bigint not null,
  predecessor_last_outcome_updated_at timestamptz,
  successor_test_id text not null,
  recorded_at_utc timestamptz not null default now(),
  constraint technical_rotation_not_same check (predecessor_series_id IS DISTINCT FROM successor_series_id)
);
alter table public.paper_technical_rotations enable row level security;
revoke all on public.paper_technical_rotations from public, anon, authenticated;
grant select, insert on public.paper_technical_rotations to service_role;
-- Deliberately no client-facing table access. SECURITY DEFINER function below
-- is executable by service_role only; frontend/user tokens cannot rotate.

create or replace function public.rotate_v2r4_technical_paper(
  p_old_series_id text,
  p_new_series_id text,
  p_new_test_id text,
  p_cutover_at_utc timestamptz,
  p_new_config jsonb,
  p_expected_old_release_sha text,
  p_expected_old_outcomes bigint,
  p_expected_old_trades bigint,
  p_expected_old_last_updated_at timestamptz
) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_old public.paper_series%rowtype;
  v_successor public.paper_series%rowtype;
  v_prior public.paper_technical_rotations%rowtype;
  v_outcomes bigint;
  v_trades bigint;
  v_last_update timestamptz;
  v_new_sha text;
  v_old_strategy text;
  v_rev text := 'V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION';
  v_excluded_keys text[] := array[
    'series_id','test_id','predecessor_series_id','series_started_at_utc',
    'release_repo_sha','runtime_bundle_fingerprint_sha256',
    'technical_change_id','technical_change_approved'
  ];
begin
  -- Additional dual-token authorization, source manifest proof and local
  -- quiescence are mandatory at the separate Edge/API + MINI-PC release gate.
  -- Do not call directly before those are implemented and reviewed.
  perform pg_advisory_xact_lock(hashtextextended('V2R4_TECHNICAL_ROTATION',0));
  if to_regclass('public.paper_series_single_active_idx') is null then
    raise exception 'one-active-series unique index missing';
  end if;
  if p_old_series_id IS DISTINCT FROM 'PAPER-V2R4-20261007T184255Z'
     or p_expected_old_outcomes is null or p_expected_old_outcomes < 0
     or p_expected_old_trades is null or p_expected_old_trades < 0
     or p_expected_old_release_sha is null
     or p_new_series_id is null or p_new_series_id !~ '^PAPER-V2R4-[0-9]{8}T[0-9]{6}Z$'
     or p_new_series_id = p_old_series_id
     or p_new_test_id is null or p_new_test_id !~ '^PAPER-V2R4-TECH-[0-9]{8}$' then
    raise exception 'unexpected technical rotation identity';
  end if;
  if p_cutover_at_utc is null then
    raise exception 'cutover UTC missing';
  end if;
  if p_new_series_id IS DISTINCT FROM ('PAPER-V2R4-' || to_char(p_cutover_at_utc at time zone 'UTC','YYYYMMDD"T"HH24MISS"Z"'))
     or p_new_test_id IS DISTINCT FROM ('PAPER-V2R4-TECH-' || to_char(p_cutover_at_utc at time zone 'UTC','YYYYMMDD'))
     or p_cutover_at_utc IS DISTINCT FROM date_trunc('second',p_cutover_at_utc) then
    raise exception 'successor identity does not match cutover UTC';
  end if;
  if p_new_config is null or jsonb_typeof(p_new_config) IS DISTINCT FROM 'object' then
    raise exception 'new config absent or not an object';
  end if;

  select * into v_old from public.paper_series
  where series_id = p_old_series_id for update;
  if not found then raise exception 'predecessor absent'; end if;
  select * into v_prior from public.paper_technical_rotations
  where predecessor_series_id = p_old_series_id for update;

  -- Safe retry: an identical already committed rotation returns success
  -- WITHOUT closing/opening any additional series or editing any evidence.
  if found then
    select * into v_successor from public.paper_series
    where series_id=v_prior.successor_series_id;
    if v_prior.successor_series_id IS DISTINCT FROM p_new_series_id
       or v_prior.successor_test_id IS DISTINCT FROM p_new_test_id
       or v_prior.cutover_at_utc IS DISTINCT FROM p_cutover_at_utc
       or v_prior.predecessor_release_repo_sha IS DISTINCT FROM lower(p_expected_old_release_sha)
       or v_prior.predecessor_outcomes IS DISTINCT FROM p_expected_old_outcomes
       or v_prior.predecessor_trades IS DISTINCT FROM p_expected_old_trades
       or v_prior.predecessor_last_outcome_updated_at
          is distinct from p_expected_old_last_updated_at
       or v_old.status IS DISTINCT FROM 'technical_closed'
       or v_successor.series_id is null
       or v_successor.status IS DISTINCT FROM 'active'
       or v_successor.config IS DISTINCT FROM p_new_config then
      raise exception 'rotation replay conflict';
    end if;
    return jsonb_build_object('ok',true,'idempotent',true,
      'predecessor_series_id',p_old_series_id,
      'successor_series_id',p_new_series_id,
      'cutover_at_utc',p_cutover_at_utc);
  end if;

  -- Late retry is safe ONLY after matching the immutable prior record.
  if p_cutover_at_utc > clock_timestamp()
     or p_cutover_at_utc < clock_timestamp() - interval '10 minutes' then
    raise exception 'cutover time outside bounded recent UTC window';
  end if;

  if (p_expected_old_last_updated_at is null and p_expected_old_outcomes > 0)
     or v_old.status IS DISTINCT FROM 'active'
     or v_old.strategy_revision IS DISTINCT FROM v_rev
     or v_old.config->>'release_repo_sha' IS DISTINCT FROM lower(p_expected_old_release_sha)
     or lower(p_expected_old_release_sha) IS DISTINCT FROM '3c6729a6c548d169f56a97f07f75892f37211636'
     or v_old.config->>'paper_only' IS DISTINCT FROM 'true'
     or v_old.config->>'real_money_actions_enabled' IS DISTINCT FROM 'false' then
    raise exception 'predecessor not pinned and active';
  end if;
  if exists(select 1 from public.paper_series
            where status='active' and series_id<>p_old_series_id) then
    raise exception 'another active series exists';
  end if;
  if exists(select 1 from public.paper_series
            where series_id=p_new_series_id) then
    raise exception 'successor id already exists';
  end if;
  -- Explicit H3-001 archival boundary: never silently rebind its baseline.
  if not exists(
    select 1 from public.v3_h3_shadow_status
    where shadow_candidate_id='V3-H3-SHADOW-001'
      and payload->>'baseline_series_id'=p_old_series_id
  ) then raise exception 'original H3 baseline missing or changed'; end if;

  -- Stable counts require the operator to quiesce local old writers and
  -- drain/acknowledge their last sync BEFORE calling this transaction.
  lock table public.paper_candidate_outcomes, public.paper_trade_results
    in share row exclusive mode;
  select count(*),max(updated_at) into v_outcomes,v_last_update
    from public.paper_candidate_outcomes where series_id=p_old_series_id;
  select count(*) into v_trades
    from public.paper_trade_results where series_id=p_old_series_id;
  if v_outcomes IS DISTINCT FROM p_expected_old_outcomes
     or v_trades IS DISTINCT FROM p_expected_old_trades
     or v_last_update is distinct from p_expected_old_last_updated_at then
    raise exception 'old evidence does not match final synced snapshot';
  end if;

  v_old_strategy := v_old.config->>'strategy_fingerprint_sha256';
  if v_old_strategy is null or v_old_strategy !~ '^[0-9a-f]{64}$'
     or v_old.config->>'runtime_bundle_fingerprint_sha256' is null then
    raise exception 'predecessor fingerprints missing';
  end if;
  v_new_sha := lower(p_new_config->>'release_repo_sha');
  if p_new_config->>'series_id' IS DISTINCT FROM p_new_series_id
     or p_new_config->>'test_id' IS DISTINCT FROM p_new_test_id
     or p_new_config->>'predecessor_series_id' IS DISTINCT FROM p_old_series_id
     or p_new_config->>'strategy_revision' IS DISTINCT FROM v_rev
     or p_new_config->>'series_started_at_utc' IS DISTINCT FROM to_char(p_cutover_at_utc at time zone 'UTC','YYYY-MM-DD"T"HH24:MI:SS"Z"')
     or p_new_config->>'technical_change_id' IS DISTINCT FROM 'V2R4_TECHNICAL_RECOVERY_20261009'
     or p_new_config->>'technical_change_approved' IS DISTINCT FROM 'true'
     or p_new_config->>'release_decision' IS DISTINCT FROM 'APPROVED_PAPER'
     or p_new_config->>'enabled' IS DISTINCT FROM 'true'
     or p_new_config->>'paper_only' IS DISTINCT FROM 'true'
     or p_new_config->>'real_money_actions_enabled' IS DISTINCT FROM 'false'
     or p_new_config->>'automatic_activation_allowed' IS DISTINCT FROM 'false'
     or p_new_config->>'strategy_fingerprint_sha256' IS DISTINCT FROM v_old_strategy
     or p_new_config->>'scout_notional_eur' IS DISTINCT FROM '50'
     or p_new_config->>'stage2_notional_eur' IS DISTINCT FROM '50'
     or p_new_config->>'target_completed_paper_trades' IS DISTINCT FROM '20'
     or v_new_sha is null or v_new_sha !~ '^[0-9a-f]{40}$'
     or p_new_config->>'runtime_bundle_fingerprint_sha256' is null or lower(p_new_config->>'runtime_bundle_fingerprint_sha256') !~ '^[0-9a-f]{64}$'
     or p_new_config->>'runtime_bundle_fingerprint_sha256' IS NOT DISTINCT FROM v_old.config->>'runtime_bundle_fingerprint_sha256'
     or (p_new_config - v_excluded_keys) IS DISTINCT FROM (v_old.config - v_excluded_keys) then
    raise exception 'successor changed strategy, safety or provenance contract';
  end if;

  -- All mutations below commit or roll back as ONE SQL transaction.
  update public.paper_series
     set status='technical_closed',updated_at=clock_timestamp()
   where series_id=p_old_series_id and status='active';
  if not found then raise exception 'predecessor close race'; end if;

  insert into public.paper_series(
    series_id,test_id,strategy_revision,started_at,
    target_completed_trades,status,config)
  values(p_new_series_id,p_new_test_id,v_rev,p_cutover_at_utc,20,'active',p_new_config);

  -- Stop H3-001's original-baseline trial in the same transaction. Its
  -- immutable prospective evidence remains tied to the predecessor. No H3-002
  -- is promoted or activated here.
  update public.v3_h3_shadow_status
    set payload = jsonb_set(payload,'{status}',to_jsonb('FROZEN_TECHNICAL_CUTOVER'::text),true)
       || jsonb_build_object('technical_cutover_at_utc',p_cutover_at_utc,
                             'baseline_immutable',true),
        updated_at = clock_timestamp()
    where shadow_candidate_id='V3-H3-SHADOW-001'
      and payload->>'baseline_series_id'=p_old_series_id;
  if not found then raise exception 'H3-001 baseline freeze failed'; end if;

  insert into public.paper_technical_rotations(
    predecessor_series_id,successor_series_id,cutover_at_utc,
    predecessor_release_repo_sha,successor_release_repo_sha,
    predecessor_runtime_sha256,successor_runtime_sha256,
    strategy_fingerprint_sha256,predecessor_outcomes,predecessor_trades,
    predecessor_last_outcome_updated_at,successor_test_id)
  values(p_old_series_id,p_new_series_id,p_cutover_at_utc,
    lower(p_expected_old_release_sha),v_new_sha,
    v_old.config->>'runtime_bundle_fingerprint_sha256',
    p_new_config->>'runtime_bundle_fingerprint_sha256',
    v_old_strategy,v_outcomes,v_trades,v_last_update,p_new_test_id);

  return jsonb_build_object('ok',true,'idempotent',false,
    'predecessor_series_id',p_old_series_id,
    'successor_series_id',p_new_series_id,
    'cutover_at_utc',p_cutover_at_utc,
    'paper_only',true,'real_money_actions',false);
end;
$$;
revoke all on function public.rotate_v2r4_technical_paper(
  text,text,text,timestamptz,jsonb,text,bigint,bigint,timestamptz)
  from public, anon, authenticated;
grant execute on function public.rotate_v2r4_technical_paper(
  text,text,text,timestamptz,jsonb,text,bigint,bigint,timestamptz)
  to service_role;
