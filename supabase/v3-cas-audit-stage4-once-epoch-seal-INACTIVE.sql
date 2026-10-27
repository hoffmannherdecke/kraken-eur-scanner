-- V3 Paper original V2R4->V3 Stage4 / SEAL source / INACTIVE.
-- CAUTION: sealing is NOT an external post-COMMIT reader attestation.
-- Must not be rendered/executed until separately verified real external Writer
-- COMMIT + authenticated independent Reader + original owner no-rearm scope.
-- The template cannot run without removing one hard lock in isolated CI.
-- Supabase original MUST remain unchanged during source-review/CI.
BEGIN;
DO $v3_stage4_seal_source_lock$
BEGIN
 RAISE EXCEPTION 'V3_STAGE4_EPOCH_SEAL_SOURCE_INACTIVE_APPROVAL_REQUIRED';
END $v3_stage4_seal_source_lock$;
DO $v3_stage4_seal_preflight$
DECLARE
 v_id text := '__V3_STAGE4_EPOCH_ID__';
 v_intent uuid := '__V3_STAGE4_INTENT_UUID__';
 v_request text := '__V3_STAGE4_REQUEST_SHA256__';
 v_source text := '__V3_STAGE4_SOURCE_SHA256__';
 v_fence text := '__V3_STAGE4_ORIGINAL_FENCE_SHA256__';
 v_acl text := '__V3_STAGE4_CALLER_ACL_SHA256__';
BEGIN
 IF current_user <> 'postgres'
    OR (SELECT count(*) FROM pg_catalog.pg_roles
        WHERE rolname='postgres' AND NOT rolsuper AND rolcreaterole
          AND rolbypassrls) <> 1 THEN
  RAISE EXCEPTION 'V3_STAGE4_SEAL_NOT_ORIGINAL_PG17_ADMIN_HOLD';
 END IF;
 IF v_id !~ '^V3CAS-AUDIT-[a-f0-9]{32}$'
    OR v_request !~ '^[a-f0-9]{64}$'
    OR v_source !~ '^[a-f0-9]{64}$'
    OR v_fence !~ '^[a-f0-9]{64}$'
    OR v_acl !~ '^[a-f0-9]{64}$' THEN
  RAISE EXCEPTION 'V3_STAGE4_SEAL_UNBOUND_DIGEST_HOLD';
 END IF;
 IF (SELECT count(*) FROM public.paper_series WHERE status='active') <> 1
    OR (SELECT count(*) FROM public.paper_series
        WHERE status='active' AND series_id='PAPER-V2R4-20261009T110135Z') <> 1
    OR (SELECT count(*) FROM v3_cas_audit.epoch_v1) <> 1
    OR (SELECT count(*) FROM v3_cas_audit.intent_v1) <> 1
    OR pg_catalog.to_regprocedure(
      'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
      ) IS NOT NULL THEN
  RAISE EXCEPTION 'V3_STAGE4_SEAL_UNEXPECTED_SERIES_AUDIT_OR_CAS_HOLD';
 END IF;
 IF (SELECT count(*) FROM v3_cas_audit.epoch_v1 e
     JOIN v3_cas_audit.intent_v1 i ON i.epoch_id=e.epoch_id
     WHERE e.epoch_id=v_id AND NOT e.sealed AND e.next_ordinal=2
       AND e.predecessor_series_id='PAPER-V2R4-20261009T110135Z'
       AND e.expected_rpc='public.rotate_v2r4_to_v3_experimental_paper'
       AND e.source_sha256=v_source
       AND e.original_fence_sha256=v_fence
       AND e.approved_caller_acl_sha256=v_acl
       AND i.ordinal=1 AND i.intent_id=v_intent
       AND i.predecessor_series_id=e.predecessor_series_id
       AND i.requested_rpc=e.expected_rpc
       AND i.request_sha256=v_request
       AND i.source_sha256=e.source_sha256
       AND i.fence_sha256=e.original_fence_sha256
       AND i.state='PREINVOKE_INTENT'
       AND i.created_at_utc>=e.opened_at_utc
       AND i.created_at_utc<=pg_catalog.clock_timestamp()
       AND i.created_at_utc>pg_catalog.clock_timestamp()-interval '5 minutes'
   ) <> 1 THEN
  RAISE EXCEPTION 'V3_STAGE4_SEAL_DURABLE_EXACT_INTENT_NOT_VISIBLE_HOLD';
 END IF;
 IF (SELECT count(*) FROM pg_catalog.pg_auth_members m
      JOIN pg_catalog.pg_roles a ON a.oid=m.member
      JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
      WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner'
        AND m.admin_option AND NOT m.set_option AND NOT m.inherit_option) <> 1
    OR pg_catalog.pg_has_role('postgres','v3_cas_audit_table_owner','SET')
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
  RAISE EXCEPTION 'V3_STAGE4_SEAL_OWNER_RLS_OR_ROLE_DRIFT_HOLD';
 END IF;
END $v3_stage4_seal_preflight$;
-- A single transaction: no committed residual owner membership/table UPDATE.
GRANT v3_cas_audit_table_owner TO postgres
 WITH ADMIN FALSE, INHERIT FALSE, SET TRUE;
SET LOCAL ROLE v3_cas_audit_table_owner;
GRANT UPDATE (sealed) ON v3_cas_audit.epoch_v1 TO postgres;
RESET ROLE;
UPDATE v3_cas_audit.epoch_v1 SET sealed=true
 WHERE epoch_id='__V3_STAGE4_EPOCH_ID__'
   AND NOT sealed AND next_ordinal=2;
SET LOCAL ROLE v3_cas_audit_table_owner;
REVOKE UPDATE (sealed) ON v3_cas_audit.epoch_v1 FROM postgres;
RESET ROLE;
REVOKE v3_cas_audit_table_owner FROM postgres;
DO $v3_stage4_seal_postflight$
BEGIN
 IF (SELECT count(*) FROM v3_cas_audit.epoch_v1
     WHERE epoch_id='__V3_STAGE4_EPOCH_ID__'
       AND sealed AND next_ordinal=2) <> 1
    OR (SELECT count(*) FROM v3_cas_audit.intent_v1
        WHERE epoch_id='__V3_STAGE4_EPOCH_ID__') <> 1
    OR pg_catalog.pg_has_role('postgres','v3_cas_audit_table_owner','SET')
    OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
        JOIN pg_catalog.pg_roles a ON a.oid=m.member
        JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
        WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner'
          AND m.admin_option AND NOT m.inherit_option AND NOT m.set_option) <> 1
    OR pg_catalog.has_column_privilege('postgres',
        'v3_cas_audit.epoch_v1','sealed','UPDATE')
 THEN RAISE EXCEPTION 'V3_STAGE4_SEAL_POSTFLIGHT_RIGHTS_REMAIN_HOLD';
 END IF;
END $v3_stage4_seal_postflight$;
COMMIT;
-- Even SEALED + persisted intent DOES NOT grant CAS dispatch; still need
-- real external issuer/reader, originalhost no-rearm, CAS one-attempt fence,
-- separate executor and all six original V3 Paper E2E gates.
