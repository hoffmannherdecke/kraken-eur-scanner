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
    OR current_setting('v3_expired_stage4.epoch_id',true) IS DISTINCT FROM 'V3CAS-AUDIT-7fce8ba3fd714b008407d687e29f50f4'
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
    ('v3_cas_audit.begin_executor_inhibit_v1(text,text,text,text)','v3_cas_audit_table_owner','08792c0af31012c0a77cc04a64586436d2e6fef93805140346bb51e6f8e65b5d'),
    ('v3_cas_audit.record_paper_release_abort_v1(text,text,text,text,text,text)','v3_cas_audit_table_owner','97a15d9d9accd71d5a488b0bdadf61467e0800926d5ac624a78ded926f3117aa'),
    ('v3_cas_audit.read_paper_release_epoch_v1(text)','postgres','8bebf7089a3e7411ed6f06961e542389016b6eda66be05930b1b828572c7ed7a')
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
DECLARE target constant text := 'V3CAS-AUDIT-7fce8ba3fd714b008407d687e29f50f4';
BEGIN
 PERFORM 1 FROM v3_cas_audit.epoch_v1 e
 WHERE e.epoch_id=target
   AND e.paper_release_commit='46c5abbd6af16266c1229943db973dc9d6b2fb4f'
   AND e.source_sha256='8b27c2392c2c8165660a40e15f5ab896c99da39befcd2201e43220acaa2e1251'
   AND e.original_fence_sha256='c9775bdeee0be54a2658fb7673180f2e499035830656300ad68067196e426e28'
   AND e.approved_caller_acl_sha256='6f0d59c57f3f7ce3d54f5c674c0d41c342a2a08b9a86001e59353d772f5f66f0'
   AND e.opened_at_utc=timestamptz '2026-11-15 07:39:19.661951+00'
   AND e.predecessor_series_id='PAPER-V2R4-20261009T110135Z'
   AND e.next_ordinal=1 AND NOT e.sealed
   AND clock_timestamp() >= timestamptz '2026-11-15 07:47:41+00'
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
SELECT set_config('v3_followup.installed_issuer_sha256','08792c0af31012c0a77cc04a64586436d2e6fef93805140346bb51e6f8e65b5d',true);
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
