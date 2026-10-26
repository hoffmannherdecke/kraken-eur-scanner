"""INACTIVE V3 CAS actor/catalog baseline reviewer; never a grant/release.

Reviews a purported result of the READ-ONLY pg_catalog SQL snapshot.
It cannot authenticate its supplier, issue credentials, verify a real
session, verify a separate audit COMMIT, or prove external immutable custody.
A matching catalogue baseline explicitly still denies CAS and Paper release.
"""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Mapping


KIND = "V3_CAS_ACTOR_CUSTODY_CATALOG_READONLY_V1"
EXPECTED_NAMES = (
    "v3_cas_audit_reader",
    "v3_cas_audit_writer",
    "v3_cas_executor",
    "v3_cas_operator_login",
)
AUTHORITY_FIELDS = (
    "authentic_independent_runtime_sessions_proven",
    "real_originalhost_tpm_signer_independence_proven",
    "external_complete_immutable_attempt_custody_proven",
    "cas_dispatch_authorized",
    "old_writer_auto_rearm_allowed",
    "v3_paper_release_authorized",
)
CATALOG_FIELDS = {
    "kind", "catalog_read_at_utc", "roles",
    "audit_epoch_installed", "audit_intent_installed", "cas_rpc_installed",
    *AUTHORITY_FIELDS,
}
ROLE_FIELDS = {
    "name", "exists", "can_login", "inherits_privileges",
    "bypasses_rls", "is_superuser", "can_create_role",
    "can_create_database", "can_replicate", "memberships",
}
GRANT_FIELDS = {
    "direction", "granted_role", "member_role",
    "admin_option", "inherit_option", "set_option",
}


def review_actor_catalog_baseline(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    """Strict structural review, not an auth/role grant/custody certificate."""
    reviewed = {
        "kind": "V3_CAS_ACTOR_CUSTODY_REVIEW_SOURCE_ONLY_V1",
        "disposition": "HOLD_CATALOG_MISSING_OR_UNTRUSTED",
        "catalog_structure_matches_predeployment_baseline": False,
        "catalog_reader_source_independently_authenticated": False,
        "separate_production_login_sessions_verified": False,
        "genuine_prior_audit_commit_independently_verified": False,
        "external_full_attempt_custody_proven": False,
        "real_tpm_signer_acl_independence_proven": False,
        "cas_dispatch_authorized": False,
        "old_writer_auto_rearm_allowed": False,
        "v3_paper_release_authorized": False,
    }
    if not isinstance(snapshot, Mapping):
        return reviewed
    reviewed["disposition"] = "HOLD_CATALOG_SHAPE_OR_ACTOR_DRIFT"
    if set(snapshot) != CATALOG_FIELDS or snapshot.get("kind") != KIND:
        return reviewed
    if any(type(snapshot.get(key)) is not bool or snapshot[key] is not False
           for key in AUTHORITY_FIELDS):
        return reviewed
    if any(type(snapshot.get(key)) is not bool or snapshot[key] is not False
           for key in ("audit_epoch_installed", "audit_intent_installed",
                       "cas_rpc_installed")):
        return reviewed
    utc = snapshot.get("catalog_read_at_utc")
    if not isinstance(utc, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z", utc
    ):
        return reviewed
    try:
        datetime.strptime(utc, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        return reviewed
    roles = snapshot.get("roles")
    if type(roles) is not list or len(roles) != 4:
        return reviewed
    if [r.get("name") if isinstance(r, Mapping) else None for r in roles] != list(EXPECTED_NAMES):
        return reviewed
    for role in roles:
        if set(role) != ROLE_FIELDS:
            return reviewed
        expected_login = role["name"] == "v3_cas_operator_login"
        required = {
            "exists": True,
            "can_login": expected_login,
            "inherits_privileges": False,
            "bypasses_rls": False,
            "is_superuser": False,
            "can_create_role": False,
            "can_create_database": False,
            "can_replicate": False,
        }
        if any(type(role.get(k)) is not bool or role[k] is not v
               for k, v in required.items()):
            return reviewed
        membership = role.get("memberships")
        if type(membership) is not list or len(membership) != 1:
            return reviewed
        grant = membership[0]
        if not isinstance(grant, Mapping) or set(grant) != GRANT_FIELDS:
            return reviewed
        if (grant["direction"] != "incoming"
            or grant["granted_role"] != role["name"]
            or grant["member_role"] != "postgres"
            or type(grant["admin_option"]) is not bool
            or grant["admin_option"] is not True
            or type(grant["inherit_option"]) is not bool
            or grant["inherit_option"] is not False
            or type(grant["set_option"]) is not bool
            or grant["set_option"] is not False):
            return reviewed
    # Catalog is still caller-supplied data. No approved custody or actor
    # credentials are implied by matching the EXPECTED SAFE HOLD baseline.
    reviewed["catalog_structure_matches_predeployment_baseline"] = True
    reviewed["disposition"] = "BASELINE_MATCH_CAS_RUNTIME_AND_CUSTODY_STILL_HOLD"
    return reviewed
