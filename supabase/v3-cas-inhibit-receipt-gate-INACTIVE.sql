-- Issue #99 / Variant 2: one original V3 CAS executor inhibit receipt schema.
-- SOURCE ONLY. The first database statement unconditionally aborts.
-- This is a proposed extension of the existing v3_cas_audit private owner;
-- NOT a new CAS RPC, a writer, an online Notebook worker, or authorization.
-- DO NOT DEPLOY / REMOVE THE LOCK outside separate reviewed originalhost/cloud
-- authorization and independently authenticated external issuer custody.
BEGIN;
DO $v3_inhibit_lock$
BEGIN
  RAISE EXCEPTION 'V3_CAS_INHIBIT_SCHEMA_SOURCE_INACTIVE_OWNER_AND_ISSUER_NOT_ABSOLVED';
END
$v3_inhibit_lock$;

DO $v3_inhibit_install$
BEGIN
 IF current_user <> 'postgres'
    OR to_regnamespace('v3_cas_audit') IS NULL
    OR to_regclass('v3_cas_audit.epoch_v1') IS NULL
    OR to_regclass('v3_cas_audit.intent_v1') IS NULL
    OR to_regclass('v3_cas_audit.executor_inhibit_v1') IS NOT NULL
    OR to_regprocedure(
       'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
    ) IS NOT NULL THEN
   RAISE EXCEPTION 'V3_CAS_INHIBIT_SCHEMA_EXISTING_OWNER_DRIFT_HOLD';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='v3_cas_audit_table_owner'
               AND NOT rolcanlogin AND NOT rolbypassrls AND NOT rolsuper)
    OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='v3_cas_executor'
               AND NOT rolcanlogin AND NOT rolbypassrls AND NOT rolsuper) THEN
   RAISE EXCEPTION 'V3_CAS_INHIBIT_ORIGINAL_ROLES_MISSING_HOLD';
 END IF;
END $v3_inhibit_install$;

-- Source draft only. Temporary role escrow follows existing Stage4's exact
-- membership pattern; this is not a new owner or a new writer.
GRANT v3_cas_audit_table_owner TO postgres WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;
SET ROLE v3_cas_audit_table_owner;

-- Source draft only. Even if eventually installed in an approved transaction:
-- NO INSERT/UPDATE/DELETE is granted to a runtime actor here. An independent
-- authenticated issuer and durable attempt/UNKNOWN coverage must be supplied
-- and separately proven first; a row written by an unrestricted cloud admin
-- cannot substitute for signed independent custody.
CREATE TABLE v3_cas_audit.executor_inhibit_v1 (
 epoch_id text PRIMARY KEY REFERENCES v3_cas_audit.epoch_v1(epoch_id),
 predecessor_series_id text NOT NULL
   CHECK (predecessor_series_id='PAPER-V2R4-20261009T110135Z'),
 expected_rpc text NOT NULL
   CHECK (expected_rpc='public.rotate_v2r4_to_v3_experimental_paper'),
 source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[a-f0-9]{64}$'),
 original_fence_sha256 text NOT NULL CHECK (original_fence_sha256 ~ '^[a-f0-9]{64}$'),
 caller_acl_sha256 text NOT NULL CHECK (caller_acl_sha256 ~ '^[a-f0-9]{64}$'),
 receipt_sha256 text NOT NULL UNIQUE CHECK (receipt_sha256 ~ '^[a-f0-9]{64}$'),
 issuer_id text NOT NULL CHECK (length(issuer_id) BETWEEN 1 AND 128),
 executor_id text NOT NULL CHECK (executor_id='v3_cas_executor'),
 state text NOT NULL CHECK (state='INHIBITED'),
 inhibit_started_at_utc timestamptz NOT NULL,
 native_stop_at_utc timestamptz NOT NULL,
 acknowledged_at_utc timestamptz NOT NULL,
 valid_through_utc timestamptz NOT NULL,
 audit_intent_high_watermark bigint NOT NULL CHECK (audit_intent_high_watermark=1),
 CHECK (inhibit_started_at_utc<native_stop_at_utc),
 CHECK (native_stop_at_utc<=acknowledged_at_utc),
 CHECK (acknowledged_at_utc<valid_through_utc),
 CHECK (valid_through_utc<=acknowledged_at_utc+interval '5 minutes')
);
ALTER TABLE v3_cas_audit.executor_inhibit_v1 ENABLE ROW LEVEL SECURITY;
ALTER TABLE v3_cas_audit.executor_inhibit_v1 FORCE ROW LEVEL SECURITY;
REVOKE ALL ON v3_cas_audit.executor_inhibit_v1
  FROM PUBLIC, anon, authenticated, service_role,
       v3_cas_operator_login, v3_cas_executor, v3_cas_audit_writer,
       v3_cas_audit_reader;
-- Narrow read permission for the existing CAS SECURITY DEFINER owner only;
-- the future caller never receives table access. FOR SHARE needs SELECT,
-- and neither CAS nor the service role gets any INSERT/UPDATE/DELETE.
GRANT SELECT ON v3_cas_audit.executor_inhibit_v1 TO postgres;
RESET ROLE;
REVOKE v3_cas_audit_table_owner FROM postgres GRANTED BY postgres;

DO $v3_inhibit_postflight$
BEGIN
 IF pg_has_role('postgres','v3_cas_audit_table_owner','SET')
    OR NOT has_table_privilege('postgres','v3_cas_audit.executor_inhibit_v1','SELECT')
    OR has_table_privilege('service_role','v3_cas_audit.executor_inhibit_v1','SELECT')
    OR has_table_privilege('v3_cas_executor','v3_cas_audit.executor_inhibit_v1','UPDATE') THEN
  RAISE EXCEPTION 'V3_CAS_INHIBIT_OWNER_ESCROW_POSTFLIGHT_HOLD';
 END IF;
END $v3_inhibit_postflight$;
-- No GRANT EXECUTE, no CAS call and no Paper mutation.
COMMIT;
