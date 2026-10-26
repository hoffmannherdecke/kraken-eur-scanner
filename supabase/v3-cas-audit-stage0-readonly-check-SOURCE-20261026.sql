-- Read-only AFTER stage-0 activation, not a release/credential/TPM/custody proof.
-- Requires the two private relations to exist; never run against pre-stage0 Cloud.
WITH catalog AS (
 SELECT
  (SELECT count(*) FROM pg_catalog.pg_class c
   JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname='v3_cas_audit' AND c.relname IN ('epoch_v1','intent_v1')
     AND c.relkind='r' AND c.relrowsecurity AND c.relforcerowsecurity)=2 AS rls_forced,
  (SELECT count(*) FROM pg_catalog.pg_policies
   WHERE schemaname='v3_cas_audit')=0 AS zero_policies,
  (SELECT count(*) FROM v3_cas_audit.epoch_v1)=0 AS zero_epochs,
  (SELECT count(*) FROM v3_cas_audit.intent_v1)=0 AS zero_intents,
  (SELECT r.rolname FROM pg_catalog.pg_namespace n
   JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner
   WHERE n.nspname='v3_cas_audit') AS schema_owner,
  pg_catalog.to_regprocedure(
   'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
   ) IS NOT NULL AS cas_installed
), actor AS (
 SELECT r.rolname,
    pg_catalog.has_schema_privilege(r.rolname,'v3_cas_audit','USAGE') AS schema_usage,
    pg_catalog.has_table_privilege(r.rolname,'v3_cas_audit.epoch_v1',
                                  'SELECT,INSERT,UPDATE,DELETE') AS epoch_dml,
    pg_catalog.has_table_privilege(r.rolname,'v3_cas_audit.intent_v1',
                                  'SELECT,INSERT,UPDATE,DELETE') AS intent_dml
 FROM pg_catalog.pg_roles r
 WHERE r.rolname IN ('anon','authenticated','service_role',
  'v3_cas_operator_login','v3_cas_executor',
  'v3_cas_audit_reader','v3_cas_audit_writer')
)
SELECT pg_catalog.jsonb_build_object(
 'kind','V3_CAS_STAGE0_PRIVATE_QUARANTINE_VERIFIED_CATALOG_V1',
 'observed_at_utc',pg_catalog.clock_timestamp(),
 'rls_forced',catalog.rls_forced,
 'zero_policies',catalog.zero_policies,
 'zero_epochs',catalog.zero_epochs,
 'zero_intents',catalog.zero_intents,
 'schema_owner',catalog.schema_owner,
 'cas_installed',catalog.cas_installed,
 'runtime_actor_privileges_absent',
  (SELECT count(*)=7 AND coalesce(bool_and(
    NOT schema_usage AND NOT epoch_dml AND NOT intent_dml),false) FROM actor),
 'cas_dispatch_authorized',false,
 'external_attempt_custody_independent',false,
 'old_writer_rearm_authorized',false,
 'v3_paper_release_authorized',false
) AS quarantine_status
FROM catalog;
