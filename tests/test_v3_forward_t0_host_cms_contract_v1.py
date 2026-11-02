"""Fail-closed source contract for existing PR515 signed current T0 reader."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
OP = ROOT / "tools/minipc-v3-paper-cutover-operator-INACTIVE.ps1"
SQL = ROOT / "supabase/v3-cas-t0-private-reader-witness-INACTIVE.sql"

class ForwardT0CmsContract(unittest.TestCase):
    def test_exact_existing_host_function_and_single_dispatch(self):
        src = OP.read_text(encoding="utf-8")
        self.assertEqual(src.count("function Test-V3ForwardT0SignedCurrentCatalog("), 1)
        self.assertEqual(src.count("function Test-V3SignedNotebookPrecommitInventory("), 1)
        self.assertIn("if($crypto.crypto_signature_valid -ne $true){return [pscustomobject]$out}", src)
        start = src.index("function Test-V3SignedNotebookPrecommitInventory(")
        end = src.index("# A real Windows XML recovery artifact", start)
        caller = src[start:end]
        self.assertLess(caller.index("if($crypto.crypto_signature_valid"), caller.index("Test-V3ForwardT0SignedCurrentCatalog -RawJson"))
        self.assertIn("V3_CAS_FORWARD_T0_CURRENT_CATALOG_READONLY_V1", caller)
        self.assertIn("V3_CAS_READER_CURRENT_PRIVATE_AUDIT_SNAPSHOT_V1", caller)

    def test_cloud_fields_are_exactly_consumed_and_types_are_not_coerced(self):
        source = OP.read_text(encoding="utf-8")
        sql = SQL.read_text(encoding="utf-8")
        block = source.split("function Test-V3ForwardT0SignedCurrentCatalog(",1)[1].split(
            "# Only validates authentic CURRENT Notebook Reader data",1)[0]
        fields = (
            "kind observed_at_utc actor requested_role active_series_count "
            "original_active_series_count epoch_count intent_count attempt_count "
            "dispatch_unknown_count inhibit_count cas_rpc_count executor_can_login "
            "history_never_proven complete_attempt_unknown_custody_authenticated "
            "t0_authenticated armed_marker_cancel_authorized "
            "native_stop_restore_authorized cas_or_v3_paper_authorized"
        ).split()
        for field in fields:
            self.assertIn("'"+field+"'", block)
            self.assertIn("'"+field+"'", sql)
        for marker in (
            "V3_FORWARD_T0_SCHEMA_DRIFT",
            "V3_FORWARD_T0_DUPLICATE_FIELD",
            "V3_FORWARD_T0_UTC_FORMAT",
            "V3_FORWARD_T0_STALE_OR_ACTOR_DRIFT",
            "V3_FORWARD_T0_NONZERO_OR_WRONG_TYPE",
            "V3_FORWARD_T0_UNSAFE_AUTHORITY_FLAG",
            r"\\s*:\\s*0(?=\\s*[,}])",
            r"\\s*:\\s*false(?=\\s*[,}])",
        ):
            self.assertIn(marker, block)
        self.assertIn("$age -gt 120", block)

    def test_all_release_and_history_authorities_stay_negative(self):
        src = OP.read_text(encoding="utf-8")
        block = src.split("function Test-V3ForwardT0SignedCurrentCatalog(",1)[1].split(
            "# Only validates authentic CURRENT Notebook Reader data",1)[0]
        for flag in (
            "independent_notebook_key_custody_verified_here",
            "independent_cas_attempt_history_complete",
            "historical_cas_never_verified",
            "originalhost_t0_time_and_fence_bound",
            "native_stop_or_restore_authorized",
            "armed_marker_cancel_authorized",
            "cloud_cas_dispatch_authorized",
            "v3_paper_release_authorized",
        ):
            self.assertIn(flag+"=$false", block)
            self.assertNotIn(flag+"=$true", block)
        self.assertIn("SIGNED_CURRENT_FORWARD_T0_CATALOG_NOT_RELEASE",block)
        self.assertNotRegex(block, r"(?m)^\\s*(?:Stop|Start|Enable|Disable|Register)-ScheduledTask\\b")
        self.assertNotRegex(block, r"(?m)^\\s*(?:Remove-Item|Invoke-RestMethod|Invoke-Command)\\b")

if __name__ == "__main__":
    unittest.main()
