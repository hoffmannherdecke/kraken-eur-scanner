#!/usr/bin/env bash
# V3 PAPER / SOURCE-ONLY / DISPOSABLE POSTGRESQL CONTRACT TEST.
# This script NEVER connects to Supabase or an existing database.
# Networkless, disposable PostgreSQL 17 Docker container; no ports or secrets.
# No V3 CAS function is installed or invoked. Original SQL remains INACTIVE.
set -Eeuo pipefail
cd "$(git rev-parse --show-toplevel)"
source_sql="supabase/v3-cas-preinvoke-ledger-INACTIVE.sql"
container="v3-cas-pg-contract-$$"

cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo 'V3_PG17_TEST_ISOLATED_NETWORK_NONE'
docker run --detach --rm --name "$container" --network none \
  --memory 512m --tmpfs /var/lib/postgresql/data:rw,size=200m \
  -e POSTGRES_PASSWORD=disposable_offline_ci_only \
  postgres:17-alpine >/dev/null

ready=0
for i in $(seq 1 40); do
  if docker exec "$container" pg_isready -q -U postgres -d postgres >/dev/null 2>&1; then
    ready=1; break
  fi
  sleep 1
done
if [[ "$ready" -ne 1 ]]; then
  echo 'FAIL_PG17_EPHEMERAL_NOT_READY' >&2
  exit 1
fi
pg() {
  docker exec --interactive "$container" psql -X -v ON_ERROR_STOP=1 -U postgres -d postgres "$@"
}
pg -c "create role anon nologin; create role authenticated nologin; create role service_role nologin;" >/dev/null

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

# ONLY within the isolated networkless disposable container: remove exactly
# one known first-statement throw to check the UNREACHABLE candidate syntax.
# This transformed SQL is NEVER committed, emitted as a migration or run in
# production; original source file remains unchanged and hardlocked.
python - "$source_sql" <<'PY' | pg -f - >/dev/null
from pathlib import Path
import sys
sql = Path(sys.argv[1]).read_text(encoding="utf-8")
needle = "  raise exception 'V3_CAS_AUDIT_LEDGER_SOURCE_INACTIVE_APPROVAL_REQUIRED';"
assert sql.count(needle) == 1
assert sql.lower().count("do $v3_cas_ledger_inactive$") == 1
print(sql.replace(needle, "  -- ONLY_EPHEMERAL_PG17_TEST_REMOVED_FIRST_THROW", 1))
PY

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
  -- Intent table owner retains UPDATE/DELETE; this proves private RLS and
  -- ACLs alone are NOT a tamper-proof/WORM audit against privileged owners.
  IF NOT has_table_privilege('postgres','v3_cas_audit.intent_v1','UPDATE') THEN
    RAISE EXCEPTION 'FAIL_OWNER_PRIVILEGE_ASSUMPTION';
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
 WHERE rolname IN ('v3_cas_audit_writer','v3_cas_audit_reader','v3_cas_executor')
 AND NOT rolcanlogin AND NOT rolbypassrls;
 IF n <> 3 THEN RAISE EXCEPTION 'FAIL_THREE_RESTRICTED_NOLOGIN_ROLES'; END IF;
 SELECT count(*) INTO n FROM pg_policies
 WHERE schemaname='v3_cas_audit'
   AND policyname IN ('v3_cas_epoch_writer_read_v1',
                      'v3_cas_epoch_reader_v1',
                      'v3_cas_intent_reader_v1');
 IF n <> 3 THEN RAISE EXCEPTION 'FAIL_THREE_READ_ONLY_RLS_POLICIES'; END IF;
 IF NOT EXISTS (
   SELECT 1 FROM pg_proc p JOIN pg_namespace ns ON ns.oid=p.pronamespace
   WHERE ns.nspname='v3_cas_audit' AND p.proname='append_intent_v1'
     AND p.prosecdef
     AND array_to_string(p.proconfig,',') LIKE '%search_path=pg_catalog, v3_cas_audit%'
 ) THEN RAISE EXCEPTION 'FAIL_APPEND_DEFINER_FIXED_SEARCH_PATH'; END IF;
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
deny_sql reader_insert \
  "set role v3_cas_audit_reader; insert into v3_cas_audit.intent_v1 default values;"
deny_sql reader_epoch_update \
  "set role v3_cas_audit_reader; update v3_cas_audit.epoch_v1 set next_ordinal=500;"
deny_sql executor_view \
  "set role v3_cas_executor; select count(*) from v3_cas_audit.intent_v1;"
deny_sql generic_service_role \
  "set role service_role; select count(*) from v3_cas_audit.intent_v1;"
echo 'V3_PG17_SEPARATED_NOLOGIN_WRITER_READER_EXECUTOR_PASS'
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
echo 'V3_PG17_EPHEMERAL_ALL_PASS_NO_PRODUCTION'
