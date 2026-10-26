-- READ ONLY: verifies Stage1A roles remain non-authenticating, zero privileges.
-- No secret value, pg_authid, role impersonation, CAS invoke, grants or data writes.
WITH actor AS (
 SELECT r.rolname,
        r.rolcanlogin, r.rolinherit, r.rolbypassrls, r.rolsuper,
        r.rolcreaterole,r.rolcreatedb,r.rolreplication,
        r.rolconnlimit,r.rolvaliduntil,
        pg_catalog.has_schema_privilege(r.rolname,'v3_cas_audit','USAGE') AS audit_usage,
        pg_catalog.has_table_privilege(r.rolname,'v3_cas_audit.epoch_v1',
                             'SELECT,INSERT,UPDATE,DELETE') AS epoch_access,
        pg_catalog.has_table_privilege(r.rolname,'v3_cas_audit.intent_v1',
                             'SELECT,INSERT,UPDATE,DELETE') AS intent_access,
        (SELECT count(*) FROM pg_catalog.pg_auth_members m
         WHERE m.member=r.oid) AS outgoing_memberships,
        (SELECT count(*) FROM pg_catalog.pg_auth_members m
         JOIN pg_catalog.pg_roles x ON x.oid=m.member
         WHERE m.roleid=r.oid AND x.rolname<>'postgres') AS non_postgres_incoming
 FROM pg_catalog.pg_roles r
 WHERE r.rolname IN ('v3_cas_audit_writer_actor',
                     'v3_cas_audit_reader_actor','v3_cas_executor_actor')
),
summary AS (
 SELECT count(*)=3 AND coalesce(bool_and(
    NOT rolcanlogin AND NOT rolinherit AND NOT rolbypassrls AND NOT rolsuper
    AND NOT rolcreaterole AND NOT rolcreatedb AND NOT rolreplication
    AND rolconnlimit=0
    AND rolvaliduntil < pg_catalog.clock_timestamp()
    AND NOT audit_usage AND NOT epoch_access AND NOT intent_access
    AND outgoing_memberships=0 AND non_postgres_incoming=0),false)
    AS three_shells_disabled,
    pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object(
     'name',rolname,'can_login',rolcanlogin,'connlimit',rolconnlimit,
     'valid_until_expired',rolvaliduntil<pg_catalog.clock_timestamp(),
     'schema_usage',audit_usage,'epoch_access',epoch_access,
     'intent_access',intent_access,'outgoing_memberships',outgoing_memberships,
     'non_postgres_incoming',non_postgres_incoming) ORDER BY rolname) AS actors
 FROM actor
)
SELECT pg_catalog.jsonb_build_object(
 'kind','V3_CAS_STAGE1A_DORMANT_ACTOR_READBACK_V1',
 'readback_utc',pg_catalog.clock_timestamp(),
 'actor_names',(SELECT actors FROM summary),
 'three_actor_shells_disabled',(SELECT three_shells_disabled FROM summary),
 'audit_epoch_rows',(SELECT count(*) FROM v3_cas_audit.epoch_v1),
 'audit_intent_rows',(SELECT count(*) FROM v3_cas_audit.intent_v1),
 'audit_force_rls',(SELECT count(*)=2 FROM pg_catalog.pg_class c
   JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname='v3_cas_audit' AND c.relname IN ('epoch_v1','intent_v1')
   AND c.relrowsecurity AND c.relforcerowsecurity),
 'audit_policies',(SELECT count(*) FROM pg_catalog.pg_policy p
   JOIN pg_catalog.pg_class c ON c.oid=p.polrelid
   JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname='v3_cas_audit'),
 'cas_rpc_installed',pg_catalog.to_regprocedure(
   'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
 ) IS NOT NULL,
 'active_original_paper',(SELECT count(*) FROM public.paper_series
   WHERE status='active' AND series_id='PAPER-V2R4-20261009T110135Z'),
 'active_paper_total',(SELECT count(*) FROM public.paper_series WHERE status='active'),
 'actual_credentialed_sessions_verified',false,
 'independent_external_attempt_custody_verified',false,
 'cas_dispatch_authorized',false,
 'v3_paper_release_authorized',false
) AS actor_stage1_readback;
