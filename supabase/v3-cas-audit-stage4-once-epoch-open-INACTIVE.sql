-- V3 Paper original V2R4->V3 Stage4 / SOURCE-ONLY / LOCKED / ONCE-ONLY.
-- DO NOT RUN ON ORIGINAL SUPABASE. Requires separate exact-source, physical
-- fence, caller ACL, independent reader and original Issue #99 approval.
-- This does NOT certify external issuer/custody, CAS no-rearm or Paper Go-Live.
-- This opens ONE genuine release epoch only; NEVER create a dummy production epoch.
-- Offline PG17 CI renders synthetic placeholders solely under --network none.
-- All temporary owner membership / INSERT column grants are reverted BEFORE
-- COMMIT; failures roll back the entire transaction with ON_ERROR_STOP.
BEGIN;
DO $v3_stage4_open_source_lock$
BEGIN
 RAISE EXCEPTION 'V3_STAGE4_EPOCH_OPEN_SOURCE_INACTIVE_APPROVAL_REQUIRED';
END $v3_stage4_open_source_lock$;
DO $v3_stage4_open_preflight$
DECLARE
 v_id text := '__V3_STAGE4_EPOCH_ID__';
 v_source text := '__V3_STAGE4_SOURCE_SHA256__';
 v_fence text := '__V3_STAGE4_ORIGINAL_FENCE_SHA256__';
 v_acl text := '__V3_STAGE4_CALLER_ACL_SHA256__';
BEGIN
 IF current_user <> 'postgres'
    OR (SELECT count(*) FROM pg_catalog.pg_roles
        WHERE rolname='postgres' AND NOT rolsuper AND rolcreaterole
          AND rolbypassrls) <> 1 THEN
  RAISE EXCEPTION 'V3_STAGE4_NOT_ORIGINAL_PG17_ADMIN_HOLD';
 END IF;
 IF v_id !~ '^V3CAS-AUDIT-[a-f0-9]{32}$'
    OR v_source !~ '^[a-f0-9]{64}$'
    OR v_fence !~ '^[a-f0-9]{64}$'
    OR v_acl !~ '^[a-f0-9]{64}$' THEN
  RAISE EXCEPTION 'V3_STAGE4_UNBOUND_EPOCH_DIGEST_HOLD';
 END IF;
 IF (SELECT count(*) FROM public.paper_series WHERE status='active') <> 1
    OR (SELECT count(*) FROM public.paper_series
        WHERE status='active' AND series_id='PAPER-V2R4-20261009T110135Z') <> 1
    OR (SELECT count(*) FROM v3_cas_audit.epoch_v1) <> 0
    OR (SELECT count(*) FROM v3_cas_audit.intent_v1) <> 0
    OR pg_catalog.to_regprocedure(
      'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
      ) IS NOT NULL THEN
  RAISE EXCEPTION 'V3_STAGE4_ORIGINAL_CAS_OR_AUDIT_NOT_EMPTY_HOLD';
 END IF;
 IF (SELECT count(*) FROM pg_catalog.pg_auth_members m
      JOIN pg_catalog.pg_roles a ON a.oid=m.member
      JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
      WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner'
        AND m.admin_option AND NOT m.set_option AND NOT m.inherit_option) <> 1
    OR pg_catalog.pg_has_role('postgres','v3_cas_audit_table_owner','SET')
    OR pg_catalog.has_column_privilege('postgres',
           'v3_cas_audit.epoch_v1','epoch_id','INSERT')
    OR pg_catalog.has_column_privilege('postgres',
           'v3_cas_audit.epoch_v1','sealed','UPDATE')
    OR pg_catalog.pg_get_userbyid(
      (SELECT relowner FROM pg_catalog.pg_class
       WHERE oid='v3_cas_audit.epoch_v1'::regclass))
       <> 'v3_cas_audit_table_owner'
    OR (SELECT count(*) FROM pg_catalog.pg_class
        WHERE oid IN ('v3_cas_audit.epoch_v1'::regclass,
                      'v3_cas_audit.intent_v1'::regclass)
          AND relrowsecurity AND relforcerowsecurity) <> 2
    OR (SELECT count(*) FROM pg_catalog.pg_roles
       WHERE rolname='v3_cas_executor_actor'
         AND NOT rolcanlogin AND rolconnlimit=0) <> 1 THEN
  RAISE EXCEPTION 'V3_STAGE4_OWNER_GRANTS_OR_RLS_DRIFT_HOLD';
 END IF;
END $v3_stage4_open_preflight$;
-- PostgreSQL 17 CREATEROLE original admin holds ADMIN-only on the owner.
-- Grant SET only for the current transaction, never grant to writer/reader.
GRANT v3_cas_audit_table_owner TO postgres
 WITH ADMIN FALSE, INHERIT FALSE, SET TRUE;
SET LOCAL ROLE v3_cas_audit_table_owner;
GRANT INSERT (epoch_id,predecessor_series_id,expected_rpc,
              source_sha256,original_fence_sha256,approved_caller_acl_sha256)
 ON v3_cas_audit.epoch_v1 TO postgres;
RESET ROLE;
-- postgres BYPASSRLS needs this temporary, exact column INSERT privilege.
INSERT INTO v3_cas_audit.epoch_v1
 (epoch_id,predecessor_series_id,expected_rpc,
  source_sha256,original_fence_sha256,approved_caller_acl_sha256)
VALUES
 ('__V3_STAGE4_EPOCH_ID__',
  'PAPER-V2R4-20261009T110135Z',
  'public.rotate_v2r4_to_v3_experimental_paper',
  '__V3_STAGE4_SOURCE_SHA256__',
  '__V3_STAGE4_ORIGINAL_FENCE_SHA256__',
  '__V3_STAGE4_CALLER_ACL_SHA256__');
-- Remove every temporary privilege before COMMIT.
SET LOCAL ROLE v3_cas_audit_table_owner;
REVOKE INSERT (epoch_id,predecessor_series_id,expected_rpc,
               source_sha256,original_fence_sha256,approved_caller_acl_sha256)
 ON v3_cas_audit.epoch_v1 FROM postgres;
RESET ROLE;
REVOKE v3_cas_audit_table_owner FROM postgres;
DO $v3_stage4_open_postflight$
BEGIN
 IF (SELECT count(*) FROM v3_cas_audit.epoch_v1
       WHERE epoch_id='__V3_STAGE4_EPOCH_ID__'
         AND predecessor_series_id='PAPER-V2R4-20261009T110135Z'
         AND expected_rpc='public.rotate_v2r4_to_v3_experimental_paper'
         AND source_sha256='__V3_STAGE4_SOURCE_SHA256__'
         AND original_fence_sha256='__V3_STAGE4_ORIGINAL_FENCE_SHA256__'
         AND approved_caller_acl_sha256='__V3_STAGE4_CALLER_ACL_SHA256__'
         AND next_ordinal=1 AND NOT sealed) <> 1
    OR (SELECT count(*) FROM v3_cas_audit.intent_v1) <> 0
    OR pg_catalog.pg_has_role('postgres','v3_cas_audit_table_owner','SET')
    OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
        JOIN pg_catalog.pg_roles a ON a.oid=m.member
        JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
        WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner'
          AND m.admin_option AND NOT m.inherit_option AND NOT m.set_option) <> 1
    OR pg_catalog.has_column_privilege('postgres',
        'v3_cas_audit.epoch_v1','epoch_id','INSERT')
 THEN RAISE EXCEPTION 'V3_STAGE4_OPEN_POSTFLIGHT_REVOKE_OR_EPOCH_HOLD';
 END IF;
END $v3_stage4_open_postflight$;
COMMIT;
-- A successful epoch OPEN does not attest a COMMITed intent, no-rearm or CAS.
