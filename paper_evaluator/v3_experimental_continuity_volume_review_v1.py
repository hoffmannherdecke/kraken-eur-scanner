#!/usr/bin/env python3
"""V3 EXPERIMENTAL research ONLY: one-change CONTINUITY entry REVIEW relaxation.

The Standard arm uses the frozen inactive P3 CONTINUITY proposal unmodified.
The Experimental arm can ask for an independent *future* full-model review
when the ONLY failed Standard check is 5m relative-volume >= 1.2 and the
valid closed 5m volume ratio lies in [1.0, 1.2). This is deliberately not
a BUY, model call, actual Paper trade, new watcher, writer, or real-money path.

Candidate clocks, PIT inputs, OHLC, volume, anti-chase, structural references,
spread and all remaining Standard checks are identical. No dynamic parameter
search: one frozen contrast for a small separately approved matched cohort.
"""
from __future__ import annotations

import math
from typing import Any

from paper_evaluator.v3_continuity_fresh_review_candidate_v1 import (
    KIND as BASELINE_KIND,
    ELIGIBLE as BASELINE_ELIGIBLE,
    propose_continuity_fresh_review,
)
from paper_evaluator.v3_extended_reentry_review_v1 import (
    EXISTING_V2R4_VOLUME_RATIO_REVIEW_FLOOR,
)

KIND = "V3_EXP_INACTIVE_CONTINUITY_ONE_CHANGE_VOLUME_REVIEW_V1"
ELIGIBLE = "EXPERIMENTAL_CONTINUITY_VOLUME_SUPPORTS_NEW_FULL_REVIEW_ONLY"
EXPERIMENTAL_FLOOR = 1.0
UNCHANGED_VOLUME_CHECK = "unchanged_closed_5m_volume_floor"
EXPECTED_STANDARD_CHECKS = frozenset({
    "closed_new_15m_continuation_above_base",
    "prior_15m_base_not_excessive",
    "no_new_excessive_extension",
    "closed_5m_price_continuation",
    "unchanged_closed_5m_volume_floor",
    "fresh_eur_spread_guard",
    "fresh_ask_not_chase",
    "only_structural_reference_below_ask",
})


def propose_experimental_continuity_review(
    candidate: dict[str, Any],
    baseline_decision: dict[str, Any],
    entry_evidence: dict[str, Any],
    ticker: dict[str, Any],
    closed_15m_bars: list[dict[str, Any]],
    *,
    decision_at_utc: str,
    optional_sources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute *both arms from the same input*, no model/network/state writes."""
    baseline = propose_continuity_fresh_review(
        candidate, baseline_decision, entry_evidence, ticker, closed_15m_bars,
        decision_at_utc=decision_at_utc, optional_sources=optional_sources,
    )
    common = {
        "kind": KIND,
        "pair": candidate.get("pair"),
        "source_candidate_id": candidate.get("candidate_id"),
        "standard_review_kind": baseline.get("kind"),
        "standard_review_status": baseline.get("status"),
        "standard_review_permission": bool(baseline.get("request_model_recheck_only")),
        "standard_volume_floor": EXISTING_V2R4_VOLUME_RATIO_REVIEW_FLOOR,
        "experimental_volume_floor": EXPERIMENTAL_FLOOR,
        "only_changed_standard_gate": UNCHANGED_VOLUME_CHECK,
        "decision": "NO_DECISION_AUTHORITY",
        "request_model_recheck_only": False,
        "approval_to_call_model": False,
        "paper_trade": False,
        "orders": False,
        "real_money_actions": False,
        "model_called": False,
        "paper_writer_started": False,
        "paper_state_changed": False,
        "active_v2r4_changed": False,
        "automatic_live_activation": False,
        "no_auto_retries": True,
        "economic_edge_proven": False,
        "release_evidence": False,
        "same_clock_baseline": True,
        "snapshot_recheck_must_be_deduplicated": True,
        "fee_pct_each_side_unchanged": 0.6,
        "scout_eur_unchanged": 50,
        "stage2_eur_unchanged": 50,
        "new_approval_required_for_full_model_and_paper_shadow": True,
    }
    def result(status: str, **details: Any) -> dict[str, Any]:
        return {**common, "status": status, **details}

    if baseline.get("kind") != BASELINE_KIND:
        return result("UNKNOWN_BASELINE_NOT_PROVEN")
    if baseline.get("status") == BASELINE_ELIGIBLE:
        return result("BASELINE_ALREADY_ELIGIBLE_NOT_INCREMENTAL")
    if baseline.get("status") != "CONTINUITY_EARLY_CONFIRMATION_NOT_PROVEN":
        return result("NO_SAFE_STANDARD_PRICE_VOLUME_PROVENANCE")

    checks = baseline.get("checks")
    if (not isinstance(checks, dict) or set(checks) != EXPECTED_STANDARD_CHECKS
            or any(type(v) is not bool for v in checks.values())
            or checks[UNCHANGED_VOLUME_CHECK] is not False
            or any(v is not True for k, v in checks.items()
                   if k != UNCHANGED_VOLUME_CHECK)):
        return result("OTHER_HARD_CONFIRMATION_FAILED")

    try:
        frame = entry_evidence["frames"]["5"]
        ratio = frame["volume_ratio_prior_5"]
        if (frame["status"] != "VALID" or type(ratio) not in (int, float)
                or not math.isfinite(ratio) or ratio < 0):
            return result("UNKNOWN_REQUIRED_5M_VOLUME_PIT")
        if not (EXPERIMENTAL_FLOOR <= ratio < EXISTING_V2R4_VOLUME_RATIO_REVIEW_FLOOR):
            return result("OUTSIDE_EXPERIMENTAL_ONE_CHANGE_VOLUME_BAND")
        if (baseline.get("source_candidate_id") != candidate.get("candidate_id")
                or baseline.get("pair") != candidate.get("pair")
                or baseline.get("new_snapshot_known_at_utc") is not None):
            # A non-eligible standard review must not imply a minted BUY.
            return result("BASELINE_PROVENANCE_MISMATCH")
        if not isinstance(entry_evidence.get("known_at_utc"), str):
            return result("UNKNOWN_REQUIRED_5M_VOLUME_PIT")
    except (KeyError, ValueError, TypeError, AttributeError):
        return result("UNKNOWN_REQUIRED_5M_VOLUME_PIT")

    ticket = result(
        ELIGIBLE,
        original_candidate_fresh=True,
        new_closed_15m_bar_after_candidate=True,
        fresh_close_at_utc=None,  # provisioned separately from verified bars below
        new_snapshot_known_at_utc=entry_evidence["known_at_utc"],
        old_standard_all_other_checks_passed=True,
        old_standard_volume_check_failed=True,
        standard_unmodified_checks=dict(checks),
        observed_relative_volume_ratio=round(float(ratio), 6),
        fee_and_stop_guards_required_in_shared_full_validator=True,
        full_model_decision_not_yet_produced=True,
        next_action="SEPARATE_APPROVAL_REQUIRED_BEFORE_ANY_MODEL_OR_PAPER_PROBE",
    )
    # Use the same canonical closed last 15m timestamp; never invent a time.
    try:
        from datetime import timedelta
        from paper_evaluator.v3_second_leg_policy_candidate_v1 import _bar_start, CLOSED_BAR_SECONDS
        last = closed_15m_bars[-1]
        ticket["fresh_close_at_utc"] = (
            _bar_start(last) + timedelta(seconds=CLOSED_BAR_SECONDS)).isoformat()
        if ticket["fresh_close_at_utc"] == "":
            return result("UNKNOWN_REQUIRED_CLOSED_BAR_CLOCK")
    except (KeyError, ValueError, TypeError, IndexError, AttributeError):
        return result("UNKNOWN_REQUIRED_CLOSED_BAR_CLOCK")
    ticket["snapshot_recheck_key"] = (
        f"{candidate['candidate_id']}|{ticket['fresh_close_at_utc']}|EXP_VOLUME_1_0")
    ticket["request_model_recheck_only"] = True
    return ticket
