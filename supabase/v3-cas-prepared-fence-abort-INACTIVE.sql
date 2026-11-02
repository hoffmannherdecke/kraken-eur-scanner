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
    OR (SELECT count(*) FROM public.paper_series WHERE status='active') <> 1
    OR (SELECT count(*) FROM public.paper_series
        WHERE status='active' AND series_id='PAPER-V2R4-20261009T110135Z') <> 1
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
