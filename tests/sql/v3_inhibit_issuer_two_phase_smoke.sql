-- Disposable-only isolated PostgreSQL issuer contract. NEVER run in Supabase.
\set ON_ERROR_STOP on
create role anon nologin;
create role authenticated nologin;
create role service_role nologin;
create role v3_cas_operator_login nologin;
create role v3_cas_executor nologin;
create role v3_cas_executor_actor nologin;
create role v3_cas_audit_writer nologin;
create role v3_cas_audit_reader nologin;
create role v3_cas_audit_table_owner nologin;
create role v3_cas_audit_reader_actor login noinherit;
create schema v3_cas_audit authorization postgres;
grant usage on schema v3_cas_audit to v3_cas_audit_table_owner; -- already true in original production
create table v3_cas_audit.epoch_v1 (
 epoch_id text primary key, predecessor_series_id text not null,
 expected_rpc text not null, source_sha256 text not null,
 original_fence_sha256 text not null, approved_caller_acl_sha256 text not null,
 next_ordinal bigint not null default 1, sealed boolean not null default false
);
create table v3_cas_audit.intent_v1 (
 epoch_id text not null references v3_cas_audit.epoch_v1(epoch_id),
 ordinal bigint not null,intent_id uuid not null unique,state text not null
);
alter table v3_cas_audit.epoch_v1 owner to v3_cas_audit_table_owner;
alter table v3_cas_audit.intent_v1 owner to v3_cas_audit_table_owner;
insert into v3_cas_audit.epoch_v1(epoch_id,predecessor_series_id,
 expected_rpc,source_sha256,original_fence_sha256,approved_caller_acl_sha256)
values ('V3CAS-AUDIT-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
 'PAPER-V2R4-20261009T110135Z',
 'public.rotate_v2r4_to_v3_experimental_paper',repeat('3',64),
 repeat('4',64),repeat('5',64));

-- Source is loaded as a CI-only copy whose unique FIRST RAISE was replaced.
\i __SOURCE_CI_ONLY__

alter role v3_cas_inhibit_issuer_actor login connection limit 1; -- disposable fixture only

-- Original unauthenticated postgres session must NOT issue a receipt.
do $negative$
begin
 begin
  perform v3_cas_audit.begin_executor_inhibit_v1(
    'V3CAS-AUDIT-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    repeat('3',64),repeat('4',64),repeat('5',64));
  raise exception 'UNAUTHORIZED_INHIBIT_ISSUER_ACCEPTED';
 exception when others then
  if sqlerrm not like '%V3_CAS_INHIBIT_ISSUER_START_SCOPE_HOLD%' then raise; end if;
 end;
end $negative$;

set session authorization v3_cas_inhibit_issuer_actor;
-- A valid hash tuple is not enough if the original epoch has been sealed.
-- The synthetic disposable fixture changes only its own isolated row.
reset session authorization;
update v3_cas_audit.epoch_v1
   set sealed=true
 where epoch_id='V3CAS-AUDIT-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
set session authorization v3_cas_inhibit_issuer_actor;
do $sealed_epoch$
begin
 begin
  perform v3_cas_audit.begin_executor_inhibit_v1(
   'V3CAS-AUDIT-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
   repeat('3',64),repeat('4',64),repeat('5',64));
  raise exception 'SEALED_EPOCH_ISSUER_ACCEPTED';
 exception when others then
  if sqlerrm not like '%V3_CAS_INHIBIT_ISSUER_EPOCH_BINDING_HOLD%' then raise; end if;
 end;
end $sealed_epoch$;
reset session authorization;
update v3_cas_audit.epoch_v1
   set sealed=false
 where epoch_id='V3CAS-AUDIT-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
set session authorization v3_cas_inhibit_issuer_actor;
-- Correctly shaped but wrong source/fence/ACL must not create an inhibit.
do $epoch_mismatch$
declare v_hash text;
begin
 foreach v_hash in array array['source','fence','acl'] loop
  begin
   perform v3_cas_audit.begin_executor_inhibit_v1(
    'V3CAS-AUDIT-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    case when v_hash='source' then repeat('9',64) else repeat('3',64) end,
    case when v_hash='fence' then repeat('9',64) else repeat('4',64) end,
    case when v_hash='acl' then repeat('9',64) else repeat('5',64) end);
   raise exception 'MISMATCHED_EPOCH_INHIBIT_ACCEPTED_%',v_hash;
  exception when others then
   if sqlerrm not like '%V3_CAS_INHIBIT_ISSUER_EPOCH_BINDING_HOLD%' then raise; end if;
  end;
 end loop;
end $epoch_mismatch$;
select v3_cas_audit.begin_executor_inhibit_v1(
  'V3CAS-AUDIT-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  repeat('3',64),repeat('4',64),repeat('5',64));
-- Direct table write must remain unavailable even to this issuer actor.
do $reader_no_table$
begin
 begin
  delete from v3_cas_audit.executor_inhibit_v1;
  raise exception 'UNSCOPED_READER_TABLE_DELETE_ACCEPTED';
 exception when insufficient_privilege then null;
 end;
end $reader_no_table$;
reset session authorization;

do $assert_started$
begin
 if (select count(*) from v3_cas_audit.executor_inhibit_v1
     where native_stop_at_utc is null and acknowledged_at_utc is null
       and receipt_sha256 is null and inhibit_started_at_utc<=clock_timestamp()) <> 1
 then raise exception 'NO_DURABLE_PRESTOP_INHIBIT_START'; end if;
end $assert_started$;

set session authorization v3_cas_inhibit_issuer_actor;
select v3_cas_audit.confirm_executor_inhibit_v1(
 'V3CAS-AUDIT-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
 clock_timestamp(),repeat('7',64));
do $no_replay$
begin
 begin
  perform v3_cas_audit.confirm_executor_inhibit_v1(
   'V3CAS-AUDIT-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
   clock_timestamp(),repeat('8',64));
  raise exception 'REPLAY_INHIBIT_CONFIRM_ACCEPTED';
 exception when others then
  if sqlerrm not like '%V3_CAS_INHIBIT_ISSUER_CONFIRM_REPLAY_OR_TIME_HOLD%' then raise; end if;
 end;
end $no_replay$;
reset session authorization;

do $assert_confirmed$
begin
 if (select count(*) from v3_cas_audit.executor_inhibit_v1
     where receipt_sha256=repeat('7',64)
       and issuer_id='v3_cas_inhibit_issuer_actor'
       and inhibit_started_at_utc<native_stop_at_utc
       and acknowledged_at_utc<valid_through_utc
       and valid_through_utc<=acknowledged_at_utc+interval '5 minutes') <> 1
 then raise exception 'INHIBIT_CONFIRM_NOT_ATOMIC_OR_BOUND'; end if;
end $assert_confirmed$;
-- The exclusively scoped executor may append a conservative UNKNOWN marker
-- before CAS, once. Notebook reader and service_role have NO direct writes.
insert into v3_cas_audit.intent_v1(epoch_id,ordinal,intent_id,state)
values('V3CAS-AUDIT-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',1,
       '123e4567-e89b-42d3-a456-426614174000','PREINVOKE_INTENT');
alter role v3_cas_executor_actor login connection limit 1; -- disposable only
set session authorization v3_cas_executor_actor;
select v3_cas_audit.append_dispatch_unknown_v1(
 'V3CAS-AUDIT-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
 '123e4567-e89b-42d3-a456-426614174000',
 repeat('6',64),repeat('3',64),repeat('4',64));
do $no_attempt_replay$
begin
 begin
  perform v3_cas_audit.append_dispatch_unknown_v1(
   'V3CAS-AUDIT-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
   '123e4567-e89b-42d3-a456-426614174000',
   repeat('6',64),repeat('3',64),repeat('4',64));
  raise exception 'REPLAYED_DISPATCH_UNKNOWN_ACCEPTED';
 exception when unique_violation then null;
 end;
end $no_attempt_replay$;
reset session authorization;
do $verify_unknown$
begin
 if (select count(*) from v3_cas_audit.attempt_v1
       where state='DISPATCH_UNKNOWN'
         and emitter_actor='v3_cas_executor_actor'
         and request_sha256=repeat('6',64))<>1 then
  raise exception 'DURABLE_UNKNOWN_NOT_PERSISTED';
 end if;
end $verify_unknown$;
select 'V3_DISPOSABLE_ISSUER_TWO_PHASE_NEGATIVE_PASS' as gate;
