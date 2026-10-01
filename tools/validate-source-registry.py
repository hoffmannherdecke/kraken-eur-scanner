#!/usr/bin/env python3
"""Validate the canonical external source registry.

This is a governance validator only. It does not contact the listed services,
mutate runtime state, or grant permissions.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "research/source-registry.json"


def nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    args = ap.parse_args()

    data = json.loads(args.registry.read_text("utf-8"))
    errors: list[str] = []

    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if data.get("kind") != "EXTERNAL_SOURCE_REGISTRY_V1":
        errors.append("kind mismatch")

    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("sources must be a non-empty list")
        sources = []

    ids: list[str] = []
    for idx, src in enumerate(sources):
        if not isinstance(src, dict):
            errors.append(f"sources[{idx}] must be an object")
            continue

        sid = str(src.get("id") or "")
        if not re.fullmatch(r"[a-z0-9_]+", sid):
            errors.append(f"sources[{idx}].id invalid: {sid!r}")
        ids.append(sid)

        for key in ("status", "class", "unique_value", "overlap_strategy", "persistence_mode", "access"):
            if not isinstance(src.get(key), str) or not src.get(key).strip():
                errors.append(f"{sid or idx}: {key} must be a non-empty string")

        if not nonempty_list(src.get("authoritative_for")):
            errors.append(f"{sid or idx}: authoritative_for must be non-empty")
        if not isinstance(src.get("not_authoritative_for"), list):
            errors.append(f"{sid or idx}: not_authoritative_for must be a list")
        if not isinstance(src.get("overlap_with"), list):
            errors.append(f"{sid or idx}: overlap_with must be a list")

        duplicate_raw = src.get("duplicate_raw_storage_allowed")
        if not isinstance(duplicate_raw, bool):
            errors.append(f"{sid or idx}: duplicate_raw_storage_allowed must be boolean")
        if duplicate_raw is True:
            justification = str(src.get("duplicate_storage_justification") or "")
            if len(justification.strip()) < 20:
                errors.append(
                    f"{sid or idx}: duplicate raw storage requires explicit justification"
                )

        unique_value = str(src.get("unique_value") or "").strip()
        if len(unique_value) < 20:
            errors.append(f"{sid or idx}: unique_value too vague")

    duplicates = sorted({x for x in ids if x and ids.count(x) > 1})
    for sid in duplicates:
        errors.append(f"duplicate source id: {sid}")

    known = set(ids)
    for src in sources:
        if not isinstance(src, dict):
            continue
        sid = str(src.get("id") or "")
        for other in src.get("overlap_with") or []:
            if not isinstance(other, str):
                errors.append(f"{sid}: overlap_with entries must be strings")
                continue
            if other.startswith("internal:"):
                continue
            if other not in known:
                errors.append(f"{sid}: overlap target not registered: {other}")

    result = {
        "kind": "SOURCE_REGISTRY_VALIDATION_V1",
        "status": "PASS" if not errors else "FAIL",
        "source_count": len(sources),
        "source_ids": sorted(x for x in ids if x),
        "errors": errors,
        "guardrails": {
            "network_used": False,
            "source_permissions_changed": False,
            "runtime_changed": False,
            "strategy_changed": False,
            "orders": False,
            "real_money_actions": False,
        },
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
