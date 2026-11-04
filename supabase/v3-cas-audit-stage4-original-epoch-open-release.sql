-- V3 Paper Issue #99: separately reviewed CLOUD_STAGE4_EPOCH_OPEN one-time variant.
-- NOT self-authorizing: only exact independently admitted detached CMS packet.
-- Stage2/Stage3 are already productive; do not reinstall.
-- Requires separately reviewed ORIGINAL source/fence/caller ACL fingerprints and
-- signed originalhost current pre-CAS/no-rearm evidence, plus scoped authorization.
-- One PostgreSQL17 transaction: temporarily grant table-owner SET to postgres,
-- temporarily grant INSERT to postgres, open exactly one source-bound epoch,
-- fully restore owner membership/ACL before COMMIT. NO INTENT and NO CAS.
-- Isolated PG17 CI may remove the FIRST intentional exception and replace
-- __...__ markers with DISPOSABLE synthetic values. NEVER do this in production
-- without the existing Issue #99 authorizations and reviewed original evidence.
BEGIN;
-- Separate reviewed one-time PRODUCTION variant. The original source-only
-- statement is unchanged in its own file; this gate is executable ONLY by
-- an externally admitted, SHA-pinned detached-CMS release packet.
DO $v3_stage4_release_gate$
BEGIN
 IF current_setting('v3_stage4.scope',true) IS DISTINCT FROM 'CLOUD_STAGE4_EPOCH_OPEN'
    OR current_setting('v3_stage4.release_commit',true) !~ '^[a-f0-9]{40}

DO $v3_stage4_preflight$
DECLARE
  v_role_memberships integer;
BEGIN
  IF current_user <> 'postgres'
     OR current_database() <> 'postgres'
     OR NOT (SELECT NOT rolsuper AND rolcreaterole AND rolbypassrls
             FROM pg_catalog.pg_roles WHERE rolname='postgres') THEN
    RAISE EXCEPTION 'V3_STAGE4_ORIGINAL_ADMIN_IDENTITY_HOLD';
  END IF;
  IF current_setting('v3_stage4.epoch_id',true) !~ '^V3CAS-AUDIT-[a-f0-9]{32}$'
     OR current_setting('v3_stage4.source_sha256',true) !~ '^[a-f0-9]{64}$'
     OR current_setting('v3_stage4.fence_sha256',true) !~ '^[a-f0-9]{64}$'
     OR current_setting('v3_stage4.caller_acl_sha256',true) !~ '^[a-f0-9]{64}$' THEN
    RAISE EXCEPTION 'V3_STAGE4_ORIGINAL_FINGERPRINTS_MISSING_HOLD';
  END IF;
  IF (SELECT count(*) FROM public.paper_series WHERE status='active') <> 1
     OR (SELECT count(*) FROM public.paper_series WHERE status='active'
             AND series_id='PAPER-V2R4-20261009T110135Z') <> 1 THEN
    RAISE EXCEPTION 'V3_STAGE4_WRONG_ACTIVE_ORIGINAL_PAPER_HOLD';
  END IF;
  IF to_regprocedure(
       'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
     ) IS NOT NULL THEN
    RAISE EXCEPTION 'V3_STAGE4_CAS_ALREADY_EXISTS_HOLD';
  END IF;
  IF to_regclass('v3_cas_audit.epoch_v1') IS NULL
     OR to_regclass('v3_cas_audit.intent_v1') IS NULL
     OR (SELECT count(*) FROM v3_cas_audit.epoch_v1) <> 0
     OR (SELECT count(*) FROM v3_cas_audit.intent_v1) <> 0 THEN
    RAISE EXCEPTION 'V3_STAGE4_EXISTING_AUDIT_EPOCH_OR_INTENT_HOLD';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace ns
      ON c.relnamespace=ns.oid WHERE ns.nspname='v3_cas_audit'
       AND c.relname IN ('epoch_v1','intent_v1')
       AND c.relrowsecurity AND c.relforcerowsecurity
       AND pg_catalog.pg_get_userbyid(c.relowner)='v3_cas_audit_table_owner') <> 2 THEN
    RAISE EXCEPTION 'V3_STAGE4_PRIVATE_FORCED_RLS_OWNER_DRIFT_HOLD';
  END IF;
  SELECT count(*) INTO v_role_memberships
    FROM pg_catalog.pg_auth_members m
    JOIN pg_catalog.pg_roles a ON a.oid=m.member
    JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
   WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner'
     AND m.admin_option AND NOT m.inherit_option AND NOT m.set_option;
  IF v_role_memberships <> 1
     OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles a ON a.oid=m.member
          JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
          WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner') <> 1
     OR pg_catalog.pg_has_role('postgres','v3_cas_audit_table_owner','SET')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','INSERT')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','UPDATE') THEN
    RAISE EXCEPTION 'V3_STAGE4_ORIGINAL_ADMIN_PRIVILEGE_ESCROW_NOT_CLEAN_HOLD';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_roles
      WHERE rolname IN ('v3_cas_audit_writer_actor','v3_cas_audit_reader_actor')
        AND rolcanlogin AND rolconnlimit=1 AND NOT rolbypassrls) <> 2
     OR (SELECT count(*) FROM pg_catalog.pg_roles
         WHERE rolname='v3_cas_executor_actor' AND NOT rolcanlogin
           AND rolconnlimit=0) <> 1 THEN
    RAISE EXCEPTION 'V3_STAGE4_ACTOR_STATE_DRIFT_HOLD';
  END IF;
END $v3_stage4_preflight$;

-- The original PostgreSQL 17 CREATEROLE owner-admin membership is
-- ADMIN TRUE, INHERIT FALSE, SET FALSE. A temporary grant from postgres
-- must NOT replace the preexisting bootstrap edge.
GRANT v3_cas_audit_table_owner TO postgres WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;
SET ROLE v3_cas_audit_table_owner;
GRANT INSERT ON v3_cas_audit.epoch_v1 TO postgres;
RESET ROLE;

-- PostgreSQL postgres BYPASSRLS can INSERT only with explicit object ACL.
-- Source/fence fingerprints must originate from approved ORIGINAL receipts.
INSERT INTO v3_cas_audit.epoch_v1
  (epoch_id,predecessor_series_id,expected_rpc,source_sha256,
   original_fence_sha256,approved_caller_acl_sha256)
VALUES
  (current_setting('v3_stage4.epoch_id',true),'PAPER-V2R4-20261009T110135Z',
   'public.rotate_v2r4_to_v3_experimental_paper',
   current_setting('v3_stage4.source_sha256',true),current_setting('v3_stage4.fence_sha256',true),current_setting('v3_stage4.caller_acl_sha256',true));

-- Restore direct privilege and temporary membership IN THE SAME transaction.
SET ROLE v3_cas_audit_table_owner;
REVOKE INSERT ON v3_cas_audit.epoch_v1 FROM postgres;
RESET ROLE;
REVOKE v3_cas_audit_table_owner FROM postgres GRANTED BY postgres;

DO $v3_stage4_postflight$
BEGIN
  IF pg_catalog.pg_has_role('postgres','v3_cas_audit_table_owner','SET')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','INSERT')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','UPDATE')
     OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles a ON a.oid=m.member
          JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
          WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner'
            AND m.admin_option AND NOT m.inherit_option AND NOT m.set_option) <> 1
     OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles a ON a.oid=m.member
          JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
          WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner') <> 1 THEN
    RAISE EXCEPTION 'V3_STAGE4_TEMPORARY_PRIVILEGE_NOT_FULLY_RESTORED_HOLD';
  END IF;
  IF (SELECT count(*) FROM v3_cas_audit.epoch_v1
          WHERE epoch_id=current_setting('v3_stage4.epoch_id',true)
            AND source_sha256=current_setting('v3_stage4.source_sha256',true)
            AND original_fence_sha256=current_setting('v3_stage4.fence_sha256',true)
            AND approved_caller_acl_sha256=current_setting('v3_stage4.caller_acl_sha256',true)
            AND predecessor_series_id='PAPER-V2R4-20261009T110135Z'
            AND expected_rpc='public.rotate_v2r4_to_v3_experimental_paper'
            AND next_ordinal=1 AND NOT sealed) <> 1
     OR (SELECT count(*) FROM v3_cas_audit.epoch_v1) <> 1
     OR (SELECT count(*) FROM v3_cas_audit.intent_v1) <> 0 THEN
    RAISE EXCEPTION 'V3_STAGE4_EPOCH_UNEXPECTED_ROWS_OR_SOURCE_HOLD';
  END IF;
END $v3_stage4_postflight$;
COMMIT;
-- Even an actual original Stage4 COMMIT does NOT authorize CAS or native stop.
-- Stage5: separately authorized append writer transaction and after-COMMIT
-- independent reader; subsequent seal and executor/No-Rearm gates still OPEN.

    OR current_setting('v3_stage4.approval_sha256',true) !~ '^[a-f0-9]{64}

DO $v3_stage4_preflight$
DECLARE
  v_role_memberships integer;
BEGIN
  IF current_user <> 'postgres'
     OR current_database() <> 'postgres'
     OR NOT (SELECT NOT rolsuper AND rolcreaterole AND rolbypassrls
             FROM pg_catalog.pg_roles WHERE rolname='postgres') THEN
    RAISE EXCEPTION 'V3_STAGE4_ORIGINAL_ADMIN_IDENTITY_HOLD';
  END IF;
  IF current_setting('v3_stage4.epoch_id',true) !~ '^V3CAS-AUDIT-[a-f0-9]{32}$'
     OR current_setting('v3_stage4.source_sha256',true) !~ '^[a-f0-9]{64}$'
     OR current_setting('v3_stage4.fence_sha256',true) !~ '^[a-f0-9]{64}$'
     OR current_setting('v3_stage4.caller_acl_sha256',true) !~ '^[a-f0-9]{64}$' THEN
    RAISE EXCEPTION 'V3_STAGE4_ORIGINAL_FINGERPRINTS_MISSING_HOLD';
  END IF;
  IF (SELECT count(*) FROM public.paper_series WHERE status='active') <> 1
     OR (SELECT count(*) FROM public.paper_series WHERE status='active'
             AND series_id='PAPER-V2R4-20261009T110135Z') <> 1 THEN
    RAISE EXCEPTION 'V3_STAGE4_WRONG_ACTIVE_ORIGINAL_PAPER_HOLD';
  END IF;
  IF to_regprocedure(
       'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
     ) IS NOT NULL THEN
    RAISE EXCEPTION 'V3_STAGE4_CAS_ALREADY_EXISTS_HOLD';
  END IF;
  IF to_regclass('v3_cas_audit.epoch_v1') IS NULL
     OR to_regclass('v3_cas_audit.intent_v1') IS NULL
     OR (SELECT count(*) FROM v3_cas_audit.epoch_v1) <> 0
     OR (SELECT count(*) FROM v3_cas_audit.intent_v1) <> 0 THEN
    RAISE EXCEPTION 'V3_STAGE4_EXISTING_AUDIT_EPOCH_OR_INTENT_HOLD';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace ns
      ON c.relnamespace=ns.oid WHERE ns.nspname='v3_cas_audit'
       AND c.relname IN ('epoch_v1','intent_v1')
       AND c.relrowsecurity AND c.relforcerowsecurity
       AND pg_catalog.pg_get_userbyid(c.relowner)='v3_cas_audit_table_owner') <> 2 THEN
    RAISE EXCEPTION 'V3_STAGE4_PRIVATE_FORCED_RLS_OWNER_DRIFT_HOLD';
  END IF;
  SELECT count(*) INTO v_role_memberships
    FROM pg_catalog.pg_auth_members m
    JOIN pg_catalog.pg_roles a ON a.oid=m.member
    JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
   WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner'
     AND m.admin_option AND NOT m.inherit_option AND NOT m.set_option;
  IF v_role_memberships <> 1
     OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles a ON a.oid=m.member
          JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
          WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner') <> 1
     OR pg_catalog.pg_has_role('postgres','v3_cas_audit_table_owner','SET')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','INSERT')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','UPDATE') THEN
    RAISE EXCEPTION 'V3_STAGE4_ORIGINAL_ADMIN_PRIVILEGE_ESCROW_NOT_CLEAN_HOLD';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_roles
      WHERE rolname IN ('v3_cas_audit_writer_actor','v3_cas_audit_reader_actor')
        AND rolcanlogin AND rolconnlimit=1 AND NOT rolbypassrls) <> 2
     OR (SELECT count(*) FROM pg_catalog.pg_roles
         WHERE rolname='v3_cas_executor_actor' AND NOT rolcanlogin
           AND rolconnlimit=0) <> 1 THEN
    RAISE EXCEPTION 'V3_STAGE4_ACTOR_STATE_DRIFT_HOLD';
  END IF;
END $v3_stage4_preflight$;

-- The original PostgreSQL 17 CREATEROLE owner-admin membership is
-- ADMIN TRUE, INHERIT FALSE, SET FALSE. A temporary grant from postgres
-- must NOT replace the preexisting bootstrap edge.
GRANT v3_cas_audit_table_owner TO postgres WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;
SET ROLE v3_cas_audit_table_owner;
GRANT INSERT ON v3_cas_audit.epoch_v1 TO postgres;
RESET ROLE;

-- PostgreSQL postgres BYPASSRLS can INSERT only with explicit object ACL.
-- Source/fence fingerprints must originate from approved ORIGINAL receipts.
INSERT INTO v3_cas_audit.epoch_v1
  (epoch_id,predecessor_series_id,expected_rpc,source_sha256,
   original_fence_sha256,approved_caller_acl_sha256)
VALUES
  (current_setting('v3_stage4.epoch_id',true),'PAPER-V2R4-20261009T110135Z',
   'public.rotate_v2r4_to_v3_experimental_paper',
   current_setting('v3_stage4.source_sha256',true),current_setting('v3_stage4.fence_sha256',true),current_setting('v3_stage4.caller_acl_sha256',true));

-- Restore direct privilege and temporary membership IN THE SAME transaction.
SET ROLE v3_cas_audit_table_owner;
REVOKE INSERT ON v3_cas_audit.epoch_v1 FROM postgres;
RESET ROLE;
REVOKE v3_cas_audit_table_owner FROM postgres GRANTED BY postgres;

DO $v3_stage4_postflight$
BEGIN
  IF pg_catalog.pg_has_role('postgres','v3_cas_audit_table_owner','SET')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','INSERT')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','UPDATE')
     OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles a ON a.oid=m.member
          JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
          WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner'
            AND m.admin_option AND NOT m.inherit_option AND NOT m.set_option) <> 1
     OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles a ON a.oid=m.member
          JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
          WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner') <> 1 THEN
    RAISE EXCEPTION 'V3_STAGE4_TEMPORARY_PRIVILEGE_NOT_FULLY_RESTORED_HOLD';
  END IF;
  IF (SELECT count(*) FROM v3_cas_audit.epoch_v1
          WHERE epoch_id=current_setting('v3_stage4.epoch_id',true)
            AND source_sha256=current_setting('v3_stage4.source_sha256',true)
            AND original_fence_sha256=current_setting('v3_stage4.fence_sha256',true)
            AND approved_caller_acl_sha256=current_setting('v3_stage4.caller_acl_sha256',true)
            AND predecessor_series_id='PAPER-V2R4-20261009T110135Z'
            AND expected_rpc='public.rotate_v2r4_to_v3_experimental_paper'
            AND next_ordinal=1 AND NOT sealed) <> 1
     OR (SELECT count(*) FROM v3_cas_audit.epoch_v1) <> 1
     OR (SELECT count(*) FROM v3_cas_audit.intent_v1) <> 0 THEN
    RAISE EXCEPTION 'V3_STAGE4_EPOCH_UNEXPECTED_ROWS_OR_SOURCE_HOLD';
  END IF;
END $v3_stage4_postflight$;
COMMIT;
-- Even an actual original Stage4 COMMIT does NOT authorize CAS or native stop.
-- Stage5: separately authorized append writer transaction and after-COMMIT
-- independent reader; subsequent seal and executor/No-Rearm gates still OPEN.

    OR current_setting('v3_stage4.release_id',true) !~ '^V3-ONETIME-[a-f0-9]{32}

DO $v3_stage4_preflight$
DECLARE
  v_role_memberships integer;
BEGIN
  IF current_user <> 'postgres'
     OR current_database() <> 'postgres'
     OR NOT (SELECT NOT rolsuper AND rolcreaterole AND rolbypassrls
             FROM pg_catalog.pg_roles WHERE rolname='postgres') THEN
    RAISE EXCEPTION 'V3_STAGE4_ORIGINAL_ADMIN_IDENTITY_HOLD';
  END IF;
  IF current_setting('v3_stage4.epoch_id',true) !~ '^V3CAS-AUDIT-[a-f0-9]{32}$'
     OR current_setting('v3_stage4.source_sha256',true) !~ '^[a-f0-9]{64}$'
     OR current_setting('v3_stage4.fence_sha256',true) !~ '^[a-f0-9]{64}$'
     OR current_setting('v3_stage4.caller_acl_sha256',true) !~ '^[a-f0-9]{64}$' THEN
    RAISE EXCEPTION 'V3_STAGE4_ORIGINAL_FINGERPRINTS_MISSING_HOLD';
  END IF;
  IF (SELECT count(*) FROM public.paper_series WHERE status='active') <> 1
     OR (SELECT count(*) FROM public.paper_series WHERE status='active'
             AND series_id='PAPER-V2R4-20261009T110135Z') <> 1 THEN
    RAISE EXCEPTION 'V3_STAGE4_WRONG_ACTIVE_ORIGINAL_PAPER_HOLD';
  END IF;
  IF to_regprocedure(
       'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
     ) IS NOT NULL THEN
    RAISE EXCEPTION 'V3_STAGE4_CAS_ALREADY_EXISTS_HOLD';
  END IF;
  IF to_regclass('v3_cas_audit.epoch_v1') IS NULL
     OR to_regclass('v3_cas_audit.intent_v1') IS NULL
     OR (SELECT count(*) FROM v3_cas_audit.epoch_v1) <> 0
     OR (SELECT count(*) FROM v3_cas_audit.intent_v1) <> 0 THEN
    RAISE EXCEPTION 'V3_STAGE4_EXISTING_AUDIT_EPOCH_OR_INTENT_HOLD';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace ns
      ON c.relnamespace=ns.oid WHERE ns.nspname='v3_cas_audit'
       AND c.relname IN ('epoch_v1','intent_v1')
       AND c.relrowsecurity AND c.relforcerowsecurity
       AND pg_catalog.pg_get_userbyid(c.relowner)='v3_cas_audit_table_owner') <> 2 THEN
    RAISE EXCEPTION 'V3_STAGE4_PRIVATE_FORCED_RLS_OWNER_DRIFT_HOLD';
  END IF;
  SELECT count(*) INTO v_role_memberships
    FROM pg_catalog.pg_auth_members m
    JOIN pg_catalog.pg_roles a ON a.oid=m.member
    JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
   WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner'
     AND m.admin_option AND NOT m.inherit_option AND NOT m.set_option;
  IF v_role_memberships <> 1
     OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles a ON a.oid=m.member
          JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
          WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner') <> 1
     OR pg_catalog.pg_has_role('postgres','v3_cas_audit_table_owner','SET')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','INSERT')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','UPDATE') THEN
    RAISE EXCEPTION 'V3_STAGE4_ORIGINAL_ADMIN_PRIVILEGE_ESCROW_NOT_CLEAN_HOLD';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_roles
      WHERE rolname IN ('v3_cas_audit_writer_actor','v3_cas_audit_reader_actor')
        AND rolcanlogin AND rolconnlimit=1 AND NOT rolbypassrls) <> 2
     OR (SELECT count(*) FROM pg_catalog.pg_roles
         WHERE rolname='v3_cas_executor_actor' AND NOT rolcanlogin
           AND rolconnlimit=0) <> 1 THEN
    RAISE EXCEPTION 'V3_STAGE4_ACTOR_STATE_DRIFT_HOLD';
  END IF;
END $v3_stage4_preflight$;

-- The original PostgreSQL 17 CREATEROLE owner-admin membership is
-- ADMIN TRUE, INHERIT FALSE, SET FALSE. A temporary grant from postgres
-- must NOT replace the preexisting bootstrap edge.
GRANT v3_cas_audit_table_owner TO postgres WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;
SET ROLE v3_cas_audit_table_owner;
GRANT INSERT ON v3_cas_audit.epoch_v1 TO postgres;
RESET ROLE;

-- PostgreSQL postgres BYPASSRLS can INSERT only with explicit object ACL.
-- Source/fence fingerprints must originate from approved ORIGINAL receipts.
INSERT INTO v3_cas_audit.epoch_v1
  (epoch_id,predecessor_series_id,expected_rpc,source_sha256,
   original_fence_sha256,approved_caller_acl_sha256)
VALUES
  (current_setting('v3_stage4.epoch_id',true),'PAPER-V2R4-20261009T110135Z',
   'public.rotate_v2r4_to_v3_experimental_paper',
   current_setting('v3_stage4.source_sha256',true),current_setting('v3_stage4.fence_sha256',true),current_setting('v3_stage4.caller_acl_sha256',true));

-- Restore direct privilege and temporary membership IN THE SAME transaction.
SET ROLE v3_cas_audit_table_owner;
REVOKE INSERT ON v3_cas_audit.epoch_v1 FROM postgres;
RESET ROLE;
REVOKE v3_cas_audit_table_owner FROM postgres GRANTED BY postgres;

DO $v3_stage4_postflight$
BEGIN
  IF pg_catalog.pg_has_role('postgres','v3_cas_audit_table_owner','SET')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','INSERT')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','UPDATE')
     OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles a ON a.oid=m.member
          JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
          WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner'
            AND m.admin_option AND NOT m.inherit_option AND NOT m.set_option) <> 1
     OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles a ON a.oid=m.member
          JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
          WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner') <> 1 THEN
    RAISE EXCEPTION 'V3_STAGE4_TEMPORARY_PRIVILEGE_NOT_FULLY_RESTORED_HOLD';
  END IF;
  IF (SELECT count(*) FROM v3_cas_audit.epoch_v1
          WHERE epoch_id=current_setting('v3_stage4.epoch_id',true)
            AND source_sha256=current_setting('v3_stage4.source_sha256',true)
            AND original_fence_sha256=current_setting('v3_stage4.fence_sha256',true)
            AND approved_caller_acl_sha256=current_setting('v3_stage4.caller_acl_sha256',true)
            AND predecessor_series_id='PAPER-V2R4-20261009T110135Z'
            AND expected_rpc='public.rotate_v2r4_to_v3_experimental_paper'
            AND next_ordinal=1 AND NOT sealed) <> 1
     OR (SELECT count(*) FROM v3_cas_audit.epoch_v1) <> 1
     OR (SELECT count(*) FROM v3_cas_audit.intent_v1) <> 0 THEN
    RAISE EXCEPTION 'V3_STAGE4_EPOCH_UNEXPECTED_ROWS_OR_SOURCE_HOLD';
  END IF;
END $v3_stage4_postflight$;
COMMIT;
-- Even an actual original Stage4 COMMIT does NOT authorize CAS or native stop.
-- Stage5: separately authorized append writer transaction and after-COMMIT
-- independent reader; subsequent seal and executor/No-Rearm gates still OPEN.

    OR current_setting('v3_stage4.runtime_release_commit',true) IS DISTINCT FROM 'ebb39488530d9c032e082ca7ab4ae8d3e1f0a719'
    OR current_setting('v3_stage4.successor_series_id',true) IS DISTINCT FROM 'PAPER-V3-20261104T133710Z'
    OR current_setting('v3_stage4.bundle_sha256',true) IS DISTINCT FROM '443ae85e299828c4c2e3779d6e2fb80aeb9a0b7966b7f6923f91524c35fdfc67'
    OR current_setting('v3_stage4.strategy_sha256',true) IS DISTINCT FROM 'aaef6e75e91b2825f194393dbb7de57e26097fd22397629b898f8c69541b0f6a'
    OR current_setting('v3_stage4.epoch_id',true) !~ '^V3CAS-AUDIT-[a-f0-9]{32}

DO $v3_stage4_preflight$
DECLARE
  v_role_memberships integer;
BEGIN
  IF current_user <> 'postgres'
     OR current_database() <> 'postgres'
     OR NOT (SELECT NOT rolsuper AND rolcreaterole AND rolbypassrls
             FROM pg_catalog.pg_roles WHERE rolname='postgres') THEN
    RAISE EXCEPTION 'V3_STAGE4_ORIGINAL_ADMIN_IDENTITY_HOLD';
  END IF;
  IF current_setting('v3_stage4.epoch_id',true) !~ '^V3CAS-AUDIT-[a-f0-9]{32}$'
     OR current_setting('v3_stage4.source_sha256',true) !~ '^[a-f0-9]{64}$'
     OR current_setting('v3_stage4.fence_sha256',true) !~ '^[a-f0-9]{64}$'
     OR current_setting('v3_stage4.caller_acl_sha256',true) !~ '^[a-f0-9]{64}$' THEN
    RAISE EXCEPTION 'V3_STAGE4_ORIGINAL_FINGERPRINTS_MISSING_HOLD';
  END IF;
  IF (SELECT count(*) FROM public.paper_series WHERE status='active') <> 1
     OR (SELECT count(*) FROM public.paper_series WHERE status='active'
             AND series_id='PAPER-V2R4-20261009T110135Z') <> 1 THEN
    RAISE EXCEPTION 'V3_STAGE4_WRONG_ACTIVE_ORIGINAL_PAPER_HOLD';
  END IF;
  IF to_regprocedure(
       'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
     ) IS NOT NULL THEN
    RAISE EXCEPTION 'V3_STAGE4_CAS_ALREADY_EXISTS_HOLD';
  END IF;
  IF to_regclass('v3_cas_audit.epoch_v1') IS NULL
     OR to_regclass('v3_cas_audit.intent_v1') IS NULL
     OR (SELECT count(*) FROM v3_cas_audit.epoch_v1) <> 0
     OR (SELECT count(*) FROM v3_cas_audit.intent_v1) <> 0 THEN
    RAISE EXCEPTION 'V3_STAGE4_EXISTING_AUDIT_EPOCH_OR_INTENT_HOLD';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace ns
      ON c.relnamespace=ns.oid WHERE ns.nspname='v3_cas_audit'
       AND c.relname IN ('epoch_v1','intent_v1')
       AND c.relrowsecurity AND c.relforcerowsecurity
       AND pg_catalog.pg_get_userbyid(c.relowner)='v3_cas_audit_table_owner') <> 2 THEN
    RAISE EXCEPTION 'V3_STAGE4_PRIVATE_FORCED_RLS_OWNER_DRIFT_HOLD';
  END IF;
  SELECT count(*) INTO v_role_memberships
    FROM pg_catalog.pg_auth_members m
    JOIN pg_catalog.pg_roles a ON a.oid=m.member
    JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
   WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner'
     AND m.admin_option AND NOT m.inherit_option AND NOT m.set_option;
  IF v_role_memberships <> 1
     OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles a ON a.oid=m.member
          JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
          WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner') <> 1
     OR pg_catalog.pg_has_role('postgres','v3_cas_audit_table_owner','SET')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','INSERT')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','UPDATE') THEN
    RAISE EXCEPTION 'V3_STAGE4_ORIGINAL_ADMIN_PRIVILEGE_ESCROW_NOT_CLEAN_HOLD';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_roles
      WHERE rolname IN ('v3_cas_audit_writer_actor','v3_cas_audit_reader_actor')
        AND rolcanlogin AND rolconnlimit=1 AND NOT rolbypassrls) <> 2
     OR (SELECT count(*) FROM pg_catalog.pg_roles
         WHERE rolname='v3_cas_executor_actor' AND NOT rolcanlogin
           AND rolconnlimit=0) <> 1 THEN
    RAISE EXCEPTION 'V3_STAGE4_ACTOR_STATE_DRIFT_HOLD';
  END IF;
END $v3_stage4_preflight$;

-- The original PostgreSQL 17 CREATEROLE owner-admin membership is
-- ADMIN TRUE, INHERIT FALSE, SET FALSE. A temporary grant from postgres
-- must NOT replace the preexisting bootstrap edge.
GRANT v3_cas_audit_table_owner TO postgres WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;
SET ROLE v3_cas_audit_table_owner;
GRANT INSERT ON v3_cas_audit.epoch_v1 TO postgres;
RESET ROLE;

-- PostgreSQL postgres BYPASSRLS can INSERT only with explicit object ACL.
-- Source/fence fingerprints must originate from approved ORIGINAL receipts.
INSERT INTO v3_cas_audit.epoch_v1
  (epoch_id,predecessor_series_id,expected_rpc,source_sha256,
   original_fence_sha256,approved_caller_acl_sha256)
VALUES
  (current_setting('v3_stage4.epoch_id',true),'PAPER-V2R4-20261009T110135Z',
   'public.rotate_v2r4_to_v3_experimental_paper',
   current_setting('v3_stage4.source_sha256',true),current_setting('v3_stage4.fence_sha256',true),current_setting('v3_stage4.caller_acl_sha256',true));

-- Restore direct privilege and temporary membership IN THE SAME transaction.
SET ROLE v3_cas_audit_table_owner;
REVOKE INSERT ON v3_cas_audit.epoch_v1 FROM postgres;
RESET ROLE;
REVOKE v3_cas_audit_table_owner FROM postgres GRANTED BY postgres;

DO $v3_stage4_postflight$
BEGIN
  IF pg_catalog.pg_has_role('postgres','v3_cas_audit_table_owner','SET')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','INSERT')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','UPDATE')
     OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles a ON a.oid=m.member
          JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
          WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner'
            AND m.admin_option AND NOT m.inherit_option AND NOT m.set_option) <> 1
     OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles a ON a.oid=m.member
          JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
          WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner') <> 1 THEN
    RAISE EXCEPTION 'V3_STAGE4_TEMPORARY_PRIVILEGE_NOT_FULLY_RESTORED_HOLD';
  END IF;
  IF (SELECT count(*) FROM v3_cas_audit.epoch_v1
          WHERE epoch_id=current_setting('v3_stage4.epoch_id',true)
            AND source_sha256=current_setting('v3_stage4.source_sha256',true)
            AND original_fence_sha256=current_setting('v3_stage4.fence_sha256',true)
            AND approved_caller_acl_sha256=current_setting('v3_stage4.caller_acl_sha256',true)
            AND predecessor_series_id='PAPER-V2R4-20261009T110135Z'
            AND expected_rpc='public.rotate_v2r4_to_v3_experimental_paper'
            AND next_ordinal=1 AND NOT sealed) <> 1
     OR (SELECT count(*) FROM v3_cas_audit.epoch_v1) <> 1
     OR (SELECT count(*) FROM v3_cas_audit.intent_v1) <> 0 THEN
    RAISE EXCEPTION 'V3_STAGE4_EPOCH_UNEXPECTED_ROWS_OR_SOURCE_HOLD';
  END IF;
END $v3_stage4_postflight$;
COMMIT;
-- Even an actual original Stage4 COMMIT does NOT authorize CAS or native stop.
-- Stage5: separately authorized append writer transaction and after-COMMIT
-- independent reader; subsequent seal and executor/No-Rearm gates still OPEN.

    OR current_setting('v3_stage4.source_sha256',true) !~ '^[a-f0-9]{64}

DO $v3_stage4_preflight$
DECLARE
  v_role_memberships integer;
BEGIN
  IF current_user <> 'postgres'
     OR current_database() <> 'postgres'
     OR NOT (SELECT NOT rolsuper AND rolcreaterole AND rolbypassrls
             FROM pg_catalog.pg_roles WHERE rolname='postgres') THEN
    RAISE EXCEPTION 'V3_STAGE4_ORIGINAL_ADMIN_IDENTITY_HOLD';
  END IF;
  IF current_setting('v3_stage4.epoch_id',true) !~ '^V3CAS-AUDIT-[a-f0-9]{32}$'
     OR current_setting('v3_stage4.source_sha256',true) !~ '^[a-f0-9]{64}$'
     OR current_setting('v3_stage4.fence_sha256',true) !~ '^[a-f0-9]{64}$'
     OR current_setting('v3_stage4.caller_acl_sha256',true) !~ '^[a-f0-9]{64}$' THEN
    RAISE EXCEPTION 'V3_STAGE4_ORIGINAL_FINGERPRINTS_MISSING_HOLD';
  END IF;
  IF (SELECT count(*) FROM public.paper_series WHERE status='active') <> 1
     OR (SELECT count(*) FROM public.paper_series WHERE status='active'
             AND series_id='PAPER-V2R4-20261009T110135Z') <> 1 THEN
    RAISE EXCEPTION 'V3_STAGE4_WRONG_ACTIVE_ORIGINAL_PAPER_HOLD';
  END IF;
  IF to_regprocedure(
       'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
     ) IS NOT NULL THEN
    RAISE EXCEPTION 'V3_STAGE4_CAS_ALREADY_EXISTS_HOLD';
  END IF;
  IF to_regclass('v3_cas_audit.epoch_v1') IS NULL
     OR to_regclass('v3_cas_audit.intent_v1') IS NULL
     OR (SELECT count(*) FROM v3_cas_audit.epoch_v1) <> 0
     OR (SELECT count(*) FROM v3_cas_audit.intent_v1) <> 0 THEN
    RAISE EXCEPTION 'V3_STAGE4_EXISTING_AUDIT_EPOCH_OR_INTENT_HOLD';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace ns
      ON c.relnamespace=ns.oid WHERE ns.nspname='v3_cas_audit'
       AND c.relname IN ('epoch_v1','intent_v1')
       AND c.relrowsecurity AND c.relforcerowsecurity
       AND pg_catalog.pg_get_userbyid(c.relowner)='v3_cas_audit_table_owner') <> 2 THEN
    RAISE EXCEPTION 'V3_STAGE4_PRIVATE_FORCED_RLS_OWNER_DRIFT_HOLD';
  END IF;
  SELECT count(*) INTO v_role_memberships
    FROM pg_catalog.pg_auth_members m
    JOIN pg_catalog.pg_roles a ON a.oid=m.member
    JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
   WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner'
     AND m.admin_option AND NOT m.inherit_option AND NOT m.set_option;
  IF v_role_memberships <> 1
     OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles a ON a.oid=m.member
          JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
          WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner') <> 1
     OR pg_catalog.pg_has_role('postgres','v3_cas_audit_table_owner','SET')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','INSERT')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','UPDATE') THEN
    RAISE EXCEPTION 'V3_STAGE4_ORIGINAL_ADMIN_PRIVILEGE_ESCROW_NOT_CLEAN_HOLD';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_roles
      WHERE rolname IN ('v3_cas_audit_writer_actor','v3_cas_audit_reader_actor')
        AND rolcanlogin AND rolconnlimit=1 AND NOT rolbypassrls) <> 2
     OR (SELECT count(*) FROM pg_catalog.pg_roles
         WHERE rolname='v3_cas_executor_actor' AND NOT rolcanlogin
           AND rolconnlimit=0) <> 1 THEN
    RAISE EXCEPTION 'V3_STAGE4_ACTOR_STATE_DRIFT_HOLD';
  END IF;
END $v3_stage4_preflight$;

-- The original PostgreSQL 17 CREATEROLE owner-admin membership is
-- ADMIN TRUE, INHERIT FALSE, SET FALSE. A temporary grant from postgres
-- must NOT replace the preexisting bootstrap edge.
GRANT v3_cas_audit_table_owner TO postgres WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;
SET ROLE v3_cas_audit_table_owner;
GRANT INSERT ON v3_cas_audit.epoch_v1 TO postgres;
RESET ROLE;

-- PostgreSQL postgres BYPASSRLS can INSERT only with explicit object ACL.
-- Source/fence fingerprints must originate from approved ORIGINAL receipts.
INSERT INTO v3_cas_audit.epoch_v1
  (epoch_id,predecessor_series_id,expected_rpc,source_sha256,
   original_fence_sha256,approved_caller_acl_sha256)
VALUES
  (current_setting('v3_stage4.epoch_id',true),'PAPER-V2R4-20261009T110135Z',
   'public.rotate_v2r4_to_v3_experimental_paper',
   current_setting('v3_stage4.source_sha256',true),current_setting('v3_stage4.fence_sha256',true),current_setting('v3_stage4.caller_acl_sha256',true));

-- Restore direct privilege and temporary membership IN THE SAME transaction.
SET ROLE v3_cas_audit_table_owner;
REVOKE INSERT ON v3_cas_audit.epoch_v1 FROM postgres;
RESET ROLE;
REVOKE v3_cas_audit_table_owner FROM postgres GRANTED BY postgres;

DO $v3_stage4_postflight$
BEGIN
  IF pg_catalog.pg_has_role('postgres','v3_cas_audit_table_owner','SET')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','INSERT')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','UPDATE')
     OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles a ON a.oid=m.member
          JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
          WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner'
            AND m.admin_option AND NOT m.inherit_option AND NOT m.set_option) <> 1
     OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles a ON a.oid=m.member
          JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
          WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner') <> 1 THEN
    RAISE EXCEPTION 'V3_STAGE4_TEMPORARY_PRIVILEGE_NOT_FULLY_RESTORED_HOLD';
  END IF;
  IF (SELECT count(*) FROM v3_cas_audit.epoch_v1
          WHERE epoch_id=current_setting('v3_stage4.epoch_id',true)
            AND source_sha256=current_setting('v3_stage4.source_sha256',true)
            AND original_fence_sha256=current_setting('v3_stage4.fence_sha256',true)
            AND approved_caller_acl_sha256=current_setting('v3_stage4.caller_acl_sha256',true)
            AND predecessor_series_id='PAPER-V2R4-20261009T110135Z'
            AND expected_rpc='public.rotate_v2r4_to_v3_experimental_paper'
            AND next_ordinal=1 AND NOT sealed) <> 1
     OR (SELECT count(*) FROM v3_cas_audit.epoch_v1) <> 1
     OR (SELECT count(*) FROM v3_cas_audit.intent_v1) <> 0 THEN
    RAISE EXCEPTION 'V3_STAGE4_EPOCH_UNEXPECTED_ROWS_OR_SOURCE_HOLD';
  END IF;
END $v3_stage4_postflight$;
COMMIT;
-- Even an actual original Stage4 COMMIT does NOT authorize CAS or native stop.
-- Stage5: separately authorized append writer transaction and after-COMMIT
-- independent reader; subsequent seal and executor/No-Rearm gates still OPEN.

    OR current_setting('v3_stage4.fence_sha256',true) IS DISTINCT FROM '36452e8fff4a9d7020eb39545dbd258fed880e00928a84a615c819e14b167e35'
    OR current_setting('v3_stage4.caller_acl_sha256',true) !~ '^[a-f0-9]{64}

DO $v3_stage4_preflight$
DECLARE
  v_role_memberships integer;
BEGIN
  IF current_user <> 'postgres'
     OR current_database() <> 'postgres'
     OR NOT (SELECT NOT rolsuper AND rolcreaterole AND rolbypassrls
             FROM pg_catalog.pg_roles WHERE rolname='postgres') THEN
    RAISE EXCEPTION 'V3_STAGE4_ORIGINAL_ADMIN_IDENTITY_HOLD';
  END IF;
  IF current_setting('v3_stage4.epoch_id',true) !~ '^V3CAS-AUDIT-[a-f0-9]{32}$'
     OR current_setting('v3_stage4.source_sha256',true) !~ '^[a-f0-9]{64}$'
     OR current_setting('v3_stage4.fence_sha256',true) !~ '^[a-f0-9]{64}$'
     OR current_setting('v3_stage4.caller_acl_sha256',true) !~ '^[a-f0-9]{64}$' THEN
    RAISE EXCEPTION 'V3_STAGE4_ORIGINAL_FINGERPRINTS_MISSING_HOLD';
  END IF;
  IF (SELECT count(*) FROM public.paper_series WHERE status='active') <> 1
     OR (SELECT count(*) FROM public.paper_series WHERE status='active'
             AND series_id='PAPER-V2R4-20261009T110135Z') <> 1 THEN
    RAISE EXCEPTION 'V3_STAGE4_WRONG_ACTIVE_ORIGINAL_PAPER_HOLD';
  END IF;
  IF to_regprocedure(
       'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
     ) IS NOT NULL THEN
    RAISE EXCEPTION 'V3_STAGE4_CAS_ALREADY_EXISTS_HOLD';
  END IF;
  IF to_regclass('v3_cas_audit.epoch_v1') IS NULL
     OR to_regclass('v3_cas_audit.intent_v1') IS NULL
     OR (SELECT count(*) FROM v3_cas_audit.epoch_v1) <> 0
     OR (SELECT count(*) FROM v3_cas_audit.intent_v1) <> 0 THEN
    RAISE EXCEPTION 'V3_STAGE4_EXISTING_AUDIT_EPOCH_OR_INTENT_HOLD';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace ns
      ON c.relnamespace=ns.oid WHERE ns.nspname='v3_cas_audit'
       AND c.relname IN ('epoch_v1','intent_v1')
       AND c.relrowsecurity AND c.relforcerowsecurity
       AND pg_catalog.pg_get_userbyid(c.relowner)='v3_cas_audit_table_owner') <> 2 THEN
    RAISE EXCEPTION 'V3_STAGE4_PRIVATE_FORCED_RLS_OWNER_DRIFT_HOLD';
  END IF;
  SELECT count(*) INTO v_role_memberships
    FROM pg_catalog.pg_auth_members m
    JOIN pg_catalog.pg_roles a ON a.oid=m.member
    JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
   WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner'
     AND m.admin_option AND NOT m.inherit_option AND NOT m.set_option;
  IF v_role_memberships <> 1
     OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles a ON a.oid=m.member
          JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
          WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner') <> 1
     OR pg_catalog.pg_has_role('postgres','v3_cas_audit_table_owner','SET')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','INSERT')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','UPDATE') THEN
    RAISE EXCEPTION 'V3_STAGE4_ORIGINAL_ADMIN_PRIVILEGE_ESCROW_NOT_CLEAN_HOLD';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_roles
      WHERE rolname IN ('v3_cas_audit_writer_actor','v3_cas_audit_reader_actor')
        AND rolcanlogin AND rolconnlimit=1 AND NOT rolbypassrls) <> 2
     OR (SELECT count(*) FROM pg_catalog.pg_roles
         WHERE rolname='v3_cas_executor_actor' AND NOT rolcanlogin
           AND rolconnlimit=0) <> 1 THEN
    RAISE EXCEPTION 'V3_STAGE4_ACTOR_STATE_DRIFT_HOLD';
  END IF;
END $v3_stage4_preflight$;

-- The original PostgreSQL 17 CREATEROLE owner-admin membership is
-- ADMIN TRUE, INHERIT FALSE, SET FALSE. A temporary grant from postgres
-- must NOT replace the preexisting bootstrap edge.
GRANT v3_cas_audit_table_owner TO postgres WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;
SET ROLE v3_cas_audit_table_owner;
GRANT INSERT ON v3_cas_audit.epoch_v1 TO postgres;
RESET ROLE;

-- PostgreSQL postgres BYPASSRLS can INSERT only with explicit object ACL.
-- Source/fence fingerprints must originate from approved ORIGINAL receipts.
INSERT INTO v3_cas_audit.epoch_v1
  (epoch_id,predecessor_series_id,expected_rpc,source_sha256,
   original_fence_sha256,approved_caller_acl_sha256)
VALUES
  (current_setting('v3_stage4.epoch_id',true),'PAPER-V2R4-20261009T110135Z',
   'public.rotate_v2r4_to_v3_experimental_paper',
   current_setting('v3_stage4.source_sha256',true),current_setting('v3_stage4.fence_sha256',true),current_setting('v3_stage4.caller_acl_sha256',true));

-- Restore direct privilege and temporary membership IN THE SAME transaction.
SET ROLE v3_cas_audit_table_owner;
REVOKE INSERT ON v3_cas_audit.epoch_v1 FROM postgres;
RESET ROLE;
REVOKE v3_cas_audit_table_owner FROM postgres GRANTED BY postgres;

DO $v3_stage4_postflight$
BEGIN
  IF pg_catalog.pg_has_role('postgres','v3_cas_audit_table_owner','SET')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','INSERT')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','UPDATE')
     OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles a ON a.oid=m.member
          JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
          WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner'
            AND m.admin_option AND NOT m.inherit_option AND NOT m.set_option) <> 1
     OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles a ON a.oid=m.member
          JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
          WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner') <> 1 THEN
    RAISE EXCEPTION 'V3_STAGE4_TEMPORARY_PRIVILEGE_NOT_FULLY_RESTORED_HOLD';
  END IF;
  IF (SELECT count(*) FROM v3_cas_audit.epoch_v1
          WHERE epoch_id=current_setting('v3_stage4.epoch_id',true)
            AND source_sha256=current_setting('v3_stage4.source_sha256',true)
            AND original_fence_sha256=current_setting('v3_stage4.fence_sha256',true)
            AND approved_caller_acl_sha256=current_setting('v3_stage4.caller_acl_sha256',true)
            AND predecessor_series_id='PAPER-V2R4-20261009T110135Z'
            AND expected_rpc='public.rotate_v2r4_to_v3_experimental_paper'
            AND next_ordinal=1 AND NOT sealed) <> 1
     OR (SELECT count(*) FROM v3_cas_audit.epoch_v1) <> 1
     OR (SELECT count(*) FROM v3_cas_audit.intent_v1) <> 0 THEN
    RAISE EXCEPTION 'V3_STAGE4_EPOCH_UNEXPECTED_ROWS_OR_SOURCE_HOLD';
  END IF;
END $v3_stage4_postflight$;
COMMIT;
-- Even an actual original Stage4 COMMIT does NOT authorize CAS or native stop.
-- Stage5: separately authorized append writer transaction and after-COMMIT
-- independent reader; subsequent seal and executor/No-Rearm gates still OPEN.

    OR clock_timestamp() >= current_setting('v3_stage4.expires_at',true)::timestamptz
 THEN RAISE EXCEPTION 'V3_STAGE4_EPOCH_ONE_TIME_SIGNED_RELEASE_GATE_HOLD'; END IF;
END
$v3_stage4_release_gate$;

DO $v3_stage4_preflight$
DECLARE
  v_role_memberships integer;
BEGIN
  IF current_user <> 'postgres'
     OR current_database() <> 'postgres'
     OR NOT (SELECT NOT rolsuper AND rolcreaterole AND rolbypassrls
             FROM pg_catalog.pg_roles WHERE rolname='postgres') THEN
    RAISE EXCEPTION 'V3_STAGE4_ORIGINAL_ADMIN_IDENTITY_HOLD';
  END IF;
  IF current_setting('v3_stage4.epoch_id',true) !~ '^V3CAS-AUDIT-[a-f0-9]{32}$'
     OR current_setting('v3_stage4.source_sha256',true) !~ '^[a-f0-9]{64}$'
     OR current_setting('v3_stage4.fence_sha256',true) !~ '^[a-f0-9]{64}$'
     OR current_setting('v3_stage4.caller_acl_sha256',true) !~ '^[a-f0-9]{64}$' THEN
    RAISE EXCEPTION 'V3_STAGE4_ORIGINAL_FINGERPRINTS_MISSING_HOLD';
  END IF;
  IF (SELECT count(*) FROM public.paper_series WHERE status='active') <> 1
     OR (SELECT count(*) FROM public.paper_series WHERE status='active'
             AND series_id='PAPER-V2R4-20261009T110135Z') <> 1 THEN
    RAISE EXCEPTION 'V3_STAGE4_WRONG_ACTIVE_ORIGINAL_PAPER_HOLD';
  END IF;
  IF to_regprocedure(
       'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
     ) IS NOT NULL THEN
    RAISE EXCEPTION 'V3_STAGE4_CAS_ALREADY_EXISTS_HOLD';
  END IF;
  IF to_regclass('v3_cas_audit.epoch_v1') IS NULL
     OR to_regclass('v3_cas_audit.intent_v1') IS NULL
     OR (SELECT count(*) FROM v3_cas_audit.epoch_v1) <> 0
     OR (SELECT count(*) FROM v3_cas_audit.intent_v1) <> 0 THEN
    RAISE EXCEPTION 'V3_STAGE4_EXISTING_AUDIT_EPOCH_OR_INTENT_HOLD';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace ns
      ON c.relnamespace=ns.oid WHERE ns.nspname='v3_cas_audit'
       AND c.relname IN ('epoch_v1','intent_v1')
       AND c.relrowsecurity AND c.relforcerowsecurity
       AND pg_catalog.pg_get_userbyid(c.relowner)='v3_cas_audit_table_owner') <> 2 THEN
    RAISE EXCEPTION 'V3_STAGE4_PRIVATE_FORCED_RLS_OWNER_DRIFT_HOLD';
  END IF;
  SELECT count(*) INTO v_role_memberships
    FROM pg_catalog.pg_auth_members m
    JOIN pg_catalog.pg_roles a ON a.oid=m.member
    JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
   WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner'
     AND m.admin_option AND NOT m.inherit_option AND NOT m.set_option;
  IF v_role_memberships <> 1
     OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles a ON a.oid=m.member
          JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
          WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner') <> 1
     OR pg_catalog.pg_has_role('postgres','v3_cas_audit_table_owner','SET')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','INSERT')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','UPDATE') THEN
    RAISE EXCEPTION 'V3_STAGE4_ORIGINAL_ADMIN_PRIVILEGE_ESCROW_NOT_CLEAN_HOLD';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_roles
      WHERE rolname IN ('v3_cas_audit_writer_actor','v3_cas_audit_reader_actor')
        AND rolcanlogin AND rolconnlimit=1 AND NOT rolbypassrls) <> 2
     OR (SELECT count(*) FROM pg_catalog.pg_roles
         WHERE rolname='v3_cas_executor_actor' AND NOT rolcanlogin
           AND rolconnlimit=0) <> 1 THEN
    RAISE EXCEPTION 'V3_STAGE4_ACTOR_STATE_DRIFT_HOLD';
  END IF;
END $v3_stage4_preflight$;

-- The original PostgreSQL 17 CREATEROLE owner-admin membership is
-- ADMIN TRUE, INHERIT FALSE, SET FALSE. A temporary grant from postgres
-- must NOT replace the preexisting bootstrap edge.
GRANT v3_cas_audit_table_owner TO postgres WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;
SET ROLE v3_cas_audit_table_owner;
GRANT INSERT ON v3_cas_audit.epoch_v1 TO postgres;
RESET ROLE;

-- PostgreSQL postgres BYPASSRLS can INSERT only with explicit object ACL.
-- Source/fence fingerprints must originate from approved ORIGINAL receipts.
INSERT INTO v3_cas_audit.epoch_v1
  (epoch_id,predecessor_series_id,expected_rpc,source_sha256,
   original_fence_sha256,approved_caller_acl_sha256)
VALUES
  (current_setting('v3_stage4.epoch_id',true),'PAPER-V2R4-20261009T110135Z',
   'public.rotate_v2r4_to_v3_experimental_paper',
   current_setting('v3_stage4.source_sha256',true),current_setting('v3_stage4.fence_sha256',true),current_setting('v3_stage4.caller_acl_sha256',true));

-- Restore direct privilege and temporary membership IN THE SAME transaction.
SET ROLE v3_cas_audit_table_owner;
REVOKE INSERT ON v3_cas_audit.epoch_v1 FROM postgres;
RESET ROLE;
REVOKE v3_cas_audit_table_owner FROM postgres GRANTED BY postgres;

DO $v3_stage4_postflight$
BEGIN
  IF pg_catalog.pg_has_role('postgres','v3_cas_audit_table_owner','SET')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','INSERT')
     OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','UPDATE')
     OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles a ON a.oid=m.member
          JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
          WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner'
            AND m.admin_option AND NOT m.inherit_option AND NOT m.set_option) <> 1
     OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles a ON a.oid=m.member
          JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
          WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner') <> 1 THEN
    RAISE EXCEPTION 'V3_STAGE4_TEMPORARY_PRIVILEGE_NOT_FULLY_RESTORED_HOLD';
  END IF;
  IF (SELECT count(*) FROM v3_cas_audit.epoch_v1
          WHERE epoch_id=current_setting('v3_stage4.epoch_id',true)
            AND source_sha256=current_setting('v3_stage4.source_sha256',true)
            AND original_fence_sha256=current_setting('v3_stage4.fence_sha256',true)
            AND approved_caller_acl_sha256=current_setting('v3_stage4.caller_acl_sha256',true)
            AND predecessor_series_id='PAPER-V2R4-20261009T110135Z'
            AND expected_rpc='public.rotate_v2r4_to_v3_experimental_paper'
            AND next_ordinal=1 AND NOT sealed) <> 1
     OR (SELECT count(*) FROM v3_cas_audit.epoch_v1) <> 1
     OR (SELECT count(*) FROM v3_cas_audit.intent_v1) <> 0 THEN
    RAISE EXCEPTION 'V3_STAGE4_EPOCH_UNEXPECTED_ROWS_OR_SOURCE_HOLD';
  END IF;
END $v3_stage4_postflight$;
COMMIT;
-- Even an actual original Stage4 COMMIT does NOT authorize CAS or native stop.
-- Stage5: separately authorized append writer transaction and after-COMMIT
-- independent reader; subsequent seal and executor/No-Rearm gates still OPEN.
