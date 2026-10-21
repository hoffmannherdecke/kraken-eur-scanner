"""Uninstalled V3 Cloud original checkpoint: static no-CAS privilege boundary."""
import re
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PRE=ROOT/"supabase/functions/v3-paper-technical-cutover-INACTIVE/index.ts"
RELAY=ROOT/"supabase/functions/v3-paper-evidence-relay/index.ts"
SQL=ROOT/"supabase/v3-experimental-paper-atomic-cas-INACTIVE-20261013.sql"
class SeparateV3CloudCASReadOnlyPreflight(unittest.TestCase):
 def test_separate_roles_and_relay_never_gain_cas(self):
  s=PRE.read_text("utf-8");r=RELAY.read_text("utf-8")
  for key in ("INACTIVE SOURCE ONLY","v3-paper-cutover-preflight-primary",
    "v3-paper-cutover-preflight-independent",
    "X-V3-Paper-Cutover-Preflight-Token",
    "X-V3-Paper-Independent-Preflight-Token",
    'first===second','"READONLY_APPROVED"'):
   self.assertIn(key,s)
  self.assertNotIn("v3-paper-cutover-preflight-primary",r)
  self.assertNotIn("v3-paper-cutover-preflight-independent",r)
 def test_mutation_paths_impossible_even_for_valid_preflight_auth(self):
  s=PRE.read_text("utf-8")
  for forbidden in (r"\.rpc\s*\(",r"\.(?:upsert|insert|update|delete)\s*\(",
                    r"(?im)^\s*(?:grant|create\s+role|alter\s+role)\b"):
   self.assertNotRegex(s,forbidden)
  self.assertIn('body.action!=="checkpoint"',s)
  self.assertIn('Object.keys(body).length!==2',s)
  for key in ("cas_execution_authorized:false","physical_originalhost_verified:false",
              "six_release_proofs_credited:0","safe_to_retry_unknown_cas:false"):
   self.assertIn(key,s)
  self.assertRegex(SQL.read_text("utf-8"),
    r"revoke all on function public\.rotate_v2r4_to_v3_experimental_paper")
 def test_dynamic_old_snapshot_and_atomic_cas_is_separate(self):
  s=PRE.read_text("utf-8")
  for needle in ('count:"exact",head:true',"nullsFirst:false",
      'version(db,"paper_candidate_outcomes",id)',
      'version(db,"paper_trade_results",id)',
      "data.length!==1","transaction lock"):
   self.assertIn(needle,s)
  self.assertNotIn("PAPER-V2R4-20261009T110135Z",s)
  self.assertNotIn("5807",s)
if __name__=="__main__": unittest.main()
