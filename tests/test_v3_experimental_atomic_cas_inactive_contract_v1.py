"""Offline review of the *inert* V2R4->V3 Paper cloud CAS DRAFT.

This is a textual policy check, not Postgres execution, authorization,
physical stop proof or a live SQL transaction test.
"""
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SQL_PATH=ROOT/"supabase/v3-experimental-paper-atomic-cas-INACTIVE-20261013.sql"
POSTGRES_SMOKE_PATH=ROOT/"tests/sql/v3_experimental_paper_atomic_cas_smoke.sql"


class InactiveV3AtomicCASContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql=SQL_PATH.read_text(encoding="utf-8")
        cls.body=cls.sql.split("as $v3_atomic_cas$",1)[-1].split(
            "$v3_atomic_cas$;",1)[0]

    def test_distinct_v3_function_is_inert_and_not_old_technical_rpc(self):
        self.assertIn("DO NOT deploy",self.sql)
        self.assertIn(
            "create or replace function public.rotate_v2r4_to_v3_experimental_paper(",
            self.sql)
        self.assertNotIn(
            "create or replace function public.rotate_v2r4_technical_paper(",
            self.sql)
        self.assertRegex(self.sql, r"security definer\s+set search_path = ''")
        grants=re.findall(r"(?im)^\s*grant\s+execute\s+on",self.sql)
        self.assertEqual(len(grants),1)
        self.assertIn("to v3_cas_executor;",self.sql)
        self.assertNotIn("to service_role;",self.sql)
        self.assertRegex(self.sql,
            r"revoke all on function public\.rotate_v2r4_to_v3_experimental_paper\(")
        self.assertRegex(self.sql,
            r"from public, anon, authenticated, service_role;")

    def test_original_sql_has_first_effectful_unconditional_cas_install_hold(self):
        # The source filename and comments cannot protect a production DB.
        # Its FIRST statement in the DO block must be a literal unconditional
        # exception; no role or function check may precede the hold.
        sql = self.sql
        marker = "raise exception 'V3_CAS_INSTALL_SOURCE_INACTIVE_APPROVAL_REQUIRED';"
        self.assertEqual(sql.count(marker), 1)
        self.assertRegex(
            sql,
            r"(?is)do \$v3_cas_install_locked\$\s*begin\s*"
            r"raise exception 'V3_CAS_INSTALL_SOURCE_INACTIVE_APPROVAL_REQUIRED';"
        )
        self.assertLess(sql.index(marker), sql.index("if pg_catalog.to_regprocedure("))
        self.assertLess(sql.index(marker), sql.index("execute $v3_cas_create_locked$"))

    def test_new_cas_function_never_exposes_default_public_execute_between_statements(self):
        # CREATE and REVOKE must run in one server transaction even when
        # psql/Supabase SQL editor use autocommit. A statement-by-statement
        # CREATE then REVOKE briefly exposes a SECURITY DEFINER endpoint.
        sql = self.sql
        beginning = "do $v3_cas_install_locked$"
        create_wrapper = "execute $v3_cas_create_locked$"
        revoke_wrapper = "execute $v3_cas_revoke_locked$"
        close = "$v3_cas_install_locked$;"
        self.assertEqual(sql.count(beginning), 1)
        self.assertEqual(sql.count(close), 1)
        self.assertEqual(sql.count(create_wrapper), 1)
        self.assertEqual(sql.count(revoke_wrapper), 1)
        self.assertTrue(sql.strip().endswith(close))
        self.assertEqual(sql.count("V3_CAS_INSTALL_EXISTING_SIGNATURE_HOLD"), 1)
        reg = "pg_catalog.to_regprocedure("
        signature = (
            "'public.rotate_v2r4_to_v3_experimental_paper("
            "text,text,text,text,bigint,bigint,timestamptz,timestamptz,"
            "text,text,text,timestamptz,jsonb,text,text,text)'"
        )
        self.assertIn(signature, sql)
        self.assertLess(sql.index(beginning), sql.index(reg))
        self.assertLess(sql.index(reg), sql.index(create_wrapper))
        self.assertLess(sql.index(create_wrapper), sql.index(
            "create or replace function public.rotate_v2r4_to_v3_experimental_paper("))
        self.assertLess(sql.index("$v3_cas_create_locked$;"),
                        sql.index(revoke_wrapper))
        self.assertLess(sql.index(revoke_wrapper),
                        sql.index("revoke all on function public.rotate_v2r4_to_v3_experimental_paper("))
        self.assertLess(sql.index("from public, anon, authenticated, service_role;"),
                        sql.index("$v3_cas_revoke_locked$;"))
        self.assertLess(sql.index("$v3_cas_revoke_locked$;"),
                        sql.rindex(close))
        # This GRANT exists only inside the same atomic DO as CREATE/REVOKE.
        # The prior 'no GRANT anywhere' assertion contradicted the contract.
        self.assertEqual(len(re.findall(r"(?im)^grant\s+execute\s+on", sql)), 1)

    def test_only_postgres_admin_only_membership_and_nologin_executor_can_receive_cas_execute(self):
        sql = self.sql
        for token in (
            "V3_CAS_EXECUTOR_OR_AUDIT_ROLE_SCOPE_UNSAFE",
            "m.admin_option and not m.set_option",
            "not m.inherit_option",
            "a.rolname='postgres'",
            "pg_catalog.pg_auth_members",
            "m.roleid=r.oid or m.member=r.oid",
            "not r.rolcanlogin",
            "not r.rolbypassrls",
            "not r.rolsuper",
            "not r.rolinherit",
            "not r.rolcreaterole",
            "not r.rolcreatedb",
            "V3_CAS_EFFECTIVE_EXECUTE_PRIVILEGE_NOT_EXCLUSIVE",
            "'anon'",
            "'authenticated'",
            "'service_role'",
            "'v3_cas_audit_writer'",
            "'v3_cas_audit_reader'",
            "'v3_cas_executor'",
            "to v3_cas_executor;",
        ):
            self.assertIn(token, sql, token)
        self.assertNotRegex(sql, r"(?im)^\s*create\s+role\b")
        self.assertNotRegex(sql, r"(?im)^\s*grant\s+v3_cas_executor\s+to\b")
        self.assertNotIn("LOGIN PASSWORD", sql)
        self.assertNotIn("TO postgres;", sql)
        self.assertLess(sql.index("V3_CAS_EXECUTOR_IS_NOT_EXCLUSIVE_NOLOGIN"),
                        sql.index("execute $v3_cas_create_locked$"))

    def test_only_existing_original_paper_tables_no_new_data_plane(self):
        self.assertNotRegex(self.body,
            r"(?im)^\s*(create\s+table|create\s+trigger|alter\s+table|"
            r"drop\s+table|truncate|delete\s+from)\b")
        self.assertNotRegex(self.body,r"(?im)^\s*update\s+public\.paper_(?:candidate_outcomes|trade_results)")
        self.assertNotRegex(self.body,r"(?im)^\s*insert\s+into\s+public\.paper_(?:candidate_outcomes|trade_results)")
        self.assertEqual(len(re.findall(
            r"(?im)^\s*update\s+public\.paper_series\b",self.body)),1)
        self.assertEqual(len(re.findall(
            r"(?im)^\s*insert\s+into\s+public\.paper_series\b",self.body)),1)
        self.assertNotIn("v2r4_technical_paper(",self.body)
        self.assertIn("paper_series_single_active_idx",self.body)
        self.assertIn("share row exclusive mode",self.body)

    def test_exact_single_active_index_catalog_contract_not_just_named_index(self):
        # Source-only negative-policy test, not a live SQL/index alteration.
        # A same-name nonunique/invalid/different-predicate index must fail.
        gate=self.body.split("if not exists (",1)[1].split(
            "raise exception 'V3 CAS missing exact valid unique single-active Paper index'",1)[0]
        self.assertIn("from pg_catalog.pg_index ix",gate)
        for predicate in (
            "ns.nspname='public'",
            "idx.relname='paper_series_single_active_idx'",
            "ix.indrelid=pg_catalog.to_regclass('public.paper_series')",
            "ix.indisunique is true",
            "ix.indisvalid is true",
            "ix.indisready is true",
            "ix.indislive is true",
            "ix.indnkeyatts=1",
            "ix.indnatts=1",
            "pg_catalog.pg_get_indexdef(ix.indexrelid,1,true)='status'",
            "pg_catalog.pg_get_expr(ix.indpred,ix.indrelid)",
            "'(status = ''active''::text)'",
        ):
            with self.subTest(predicate=predicate):
                self.assertIn(predicate,gate)
        self.assertIn("if not exists (",self.body)
        self.assertIn("V3 CAS missing exact valid unique single-active Paper index",self.body)
        self.assertNotRegex(gate,r"(?im)^\s*(create|alter|drop)\s+index")

    def test_private_committed_preinvoke_first_intent_is_server_side_gate(self):
        # The standalone caller's claimed CMS/reader booleans cannot release
        # the CAS; this does not prove the external identity or full request.
        body = self.body
        for predicate in (
            "pg_catalog.to_regclass('v3_cas_audit.epoch_v1')",
            "pg_catalog.to_regclass('v3_cas_audit.intent_v1')",
            "V3_CAS_PREINVOKE_AUDIT_SCHEMA_ABSENT_HOLD",
            "V3_CAS_PREINVOKE_REFERENCE_INVALID_HOLD",
            "V3_CAS_PREINVOKE_INTENT_NOT_PERSISTED_OR_BOUND",
            "e.sealed is true and e.next_ordinal=2 and i.ordinal=1",
            "i.intent_id=(p_new_v3_config->>'preinvoke_intent_id')::uuid",
            "i.request_sha256=p_new_v3_config->>'preinvoke_request_sha256'",
            "i.source_sha256=e.source_sha256",
            "i.fence_sha256=e.original_fence_sha256",
            "e.approved_caller_acl_sha256=p_new_v3_config->>'preinvoke_caller_acl_sha256'",
            "i.created_at_utc>pg_catalog.clock_timestamp()-interval '5 minutes'",
            "for update of e,i",
        ):
            with self.subTest(predicate=predicate):
                self.assertIn(predicate, body)
        self.assertLess(body.index("V3_CAS_PREINVOKE_AUDIT_SCHEMA_ABSENT_HOLD"),
                        body.index("V3_CAS_PREINVOKE_INTENT_NOT_PERSISTED_OR_BOUND"))
        self.assertLess(body.index("V3_CAS_PREINVOKE_INTENT_NOT_PERSISTED_OR_BOUND"),
                        body.index("update public.paper_series"))
        self.assertIn("The same PG17 canonical formula", body)
        self.assertNotIn("current_setting('v3.", body)
        self.assertNotIn("SET ROLE v3_cas_executor", body)
        self.assertNotIn("grant v3_cas_executor to v3_cas_operator_login", self.sql)

    def test_all_sixteen_actual_rpc_arguments_have_server_side_digest_binding(self):
        # This is a real PG17-source contract, not a claim that external
        # custody/reader-after-COMMIT or signer ACL is already established.
        body = self.body
        self.assertEqual(body.count("V3_CAS_FULL_REQUEST_PG17_JSONB_SHA256_V1"), 1)
        self.assertIn("v_actual_request_sha256 := pg_catalog.encode(", body)
        self.assertIn("pg_catalog.sha256(pg_catalog.convert_to(", body)
        self.assertIn("pg_catalog.jsonb_build_array(", body)
        self.assertIn("p_new_v3_config - 'preinvoke_request_sha256'", body)
        expr = body.split("v_actual_request_sha256 := ", 1)[1].split(";", 1)[0]
        names = [
            "p_expected_old_series_id", "p_expected_old_release_sha",
            "p_expected_old_strategy_sha256", "p_expected_old_runtime_sha256",
            "p_expected_old_candidate_count", "p_expected_old_trade_count",
            "p_expected_old_last_outcome_updated_at",
            "p_expected_old_last_trade_updated_at",
            "p_proposed_v3_series_id", "p_proposed_v3_test_id",
            "p_proposed_v3_revision", "p_cutover_at_utc", "p_new_v3_config",
            "p_reviewed_new_repo_sha", "p_reviewed_new_bundle_sha256",
            "p_reviewed_new_strategy_sha256",
        ]
        self.assertEqual(len(names), 16)
        import re
        for name in names:
            with self.subTest(argument=name):
                self.assertEqual(len(re.findall(r"\b" + name + r"\b", expr)), 1)
        self.assertEqual(expr.count('YYYY-MM-DD"T"HH24:MI:SS.US"Z"'), 3)
        self.assertIn("'UTF8'", expr)
        self.assertIn("V3_CAS_FULL_REQUEST_MISMATCH_HOLD", body)
        self.assertLess(body.index("i.request_sha256=p_new_v3_config"),
                        body.index("v_actual_request_sha256 :="))
        self.assertLess(body.index("V3_CAS_FULL_REQUEST_MISMATCH_HOLD"),
                        body.index("update public.paper_series"))
        self.assertNotIn("CREATE EXTENSION", self.sql.upper())
        self.assertNotIn("CREATE ROLE", self.sql.upper())

    def test_pg17_disposable_fixture_recomputes_both_standard_and_zero_trade_hash(self):
        fixture = POSTGRES_SMOKE_PATH.read_text(encoding="utf-8")
        for phrase in (
            "request_sha := pg_catalog.encode(pg_catalog.sha256(",
            "zero_trade_sha := pg_catalog.encode(pg_catalog.sha256(",
            "'V3_CAS_FULL_REQUEST_PG17_JSONB_SHA256_V1'",
            "pg_catalog.to_jsonb(request_sha)",
            "pg_catalog.to_jsonb(zero_trade_sha)",
            "request_sha256=zero_trade_sha",
            "zero-trade fixture audit row not restored",
            "tampered optional successor config bypassed full request SHA",
            "full request mismatch mutated Paper lifecycle",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, fixture)
        self.assertEqual(fixture.count(
            "'V3_CAS_FULL_REQUEST_PG17_JSONB_SHA256_V1'"), 2)
        self.assertIn("'V3_CAS_FULL_REQUEST_MISMATCH_HOLD'", self.body)

    def test_native_pg17_intent_negative_fixtures_and_transaction_rollback(self):
        fixture = POSTGRES_SMOKE_PATH.read_text(encoding="utf-8")
        for evidence in (
            "create schema v3_cas_audit",
            "create table v3_cas_audit.epoch_v1",
            "create table v3_cas_audit.intent_v1",
            "drop schema v3_cas_audit cascade",
            "missing private audit schema bypassed CAS",
            "missing epoch reference bypassed CAS",
            "wrong source accepted as committed intent",
            "replayed/foreign intent ID accepted",
            "unsealed epoch bypass or rollback restoration failure",
            "unbounded second ordinal accepted",
            "stale committed audit intent accepted",
            "audit negative case modified protected Paper state",
            "rollback;",
        ):
            with self.subTest(evidence=evidence):
                self.assertIn(evidence, fixture)

    def test_conditional_atomicity_is_bound_to_original_cloud_state(self):
        for required in (
            "pg_advisory_xact_lock",
            "for update",
            "old_row.status is distinct from 'active'",
            "p_expected_old_series_id",
            "p_expected_old_release_sha",
            "p_expected_old_strategy_sha256",
            "p_expected_old_runtime_sha256",
            "p_expected_old_candidate_count",
            "p_expected_old_trade_count",
            "p_expected_old_last_outcome_updated_at",
            "p_expected_old_last_trade_updated_at",
            "last_outcome is distinct from p_expected_old_last_outcome_updated_at",
            "last_trade is distinct from p_expected_old_last_trade_updated_at",
            "trade_count is distinct from p_expected_old_trade_count",
            "outcome_count is distinct from p_expected_old_candidate_count",
            "p_proposed_v3_series_id",
            "p_proposed_v3_revision",
            "p_reviewed_new_repo_sha",
            "p_reviewed_new_bundle_sha256",
            "p_reviewed_new_strategy_sha256",
            "p_cutover_at_utc",
            "pg_catalog.clock_timestamp()-interval '10 minutes'",
            "status='strategy_cutover_closed'",
            "status='active'",
        ):
            with self.subTest(required=required):
                self.assertIn(required,self.body)

    def test_old_trade_exit_version_must_be_in_same_atomic_cas(self):
        # Existing open Paper trades can close without increasing trade count.
        self.assertRegex(
            self.sql,
            r"p_expected_old_trade_count\s+bigint,\s*"
            r"p_expected_old_last_outcome_updated_at\s+timestamptz,\s*"
            r"p_expected_old_last_trade_updated_at\s+timestamptz")
        self.assertIn("last_trade timestamptz;",self.body)
        self.assertRegex(
            self.body,
            r"select\s+count\(\*\),max\(updated_at\)\s+"
            r"into\s+trade_count,last_trade\s+"
            r"from\s+public\.paper_trade_results")
        self.assertIn(
            "last_trade is distinct from p_expected_old_last_trade_updated_at",
            self.body)
        self.assertRegex(
            self.body,
            r"p_expected_old_trade_count > 0 and\s*"
            r"p_expected_old_last_trade_updated_at is null")
        self.assertRegex(
            self.sql,
            r"text,text,text,text,bigint,bigint,timestamptz,timestamptz,\s*"
            r"text,text,text,timestamptz,jsonb,text,text,text\)")
        self.assertLess(
            self.body.index("last_trade is distinct from"),
            self.body.index("update public.paper_series"))
        self.assertRegex(self.sql, r"(?im)^\s*grant\s+execute\s+on")
        self.assertIn("execute $v3_cas_executor_only$",self.sql)
        self.assertIn("$v3_cas_executor_only$;",self.sql)
        self.assertLess(self.sql.index("$v3_cas_revoke_locked$;"),
                        self.sql.index("execute $v3_cas_executor_only$"))
        self.assertLess(self.sql.index("$v3_cas_executor_only$;"),
                        self.sql.rindex("$v3_cas_install_locked$;"))

    def test_disposable_postgres_checks_same_count_trade_version_drift(self):
        fixture=POSTGRES_SMOKE_PATH.read_text(encoding="utf-8")
        self.assertIn("select count(*),max(updated_at) into n_trade,last_trade",fixture)
        self.assertIn("updated_at=last_trade+interval '5 seconds'",fixture)
        self.assertIn("stale same-count old trade update accepted",fixture)
        self.assertIn("last_out,last_trade,",fixture)
        self.assertNotIn("n_trade,last_out,\\n",fixture)
        self.assertIn("rollback;",fixture.lower())

    def test_never_accept_fake_auto_money_or_second_strategy(self):
        for key in (
            "'EXPERIMENTAL_PAPER_ONLY'",
            "'APPROVED_EXPERIMENTAL_PAPER'",
            "'real_money_actions_enabled' is distinct from 'false'",
            "'automatic_activation_allowed' is distinct from 'false'",
            "'paper_only' is distinct from 'true'",
            "'scout_notional_eur' is distinct from '50'",
            "'stage2_notional_eur' is distinct from '50'",
            "'target_completed_paper_trades' is distinct from '20'",
            "'old_followup_owner_preserved' is distinct from 'true'",
            "'physical_v2r4_writer_fence_verified' is distinct from 'true'",
            "'supervisor_old_intake_rearm_blocked' is distinct from 'true'",
            "'independent_six_e2e_proofs_verified' is distinct from 'true'",
        ):
            with self.subTest(key=key):
                self.assertIn(key,self.body)

    def test_release_must_still_prove_authentic_physical_cutover(self):
        self.assertIn("dual-token",self.sql)
        self.assertIn("physical",self.sql.lower())
        self.assertIn("status compatibility",self.sql)
        self.assertIn("NEVER claim this SQL alone",self.sql)
        self.assertIn("unknown commit result",self.sql.lower())
        self.assertIn("old-series paper_candidate_outcomes",self.sql)
        self.assertIn("old followup writer",self.sql)
        self.assertIn("No trigger/table/extra writer",self.sql)


if __name__=="__main__":
    unittest.main()
