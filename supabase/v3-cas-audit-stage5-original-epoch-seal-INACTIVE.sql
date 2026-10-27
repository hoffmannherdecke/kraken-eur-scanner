-- V3 Paper Issue #99 – STAGE5 ORIGINAL audit epoch seal, SOURCE-ONLY INACTIVE.
-- Extends ONLY original merged PR #583 Stage4 open; never ship PR #584's
-- competing epoch opener. Stage0/2/3 and PG17 protected writer are already live.
-- This seal is NOT an originalhost/reader-ACK, once-only CAS execution fence,
-- external signature, restoration authority, SQL migration, or V3 release.
-- External original Writer COMMIT and separate authenticated Reader after COMMIT,
-- exact 16-argument request digest, approved original source/fence/caller ACL,
-- and originalhost no-rearm must be physically verified before any real unlock.
-- CI may remove the single first exception using disposable synthetic fixtures
-- in the existing --network none PG17 container ONLY. Never run on live Cloud.
BEGIN;
DO $v3_stage5_source_lock$
BEGIN
 RAISE EXCEPTION 'V3_STAGE5_ORIGINAL_EPOCH_SEAL_SOURCE_INACTIVE_NO_PRODUCTION_RELEASE';
END
$v3_stage5_source_lock$;
DO $v3_stage5_preflight$
BEGIN
 IF current_user <> 'postgres' OR current_database() <> 'postgres'
    OR NOT (SELECT NOT rolsuper AND rolcreaterole AND rolbypassrls
            FROM pg_catalog.pg_roles WHERE rolname='postgres') THEN
   RAISE EXCEPTION 'V3_STAGE5_ORIGINAL_ADMIN_IDENTITY_HOLD';
 END IF;
 IF '__EPOCH_ID__' !~ '^V3CAS-AUDIT-[a-f0-9]{32}$'
    OR '__INTENT_UUID__' !~
       '^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
    OR '__REQUEST_SHA256__' !~ '^[a-f0-9]{64}$'
    OR '__SOURCE_SHA256__' !~ '^[a-f0-9]{64}$'
    OR '__FENCE_SHA256__' !~ '^[a-f0-9]{64}$'
    OR '__CALLER_ACL_SHA256__' !~ '^[a-f0-9]{64}$' THEN
   RAISE EXCEPTION 'V3_STAGE5_ORIGINAL_BINDING_INPUTS_MISSING_HOLD';
 END IF;
 IF (SELECT count(*) FROM public.paper_series WHERE status='active') <> 1
    OR (SELECT count(*) FROM public.paper_series WHERE status='active'
       AND series_id='PAPER-V2R4-20261009T110135Z') <> 1
    OR to_regprocedure(
       'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
      ) IS NOT NULL THEN
   RAISE EXCEPTION 'V3_STAGE5_ORIGINAL_PAPER_OR_CAS_DRIFT_HOLD';
 END IF;
 IF (SELECT count(*) FROM pg_catalog.pg_class c
     JOIN pg_catalog.pg_namespace ns ON c.relnamespace=ns.oid
     WHERE ns.nspname='v3_cas_audit'
       AND c.relname IN ('epoch_v1','intent_v1')
       AND c.relrowsecurity AND c.relforcerowsecurity
       AND pg_catalog.pg_get_userbyid(c.relowner)='v3_cas_audit_table_owner') <> 2
    OR (SELECT count(*) FROM pg_catalog.pg_roles
        WHERE rolname IN ('v3_cas_audit_writer_actor','v3_cas_audit_reader_actor')
          AND rolcanlogin AND rolconnlimit=1 AND NOT rolbypassrls) <> 2
    OR (SELECT count(*) FROM pg_catalog.pg_roles
        WHERE rolname='v3_cas_executor_actor' AND NOT rolcanlogin
          AND rolconnlimit=0) <> 1 THEN
   RAISE EXCEPTION 'V3_STAGE5_ORIGINAL_OWNER_OR_ACTOR_DRIFT_HOLD';
 END IF;
 IF (SELECT count(*) FROM v3_cas_audit.epoch_v1) <> 1
    OR (SELECT count(*) FROM v3_cas_audit.intent_v1) <> 1
    OR (SELECT count(*) FROM v3_cas_audit.epoch_v1 e
         JOIN v3_cas_audit.intent_v1 i ON e.epoch_id=i.epoch_id
         WHERE e.epoch_id='__EPOCH_ID__' AND NOT e.sealed
           AND e.next_ordinal=2
           AND e.predecessor_series_id='PAPER-V2R4-20261009T110135Z'
           AND e.expected_rpc='public.rotate_v2r4_to_v3_experimental_paper'
           AND e.source_sha256='__SOURCE_SHA256__'
           AND e.original_fence_sha256='__FENCE_SHA256__'
           AND e.approved_caller_acl_sha256='__CALLER_ACL_SHA256__'
           AND i.ordinal=1
           AND i.intent_id::text='__INTENT_UUID__'
           AND i.requested_rpc=e.expected_rpc
           AND i.predecessor_series_id=e.predecessor_series_id
           AND i.request_sha256='__REQUEST_SHA256__'
           AND i.source_sha256=e.source_sha256
           AND i.fence_sha256=e.original_fence_sha256
           AND i.state='PREINVOKE_INTENT'
           AND i.created_at_utc>=e.opened_at_utc
           AND i.created_at_utc<=pg_catalog.clock_timestamp()
           AND i.created_at_utc>pg_catalog.clock_timestamp()-interval '5 minutes'
       ) <> 1 THEN
   RAISE EXCEPTION 'V3_STAGE5_EXACT_COMMITTED_INTENT_NOT_PRESENT_HOLD';
 END IF;
 IF (SELECT count(*) FROM pg_catalog.pg_auth_members m
       JOIN pg_catalog.pg_roles a ON a.oid=m.member
       JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
       WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner'
         AND m.admin_option AND NOT m.inherit_option AND NOT m.set_option) <> 1
    OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
       JOIN pg_catalog.pg_roles a ON a.oid=m.member
       JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
       WHERE a.rolname='postgres' AND g.rolname='v3_cas_audit_table_owner') <> 1
    OR pg_catalog.pg_has_role('postgres','v3_cas_audit_table_owner','SET')
    OR pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','UPDATE') THEN
   RAISE EXCEPTION 'V3_STAGE5_ORIGINAL_OWNER_ESCROW_NOT_CLEAN_HOLD';
 END IF;
END $v3_stage5_preflight$;
-- Temporarily borrow the original NOLOGIN owner within one transaction.
-- The actual release must have separately verified original physical custody.
GRANT v3_cas_audit_table_owner TO postgres WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;
SET ROLE v3_cas_audit_table_owner;
GRANT UPDATE (sealed) ON v3_cas_audit.epoch_v1 TO postgres;
RESET ROLE;
-- Admin BYPASSRLS still requires narrow UPDATE object ACL.
UPDATE v3_cas_audit.epoch_v1 SET sealed=true
 WHERE epoch_id='__EPOCH_ID__' AND NOT sealed AND next_ordinal=2;
-- Restore column UPDATE and original PG17 admin-only membership BEFORE COMMIT.
SET ROLE v3_cas_audit_table_owner;
REVOKE UPDATE (sealed) ON v3_cas_audit.epoch_v1 FROM postgres;
RESET ROLE;
REVOKE v3_cas_audit_table_owner FROM postgres GRANTED BY postgres;
DO $v3_stage5_postflight$
BEGIN
 IF (SELECT count(*) FROM v3_cas_audit.epoch_v1 e
       WHERE e.epoch_id='__EPOCH_ID__'
         AND e.sealed AND e.next_ordinal=2
         AND e.source_sha256='__SOURCE_SHA256__'
         AND e.original_fence_sha256='__FENCE_SHA256__'
         AND e.approved_caller_acl_sha256='__CALLER_ACL_SHA256__') <> 1
    OR (SELECT count(*) FROM v3_cas_audit.epoch_v1) <> 1
    OR (SELECT count(*) FROM v3_cas_audit.intent_v1
        WHERE epoch_id='__EPOCH_ID__' AND ordinal=1
          AND intent_id::text='__INTENT_UUID__'
          AND request_sha256='__REQUEST_SHA256__') <> 1
    OR (SELECT count(*) FROM v3_cas_audit.intent_v1) <> 1
    OR pg_catalog.pg_has_role('postgres','v3_cas_audit_table_owner','SET')
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
   RAISE EXCEPTION 'V3_STAGE5_SEAL_OR_TEMP_PRIVILEGE_RESTORATION_HOLD';
 END IF;
END $v3_stage5_postflight$;
COMMIT;
-- A sealed row is NOT proof of separately verified external post-COMMIT
-- witness, originalhost release/No-Rearm, signer, CAS dispatch or V3 Paper.
