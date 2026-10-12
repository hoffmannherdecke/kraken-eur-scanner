#!/usr/bin/env python3
"""Structural security test for INACTIVE H10 source receipt SQL. No DB connection."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DDL=ROOT / "supabase/v3-h10-selected-original-source-receipts-inactive.sql"
BUILDER=ROOT / "tools/v3_h10_selected_original_receipt_v1.py"
CONTRACT=ROOT / "research/v3/h10-selected-original-receipt-contract-v1.json"

class H10SourceReceiptStorageDraftTests(unittest.TestCase):
    def test_new_source_specific_table_not_paper_journal(self):
        sql=DDL.read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE public.v3_h10_selected_source_receipts",sql)
        self.assertNotIn("CREATE TABLE IF NOT EXISTS public.v3_paper_event_receipts",sql)
        self.assertNotIn("INSERT INTO public.v3_paper_event_receipts",sql)
        self.assertIn("UNIQUE\n        (cohort_id, cohort_role, coin, window_start_utc)",sql)
        self.assertIn("original_payload_canonical text NOT NULL",sql)
        self.assertIn("received_at_utc timestamptz NOT NULL DEFAULT now()",sql)

    def test_immutable_and_no_public_rights(self):
        sql=DDL.read_text(encoding="utf-8")
        self.assertIn("ENABLE ROW LEVEL SECURITY",sql)
        self.assertIn("REVOKE ALL ON TABLE public.v3_h10_selected_source_receipts",sql)
        self.assertIn("FROM PUBLIC, anon, authenticated, service_role",sql)
        self.assertIn("GRANT SELECT ON TABLE public.v3_h10_selected_source_receipts TO service_role",sql)
        self.assertIn("GRANT INSERT (candidate_id, cohort_id",sql)
        self.assertIn("TO service_role;",sql)
        self.assertNotIn("GRANT UPDATE",sql)
        self.assertNotIn("GRANT DELETE",sql)
        self.assertIn("extensions.digest(convert_to(original_payload_canonical",sql)
        self.assertIn("octet_length(original_payload_canonical) <= 65536",sql)
        self.assertIn("interval '47 hours 55 minutes'",sql)
        self.assertIn("source_event_count",sql)
        self.assertIn("received_at_utc timestamptz NOT NULL DEFAULT now()",sql)
        self.assertNotIn("CREATE OR REPLACE FUNCTION",sql)
        self.assertNotIn("CREATE TABLE IF NOT EXISTS",sql)
        self.assertNotIn("CREATE EXTENSION",sql)
        self.assertIn("BEFORE UPDATE OR DELETE ON public.v3_h10_selected_source_receipts",sql)
        self.assertIn("RAISE EXCEPTION",sql)
        self.assertIn("SECURITY INVOKER SET search_path = ''",sql)
        self.assertIn("CONSTRAINT h10_selected_original_nontrade",sql)

    def test_no_hidden_deploy_or_keys(self):
        import json
        sql=DDL.read_text(encoding="utf-8")
        self.assertTrue(sql.lstrip().startswith("-- INACTIVE / REVIEW ONLY"))
        for forbidden in ("SUPABASE_SECRET_KEY=", "SUPABASE_SERVICE_ROLE_KEY=",
                          "ALTER TABLE public.v3_h10_fill_events",
                          "DROP TABLE", "DROP TRIGGER", "CREATE POLICY",
                          "COPY PROGRAM", "CREATE EXTENSION", "TRUNCATE TABLE"):
            self.assertNotIn(forbidden,sql)
        contract=json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertFalse(contract["future_storage"]["schema_applied"])
        self.assertFalse(contract["future_storage"]["write_connected"])
        self.assertFalse(contract["future_storage"]["exact_cloud_ack_evidenced"])
        self.assertTrue(contract["future_storage"]["revoke_anon_and_authenticated"])
        self.assertTrue(BUILDER.is_file())

if __name__=="__main__":
    unittest.main()
