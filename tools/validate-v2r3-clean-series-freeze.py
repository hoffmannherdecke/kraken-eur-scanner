#!/usr/bin/env python3
"""Validate the active V2R3 clean-series freeze contract.

CI trigger note: validator changes are themselves freeze-guarded.

Fails closed if strategy spec/runtime fingerprint or scanner cadence/settings drift
while the clean comparison series is still active.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/"research/v2r3/clean-series-freeze-20261001.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def runtime_fingerprint(paths: list[str]) -> str:
    h=hashlib.sha256()
    for rel in paths:
        p=ROOT/rel
        h.update(rel.encode("utf-8")+b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def require_text(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise SystemExit(f"freeze guard failed: {label} changed or missing: {needle!r}")


def main() -> int:
    m=json.loads(MANIFEST.read_text("utf-8"))
    control=json.loads((ROOT/"paper_runtime_control.json").read_text("utf-8"))

    if m.get("status")=="RETIRED_AFTER_RELEASE_REVIEW_COMPLETE":
        approval_path=ROOT/str(m.get("retirement_approval_artifact") or "")
        if not approval_path.exists():
            raise SystemExit("freeze retirement evidence is missing")
        approval=json.loads(approval_path.read_text("utf-8"))
        if approval.get("decision")!="APPROVED_PAPER":
            raise SystemExit("freeze retirement evidence is not APPROVED_PAPER")
        if approval.get("predecessor_series_id")!=m.get("series_id"):
            raise SystemExit("freeze retirement predecessor mismatch")
        if approval.get("automatic_activation_allowed") is not False:
            raise SystemExit("freeze retirement automatic-activation guardrail changed")
        if approval.get("real_money_actions_allowed") is not False:
            raise SystemExit("freeze retirement real-money guardrail changed")
        if control.get("enabled") is not False:
            raise SystemExit("retired V2R3 freeze requires legacy runtime disabled")
        if control.get("git_runtime_compatibility_mode")!="DISABLED_V2R4_LOCAL_SUPABASE_PRIMARY":
            raise SystemExit("retired V2R3 freeze requires explicit V2R4 local-runtime cutover")
        print(json.dumps({
            "kind":"V2R3_CLEAN_SERIES_FREEZE_VALIDATION_V1",
            "status":"RETIRED_AFTER_RELEASE_REVIEW_COMPLETE",
            "series_id":m["series_id"],
            "historical_strategy_fingerprint_sha256":m["expected_strategy_fingerprint_sha256"],
            "historical_runtime_code_fingerprint_sha256":m["expected_runtime_code_fingerprint_sha256"],
            "retirement_release_id":m.get("retirement_release_id"),
            "retirement_approval_artifact":m.get("retirement_approval_artifact"),
            "guardrails":m["guardrails"],
        },sort_keys=True))
        return 0

    if m.get("status")!="ACTIVE_UNTIL_RELEASE_REVIEW_COMPLETE":
        raise SystemExit("freeze manifest has unknown status")

    for key in ("series_id","test_id","strategy_revision"):
        if control.get(key)!=m.get(key):
            raise SystemExit(
                f"freeze guard failed: paper_runtime_control {key}={control.get(key)!r}, "
                f"expected {m.get(key)!r}"
            )

    spec_hash=sha256_bytes((ROOT/"paper_strategy_spec.json").read_bytes())
    if spec_hash!=m["expected_strategy_fingerprint_sha256"]:
        raise SystemExit(
            "freeze guard failed: strategy fingerprint changed: "
            f"{spec_hash} != {m['expected_strategy_fingerprint_sha256']}"
        )

    runtime_hash=runtime_fingerprint(m["runtime_fingerprint_files"])
    if runtime_hash!=m["expected_runtime_code_fingerprint_sha256"]:
        raise SystemExit(
            "freeze guard failed: runtime code fingerprint changed: "
            f"{runtime_hash} != {m['expected_runtime_code_fingerprint_sha256']}"
        )

    scan=(ROOT/m["scanner"]["workflow"]).read_text("utf-8")
    require_text(
        scan,
        f"cron: '{m['scanner']['expected_schedule_cron']}'",
        "scanner cadence",
    )
    require_text(
        scan,
        m["scanner"]["expected_package_sha256"],
        "scanner package checksum",
    )
    for key,value in m["scanner"]["expected_runtime_settings"].items():
        pattern=rf"{re.escape(key)}:\s*['\"]?{re.escape(str(value))}['\"]?"
        if not re.search(pattern,scan):
            raise SystemExit(
                f"freeze guard failed: scanner runtime setting {key}={value!r} changed/missing"
            )

    # The unified paper workflow contains behaviorally relevant execution semantics
    # that are not part of evaluate.py/revalidate.py fingerprints (model selection,
    # prospective age window, bounded batch selection and lifecycle ordering).
    # Freeze those semantics too, while still allowing persistence/observability-only
    # workflow edits that do not change these invariants.
    runtime_workflow=(ROOT/".github/workflows/paper-evaluator.yml").read_text("utf-8")
    for needle,label in (
        ("group: paper-runtime-v2r2","paper runtime concurrency group"),
        ("cancel-in-progress: false","paper runtime non-cancelling concurrency"),
        ("OPENAI_MODEL: gpt-6-luna","paper evaluator model"),
        ("0<=age<=3600","prospective candidate age window"),
        ("sorted(rows)][:8]","bounded candidate batch size"),
        ("PYTHONPATH=paper_evaluator python paper_evaluator/revalidate.py","WAIT revalidation lifecycle"),
        ("python paper_position_tracker.py","paper position lifecycle"),
        ("python paper_followup.py","paper follow-up lifecycle"),
    ):
        require_text(runtime_workflow,needle,label)

    out={
        "kind":"V2R3_CLEAN_SERIES_FREEZE_VALIDATION_V1",
        "status":"PASS",
        "series_id":m["series_id"],
        "test_id":m["test_id"],
        "strategy_revision":m["strategy_revision"],
        "strategy_fingerprint_sha256":spec_hash,
        "runtime_code_fingerprint_sha256":runtime_hash,
        "scanner_schedule_cron":m["scanner"]["expected_schedule_cron"],
        "scanner_package_sha256":m["scanner"]["expected_package_sha256"],
        "guardrails":m["guardrails"],
    }
    print(json.dumps(out,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
