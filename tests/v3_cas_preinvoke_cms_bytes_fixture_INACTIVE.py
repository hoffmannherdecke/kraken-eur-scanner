"""Emit one deterministic PUBLIC CI-only canonical preinvoke candidate.

Pure fixture: no Cloud session, secrets, original-host certificate, database,
network, CAS dispatch, native Windows runner, Paper or output file.
The candidate's untrusted reader claim NEVER represents COMMIT evidence.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.test_v3_cas_preinvoke_signed_candidate_inactive import fixture
from tools.v3_cas_preinvoke_protocol_INACTIVE import (
    build_unsigned_preinvoke_cms_proposal,
)


def main() -> None:
    intent, claimed_readback = fixture()
    reviewed = build_unsigned_preinvoke_cms_proposal(
        intent, claimed_readback, reviewed_at_utc="2026-10-26T15:00:15Z"
    )
    payload = reviewed["unsigned_payload_utf8"]
    digest = hashlib.sha256(payload).hexdigest()
    if (
        digest != reviewed["unsigned_payload_sha256"]
        or reviewed["cas_dispatch_authorized"] is not False
        or reviewed["cloud_commit_independently_proven"] is not False
        or reviewed["originalhost_tpm_cms_signature_produced"] is not False
        or reviewed["v3_paper_release_authorized"] is not False
    ):
        raise RuntimeError("V3_CMS_CI_FIXTURE_UNSAFE_NONCANONICAL_PROPOSAL")
    print(json.dumps({
        "kind": "V3_CI_CANONICAL_PREINVOKE_BYTES_ONLY_NOT_REAL_CUSTODY",
        "payload_base64": base64.b64encode(payload).decode("ascii"),
        "payload_sha256": digest,
        "is_production_signer": False,
        "independent_cloud_reader_proven": False,
        "cas_dispatch_authorized": False,
        "v3_paper_release_authorized": False,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=True))


if __name__ == "__main__":
    main()
