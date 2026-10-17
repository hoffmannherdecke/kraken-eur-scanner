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


if __name__=="__main__":
    unittest.main()
