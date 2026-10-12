"""New V3 experimental PAPER decision semantics: consume proven PIT, not V2R3 selector.

Pure prompt builder. The actual complete model client and P4 validation must
be separately invoked under bounded Paper-only authority. Hindsight outcomes
and optional source failures are never included as past decision evidence.
"""
from __future__ import annotations
import json
from typing import Any
from paper_evaluator.v3_experimental_paper_initial_review_v1 import (
    KIND as INITIAL_KIND, ELIGIBLE as INITIAL_ELIGIBLE,
)
from paper_evaluator.v3_entry_handoff_probe import attach_to_future_evaluator,utc
from paper_evaluator.v3_paper_context_bridge_v1 import (KIND as CONTEXT_KIND, fuse_existing_sources)
from paper_evaluator.v3_paper_positive_source_entry_v1 import (
    ELIGIBLE as POSITIVE_ELIGIBLE, assess_positive_source, make_source_candidate,
)

KIND="V3_EXPERIMENTAL_PAPER_FULL_MODEL_PROMPT_V1"


def build_v3_paper_full_model_prompt(*,candidate:dict[str,Any],
                                     eligibility:dict[str,Any],
                                     entry_evidence:dict[str,Any],
                                     ticker:dict[str,Any],
                                     pair_metadata:dict[str,Any],
                                     decision_at_utc:str,
                                     optional_context:dict[str,Any]|None=None)->str:
    """Return model input only; no model call, simulated trade, or raw outcome."""
    if (eligibility.get("status")!=INITIAL_ELIGIBLE
            or eligibility.get("kind")!=INITIAL_KIND
            or eligibility.get("request_model_recheck_only") is not True
            or eligibility.get("source_candidate_id")!=candidate.get("candidate_id")
            or eligibility.get("pair")!=candidate.get("pair")
            or eligibility.get("new_snapshot_known_at_utc")!=entry_evidence.get("known_at_utc")):
        raise ValueError("V3 initial real source review not authorized")
    attached=attach_to_future_evaluator(
        {"pair":candidate.get("pair")},{},entry_evidence,decision_at_utc)
    if (ticker.get("pair")!=candidate.get("pair")
            or pair_metadata.get("pair")!=candidate.get("pair")
            or pair_metadata.get("status")!="online"
            or pair_metadata.get("spot") is not True
            or pair_metadata.get("quote")!="EUR"):
        raise ValueError("spot EUR authority mismatch")
    _=utc(decision_at_utc)
    # Raw optional context is not a hard veto and may contain sensitive fields;
    # only separately curated, categorically named present/unavailable status.
    sources={}
    for key,value in (optional_context or {}).items():
        if not isinstance(key,str) or len(key)>45 or not key.replace("_","").isalnum():
            raise ValueError("untrusted optional-source name")
        sources[key]={"available": value is not None}
    # Never accept a rich candidate payload with a retrospective outcome.
    forbidden={"followup","post_event_mfe","post_event_mae","actual_pnl",
               "future_close","outcome24h","future_result"}
    if forbidden.intersection(candidate):
        raise ValueError("hindsight candidate field cannot enter true model")
    # Accept verified bounded source facts, not merely a boolean availability.
    # Real per-source known_at cannot be after the actual model input clock.
    if optional_context and optional_context.get("kind")==CONTEXT_KIND:
        context=fuse_existing_sources(optional_context.get("raw_snapshots",{}),
                                      decision_at_utc=decision_at_utc,
                                      pair=candidate["pair"])
        sources={key:{"available":value["state"]=="AVAILABLE_PIT_CONTEXT_ONLY"}
                 for key,value in context["sources"].items()}
    else:
        context=fuse_existing_sources({},decision_at_utc=decision_at_utc,
                                      pair=candidate["pair"])
    positive_trigger=None
    if candidate.get("entry_origin")=="VERIFIED_POSITIVE_SOURCE_CATALYST":
        if not optional_context or optional_context.get("kind")!=CONTEXT_KIND:
            raise ValueError("positive entry cannot be prompt-only or unverified")
        provided=optional_context.get("raw_snapshots") or {}
        name=candidate.get("positive_source_name")
        snap=provided.get(name)
        proof=assess_positive_source(
            pair=candidate["pair"],source_name=name,snapshot=snap,
            decision_at_utc=decision_at_utc,
            market_move=provided.get("dynamic_move_radar"))
        if proof["status"]!=POSITIVE_ELIGIBLE:
            raise ValueError("unverified positive source event")
        expected=make_source_candidate(
            pair=candidate["pair"],kraken_altname=candidate["altname"],
            source_name=name,snapshot=snap,decision_at_utc=decision_at_utc,
            market_move=provided.get("dynamic_move_radar"))
        if (expected["candidate_id"]!=candidate["candidate_id"]
                or expected["event_time_utc"]!=candidate["event_time_utc"]
                or expected["positive_source_event_id"]!=candidate.get("positive_source_event_id")):
            raise ValueError("positive source event/candidate identity mismatch")
        positive_trigger={
            "status":proof["status"],"reason":proof["positive_reason"],
            "source_name":name,"source_event_id":proof["source_event_id"],
            "source_owner":proof["source_owner"],"source_id":proof["source_id"],
            "observed_at_utc":proof["source_observed_at_utc"],
            "known_at_utc":proof["source_known_at_utc"],
            "coin_impact_mechanism":proof["impact_mechanism"],
            "independent_from_scanner":True,
            "source_is_not_buy_authority":True,
        }
    data={
        "strategy":"V3-EXPERIMENTAL-PAPER-ONLY-NO-REAL-ORDERS",
        "candidate":{"candidate_id":candidate["candidate_id"],
                     "pair":candidate["pair"],
                     "event_time_utc":candidate["event_time_utc"],
                     "scanner_market_context":candidate.get("scanner_market_context")},
        "decision_at_utc":decision_at_utc,
        "source_eligibility":{k:eligibility.get(k) for k in
                              ("kind","status","checks","source_5m_volume_ratio",
                               "new_snapshot_known_at_utc")},
        "current_kraken_execution":{k:ticker.get(k) for k in
                                    ("pair","bid","ask","spread_pct","observed_at_utc")},
        "current_kraken_spot_eur_pair":{k:pair_metadata.get(k) for k in
                                      ("pair","status","spot","quote","minimum_order_passed",
                                       "observed_at_utc")},
        "candidate_entry_evidence":attached["candidate_entry_evidence"],
        "positive_source_trigger_for_independent_paper_entry":positive_trigger,
        "optional_source_availability_context_only":sources,
        "actual_optional_context_with_source_clock":context,
        "scout_eur":50,"stage2_eur":50,"taker_fee_pct_each_side":0.6,
    }
    intro="""PAPER RESEARCH EVALUATOR, V3-EXPERIMENTAL, NEVER REAL MONEY OR ORDERS.
Return ONE JSON decision only, no markdown; no signals from future outcomes.
This is a NEW independent V3 decision policy, NOT the V2R3/V2R4 old
conservative model prompt. Scanner ranking is a sensor, never a BUY vote.

A second, INDEPENDENT SOURCE-CATALYST ENTRY PATH exists: when the verified
positive_source_trigger_for_independent_paper_entry is non-null, treat it as
a genuine candidate genesis and an actionable POSITIVE input, not mere
sentiment decoration. A verified official government decision directly
benefiting this coin, multiple independently confirmed net buys, or a
directly coin-beneficial Polymarket event confirmed by same-pair early price
movement may justify a 50 EUR initial SCOUT even BEFORE a technical breakout
or conventional volume surge, IF Kraken execution, stop and fee-adjusted
expected remaining opportunity are independently defensible. This evidence
may increase confidence and change a WAIT/REJECT to BUY_SCOUT when warranted,
but never accept vague news, generic mood, unrelated probability markets or
unverified wallet claims as a causal coin catalyst. No source is a direct
buy instruction; explain SOURCE_CATALYST in reason_codes when decisive.
Missing optional sources must not block an otherwise legitimate technical
opportunity. Never infer a coin-specific causal link from a headline alone.

Evaluate a fresh first-stage 50 EUR SCOUT RIGHT NOW if the closed real Kraken
1m/5m/15m structure, relative price/volume, fresh ask/spread and structural
ATR/8-bar invalidation make the stop and net expected move acceptable.
Do NOT require an extra post-signal 15m confirmation, a previously triggered
WAIT, a guaranteed catalyst, or already achieved Stage2 momentum for SCOUT.
A later independently observable confirmation trigger ABOVE current ask is
required for the separate 50 EUR Stage2 (1..60 minute TTL) and must be
recorded as a PLAN, not as an immediate completed buy.

Classify IGNITION, CONTINUITY, REVERSAL, EXTENDED, NONE independently. A
genuinely fresh 1-3h base after an earlier extended move may be a NEW setup,
while a price simply running further without a base still carries chase risk.
Strong 7d/30d appreciation, an old resistance, generalized major-market
caution and absent news/onchain/derivative source are NOT standalone hard
vetoes. Consider negative market/regime evidence in risk sizing/expected move,
but do not turn missing optional inputs into hard REJECTs. No universal
5m relative-volume 1.2 hard veto for initial SCOUT evaluation: reason about
reliability and available actual volume/price evidence, including valid zero.

If FULL source data are absent or stop/Stage2 cannot be expressed with
current Kraken prices: do not fabricate them. WAIT requires an executable
1..6 watch_conditions with metric/op/value, TTL 1..60 and a clear followup
thesis. A temporary current-price problem or an old WAIT expiry does NOT mean
the coin can never be reviewed again on genuinely fresh closed data. Use
REJECT only for an economically or structurally invalid present setup;
clearly identify which hard execution/risk constraint failed.

BUY_SCOUT requires stop_eur (0<stop<ask), stage2_trigger_eur > ask,
stage2_ttl_minutes in 1..60, anti_chase_passed true, defensible positive
expected_remaining_move_pct AFTER considering 0.60% taker each side,
spread/slippage, downside risk and model uncertainty. No auto BUY from this
prompt: shared V3 P4 checks and an isolated Paper writer must validate first.
No leverage, Kraken public online Spot EUR only.

Return JSON with: candidate_id, pair, decision_at_utc, decision
(BUY_SCOUT|WAIT|REJECT), setup_lane (IGNITION|CONTINUITY|EXTENDED|REVERSAL|NONE),
reason_codes (strings), anti_chase_passed (boolean), stop_eur (number or null),
expected_remaining_move_pct (number or null), stage2_trigger_eur (number or
null), stage2_ttl_minutes (integer 0..60), ttl_minutes (integer 0..60),
watch_conditions (0..6 exact metric/op/value objects). For WAIT use only
last_eur, bid_eur, ask_eur, spread_pct, closed_1m_close_eur,
closed_1m_volume_ratio_5, closed_5m_close_eur,
closed_5m_volume_ratio_5, closed_15m_close_eur,
closed_15m_volume_ratio_4 and operators > >= < <=. For BUY/REJECT watch
conditions empty. Record economic veto reasons separately from missing data.
"""
    return intro+"\nVERIFIED DECISION INPUT:\n"+json.dumps(
        data,sort_keys=True,separators=(",",":"),allow_nan=False)
