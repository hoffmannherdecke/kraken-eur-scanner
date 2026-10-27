#!/usr/bin/env bash
# V3 PAPER / SOURCE-ONLY / DISPOSABLE POSTGRESQL CONTRACT TEST.
# This script NEVER connects to Supabase or an existing database.
# Networkless, disposable PostgreSQL 17 Docker container; no ports or secrets.
# No V3 CAS function is installed or invoked. Original SQL remains INACTIVE.
set -Eeuo pipefail
cd "$(git rev-parse --show-toplevel)"
source_sql="supabase/v3-cas-preinvoke-ledger-INACTIVE.sql"
# Reviewed one-time Stage-2 source; the dormant original retains its first RAISE.
stage2_sql="supabase/v3-cas-audit-stage2-install-APPROVED-20261027.sql"
container="v3-cas-pg-contract-$$"

cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo 'V3_PG17_TEST_ISOLATED_NETWORK_NONE'
docker run --detach --rm --name "$container" --network none \
  --memory 512m --tmpfs /var/lib/postgresql/data:rw,size=200m \
  -e POSTGRES_USER=v3_ci_restore_root \
  -e POSTGRES_PASSWORD=disposable_offline_ci_only \
  postgres:17-alpine >/dev/null

ready=0
for i in $(seq 1 40); do
  if docker exec "$container" pg_isready -q -U v3_ci_restore_root -d v3_ci_restore_root >/dev/null 2>&1; then
    ready=1; break
  fi
  sleep 1
done
if [[ "$ready" -ne 1 ]]; then
  echo 'FAIL_PG17_EPHEMERAL_NOT_READY' >&2
  exit 1
fi
# Initialize the DISPOSABLE database with a distinct, private bootstrap
# SUPERUSER. Actual "postgres" is then CREATED from the beginning with the
# same restricted PG17 role class as original production Supabase.
docker exec "$container" psql -X -v ON_ERROR_STOP=1 -U v3_ci_restore_root -d v3_ci_restore_root \
  -c "CREATE ROLE postgres LOGIN NOSUPERUSER CREATEROLE CREATEDB BYPASSRLS;" >/dev/null
docker exec "$container" psql -X -v ON_ERROR_STOP=1 -U v3_ci_restore_root -d v3_ci_restore_root \
  -c "ALTER DATABASE postgres OWNER TO postgres;" >/dev/null
pg() {
  docker exec --interactive "$container" psql -X -v ON_ERROR_STOP=1 -U postgres -d postgres "$@"
}
pg_root() {
  docker exec --interactive "$container" psql -X -v ON_ERROR_STOP=1 -U v3_ci_restore_root -d v3_ci_restore_root "$@"
}
if [[ "$(pg -Atc "select (not rolsuper and rolcreaterole and rolbypassrls)::text from pg_roles where rolname='postgres'")" != "true" ]]; then
  echo 'FAIL_PG17_LIMITED_ORIGINAL_POSTGRES_INITIALIZED' >&2; exit 1
fi
pg -c "create role anon nologin; create role authenticated nologin; create role service_role nologin;" >/dev/null
# Actual PG17 nonsuperuser CREATEROLE creates one original ADMIN-only
# membership to postgres automatically (SET FALSE/INHERIT FALSE).
# Do NOT re-GRANT membership to one's own grantor: PG17 rightly rejects it.
pg -f - <<'SQL' >/dev/null
CREATE ROLE v3_cas_executor NOLOGIN NOINHERIT NOBYPASSRLS;
CREATE ROLE v3_cas_audit_writer NOLOGIN NOINHERIT NOBYPASSRLS;
CREATE ROLE v3_cas_audit_reader NOLOGIN NOINHERIT NOBYPASSRLS;
SQL


# PRE-COMMIT stage-0 quarantined production-schema SOURCE test. This runs
# entirely inside one disposable PG17 transaction and ROLLS BACK before
# touching the original inactive append-ledger source. No production roles,
# credentials, schema, or paper data are touched by this script.
stage0_sql="supabase/v3-cas-audit-stage0-private-quarantine-SOURCE-20261026.sql"
pg -f - <<'SQL' >/dev/null
CREATE ROLE v3_cas_operator_login LOGIN NOINHERIT NOBYPASSRLS;
CREATE TABLE public.paper_series(series_id text PRIMARY KEY,status text NOT NULL);
INSERT INTO public.paper_series VALUES
 ('PAPER-V2R4-20261009T110135Z','active');
SQL
{
  printf 'BEGIN;\n'
  cat "$stage0_sql"
  cat <<'SQL'
DO $v3_stage0_ci$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace
                WHERE nspname='v3_cas_audit')
    OR (SELECT count(*) FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='v3_cas_audit'
          AND c.relname IN ('epoch_v1','intent_v1')
          AND c.relrowsecurity AND c.relforcerowsecurity) <> 2
    OR EXISTS(SELECT 1 FROM pg_catalog.pg_policies
              WHERE schemaname='v3_cas_audit')
    OR EXISTS (
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
    RAISE EXCEPTION 'FAIL_STAGE0_QUARANTINE_ACTOR_PRIVILEGE_OR_RLS';
 END IF;
END
$v3_stage0_ci$;
ROLLBACK;
SQL
} | pg -f - >/dev/null
if [[ "$(pg -Atc "SELECT count(*) FROM pg_catalog.pg_namespace WHERE nspname='v3_cas_audit'")" != '0' ]]; then
 echo 'FAIL_STAGE0_ROLLBACK_CREATED_PERSISTENT_SCHEMA' >&2; exit 1
fi
echo 'V3_PG17_STAGE0_PRIVATE_SCHEMA_QUARANTINE_AND_ROLLBACK_PASS'

# Negative: wrong LOGIN permission on existing audit-writer role must reject
# the ENTIRE Stage0 transaction, not mutate existing private state.
pg_root -c "ALTER ROLE v3_cas_audit_writer LOGIN;" >/dev/null
stage0_drift="$(mktemp)"
if pg -f - < "$stage0_sql" >"$stage0_drift" 2>&1; then
 cat "$stage0_drift" >&2
 echo 'FAIL_STAGE0_ALLOWED_ROLE_SET_PRIVILEGE_DRIFT' >&2; exit 1
fi
if ! grep -q 'V3_STAGE0_ROLE_GRAPH_DRIFT_ABORT' "$stage0_drift" ; then
 cat "$stage0_drift" >&2
 echo 'FAIL_STAGE0_ROLE_DRIFT_WAS_NOT_REJECTED' >&2; exit 1
fi
rm -f "$stage0_drift"
pg_root -c "ALTER ROLE v3_cas_audit_writer NOLOGIN;" >/dev/null
if [[ "$(pg -Atc "SELECT count(*) FROM pg_catalog.pg_namespace WHERE nspname='v3_cas_audit'")" != '0' ]]; then
 echo 'FAIL_STAGE0_NEGATIVE_CREATED_SCHEMA' >&2; exit 1
fi
echo 'V3_PG17_STAGE0_ROLE_DRIFT_ABORT_PASS'


# Stage 1A: EXACT future production SQL, transactional in this *same*
# isolated PG17 container and always ROLLED BACK before legacy ledger tests.
# No password values, real production Cloud connection, logins, or CAS.
stage1_sql="supabase/v3-cas-actor-stage1-disabled-20261026.sql"
{
 printf 'BEGIN;\n'
 cat "$stage0_sql"
 cat "$stage1_sql"
 cat <<'SQL'
DO $v3_actor_stage1_test$
BEGIN
 IF (SELECT count(*) FROM pg_catalog.pg_roles
     WHERE rolname IN ('v3_cas_audit_writer_actor',
       'v3_cas_audit_reader_actor','v3_cas_executor_actor')
       AND NOT rolcanlogin AND NOT rolinherit AND NOT rolbypassrls
       AND NOT rolcreaterole AND NOT rolcreatedb AND NOT rolsuper
       AND NOT rolreplication AND rolconnlimit=0
       AND rolvaliduntil < pg_catalog.clock_timestamp()) <> 3 THEN
  RAISE EXCEPTION 'FAIL_STAGE1_DORMANT_ACTOR_ATTRIBUTES';
 END IF;
 IF EXISTS(
   SELECT 1 FROM pg_catalog.pg_auth_members m
   JOIN pg_catalog.pg_roles r ON r.oid=m.member
   WHERE r.rolname IN ('v3_cas_audit_writer_actor',
     'v3_cas_audit_reader_actor','v3_cas_executor_actor')
 ) OR EXISTS(
   SELECT 1 FROM pg_catalog.pg_roles r
   WHERE r.rolname IN ('v3_cas_audit_writer_actor',
      'v3_cas_audit_reader_actor','v3_cas_executor_actor')
     AND pg_catalog.has_schema_privilege(r.rolname,'v3_cas_audit','USAGE')
 ) THEN
  RAISE EXCEPTION 'FAIL_STAGE1_ACTOR_MEMBERSHIP_OR_USAGE';
 END IF;
END
$v3_actor_stage1_test$;
ROLLBACK;
SQL
} | pg -f - >/dev/null
if [[ "$(pg -Atc "select count(*) from pg_catalog.pg_roles where rolname in ('v3_cas_audit_writer_actor','v3_cas_audit_reader_actor','v3_cas_executor_actor')")" != '0' ||
      "$(pg -Atc "select count(*) from pg_catalog.pg_namespace where nspname='v3_cas_audit'")" != '0' ]]; then
 echo 'FAIL_STAGE1_DORMANT_ACTORS_OR_SCHEMA_SURVIVED_ROLLBACK' >&2; exit 1
fi
echo 'V3_PG17_STAGE1_DISABLED_ACTOR_SHELLS_ROLLBACK_PASS'

# Negative: cannot create any actor before Stage-0 exists.
stage1_negative="$(mktemp)"
if pg -f - < "$stage1_sql" >"$stage1_negative" 2>&1; then
 echo 'FAIL_STAGE1_WITHOUT_STAGE0_ACCEPTED' >&2; exit 1
fi
if ! grep -q 'V3_STAGE1_STAGE0_OR_CAS_GUARD_HOLD' "$stage1_negative"; then
 cat "$stage1_negative" >&2
 echo 'FAIL_STAGE1_EXPECTED_ABSENT_STAGE0_HOLD' >&2; exit 1
fi
rm -f "$stage1_negative"
if [[ "$(pg -Atc "select count(*) from pg_catalog.pg_roles where rolname in ('v3_cas_audit_writer_actor','v3_cas_audit_reader_actor','v3_cas_executor_actor')")" != '0' ]]; then
 echo 'FAIL_STAGE1_NEGATIVE_LEFT_ANY_ROLE' >&2; exit 1
fi
echo 'V3_PG17_STAGE1_ABSENT_STAGE0_FAILCLOSED_PASS'


# The original source MUST remain unusable as-is, with zero schema effects.
fail_log="$(mktemp)"
trap 'cleanup; rm -f "$fail_log"' EXIT
if pg -f - < "$source_sql" >"$fail_log" 2>&1; then
  echo 'FAIL_INACTIVE_SOURCE_EXECUTED' >&2; exit 1
fi
if ! grep -q 'V3_CAS_AUDIT_LEDGER_SOURCE_INACTIVE_APPROVAL_REQUIRED' "$fail_log"; then
  cat "$fail_log" >&2; echo 'FAIL_INACTIVE_LOCK_NOT_PROVEN' >&2; exit 1
fi
if [[ "$(pg -Atc "select count(*) from pg_namespace where nspname='v3_cas_audit'")" != '0' ]]; then
  echo 'FAIL_LOCKED_SOURCE_CREATED_SCHEMA' >&2; exit 1
fi
echo 'V3_PG17_INACTIVE_FIRST_STATEMENT_LOCK_PASS'

# The quarantined Stage-0 tables have already been created in production.
# Assert the future Stage-2 upgrade cannot proceed when Stage-0 is missing.
# This remains the same disposable, networkless PostgreSQL instance.
if pg -f - < "$stage2_sql" >/dev/null 2>&1; then
  echo 'FAIL_STAGE2_ACCEPTED_WITHOUT_STAGE0' >&2; exit 1
fi
if [[ "$(pg -Atc "select count(*) from pg_namespace where nspname='v3_cas_audit'")" != '0' ]]; then
  echo 'FAIL_STAGE2_WITHOUT_STAGE0_CREATED_SCHEMA' >&2; exit 1
fi
echo 'V3_PG17_STAGE2_REQUIRES_EXISTING_STAGE0_PASS'

# Apply ONLY the existing approved Stage-0 source to the disposable PG17
# AFTER testing its transactional rollback and negative cases above.
# Do not create new private tables in the Stage-2 candidate.
pg -f - < "$stage0_sql" >/dev/null
if [[ "$(pg -Atc "select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='v3_cas_audit' and c.relname in ('epoch_v1','intent_v1')")" != '2' ]]; then
  echo 'FAIL_DISPOSABLE_STAGE0_WAS_NOT_CREATED' >&2; exit 1
fi
existing_epoch_oid="$(pg -Atc "select 'v3_cas_audit.epoch_v1'::regclass::oid")"
existing_intent_oid="$(pg -Atc "select 'v3_cas_audit.intent_v1'::regclass::oid")"
echo 'V3_PG17_CURRENT_PRODUCTION_STAGE0_SHAPE_STAGED_PASS'

# Unlike Docker's default postgres SUPERUSER, the original production
# Supabase postgres is a PG17 NON-superuser with CREATEROLE and BYPASSRLS.
# Exercise the already prepared Stage-0 -> Stage-2 owner/grant transition
# under those real privilege characteristics, not under a CI superuser.
# The separate disposable bootstrap root role restores the fixture for the
# unrelated legacy negative ACL tests that follow. Zero Cloud access.
if [[ "$(docker exec "$container" psql -X -v ON_ERROR_STOP=1 -U v3_ci_restore_root -d v3_ci_restore_root -Atc 'select current_user')" != "v3_ci_restore_root" ]] ||
   [[ "$(pg -Atc "select (not rolsuper and rolcreaterole and rolbypassrls)::text from pg_roles where rolname='postgres'")" != "true" ]]; then
  echo 'FAIL_PG17_NON_SUPERUSER_CAS_OWNER_FIXTURE_NOT_EFFECTIVE' >&2; exit 1
fi
echo 'V3_PG17_REAL_SUPABASE_LIKE_NON_SUPERUSER_ROLE_SCOPE_PASS'

# Execute the EXACT separately reviewed Stage-2 install artifact under the
# production-like PG17 non-superuser; original dormant SQL stays hardlocked.
pg -f - < "$stage2_sql" >/dev/null

# The source has now run as effective NON-superuser postgres, with PG17
# CREATEROLE/BYPASSRLS, and must not leave direct SET/CREATE grants in that
# original administrator's production-like effective role scope.
if [[ "$(pg -Atc "select (not rolsuper and rolcreaterole and rolbypassrls)::text from pg_roles where rolname='postgres'")" != "true" ]] ||
   [[ "$(pg -Atc "select count(*) from pg_auth_members m join pg_roles r on r.oid=m.roleid join pg_roles g on g.oid=m.member where r.rolname in ('v3_cas_audit_table_owner','v3_cas_audit_append_definer') and (g.rolname <> 'postgres' or m.set_option or m.inherit_option or not m.admin_option)")" != "0" ]] ||
   [[ "$(pg -Atc "select count(*) from pg_roles where rolname in ('v3_cas_audit_table_owner','v3_cas_audit_append_definer') and has_schema_privilege(rolname,'v3_cas_audit','CREATE')")" != "0" ]]; then
  echo 'FAIL_PG17_ORIGINAL_NON_SUPERUSER_EFFECTIVE_SET_OR_CREATE_PRIVILEGE_LEAK' >&2; exit 1
fi
echo 'V3_PG17_ORIGINAL_NON_SUPERUSER_STAGE2_EFFECTIVE_OWNER_AND_REVOKE_PASS'
docker exec "$container" psql -X -v ON_ERROR_STOP=1 -U v3_ci_restore_root -d v3_ci_restore_root \
  -c "ALTER ROLE postgres SUPERUSER;" >/dev/null

# Upgrade MUST preserve existing Stage-0 table identity, not recreate or
# replace old audit data-plane tables.
if [[ "$(pg -Atc "select 'v3_cas_audit.epoch_v1'::regclass::oid")" != "$existing_epoch_oid" ||
      "$(pg -Atc "select 'v3_cas_audit.intent_v1'::regclass::oid")" != "$existing_intent_oid" ]]; then
  echo 'FAIL_STAGE2_REPLACED_STAGE0_TABLE_IDENTITY' >&2; exit 1
fi
echo 'V3_PG17_STAGE2_INPLACE_TABLE_OID_PRESERVED_PASS'

# Stage 3 SOURCE-ONLY: exercise exactly two separate already-named dormant
# shells and locally synthesized CI-fixture SCRAM verifiers in the SAME
# disposable PG17 database. No production password, role, network or CAS.
stage3_sql="supabase/v3-cas-audit-stage3-actors-enrollment-INACTIVE.sql"
if pg -f - < "$stage3_sql" >/dev/null 2>&1; then
 echo 'FAIL_STAGE3_INACTIVE_TEMPLATE_EXECUTABLE' >&2; exit 1
fi
# Real actor shells were originally created by a non-superuser
# CREATEROLE postgres; recreate THAT exact PG17 auto-admin membership.
pg_root -c "ALTER ROLE postgres NOSUPERUSER CREATEROLE CREATEDB BYPASSRLS;" >/dev/null
pg -f - <<'SQL' >/dev/null
CREATE ROLE v3_cas_audit_writer_actor NOSUPERUSER NOLOGIN NOINHERIT
 NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION
 CONNECTION LIMIT 0 PASSWORD NULL VALID UNTIL '2000-01-01';
CREATE ROLE v3_cas_audit_reader_actor NOSUPERUSER NOLOGIN NOINHERIT
 NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION
 CONNECTION LIMIT 0 PASSWORD NULL VALID UNTIL '2000-01-01';
CREATE ROLE v3_cas_executor_actor NOSUPERUSER NOLOGIN NOINHERIT
 NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION
 CONNECTION LIMIT 0 PASSWORD NULL VALID UNTIL '2000-01-01';
SQL
python - "$stage3_sql" <<'PY' | pg -f - >/dev/null
import base64, hashlib, hmac, pathlib, sys
s=pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
needle="  RAISE EXCEPTION 'V3_STAGE3_LOCAL_ENROLLMENT_TEMPLATE_INACTIVE';"
assert s.count(needle)==1
def scram(pwd, salt):
  salted=hashlib.pbkdf2_hmac("sha256",pwd.encode("ascii"),salt,4096)
  client=hmac.new(salted,b"Client Key","sha256").digest()
  stored=hashlib.sha256(client).digest()
  server=hmac.new(salted,b"Server Key","sha256").digest()
  return "SCRAM-SHA-256$4096:"+base64.b64encode(salt).decode()+"$"+base64.b64encode(stored).decode()+":"+base64.b64encode(server).decode()
s=s.replace(needle,"  -- disposable offline CI only; live source remains locked.",1)
s=s.replace("__WRITER_SCRAM_SHA256_VERIFIER__",scram("CI-WRITER-NO-PRODUCTION-SECRET",b"ci_writer_salt_1"))
s=s.replace("__READER_SCRAM_SHA256_VERIFIER__",scram("CI-READER-NO-PRODUCTION-SECRET",b"ci_reader_salt_1"))
assert "__" not in s
print(s)
PY
pg -f - <<'SQL' >/dev/null
DO $v3_stage3_ci$
BEGIN
 IF (SELECT count(*) FROM pg_roles WHERE rolname IN
     ('v3_cas_audit_writer_actor','v3_cas_audit_reader_actor')
     AND rolcanlogin AND NOT rolinherit AND NOT rolbypassrls AND rolconnlimit=1) <> 2
  OR (SELECT count(*) FROM pg_roles WHERE rolname='v3_cas_executor_actor'
     AND NOT rolcanlogin AND rolconnlimit=0) <> 1
  OR (SELECT count(*) FROM pg_auth_members m
      JOIN pg_roles a ON a.oid=m.member
      JOIN pg_roles g ON g.oid=m.roleid
      WHERE ((a.rolname='v3_cas_audit_writer_actor' AND g.rolname='v3_cas_audit_writer')
         OR (a.rolname='v3_cas_audit_reader_actor' AND g.rolname='v3_cas_audit_reader'))
       AND NOT m.admin_option AND NOT m.inherit_option AND m.set_option) <> 2
  OR NOT pg_has_role('v3_cas_audit_writer_actor','v3_cas_audit_writer','SET')
  OR NOT pg_has_role('v3_cas_audit_reader_actor','v3_cas_audit_reader','SET')
  OR pg_has_role('v3_cas_audit_reader_actor','v3_cas_audit_writer','SET')
  OR pg_has_role('v3_cas_audit_writer_actor','v3_cas_audit_reader','SET')
  THEN
   RAISE EXCEPTION 'FAIL_STAGE3_TWO_DISTINCT_AUTHENTICABLE_AUDIT_ACTORS';
 END IF;
END
$v3_stage3_ci$;
SQL
# postgres:17-alpine loopback defaults to TRUST; force the two NEW
# Stage3 actors onto narrow SCRAM-only rules before testing credentials.
# This file lives ONLY in the disposable --network none PG17 container.
docker exec -u postgres "$container" sh -ec '
 sed -i "1i host postgres v3_cas_audit_writer_actor 127.0.0.1/32 scram-sha-256" "$PGDATA/pg_hba.conf"
 sed -i "1i host postgres v3_cas_audit_reader_actor 127.0.0.1/32 scram-sha-256" "$PGDATA/pg_hba.conf"
'
# Reload requires cluster admin and is test-container-only.
pg_root -c 'SELECT pg_reload_conf();' >/dev/null
# These actual PG17 TCP/SCRAM logins are isolated CI-fixture credentials.
# They verify DIFFERENT session_user roles, distinct SET ROLE capabilities
# and a wrong-password rejection. Never use these source-fixed fixture secrets
# in the real Notebook/Supabase or claim this is production authentication.
for tuple in \
 'v3_cas_audit_writer_actor|v3_cas_audit_writer|CI-WRITER-NO-PRODUCTION-SECRET' \
 'v3_cas_audit_reader_actor|v3_cas_audit_reader|CI-READER-NO-PRODUCTION-SECRET'; do
 IFS='|' read -r actor group pwd <<< "$tuple"
 actual="$(docker exec -e PGPASSWORD="$pwd" "$container" \
   psql -X -qAt -v ON_ERROR_STOP=1 -h 127.0.0.1 -U "$actor" -d postgres \
     -c "SET ROLE $group; SELECT session_user || '|' || current_user;" 2>/dev/null)"
 if [[ "$actual" != "$actor|$group" ]]; then
  echo 'FAIL_STAGE3_DIFFERENT_ACTOR_SCRAM_TCP_SESSION' >&2; exit 1
 fi
done
if docker exec -e PGPASSWORD='CI-INTENTIONALLY-WRONG' "$container" \
    psql -X -qAt -h 127.0.0.1 -U v3_cas_audit_reader_actor -d postgres \
    -c 'select current_user;' >/dev/null 2>&1; then
  echo 'FAIL_STAGE3_INCORRECT_PASSWORD_AUTHENTICATED' >&2; exit 1
fi
echo 'V3_PG17_STAGE3_DISTINCT_REAL_CI_SCRAM_TCP_SESSIONS_PASS_CAS_OFF'
# Check the actual Notebook helper syntax using hosted PowerShell AST only.
# Parsing does not run its -Stage flag, read DPAPI or create local secrets.
if command -v pwsh >/dev/null 2>&1; then
 pwsh -NoProfile -NonInteractive -Command '
   $tokens=$null; $errors=$null
   [System.Management.Automation.Language.Parser]::ParseFile(
     "tools/v3-notebook-cas-stage3-two-actor-scram-INACTIVE.ps1",
     [ref]$tokens,[ref]$errors) | Out-Null
   if($errors.Count -ne 0){ throw "V3_STAGE3_PWSH_SOURCE_SYNTAX_HOLD" }
 ' >/dev/null
fi
echo 'V3_PG17_STAGE3_DISTINCT_WRITER_READER_ACTORS_SOURCE_TEST_PASS_CAS_OFF'
# Restore disposable-root semantics for legacy isolated tests only.
pg_root -c "ALTER ROLE postgres SUPERUSER;" >/dev/null
# Confirm audit data remained unchanged independently, using ONLY the
# disposable PG17 bootstrap root; restricted postgres is denied table SELECT.
if [[ "$(pg -Atc 'select count(*) from v3_cas_audit.epoch_v1')" != '0' ||
      "$(pg -Atc 'select count(*) from v3_cas_audit.intent_v1')" != '0' ]]; then
  echo 'FAIL_STAGE3_ENROLLMENT_WROTE_AUDIT_DATA' >&2; exit 1
fi

# PostgreSQL real catalog readback: both tables RLS+FORCE, no exposed schema,
# no generic EXECUTE/grants, and no CAS RPC. Validate effective role privileges.
pg -f - <<'SQL' >/dev/null
DO $$
DECLARE role_name text;
BEGIN
  IF (SELECT count(*) FROM pg_namespace WHERE nspname='v3_cas_audit') <> 1 THEN
    RAISE EXCEPTION 'FAIL_NO_PRIVATE_AUDIT_SCHEMA';
  END IF;
  IF (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname='v3_cas_audit' AND c.relname IN ('epoch_v1','intent_v1')
        AND c.relkind='r' AND c.relrowsecurity AND c.relforcerowsecurity) <> 2 THEN
    RAISE EXCEPTION 'FAIL_AUDIT_RLS_FORCE_NOT_APPLIED';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
             WHERE p.proname='rotate_v2r4_to_v3_experimental_paper') THEN
    RAISE EXCEPTION 'FAIL_V3_CAS_RPC_CREATED';
  END IF;
  FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
    IF has_schema_privilege(role_name,'v3_cas_audit','USAGE') OR
       has_table_privilege(role_name,'v3_cas_audit.epoch_v1','SELECT') OR
       has_table_privilege(role_name,'v3_cas_audit.intent_v1','SELECT') OR
       has_table_privilege(role_name,'v3_cas_audit.intent_v1','INSERT') OR
       has_table_privilege(role_name,'v3_cas_audit.intent_v1','UPDATE') OR
       has_table_privilege(role_name,'v3_cas_audit.intent_v1','DELETE') THEN
      RAISE EXCEPTION 'FAIL_INCORRECT_AUDIT_PRIVILEGE_%',role_name;
    END IF;
  END LOOP;
  -- Table owner and append definer must be different even in ephemeral PG.
  IF (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname='v3_cas_audit'
        AND c.relname IN ('epoch_v1','intent_v1')
        AND pg_get_userbyid(c.relowner)='v3_cas_audit_table_owner') <> 2 THEN
    RAISE EXCEPTION 'FAIL_SEPARATE_TABLE_OWNER';
  END IF;
END $$;
SQL
for role in anon authenticated service_role; do
  if pg -c "set role $role; select count(*) from v3_cas_audit.intent_v1;" >/dev/null 2>&1; then
    echo "FAIL_DIRECT_READ_ALLOWED_FOR_$role" >&2; exit 1
  fi
done
echo 'V3_PG17_PRIVATE_RLS_NO_GENERIC_ROLES_PASS'

pg -f - <<'SQL' >/dev/null
INSERT INTO v3_cas_audit.epoch_v1
 (epoch_id,predecessor_series_id,expected_rpc,source_sha256,
  original_fence_sha256,approved_caller_acl_sha256)
VALUES
 ('V3CAS-AUDIT-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  'PAPER-V2R4-20261009T110135Z',
  'public.rotate_v2r4_to_v3_experimental_paper',
  repeat('a',64), repeat('b',64), repeat('c',64));
BEGIN;
SELECT next_ordinal FROM v3_cas_audit.epoch_v1
 WHERE epoch_id='V3CAS-AUDIT-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' FOR UPDATE;
UPDATE v3_cas_audit.epoch_v1 SET next_ordinal=next_ordinal+1
 WHERE epoch_id='V3CAS-AUDIT-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
INSERT INTO v3_cas_audit.intent_v1
 (epoch_id,ordinal,intent_id,requested_rpc,predecessor_series_id,
  request_sha256,source_sha256,fence_sha256)
VALUES
 ('V3CAS-AUDIT-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',1,
  '11111111-1111-4111-8111-111111111111',
  'public.rotate_v2r4_to_v3_experimental_paper',
  'PAPER-V2R4-20261009T110135Z',repeat('d',64),
  repeat('a',64),repeat('b',64));
COMMIT;
SQL
# A DIFFERENT psql connection sees durable ACK after prior COMMIT.
if [[ "$(pg -Atc 'select count(*) from v3_cas_audit.intent_v1')" != '1' ]]; then
  echo 'FAIL_SEPARATE_CONNECTION_ACK_MISSING' >&2; exit 1
fi

# Later simulated failed CAS transaction MUST NOT erase the separately
# committed preinvoke intent. No actual experimental CAS RPC is invoked.
if pg -c "do \$\$ begin raise exception 'SIMULATED_CAS_ROLLBACK'; end \$\$;" >/dev/null 2>&1; then
  echo 'FAIL_EXPECTED_CAS_TRANSACTION_ERROR' >&2; exit 1
fi
if [[ "$(pg -Atc 'select count(*) from v3_cas_audit.intent_v1')" != '1' ]]; then
  echo 'FAIL_ROLLBACK_ERASED_PRECOMMIT_INTENT' >&2; exit 1
fi

# Same-transaction 'intent' is LOST on ROLLBACK: this tests the actual
# PostgreSQL behavior that makes per-RPC same-tx intent invalid.
pg -f - <<'SQL' >/dev/null
BEGIN;
SELECT next_ordinal FROM v3_cas_audit.epoch_v1
 WHERE epoch_id='V3CAS-AUDIT-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' FOR UPDATE;
UPDATE v3_cas_audit.epoch_v1 SET next_ordinal=next_ordinal+1
 WHERE epoch_id='V3CAS-AUDIT-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
INSERT INTO v3_cas_audit.intent_v1
 (epoch_id,ordinal,intent_id,requested_rpc,predecessor_series_id,
  request_sha256,source_sha256,fence_sha256)
VALUES
 ('V3CAS-AUDIT-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',2,
  '22222222-2222-4222-8222-222222222222',
  'public.rotate_v2r4_to_v3_experimental_paper',
  'PAPER-V2R4-20261009T110135Z',
  repeat('d',64),repeat('a',64),repeat('b',64));
ROLLBACK;
SQL
if [[ "$(pg -Atc 'select count(*) from v3_cas_audit.intent_v1')" != '1' ]] ||
   [[ "$(pg -Atc "select next_ordinal from v3_cas_audit.epoch_v1 where epoch_id='V3CAS-AUDIT-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'")" != '2' ]]; then
  echo 'FAIL_SAME_TRANSACTION_ROLLBACK_BEHAVIOUR' >&2; exit 1
fi
# No duplicate ordinal or UUID may be accepted in the source candidate.
if pg -c "insert into v3_cas_audit.intent_v1
   (epoch_id,ordinal,intent_id,requested_rpc,predecessor_series_id,
    request_sha256,source_sha256,fence_sha256)
   values('V3CAS-AUDIT-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',1,
   '33333333-3333-4333-8333-333333333333',
   'public.rotate_v2r4_to_v3_experimental_paper',
   'PAPER-V2R4-20261009T110135Z',
   repeat('d',64),repeat('a',64),repeat('b',64));" >/dev/null 2>&1; then
  echo 'FAIL_DUPLICATE_ORDINAL_ACCEPTED' >&2; exit 1
fi
if [[ "$(pg -Atc 'select count(*) from v3_cas_audit.intent_v1')" != '1' ]]; then
  echo 'FAIL_UNEXPECTED_INTENT_COUNT' >&2; exit 1
fi
echo 'V3_PG17_REAL_COMMIT_ROLLBACK_AND_DEDUP_PASS'
# Real PostgreSQL role/policy verification of the inert future source. Only
# synthetic NOLOGIN roles in this disposable DB, never original Supabase.
pg -f - <<'SQL' >/dev/null
DO $$
DECLARE n integer;
BEGIN
 SELECT count(*) INTO n FROM pg_roles
 WHERE rolname IN ('v3_cas_audit_writer','v3_cas_audit_reader','v3_cas_executor',
                   'v3_cas_audit_table_owner','v3_cas_audit_append_definer')
 AND NOT rolcanlogin AND NOT rolbypassrls AND NOT rolinherit;
 IF n <> 5 THEN RAISE EXCEPTION 'FAIL_FIVE_RESTRICTED_NOLOGIN_ROLES'; END IF;
 IF EXISTS (SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.roleid
   JOIN pg_roles g ON g.oid=m.member
   WHERE r.rolname IN ('v3_cas_audit_table_owner','v3_cas_audit_append_definer')
     AND (g.rolname <> 'postgres' OR m.set_option OR m.inherit_option
          OR NOT m.admin_option))
 THEN RAISE EXCEPTION 'FAIL_OWNER_ROLE_MEMBER_INHERITANCE'; END IF;
 IF (SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.roleid
   JOIN pg_roles a ON a.oid=m.member
   WHERE r.rolname IN ('v3_cas_executor','v3_cas_audit_writer','v3_cas_audit_reader')
     AND a.rolname='postgres'
     AND m.admin_option AND NOT m.set_option AND NOT m.inherit_option) <> 3 THEN
   RAISE EXCEPTION 'FAIL_PREPROVISIONED_CREATOR_ADMIN_REUSE';
 END IF;

 SELECT count(*) INTO n FROM pg_policies
 WHERE schemaname='v3_cas_audit'
   AND policyname IN ('v3_cas_epoch_writer_read_v1',
                      'v3_cas_epoch_reader_v1',
                      'v3_cas_intent_reader_v1',
                      'v3_cas_epoch_definer_read_v1',
                      'v3_cas_epoch_definer_update_v1',
                      'v3_cas_intent_definer_insert_v1');
 IF n <> 6 THEN RAISE EXCEPTION 'FAIL_SIX_MINIMAL_RLS_POLICIES'; END IF;
 IF NOT EXISTS (
   SELECT 1 FROM pg_proc p JOIN pg_namespace ns ON ns.oid=p.pronamespace
   WHERE ns.nspname='v3_cas_audit' AND p.proname='append_intent_v1'
     AND p.prosecdef
     AND array_to_string(p.proconfig,',') LIKE '%search_path=pg_catalog, v3_cas_audit%'
     AND pg_get_userbyid(p.proowner)='v3_cas_audit_append_definer'
 ) THEN RAISE EXCEPTION 'FAIL_APPEND_DEFINER_NONADMIN_OWNER_OR_FIXED_PATH'; END IF;
 IF NOT has_schema_privilege('v3_cas_audit_table_owner','v3_cas_audit','USAGE') OR
    has_schema_privilege('v3_cas_audit_table_owner','v3_cas_audit','CREATE') OR
    NOT has_schema_privilege('v3_cas_audit_append_definer','v3_cas_audit','USAGE') OR
    has_schema_privilege('v3_cas_audit_append_definer','v3_cas_audit','CREATE') OR
    NOT has_column_privilege('v3_cas_audit_append_definer',
         'v3_cas_audit.epoch_v1','sealed','SELECT') OR
    NOT has_column_privilege('v3_cas_audit_append_definer',
         'v3_cas_audit.epoch_v1','next_ordinal','UPDATE') OR
    NOT has_table_privilege('v3_cas_audit_append_definer',
         'v3_cas_audit.intent_v1','INSERT') OR
    has_table_privilege('v3_cas_audit_append_definer',
         'v3_cas_audit.intent_v1','SELECT') OR
    has_table_privilege('v3_cas_audit_append_definer',
         'v3_cas_audit.intent_v1','DELETE') OR
    has_table_privilege('v3_cas_audit_append_definer',
         'v3_cas_audit.intent_v1','UPDATE') THEN
   RAISE EXCEPTION 'FAIL_APPEND_DEFINER_LEAST_PRIVILEGE';
 END IF;
 IF NOT has_function_privilege('v3_cas_audit_writer',
       'v3_cas_audit.append_intent_v1(text,uuid,text,text,text)','EXECUTE') OR
    has_function_privilege('anon',
       'v3_cas_audit.append_intent_v1(text,uuid,text,text,text)','EXECUTE') OR
    has_function_privilege('authenticated',
       'v3_cas_audit.append_intent_v1(text,uuid,text,text,text)','EXECUTE') OR
    has_function_privilege('service_role',
       'v3_cas_audit.append_intent_v1(text,uuid,text,text,text)','EXECUTE') OR
    has_function_privilege('v3_cas_audit_reader',
       'v3_cas_audit.append_intent_v1(text,uuid,text,text,text)','EXECUTE') OR
    has_function_privilege('v3_cas_executor',
       'v3_cas_audit.append_intent_v1(text,uuid,text,text,text)','EXECUTE') THEN
   RAISE EXCEPTION 'FAIL_APPEND_EXECUTE_ROLE_SCOPE';
 END IF;
 IF NOT has_schema_privilege('v3_cas_audit_writer','v3_cas_audit','USAGE') OR
    NOT has_schema_privilege('v3_cas_audit_reader','v3_cas_audit','USAGE') OR
    has_schema_privilege('v3_cas_executor','v3_cas_audit','USAGE') OR
    has_table_privilege('v3_cas_audit_writer','v3_cas_audit.intent_v1','SELECT') OR
    has_table_privilege('v3_cas_audit_writer','v3_cas_audit.intent_v1','INSERT') OR
    has_table_privilege('v3_cas_audit_writer','v3_cas_audit.intent_v1','DELETE') OR
    NOT has_table_privilege('v3_cas_audit_reader','v3_cas_audit.intent_v1','SELECT') OR
    has_table_privilege('v3_cas_audit_reader','v3_cas_audit.intent_v1','INSERT') OR
    has_table_privilege('v3_cas_audit_reader','v3_cas_audit.epoch_v1','UPDATE') OR
    has_table_privilege('v3_cas_executor','v3_cas_audit.intent_v1','INSERT') OR
    has_column_privilege('v3_cas_audit_writer',
          'v3_cas_audit.epoch_v1','next_ordinal','UPDATE') OR
    has_column_privilege('v3_cas_audit_writer',
          'v3_cas_audit.epoch_v1','sealed','UPDATE') THEN
    RAISE EXCEPTION 'FAIL_OWNER_VS_WRITER_READER_EXECUTOR_GRANTS';
 END IF;
END $$;
SQL

# Create one test epoch *as the owner*; future Cloud epoch creation is still
# an independent security-reviewed provisioning step, never writer authority.
pg -f - <<'SQL' >/dev/null
INSERT INTO v3_cas_audit.epoch_v1
(epoch_id,predecessor_series_id,expected_rpc,source_sha256,
 original_fence_sha256,approved_caller_acl_sha256)
VALUES
('V3CAS-AUDIT-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
 'PAPER-V2R4-20261009T110135Z',
 'public.rotate_v2r4_to_v3_experimental_paper',
 repeat('a',64),repeat('b',64),repeat('c',64));
SQL
# Restricted writer can EXECUTE only the one append function. Caller may
# not choose ordinal or directly perform INSERT/UPDATE.
pg -f - <<'SQL' >/dev/null
SET ROLE v3_cas_audit_writer;
BEGIN;
SELECT v3_cas_audit.append_intent_v1(
 'V3CAS-AUDIT-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
 '44444444-4444-4444-8444-444444444444'::uuid,
 repeat('d',64),repeat('a',64),repeat('b',64));
COMMIT;
RESET ROLE;
SQL
count="$(pg -Atc "set role v3_cas_audit_reader; select count(*) from v3_cas_audit.intent_v1 where epoch_id='V3CAS-AUDIT-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';" | tail -n 1)"
if [[ "$count" != '1' ]]; then echo 'FAIL_INDEPENDENT_READER_CANNOT_ACK_WRITER_COMMIT' >&2; exit 1; fi

# Negative effective privilege tests: no writer SELECT/DELETE/other UPDATE,
# no reader append/UPDATE, no executor table or schema, no normal role access.
deny_sql() {
  local label="$1"; shift
  if pg -c "$*" >/dev/null 2>&1; then
    echo "FAIL_EXPECTED_ROLE_DENIAL_$label" >&2; exit 1
  fi
}
deny_sql writer_intent_select \
  "set role v3_cas_audit_writer; select count(*) from v3_cas_audit.intent_v1;"
deny_sql writer_intent_delete \
  "set role v3_cas_audit_writer; delete from v3_cas_audit.intent_v1;"
deny_sql writer_epoch_source_change \
  "set role v3_cas_audit_writer; update v3_cas_audit.epoch_v1 set source_sha256=repeat('e',64);"
deny_sql writer_direct_next_ordinal_jump \
  "set role v3_cas_audit_writer; update v3_cas_audit.epoch_v1 set next_ordinal=999;"
deny_sql writer_direct_intent_insert \
  "set role v3_cas_audit_writer; insert into v3_cas_audit.intent_v1 default values;"
deny_sql reader_append_function \
  "set role v3_cas_audit_reader; select v3_cas_audit.append_intent_v1('V3CAS-AUDIT-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb','55555555-5555-4555-8555-555555555555'::uuid,repeat('d',64),repeat('a',64),repeat('b',64));"
deny_sql generic_service_role_append_function \
  "set role service_role; select v3_cas_audit.append_intent_v1('V3CAS-AUDIT-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb','55555555-5555-4555-8555-555555555555'::uuid,repeat('d',64),repeat('a',64),repeat('b',64));"
deny_sql executor_append_function \
  "set role v3_cas_executor; select v3_cas_audit.append_intent_v1('V3CAS-AUDIT-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb','55555555-5555-4555-8555-555555555555'::uuid,repeat('d',64),repeat('a',64),repeat('b',64));"
deny_sql definer_intent_delete \
  "set role v3_cas_audit_append_definer; delete from v3_cas_audit.intent_v1;"
deny_sql definer_intent_select \
  "set role v3_cas_audit_append_definer; select count(*) from v3_cas_audit.intent_v1;"
deny_sql reader_insert \
  "set role v3_cas_audit_reader; insert into v3_cas_audit.intent_v1 default values;"
deny_sql reader_epoch_update \
  "set role v3_cas_audit_reader; update v3_cas_audit.epoch_v1 set next_ordinal=500;"
deny_sql executor_view \
  "set role v3_cas_executor; select count(*) from v3_cas_audit.intent_v1;"
deny_sql generic_service_role \
  "set role service_role; select count(*) from v3_cas_audit.intent_v1;"
# FORCE RLS must hide existing rows even from the non-login table owner
# when merely SET ROLE is used (an administrator could still ALTER ownership).
table_owner_count="$(pg -Atc 'set role v3_cas_audit_table_owner; select count(*) from v3_cas_audit.intent_v1;' | tail -n 1)"
if [[ "$table_owner_count" != '0' ]]; then
  echo 'FAIL_FORCE_RLS_ON_NONLOGIN_TABLE_OWNER' >&2; exit 1
fi
echo 'V3_PG17_SEPARATED_NOLOGIN_WRITER_READER_EXECUTOR_PASS'
echo 'V3_PG17_SEPARATED_TABLE_OWNER_APPEND_DEFINER_PASS'
# Real concurrent PostgreSQL sessions, same audit epoch, same restricted
# writer: row lock must serialize the ordinal assignment and intent insert.
pg -f - <<'SQL' >/dev/null
INSERT INTO v3_cas_audit.epoch_v1
(epoch_id,predecessor_series_id,expected_rpc,source_sha256,
 original_fence_sha256,approved_caller_acl_sha256)
VALUES
('V3CAS-AUDIT-cccccccccccccccccccccccccccccccc',
 'PAPER-V2R4-20261009T110135Z',
 'public.rotate_v2r4_to_v3_experimental_paper',
 repeat('a',64),repeat('b',64),repeat('c',64));
SQL
concurrent_log_dir="$(mktemp -d)"
# Clean both disposable host logs and Docker container on any failure.
trap 'cleanup; rm -f "$fail_log"; rm -rf "$concurrent_log_dir"' EXIT
pg -At -f - >"$concurrent_log_dir/a" 2>&1 <<'SQL' &
SET ROLE v3_cas_audit_writer;
BEGIN;
SELECT v3_cas_audit.append_intent_v1(
 'V3CAS-AUDIT-cccccccccccccccccccccccccccccccc',
 '66666666-6666-4666-8666-666666666666'::uuid,
 repeat('d',64),repeat('a',64),repeat('b',64));
SELECT pg_sleep(3);
COMMIT;
SQL
first_pid=$!
first_seen=0
for i in $(seq 1 40); do
  if grep -qx '1' "$concurrent_log_dir/a"; then
    first_seen=1; break
  fi
  sleep 0.1
done
if [[ "$first_seen" -ne 1 ]]; then
  echo 'FAIL_FIRST_APPEND_NOT_OBSERVED_BEFORE_CONCURRENCY' >&2
  cat "$concurrent_log_dir/a" >&2
  exit 1
fi
pg -At -f - >"$concurrent_log_dir/b" 2>&1 <<'SQL' &
SET ROLE v3_cas_audit_writer;
BEGIN;
SELECT v3_cas_audit.append_intent_v1(
 'V3CAS-AUDIT-cccccccccccccccccccccccccccccccc',
 '77777777-7777-4777-8777-777777777777'::uuid,
 repeat('d',64),repeat('a',64),repeat('b',64));
COMMIT;
SQL
second_pid=$!
sleep 0.35
if grep -qx '2' "$concurrent_log_dir/b"; then
  echo 'FAIL_CONCURRENT_APPEND_BYPASSED_ROW_LOCK' >&2; exit 1
fi
wait "$first_pid"
wait "$second_pid"
if ! grep -qx '1' "$concurrent_log_dir/a" ||
   ! grep -qx '2' "$concurrent_log_dir/b"; then
  echo 'FAIL_CONCURRENT_APPEND_NOT_SERIALIZED' >&2
  cat "$concurrent_log_dir/a" "$concurrent_log_dir/b" >&2; exit 1
fi
check="$(pg -Atc "select (select next_ordinal from v3_cas_audit.epoch_v1 where epoch_id='V3CAS-AUDIT-cccccccccccccccccccccccccccccccc')::text || ':' ||
 (select string_agg(ordinal::text,',' order by ordinal) from v3_cas_audit.intent_v1 where epoch_id='V3CAS-AUDIT-cccccccccccccccccccccccccccccccc')")"
if [[ "$check" != '3:1,2' ]]; then
  echo "FAIL_CONCURRENT_COUNTER_INTENT_INTEGRITY_$check" >&2; exit 1
fi

# Simulate failed append in the SAME PG transaction: no gap after rollback.
pg -f - <<'SQL' >/dev/null
SET ROLE v3_cas_audit_writer;
BEGIN;
SELECT v3_cas_audit.append_intent_v1(
 'V3CAS-AUDIT-cccccccccccccccccccccccccccccccc',
 '88888888-8888-4888-8888-888888888888'::uuid,
 repeat('d',64),repeat('a',64),repeat('b',64));
ROLLBACK;
SQL
check="$(pg -Atc "select (select next_ordinal from v3_cas_audit.epoch_v1 where epoch_id='V3CAS-AUDIT-cccccccccccccccccccccccccccccccc')::text || ':' ||
 (select string_agg(ordinal::text,',' order by ordinal) from v3_cas_audit.intent_v1 where epoch_id='V3CAS-AUDIT-cccccccccccccccccccccccccccccccc')")"
if [[ "$check" != '3:1,2' ]]; then
  echo "FAIL_ROLLBACK_CREATED_ORDINAL_GAP_$check" >&2; exit 1
fi

# Duplicate id fails atomically, must not consume next_ordinal 3.
deny_sql duplicate_uuid_no_gap \
  "set role v3_cas_audit_writer; select v3_cas_audit.append_intent_v1('V3CAS-AUDIT-cccccccccccccccccccccccccccccccc','66666666-6666-4666-8666-666666666666'::uuid,repeat('d',64),repeat('a',64),repeat('b',64));"
# Wrong bound source and bad request digest fail before writing.
deny_sql wrong_epoch_source \
  "set role v3_cas_audit_writer; select v3_cas_audit.append_intent_v1('V3CAS-AUDIT-cccccccccccccccccccccccccccccccc','99999999-9999-4999-8999-999999999999'::uuid,repeat('d',64),repeat('f',64),repeat('b',64));"
deny_sql invalid_request_digest \
  "set role v3_cas_audit_writer; select v3_cas_audit.append_intent_v1('V3CAS-AUDIT-cccccccccccccccccccccccccccccccc','99999999-9999-4999-8999-999999999999'::uuid,'bogus',repeat('a',64),repeat('b',64));"
check="$(pg -Atc "select (select next_ordinal from v3_cas_audit.epoch_v1 where epoch_id='V3CAS-AUDIT-cccccccccccccccccccccccccccccccc')::text || ':' ||
 (select string_agg(ordinal::text,',' order by ordinal) from v3_cas_audit.intent_v1 where epoch_id='V3CAS-AUDIT-cccccccccccccccccccccccccccccccc')")"
if [[ "$check" != '3:1,2' ]]; then
  echo "FAIL_REJECTED_ATTEMPT_CREATED_GAP_$check" >&2; exit 1
fi
echo 'V3_PG17_ATOMIC_PLUS_ONE_CONCURRENT_REPLAY_ROLLBACK_PASS'
# NEW: genuinely separate disposable PostgreSQL 17 SCRAM LOGIN sessions.
# Earlier SET ROLE probes used the SAME superuser session_user=postgres and
# could not attest real actor isolation. These two LOGIN accounts have fixed
# public CI-only credentials; they do not exist or run on Supabase/MINI-PC.
# No new workflow, real password, real Cloud role/member or CAS invocation.
pg -f - <<'SQL' >/dev/null
CREATE ROLE v3_ci_writer_login LOGIN NOINHERIT NOBYPASSRLS
  PASSWORD 'ci_only_writer_not_a_secret_20261026';
CREATE ROLE v3_ci_reader_login LOGIN NOINHERIT NOBYPASSRLS
  PASSWORD 'ci_only_reader_not_a_secret_20261026';
GRANT v3_cas_audit_writer TO v3_ci_writer_login
  WITH ADMIN FALSE, INHERIT FALSE, SET TRUE;
GRANT v3_cas_audit_reader TO v3_ci_reader_login
  WITH ADMIN FALSE, INHERIT FALSE, SET TRUE;
INSERT INTO v3_cas_audit.epoch_v1
(epoch_id,predecessor_series_id,expected_rpc,source_sha256,
 original_fence_sha256,approved_caller_acl_sha256)
VALUES ('V3CAS-AUDIT-dddddddddddddddddddddddddddddddd',
 'PAPER-V2R4-20261009T110135Z',
 'public.rotate_v2r4_to_v3_experimental_paper',
 repeat('a',64),repeat('b',64),repeat('c',64));
DO $v3_ci_scram$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_hba_file_rules
    WHERE type='host' AND auth_method='scram-sha-256'
      AND error IS NULL
  ) THEN
    RAISE EXCEPTION 'V3_CI_NOT_REAL_HOST_SCRAM';
  END IF;
END $v3_ci_scram$;
SQL

# The default postgres:17-alpine initdb may put 127.0.0.1/32 TRUST
# ahead of its catch-all host SCRAM line. A wrong-password negative case
# correctly revealed that this CI-only loopback path was not authenticated.
# Insert two narrow user/db/loopback SCRAM rules FIRST, preserving every
# other existing pg_hba entry, only inside disposable --network none Docker.
# Do not change any real Windows or Supabase pg_hba/configuration.
docker exec -u postgres "$container" sh -ec '
  sed -i "1i host postgres v3_ci_reader_login 127.0.0.1/32 scram-sha-256" "$PGDATA/pg_hba.conf"
  sed -i "1i host postgres v3_ci_writer_login 127.0.0.1/32 scram-sha-256" "$PGDATA/pg_hba.conf"
'
pg -c 'SELECT pg_reload_conf();' >/dev/null
# The negative password test below is the end-to-end proof that the *actual
# effective first matching rule* requires SCRAM, not merely that an HBA
# entry containing the string scram exists somewhere in the file.

# Host loopback is *inside* a --network none container. Unlike the socket
# trust route, -h 127.0.0.1 requires real SCRAM authentication. Keep fixtures
# out of application/GitHub secrets; NEVER reuse these sample passwords.
pg_writer_scram() {
  docker exec --interactive -e PGPASSWORD=ci_only_writer_not_a_secret_20261026 \
    "$container" psql -h 127.0.0.1 -X -v ON_ERROR_STOP=1 -At \
    -U v3_ci_writer_login -d postgres "$@"
}
pg_reader_scram() {
  docker exec --interactive -e PGPASSWORD=ci_only_reader_not_a_secret_20261026 \
    "$container" psql -h 127.0.0.1 -X -v ON_ERROR_STOP=1 -At \
    -U v3_ci_reader_login -d postgres "$@"
}
if docker exec -e PGPASSWORD=wrong_fixture_password "$container" \
  psql -h 127.0.0.1 -X -v ON_ERROR_STOP=1 -At \
  -U v3_ci_reader_login -d postgres -c 'select 1' >/dev/null 2>&1; then
  echo 'FAIL_CI_DISTINCT_READER_DID_NOT_REQUIRE_SCRAM' >&2; exit 1
fi
writer_identity="$(pg_writer_scram -c "SET ROLE v3_cas_audit_writer; SELECT session_user||':'||current_user;" | tail -n 1)"
reader_identity="$(pg_reader_scram -c "SET ROLE v3_cas_audit_reader; SELECT session_user||':'||current_user;" | tail -n 1)"
if [[ "$writer_identity" != 'v3_ci_writer_login:v3_cas_audit_writer' ||
      "$reader_identity" != 'v3_ci_reader_login:v3_cas_audit_reader' ]]; then
  echo 'FAIL_SCRAM_SEPARATE_SESSION_IDENTITIES' >&2; exit 1
fi
if pg_writer_scram -c "SET ROLE v3_cas_audit_writer; SELECT count(*) FROM v3_cas_audit.intent_v1;" >/dev/null 2>&1; then
  echo 'FAIL_SCRAM_WRITER_ALLOWED_READBACK' >&2; exit 1
fi
if pg_reader_scram -c "SET ROLE v3_cas_audit_reader; SELECT v3_cas_audit.append_intent_v1('V3CAS-AUDIT-dddddddddddddddddddddddddddddddd','99999999-9999-4999-8999-999999999999',repeat('d',64),repeat('a',64),repeat('b',64));" >/dev/null 2>&1; then
  echo 'FAIL_SCRAM_READER_ALLOWED_APPEND' >&2; exit 1
fi

# Writer's committed ACK cannot be created merely by returning ordinal=1.
# While writer transaction is still open, the independently authenticated
# reader in another backend must see zero, *despite* writer seeing its own row.
pg_writer_scram -f - >"$concurrent_log_dir/scram_writer" 2>&1 <<'SQL' &
SET ROLE v3_cas_audit_writer;
BEGIN;
SELECT v3_cas_audit.append_intent_v1(
  'V3CAS-AUDIT-dddddddddddddddddddddddddddddddd',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'::uuid,
  repeat('d',64),repeat('a',64),repeat('b',64));
SELECT pg_sleep(4);
COMMIT;
SQL
scram_writer_pid=$!
scram_first_seen=0
for i in $(seq 1 40); do
  if grep -qx '1' "$concurrent_log_dir/scram_writer"; then
    scram_first_seen=1; break
  fi
  sleep 0.05
done
if [[ "$scram_first_seen" -ne 1 ]]; then
  echo 'FAIL_SCRAM_FIRST_INTENT_NOT_OBSERVED_IN_WRITER' >&2
  cat "$concurrent_log_dir/scram_writer" >&2
  exit 1
fi
reader_precommit="$(pg_reader_scram -c "SET ROLE v3_cas_audit_reader; SELECT count(*) FROM v3_cas_audit.intent_v1 WHERE epoch_id='V3CAS-AUDIT-dddddddddddddddddddddddddddddddd';" | tail -n 1)"
if [[ "$reader_precommit" != '0' ]]; then
  echo 'FAIL_SCRAM_INDEPENDENT_READER_SAW_UNCOMMITTED_INTENT' >&2; exit 1
fi
wait "$scram_writer_pid"
reader_postcommit="$(pg_reader_scram -c "SET ROLE v3_cas_audit_reader; SELECT e.next_ordinal||':'||count(i.intent_id)||':'||min(i.ordinal)||':'||max(i.ordinal)||':'||min(i.request_sha256) FROM v3_cas_audit.epoch_v1 e JOIN v3_cas_audit.intent_v1 i ON i.epoch_id=e.epoch_id WHERE e.epoch_id='V3CAS-AUDIT-dddddddddddddddddddddddddddddddd' GROUP BY e.next_ordinal;" | tail -n 1)"
if [[ "$reader_postcommit" != "2:1:1:1:$(printf '%064d' 0 | tr '0' 'd')" ]]; then
  echo 'FAIL_SCRAM_INDEPENDENT_READER_AFTER_COMMIT_CONTENT_MISMATCH' >&2; exit 1
fi
# Different actual SQL backends and different LOGINs are observed; this is
# still test-only, NOT an approved/independently protected Cloud reader.
writer_pid="$(pg_writer_scram -c 'SELECT pg_backend_pid()' | tail -n 1)"
reader_pid="$(pg_reader_scram -c 'SELECT pg_backend_pid()' | tail -n 1)"
if [[ "$writer_pid" == "$reader_pid" || "$writer_identity" == "$reader_identity" ]]; then
  echo 'FAIL_SCRAM_READER_AND_WRITER_BACKEND_SEPARATION' >&2; exit 1
fi
# A rollback in another writer connection must not become an apparent ACK.
pg_writer_scram -f - >"$concurrent_log_dir/scram_rollback" 2>&1 <<'SQL'
SET ROLE v3_cas_audit_writer;
BEGIN;
SELECT v3_cas_audit.append_intent_v1(
  'V3CAS-AUDIT-dddddddddddddddddddddddddddddddd',
  'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'::uuid,
  repeat('d',64),repeat('a',64),repeat('b',64));
ROLLBACK;
SQL
rollback_readback="$(pg_reader_scram -c "SET ROLE v3_cas_audit_reader; SELECT e.next_ordinal||':'||count(i.intent_id) FROM v3_cas_audit.epoch_v1 e JOIN v3_cas_audit.intent_v1 i ON i.epoch_id=e.epoch_id WHERE e.epoch_id='V3CAS-AUDIT-dddddddddddddddddddddddddddddddd' GROUP BY e.next_ordinal;" | tail -n 1)"
if [[ "$rollback_readback" != '2:1' ]]; then
  echo 'FAIL_SCRAM_READER_FALSE_ROLLBACK_ACK' >&2; exit 1
fi
echo 'V3_PG17_DISTINCT_SCRAM_READER_PRECOMMIT_INVISIBLE_PASS'
echo 'V3_PG17_DISTINCT_SCRAM_READER_AFTER_COMMIT_PASS_NO_RELEASE'

echo 'V3_PG17_EPHEMERAL_ALL_PASS_NO_PRODUCTION'
