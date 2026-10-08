-- Focused disposable PostgreSQL CI fixture for the technical cutover function.
-- NEVER execute in a production project. All rows are test-only.
\set ON_ERROR_STOP on
begin;

create role service_role nologin;
create role anon nologin;
create role authenticated nologin;

create table public.paper_series (
  series_id text primary key,
  test_id text not null,
  strategy_revision text not null,
  started_at timestamptz not null,
  target_completed_trades integer not null,
  status text not null default 'active',
  config jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index paper_series_single_active_idx on public.paper_series ((status)) where status='active';
create table public.paper_candidate_outcomes (
  candidate_id text primary key,
  series_id text references public.paper_series(series_id),
  updated_at timestamptz not null default now()
);
create table public.paper_trade_results (
  candidate_id text primary key,
  series_id text references public.paper_series(series_id),
  updated_at timestamptz not null default now()
);
create table public.v3_h3_shadow_status (
  shadow_candidate_id text primary key,
  payload jsonb not null
);

insert into public.paper_series (
  series_id,test_id,strategy_revision,started_at,target_completed_trades,status,config
) values (
  'PAPER-V2R4-20261007T184255Z',
  'PAPER-V2R4-SERIES1-20261007',
  'V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION',
  '2026-10-07T18:42:55Z',20,'active',
  jsonb_build_object(
    'series_id','PAPER-V2R4-20261007T184255Z',
    'test_id','PAPER-V2R4-SERIES1-20261007',
    'predecessor_series_id','PAPER-V2R3-CLEAN-20261001T0925Z',
    'series_started_at_utc','2026-10-07T18:42:55Z',
    'strategy_revision','V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION',
    'enabled',true,'paper_only',true,'real_money_actions_enabled',false,
    'automatic_activation_allowed',false,
    'scout_notional_eur',50,'stage2_notional_eur',50,'target_completed_paper_trades',20,
    'release_decision','APPROVED_PAPER',
    'release_repo_sha','3c6729a6c548d169f56a97f07f75892f37211636',
    'strategy_fingerprint_sha256',repeat('a',64),
    'runtime_bundle_fingerprint_sha256',repeat('b',64),
    'candidate_merge_sha',repeat('d',40)
  )
);
insert into public.paper_candidate_outcomes(candidate_id,series_id)
values ('fixture-1','PAPER-V2R4-20261007T184255Z'),
       ('fixture-2','PAPER-V2R4-20261007T184255Z');
insert into public.v3_h3_shadow_status(shadow_candidate_id,payload)
values ('V3-H3-SHADOW-001','{"baseline_series_id":"PAPER-V2R4-20261007T184255Z"}');

\ir ../../supabase/v2r4-technical-paper-rotation-20261009.sql

do $fixture$
declare
  stamp timestamptz := date_trunc('second', clock_timestamp() - interval '20 seconds');
  new_sid text;
  new_tid text;
  cfg jsonb;
  old_count bigint;
  old_update timestamptz;
  rec jsonb;
  exception_seen boolean;
  pre_status text;
begin
  new_sid := 'PAPER-V2R4-' || to_char(stamp at time zone 'UTC','YYYYMMDD"T"HH24MISS"Z"');
  new_tid := 'PAPER-V2R4-TECH-' || to_char(stamp at time zone 'UTC','YYYYMMDD');
  select count(*),max(updated_at) into old_count,old_update
    from public.paper_candidate_outcomes where series_id='PAPER-V2R4-20261007T184255Z';
  select config || jsonb_build_object(
    'series_id',new_sid,'test_id',new_tid,
    'predecessor_series_id','PAPER-V2R4-20261007T184255Z',
    'series_started_at_utc',to_char(stamp at time zone 'UTC','YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    'technical_change_id','V2R4_TECHNICAL_RECOVERY_20261009',
    'technical_change_approved',true,
    'release_repo_sha','927e8c8d4455c28bb0cb230e86eb1d83bc09576f',
    'runtime_bundle_fingerprint_sha256',repeat('c',64)
  ) into cfg
  from public.paper_series where series_id='PAPER-V2R4-20261007T184255Z';

  -- Fail closed: safety deviation may not close predecessor or insert successor.
  exception_seen := false;
  begin
    perform public.rotate_v2r4_technical_paper(
      'PAPER-V2R4-20261007T184255Z',new_sid,new_tid,stamp,
      cfg || '{"real_money_actions_enabled":true}'::jsonb,
      '3c6729a6c548d169f56a97f07f75892f37211636',old_count,0,old_update
    );
  exception when others then exception_seen := true;
  end;
  if not exception_seen or (select count(*) from public.paper_series where status='active') <> 1 then
    raise exception 'unsafe input accepted or predecessor damaged';
  end if;

  -- Fail closed: a mismatched final cloud evidence count cannot rotate.
  exception_seen := false;
  begin
    perform public.rotate_v2r4_technical_paper(
      'PAPER-V2R4-20261007T184255Z',new_sid,new_tid,stamp,cfg,
      '3c6729a6c548d169f56a97f07f75892f37211636',old_count+1,0,old_update
    );
  exception when others then exception_seen := true;
  end;
  if not exception_seen or
    (select status from public.paper_series where series_id='PAPER-V2R4-20261007T184255Z') <> 'active' then
    raise exception 'evidence count mismatch accepted';
  end if;

  -- Happy path, one and only one active successor and immutable predecessor.
  rec := public.rotate_v2r4_technical_paper(
    'PAPER-V2R4-20261007T184255Z',new_sid,new_tid,stamp,cfg,
    '3c6729a6c548d169f56a97f07f75892f37211636',old_count,0,old_update
  );
  if rec->>'idempotent' <> 'false'
      or (select count(*) from public.paper_series where status='active') <> 1
      or (select status from public.paper_series where series_id='PAPER-V2R4-20261007T184255Z') <> 'technical_closed'
      or (select status from public.paper_series where series_id=new_sid) <> 'active'
      or (select count(*) from public.paper_technical_rotations) <> 1 then
    raise exception 'atomic rotate invariants failed';
  end if;

  -- Idempotent retry with identical manifest cannot insert or mutate more rows.
  rec := public.rotate_v2r4_technical_paper(
    'PAPER-V2R4-20261007T184255Z',new_sid,new_tid,stamp,cfg,
    '3c6729a6c548d169f56a97f07f75892f37211636',old_count,0,old_update
  );
  if rec->>'idempotent' <> 'true' or
     (select count(*) from public.paper_technical_rotations) <> 1 then
    raise exception 'idempotency failed';
  end if;

  -- Conflicting replay (same series, different config) is rejected.
  exception_seen := false;
  begin
    perform public.rotate_v2r4_technical_paper(
      'PAPER-V2R4-20261007T184255Z',new_sid,new_tid,stamp,
      cfg || '{"scout_notional_eur":75}'::jsonb,
      '3c6729a6c548d169f56a97f07f75892f37211636',old_count,0,old_update
    );
  exception when others then exception_seen := true;
  end;
  if not exception_seen then raise exception 'conflicting replay accepted'; end if;
  raise notice 'TECHNICAL_ROTATION_SQL_ATOMIC_SMOKE_PASS';
end;
$fixture$;

rollback;
