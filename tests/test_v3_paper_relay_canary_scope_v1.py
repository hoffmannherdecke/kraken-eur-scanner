"""Source-derived V3 Cloud relay CANARY boundary; offline, no Cloud IO.

The existing live trial uses the strict PAPER-V3-CANARY-* namespace.
Only this namespace may omit the real-active-series lookup; a non-CANARY
Paper name must never obtain the trial exception by embedded keywords.
"""
from pathlib import Path
import re
import unittest

RELAY=(Path(__file__).resolve().parents[1] /
       "supabase/functions/v3-paper-evidence-relay/index.ts")


class V3PaperRelayCanaryScope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=RELAY.read_text(encoding="utf-8")
        match=re.search(
            r"const canarySeries=/([^/]+)/\.test\(sid\);",
            cls.source,
        )
        if match is None:
            raise AssertionError("canonical canary-series matcher absent")
        cls.canary=re.compile(match.group(1))

    def test_actual_isolated_canaries_still_match(self):
        for sid in (
            "PAPER-V3-CANARY-ONESHOT-20261016",
            "PAPER-V3-CANARY-WRITER-SMOKE-20261012",
        ):
            with self.subTest(sid=sid):
                self.assertIsNotNone(self.canary.fullmatch(sid))

    def test_noncanary_series_cannot_bypass_real_active_series_readback(self):
        for sid in (
            "PAPER-V3-LIVE-CANARY-BYPASS",
            "PAPER-V3-EXPERIMENTAL-CANARY-X",
            "PAPER-V3-PRODUCTION-20261017",
            "PAPER-V3-CANARY",
            "PAPER-V3-CANARY-",
            "X-PAPER-V3-CANARY-ONESHOT-20261016",
        ):
            with self.subTest(sid=sid):
                self.assertIsNone(self.canary.fullmatch(sid))
        self.assertIn("if(!canarySeries){",self.source)
        self.assertIn('.eq("series_id",sid).maybeSingle()',self.source)
        self.assertIn("real_v3_paper_series_not_active",self.source)
        self.assertNotIn('sid.includes("CANARY")',self.source)

    def test_read_only_active_series_branch_requires_relay_auth_and_never_mutates(self):
        s=self.source
        self.assertLess(s.index("if(!await authorized(db,req))"),
                        s.index('if(body?.action==="read_active_paper_series")'))
        self.assertIn('Object.keys(body).length!==2',s)
        self.assertIn('!/^PAPER-V3-[0-9]{8}T[0-9]{6}Z$/.test(sid)',s)
        self.assertIn('.select("status,strategy_revision,config")',s)
        self.assertIn('.eq("series_id",sid).maybeSingle()',s)
        self.assertIn('series?.status!=="active"',s)
        self.assertIn('new Date().toISOString()',s)
        self.assertIn('read_only:true,orders:false,real_money_actions:false',s)
        self.assertIn('cloud_cas_performed:false,physical_release_proofs_credited:0',s)
        first=s.index('if(body?.action==="read_active_paper_series")')
        second=s.index('if(body?.action!=="sync_paper_receipts")',first)
        read_branch=s[first:second]
        for forbidden in ('.insert(','.update(','.upsert(','.delete(',
                          '.rpc(', 'supabase/functions/v1', 'service_role_key'):
            self.assertNotIn(forbidden,read_branch)
        self.assertIn('if(body?.action!=="sync_paper_receipts")',s)

    def test_readback_returns_whitelisted_paper_release_pins_only(self):
        s=self.source
        first=s.index('const allowed=[')
        last=s.index('for(const field of allowed)',first)
        allowed=s[first:last]
        for key in ('series_id','strategy_revision','release_repo_sha',
                    'runtime_bundle_fingerprint_sha256',
                    'strategy_fingerprint_sha256','paper_only',
                    'real_money_actions_enabled',
                    'automatic_activation_allowed',
                    'physical_v2r4_writer_fence_verified',
                    'supervisor_old_intake_rearm_blocked',
                    'old_followup_owner_preserved',
                    'independent_six_e2e_proofs_verified'):
            self.assertIn('"'+key+'"',allowed)
        for forbidden in ('api_key','token_sha256','SUPABASE_SERVICE_ROLE_KEY',
                          'model_key','position_secret'):
            self.assertNotIn(forbidden,allowed)



if __name__=="__main__":
    unittest.main()
