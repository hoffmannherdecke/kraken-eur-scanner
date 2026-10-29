"""Fail-closed offline PRE-CAS custody contract tests. No cloud, Windows or CAS calls.

Run: python -m unittest tools/test_v3_precas_custody_contract.py
This is research-only; it never authorizes PR515 restore or native STOP.
"""
import unittest



def _continuous_same_fence(e):
    """Offline negative contract: these caller-provided fields are NOT authenticated."""
    first = e.get("before_mutation")
    second = e.get("immediately_before_mutation")
    if not isinstance(first, dict) or not isinstance(second, dict):
        return False
    keys = ("issuer", "executor", "fence_sha256", "backup_sha256", "series_id")
    for key in keys:
        if not isinstance(first.get(key), str) or not first[key] or first[key] != second.get(key):
            return False
    if any(len(first[key]) != 64 or any(c not in "0123456789abcdef" for c in first[key])
           for key in ("fence_sha256", "backup_sha256")):
        return False
    if first["series_id"] != "PAPER-V2R4-20261009T110135Z":
        return False
    from datetime import datetime
    def utc(value):
        if not isinstance(value, str) or not value.endswith("Z"):
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    start = utc(first.get("inhibit_started"))
    stopped = utc(first.get("native_stop"))
    one = utc(first.get("observed"))
    two = utc(second.get("observed"))
    through = utc(second.get("inhibit_through"))
    if any(t is None for t in (start, stopped, one, two, through)):
        return False
    if not (start < stopped <= one < two <= through):
        return False
    if (two - one).total_seconds() > 30:
        return False
    a, b = first.get("intent_high_watermark"), second.get("intent_high_watermark")
    return type(a) is int and type(b) is int and a == b and a >= 0



def review_variant2_notebook_boundary(action, evidence):
    """Variant 2 offline policy; source-only, never live release authority.

    Normal trading does not call the Notebook. Critical cutover/recovery must
    have an independently authenticated Notebook receipt plus the existing
    exclusive CAS inhibit and audit evidence. Caller claims are NOT signatures.
    """
    normal = {"NORMAL_MARKET_SCAN", "NORMAL_PAPER_DECISION", "NORMAL_PAPER_ORDER",
              "NORMAL_PAPER_STOP", "NORMAL_PAPER_AUDIT"}
    critical = {"NATIVE_STOP", "PR515_PRECOMMIT_RESTORE", "CAS_CUTOVER",
                "CRITICAL_RECOVERY", "LIVE_MONEY_ACTIVATION"}
    if action in normal:
        if evidence.get("current_epoch_authorized") is True and (
            evidence.get("unknown_latch") is False and
            evidence.get("runtime_guard_healthy") is True
        ):
            return "REVIEW_ONLY_NOTEBOOK_NOT_REQUIRED_FOR_NORMAL_OPERATION"
        return "HOLD_NORMAL_OPERATION_GUARDS"
    if action not in critical:
        return "HOLD_UNKNOWN_OPERATION"
    required = (
        "notebook_independent_receipt_authenticated",
        "critical_scope_signed_and_fence_bound",
        "exclusive_executor_inhibit_continuous",
        "complete_attempt_unknown_history_authenticated",
        "originalhost_guard_verified",
        "fresh_pre_mutation_recheck",
    )
    if not all(evidence.get(key) is True for key in required):
        return "HOLD_CRITICAL_INDEPENDENT_PROOF_MISSING"
    if evidence.get("unknown_latch") is not False:
        return "HOLD_CRITICAL_UNKNOWN"
    return "REVIEW_ONLY_CRITICAL_CANDIDATE_NOT_RELEASED"


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
    if not _continuous_same_fence(e):
        return "HOLD_CUSTODY_INTERVAL_OR_FENCE_MISMATCH"
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

    same = dict(issuer="external-issuer", executor="exclusive-executor",
                fence_sha256="a" * 64, backup_sha256="b" * 64,
                series_id="PAPER-V2R4-20261009T110135Z", intent_high_watermark=0)
    x["before_mutation"] = dict(same, inhibit_started="2026-10-29T12:00:00Z",
                                native_stop="2026-10-29T12:00:01Z", observed="2026-10-29T12:00:02Z")
    x["immediately_before_mutation"] = dict(same, observed="2026-10-29T12:00:03Z",
                                            inhibit_through="2026-10-29T12:00:04Z")
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


    def test_missing_or_mismatched_second_receipt_holds(self):
        for missing in ("before_mutation", "immediately_before_mutation"):
            x = complete_fixture()
            del x[missing]
            self.assertTrue(review_precas_evidence(x).startswith("HOLD"))
        for field in ("issuer", "executor", "fence_sha256", "backup_sha256", "series_id"):
            x = complete_fixture()
            x["immediately_before_mutation"][field] = "other"
            self.assertTrue(review_precas_evidence(x).startswith("HOLD"))

    def test_gap_replay_or_new_intent_holds(self):
        for lane, field, value in (
            ("before_mutation", "inhibit_started", "2026-10-29T12:00:02Z"),
            ("immediately_before_mutation", "observed", "2026-10-29T12:01:00Z"),
            ("immediately_before_mutation", "observed", "2026-10-29T11:59:59Z"),
            ("immediately_before_mutation", "inhibit_through", "2026-10-29T12:00:02Z"),
            ("immediately_before_mutation", "intent_high_watermark", 1),
            ("immediately_before_mutation", "intent_high_watermark", -1),
            ("immediately_before_mutation", "observed", "UNKNOWN"),
        ):
            with self.subTest(field=field, value=value):
                x = complete_fixture()
                x[lane][field] = value
                self.assertTrue(review_precas_evidence(x).startswith("HOLD"))


    def test_variant2_normal_paper_does_not_require_online_notebook(self):
        for action in ("NORMAL_MARKET_SCAN", "NORMAL_PAPER_DECISION",
                       "NORMAL_PAPER_ORDER", "NORMAL_PAPER_STOP", "NORMAL_PAPER_AUDIT"):
            with self.subTest(action=action):
                e = {"current_epoch_authorized": True,
                     "unknown_latch": False, "runtime_guard_healthy": True,
                     "notebook_online": False}
                self.assertEqual(review_variant2_notebook_boundary(action, e),
                                 "REVIEW_ONLY_NOTEBOOK_NOT_REQUIRED_FOR_NORMAL_OPERATION")

    def test_variant2_critical_actions_require_independent_receipt(self):
        for action in ("NATIVE_STOP", "PR515_PRECOMMIT_RESTORE", "CAS_CUTOVER",
                       "CRITICAL_RECOVERY", "LIVE_MONEY_ACTIVATION"):
            e = {"current_epoch_authorized": True, "unknown_latch": False}
            with self.subTest(action=action):
                self.assertTrue(review_variant2_notebook_boundary(action, e).startswith("HOLD"))
                e.update({key: True for key in (
                    "notebook_independent_receipt_authenticated",
                    "critical_scope_signed_and_fence_bound",
                    "exclusive_executor_inhibit_continuous",
                    "complete_attempt_unknown_history_authenticated",
                    "originalhost_guard_verified", "fresh_pre_mutation_recheck",
                )})
                self.assertEqual(review_variant2_notebook_boundary(action, e),
                                 "REVIEW_ONLY_CRITICAL_CANDIDATE_NOT_RELEASED")

    def test_variant2_fails_closed_for_unknown_or_unguarded_normal_operation(self):
        self.assertEqual(review_variant2_notebook_boundary("UNRECOGNIZED", {}),
                         "HOLD_UNKNOWN_OPERATION")
        for evidence in ({"current_epoch_authorized": True,
                          "unknown_latch": True, "runtime_guard_healthy": True},
                         {"current_epoch_authorized": True,
                          "unknown_latch": False, "runtime_guard_healthy": False}):
            self.assertTrue(review_variant2_notebook_boundary(
                "NORMAL_PAPER_ORDER", evidence).startswith("HOLD"))

    def test_wrong_phase_holds(self):
        for phase in ("CAS_INVOKED", "CLOUD_COMMITTED", "PRE_CUTOVER", None):
            with self.subTest(phase=phase):
                x = complete_fixture()
                x["phase"] = phase
                self.assertTrue(review_precas_evidence(x).startswith("HOLD"))


if __name__ == "__main__":
    unittest.main()
