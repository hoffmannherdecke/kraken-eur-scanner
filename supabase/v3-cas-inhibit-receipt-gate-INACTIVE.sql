-- Original V3 Paper CAS private inhibit receipt, Variant 2, Issue #99.
-- SOURCE ONLY: first effectful DO statement unconditionally RAISES.
-- Existing Notebook reader remains READ ONLY. Separate critical issuer is
-- NOLOGIN/connection-limit-zero until independently approved physical setup.
-- No existing database object/role/Task is changed by this source file.
BEGIN;
DO $v3_inhibit_lock$
BEGIN
  RAISE EXCEPTION 'V3_CAS_INHIBIT_SCHEMA_SOURCE_INACTIVE_OWNER_AND_ISSUER_NOT_ABSOLVED';
END
$v3_inhibit_lock$;

DO $v3_inhibit_preflight$
BEGIN
 IF current_user <> 'postgres'
    OR to_regnamespace('v3_cas_audit') IS NULL
    OR to_regclass('v3_cas_audit.epoch_v1') IS NULL
    OR to_regclass('v3_cas_audit.intent_v1') IS NULL
    OR to_regclass('v3_cas_audit.executor_inhibit_v1') IS NOT NULL
    OR to_regrole('v3_cas_inhibit_issuer_actor') IS NOT NULL
    OR to_regprocedure(
       'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
    ) IS NOT NULL THEN
  RAISE EXCEPTION 'V3_CAS_INHIBIT_SCHEMA_EXISTING_OWNER_DRIFT_HOLD';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='v3_cas_audit_table_owner'
                AND NOT rolcanlogin AND NOT rolbypassrls AND NOT rolsuper)
    OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='v3_cas_executor'
                AND NOT rolcanlogin AND NOT rolbypassrls AND NOT rolsuper)
    OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='v3_cas_audit_reader_actor'
                AND rolcanlogin AND NOT rolbypassrls) THEN
  RAISE EXCEPTION 'V3_CAS_INHIBIT_ORIGINAL_ROLES_MISSING_HOLD';
 END IF;
 CREATE ROLE v3_cas_inhibit_issuer_actor NOLOGIN NOINHERIT NOBYPASSRLS CONNECTION LIMIT 0;
END
$v3_inhibit_preflight$;

-- Restrict existing schema CREATE to a single transaction-scoped escrow.
GRANT CREATE ON SCHEMA v3_cas_audit TO v3_cas_audit_table_owner;
GRANT v3_cas_audit_table_owner TO postgres WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;
SET ROLE v3_cas_audit_table_owner;

CREATE TABLE v3_cas_audit.executor_inhibit_v1 (
 epoch_id text PRIMARY KEY REFERENCES v3_cas_audit.epoch_v1(epoch_id),
 predecessor_series_id text NOT NULL
   CHECK (predecessor_series_id='PAPER-V2R4-20261009T110135Z'),
 expected_rpc text NOT NULL
   CHECK (expected_rpc='public.rotate_v2r4_to_v3_experimental_paper'),
 source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[a-f0-9]{64}$'),
 original_fence_sha256 text NOT NULL CHECK (original_fence_sha256 ~ '^[a-f0-9]{64}$'),
 caller_acl_sha256 text NOT NULL CHECK (caller_acl_sha256 ~ '^[a-f0-9]{64}$'),
 receipt_sha256 text UNIQUE CHECK (receipt_sha256 ~ '^[a-f0-9]{64}$'),
 issuer_id text NOT NULL CHECK (issuer_id='v3_cas_inhibit_issuer_actor'),
 executor_id text NOT NULL CHECK (executor_id='v3_cas_executor'),
 state text NOT NULL CHECK (state='INHIBITED'),
 inhibit_started_at_utc timestamptz NOT NULL DEFAULT clock_timestamp(),
 native_stop_at_utc timestamptz,
 acknowledged_at_utc timestamptz,
 valid_through_utc timestamptz,
 audit_intent_high_watermark bigint CHECK (audit_intent_high_watermark=1),
 CHECK (
   (native_stop_at_utc IS NULL AND acknowledged_at_utc IS NULL
    AND valid_through_utc IS NULL AND receipt_sha256 IS NULL
    AND audit_intent_high_watermark IS NULL)
   OR
   (native_stop_at_utc IS NOT NULL AND acknowledged_at_utc IS NOT NULL
    AND valid_through_utc IS NOT NULL AND receipt_sha256 IS NOT NULL
    AND audit_intent_high_watermark=1
    AND inhibit_started_at_utc<native_stop_at_utc
    AND native_stop_at_utc<=acknowledged_at_utc
    AND acknowledged_at_utc<valid_through_utc
    AND valid_through_utc<=acknowledged_at_utc+interval '5 minutes')
 )
);
ALTER TABLE v3_cas_audit.executor_inhibit_v1 ENABLE ROW LEVEL SECURITY;
ALTER TABLE v3_cas_audit.executor_inhibit_v1 FORCE ROW LEVEL SECURITY;
CREATE POLICY v3_cas_inhibit_owner_only_v1 ON v3_cas_audit.executor_inhibit_v1
 FOR ALL TO v3_cas_audit_table_owner USING (true) WITH CHECK (true);
REVOKE ALL ON v3_cas_audit.executor_inhibit_v1
 FROM PUBLIC,anon,authenticated,service_role,
      v3_cas_operator_login,v3_cas_executor,v3_cas_audit_writer,
      v3_cas_audit_reader,v3_cas_audit_reader_actor;

-- Critical-only issuer identity is authenticated independently of Originalhost
-- via its dedicated login credential on the Notebook, never by user JSON.
-- Function owner NOLOGIN is the existing audit table owner, not a new executor.
-- The private role remains NOLOGIN until a separate physical approval.
-- This is NOT validation of a detached CMS signature or attempt history.
CREATE FUNCTION v3_cas_audit.begin_executor_inhibit_v1(
 p_epoch_id text,p_source_sha256 text,p_fence_sha256 text,p_caller_acl_sha256 text
) RETURNS timestamptz
LANGUAGE plpgsql SECURITY DEFINER
SET search_path='pg_catalog','v3_cas_audit'
AS $v3_begin$
DECLARE v_time timestamptz;
BEGIN
 IF session_user <> 'v3_cas_inhibit_issuer_actor'
    OR p_epoch_id !~ '^V3CAS-AUDIT-[a-f0-9]{32}$'
    OR p_source_sha256 !~ '^[a-f0-9]{64}$'
    OR p_fence_sha256 !~ '^[a-f0-9]{64}$'
    OR p_caller_acl_sha256 !~ '^[a-f0-9]{64}$'
    OR to_regprocedure(
       'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
       ) IS NOT NULL
    OR (SELECT rolcanlogin FROM pg_roles WHERE rolname='v3_cas_executor') IS DISTINCT FROM FALSE
 THEN RAISE EXCEPTION 'V3_CAS_INHIBIT_ISSUER_START_SCOPE_HOLD'; END IF;
 INSERT INTO v3_cas_audit.executor_inhibit_v1
   (epoch_id,predecessor_series_id,expected_rpc,source_sha256,
    original_fence_sha256,caller_acl_sha256,issuer_id,executor_id,state)
 VALUES
   (p_epoch_id,'PAPER-V2R4-20261009T110135Z',
    'public.rotate_v2r4_to_v3_experimental_paper',p_source_sha256,
    p_fence_sha256,p_caller_acl_sha256,
    'v3_cas_inhibit_issuer_actor','v3_cas_executor','INHIBITED')
 RETURNING inhibit_started_at_utc INTO v_time;
 RETURN v_time;
END
$v3_begin$;

CREATE FUNCTION v3_cas_audit.confirm_executor_inhibit_v1(
 p_epoch_id text,p_stop_time timestamptz,p_receipt_sha256 text
) RETURNS timestamptz
LANGUAGE plpgsql SECURITY DEFINER
SET search_path='pg_catalog','v3_cas_audit'
AS $v3_confirm$
DECLARE v_at timestamptz;
BEGIN
 IF session_user <> 'v3_cas_inhibit_issuer_actor'
    OR p_receipt_sha256 !~ '^[a-f0-9]{64}$'
    OR p_stop_time IS NULL OR p_stop_time>clock_timestamp()
 THEN RAISE EXCEPTION 'V3_CAS_INHIBIT_ISSUER_CONFIRM_SCOPE_HOLD'; END IF;
 UPDATE v3_cas_audit.executor_inhibit_v1
 SET native_stop_at_utc=p_stop_time,
     acknowledged_at_utc=clock_timestamp(),
     valid_through_utc=clock_timestamp()+interval '4 minutes',
     receipt_sha256=p_receipt_sha256,
     audit_intent_high_watermark=1
 WHERE epoch_id=p_epoch_id
   AND issuer_id='v3_cas_inhibit_issuer_actor'
   AND native_stop_at_utc IS NULL
   AND inhibit_started_at_utc<p_stop_time
 RETURNING acknowledged_at_utc INTO v_at;
 IF NOT FOUND THEN
  RAISE EXCEPTION 'V3_CAS_INHIBIT_ISSUER_CONFIRM_REPLAY_OR_TIME_HOLD';
 END IF;
 RETURN v_at;
END
$v3_confirm$;

-- Newly created SECURITY DEFINER functions default EXECUTE to PUBLIC.
-- Revoke within this SAME uncommitted transaction before anyone can call.
REVOKE ALL ON FUNCTION v3_cas_audit.begin_executor_inhibit_v1(text,text,text,text)
 FROM PUBLIC,anon,authenticated,service_role;
REVOKE ALL ON FUNCTION v3_cas_audit.confirm_executor_inhibit_v1(text,timestamptz,text)
 FROM PUBLIC,anon,authenticated,service_role;
GRANT EXECUTE ON FUNCTION v3_cas_audit.begin_executor_inhibit_v1(text,text,text,text)
 TO v3_cas_inhibit_issuer_actor;
GRANT EXECUTE ON FUNCTION v3_cas_audit.confirm_executor_inhibit_v1(text,timestamptz,text)
 TO v3_cas_inhibit_issuer_actor;
GRANT SELECT ON v3_cas_audit.executor_inhibit_v1 TO postgres;

RESET ROLE;
REVOKE CREATE ON SCHEMA v3_cas_audit FROM v3_cas_audit_table_owner;
GRANT USAGE ON SCHEMA v3_cas_audit TO v3_cas_inhibit_issuer_actor;
REVOKE v3_cas_audit_table_owner FROM postgres GRANTED BY postgres;

DO $v3_inhibit_postflight$
BEGIN
 IF pg_has_role('postgres','v3_cas_audit_table_owner','SET')
    OR has_schema_privilege('v3_cas_audit_table_owner','v3_cas_audit','CREATE')
    OR NOT has_table_privilege('postgres','v3_cas_audit.executor_inhibit_v1','SELECT')
    OR has_table_privilege('service_role','v3_cas_audit.executor_inhibit_v1','SELECT')
    OR has_table_privilege('v3_cas_inhibit_issuer_actor','v3_cas_audit.executor_inhibit_v1','INSERT')
    OR has_table_privilege('v3_cas_audit_reader_actor','v3_cas_audit.executor_inhibit_v1','UPDATE')
    OR (SELECT rolcanlogin FROM pg_roles WHERE rolname='v3_cas_inhibit_issuer_actor') IS DISTINCT FROM FALSE
 THEN RAISE EXCEPTION 'V3_CAS_INHIBIT_OWNER_ESCROW_POSTFLIGHT_HOLD'; END IF;
END
$v3_inhibit_postflight$;
-- No real CAS call, issuer LOGIN activation, Paper or Windows mutation.
COMMIT;
