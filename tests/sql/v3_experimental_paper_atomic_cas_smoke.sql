-- Disposable PostgreSQL 17 V3 experimental PAPER CAS test.
-- Executed only in an offline/no-port Docker container on CAS SQL file changes
-- inside existing architecture CI. No Supabase project is contacted.
-- NEVER run on Supabase or against original Mini-PC / production Cloud.
-- Also verify a same-count original trade version drift blocks real atomic CAS.
-- Synthetic evidence/approval booleans below exist ONLY in this CI fixture;
-- they are not host physical release proof, a permission, or a deployment.
\set ON_ERROR_STOP on
begin;

create role service_role nologin;
create role anon nologin;
create role authenticated nologin;
-- NOLOGIN roles from original source-only audit candidate. Simulate
-- PostgreSQL 17 Supabase non-superuser CREATEROLE's unavoidable restricted
-- creator-admin membership even though Docker postgres is a real superuser.
-- SET FALSE / INHERIT FALSE means no immediate EXECUTE authority.
create role v3_cas_executor nologin noinherit nobypassrls;
create role v3_cas_audit_writer nologin noinherit nobypassrls;
create role v3_cas_audit_reader nologin noinherit nobypassrls;
grant v3_cas_executor to postgres with admin true, set false, inherit false;
grant v3_cas_audit_writer to postgres with admin true, set false, inherit false;
grant v3_cas_audit_reader to postgres with admin true, set false, inherit false;

create table public.paper_series (
  series_id text primary key, test_id text not null,
  strategy_revision text not null, started_at timestamptz not null,
  target_completed_trades integer not null, status text not null,
  config jsonb not null, updated_at timestamptz not null default now()
);
create unique index paper_series_single_active_idx
  on public.paper_series ((status)) where status='active';
create table public.paper_candidate_outcomes (
  candidate_id text primary key,
  series_id text not null references public.paper_series(series_id),
  followup jsonb, updated_at timestamptz not null default now()
);
create table public.paper_trade_results (
  candidate_id text primary key,
  series_id text not null references public.paper_series(series_id),
  status text not null, payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

insert into public.paper_series(
  series_id,test_id,strategy_revision,started_at,target_completed_trades,status,config
) values (
 'PAPER-V2R4-20261009T110135Z',
 'PAPER-V2R4-SERIES1-20261009',
 'V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION',
 '2026-10-09T11:01:35Z',20,'active',
 jsonb_build_object(
   'release_repo_sha',repeat('a',40),
   'strategy_fingerprint_sha256',repeat('b',64),
   'runtime_bundle_fingerprint_sha256',repeat('c',64),
   'paper_only',true,
   'real_money_actions_enabled',false,
   'automatic_activation_allowed',false
 )
);
insert into public.paper_candidate_outcomes(candidate_id,series_id,followup)
values ('preserve-old-wait','PAPER-V2R4-20261009T110135Z',
        '{"horizon6h":"PENDING"}');
insert into public.paper_trade_results(candidate_id,series_id,status,payload)
values ('preserve-old-open-trade','PAPER-V2R4-20261009T110135Z',
        'OPEN','{"stages":["SCOUT"]}');

-- This inactive SQL file is loaded ONLY in disposable PostgreSQL.
\ir ../../supabase/v3-experimental-paper-atomic-cas-INACTIVE-20261013.sql

-- Exercise true transaction rollback on INSERT after the predecessor UPDATE,
-- not just textual acceptance of a BEGIN/END statement.
create function public.reject_v3_fixture_insert() returns trigger
language plpgsql as $reject$ begin
 if new.series_id like 'PAPER-V3-%' then
   raise exception 'test_only_force_insert_abort';
 end if;
 return new;
end; $reject$;
create trigger reject_v3_insert_ci_only before insert on public.paper_series
for each row execute function public.reject_v3_fixture_insert();

do $fixture$
declare
  old_id text := 'PAPER-V2R4-20261009T110135Z';
  old_sha text := repeat('a',40);
  strategy_sha text := repeat('b',64);
  runtime_sha text := repeat('c',64);
  new_sha text := repeat('d',40);
  bundle_sha text := repeat('e',64);
  new_strategy_sha text := repeat('f',64);
  stamp timestamptz := date_trunc('second',clock_timestamp()-interval '20 seconds');
  new_id text;
  new_test text := 'PAPER-V3-DISPOSABLE-SQL-CI-001';
  new_rev text := 'V3-EXPERIMENTAL-PAPER-CI-ONLY';
  cfg jsonb;
  n_out bigint;
  n_trade bigint;
  last_out timestamptz;
  last_trade timestamptz;
  caught boolean;
  reply jsonb;
  fn text := 'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)';
begin
  new_id := 'PAPER-V3-' || to_char(stamp at time zone 'UTC',
             'YYYYMMDD"T"HH24MISS"Z"');
  select count(*),max(updated_at) into n_out,last_out
  from public.paper_candidate_outcomes where series_id=old_id;
  select count(*),max(updated_at) into n_trade,last_trade
  from public.paper_trade_results where series_id=old_id;
  cfg := jsonb_build_object(
    'series_id',new_id,'test_id',new_test,
    'strategy_revision',new_rev,'predecessor_series_id',old_id,
    'release_repo_sha',new_sha,
    'runtime_bundle_fingerprint_sha256',bundle_sha,
    'strategy_fingerprint_sha256',new_strategy_sha,
    'series_started_at_utc',to_char(stamp at time zone 'UTC',
          'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    'paper_phase','EXPERIMENTAL_PAPER_ONLY',
    'explicit_human_release_decision','APPROVED_EXPERIMENTAL_PAPER',
    'real_money_actions_enabled',false,
    'automatic_activation_allowed',false,'paper_only',true,'enabled',true,
    'scout_notional_eur',50,'stage2_notional_eur',50,
    'target_completed_paper_trades',20,
    'old_followup_owner_preserved',true,
    'physical_v2r4_writer_fence_verified',true,
    'supervisor_old_intake_rearm_blocked',true,
    'independent_six_e2e_proofs_verified',true
  );

  -- EXECUTE must be absent for both public and live relay identities.
  if has_function_privilege('anon',fn,'EXECUTE')
     or has_function_privilege('authenticated',fn,'EXECUTE')
     or has_function_privilege('service_role',fn,'EXECUTE')
     or has_function_privilege('v3_cas_audit_writer',fn,'EXECUTE')
     or has_function_privilege('v3_cas_audit_reader',fn,'EXECUTE')
     or not has_function_privilege('v3_cas_executor',fn,'EXECUTE')
     or (select count(*) from pg_catalog.pg_auth_members m
         join pg_catalog.pg_roles r on r.oid=m.roleid
         where r.rolname='v3_cas_executor') <> 1
     or not exists (
        select 1 from pg_catalog.pg_auth_members m
        join pg_catalog.pg_roles r on r.oid=m.roleid
        join pg_catalog.pg_roles a on a.oid=m.member
        where r.rolname='v3_cas_executor'
          and a.rolname='postgres'
          and m.admin_option and not m.set_option and not m.inherit_option)
     or (select count(*) from pg_catalog.pg_roles
         where rolname='v3_cas_executor' and not rolcanlogin
           and not rolbypassrls and not rolsuper and not rolinherit) <> 1 then
    raise exception 'V3 inactive function CAS exclusive executor ACL mismatch';
  end if;

  -- Unsafe real-money successor must not pass even with CI synthetic permits.
  caught := false;
  begin
    perform public.rotate_v2r4_to_v3_experimental_paper(
      old_id,old_sha,strategy_sha,runtime_sha,n_out,n_trade,last_out,last_trade,
      new_id,new_test,new_rev,stamp,
      cfg||'{"real_money_actions_enabled":true}'::jsonb,
      new_sha,bundle_sha,new_strategy_sha);
  exception when others then caught := true; end;
  if not caught then raise exception 'real-money config accepted'; end if;

  -- Drift in actual old-series Cloud count must fail closed.
  caught := false;
  begin
    perform public.rotate_v2r4_to_v3_experimental_paper(
      old_id,old_sha,strategy_sha,runtime_sha,n_out+1,n_trade,last_out,last_trade,
      new_id,new_test,new_rev,stamp,cfg,
      new_sha,bundle_sha,new_strategy_sha);
  exception when others then caught := true; end;
  if not caught then raise exception 'Cloud evidence-count drift accepted'; end if;

  -- Do not fake historic V2R4 ownership, or accept an absent No-Rearm proof.
  caught := false;
  begin
    perform public.rotate_v2r4_to_v3_experimental_paper(
      old_id,repeat('9',40),strategy_sha,runtime_sha,n_out,n_trade,last_out,last_trade,
      new_id,new_test,new_rev,stamp,cfg,
      new_sha,bundle_sha,new_strategy_sha);
  exception when others then caught := true; end;
  if not caught then raise exception 'wrong original source SHA accepted'; end if;

  caught := false;
  begin
    perform public.rotate_v2r4_to_v3_experimental_paper(
      old_id,old_sha,strategy_sha,runtime_sha,n_out,n_trade,last_out,last_trade,
      new_id,new_test,new_rev,stamp,
      cfg||'{"supervisor_old_intake_rearm_blocked":false}'::jsonb,
      new_sha,bundle_sha,new_strategy_sha);
  exception when others then caught := true; end;
  if not caught then raise exception 'No-Rearm predecessor guard bypassed'; end if;

  -- A closed original trade can retain the SAME row count. An outdated
  -- trade version must fail before changing the active Paper series; the
  -- exception subtransaction also restores this disposable test's old row.
  caught := false;
  begin
    update public.paper_trade_results
       set status='CLOSED',updated_at=last_trade+interval '5 seconds'
     where candidate_id='preserve-old-open-trade';
    perform public.rotate_v2r4_to_v3_experimental_paper(
      old_id,old_sha,strategy_sha,runtime_sha,n_out,n_trade,last_out,last_trade,
      new_id,new_test,new_rev,stamp,cfg,new_sha,bundle_sha,new_strategy_sha);
  exception when others then
    if sqlerrm like '%fresh old Cloud outcome/trade checkpoint drift%' then
      caught := true;
    else
      raise;
    end if;
  end;
  if not caught
     or (select count(*) from public.paper_trade_results
         where series_id=old_id) <> n_trade
     or (select status from public.paper_trade_results
         where candidate_id='preserve-old-open-trade') <> 'OPEN'
     or (select max(updated_at) from public.paper_trade_results
         where series_id=old_id) is distinct from last_trade then
    raise exception 'stale same-count old trade update accepted';
  end if;

  -- The synthetic trigger forces the exact dangerous partial-failure moment:
  -- old series UPDATED closed, new INSERT rejects. It MUST roll back both.
  caught := false;
  begin
    perform public.rotate_v2r4_to_v3_experimental_paper(
      old_id,old_sha,strategy_sha,runtime_sha,n_out,n_trade,last_out,last_trade,
      new_id,new_test,new_rev,stamp,cfg,
      new_sha,bundle_sha,new_strategy_sha);
  exception when others then caught := true; end;
  if not caught
     or (select status from public.paper_series where series_id=old_id) <> 'active'
     or (select count(*) from public.paper_series where status='active') <> 1
     or exists(select 1 from public.paper_series where series_id=new_id) then
    raise exception 'old-series closure was not rolled back after new insert failure';
  end if;

  -- The trigger is fixture-only and is removed before valid/disposable
  -- positive tests. The following subtransactions always roll back their
  -- synthetic changes; the original old series stays ACTIVE until the
  -- final, separately checked successful test below.
  execute 'drop trigger reject_v3_insert_ci_only on public.paper_series';

  -- The currently observed V2R4 Paper strategy may have ZERO trades.
  -- A zero-row original trade snapshot MUST use count=0 and max=NULL;
  -- both Postgres series rows must atomically change, old WAIT original
  -- outcomes must survive, and the test must revert before the next case.
  caught := false;
  begin
    delete from public.paper_trade_results
     where candidate_id='preserve-old-open-trade';
    reply := public.rotate_v2r4_to_v3_experimental_paper(
      old_id,old_sha,strategy_sha,runtime_sha,n_out,0,last_out,null,
      new_id,new_test,new_rev,stamp,cfg,
      new_sha,bundle_sha,new_strategy_sha
    );
    if reply->>'ok' <> 'true'
       or (reply->>'predecessor_trade_count')::bigint <> 0
       or (select count(*) from public.paper_series where status='active') <> 1
       or (select status from public.paper_series where series_id=old_id)
          <> 'strategy_cutover_closed'
       or (select status from public.paper_series where series_id=new_id)
          <> 'active'
       or (select count(*) from public.paper_candidate_outcomes
            where series_id=old_id) <> n_out
       or (select followup->>'horizon6h' from public.paper_candidate_outcomes
            where candidate_id='preserve-old-wait') <> 'PENDING' then
      raise exception 'zero-trade SQL CAS corrupted original Paper rows';
    end if;
    -- A deliberate exception restores this disposable subtransaction,
    -- not a production rollback/rearm procedure.
    raise exception 'FIXTURE_RESTORE_ZERO_TRADE_CASE';
  exception when others then
    if sqlerrm = 'FIXTURE_RESTORE_ZERO_TRADE_CASE' then
      caught := true;
    else
      raise;
    end if;
  end;
  if not caught
     or (select status from public.paper_series where series_id=old_id) <> 'active'
     or (select count(*) from public.paper_series where status='active') <> 1
     or exists(select 1 from public.paper_series where series_id=new_id)
     or (select count(*) from public.paper_trade_results where series_id=old_id)
        <> n_trade then
    raise exception 'zero-trade disposable CAS did not roll back to original';
  end if;

  -- Drift in the original candidate clock with an UNCHANGED candidate
  -- count must also abort CAS before it closes the original Paper series.
  -- This exercises the actual table-lock and checkpoint, not a string
  -- comparison in a source-only policy mock.
  caught := false;
  begin
    update public.paper_candidate_outcomes
       set updated_at=last_out+interval '5 seconds'
     where candidate_id='preserve-old-wait';
    perform public.rotate_v2r4_to_v3_experimental_paper(
      old_id,old_sha,strategy_sha,runtime_sha,n_out,n_trade,last_out,last_trade,
      new_id,new_test,new_rev,stamp,cfg,
      new_sha,bundle_sha,new_strategy_sha);
  exception when others then
    if sqlerrm like '%fresh old Cloud outcome/trade checkpoint drift%' then
      caught := true;
    else
      raise;
    end if;
  end;
  if not caught
     or (select max(updated_at) from public.paper_candidate_outcomes
         where series_id=old_id) is distinct from last_out
     or (select status from public.paper_series where series_id=old_id) <> 'active'
     or exists(select 1 from public.paper_series where series_id=new_id) then
    raise exception 'stale same-count old candidate update accepted';
  end if;

  -- Independent source-only negative cases: user approval, protected old
  -- aftercare and six E2E attestation flags cannot be omitted or relaxed
  -- by the future CAS caller, even when its V2R4 snapshot is otherwise exact.
  caught := false;
  begin
    perform public.rotate_v2r4_to_v3_experimental_paper(
      old_id,old_sha,strategy_sha,runtime_sha,n_out,n_trade,last_out,last_trade,
      new_id,new_test,new_rev,stamp,
      cfg||'{"explicit_human_release_decision":"NOT_APPROVED"}'::jsonb,
      new_sha,bundle_sha,new_strategy_sha);
  exception when others then
    if sqlerrm like '%fails explicit bounded Paper-only release contract%' then
      caught := true;
    else raise;
    end if;
  end;
  if not caught then raise exception 'missing user release accepted'; end if;

  caught := false;
  begin
    perform public.rotate_v2r4_to_v3_experimental_paper(
      old_id,old_sha,strategy_sha,runtime_sha,n_out,n_trade,last_out,last_trade,
      new_id,new_test,new_rev,stamp,
      cfg||'{"old_followup_owner_preserved":false}'::jsonb,
      new_sha,bundle_sha,new_strategy_sha);
  exception when others then
    if sqlerrm like '%fails explicit bounded Paper-only release contract%' then
      caught := true;
    else raise;
    end if;
  end;
  if not caught then raise exception 'old aftercare removal accepted'; end if;

  caught := false;
  begin
    perform public.rotate_v2r4_to_v3_experimental_paper(
      old_id,old_sha,strategy_sha,runtime_sha,n_out,n_trade,last_out,last_trade,
      new_id,new_test,new_rev,stamp,
      cfg||'{"independent_six_e2e_proofs_verified":false}'::jsonb,
      new_sha,bundle_sha,new_strategy_sha);
  exception when others then
    if sqlerrm like '%fails explicit bounded Paper-only release contract%' then
      caught := true;
    else raise;
    end if;
  end;
  if not caught then raise exception 'six-proof false claim accepted'; end if;

  reply := public.rotate_v2r4_to_v3_experimental_paper(
    old_id,old_sha,strategy_sha,runtime_sha,n_out,n_trade,last_out,last_trade,
    new_id,new_test,new_rev,stamp,cfg,new_sha,bundle_sha,new_strategy_sha
  );
  if reply->>'ok' <> 'true'
     or reply->>'paper_only' <> 'true'
     or reply->>'real_money_actions' <> 'false'
     or (select status from public.paper_series where series_id=old_id)
        <> 'strategy_cutover_closed'
     or (select count(*) from public.paper_series where status='active') <> 1
     or (select status from public.paper_series where series_id=new_id) <> 'active'
     or (select count(*) from public.paper_candidate_outcomes where series_id=old_id) <> n_out
     or (select count(*) from public.paper_trade_results where series_id=old_id) <> n_trade
     or (select followup->>'horizon6h' from public.paper_candidate_outcomes
         where candidate_id='preserve-old-wait') <> 'PENDING'
     or (select status from public.paper_trade_results
         where candidate_id='preserve-old-open-trade') <> 'OPEN' then
    raise exception 'V3 disposable atomic transfer/preservation failed';
  end if;

  -- No automatic retry after uncertain acknowledgement. A replay must refuse
  -- the already closed predecessor and not create a second active Paper series.
  caught := false;
  begin
    perform public.rotate_v2r4_to_v3_experimental_paper(
      old_id,old_sha,strategy_sha,runtime_sha,n_out,n_trade,last_out,last_trade,
      new_id,new_test,new_rev,stamp,cfg,new_sha,bundle_sha,new_strategy_sha
    );
  exception when others then caught := true; end;
  if not caught
    or (select count(*) from public.paper_series where status='active') <> 1
    or (select count(*) from public.paper_series where series_id=new_id) <> 1 then
    raise exception 'duplicate V3 CAS replay must fail closed';
  end if;
  raise notice 'V3_DISPOSABLE_POSTGRES_ATOMIC_CAS_FAILCLOSED_AND_ROLLBACK_PASS';
end;
$fixture$;

-- No fixture tables, roles, function, or trigger survive this transaction.
rollback;
