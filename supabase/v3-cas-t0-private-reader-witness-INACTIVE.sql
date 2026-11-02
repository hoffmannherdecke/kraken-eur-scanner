-- V3 Issue #99: restricted, current-only private CAS audit witness.
-- SOURCE INACTIVE. NEVER execute directly in production.
-- Reuses existing v3_cas_audit owner and the pre-enrolled Notebook reader actor.
-- No additional CAS executor, scheduler, issuer, table, general SELECT grant,
-- paper activation, native STOP, restore, or audit history backfill.
-- This is NOT historical NEVER, liveness continuity, independent signature or T0.
-- Deployment requires separate reviewed one-time source-lock removal,
-- migration approval, PG17 negative tests, and original catalog/ACL readback.
DO $v3_t0_witness_install_locked$
BEGIN
  RAISE EXCEPTION 'V3_T0_READER_WITNESS_SOURCE_INACTIVE_APPROVAL_REQUIRED';
  IF session_user <> 'postgres'
     OR pg_catalog.to_regprocedure('v3_cas_audit.read_forward_t0_current_v1()') IS NOT NULL
     OR pg_catalog.to_regclass('v3_cas_audit.epoch_v1') IS NULL
     OR pg_catalog.to_regclass('v3_cas_audit.intent_v1') IS NULL
     OR pg_catalog.to_regclass('v3_cas_audit.attempt_v1') IS NULL
     OR pg_catalog.to_regclass('v3_cas_audit.executor_inhibit_v1') IS NULL
     OR (SELECT rolcanlogin FROM pg_catalog.pg_roles
          WHERE rolname='v3_cas_audit_reader_actor') IS DISTINCT FROM TRUE
     OR (SELECT rolcanlogin FROM pg_catalog.pg_roles
          WHERE rolname='v3_cas_audit_reader') IS DISTINCT FROM FALSE
     OR NOT pg_catalog.pg_has_role(
          'v3_cas_audit_reader_actor','v3_cas_audit_reader','SET')
     OR pg_catalog.has_table_privilege(
          'v3_cas_audit_reader','v3_cas_audit.attempt_v1','SELECT')
     OR pg_catalog.has_table_privilege(
          'v3_cas_audit_reader','v3_cas_audit.executor_inhibit_v1','SELECT')
  THEN
    RAISE EXCEPTION 'V3_T0_READER_WITNESS_ORIGINAL_ROLE_OR_CATALOG_HOLD';
  END IF;

  -- Dynamic CREATE and GRANT execute within one atomic DO, never expose
  -- SECURITY DEFINER via a separate autocommit window.
  EXECUTE $v3_t0_create$
    CREATE FUNCTION v3_cas_audit.read_forward_t0_current_v1()
    RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = 'pg_catalog'
    AS $v3_t0_fn$
    BEGIN
      -- SECURITY DEFINER changes current_user. The session role is checked
      -- using session_user plus the actual SET ROLE GUC.
      IF session_user <> 'v3_cas_audit_reader_actor'
         OR pg_catalog.current_setting('role',true) <> 'v3_cas_audit_reader'
      THEN
        RAISE EXCEPTION 'V3_T0_READER_WITNESS_WRONG_ACTOR_OR_ROLE';
      END IF;
      RETURN pg_catalog.jsonb_build_object(
        'kind','V3_CAS_FORWARD_T0_CURRENT_CATALOG_READONLY_V1',
        'observed_at_utc',pg_catalog.to_char(
          pg_catalog.clock_timestamp() AT TIME ZONE 'UTC',
          'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
        'actor',session_user,
        'requested_role','v3_cas_audit_reader',
        'active_series_count',(SELECT count(*) FROM public.paper_series
                               WHERE status='active'),
        'original_active_series_count',(SELECT count(*) FROM public.paper_series
             WHERE status='active'
               AND series_id='PAPER-V2R4-20261009T110135Z'),
        'epoch_count',(SELECT count(*) FROM v3_cas_audit.epoch_v1),
        'intent_count',(SELECT count(*) FROM v3_cas_audit.intent_v1),
        'attempt_count',(SELECT count(*) FROM v3_cas_audit.attempt_v1),
        'dispatch_unknown_count',(SELECT count(*) FROM v3_cas_audit.attempt_v1
                                   WHERE state='DISPATCH_UNKNOWN'),
        'inhibit_count',(SELECT count(*) FROM v3_cas_audit.executor_inhibit_v1),
        'cas_rpc_count',(SELECT count(*) FROM pg_catalog.pg_proc p
                JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
                WHERE n.nspname='public'
                  AND p.proname='rotate_v2r4_to_v3_experimental_paper'),
        'executor_can_login',(SELECT rolcanlogin FROM pg_catalog.pg_roles
                              WHERE rolname='v3_cas_executor_actor'),
        'history_never_proven',false,
        'complete_attempt_unknown_custody_authenticated',false,
        't0_authenticated',false,
        'armed_marker_cancel_authorized',false,
        'native_stop_restore_authorized',false,
        'cas_or_v3_paper_authorized',false
      );
    END
    $v3_t0_fn$;
  $v3_t0_create$;

  EXECUTE 'REVOKE ALL ON FUNCTION v3_cas_audit.read_forward_t0_current_v1()
    FROM PUBLIC, anon, authenticated, service_role,
         v3_cas_audit_reader_actor, v3_cas_audit_writer,
         v3_cas_executor_actor, v3_cas_operator_login';
  EXECUTE 'GRANT EXECUTE ON FUNCTION v3_cas_audit.read_forward_t0_current_v1()
    TO v3_cas_audit_reader';

  IF NOT pg_catalog.has_function_privilege(
           'v3_cas_audit_reader',
           'v3_cas_audit.read_forward_t0_current_v1()','EXECUTE')
     OR pg_catalog.has_function_privilege(
           'service_role',
           'v3_cas_audit.read_forward_t0_current_v1()','EXECUTE')
     OR pg_catalog.has_function_privilege(
           'anon',
           'v3_cas_audit.read_forward_t0_current_v1()','EXECUTE')
     OR pg_catalog.has_table_privilege(
           'v3_cas_audit_reader','v3_cas_audit.attempt_v1','SELECT')
     OR pg_catalog.has_table_privilege(
           'v3_cas_audit_reader','v3_cas_audit.executor_inhibit_v1','SELECT')
  THEN
    RAISE EXCEPTION 'V3_T0_READER_WITNESS_POSTINSTALL_ACL_HOLD';
  END IF;
END
$v3_t0_witness_install_locked$;
