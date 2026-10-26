-- V3 Paper Issue #99: production stage-0 audit storage ONLY; explicitly user-approved 2026-10-26.
-- Executes as ONE atomic DO statement. No secrets, actor LOGINs, role membership,
-- owner changes, audit append EXECUTE, CAS RPC, CAS grants, functions, tasks, or live writer changes.
-- FAIL CLOSED if original Cloud prereqs differ. DBA/postgres remains an acknowledged tamper exception.
DO $v3_stage0_private$
DECLARE v_count integer;
BEGIN
  IF pg_catalog.to_regnamespace('v3_cas_audit') IS NOT NULL
     OR pg_catalog.to_regclass('v3_cas_audit.epoch_v1') IS NOT NULL
     OR pg_catalog.to_regclass('v3_cas_audit.intent_v1') IS NOT NULL THEN
    RAISE EXCEPTION 'V3_STAGE0_ALREADY_PRESENT_ABORT_WITHOUT_REPAIR';
  END IF;
  IF pg_catalog.to_regprocedure(
      'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
     ) IS NOT NULL THEN
    RAISE EXCEPTION 'V3_STAGE0_CAS_ALREADY_INSTALLED_ABORT';
  END IF;
  SELECT count(*) INTO v_count FROM pg_catalog.pg_roles r
    WHERE r.rolname IN ('v3_cas_audit_reader','v3_cas_audit_writer',
                       'v3_cas_executor','v3_cas_operator_login')
      AND NOT r.rolinherit AND NOT r.rolbypassrls AND NOT r.rolsuper
      AND NOT r.rolcreaterole AND NOT r.rolcreatedb AND NOT r.rolreplication
      AND r.rolcanlogin = (r.rolname = 'v3_cas_operator_login')
      AND (SELECT count(*) FROM pg_catalog.pg_auth_members m
           WHERE m.roleid=r.oid OR m.member=r.oid) = 1
      AND EXISTS (
         SELECT 1 FROM pg_catalog.pg_auth_members m
         JOIN pg_catalog.pg_roles c ON c.oid=m.member
         WHERE m.roleid=r.oid AND c.rolname='postgres'
           AND m.admin_option AND NOT m.inherit_option AND NOT m.set_option
      );
  IF v_count <> 4 THEN
    RAISE EXCEPTION 'V3_STAGE0_ROLE_GRAPH_DRIFT_ABORT';
  END IF;
  IF (SELECT count(*) FROM public.paper_series WHERE status='active') <> 1
     OR (SELECT count(*) FROM public.paper_series
         WHERE status='active'
           AND series_id='PAPER-V2R4-20261009T110135Z') <> 1 THEN
    RAISE EXCEPTION 'V3_STAGE0_ORIGINAL_V2R4_NOT_SOLE_ACTIVE_ABORT';
  END IF;

  CREATE SCHEMA v3_cas_audit;
  REVOKE ALL ON SCHEMA v3_cas_audit FROM PUBLIC, anon, authenticated,
       service_role, v3_cas_operator_login, v3_cas_executor,
       v3_cas_audit_writer, v3_cas_audit_reader;

  CREATE TABLE v3_cas_audit.epoch_v1 (
    epoch_id text PRIMARY KEY
      CHECK (epoch_id ~ '^V3CAS-AUDIT-[a-f0-9]{32}$'),
    predecessor_series_id text NOT NULL
      CHECK (predecessor_series_id = 'PAPER-V2R4-20261009T110135Z'),
    expected_rpc text NOT NULL
      CHECK (expected_rpc = 'public.rotate_v2r4_to_v3_experimental_paper'),
    source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[a-f0-9]{64}$'),
    original_fence_sha256 text NOT NULL CHECK (original_fence_sha256 ~ '^[a-f0-9]{64}$'),
    approved_caller_acl_sha256 text NOT NULL
      CHECK (approved_caller_acl_sha256 ~ '^[a-f0-9]{64}$'),
    opened_at_utc timestamptz NOT NULL DEFAULT clock_timestamp(),
    next_ordinal bigint NOT NULL DEFAULT 1 CHECK (next_ordinal >= 1),
    sealed boolean NOT NULL DEFAULT false
  );

  CREATE TABLE v3_cas_audit.intent_v1 (
    epoch_id text NOT NULL REFERENCES v3_cas_audit.epoch_v1(epoch_id),
    ordinal bigint NOT NULL CHECK (ordinal >= 1),
    intent_id uuid NOT NULL UNIQUE,
    requested_rpc text NOT NULL
      CHECK (requested_rpc = 'public.rotate_v2r4_to_v3_experimental_paper'),
    predecessor_series_id text NOT NULL
      CHECK (predecessor_series_id = 'PAPER-V2R4-20261009T110135Z'),
    request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[a-f0-9]{64}$'),
    source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[a-f0-9]{64}$'),
    fence_sha256 text NOT NULL CHECK (fence_sha256 ~ '^[a-f0-9]{64}$'),
    created_at_utc timestamptz NOT NULL DEFAULT clock_timestamp(),
    state text NOT NULL DEFAULT 'PREINVOKE_INTENT'
      CHECK (state='PREINVOKE_INTENT'),
    PRIMARY KEY (epoch_id, ordinal)
  );

  ALTER TABLE v3_cas_audit.epoch_v1 ENABLE ROW LEVEL SECURITY;
  ALTER TABLE v3_cas_audit.epoch_v1 FORCE ROW LEVEL SECURITY;
  ALTER TABLE v3_cas_audit.intent_v1 ENABLE ROW LEVEL SECURITY;
  ALTER TABLE v3_cas_audit.intent_v1 FORCE ROW LEVEL SECURITY;

  -- No policies, no callable SQL, no INSERT/UPDATE/DELETE/SELECT access
  -- to any application role. The entire schema is quarantined by default.
  REVOKE ALL ON ALL TABLES IN SCHEMA v3_cas_audit
    FROM PUBLIC, anon, authenticated, service_role,
         v3_cas_operator_login, v3_cas_executor,
         v3_cas_audit_writer, v3_cas_audit_reader;
  ALTER DEFAULT PRIVILEGES IN SCHEMA v3_cas_audit
    REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated, service_role;
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_namespace n
    JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner
    WHERE n.nspname='v3_cas_audit' AND r.rolname <> current_user
  ) THEN
    RAISE EXCEPTION 'V3_STAGE0_UNEXPECTED_SCHEMA_OWNER_ABORT';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_policy
       WHERE polrelid IN ('v3_cas_audit.epoch_v1'::regclass,
                          'v3_cas_audit.intent_v1'::regclass)) <> 0 THEN
    RAISE EXCEPTION 'V3_STAGE0_UNEXPECTED_POLICY_ABORT';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles r
    WHERE r.rolname IN ('anon','authenticated','service_role',
                       'v3_cas_operator_login','v3_cas_executor',
                       'v3_cas_audit_writer','v3_cas_audit_reader')
      AND (pg_catalog.has_schema_privilege(r.rolname,'v3_cas_audit','USAGE')
        OR pg_catalog.has_table_privilege(r.rolname,
          'v3_cas_audit.epoch_v1','SELECT,INSERT,UPDATE,DELETE')
        OR pg_catalog.has_table_privilege(r.rolname,
          'v3_cas_audit.intent_v1','SELECT,INSERT,UPDATE,DELETE'))
  ) THEN
    RAISE EXCEPTION 'V3_STAGE0_ANY_RUNTIME_ACCESS_ABORT';
  END IF;
END
$v3_stage0_private$;
