"""NO-CAS original Windows one-shot probe of the inactive local witness source.

Invoked only by the SHA-reviewed restricted Mini-PC staging task on a unique,
empty, temporary child of the newly authorized witness archive directory.
Uses SYNTHETIC AuditIntent. Never accesses Supabase, GitHub, trading secrets,
live CAS, Windows tasks, or the live Paper runtime. Never deletes anything.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import sys
import uuid

from v3_cas_preinvoke_protocol_INACTIVE import (
    ORIGINAL_SERIES, RPC, build_unsigned_intent,
)
from v3_cas_local_spool_INACTIVE import (
    ZERO_DIGEST, append_local_witness_candidate,
    review_local_witness_candidate,
)

MARKER = "V3_LOCAL_WITNESS_REAL_ORIGINALHOST_SANDBOX_PROBE_PASS"
BASE = Path(r"C:\CryptoSupport\Workspace\V3CasWitness-INACTIVE")


def main() -> int:
    if os.name != "nt" or len(sys.argv) != 2:
        raise RuntimeError("V3_WITNESS_HOST_PROBE_WINDOWS_FIXED_CHILD_ONLY")
    directory = Path(sys.argv[1])
    if (directory.parent != BASE or
            re.fullmatch(r"v3probe-[a-f0-9]{32}", directory.name) is None or
            not directory.is_dir() or
            tuple(directory.iterdir())):
        raise RuntimeError("V3_WITNESS_HOST_PROBE_BAD_SANDBOX")
    empty = review_local_witness_candidate(directory)
    assert empty["local_records_checked"] == 0
    assert empty["last_entry_sha256"] == ZERO_DIGEST
    for number in (1, 2):
        intent = build_unsigned_intent(
            epoch_id="V3CAS-AUDIT-" + "1" * 32,
            ordinal=number,
            intent_id=str(uuid.uuid4()),
            predecessor_series_id=ORIGINAL_SERIES,
            rpc=RPC,
            request_sha256="2" * 64,
            source_sha256="3" * 64,
            fence_sha256="4" * 64,
        )
        result = append_local_witness_candidate(directory, intent)
        assert result["local_records_checked"] == number
        assert result["cloud_cas_authorized"] is False
        assert result["native_restore_authorized"] is False
        assert result["old_writer_auto_rearm_allowed"] is False
        assert result["v3_paper_release_authorized"] is False
    verified = review_local_witness_candidate(directory)
    assert verified["local_records_checked"] == 2
    assert verified["last_entry_sha256"] != ZERO_DIGEST
    assert verified["independent_offdb_durable_storage_proven"] is False
    assert verified["historical_cas_never_invoked_proven"] is False
    assert sorted(x.name for x in directory.iterdir()) == [
        "000001.json", "000002.json",
    ]
    print(MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
