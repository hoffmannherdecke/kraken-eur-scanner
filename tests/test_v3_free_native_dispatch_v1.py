"""Existing original native P4 dispatcher defaults to free rules, never model.

No Cloud/CAS/Windows mutation; lower-level release identity is mocked here
only to prove branch selection and paid-input denial.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paper_evaluator import v3_paper_minipc_native_launcher_v1 as dispatcher
from tests.test_v3_paper_minipc_one_candidate_v1 import (
    SID,valid_approval,fixture,
)


def params(root):
    j=root/"journal"; c=root/"capture"; m=root/"budgets"; a=root/"ack.json"
    for p in (j,c,m):p.mkdir()
    return dict(phase="FIRST_SCANNER_MODEL_P4",
                series_id=SID,repo_sha="a"*40,
                bundle_sha256="b"*64,strategy_sha256="c"*64,
                journal=j,capture_dir=c,model_reservations=m,ack_file=a,
                read_active_series=lambda *_:{"status":"not-real"},
                candidate=fixture()[0],preflight={"kind":"test-only"})


class ZeroCostNativeDispatchTests(unittest.TestCase):
    def test_default_dispatches_free_rule_without_model_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=params(Path(tmp))
            with patch.object(dispatcher,"validate_one_owner_contract"), \
                 patch.object(dispatcher,"released_paper_first_scanner_rule_once",
                              return_value={"status":"FREE","model_http_calls":0}) as free, \
                 patch.object(dispatcher,"released_paper_first_scanner_model_once") as paid:
                result=dispatcher.dispatch_one_owned_paper_phase(**p)
            self.assertEqual(result["model_http_calls"],0)
            free.assert_called_once()
            paid.assert_not_called()
            self.assertNotIn("approval",free.call_args.kwargs)
            self.assertNotIn("model_key",free.call_args.kwargs)

    def test_key_only_or_approval_only_fails_before_source(self):
        for suffix in (dict(model_key="NO_REAL_KEY_FOR_TEST_123456789012"),
                       dict(approval=valid_approval()),
                       dict(model_client=lambda *_:None)):
            with self.subTest(which=tuple(suffix)):
                with tempfile.TemporaryDirectory() as tmp:
                    p=params(Path(tmp));p.update(suffix)
                    with patch.object(dispatcher,"validate_one_owner_contract"), \
                         patch.object(dispatcher,"released_paper_first_scanner_rule_once") as free, \
                         patch.object(dispatcher,"released_paper_first_scanner_model_once") as paid:
                        with self.assertRaisesRegex(ValueError,"partial paid-model"):
                            dispatcher.dispatch_one_owned_paper_phase(**p)
                    free.assert_not_called();paid.assert_not_called()

    def test_only_explicit_budget_can_dispatch_legacy_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=params(Path(tmp))
            p.update(approval=valid_approval(),
                     model_key="NO_REAL_KEY_FOR_TEST_123456789012")
            with patch.object(dispatcher,"validate_one_owner_contract"), \
                 patch.object(dispatcher,"released_paper_first_scanner_rule_once") as free, \
                 patch.object(dispatcher,"released_paper_first_scanner_model_once",
                              return_value={"status":"MODEL_TEST_NOT_HTTP"}) as paid:
                r=dispatcher.dispatch_one_owned_paper_phase(**p)
            self.assertEqual(r["status"],"MODEL_TEST_NOT_HTTP")
            free.assert_not_called();paid.assert_called_once()


if __name__=="__main__":
    unittest.main()
