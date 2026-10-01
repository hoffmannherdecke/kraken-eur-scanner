#!/usr/bin/env python3
"""Build a fail-closed paper release rollback snapshot.

The snapshot is content-addressed and limited to explicitly protected code/config
files. It is NOT an instruction to reset the whole repository to an old commit,
because the repository also carries evolving paper evidence/state.

No runtime is enabled/disabled, no strategy is changed, no exchange is called,
and no order or real-money action exists in this tool.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FREEZE = ROOT / "research/v2r3/clean-series-freeze-20261001.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def runtime_fingerprint(root: Path, paths: list[str]) -> str:
    h = hashlib.sha256()
    for rel in paths:
        p = root / rel
        h.update(rel.encode("utf-8") + b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def git_head(root: Path) -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return out or None
    except Exception:
        return None


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    root = args.root.resolve()
    freeze_path = args.freeze.resolve()
    freeze = load_json(freeze_path)
    if freeze.get("status") != "ACTIVE_UNTIL_RELEASE_REVIEW_COMPLETE":
        raise SystemExit("rollback snapshot blocked: freeze manifest is not active")

    control_path = root / "paper_runtime_control.json"
    spec_path = root / "paper_strategy_spec.json"
    control = load_json(control_path)
    spec_bytes = spec_path.read_bytes()

    for key in ("series_id", "test_id", "strategy_revision"):
        if control.get(key) != freeze.get(key):
            raise SystemExit(
                f"rollback snapshot blocked: control {key}={control.get(key)!r}, "
                f"expected {freeze.get(key)!r}"
            )

    strategy_hash = sha256_bytes(spec_bytes)
    if strategy_hash != freeze["expected_strategy_fingerprint_sha256"]:
        raise SystemExit(
            "rollback snapshot blocked: strategy fingerprint drift "
            f"{strategy_hash} != {freeze['expected_strategy_fingerprint_sha256']}"
        )

    runtime_files = list(freeze["runtime_fingerprint_files"])
    runtime_hash = runtime_fingerprint(root, runtime_files)
    if runtime_hash != freeze["expected_runtime_code_fingerprint_sha256"]:
        raise SystemExit(
            "rollback snapshot blocked: runtime fingerprint drift "
            f"{runtime_hash} != {freeze['expected_runtime_code_fingerprint_sha256']}"
        )

    scanner_workflow = str(freeze["scanner"]["workflow"])
    protected = [
        "paper_runtime_control.json",
        "paper_strategy_spec.json",
        *runtime_files,
        scanner_workflow,
        str(freeze_path.relative_to(root)).replace("\\", "/"),
    ]

    file_hashes: dict[str, str] = {}
    for rel in protected:
        p = root / rel
        if not p.is_file():
            raise SystemExit(f"rollback snapshot blocked: protected file missing: {rel}")
        file_hashes[rel] = sha256_bytes(p.read_bytes())

    snapshot = {
        "schema_version": 1,
        "kind": "PAPER_RELEASE_ROLLBACK_SNAPSHOT_V1",
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "LAST_KNOWN_GOOD_REFERENCE",
        "source_git_head": git_head(root),
        "source_git_head_scope": (
            "audit reference only; NEVER reset the whole repository to this commit "
            "because paper evidence/state continues to evolve"
        ),
        "series_id": freeze["series_id"],
        "test_id": freeze["test_id"],
        "strategy_revision": freeze["strategy_revision"],
        "strategy_fingerprint_sha256": strategy_hash,
        "runtime_code_fingerprint_sha256": runtime_hash,
        "scanner_schedule_cron": freeze["scanner"]["expected_schedule_cron"],
        "scanner_package_sha256": freeze["scanner"]["expected_package_sha256"],
        "protected_files_sha256": file_hashes,
        "rollback_semantics": {
            "whole_repo_reset_allowed": False,
            "evidence_or_state_rewind_allowed": False,
            "protected_code_config_restore_only": True,
            "preserve_failed_new_series_evidence": True,
            "queue_ttl_persistence_reconciliation_required_before_restart": True,
        },
        "guardrails": {
            "strategy_changed": False,
            "runtime_enabled_or_disabled": False,
            "exchange_called": False,
            "orders": False,
            "real_money_actions": False,
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", "utf-8")
    print(json.dumps(snapshot, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
