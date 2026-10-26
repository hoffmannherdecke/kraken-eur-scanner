-- V3 Paper #99 / SECURITY Stage 1A: dormant distinct future caller shells.
-- Requires user-approved live Stage 0. One atomic transaction, no secrets,
-- grants, LOGIN capability, usable DB connection, append/CAS functions, or Paper mutation.
-- Deliberately no autonomous enrollment, no service_role or postgres-as-caller.
DO $v3_actor_stage1_disabled$
DECLARE
 v_original_role_count integer;
BEGIN
 IF current_user <> 'postgres' OR current_database() <> 'postgres' THEN
  RAISE EXCEPTION 'V3_STAGE1_UNEXPECTED_OWNER_OR_DATABASE_HOLD';
 END IF;
 IF pg_catalog.to_regnamespace('v3_cas_audit') IS NULL
    OR pg_catalog.to_regclass('v3_cas_audit.epoch_v1') IS NULL
    OR pg_catalog.to_regclass('v3_cas_audit.intent_v1') IS NULL
    OR pg_catalog.to_regprocedure(
     'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
    ) IS NOT NULL THEN
  RAISE EXCEPTION 'V3_STAGE1_STAGE0_OR_CAS_GUARD_HOLD';
 END IF;
 IF (SELECT count(*) FROM pg_catalog.pg_class c
     JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
     WHERE n.nspname='v3_cas_audit'
      AND c.relname IN ('epoch_v1','intent_v1')
      AND c.relkind='r' AND c.relrowsecurity AND c.relforcerowsecurity) <> 2
    OR (SELECT count(*) FROM pg_catalog.pg_policy p
        JOIN pg_catalog.pg_class c ON c.oid=p.polrelid
        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='v3_cas_audit') <> 0
    OR EXISTS(SELECT 1 FROM v3_cas_audit.epoch_v1)
    OR EXISTS(SELECT 1 FROM v3_cas_audit.intent_v1) THEN
  RAISE EXCEPTION 'V3_STAGE1_QUARANTINE_TABLES_NOT_EMPTY_LOCKED_HOLD';
 END IF;
 IF (SELECT r.rolname FROM pg_catalog.pg_namespace n
     JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner
     WHERE n.nspname='v3_cas_audit') <> 'postgres' THEN
  RAISE EXCEPTION 'V3_STAGE1_SCHEMA_OWNER_DRIFT_HOLD';
 END IF;
 IF (SELECT count(*) FROM public.paper_series WHERE status='active') <> 1
    OR (SELECT count(*) FROM public.paper_series
        WHERE status='active' AND series_id='PAPER-V2R4-20261009T110135Z') <> 1 THEN
  RAISE EXCEPTION 'V3_STAGE1_ORIGINAL_V2R4_ONLY_HOLD';
 END IF;
 IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles
    WHERE rolname IN ('v3_cas_audit_writer_actor',
                      'v3_cas_audit_reader_actor','v3_cas_executor_actor')) THEN
  RAISE EXCEPTION 'V3_STAGE1_ACTOR_NAME_ALREADY_PRESENT_NO_REPAIR';
 END IF;
 SELECT count(*) INTO v_original_role_count FROM pg_catalog.pg_roles r
 WHERE r.rolname IN ('v3_cas_operator_login','v3_cas_executor',
                     'v3_cas_audit_writer','v3_cas_audit_reader')
  AND NOT r.rolinherit AND NOT r.rolbypassrls AND NOT r.rolsuper
  AND NOT r.rolcreaterole AND NOT r.rolcreatedb AND NOT r.rolreplication
  AND r.rolcanlogin=(r.rolname='v3_cas_operator_login')
  AND (SELECT count(*) FROM pg_catalog.pg_auth_members m
       WHERE m.roleid=r.oid OR m.member=r.oid)=1
  AND EXISTS(
    SELECT 1 FROM pg_catalog.pg_auth_members m
    JOIN pg_catalog.pg_roles a ON a.oid=m.member
    WHERE m.roleid=r.oid AND a.rolname='postgres'
      AND m.admin_option AND NOT m.inherit_option AND NOT m.set_option
  );
 IF v_original_role_count <> 4 THEN
  RAISE EXCEPTION 'V3_STAGE1_ORIGINAL_ACTOR_GROUP_GRAPH_DRIFT_HOLD';
 END IF;
 IF EXISTS (
  SELECT 1 FROM pg_catalog.pg_roles r
  WHERE r.rolname IN ('anon','authenticated','service_role',
                      'v3_cas_operator_login','v3_cas_executor',
                      'v3_cas_audit_reader','v3_cas_audit_writer')
    AND (pg_catalog.has_schema_privilege(r.rolname,'v3_cas_audit','USAGE')
      OR pg_catalog.has_table_privilege(r.rolname,'v3_cas_audit.epoch_v1',
                                          'SELECT,INSERT,UPDATE,DELETE')
      OR pg_catalog.has_table_privilege(r.rolname,'v3_cas_audit.intent_v1',
                                          'SELECT,INSERT,UPDATE,DELETE'))
 ) THEN
  RAISE EXCEPTION 'V3_STAGE1_ORIGINAL_QUARANTINE_ACCESS_DRIFT_HOLD';
 END IF;
 -- Separate role identities, deliberately unusable. Later provisioning
 -- must have its own secure credential delivery, bounded membership grants,
 -- originalhost/DBA threat review and external custody acknowledgements.
 CREATE ROLE v3_cas_audit_writer_actor
  NOSUPERUSER NOLOGIN NOINHERIT NOBYPASSRLS NOCREATEDB NOCREATEROLE
  NOREPLICATION CONNECTION LIMIT 0 PASSWORD NULL VALID UNTIL '2000-01-01';
 CREATE ROLE v3_cas_audit_reader_actor
  NOSUPERUSER NOLOGIN NOINHERIT NOBYPASSRLS NOCREATEDB NOCREATEROLE
  NOREPLICATION CONNECTION LIMIT 0 PASSWORD NULL VALID UNTIL '2000-01-01';
 CREATE ROLE v3_cas_executor_actor
  NOSUPERUSER NOLOGIN NOINHERIT NOBYPASSRLS NOCREATEDB NOCREATEROLE
  NOREPLICATION CONNECTION LIMIT 0 PASSWORD NULL VALID UNTIL '2000-01-01';
 IF (SELECT count(*) FROM pg_catalog.pg_roles
     WHERE rolname IN ('v3_cas_audit_writer_actor','v3_cas_audit_reader_actor',
                       'v3_cas_executor_actor')
       AND NOT rolcanlogin AND NOT rolinherit AND NOT rolbypassrls
       AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole
       AND NOT rolreplication AND rolconnlimit=0
       AND rolvaliduntil < pg_catalog.clock_timestamp()) <> 3 THEN
  RAISE EXCEPTION 'V3_STAGE1_NEW_ACTOR_FAILCLOSED_ATTRS_HOLD';
 END IF;
 IF EXISTS(
  SELECT 1 FROM pg_catalog.pg_auth_members m
  JOIN pg_catalog.pg_roles r ON r.oid=m.member
  WHERE r.rolname IN ('v3_cas_audit_writer_actor','v3_cas_audit_reader_actor',
                      'v3_cas_executor_actor')
 ) OR EXISTS(
  SELECT 1 FROM pg_catalog.pg_auth_members m
  JOIN pg_catalog.pg_roles r ON r.oid=m.roleid
  JOIN pg_catalog.pg_roles x ON x.oid=m.member
  WHERE r.rolname IN ('v3_cas_audit_writer_actor','v3_cas_audit_reader_actor',
                      'v3_cas_executor_actor')
    AND x.rolname <> 'postgres'
 ) THEN
  RAISE EXCEPTION 'V3_STAGE1_UNEXPECTED_ACTOR_MEMBERSHIP_HOLD';
 END IF;
 IF EXISTS(
  SELECT 1 FROM pg_catalog.pg_roles r
  WHERE r.rolname IN ('v3_cas_audit_writer_actor','v3_cas_audit_reader_actor',
                      'v3_cas_executor_actor')
    AND (pg_catalog.has_schema_privilege(r.rolname,'v3_cas_audit','USAGE')
      OR pg_catalog.has_table_privilege(r.rolname,'v3_cas_audit.epoch_v1',
                                           'SELECT,INSERT,UPDATE,DELETE')
      OR pg_catalog.has_table_privilege(r.rolname,'v3_cas_audit.intent_v1',
                                           'SELECT,INSERT,UPDATE,DELETE'))
 ) THEN
  RAISE EXCEPTION 'V3_STAGE1_UNEXPECTED_ACTOR_AUDIT_PRIVILEGE_HOLD';
 END IF;
END
$v3_actor_stage1_disabled$;
