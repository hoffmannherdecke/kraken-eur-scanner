"""Offline review of the *inert* V2R4->V3 Paper cloud CAS DRAFT.

This is a textual policy check, not Postgres execution, authorization,
physical stop proof or a live SQL transaction test.
"""
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SQL_PATH=ROOT/"supabase/v3-experimental-paper-atomic-cas-INACTIVE-20261013.sql"


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
        self.assertEqual(grants,[])
        self.assertRegex(self.sql,
            r"revoke all on function public\.rotate_v2r4_to_v3_experimental_paper\(")
        self.assertRegex(self.sql,
            r"from public, anon, authenticated, service_role;")

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
        self.assertNotRegex(gate,r"(?im)^\\s*(create|alter|drop)\\s+index")

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
            "last_outcome is distinct from p_expected_old_last_outcome_updated_at",
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
