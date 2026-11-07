-- #99, existing one-time Stage4 scope. The Originalhost operator supplies
-- these settings only after verifying the signed plan, inventory and admission.
BEGIN;
SET LOCAL statement_timeout = '15s';
SELECT pg_advisory_xact_lock(82314, 4);
DO $gate$
BEGIN
 IF session_user <> 'postgres' OR current_user <> 'postgres'
    OR current_database() <> 'postgres'
    OR NOT EXISTS (SELECT FROM pg_roles WHERE rolname='postgres'
                   AND NOT rolsuper AND rolcreaterole AND rolbypassrls)
    OR current_setting('v3_followup.scope',true) IS DISTINCT FROM 'CLOUD_STAGE4_EPOCH_OPEN'
    OR coalesce(current_setting('v3_followup.commit',true),'') !~ '^[a-f0-9]{40}$'
    OR coalesce(current_setting('v3_followup.epoch_id',true),'') !~ '^V3CAS-AUDIT-[a-f0-9]{32}$'
    OR coalesce(current_setting('v3_followup.source_sha256',true),'') !~ '^[a-f0-9]{64}$'
    OR coalesce(current_setting('v3_followup.fence_sha256',true),'') !~ '^[a-f0-9]{64}$'
    OR coalesce(current_setting('v3_followup.caller_acl_sha256',true),'') !~ '^[a-f0-9]{64}$'
    OR coalesce(current_setting('v3_followup.approval_sha256',true),'') !~ '^[a-f0-9]{64}$'
    OR (clock_timestamp() < current_setting('v3_followup.expires_at',true)::timestamptz) IS DISTINCT FROM TRUE
 THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_STAGE4_SCOPE_HOLD'; END IF;
 IF (SELECT count(*) FROM public.paper_series WHERE status='active') <> 1
    OR NOT EXISTS (SELECT FROM public.paper_series WHERE status='active' AND series_id='PAPER-V2R4-20261009T110135Z')
    OR (SELECT count(*) FROM v3_cas_audit.epoch_v1) <> 1
    OR (SELECT count(*) FROM v3_cas_audit.prepared_fence_abort_v1) <> 1
    OR NOT EXISTS (
        SELECT FROM v3_cas_audit.epoch_v1 e
        JOIN v3_cas_audit.prepared_fence_abort_v1 a ON a.epoch_id=e.epoch_id
        WHERE e.predecessor_series_id='PAPER-V2R4-20261009T110135Z'
          AND e.expected_rpc='public.rotate_v2r4_to_v3_experimental_paper'
          AND a.state='ABORT_RECORDED_NOT_RELEASED'
          AND a.source_sha256=e.source_sha256 AND a.prepared_fence_sha256=e.original_fence_sha256
          AND a.caller_acl_sha256=e.approved_caller_acl_sha256
          AND e.next_ordinal=1
          AND e.epoch_id<>current_setting('v3_followup.epoch_id')
          AND e.source_sha256<>current_setting('v3_followup.source_sha256')
          AND e.original_fence_sha256<>current_setting('v3_followup.fence_sha256'))
    OR EXISTS (SELECT FROM v3_cas_audit.intent_v1)
    OR EXISTS (SELECT FROM v3_cas_audit.attempt_v1)
    OR EXISTS (SELECT FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
               WHERE n.nspname='public' AND p.proname='rotate_v2r4_to_v3_experimental_paper')
    OR (SELECT count(*) FROM pg_roles WHERE rolname IN ('v3_cas_executor_actor','v3_cas_executor')
        AND NOT rolcanlogin AND NOT rolbypassrls AND NOT rolsuper) <> 2
    OR NOT EXISTS (SELECT FROM pg_roles WHERE rolname='v3_cas_executor_actor' AND rolconnlimit=0)
    OR EXISTS (SELECT FROM pg_stat_activity WHERE usename IN ('v3_cas_executor_actor','v3_cas_executor'))
    OR EXISTS (SELECT FROM pg_auth_members WHERE member='v3_cas_executor_actor'::regrole)
    OR (SELECT count(*) FROM pg_trigger t
        WHERE (t.tgrelid,t.tgname) IN
          (('v3_cas_audit.intent_v1'::regclass,'v3_reject_aborted_intent_insert_v1'),
           ('v3_cas_audit.attempt_v1'::regclass,'v3_reject_aborted_attempt_insert_v1'))
          AND t.tgenabled='O'
          AND t.tgfoid='v3_cas_audit.reject_aborted_epoch_dispatch_v1()'::regprocedure) <> 2
 THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_ORIGINAL_STATE_HOLD'; END IF;
 IF (SELECT count(*) FROM pg_class
     WHERE oid IN ('v3_cas_audit.epoch_v1'::regclass,'v3_cas_audit.intent_v1'::regclass,
                   'v3_cas_audit.attempt_v1'::regclass,'v3_cas_audit.prepared_fence_abort_v1'::regclass)
       AND relrowsecurity AND relforcerowsecurity
       AND relowner='v3_cas_audit_table_owner'::regrole) <> 4
    OR pg_has_role('postgres','v3_cas_audit_table_owner','SET')
    OR has_table_privilege('postgres','v3_cas_audit.epoch_v1','INSERT,UPDATE')
    OR (SELECT count(*) FROM pg_auth_members WHERE roleid='v3_cas_audit_table_owner'::regrole
        AND member='postgres'::regrole) <> 1
    OR NOT EXISTS (SELECT FROM pg_auth_members WHERE roleid='v3_cas_audit_table_owner'::regrole
        AND member='postgres'::regrole AND admin_option AND NOT set_option AND NOT inherit_option)
 THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_OWNER_ESCROW_HOLD'; END IF;
END $gate$;

-- Same temporary owner escrow as the original Stage4 transaction.
GRANT v3_cas_audit_table_owner TO postgres WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;
SET ROLE v3_cas_audit_table_owner;
ALTER TABLE v3_cas_audit.epoch_v1 ADD COLUMN paper_release_commit text
 CHECK (paper_release_commit ~ '^[a-f0-9]{40}$');
GRANT INSERT ON v3_cas_audit.epoch_v1 TO postgres;
RESET ROLE;
INSERT INTO v3_cas_audit.epoch_v1
 (epoch_id,predecessor_series_id,expected_rpc,source_sha256,original_fence_sha256,
  approved_caller_acl_sha256,paper_release_commit)
VALUES
 (current_setting('v3_followup.epoch_id'),'PAPER-V2R4-20261009T110135Z',
  'public.rotate_v2r4_to_v3_experimental_paper',current_setting('v3_followup.source_sha256'),
  current_setting('v3_followup.fence_sha256'),current_setting('v3_followup.caller_acl_sha256'),
  current_setting('v3_followup.commit'));
SET ROLE v3_cas_audit_table_owner;
REVOKE INSERT ON v3_cas_audit.epoch_v1 FROM postgres;
RESET ROLE;
REVOKE v3_cas_audit_table_owner FROM postgres GRANTED BY postgres;

-- The same issuer can terminalize only this release epoch before any attempt.
-- The installed CAS cannot dispatch through an aborted epoch even if an
-- intent already exists: the original attempt trigger remains authoritative.
GRANT v3_cas_audit_table_owner TO postgres WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;
GRANT CREATE ON SCHEMA v3_cas_audit TO v3_cas_audit_table_owner;
SET ROLE v3_cas_audit_table_owner;
CREATE FUNCTION v3_cas_audit.record_paper_release_abort_v1(p_epoch text,p_commit text,
 p_source text,p_fence text,p_acl text,p_receipt text)
RETURNS timestamptz LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $abort$
DECLARE result_at timestamptz;
BEGIN
 IF session_user <> 'v3_cas_inhibit_issuer_actor'
    OR coalesce(p_receipt,'') !~ '^[a-f0-9]{64}$'
    OR (SELECT count(*) FROM pg_roles WHERE rolname IN ('v3_cas_executor_actor','v3_cas_executor')
        AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls) <> 2
    OR NOT EXISTS (SELECT FROM pg_roles WHERE rolname='v3_cas_executor_actor' AND rolconnlimit=0)
    OR EXISTS (SELECT FROM pg_stat_activity WHERE usename IN ('v3_cas_executor_actor','v3_cas_executor'))
 THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_ABORT_ACTOR_HOLD'; END IF;
 PERFORM 1 FROM v3_cas_audit.epoch_v1 e
 JOIN v3_cas_audit.executor_inhibit_v1 g ON g.epoch_id=e.epoch_id
 WHERE e.epoch_id=p_epoch AND e.paper_release_commit=p_commit
   AND e.source_sha256=p_source AND e.original_fence_sha256=p_fence AND e.approved_caller_acl_sha256=p_acl
   AND g.source_sha256=p_source AND g.original_fence_sha256=p_fence AND g.caller_acl_sha256=p_acl
   AND g.issuer_id=session_user AND g.state='INHIBITED'
 FOR UPDATE OF e;
 IF NOT FOUND OR EXISTS (SELECT FROM v3_cas_audit.attempt_v1)
 THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_ABORT_EPOCH_OR_ATTEMPT_HOLD'; END IF;
 INSERT INTO v3_cas_audit.prepared_fence_abort_v1
  (epoch_id,source_sha256,prepared_fence_sha256,caller_acl_sha256,issuer_actor,receipt_sha256,state)
 VALUES (p_epoch,p_source,p_fence,p_acl,session_user,p_receipt,'ABORT_RECORDED_NOT_RELEASED')
 RETURNING created_at_utc INTO result_at;
 RETURN result_at;
END $abort$;
REVOKE ALL ON FUNCTION v3_cas_audit.record_paper_release_abort_v1(text,text,text,text,text,text)
 FROM PUBLIC,anon,authenticated,service_role;
GRANT EXECUTE ON FUNCTION v3_cas_audit.record_paper_release_abort_v1(text,text,text,text,text,text)
 TO v3_cas_inhibit_issuer_actor;
RESET ROLE;
REVOKE CREATE ON SCHEMA v3_cas_audit FROM v3_cas_audit_table_owner;
REVOKE v3_cas_audit_table_owner FROM postgres GRANTED BY postgres;

-- Read-only extension for the existing independent Notebook Reader.
-- The original no-argument Gate-A/Stage4 Reader and abort trigger remain intact.
CREATE FUNCTION v3_cas_audit.read_paper_release_epoch_v1(p_epoch_id text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $reader$
DECLARE e record; g record; i v3_cas_audit.intent_v1%ROWTYPE; actor record; rpc oid; installed boolean; witness_state text;
BEGIN
 IF session_user <> 'v3_cas_audit_reader_actor'
    OR current_setting('role',true) IS DISTINCT FROM 'v3_cas_audit_reader'
 THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_READER_IDENTITY_HOLD'; END IF;
 SELECT * INTO e FROM v3_cas_audit.epoch_v1 WHERE epoch_id=p_epoch_id AND paper_release_commit IS NOT NULL;
 IF NOT FOUND
    OR (SELECT count(*) FROM v3_cas_audit.epoch_v1 WHERE paper_release_commit IS NOT NULL) <> 1
    OR (SELECT count(*) FROM public.paper_series WHERE status='active') <> 1
    OR NOT EXISTS (SELECT FROM public.paper_series WHERE status='active' AND series_id=e.predecessor_series_id)
    OR EXISTS (SELECT FROM v3_cas_audit.attempt_v1)
 THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_READER_EPOCH_OR_SERIES_HOLD'; END IF;
 SELECT * INTO actor FROM pg_roles WHERE rolname='v3_cas_executor_actor'
  AND NOT rolsuper AND NOT rolbypassrls AND NOT rolinherit
  AND NOT rolcreaterole AND NOT rolcreatedb AND NOT rolreplication;
 IF NOT FOUND OR NOT EXISTS (SELECT FROM pg_roles WHERE rolname='v3_cas_executor' AND NOT rolcanlogin)
    OR EXISTS (SELECT FROM pg_stat_activity WHERE usename IN ('v3_cas_executor_actor','v3_cas_executor'))
 THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_READER_EXECUTOR_HOLD'; END IF;
 rpc:=to_regprocedure('public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)');
 installed:=rpc IS NOT NULL;
 IF (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
     WHERE n.nspname='public' AND p.proname='rotate_v2r4_to_v3_experimental_paper') <> installed::int
    OR (SELECT count(*) FROM pg_auth_members WHERE member=actor.oid) <> installed::int
    OR (installed AND NOT EXISTS (SELECT FROM pg_auth_members WHERE member=actor.oid
      AND roleid='v3_cas_executor'::regrole AND set_option AND NOT admin_option AND NOT inherit_option))
    OR (installed AND (
      NOT has_function_privilege('v3_cas_executor',rpc,'EXECUTE')
      OR has_function_privilege('v3_cas_audit_reader',rpc,'EXECUTE')
      OR has_function_privilege('v3_cas_audit_writer',rpc,'EXECUTE')
      OR has_function_privilege('v3_cas_executor_actor',rpc,'EXECUTE')
      OR has_function_privilege('anon',rpc,'EXECUTE')
      OR has_function_privilege('authenticated',rpc,'EXECUTE')
      OR has_function_privilege('service_role',rpc,'EXECUTE')))
 THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_READER_RPC_OR_MEMBERSHIP_HOLD'; END IF;
 SELECT * INTO g FROM v3_cas_audit.executor_inhibit_v1
  WHERE epoch_id=p_epoch_id AND source_sha256=e.source_sha256
    AND original_fence_sha256=e.original_fence_sha256 AND caller_acl_sha256=e.approved_caller_acl_sha256
    AND issuer_id='v3_cas_inhibit_issuer_actor' AND state='INHIBITED';
 IF NOT FOUND THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_READER_INHIBIT_HOLD'; END IF;
 IF EXISTS (SELECT FROM v3_cas_audit.prepared_fence_abort_v1
      WHERE epoch_id=p_epoch_id AND source_sha256=e.source_sha256
        AND prepared_fence_sha256=e.original_fence_sha256 AND caller_acl_sha256=e.approved_caller_acl_sha256
        AND issuer_actor='v3_cas_inhibit_issuer_actor' AND state='ABORT_RECORDED_NOT_RELEASED') THEN
   IF actor.rolcanlogin OR actor.rolconnlimit<>0
   THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_ABORT_READER_ACTOR_HOLD'; END IF;
   witness_state:='PRECAS_ABORT_SEALED_OLD_ONLY_ZERO_ATTEMPTS';
 ELSIF EXISTS (SELECT FROM v3_cas_audit.prepared_fence_abort_v1 WHERE epoch_id=p_epoch_id)
 THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_ABORT_BINDINGS_HOLD';
 ELSIF NOT actor.rolcanlogin AND NOT e.sealed AND e.next_ordinal=1 AND g.native_stop_at_utc IS NULL
    AND g.acknowledged_at_utc IS NULL AND g.receipt_sha256 IS NULL
    AND NOT EXISTS (SELECT FROM v3_cas_audit.intent_v1) THEN
   witness_state:=CASE WHEN installed THEN 'PRESTOP_INHIBITED_OLD_ONLY_NO_ATTEMPTS'
               ELSE 'INSTALL_APPROVED_OLD_ONLY_NO_ATTEMPTS' END;
 ELSIF installed AND e.next_ordinal=2 AND g.native_stop_at_utc IS NOT NULL
       AND g.acknowledged_at_utc IS NOT NULL AND g.receipt_sha256 IS NOT NULL
       AND g.valid_through_utc>clock_timestamp() AND g.audit_intent_high_watermark=1
       AND ((NOT actor.rolcanlogin AND actor.rolconnlimit=0)
            OR (e.sealed AND actor.rolcanlogin AND actor.rolconnlimit=1 AND actor.rolvaliduntil>clock_timestamp()))
       AND (SELECT count(*) FROM v3_cas_audit.intent_v1)=1 THEN
   SELECT * INTO i FROM v3_cas_audit.intent_v1 WHERE epoch_id=p_epoch_id AND ordinal=1
     AND source_sha256=e.source_sha256 AND fence_sha256=e.original_fence_sha256
     AND requested_rpc=e.expected_rpc AND predecessor_series_id=e.predecessor_series_id
     AND state='PREINVOKE_INTENT';
   IF NOT FOUND THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_READER_INTENT_HOLD'; END IF;
   witness_state:=CASE WHEN NOT e.sealed THEN 'STOP_CONFIRMED_INTENT_COMMITTED'
               WHEN actor.rolcanlogin THEN 'SEALED_INTENT_INHIBIT_STOP_CONFIRMED'
               ELSE 'SEALED_INTENT_EXECUTOR_INHIBITED' END;
 ELSE RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_READER_PHASE_HOLD'; END IF;
 RETURN jsonb_build_object(
  'kind','V3_PAPER_RELEASE_EPOCH_READER_V1','state',witness_state,
  'observed_at_utc',to_char(clock_timestamp() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
  'release_commit',e.paper_release_commit,'epoch_id',p_epoch_id,
  'source_sha256',e.source_sha256,'fence_sha256',e.original_fence_sha256,
  'caller_acl_sha256',e.approved_caller_acl_sha256,
  'preinvoke_epoch_id',p_epoch_id,'preinvoke_intent_id',i.intent_id,
  'preinvoke_request_sha256',i.request_sha256,'preinvoke_source_sha256',e.source_sha256,
  'preinvoke_fence_sha256',e.original_fence_sha256,'preinvoke_inhibit_receipt_sha256',g.receipt_sha256);
END $reader$;
REVOKE ALL ON FUNCTION v3_cas_audit.read_paper_release_epoch_v1(text)
 FROM PUBLIC,anon,authenticated,service_role;
GRANT EXECUTE ON FUNCTION v3_cas_audit.read_paper_release_epoch_v1(text) TO v3_cas_audit_reader;

DO $postflight$
BEGIN
 IF pg_has_role('postgres','v3_cas_audit_table_owner','SET')
    OR has_table_privilege('postgres','v3_cas_audit.epoch_v1','INSERT,UPDATE')
    OR (SELECT count(*) FROM pg_auth_members WHERE roleid='v3_cas_audit_table_owner'::regrole
        AND member='postgres'::regrole) <> 1
    OR (clock_timestamp() < current_setting('v3_followup.expires_at',true)::timestamptz) IS DISTINCT FROM TRUE
 THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_OWNER_RESTORE_OR_EXPIRED_HOLD'; END IF;
END $postflight$;
COMMIT;
