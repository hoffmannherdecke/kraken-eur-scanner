-- V3 PAPER / ISSUE #99 / READ ONLY diagnostic, never a migration.
-- This is a single SELECT. No role change, secret, password, DDL, DML,
-- SECURITY DEFINER invocation, backend CAS call or lock is requested.
-- Captures the actual PostgreSQL role grant graph and object existence.
-- The result CANNOT prove an authenticated separate connection, source
-- originality, WORM custody, completeness of CAS attempts, or Paper release.
-- It intentionally marks ALL execution/custody authority fields FALSE.
WITH wanted(rolname) AS (
 VALUES ('v3_cas_operator_login'),
        ('v3_cas_executor'),
        ('v3_cas_audit_writer'),
        ('v3_cas_audit_reader')
),
described AS (
 SELECT w.rolname,
        (r.oid IS NOT NULL) AS exists_now,
        r.rolcanlogin AS can_login,
        r.rolinherit AS inherits_privileges,
        r.rolbypassrls AS bypasses_rls,
        r.rolsuper AS is_superuser,
        r.rolcreaterole AS can_create_role,
        r.rolcreatedb AS can_create_database,
        r.rolreplication AS can_replicate,
        coalesce((
          SELECT pg_catalog.jsonb_agg(
            pg_catalog.jsonb_build_object(
              'direction',CASE WHEN m.roleid=r.oid THEN 'incoming' ELSE 'outgoing' END,
              'granted_role',granted.rolname,
              'member_role',member.rolname,
              'admin_option',m.admin_option,
              'inherit_option',m.inherit_option,
              'set_option',m.set_option
            ) ORDER BY granted.rolname, member.rolname
          )
          FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles granted ON granted.oid=m.roleid
          JOIN pg_catalog.pg_roles member ON member.oid=m.member
          WHERE m.roleid=r.oid OR m.member=r.oid
        ), '[]'::jsonb) AS memberships
 FROM wanted w
 LEFT JOIN pg_catalog.pg_roles r ON r.rolname=w.rolname
),
objects AS (
 SELECT
  (pg_catalog.to_regclass('v3_cas_audit.epoch_v1') IS NOT NULL) AS audit_epoch_installed,
  (pg_catalog.to_regclass('v3_cas_audit.intent_v1') IS NOT NULL) AS audit_intent_installed,
  (pg_catalog.to_regprocedure(
    'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
  ) IS NOT NULL) AS cas_rpc_installed
)
SELECT pg_catalog.jsonb_build_object(
 'kind','V3_CAS_ACTOR_CUSTODY_CATALOG_READONLY_V1',
 'catalog_read_at_utc',pg_catalog.to_char(
    pg_catalog.clock_timestamp() AT TIME ZONE 'UTC',
    'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
 'roles',(SELECT pg_catalog.jsonb_agg(
   pg_catalog.jsonb_build_object(
    'name',rolname, 'exists',exists_now, 'can_login',can_login,
    'inherits_privileges',inherits_privileges,'bypasses_rls',bypasses_rls,
    'is_superuser',is_superuser,'can_create_role',can_create_role,
    'can_create_database',can_create_database,'can_replicate',can_replicate,
    'memberships',memberships
   ) ORDER BY rolname) FROM described),
 'audit_epoch_installed',(SELECT audit_epoch_installed FROM objects),
 'audit_intent_installed',(SELECT audit_intent_installed FROM objects),
 'cas_rpc_installed',(SELECT cas_rpc_installed FROM objects),
 'authentic_independent_runtime_sessions_proven',false,
 'real_originalhost_tpm_signer_independence_proven',false,
 'external_complete_immutable_attempt_custody_proven',false,
 'cas_dispatch_authorized',false,
 'old_writer_auto_rearm_allowed',false,
 'v3_paper_release_authorized',false
) AS catalog_readonly_v1;
