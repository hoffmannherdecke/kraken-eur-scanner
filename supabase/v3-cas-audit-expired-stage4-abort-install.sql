-- The existing signed release operator leases this template and the source
-- of exactly three definitions. This transaction installs them only.
BEGIN;
SET LOCAL lock_timeout='5s';
SET LOCAL statement_timeout='30s';
DO $install_gate$
BEGIN
 IF NOT pg_try_advisory_xact_lock(739901104,1)
    OR NOT pg_try_advisory_xact_lock(82314,4)
    OR current_user <> 'postgres' OR session_user <> 'postgres'
    OR current_database() <> 'postgres'
    OR NOT EXISTS (SELECT FROM pg_roles WHERE rolname='postgres'
                   AND NOT rolsuper AND rolcreaterole AND rolbypassrls)
    OR current_setting('v3_expired_stage4.scope',true) IS DISTINCT FROM 'CLOUD_ABORT_INSTALL'
    OR current_setting('v3_expired_stage4.epoch_id',true) IS DISTINCT FROM 'V3CAS-AUDIT-caafcb9247b0480b8925b154f8351935'
    OR coalesce(current_setting('v3_expired_stage4.approval_sha256',true),'') !~ '^[a-f0-9]{64}$'
    OR (current_setting('v3_expired_stage4.expires_at',true)::timestamptz
          BETWEEN clock_timestamp() AND clock_timestamp()+interval '15 minutes') IS DISTINCT FROM TRUE
 THEN RAISE EXCEPTION 'V3_EXPIRED_STAGE4_INSTALL_SCOPE_HOLD'; END IF;
 IF pg_has_role('postgres','v3_cas_audit_table_owner','SET')
    OR has_schema_privilege('v3_cas_audit_table_owner','v3_cas_audit','CREATE')
    OR has_table_privilege('postgres','v3_cas_audit.epoch_v1','INSERT,UPDATE')
    OR NOT EXISTS (SELECT FROM pg_auth_members WHERE roleid='v3_cas_audit_table_owner'::regrole
        AND member='postgres'::regrole AND admin_option AND NOT set_option AND NOT inherit_option)
    OR (SELECT count(*) FROM pg_roles WHERE rolname IN ('v3_cas_executor_actor','v3_cas_executor')
        AND NOT rolcanlogin AND NOT rolbypassrls AND NOT rolsuper) <> 2
    OR NOT EXISTS (SELECT FROM pg_roles WHERE rolname='v3_cas_executor_actor' AND rolconnlimit=0)
    OR EXISTS (SELECT FROM pg_stat_activity WHERE usename IN ('v3_cas_executor_actor','v3_cas_executor'))
 THEN RAISE EXCEPTION 'V3_EXPIRED_STAGE4_INSTALL_OWNER_OR_EXECUTOR_HOLD'; END IF;
 IF EXISTS (
   SELECT FROM (VALUES
    ('v3_cas_audit.begin_executor_inhibit_v1(text,text,text,text)','v3_cas_audit_table_owner','50be2e1c95a23fe3c281afc43bae456728fc4f36dd2065a18a233e4af8859626'),
    ('v3_cas_audit.record_paper_release_abort_v1(text,text,text,text,text,text)','v3_cas_audit_table_owner','057b582994b4a8c821e3bc143eb4f09eafd48040de8d5a3fb8e022c406169bbf'),
    ('v3_cas_audit.read_paper_release_epoch_v1(text)','postgres','b1e3799d7509f36109a0682962041362d01aa9b5ec3fb390cfcdad01273ca21a')
   ) pin(signature,owner_name,digest)
   LEFT JOIN pg_proc p ON p.oid=to_regprocedure(pin.signature)
   WHERE pg_get_userbyid(p.proowner) IS DISTINCT FROM pin.owner_name
      OR encode(sha256(convert_to(pg_get_functiondef(p.oid),'UTF8')),'hex') IS DISTINCT FROM pin.digest
 ) THEN RAISE EXCEPTION 'V3_EXPIRED_STAGE4_INSTALL_DEFINITION_DRIFT_OR_ALREADY_INSTALLED'; END IF;
 IF (SELECT count(*) FROM public.paper_series WHERE status='active') <> 1
    OR NOT EXISTS (SELECT FROM public.paper_series
        WHERE status='active' AND series_id='PAPER-V2R4-20261009T110135Z')
 THEN RAISE EXCEPTION 'V3_EXPIRED_STAGE4_INSTALL_ACTIVE_SERIES_HOLD'; END IF;
END $install_gate$;

GRANT v3_cas_audit_table_owner TO postgres WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;
GRANT CREATE ON SCHEMA v3_cas_audit TO v3_cas_audit_table_owner;
SET ROLE v3_cas_audit_table_owner;
DO $install_epoch$
DECLARE target constant text := 'V3CAS-AUDIT-caafcb9247b0480b8925b154f8351935';
BEGIN
 PERFORM 1 FROM v3_cas_audit.epoch_v1 e
 WHERE e.epoch_id=target
   AND e.paper_release_commit='46c5abbd6af16266c1229943db973dc9d6b2fb4f'
   AND e.source_sha256='989e1657e03867774907f3a1ec9c9f4f84ee70c2d4b7a258cad9dc3e480f0043'
   AND e.original_fence_sha256='d4b81e56c455348259d95514ff95b5a28bd057df4c576d912d8f3476d216537b'
   AND e.approved_caller_acl_sha256='6f0d59c57f3f7ce3d54f5c674c0d41c342a2a08b9a86001e59353d772f5f66f0'
   AND e.opened_at_utc=timestamptz '2026-11-23 09:16:40.773805+00'
   AND e.predecessor_series_id='PAPER-V2R4-20261009T110135Z'
   AND e.next_ordinal=1 AND NOT e.sealed
   AND clock_timestamp() >= timestamptz '2026-11-23 09:24:58+00'
   AND NOT EXISTS (SELECT FROM v3_cas_audit.epoch_v1 later
                  WHERE later.epoch_id<>target AND later.opened_at_utc>=e.opened_at_utc)
 FOR UPDATE;
 IF NOT FOUND
    OR EXISTS (SELECT FROM v3_cas_audit.executor_inhibit_v1 WHERE epoch_id=target)
    OR EXISTS (SELECT FROM v3_cas_audit.intent_v1)
    OR EXISTS (SELECT FROM v3_cas_audit.attempt_v1)
    OR EXISTS (SELECT FROM v3_cas_audit.prepared_fence_abort_v1 WHERE epoch_id=target)
 THEN RAISE EXCEPTION 'V3_EXPIRED_STAGE4_INSTALL_EPOCH_STATE_HOLD'; END IF;
END $install_epoch$;
SELECT set_config('v3_followup.prior_epoch_id',current_setting('v3_expired_stage4.epoch_id'),true);
SELECT set_config('v3_followup.installed_issuer_sha256','50be2e1c95a23fe3c281afc43bae456728fc4f36dd2065a18a233e4af8859626',true);
/*__ISSUER__*/
/*__ABORT__*/
RESET ROLE;
REVOKE CREATE ON SCHEMA v3_cas_audit FROM v3_cas_audit_table_owner;
REVOKE v3_cas_audit_table_owner FROM postgres GRANTED BY postgres;
/*__READER__*/
DO $install_postflight$
BEGIN
 IF pg_has_role('postgres','v3_cas_audit_table_owner','SET')
    OR has_schema_privilege('v3_cas_audit_table_owner','v3_cas_audit','CREATE')
    OR has_table_privilege('postgres','v3_cas_audit.epoch_v1','INSERT,UPDATE')
    OR (clock_timestamp() < current_setting('v3_expired_stage4.expires_at')::timestamptz) IS DISTINCT FROM TRUE
    OR position('V3_PAPER_EXPIRED_STAGE4_INHIBIT_HOLD' in pg_get_functiondef(
       'v3_cas_audit.begin_executor_inhibit_v1(text,text,text,text)'::regprocedure))=0
    OR position('V3_PAPER_EXPIRED_STAGE4_ABORT_STATE_HOLD' in pg_get_functiondef(
       'v3_cas_audit.record_paper_release_abort_v1(text,text,text,text,text,text)'::regprocedure))=0
    OR position('EXPIRED_STAGE4_ABORTED_BEFORE_INHIBIT' in pg_get_functiondef(
       'v3_cas_audit.read_paper_release_epoch_v1(text)'::regprocedure))=0
 THEN RAISE EXCEPTION 'V3_EXPIRED_STAGE4_INSTALL_POSTFLIGHT_HOLD'; END IF;
END $install_postflight$;
COMMIT;
