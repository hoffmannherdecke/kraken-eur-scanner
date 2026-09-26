"""Deterministic parity harness for shared Paper and future Live assessments.

This compares the common market-data basis and read-only assessment callbacks.
It does not implement a strategy, connect to an account, or enable live mode.
"""
import hashlib
import json
import copy
from datetime import datetime

from .microstructure import derive_microstructure_bias


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def canonical_sha256(value):
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _validate_utc(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("event timestamp must be explicit UTC with Z suffix")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.utcoffset().total_seconds() != 0:
        raise ValueError("event timestamp is not UTC")


def evaluation_basis(snapshot):
    """Build the one canonical read-only input envelope shared by both paths."""
    required = ("symbol", "exchange_at", "seq", "received_at", "quality", "book",
                "flow", "mid_return_60s_pct", "wall_events")
    missing = [key for key in required if key not in snapshot]
    if missing:
        raise ValueError("incomplete assessment basis: " + ",".join(missing))
    _validate_utc(snapshot["exchange_at"])
    _validate_utc(snapshot["received_at"])
    if not isinstance(snapshot["seq"], int) or snapshot["seq"] < 1:
        raise ValueError("event sequence must be a positive integer")
    basis = {key: snapshot[key] for key in required}
    for key in ("source_wire_seq", "source_trade_ids", "last_trade", "candles",
                "context_age_seconds", "context_levels", "ticker24"):
        if key in snapshot:
            basis[key] = snapshot[key]
    return basis


def common_market_assessment(basis):
    """Return the existing descriptive market labels; never a trade action."""
    bias, absorption = derive_microstructure_bias(
        basis["flow"]["60s"], basis["book"]["imbalance_top10"],
        basis["mid_return_60s_pct"])
    return {"microstructure_bias": bias, "absorption_candidate": absorption}


def compare_assessment_paths(raw_events, snapshot, paper_assessor=None, live_assessor=None):
    """Produce an auditable parity report from identical captured inputs.

    Assessors are injected by the test or integration harness. The default
    callback is the shared descriptive assessment function. Live use remains
    separately disabled by market_data.runtime.
    """
    paper_assessor = paper_assessor or common_market_assessment
    live_assessor = live_assessor or common_market_assessment
    basis = evaluation_basis(snapshot)
    previous_seq = 0
    for event in raw_events:
        if not isinstance(event.get("seq"), int) or event["seq"] <= previous_seq:
            raise ValueError("raw event sequence must be strictly increasing")
        _validate_utc(event.get("exchange_at"))
        _validate_utc(event.get("received_at"))
        previous_seq = event["seq"]
    raw_digest = canonical_sha256(raw_events)
    differences = []
    basis_digest = canonical_sha256(basis)
    paper_basis = copy.deepcopy(basis)
    live_basis = copy.deepcopy(basis)
    paper_basis_digest = canonical_sha256(paper_basis)
    live_basis_digest = canonical_sha256(live_basis)
    if paper_basis_digest != live_basis_digest:
        differences.append("assessment_input")
    paper_result = paper_assessor(paper_basis)
    live_result = live_assessor(live_basis)
    if canonical_sha256(paper_basis) != basis_digest:
        differences.append("paper_input_mutated")
    if canonical_sha256(live_basis) != basis_digest:
        differences.append("live_input_mutated")
    if _canonical(paper_result) != _canonical(live_result):
        differences.append("assessment_result")
    return {
        "schema_version": 1,
        "status": "PASS" if not differences else "FAIL",
        "raw_events": raw_events,
        "raw_events_sha256": raw_digest,
        "utc_timestamps_and_order": [
            {"seq": event["seq"], "exchange_at": event["exchange_at"],
             "received_at": event["received_at"]} for event in raw_events
        ],
        "shared_input": basis,
        "shared_input_sha256": basis_digest,
        "paper_input_sha256": paper_basis_digest,
        "live_input_sha256": live_basis_digest,
        "paper_result": paper_result,
        "live_path_result": live_result,
        "deviations": differences,
        "scope": "shared_data_and_descriptive_assessment_only; no strategy or orders",
    }
