-- Fresh separate transaction: original catalog readback, never installation.
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='15s';
DO $readback$
BEGIN
 IF session_user <> 'postgres' OR current_user <> 'postgres' OR current_database() <> 'postgres'
    OR (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='v3_cas_audit' AND c.relname='prepared_fence_abort_v1'
          AND c.relkind='r' AND c.relrowsecurity AND c.relforcerowsecurity
          AND pg_get_userbyid(c.relowner)='v3_cas_audit_table_owner') <> 1
    OR pg_has_role('postgres','v3_cas_audit_table_owner','SET')
    OR has_schema_privilege('v3_cas_audit_table_owner','v3_cas_audit','CREATE')
    OR NOT has_table_privilege('v3_cas_audit_reader','v3_cas_audit.prepared_fence_abort_v1','SELECT')
    OR has_table_privilege('v3_cas_audit_reader','v3_cas_audit.prepared_fence_abort_v1','INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
    OR EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('anon','authenticated','service_role',
       'v3_cas_operator_login','v3_cas_executor','v3_cas_executor_actor','v3_cas_audit_writer',
       'v3_cas_audit_writer_actor','v3_cas_audit_reader_actor','v3_cas_inhibit_issuer_actor')
       AND has_table_privilege(rolname,'v3_cas_audit.prepared_fence_abort_v1','SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'))
    OR (SELECT count(*) FROM pg_policy WHERE polrelid='v3_cas_audit.prepared_fence_abort_v1'::regclass) <> 2
    OR (SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgenabled='O'
        AND ((tgrelid='v3_cas_audit.intent_v1'::regclass AND tgname='v3_reject_aborted_intent_insert_v1')
          OR (tgrelid='v3_cas_audit.attempt_v1'::regclass AND tgname='v3_reject_aborted_attempt_insert_v1'))
        AND tgfoid='v3_cas_audit.reject_aborted_epoch_dispatch_v1()'::regprocedure) <> 2
    OR (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='v3_cas_audit' AND p.proname IN ('record_prepared_fence_abort_v1',
         'read_committed_pre_stop_inhibit_v1','reject_aborted_epoch_dispatch_v1')
         AND p.prosecdef AND pg_get_userbyid(p.proowner)='v3_cas_audit_table_owner'
         AND p.proconfig=ARRAY['search_path=pg_catalog, v3_cas_audit']) <> 3
    OR EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('v3_cas_executor','v3_cas_executor_actor') AND rolcanlogin)
    OR EXISTS (SELECT 1 FROM pg_stat_activity WHERE usename IN ('v3_cas_executor','v3_cas_executor_actor'))
    OR to_regprocedure('public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)') IS NOT NULL
 THEN RAISE EXCEPTION 'V3_RELEASE_ORIGINAL_CATALOG_READBACK_HOLD'; END IF;
END $readback$;
SELECT json_build_object(
 'kind','V3_ONE_TIME_ABORT_INSTALL_READBACK_V1','verified',true,
 'observed_at_utc',to_char(clock_timestamp() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
 'installation',obj_description('v3_cas_audit.prepared_fence_abort_v1'::regclass,'pg_class')::json,
 'function_bodies',(SELECT json_agg(json_build_object('name',p.proname,'body',p.prosrc) ORDER BY p.proname)
   FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
   WHERE n.nspname='v3_cas_audit' AND p.proname IN ('record_prepared_fence_abort_v1',
     'read_committed_pre_stop_inhibit_v1','reject_aborted_epoch_dispatch_v1')),
 'policies',(SELECT json_agg(json_build_object('table_name',tablename,'policy_name',policyname,
   'roles',roles,'command',cmd,'using_expression',qual,'check_expression',with_check) ORDER BY tablename,policyname)
   FROM pg_policies WHERE schemaname='v3_cas_audit' AND policyname IN (
    'v3_cas_epoch_owner_abort_read_v1','v3_cas_epoch_owner_abort_update_v1','v3_cas_intent_owner_abort_read_v1',
    'v3_prepared_abort_owner_only_v1','v3_prepared_abort_reader_select_v1')),
 'function_acl',(SELECT json_agg(json_build_object('function_name',p.proname,
   'grantee',CASE WHEN x.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee) END,
   'privilege',x.privilege_type,'grantable',x.is_grantable) ORDER BY p.proname,x.grantee)
   FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
   CROSS JOIN LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) x
   WHERE n.nspname='v3_cas_audit' AND p.proname IN ('record_prepared_fence_abort_v1',
    'read_committed_pre_stop_inhibit_v1','reject_aborted_epoch_dispatch_v1'))
);
COMMIT;
