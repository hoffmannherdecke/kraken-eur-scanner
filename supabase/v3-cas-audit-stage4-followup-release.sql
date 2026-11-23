-- #99, existing one-time Stage4 scope. The Originalhost operator supplies
-- these settings only after verifying the signed plan, inventory and admission.
BEGIN;
SET LOCAL statement_timeout = '15s';
SELECT pg_advisory_xact_lock(82314, 4);
DO $gate$
DECLARE continuing boolean := coalesce(current_setting('v3_followup.prior_epoch_id',true),'')<>'';
 rpc oid := to_regprocedure('public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)');
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
    OR EXISTS (SELECT FROM v3_cas_audit.intent_v1)
    OR EXISTS (SELECT FROM v3_cas_audit.attempt_v1)
    OR (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
         WHERE n.nspname='public' AND p.proname='rotate_v2r4_to_v3_experimental_paper') <> continuing::int
    OR (SELECT count(*) FROM pg_roles WHERE rolname IN ('v3_cas_executor_actor','v3_cas_executor')
        AND NOT rolcanlogin AND NOT rolbypassrls AND NOT rolsuper) <> 2
    OR NOT EXISTS (SELECT FROM pg_roles WHERE rolname='v3_cas_executor_actor' AND rolconnlimit=0)
    OR EXISTS (SELECT FROM pg_stat_activity WHERE usename IN ('v3_cas_executor_actor','v3_cas_executor'))
    OR (SELECT count(*) FROM pg_auth_members WHERE member='v3_cas_executor_actor'::regrole) <> continuing::int
    OR (continuing AND NOT EXISTS (SELECT FROM pg_auth_members
        WHERE member='v3_cas_executor_actor'::regrole AND roleid='v3_cas_executor'::regrole
          AND set_option AND NOT inherit_option AND NOT admin_option))
    OR (SELECT count(*) FROM pg_trigger t
        WHERE (t.tgrelid,t.tgname) IN
          (('v3_cas_audit.intent_v1'::regclass,'v3_reject_aborted_intent_insert_v1'),
           ('v3_cas_audit.attempt_v1'::regclass,'v3_reject_aborted_attempt_insert_v1'))
          AND t.tgenabled='O'
          AND t.tgfoid='v3_cas_audit.reject_aborted_epoch_dispatch_v1()'::regprocedure) <> 2
 THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_ORIGINAL_STATE_HOLD'; END IF;
 -- The next epoch can open only after every earlier one is terminal.
 IF NOT EXISTS (SELECT FROM v3_cas_audit.epoch_v1)
    OR EXISTS (
      SELECT FROM v3_cas_audit.epoch_v1 e
      LEFT JOIN v3_cas_audit.prepared_fence_abort_v1 a ON a.epoch_id=e.epoch_id
      WHERE a.state IS DISTINCT FROM 'ABORT_RECORDED_NOT_RELEASED'
         OR a.source_sha256 IS DISTINCT FROM e.source_sha256
         OR a.prepared_fence_sha256 IS DISTINCT FROM e.original_fence_sha256
         OR a.caller_acl_sha256 IS DISTINCT FROM e.approved_caller_acl_sha256
         OR e.predecessor_series_id<>'PAPER-V2R4-20261009T110135Z'
         OR e.expected_rpc<>'public.rotate_v2r4_to_v3_experimental_paper'
         OR e.next_ordinal<>1 OR e.sealed
         OR e.epoch_id=current_setting('v3_followup.epoch_id')
         OR e.original_fence_sha256=current_setting('v3_followup.fence_sha256'))
 THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_TERMINAL_HISTORY_HOLD'; END IF;
 IF continuing THEN
   -- The predecessor is immutable historical evidence; it may have a different
   -- source hash from the newly pinned CAS original for this successor epoch.
   IF coalesce(current_setting('v3_followup.prior_source_sha256',true),'') !~ '^[a-f0-9]{64}$'
   THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_PRIOR_SOURCE_PIN_HOLD'; END IF;
   IF (current_setting('v3_followup.series_time',true)::timestamptz
          BETWEEN clock_timestamp()-interval '10 minutes' AND clock_timestamp()) IS DISTINCT FROM TRUE
      OR encode(sha256(convert_to(pg_get_functiondef(
          'v3_cas_audit.read_paper_release_epoch_v1(text)'::regprocedure),'UTF8')),'hex')
         IS DISTINCT FROM current_setting('v3_followup.installed_reader_sha256',true)
      OR rpc IS NULL OR encode(sha256(convert_to(pg_get_functiondef(rpc),'UTF8')),'hex')
         IS DISTINCT FROM current_setting('v3_followup.installed_cas_sha256',true)
      OR NOT has_function_privilege('v3_cas_executor',rpc,'EXECUTE')
      OR EXISTS (SELECT FROM unnest(ARRAY['anon','authenticated','service_role','v3_cas_executor_actor',
          'v3_cas_audit_reader','v3_cas_audit_writer']) AS r(role_name) WHERE has_function_privilege(r.role_name,rpc,'EXECUTE'))
      OR NOT EXISTS (
        SELECT FROM v3_cas_audit.epoch_v1 e
        JOIN v3_cas_audit.prepared_fence_abort_v1 a ON a.epoch_id=e.epoch_id
        LEFT JOIN v3_cas_audit.executor_inhibit_v1 i ON i.epoch_id=e.epoch_id
        WHERE e.epoch_id=current_setting('v3_followup.prior_epoch_id')
          AND e.paper_release_commit=current_setting('v3_followup.prior_commit')
          AND e.source_sha256=current_setting('v3_followup.prior_source_sha256')
          AND e.approved_caller_acl_sha256=current_setting('v3_followup.caller_acl_sha256')
          AND a.receipt_sha256=current_setting('v3_followup.prior_terminal_sha256')
          AND a.issuer_actor='v3_cas_inhibit_issuer_actor'
          AND (
            (i.state='INHIBITED' AND i.issuer_id=a.issuer_actor
             AND i.source_sha256=e.source_sha256 AND i.original_fence_sha256=e.original_fence_sha256
             AND i.caller_acl_sha256=e.approved_caller_acl_sha256 AND i.native_stop_at_utc IS NULL)
            OR (i.epoch_id IS NULL
                AND e.paper_release_commit='46c5abbd6af16266c1229943db973dc9d6b2fb4f'
                AND ((e.epoch_id='V3CAS-AUDIT-7fce8ba3fd714b008407d687e29f50f4'
                      AND e.original_fence_sha256='c9775bdeee0be54a2658fb7673180f2e499035830656300ad68067196e426e28')
                  OR (e.epoch_id='V3CAS-AUDIT-4c43add6968a46a6a8133a55ae92cf93'
                      AND e.source_sha256='989e1657e03867774907f3a1ec9c9f4f84ee70c2d4b7a258cad9dc3e480f0043'
                      AND e.original_fence_sha256='0e5ff6f9d2cc6b2b588a053d1ea7e2e7a8a9ada9f5744c5491699803aca0b025')
                  OR (e.epoch_id='V3CAS-AUDIT-caafcb9247b0480b8925b154f8351935' AND e.source_sha256='989e1657e03867774907f3a1ec9c9f4f84ee70c2d4b7a258cad9dc3e480f0043'
                      AND e.original_fence_sha256='d4b81e56c455348259d95514ff95b5a28bd057df4c576d912d8f3476d216537b')))
          )
          AND NOT EXISTS (SELECT FROM v3_cas_audit.epoch_v1 later WHERE later.opened_at_utc>e.opened_at_utc))
   THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_SUPERSESSION_BINDING_HOLD'; END IF;
 ELSIF (SELECT count(*) FROM v3_cas_audit.epoch_v1)<>1
    OR EXISTS (SELECT FROM v3_cas_audit.epoch_v1 WHERE source_sha256=current_setting('v3_followup.source_sha256'))
 THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_FIRST_EPOCH_HOLD'; END IF;

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
DO $epoch_schema$
BEGIN
 IF coalesce(current_setting('v3_followup.prior_epoch_id',true),'')='' THEN
   ALTER TABLE v3_cas_audit.epoch_v1 ADD COLUMN paper_release_commit text
    CHECK (paper_release_commit ~ '^[a-f0-9]{40}$');
 END IF;
END $epoch_schema$;
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
DO $issuer_upgrade$
DECLARE issuer oid := 'v3_cas_audit.begin_executor_inhibit_v1(text,text,text,text)'::regprocedure;
 old_def text;
 new_def text;
 old_guard text := $guard$OR to_regprocedure(
       'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
       ) IS NOT NULL$guard$;
BEGIN
 IF coalesce(current_setting('v3_followup.prior_epoch_id',true),'')='' THEN RETURN; END IF;
 old_def:=pg_get_functiondef(issuer);
 IF encode(sha256(convert_to(old_def,'UTF8')),'hex')
      IS DISTINCT FROM current_setting('v3_followup.installed_issuer_sha256',true)
 THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_ISSUER_SOURCE_DRIFT'; END IF;
 new_def:=old_def;
 IF position('V3_SIGNED_FOLLOWUP_INSTALLED_RPC' in old_def)=0 THEN
   new_def:=replace(old_def,old_guard,'OR ('||substring(old_guard from 4)||$permit$
    AND NOT ( -- V3_SIGNED_FOLLOWUP_INSTALLED_RPC
      EXISTS (SELECT FROM v3_cas_audit.epoch_v1 current_epoch
        WHERE current_epoch.epoch_id=p_epoch_id AND current_epoch.paper_release_commit IS NOT NULL
          AND NOT EXISTS (SELECT FROM v3_cas_audit.prepared_fence_abort_v1 a WHERE a.epoch_id=p_epoch_id))
      AND NOT EXISTS (SELECT FROM v3_cas_audit.epoch_v1 e WHERE e.epoch_id<>p_epoch_id AND NOT EXISTS (
        SELECT FROM v3_cas_audit.prepared_fence_abort_v1 a WHERE a.epoch_id=e.epoch_id
         AND a.state='ABORT_RECORDED_NOT_RELEASED' AND a.source_sha256=e.source_sha256
         AND a.prepared_fence_sha256=e.original_fence_sha256 AND a.caller_acl_sha256=e.approved_caller_acl_sha256))
      AND (SELECT count(*) FROM v3_cas_audit.epoch_v1)>=3
      AND NOT EXISTS (SELECT FROM v3_cas_audit.intent_v1)
      AND NOT EXISTS (SELECT FROM v3_cas_audit.attempt_v1)
      AND EXISTS (SELECT FROM pg_roles WHERE rolname='v3_cas_executor_actor' AND NOT rolcanlogin AND rolconnlimit=0)
      AND NOT EXISTS (SELECT FROM pg_stat_activity WHERE usename IN ('v3_cas_executor_actor','v3_cas_executor'))
    ))$permit$);
   IF new_def=old_def THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_ISSUER_GUARD_SEAM_HOLD'; END IF;
 END IF;
 IF position('V3_PAPER_EXPIRED_STAGE4_INHIBIT_HOLD' in new_def)=0 THEN
   IF (length(new_def)-length(replace(new_def,' INSERT INTO v3_cas_audit.executor_inhibit_v1','')))
        <> length(' INSERT INTO v3_cas_audit.executor_inhibit_v1')
   THEN RAISE EXCEPTION 'V3_PAPER_EXPIRED_STAGE4_ISSUER_SEAM_HOLD'; END IF;
   new_def:=replace(new_def,' INSERT INTO v3_cas_audit.executor_inhibit_v1',$guard$
 IF p_epoch_id IN ('V3CAS-AUDIT-7fce8ba3fd714b008407d687e29f50f4','V3CAS-AUDIT-4c43add6968a46a6a8133a55ae92cf93')
    AND (clock_timestamp() >= CASE p_epoch_id
          WHEN 'V3CAS-AUDIT-7fce8ba3fd714b008407d687e29f50f4' THEN timestamptz '2026-11-15 07:47:41+00'
          ELSE timestamptz '2026-11-19 09:19:35+00' END
         OR EXISTS (SELECT FROM v3_cas_audit.prepared_fence_abort_v1 WHERE epoch_id=p_epoch_id))
 THEN RAISE EXCEPTION 'V3_PAPER_EXPIRED_STAGE4_INHIBIT_HOLD'; END IF;
 INSERT INTO v3_cas_audit.executor_inhibit_v1$guard$);
 ELSIF position('V3CAS-AUDIT-4c43add6968a46a6a8133a55ae92cf93' in new_def)=0 THEN
   -- Existing production issuer already contains the historical guard.
   -- Extend only that exact old guard; any difference fails closed.
   new_def:=replace(new_def,$old_expired$
 IF p_epoch_id='V3CAS-AUDIT-7fce8ba3fd714b008407d687e29f50f4'
    AND (clock_timestamp() >= timestamptz '2026-11-15 07:47:41+00'
         OR EXISTS (SELECT FROM v3_cas_audit.prepared_fence_abort_v1 WHERE epoch_id=p_epoch_id))
 THEN RAISE EXCEPTION 'V3_PAPER_EXPIRED_STAGE4_INHIBIT_HOLD'; END IF;$old_expired$,$both_expired$
 IF p_epoch_id IN ('V3CAS-AUDIT-7fce8ba3fd714b008407d687e29f50f4','V3CAS-AUDIT-4c43add6968a46a6a8133a55ae92cf93')
    AND (clock_timestamp() >= CASE p_epoch_id
          WHEN 'V3CAS-AUDIT-7fce8ba3fd714b008407d687e29f50f4' THEN timestamptz '2026-11-15 07:47:41+00'
          ELSE timestamptz '2026-11-19 09:19:35+00' END
         OR EXISTS (SELECT FROM v3_cas_audit.prepared_fence_abort_v1 WHERE epoch_id=p_epoch_id))
 THEN RAISE EXCEPTION 'V3_PAPER_EXPIRED_STAGE4_INHIBIT_HOLD'; END IF;$both_expired$);
   IF new_def=old_def THEN RAISE EXCEPTION 'V3_PAPER_EXPIRED_STAGE4_ISSUER_SEAM_HOLD'; END IF;
 END IF;
 IF position('V3CAS-AUDIT-caafcb9247b0480b8925b154f8351935' in new_def)=0 THEN
   IF (length(new_def)-length(replace(new_def,' INSERT INTO v3_cas_audit.executor_inhibit_v1','')))
        <> length(' INSERT INTO v3_cas_audit.executor_inhibit_v1')
   THEN RAISE EXCEPTION 'V3_PAPER_EXPIRED_STAGE4_ISSUER_SEAM_HOLD'; END IF;
   new_def:=replace(new_def,' INSERT INTO v3_cas_audit.executor_inhibit_v1',$current_expired$
 IF p_epoch_id='V3CAS-AUDIT-caafcb9247b0480b8925b154f8351935'
    AND (clock_timestamp() >= timestamptz '2026-11-23 09:24:58+00'
         OR EXISTS (SELECT FROM v3_cas_audit.prepared_fence_abort_v1 WHERE epoch_id=p_epoch_id))
 THEN RAISE EXCEPTION 'V3_PAPER_EXPIRED_STAGE4_INHIBIT_HOLD'; END IF;
 INSERT INTO v3_cas_audit.executor_inhibit_v1$current_expired$);
 END IF;
 IF new_def<>old_def THEN EXECUTE new_def; END IF;
END $issuer_upgrade$;
CREATE OR REPLACE FUNCTION v3_cas_audit.record_paper_release_abort_v1(p_epoch text,p_commit text,
 p_source text,p_fence text,p_acl text,p_receipt text)
RETURNS timestamptz LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $abort$
DECLARE result_at timestamptz;
    stage4_expired_epoch constant text := 'V3CAS-AUDIT-7fce8ba3fd714b008407d687e29f50f4';
BEGIN
 IF session_user <> 'v3_cas_inhibit_issuer_actor'
    OR coalesce(p_receipt,'') !~ '^[a-f0-9]{64}$'
    OR (SELECT count(*) FROM pg_roles WHERE rolname IN ('v3_cas_executor_actor','v3_cas_executor')
        AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls) <> 2
    OR NOT EXISTS (SELECT FROM pg_roles WHERE rolname='v3_cas_executor_actor' AND rolconnlimit=0)
    OR EXISTS (SELECT FROM pg_stat_activity WHERE usename IN ('v3_cas_executor_actor','v3_cas_executor'))
 THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_ABORT_ACTOR_HOLD'; END IF;
 IF p_epoch IN (stage4_expired_epoch, 'V3CAS-AUDIT-4c43add6968a46a6a8133a55ae92cf93', 'V3CAS-AUDIT-caafcb9247b0480b8925b154f8351935') THEN
   IF current_setting('transaction_isolation') <> 'read committed'
   THEN RAISE EXCEPTION 'V3_PAPER_EXPIRED_STAGE4_ABORT_ISOLATION_HOLD'; END IF;
   -- Take an exclusive row lock and create a new row version. BeginInhibit
   -- takes FOR SHARE and AppendIntent locks the same epoch before inserting.
   -- An older repeatable-read snapshot must not proceed across the abort.
   UPDATE v3_cas_audit.epoch_v1 e SET next_ordinal=e.next_ordinal
   WHERE e.epoch_id=p_epoch AND e.paper_release_commit=p_commit
     AND p_commit='46c5abbd6af16266c1229943db973dc9d6b2fb4f'
     AND e.source_sha256=p_source AND e.original_fence_sha256=p_fence
     AND ((p_epoch=stage4_expired_epoch AND p_fence='c9775bdeee0be54a2658fb7673180f2e499035830656300ad68067196e426e28')
       OR (p_epoch='V3CAS-AUDIT-4c43add6968a46a6a8133a55ae92cf93' AND p_fence='0e5ff6f9d2cc6b2b588a053d1ea7e2e7a8a9ada9f5744c5491699803aca0b025'
           AND p_source='989e1657e03867774907f3a1ec9c9f4f84ee70c2d4b7a258cad9dc3e480f0043')
       OR (p_epoch='V3CAS-AUDIT-caafcb9247b0480b8925b154f8351935' AND p_fence='d4b81e56c455348259d95514ff95b5a28bd057df4c576d912d8f3476d216537b' AND p_source='989e1657e03867774907f3a1ec9c9f4f84ee70c2d4b7a258cad9dc3e480f0043'))
     AND e.approved_caller_acl_sha256=p_acl AND NOT e.sealed AND e.next_ordinal=1
     AND e.predecessor_series_id='PAPER-V2R4-20261009T110135Z'
     AND e.expected_rpc='public.rotate_v2r4_to_v3_experimental_paper'
     AND clock_timestamp() >= CASE p_epoch WHEN stage4_expired_epoch
           THEN timestamptz '2026-11-15 07:47:41+00'
           WHEN 'V3CAS-AUDIT-4c43add6968a46a6a8133a55ae92cf93' THEN timestamptz '2026-11-19 09:19:35+00'
           ELSE timestamptz '2026-11-23 09:24:58+00' END;
   IF NOT FOUND
      OR EXISTS (SELECT FROM v3_cas_audit.epoch_v1 later JOIN v3_cas_audit.epoch_v1 e ON e.epoch_id=p_epoch
                 WHERE later.epoch_id<>e.epoch_id AND later.opened_at_utc>=e.opened_at_utc)
      OR EXISTS (SELECT FROM v3_cas_audit.executor_inhibit_v1 WHERE epoch_id=p_epoch)
      OR EXISTS (SELECT FROM v3_cas_audit.intent_v1)
      OR EXISTS (SELECT FROM v3_cas_audit.attempt_v1)
      OR EXISTS (SELECT FROM v3_cas_audit.prepared_fence_abort_v1 WHERE epoch_id=p_epoch)
   THEN RAISE EXCEPTION 'V3_PAPER_EXPIRED_STAGE4_ABORT_STATE_HOLD'; END IF;
 ELSE
   PERFORM 1 FROM v3_cas_audit.epoch_v1 e
   JOIN v3_cas_audit.executor_inhibit_v1 g ON g.epoch_id=e.epoch_id
   WHERE e.epoch_id=p_epoch AND e.paper_release_commit=p_commit
     AND e.source_sha256=p_source AND e.original_fence_sha256=p_fence AND e.approved_caller_acl_sha256=p_acl
     AND g.source_sha256=p_source AND g.original_fence_sha256=p_fence AND g.caller_acl_sha256=p_acl
     AND g.issuer_id=session_user AND g.state='INHIBITED'
   FOR UPDATE OF e;
   IF NOT FOUND OR EXISTS (SELECT FROM v3_cas_audit.attempt_v1)
   THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_ABORT_EPOCH_OR_ATTEMPT_HOLD'; END IF;
 END IF;
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
CREATE OR REPLACE FUNCTION v3_cas_audit.read_paper_release_epoch_v1(p_epoch_id text)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $reader$
DECLARE e record; g record; i v3_cas_audit.intent_v1%ROWTYPE;
 actor record; terminal_receipt text; successor_id text; successor_config jsonb; rpc oid; installed boolean; witness_state text;
BEGIN
 IF session_user <> 'v3_cas_audit_reader_actor'
    OR current_setting('role',true) IS DISTINCT FROM 'v3_cas_audit_reader'
 THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_READER_IDENTITY_HOLD'; END IF;
 SELECT * INTO e FROM v3_cas_audit.epoch_v1 WHERE epoch_id=p_epoch_id AND paper_release_commit IS NOT NULL;
 IF NOT FOUND
    OR EXISTS (SELECT FROM v3_cas_audit.epoch_v1 other
      WHERE other.epoch_id<>p_epoch_id AND NOT EXISTS (
       SELECT FROM v3_cas_audit.prepared_fence_abort_v1 a WHERE a.epoch_id=other.epoch_id
        AND a.state='ABORT_RECORDED_NOT_RELEASED' AND a.source_sha256=other.source_sha256
        AND a.prepared_fence_sha256=other.original_fence_sha256 AND a.caller_acl_sha256=other.approved_caller_acl_sha256))
    OR (SELECT count(*) FROM public.paper_series WHERE status='active') <> 1
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
 IF NOT FOUND THEN
   SELECT a.receipt_sha256 INTO terminal_receipt FROM v3_cas_audit.prepared_fence_abort_v1 a
   WHERE a.epoch_id=p_epoch_id AND a.source_sha256=e.source_sha256
     AND a.prepared_fence_sha256=e.original_fence_sha256 AND a.caller_acl_sha256=e.approved_caller_acl_sha256
     AND a.issuer_actor='v3_cas_inhibit_issuer_actor' AND a.state='ABORT_RECORDED_NOT_RELEASED';
   IF p_epoch_id NOT IN ('V3CAS-AUDIT-7fce8ba3fd714b008407d687e29f50f4','V3CAS-AUDIT-4c43add6968a46a6a8133a55ae92cf93', 'V3CAS-AUDIT-caafcb9247b0480b8925b154f8351935')
      OR e.paper_release_commit IS DISTINCT FROM '46c5abbd6af16266c1229943db973dc9d6b2fb4f'
      OR NOT ((p_epoch_id='V3CAS-AUDIT-7fce8ba3fd714b008407d687e29f50f4' AND e.original_fence_sha256='c9775bdeee0be54a2658fb7673180f2e499035830656300ad68067196e426e28')
        OR (p_epoch_id='V3CAS-AUDIT-4c43add6968a46a6a8133a55ae92cf93' AND e.original_fence_sha256='0e5ff6f9d2cc6b2b588a053d1ea7e2e7a8a9ada9f5744c5491699803aca0b025' AND e.source_sha256='989e1657e03867774907f3a1ec9c9f4f84ee70c2d4b7a258cad9dc3e480f0043')
        OR (p_epoch_id='V3CAS-AUDIT-caafcb9247b0480b8925b154f8351935' AND e.original_fence_sha256='d4b81e56c455348259d95514ff95b5a28bd057df4c576d912d8f3476d216537b' AND e.source_sha256='989e1657e03867774907f3a1ec9c9f4f84ee70c2d4b7a258cad9dc3e480f0043'))
      OR terminal_receipt IS NULL OR actor.rolcanlogin OR actor.rolconnlimit<>0
      OR e.sealed OR e.next_ordinal<>1
      OR EXISTS (SELECT FROM v3_cas_audit.executor_inhibit_v1 WHERE epoch_id=p_epoch_id)
      OR EXISTS (SELECT FROM v3_cas_audit.intent_v1) OR EXISTS (SELECT FROM v3_cas_audit.attempt_v1)
      OR NOT EXISTS (SELECT FROM public.paper_series WHERE status='active' AND series_id=e.predecessor_series_id)
   THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_READER_INHIBIT_HOLD'; END IF;
   RETURN jsonb_build_object(
     'kind','V3_PAPER_RELEASE_EPOCH_READER_V1','state','EXPIRED_STAGE4_ABORTED_BEFORE_INHIBIT',
     'observed_at_utc',to_char(clock_timestamp() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
     'release_commit',e.paper_release_commit,'epoch_id',p_epoch_id,'source_sha256',e.source_sha256,
     'fence_sha256',e.original_fence_sha256,'caller_acl_sha256',e.approved_caller_acl_sha256,
     'receipt_sha256',terminal_receipt);
 END IF;
 IF EXISTS (SELECT FROM v3_cas_audit.attempt_v1) THEN
   -- DISPATCH_UNKNOWN alone is never evidence of a committed rotation.
   -- Require the sole active successor to carry the exact sealed request.
   IF NOT installed OR NOT e.sealed OR e.next_ordinal<>2 OR actor.rolcanlogin OR actor.rolconnlimit<>0
      OR g.native_stop_at_utc IS NULL OR g.acknowledged_at_utc IS NULL OR g.receipt_sha256 IS NULL
      OR g.audit_intent_high_watermark IS DISTINCT FROM 1
      OR EXISTS (SELECT FROM v3_cas_audit.prepared_fence_abort_v1 WHERE epoch_id=p_epoch_id)
      OR (SELECT count(*) FROM v3_cas_audit.intent_v1)<>1
      OR (SELECT count(*) FROM v3_cas_audit.attempt_v1)<>1
      OR NOT EXISTS (SELECT FROM public.paper_series
          WHERE series_id=e.predecessor_series_id AND status='strategy_cutover_closed')
   THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_POSTCAS_CUSTODY_HOLD'; END IF;
   SELECT i0.* INTO i FROM v3_cas_audit.intent_v1 i0
     JOIN v3_cas_audit.attempt_v1 t ON t.intent_id=i0.intent_id AND t.epoch_id=i0.epoch_id
     WHERE i0.epoch_id=p_epoch_id AND i0.ordinal=1 AND i0.state='PREINVOKE_INTENT'
       AND i0.predecessor_series_id=e.predecessor_series_id AND i0.requested_rpc=e.expected_rpc
       AND i0.source_sha256=e.source_sha256 AND i0.fence_sha256=e.original_fence_sha256
       AND t.state='DISPATCH_UNKNOWN' AND t.emitter_actor='v3_cas_executor_actor'
       AND t.requested_rpc=e.expected_rpc AND t.request_sha256=i0.request_sha256
       AND t.source_sha256=i0.source_sha256 AND t.fence_sha256=i0.fence_sha256
       AND t.created_at_utc>=i0.created_at_utc;
   IF NOT FOUND THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_POSTCAS_ATTEMPT_DRIFT'; END IF;
   SELECT series_id,config INTO successor_id,successor_config FROM public.paper_series WHERE status='active'
     AND series_id ~ '^PAPER-V3-[0-9]{8}T[0-9]{6}Z$'
     AND config->>'series_id'=series_id AND config->>'predecessor_series_id'=e.predecessor_series_id
     AND config->>'release_repo_sha'=e.paper_release_commit
     AND config->>'runtime_bundle_fingerprint_sha256' ~ '^[a-f0-9]{64}$'
     AND config->>'strategy_fingerprint_sha256' ~ '^[a-f0-9]{64}$'
     AND config->>'paper_only'='true' AND config->>'real_money_actions_enabled'='false'
     AND config->>'automatic_activation_allowed'='false'
     AND config->>'preinvoke_epoch_id'=p_epoch_id AND config->>'preinvoke_intent_id'=i.intent_id::text
     AND config->>'preinvoke_request_sha256'=i.request_sha256
     AND config->>'preinvoke_source_sha256'=i.source_sha256 AND config->>'preinvoke_fence_sha256'=i.fence_sha256
     AND config->>'preinvoke_caller_acl_sha256'=e.approved_caller_acl_sha256
     AND config->>'preinvoke_inhibit_receipt_sha256'=g.receipt_sha256;
   IF NOT FOUND THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_POSTCAS_SUCCESSOR_HOLD'; END IF;
   witness_state:='CAS_COMMITTED_EXACT_SUCCESSOR_SINGLE_ACTIVE';
 ELSIF NOT EXISTS (SELECT FROM public.paper_series WHERE status='active' AND series_id=e.predecessor_series_id)
 THEN RAISE EXCEPTION 'V3_PAPER_FOLLOWUP_READER_EPOCH_OR_SERIES_HOLD';
 ELSIF EXISTS (SELECT FROM v3_cas_audit.prepared_fence_abort_v1
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
  'preinvoke_fence_sha256',e.original_fence_sha256,'preinvoke_inhibit_receipt_sha256',g.receipt_sha256)
  || CASE WHEN witness_state='CAS_COMMITTED_EXACT_SUCCESSOR_SINGLE_ACTIVE' THEN jsonb_build_object(
       'successor_series_id',successor_id,'repo_sha',successor_config->>'release_repo_sha',
       'bundle_sha256',successor_config->>'runtime_bundle_fingerprint_sha256',
       'strategy_sha256',successor_config->>'strategy_fingerprint_sha256')
     ELSE '{}'::jsonb END;
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
