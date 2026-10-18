"""CI contract: eight user-approved offensive V3 Paper policy items cannot disappear
or silently turn into PASS merely through prose or PR/CI status.

Not a seventh release gate and NOT physical Paper E2E certification.
"""
import json
import unittest
from pathlib import Path

BUNDLE = Path("research/v3/v3-experimental-paper-all-lessons-bundle-20261011.json")
IDS = (
    "EARLY_INITIAL_REVIEW",
    "POSITIVE_CATALYST_BUY",
    "WAIT_REJECT_FRESH_RECHECK",
    "CONTINUITY_FAST",
    "VOLUME_SOFT_CONTEXT",
    "EXTENDED_NEW_BASE",
    "RISK_REGIME_OPTIONAL_SOURCES",
    "MODEL_BUY_CONVERSION",
)


def validate_policy(bundle):
    errors = []
    policy = bundle.get("offensive_paper_policy_concrete_20261018")
    if not isinstance(policy, dict):
        return ["eight-point offensive V3 policy missing"]
    changes = policy.get("changes")
    tracking = policy.get("acceptance_tracking")
    if not isinstance(changes, list) or not isinstance(tracking, dict):
        return ["offensive changes or acceptance tracking missing"]
    items = tracking.get("items")
    if not isinstance(items, list):
        return ["eight-point acceptance rows missing"]
    for label, rows in (("changes", changes), ("tracking", items)):
        ids = [x.get("id") for x in rows if isinstance(x, dict)]
        if len(rows) != len(IDS) or sorted(ids) != sorted(IDS):
            errors.append(label + " must contain eight unique original policy IDs")
    for row in changes:
        if not isinstance(row, dict):
            errors.append("invalid offensive change")
            continue
        for field in ("point", "action", "test"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                errors.append(str(row.get("id")) + " missing " + field)
    for row in items:
        if not isinstance(row, dict):
            errors.append("invalid acceptance row")
            continue
        ident = str(row.get("id"))
        if row.get("positive_and_negative_tests_required") is not True:
            errors.append(ident + " must require positive and negative tests")
        if row.get("physical_proof_required_when_writer_path") is not True:
            errors.append(ident + " must require physical writer-path evidence")
        if not isinstance(row.get("implementation_owner"), str) or not row["implementation_owner"].strip():
            errors.append(ident + " missing existing implementation owner")
        receipts = row.get("original_receipt_ids")
        if not isinstance(receipts, list) or any(
            not isinstance(x, str) or not x.strip() for x in receipts
        ) or len(receipts) != len(set(receipts)):
            errors.append(ident + " invalid original receipt IDs")
        if row.get("status") == "OPEN_NOT_E2E_VERIFIED":
            if row.get("acceptance") != "NOT_ACCEPTED" or receipts:
                errors.append(ident + " open status cannot carry acceptance or claimed proof")
        elif row.get("status") == "VERIFIED_E2E":
            # A string/CI label alone must never self-certify original physical evidence.
            # Release owner must separately authenticate the physical host + Cloud
            # originals in the existing six-proof technical release gate.
            errors.append(ident + " cannot self-approve from strategy JSON/CI")
        else:
            errors.append(ident + " unexpected acceptance state")
    if tracking.get("physical_gate") != "V3_REAL_MODEL_COIN_PIT_P4_INPUT_E2E":
        errors.append("eight items must share the original first technical gate")
    if tracking.get("physical_gate_passed") is not False:
        errors.append("physical gate cannot be marked passed by strategy JSON")
    if policy.get("scope") != "V3_EXPERIMENTAL_PAPER_ONLY":
        errors.append("offensive policy escaped V3 Paper-only scope")
    if len(policy.get("hard_gates_unchanged", [])) < 9:
        errors.append("V3 Paper execution safeguards lost")
    return errors


# Existing, executable implementation surfaces. Source presence is necessary,
# never sufficient for E2E acceptance; host+Cloud originals remain mandatory.
IMPLEMENTATION_SURFACES = {
    "EARLY_INITIAL_REVIEW": (
        "paper_evaluator/v3_experimental_paper_initial_review_v1.py",
        "def propose_initial_full_review(",
    ),
    "POSITIVE_CATALYST_BUY": (
        "paper_evaluator/v3_paper_minipc_selective_tick_v1.py",
        "def released_paper_positive_catalyst_model_once(",
    ),
    "WAIT_REJECT_FRESH_RECHECK": (
        "paper_evaluator/v3_second_leg_policy_candidate_v1.py",
        "def prepare_original_owner_reentry_child(",
    ),
    "CONTINUITY_FAST": (
        "paper_evaluator/v3_p3_early_5m_continuity_research_v1.py",
        "def propose_early_5m_continuity_review(",
    ),
    "VOLUME_SOFT_CONTEXT": (
        "paper_evaluator/v3_experimental_continuity_volume_review_v1.py",
        "def propose_experimental_continuity_review(",
    ),
    "EXTENDED_NEW_BASE": (
        "paper_evaluator/v3_second_leg_policy_candidate_v1.py",
        "def canonical_second_leg_episode(",
    ),
    "RISK_REGIME_OPTIONAL_SOURCES": (
        "paper_evaluator/v3_experimental_paper_model_prompt_v1.py",
        "def build_v3_paper_full_model_prompt(",
    ),
    "MODEL_BUY_CONVERSION": (
        "paper_evaluator/v3_paper_minipc_selective_tick_v1.py",
        "def released_paper_reentry_child_model_once(",
    ),
}


class OffensiveV3PolicyTrackingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = json.loads(BUNDLE.read_text(encoding="utf-8"))

    def test_all_eight_policy_ids_remain_tracked_without_fake_acceptance(self):
        self.assertEqual(validate_policy(self.bundle), [])

    def test_all_eight_offensive_items_have_existing_real_code_owners(self):
        self.assertEqual(set(IMPLEMENTATION_SURFACES), set(IDS))
        root = Path(__file__).resolve().parents[1]
        for item in IDS:
            path, symbol = IMPLEMENTATION_SURFACES[item]
            with self.subTest(item=item):
                self.assertTrue((root / path).is_file(), path)
                self.assertIn(symbol, (root / path).read_text("utf-8"))
                self.assertNotIn("paper_evaluator/evaluate.py", path)
                self.assertNotIn("v2r4_", path)
        # All rows remain unaccepted until original host and Cloud receipts,
        # even though all implementation *surfaces* now exist.
        rows = self.bundle["offensive_paper_policy_concrete_20261018"]["acceptance_tracking"]["items"]
        self.assertTrue(all(x["acceptance"] == "NOT_ACCEPTED" for x in rows))

    def test_missing_duplicate_or_reordered_policy_identity_is_rejected(self):
        import copy
        for change in (
            lambda b: b["offensive_paper_policy_concrete_20261018"]["changes"].pop(),
            lambda b: b["offensive_paper_policy_concrete_20261018"]["acceptance_tracking"]["items"][0].update(
                id="MODEL_BUY_CONVERSION"),
            lambda b: b["offensive_paper_policy_concrete_20261018"]["acceptance_tracking"]["items"].pop(),
        ):
            altered = copy.deepcopy(self.bundle)
            change(altered)
            self.assertTrue(validate_policy(altered))

    def test_no_paper_or_cloud_proof_may_be_credited_by_text_or_ci(self):
        import copy
        for update in (
            {"status": "VERIFIED_E2E", "acceptance": "ACCEPTED"},
            {"status": "OPEN_NOT_E2E_VERIFIED", "acceptance": "ACCEPTED"},
            {"status": "OPEN_NOT_E2E_VERIFIED", "original_receipt_ids": ["FAKE-CI"]},
        ):
            altered = copy.deepcopy(self.bundle)
            altered["offensive_paper_policy_concrete_20261018"]["acceptance_tracking"]["items"][0].update(update)
            self.assertTrue(validate_policy(altered))
        altered = copy.deepcopy(self.bundle)
        altered["offensive_paper_policy_concrete_20261018"]["acceptance_tracking"]["physical_gate_passed"] = True
        self.assertTrue(validate_policy(altered))

    def test_offensive_policy_cannot_disable_cost_risk_or_original_gate(self):
        import copy
        altered = copy.deepcopy(self.bundle)
        altered["offensive_paper_policy_concrete_20261018"]["scope"] = "REAL_TRADING"
        self.assertTrue(validate_policy(altered))
        altered = copy.deepcopy(self.bundle)
        altered["offensive_paper_policy_concrete_20261018"]["hard_gates_unchanged"] = []
        self.assertTrue(validate_policy(altered))


if __name__ == "__main__":
    unittest.main()
