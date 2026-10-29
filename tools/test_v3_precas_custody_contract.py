"""Fail-closed offline PRE-CAS custody contract tests. No cloud, Windows or CAS calls.

Run: python -m unittest tools/test_v3_precas_custody_contract.py
This is research-only; it never authorizes PR515 restore or native STOP.
"""
import unittest


def review_precas_evidence(e):
    """Candidate evidence policy, NOT a release authority."""
    required = (
        "signed_fence_valid", "fence_matches_originalhost",
        "exclusive_executor_inhibit_independently_signed",
        "executor_inhibit_continuous_since_before_stop",
        "executor_identity_unchanged", "durable_attempt_history_authenticated",
        "cloud_old_only_authenticated", "fresh_native_task_xml",
        "both_intake_tasks_disabled", "process_family_absent_independent",
        "supervisor_no_rearm_independent", "pr515_backup_valid",
        "protected_aftercare_running", "fresh_second_check",
    )
    if not all(e.get(k) is True for k in required):
        return "HOLD_MISSING_INDEPENDENT_PROOF"
    if e.get("phase") not in ("ARMED", "QUIESCED"):
        return "HOLD_WRONG_PHASE"
    if any(e.get(k) is not False for k in (
        "cas_dispatched", "persisted_intent", "unknown_latch",
        "cas_committed", "writer_started", "executor_inhibit_gap",
        "new_intent_after_readback", "fence_or_xml_drift",
    )):
        return "HOLD_CAS_OR_STATE_RISK"
    # A positive review remains non-authoritative until physically integrated
    # with an independently authenticated issuer and fresh originalhost readback.
    return "REVIEW_ONLY_PRECAS_CANDIDATE_NOT_RELEASED"


def complete_fixture():
    x = {k: True for k in (
        "signed_fence_valid", "fence_matches_originalhost",
        "exclusive_executor_inhibit_independently_signed",
        "executor_inhibit_continuous_since_before_stop",
        "executor_identity_unchanged", "durable_attempt_history_authenticated",
        "cloud_old_only_authenticated", "fresh_native_task_xml",
        "both_intake_tasks_disabled", "process_family_absent_independent",
        "supervisor_no_rearm_independent", "pr515_backup_valid",
        "protected_aftercare_running", "fresh_second_check",
    )}
    x.update({k: False for k in (
        "cas_dispatched", "persisted_intent", "unknown_latch",
        "cas_committed", "writer_started", "executor_inhibit_gap",
        "new_intent_after_readback", "fence_or_xml_drift",
    )})
    x["phase"] = "ARMED"
    return x


class PreCasCustodyContractTests(unittest.TestCase):
    def test_complete_synthetic_fixture_never_authorizes_release(self):
        self.assertEqual(review_precas_evidence(complete_fixture()),
                         "REVIEW_ONLY_PRECAS_CANDIDATE_NOT_RELEASED")

    def test_every_required_proof_missing_fails_closed(self):
        x = complete_fixture()
        for key in [k for k, v in x.items() if v is True]:
            with self.subTest(missing=key):
                y = dict(x)
                y.pop(key)
                self.assertTrue(review_precas_evidence(y).startswith("HOLD"))

    def test_every_negative_case_fails_closed(self):
        x = complete_fixture()
        for key in [k for k, v in x.items() if v is False]:
            with self.subTest(risk=key):
                y = dict(x)
                y[key] = True
                self.assertTrue(review_precas_evidence(y).startswith("HOLD"))

    def test_unknown_is_not_absence(self):
        x = complete_fixture()
        for key in ("cas_dispatched", "persisted_intent", "unknown_latch"):
            with self.subTest(unknown=key):
                y = dict(x)
                y[key] = None
                self.assertTrue(review_precas_evidence(y).startswith("HOLD"))

    def test_inhibit_now_does_not_prove_continuity(self):
        x = complete_fixture()
        x["executor_inhibit_continuous_since_before_stop"] = False
        self.assertTrue(review_precas_evidence(x).startswith("HOLD"))

    def test_untrusted_caller_claims_never_override_missing_custody(self):
        x = complete_fixture()
        x["durable_attempt_history_authenticated"] = False
        x["caller_claims_cas_never_invoked"] = True
        x["current_rpc_count"] = 0
        x["current_audit_epoch_count"] = 0
        self.assertTrue(review_precas_evidence(x).startswith("HOLD"))

    def test_wrong_phase_holds(self):
        for phase in ("CAS_INVOKED", "CLOUD_COMMITTED", "PRE_CUTOVER", None):
            with self.subTest(phase=phase):
                x = complete_fixture()
                x["phase"] = phase
                self.assertTrue(review_precas_evidence(x).startswith("HOLD"))


if __name__ == "__main__":
    unittest.main()
