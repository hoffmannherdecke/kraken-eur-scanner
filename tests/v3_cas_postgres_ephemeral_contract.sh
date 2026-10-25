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
echo 'V3_PG17_EPHEMERAL_ALL_PASS_NO_PRODUCTION'
