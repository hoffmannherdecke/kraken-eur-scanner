"""Offline adversarial tests for live-role catalog reviewer: never a CAS gate."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from v3_cas_actor_custody_gate_INACTIVE import (
    KIND, EXPECTED_NAMES, AUTHORITY_FIELDS, review_actor_catalog_baseline,
)


def baseline():
    roles = []
    for name in EXPECTED_NAMES:
        roles.append({
            "name": name,
            "exists": True,
            "can_login": name == "v3_cas_operator_login",
            "inherits_privileges": False,
            "bypasses_rls": False,
            "is_superuser": False,
            "can_create_role": False,
            "can_create_database": False,
            "can_replicate": False,
            "memberships": [{
                "direction": "incoming", "granted_role": name,
                "member_role": "postgres", "admin_option": True,
                "inherit_option": False, "set_option": False,
            }],
        })
    return {
        "kind": KIND,
        "catalog_read_at_utc": "2026-10-26T18:00:11.572541Z",
        "roles": roles,
        "audit_epoch_installed": False,
        "audit_intent_installed": False,
        "cas_rpc_installed": False,
        **{key: False for key in AUTHORITY_FIELDS},
    }


class V3CasActorCustodyReadOnlySourceTests(unittest.TestCase):
    @staticmethod
    def review(row):
        return review_actor_catalog_baseline(row)

    def assert_no_authority(self, result):
        for key in (
            "catalog_reader_source_independently_authenticated",
            "separate_production_login_sessions_verified",
            "genuine_prior_audit_commit_independently_verified",
            "external_full_attempt_custody_proven",
            "real_tpm_signer_acl_independence_proven",
            "cas_dispatch_authorized", "old_writer_auto_rearm_allowed",
            "v3_paper_release_authorized",
        ):
            self.assertIs(result[key], False, key)

    def test_realistic_live_baseline_is_hold_not_authorization(self):
        result = self.review(baseline())
        self.assertTrue(result["catalog_structure_matches_predeployment_baseline"])
        self.assertEqual(result["disposition"],
                         "BASELINE_MATCH_CAS_RUNTIME_AND_CUSTODY_STILL_HOLD")
        self.assert_no_authority(result)

    def test_absent_and_untrusted_shape_hold(self):
        for row in (None, {}, [], "ok", {"kind": KIND}):
            with self.subTest(row=row):
                result = self.review(row)
                self.assertFalse(result["catalog_structure_matches_predeployment_baseline"])
                self.assert_no_authority(result)

    def test_extra_fields_and_self_authorizing_claims_hold(self):
        for value in (True, "true", 1, None):
            row = baseline()
            row["cas_dispatch_authorized"] = value
            result = self.review(row)
            self.assertFalse(result["catalog_structure_matches_predeployment_baseline"])
            self.assert_no_authority(result)
        for wrong in ({"untrusted_approval": True}, {"credential": "fake"},
                      {"reader_signed_by_tpm": True}):
            row = baseline()
            row.update(wrong)
            self.assertFalse(self.review(row)["catalog_structure_matches_predeployment_baseline"])

    def test_role_login_membership_and_privilege_drift_hold(self):
        for idx, field, value in (
            (0, "can_login", True),
            (1, "bypasses_rls", True),
            (2, "inherits_privileges", True),
            (3, "is_superuser", True),
            (0, "can_create_role", True),
            (2, "can_create_database", True),
            (3, "can_replicate", True),
            (3, "can_login", False),
            (2, "exists", False),
            (1, "can_login", "false"),
        ):
            row = baseline()
            row["roles"][idx][field] = value
            with self.subTest(idx=idx,field=field,value=value):
                result = self.review(row)
                self.assertFalse(result["catalog_structure_matches_predeployment_baseline"])
                self.assert_no_authority(result)

    def test_cross_role_grant_or_admin_set_option_fail(self):
        mutations = [
            ("member_role", "v3_cas_operator_login"),
            ("granted_role", "v3_cas_executor"),
            ("direction", "outgoing"),
            ("set_option", True),
            ("inherit_option", True),
            ("admin_option", False),
        ]
        for key, value in mutations:
            row = baseline()
            row["roles"][0]["memberships"][0][key] = value
            with self.subTest(key=key,value=value):
                self.assertFalse(self.review(row)["catalog_structure_matches_predeployment_baseline"])
        row = baseline()
        row["roles"][0]["memberships"].append(deepcopy(
            row["roles"][0]["memberships"][0]))
        self.assertFalse(self.review(row)["catalog_structure_matches_predeployment_baseline"])

    def test_installed_objects_need_new_gate_not_existing_baseline_pass(self):
        for key in ("cas_rpc_installed", "audit_epoch_installed",
                    "audit_intent_installed"):
            for value in (True, None, "false"):
                row = baseline()
                row[key] = value
                with self.subTest(key=key,value=value):
                    result = self.review(row)
                    self.assertFalse(result["catalog_structure_matches_predeployment_baseline"])
                    self.assert_no_authority(result)

    def test_wrong_order_count_or_timestamp_fail(self):
        changed = [
            lambda d: d["roles"].reverse(),
            lambda d: d["roles"].pop(),
            lambda d: d["roles"].append(deepcopy(d["roles"][0])),
            lambda d: d.update(catalog_read_at_utc="2026-10-26T18:00:11Z"),
            lambda d: d.update(catalog_read_at_utc="2026-02-30T18:00:11.123456Z"),
            lambda d: d.update(catalog_read_at_utc="2026-10-26T18:00:11.123456+00:00"),
        ]
        for mutate in changed:
            row = baseline()
            mutate(row)
            self.assertFalse(self.review(row)["catalog_structure_matches_predeployment_baseline"])

    def test_catalog_sql_is_select_only_no_secret_or_role_provisioning(self):
        sql = (ROOT / "supabase/v3-cas-actor-custody-readonly-preflight-INACTIVE.sql").read_text("utf8")
        executable = "\n".join(line for line in sql.splitlines()
                               if not line.lstrip().startswith("--"))
        self.assertTrue(executable.lstrip().startswith("WITH wanted(rolname) AS"))
        self.assertEqual(executable.count(" AS catalog_readonly_v1;"),1)
        self.assertIn("pg_catalog.pg_auth_members", executable)
        self.assertIn("pg_catalog.pg_roles", executable)
        self.assertIn("pg_catalog.to_regprocedure", executable)
        self.assertIn("'cas_dispatch_authorized',false", executable)
        self.assertNotRegex(executable.lower(),
            r"\b(?:create|alter|drop|grant|revoke|insert|update|delete|truncate|call|do|execute|set role)\s+"
            r"(?:role|table|function|schema|into|on|from|public|v3_)")
        for secret_key in ("password", "pg_authid", "pg_shadow", "connection_string",
                           "apikey", "pgp_sym_", "private_key"):
            self.assertNotIn(secret_key, executable.lower())


if __name__ == "__main__":
    unittest.main()
