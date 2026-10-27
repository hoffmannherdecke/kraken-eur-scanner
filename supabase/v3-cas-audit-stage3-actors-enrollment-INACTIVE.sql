-- V3 Paper / original Issue #99: ONE-TIME LOCAL ENROLLMENT TEMPLATE, INACTIVE.
-- NOT a migration. NEVER execute this template directly. Credentials are
-- generated ONLY on the user's single-user Notebook, never in GitHub/chat.
-- Requires already installed original Stage-2 private audit schema.
-- Limited to TWO existing actor shells; V3 CAS executor remains disabled.
-- Do not SELECT private Stage2 table rows as restricted postgres: the
-- original Stage2 ownership/ACL intentionally denies it. A separate
-- authenticated audit reader verifies row state after later enrollment.
-- Never creates an audit epoch/intent, CAS RPC, V3 Paper series or Task.
DO $v3_cas_stage3_audit_actors$
DECLARE
 v_reader text := '__READER_SCRAM_SHA256_VERIFIER__';
 v_writer text := '__WRITER_SCRAM_SHA256_VERIFIER__';
BEGIN
  RAISE EXCEPTION 'V3_STAGE3_LOCAL_ENROLLMENT_TEMPLATE_INACTIVE';

  IF current_user <> 'postgres' OR current_database() <> 'postgres'
     OR pg_catalog.to_regnamespace('v3_cas_audit') IS NULL
     OR pg_catalog.to_regprocedure('v3_cas_audit.append_intent_v1(text,uuid,text,text,text)') IS NULL
     OR pg_catalog.to_regprocedure(
       'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
       ) IS NOT NULL
     OR (SELECT count(*) FROM public.paper_series WHERE status='active') <> 1
     OR (SELECT count(*) FROM public.paper_series WHERE status='active'
         AND series_id='PAPER-V2R4-20261009T110135Z') <> 1
     THEN
    RAISE EXCEPTION 'V3_STAGE3_STAGE2_OR_ORIGINAL_SERIES_NOT_READY';
  END IF;
  IF v_writer !~ '^SCRAM-SHA-256\$4096:[A-Za-z0-9+/]{22}==\$[A-Za-z0-9+/]{43}=:[A-Za-z0-9+/]{43}=$'
     OR v_reader !~ '^SCRAM-SHA-256\$4096:[A-Za-z0-9+/]{22}==\$[A-Za-z0-9+/]{43}=:[A-Za-z0-9+/]{43}=$'
     OR v_reader = v_writer THEN
    RAISE EXCEPTION 'V3_STAGE3_TWO_DISTINCT_SCRAM_VERIFIERS_REQUIRED';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_class c
      JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname='v3_cas_audit' AND c.relname IN ('epoch_v1','intent_v1')
        AND c.relkind='r' AND c.relrowsecurity AND c.relforcerowsecurity
        AND pg_catalog.pg_get_userbyid(c.relowner)='v3_cas_audit_table_owner') <> 2
    OR (SELECT count(*) FROM pg_catalog.pg_policy p
        JOIN pg_catalog.pg_class c ON c.oid=p.polrelid
        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='v3_cas_audit') <> 6
    OR NOT pg_catalog.has_function_privilege('v3_cas_audit_writer',
           'v3_cas_audit.append_intent_v1(text,uuid,text,text,text)','EXECUTE')
    OR pg_catalog.has_function_privilege('v3_cas_audit_reader',
           'v3_cas_audit.append_intent_v1(text,uuid,text,text,text)','EXECUTE')
    OR NOT pg_catalog.has_table_privilege('v3_cas_audit_reader',
           'v3_cas_audit.intent_v1','SELECT')
    OR pg_catalog.has_table_privilege('v3_cas_audit_writer',
           'v3_cas_audit.intent_v1','INSERT')
    OR EXISTS(SELECT 1 FROM pg_catalog.pg_roles r
        WHERE r.rolname IN ('anon','authenticated','service_role','v3_cas_operator_login')
        AND (pg_catalog.has_schema_privilege(r.rolname,'v3_cas_audit','USAGE')
          OR pg_catalog.has_function_privilege(r.rolname,
             'v3_cas_audit.append_intent_v1(text,uuid,text,text,text)','EXECUTE')))
    THEN
    RAISE EXCEPTION 'V3_STAGE3_STAGE2_PRIVATE_ACL_DRIFT_HOLD';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_roles r
      WHERE r.rolname IN ('v3_cas_audit_writer_actor','v3_cas_audit_reader_actor')
        AND NOT r.rolcanlogin AND NOT r.rolinherit AND NOT r.rolbypassrls
        AND NOT r.rolsuper AND NOT r.rolcreaterole AND NOT r.rolcreatedb
        AND NOT r.rolreplication AND r.rolconnlimit=0
        AND r.rolvaliduntil < pg_catalog.clock_timestamp()
        AND (SELECT count(*) FROM pg_catalog.pg_auth_members m WHERE m.member=r.oid)=0
        AND (SELECT count(*) FROM pg_catalog.pg_auth_members m WHERE m.roleid=r.oid)=1
        AND EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members m
             JOIN pg_catalog.pg_roles g ON g.oid=m.member
             WHERE m.roleid=r.oid AND g.rolname='postgres'
               AND m.admin_option AND NOT m.set_option AND NOT m.inherit_option)
     ) <> 2
     OR (SELECT count(*) FROM pg_catalog.pg_roles r WHERE r.rolname='v3_cas_executor_actor'
           AND NOT r.rolcanlogin AND r.rolconnlimit=0
           AND r.rolvaliduntil < pg_catalog.clock_timestamp()) <> 1
     OR (SELECT count(*) FROM pg_catalog.pg_roles r
         WHERE r.rolname IN ('v3_cas_audit_reader','v3_cas_audit_writer','v3_cas_executor')
           AND NOT r.rolcanlogin AND NOT r.rolinherit AND NOT r.rolbypassrls) <> 3 THEN
    RAISE EXCEPTION 'V3_STAGE3_ACTOR_OR_GROUP_ROLE_DRIFT_HOLD';
  END IF;
  -- PG17 admin membership on original group roles permits only two
  -- explicitly scoped grants. NO INHERIT: caller must choose exactly its
  -- approved NOLOGIN capability with SET ROLE in its own TLS session.
  GRANT v3_cas_audit_writer TO v3_cas_audit_writer_actor
    WITH ADMIN FALSE, INHERIT FALSE, SET TRUE;
  GRANT v3_cas_audit_reader TO v3_cas_audit_reader_actor
    WITH ADMIN FALSE, INHERIT FALSE, SET TRUE;
  EXECUTE format('ALTER ROLE v3_cas_audit_writer_actor LOGIN CONNECTION LIMIT 1 VALID UNTIL %L PASSWORD %L',
    'infinity',v_writer);
  EXECUTE format('ALTER ROLE v3_cas_audit_reader_actor LOGIN CONNECTION LIMIT 1 VALID UNTIL %L PASSWORD %L',
    'infinity',v_reader);
  IF (SELECT count(*) FROM pg_catalog.pg_roles r
      WHERE r.rolname IN ('v3_cas_audit_writer_actor','v3_cas_audit_reader_actor')
        AND r.rolcanlogin AND NOT r.rolinherit AND NOT r.rolbypassrls
        AND NOT r.rolsuper AND NOT r.rolcreaterole AND NOT r.rolcreatedb
        AND r.rolconnlimit=1) <> 2
     OR (SELECT count(*) FROM pg_catalog.pg_auth_members m
           JOIN pg_catalog.pg_roles a ON a.oid=m.member
           JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
           WHERE ((a.rolname='v3_cas_audit_writer_actor' AND g.rolname='v3_cas_audit_writer')
              OR (a.rolname='v3_cas_audit_reader_actor' AND g.rolname='v3_cas_audit_reader'))
            AND NOT m.admin_option AND NOT m.inherit_option AND m.set_option) <> 2
     OR (SELECT count(*) FROM pg_catalog.pg_roles r
           WHERE r.rolname='v3_cas_executor_actor'
             AND NOT r.rolcanlogin AND r.rolconnlimit=0
             AND r.rolvaliduntil < pg_catalog.clock_timestamp()) <> 1 THEN
    RAISE EXCEPTION 'V3_STAGE3_POST_ENROLLMENT_DRIFT_ROLLBACK';
  END IF;
END
$v3_cas_stage3_audit_actors$;
