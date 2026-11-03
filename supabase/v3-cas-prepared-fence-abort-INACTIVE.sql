-- V3 #99 / PR515 PREPARED-fence abort receipt. Existing v3_cas_audit OWNER.
-- SOURCE-ONLY, not a migration, not physical marker cancellation or CAS authority.
-- The FIRST effectful statement hardlocks production deployment.
BEGIN;
DO $locked$ BEGIN
 RAISE EXCEPTION 'V3_PREPARED_ABORT_SOURCE_INACTIVE_NO_PRODUCTION_INSTALL';
END $locked$;
DO $pre$ BEGIN
 IF current_user <> 'postgres'
    OR to_regclass('v3_cas_audit.epoch_v1') IS NULL
    OR to_regclass('v3_cas_audit.intent_v1') IS NULL
    OR to_regclass('v3_cas_audit.attempt_v1') IS NULL
    OR to_regclass('v3_cas_audit.executor_inhibit_v1') IS NULL
    OR to_regclass('v3_cas_audit.prepared_fence_abort_v1') IS NOT NULL
    OR to_regprocedure('v3_cas_audit.begin_executor_inhibit_v1(text,text,text,text)') IS NULL
    OR (SELECT count(*) FROM pg_roles WHERE rolname='v3_cas_inhibit_issuer_actor'
         AND rolcanlogin AND NOT rolbypassrls AND NOT rolsuper) <> 1
    OR (SELECT count(*) FROM pg_roles WHERE rolname='v3_cas_executor_actor'
         AND NOT rolcanlogin AND NOT rolbypassrls) <> 1
 THEN RAISE EXCEPTION 'V3_PREPARED_ABORT_OWNER_PREFLIGHT_HOLD'; END IF;
END $pre$;
-- Reuse original Stage2 temporary owner escrow; never add an executor/credential.
GRANT CREATE ON SCHEMA v3_cas_audit TO v3_cas_audit_table_owner;
GRANT v3_cas_audit_table_owner TO postgres WITH ADMIN FALSE, INHERIT FALSE, SET TRUE;
SET ROLE v3_cas_audit_table_owner;
-- Existing Stage2 epoch/intent FORCE-RLS rules omit their own NOLOGIN table
-- owner. Without THESE narrowly named policies the existing issuer's
-- SECURITY DEFINER epoch read silently sees zero rows, and checking for
-- absent intents could falsely report zero. Do not change any actor grants.
CREATE POLICY v3_cas_epoch_owner_abort_read_v1 ON v3_cas_audit.epoch_v1
 FOR SELECT TO v3_cas_audit_table_owner USING(true);
CREATE POLICY v3_cas_epoch_owner_abort_update_v1 ON v3_cas_audit.epoch_v1
 FOR UPDATE TO v3_cas_audit_table_owner USING(true) WITH CHECK(true);
CREATE POLICY v3_cas_intent_owner_abort_read_v1 ON v3_cas_audit.intent_v1
 FOR SELECT TO v3_cas_audit_table_owner USING(true);
CREATE TABLE v3_cas_audit.prepared_fence_abort_v1 (
 epoch_id text PRIMARY KEY REFERENCES v3_cas_audit.epoch_v1(epoch_id),
 source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[a-f0-9]{64}$'),
 prepared_fence_sha256 text NOT NULL CHECK (prepared_fence_sha256 ~ '^[a-f0-9]{64}$'),
 caller_acl_sha256 text NOT NULL CHECK (caller_acl_sha256 ~ '^[a-f0-9]{64}$'),
 issuer_actor text NOT NULL CHECK (issuer_actor='v3_cas_inhibit_issuer_actor'),
 receipt_sha256 text NOT NULL UNIQUE CHECK (receipt_sha256 ~ '^[a-f0-9]{64}$'),
 state text NOT NULL CHECK (state='ABORT_RECORDED_NOT_RELEASED'),
 created_at_utc timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE v3_cas_audit.prepared_fence_abort_v1 ENABLE ROW LEVEL SECURITY;
ALTER TABLE v3_cas_audit.prepared_fence_abort_v1 FORCE ROW LEVEL SECURITY;
CREATE POLICY v3_prepared_abort_owner_only_v1 ON v3_cas_audit.prepared_fence_abort_v1
 FOR ALL TO v3_cas_audit_table_owner USING(true) WITH CHECK(true);
REVOKE ALL ON v3_cas_audit.prepared_fence_abort_v1
 FROM PUBLIC,anon,authenticated,service_role,v3_cas_operator_login,
 v3_cas_executor,v3_cas_executor_actor,v3_cas_audit_writer,
 v3_cas_audit_writer_actor,v3_cas_audit_reader,v3_cas_audit_reader_actor,
 v3_cas_inhibit_issuer_actor;
-- Reuse the existing independent read-only CAS actor; no new login, writer or
-- service role. A terminal abort without an external Reader readback cannot
-- safely authorize any originalhost marker-only cancellation.
CREATE POLICY v3_prepared_abort_reader_select_v1
 ON v3_cas_audit.prepared_fence_abort_v1
 FOR SELECT TO v3_cas_audit_reader USING (true);
GRANT SELECT ON v3_cas_audit.prepared_fence_abort_v1 TO v3_cas_audit_reader;
-- Exact issuer, unsealed zero-intent epoch, prior independent inhibit and
-- NO native STOP: append once, never delete or imply permission to rearm.
CREATE FUNCTION v3_cas_audit.record_prepared_fence_abort_v1(
 p_epoch text,p_source text,p_fence text,p_acl text,p_receipt text)
RETURNS timestamptz LANGUAGE plpgsql SECURITY DEFINER
SET search_path='pg_catalog','v3_cas_audit'
AS $fn$
DECLARE result_at timestamptz;
BEGIN
 IF session_user <> 'v3_cas_inhibit_issuer_actor'
    OR p_epoch !~ '^V3CAS-AUDIT-[a-f0-9]{32}$'
    OR p_source !~ '^[a-f0-9]{64}$'
    OR p_fence !~ '^[a-f0-9]{64}$'
    OR p_acl !~ '^[a-f0-9]{64}$'
    OR p_receipt !~ '^[a-f0-9]{64}$'
    OR (SELECT rolcanlogin FROM pg_roles WHERE rolname='v3_cas_executor_actor') IS DISTINCT FROM FALSE
    OR (SELECT rolcanlogin FROM pg_roles WHERE rolname='v3_cas_executor') IS DISTINCT FROM FALSE
    OR to_regprocedure('public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)') IS NOT NULL
    -- This private SECURITY DEFINER cannot infer public-series custody.
    -- A separately authenticated original Cloud reader must bind series truth.
 THEN RAISE EXCEPTION 'V3_PREPARED_ABORT_CAS_OR_ACTOR_HOLD'; END IF;
 -- Serialize this record with the original epoch writer. A database snapshot
 -- alone still cannot attest complete external privileged/host history.
 PERFORM 1 FROM v3_cas_audit.epoch_v1 e
 WHERE e.epoch_id=p_epoch AND NOT e.sealed AND e.next_ordinal=1
  AND e.predecessor_series_id='PAPER-V2R4-20261009T110135Z'
  AND e.source_sha256=p_source AND e.original_fence_sha256=p_fence
  AND e.approved_caller_acl_sha256=p_acl
 FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'V3_PREPARED_ABORT_EPOCH_HOLD'; END IF;
 IF EXISTS(SELECT 1 FROM v3_cas_audit.intent_v1 WHERE epoch_id=p_epoch)
    OR EXISTS(SELECT 1 FROM v3_cas_audit.attempt_v1 WHERE epoch_id=p_epoch)
    OR NOT EXISTS(SELECT 1 FROM v3_cas_audit.executor_inhibit_v1 i
       WHERE i.epoch_id=p_epoch AND i.source_sha256=p_source
         AND i.original_fence_sha256=p_fence AND i.caller_acl_sha256=p_acl
         AND i.state='INHIBITED' AND i.issuer_id='v3_cas_inhibit_issuer_actor'
         AND i.native_stop_at_utc IS NULL AND i.acknowledged_at_utc IS NULL)
 THEN RAISE EXCEPTION 'V3_PREPARED_ABORT_INTENT_OR_ISSUER_HOLD'; END IF;
 INSERT INTO v3_cas_audit.prepared_fence_abort_v1
  (epoch_id,source_sha256,prepared_fence_sha256,caller_acl_sha256,
   issuer_actor,receipt_sha256,state)
 VALUES(p_epoch,p_source,p_fence,p_acl,'v3_cas_inhibit_issuer_actor',
   p_receipt,'ABORT_RECORDED_NOT_RELEASED')
 RETURNING created_at_utc INTO result_at;
 RETURN result_at;
END $fn$;
REVOKE ALL ON FUNCTION v3_cas_audit.record_prepared_fence_abort_v1(text,text,text,text,text)
 FROM PUBLIC,anon,authenticated,service_role;
GRANT EXECUTE ON FUNCTION v3_cas_audit.record_prepared_fence_abort_v1(text,text,text,text,text)
 TO v3_cas_inhibit_issuer_actor;
-- Prospective, independently authenticated COMMITTED pre-STOP issuer readback.
-- Source-only: the FIRST effectful SQL statement still unconditionally RAISES.
-- Reuses the existing NOLOGIN audit owner and already enrolled Reader actor.
-- Must never be interpreted as a release or continuous UNKNOWN-history custody.
CREATE FUNCTION v3_cas_audit.read_committed_pre_stop_inhibit_v1()
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path='pg_catalog','v3_cas_audit'
AS $read$
DECLARE v_result jsonb;
BEGIN
 IF session_user <> 'v3_cas_audit_reader_actor'
    OR pg_catalog.current_setting('role',true) <> 'v3_cas_audit_reader'
    OR (SELECT rolcanlogin FROM pg_catalog.pg_roles
        WHERE rolname='v3_cas_executor_actor') IS DISTINCT FROM FALSE
    OR (SELECT rolcanlogin FROM pg_catalog.pg_roles
        WHERE rolname='v3_cas_executor') IS DISTINCT FROM FALSE
    -- NOLOGIN prevents new logins; it does not terminate an earlier session.
    OR EXISTS (SELECT 1 FROM pg_catalog.pg_stat_activity
               WHERE usename IN ('v3_cas_executor_actor','v3_cas_executor'))
    OR (SELECT count(*) FROM v3_cas_audit.epoch_v1) <> 1
    OR (SELECT count(*) FROM v3_cas_audit.executor_inhibit_v1) <> 1
    OR (SELECT count(*) FROM v3_cas_audit.intent_v1) <> 0
    OR (SELECT count(*) FROM v3_cas_audit.attempt_v1) <> 0
    OR (SELECT count(*) FROM v3_cas_audit.prepared_fence_abort_v1) <> 0
    OR to_regprocedure(
      'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
      ) IS NOT NULL
 THEN RAISE EXCEPTION 'V3_ISSUER_PRESTOP_READER_HOLD'; END IF;
 SELECT pg_catalog.jsonb_build_object(
  'kind','V3_CAS_ISSUER_COMMITTED_PRESTOP_READER_V1',
  'observed_at_utc',pg_catalog.to_char(
    pg_catalog.clock_timestamp() AT TIME ZONE 'UTC',
    'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
  'actor',session_user,'requested_role','v3_cas_audit_reader',
  'epoch_id',i.epoch_id,'source_sha256',i.source_sha256,
  'original_fence_sha256',i.original_fence_sha256,
  'caller_acl_sha256',i.caller_acl_sha256,
  'issuer_actor',i.issuer_id,
  'inhibit_started_at_utc',pg_catalog.to_char(
    i.inhibit_started_at_utc AT TIME ZONE 'UTC',
    'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
  'state',i.state,'native_stop_done',false,
  'unknown_count',0,'cas_or_paper_authorized',false
 ) INTO v_result
 FROM v3_cas_audit.executor_inhibit_v1 i
 JOIN v3_cas_audit.epoch_v1 e ON e.epoch_id=i.epoch_id
 WHERE NOT e.sealed AND e.next_ordinal=1
   AND e.predecessor_series_id='PAPER-V2R4-20261009T110135Z'
   AND e.source_sha256=i.source_sha256
   AND e.original_fence_sha256=i.original_fence_sha256
   AND e.approved_caller_acl_sha256=i.caller_acl_sha256
   AND i.state='INHIBITED'
   AND i.issuer_id='v3_cas_inhibit_issuer_actor'
   AND i.native_stop_at_utc IS NULL
   AND i.acknowledged_at_utc IS NULL
   AND i.receipt_sha256 IS NULL;
 IF v_result IS NULL THEN
  RAISE EXCEPTION 'V3_ISSUER_PRESTOP_SOURCE_OR_STATE_HOLD';
 END IF;
 RETURN v_result;
END $read$;
REVOKE ALL ON FUNCTION v3_cas_audit.read_committed_pre_stop_inhibit_v1()
 FROM PUBLIC,anon,authenticated,service_role,
      v3_cas_inhibit_issuer_actor,v3_cas_executor_actor,
      v3_cas_audit_writer_actor,v3_cas_audit_reader_actor;
GRANT EXECUTE ON FUNCTION v3_cas_audit.read_committed_pre_stop_inhibit_v1()
 TO v3_cas_audit_reader;
-- A terminal abort must also prevent *future* intent/UNKNOWN inserts through
-- the existing append function or any direct privileged insert path. Serialize
-- against the same epoch row lock used by the abort append: no TOCTOU gap.
CREATE FUNCTION v3_cas_audit.reject_aborted_epoch_dispatch_v1()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path='pg_catalog','v3_cas_audit'
AS $deny$
BEGIN
 PERFORM 1 FROM v3_cas_audit.epoch_v1
  WHERE epoch_id=NEW.epoch_id FOR SHARE;
 IF NOT FOUND OR EXISTS (
   SELECT 1 FROM v3_cas_audit.prepared_fence_abort_v1
    WHERE epoch_id=NEW.epoch_id
 ) THEN RAISE EXCEPTION 'V3_ABORTED_EPOCH_CANNOT_APPEND_INTENT_OR_ATTEMPT'; END IF;
 RETURN NEW;
END $deny$;
CREATE TRIGGER v3_reject_aborted_intent_insert_v1
 BEFORE INSERT ON v3_cas_audit.intent_v1
 FOR EACH ROW EXECUTE FUNCTION v3_cas_audit.reject_aborted_epoch_dispatch_v1();
CREATE TRIGGER v3_reject_aborted_attempt_insert_v1
 BEFORE INSERT ON v3_cas_audit.attempt_v1
 FOR EACH ROW EXECUTE FUNCTION v3_cas_audit.reject_aborted_epoch_dispatch_v1();
REVOKE ALL ON FUNCTION v3_cas_audit.reject_aborted_epoch_dispatch_v1()
 FROM PUBLIC,anon,authenticated,service_role;

RESET ROLE;
REVOKE CREATE ON SCHEMA v3_cas_audit FROM v3_cas_audit_table_owner;
REVOKE v3_cas_audit_table_owner FROM postgres GRANTED BY postgres;
DO $post$ BEGIN
 IF pg_has_role('postgres','v3_cas_audit_table_owner','SET')
    OR has_schema_privilege('v3_cas_audit_table_owner','v3_cas_audit','CREATE')
    OR NOT has_table_privilege('v3_cas_audit_reader',
           'v3_cas_audit.prepared_fence_abort_v1','SELECT')
    OR has_table_privilege('v3_cas_audit_reader',
           'v3_cas_audit.prepared_fence_abort_v1','INSERT,UPDATE,DELETE')
    OR has_table_privilege('service_role','v3_cas_audit.prepared_fence_abort_v1','SELECT')
    OR has_table_privilege('v3_cas_inhibit_issuer_actor',
           'v3_cas_audit.prepared_fence_abort_v1','INSERT')
    OR has_function_privilege('service_role',
           'v3_cas_audit.record_prepared_fence_abort_v1(text,text,text,text,text)','EXECUTE')
 THEN RAISE EXCEPTION 'V3_PREPARED_ABORT_PRIVILEGE_RESTORE_HOLD'; END IF;
END $post$;
COMMIT;
-- Strict unresolved dependency: append_intent/dispatch and Stage5 must reject
-- aborted epoch; external independent custody verifier must verify signed
-- issuer receipt, full UNKNOWN coverage, native tasks and marker ACL/SHA.
-- This file implements NEITHER deployment NOR originalhost marker removal.
-- Until those consumers are wired/tested, retain the existing HOLD gates.
