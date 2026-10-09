#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "research/v3/h10-kraken-outcome-context-join-contract-v1.json"
c = json.loads(P.read_text(encoding="utf-8"))

assert c["kind"] == "V3_H10_KRAKEN_OUTCOME_CONTEXT_JOIN_CONTRACT_V1"
assert c["status"] == "FROZEN_PREREGISTERED_INACTIVE"
assert c["authorities"]["cohort"] == "research/v3/h10-trader-cohort-v1.json"
assert c["fixed_input_population"]["primary_wallets"] == 20
assert c["fixed_input_population"]["active_controls"] == 6
assert c["fixed_input_population"]["wallet_reselection_allowed"] is False
assert c["point_in_time_join"]["symbol_mapping"]["future_mapping_forbidden"] is True
assert c["point_in_time_join"]["outcome_horizons_minutes"] == [15, 60, 180, 360, 1440]
assert c["cost_and_outcome_model"]["notional_eur"] == 50
assert c["cost_and_outcome_model"]["taker_fee_pct_per_fill"] == 0.60
assert c["cost_and_outcome_model"]["round_trip_fee_pct"] == 1.20
assert c["cost_and_outcome_model"]["no_fill_claim"] is True
assert c["frozen_false_positive_label"]["name"] == "H10_FALSE_POSITIVE_AFTER_COST_6H_V1"
assert c["frozen_false_positive_label"]["threshold_search_allowed"] is False
g = c["fixed_review_gate"]
assert g["min_eligible_events_total"] == 50
assert g["min_primary_events"] + g["min_control_events"] == g["min_eligible_events_total"]
assert g["all_events_require_complete_24h"] is True
assert g["automatic_extension"] is False
assert g["automatic_promotion"] is False
h = c["holdout_and_search_controls"]
assert h["freeze_before_outcome_query"] is True
assert h["no_wallet_asset_horizon_threshold_or_label_reselection"] is True
s = c["safety"]
for key in ("capture_change","scheduler_change","strategy_coupling","v2r4_change","h3_change","orders","copy_trading","real_money_actions","automatic_release"):
    assert s[key] is False, key
print("H10_KRAKEN_OUTCOME_CONTEXT_JOIN_CONTRACT_PASS")
