create or replace view public.v3_h7_meta_gate_readiness
with (security_invoker=true)
as
with review as (
  select *
  from public.v2r3_release_review_snapshot
  limit 1
),
activation as (
  select *
  from public.v2r4_activation_readiness
  limit 1
)
select
  now() as generated_at,
  r.series_id,
  r.strategy_revision,
  r.candidate_outcomes,
  r.completed_trades,
  r.eligible_24h,
  r.complete_24h,
  r.coverage_24h_pct,
  r.gate_state as v2r3_gate_state,
  r.integrity_state as v2r3_integrity_state,
  r.final_review_allowed,
  coalesce(a.v2r4_shadow_readiness_state,'UNAVAILABLE') as v2r4_shadow_readiness_state,
  'NOT_FROZEN'::text as label_definition_state,
  false as meta_training_allowed,
  false as automatic_take_no_take_allowed,
  case
    when coalesce(r.final_review_allowed,false) is false then 'WAITING_V2R3_FINAL_REVIEW'
    when coalesce(r.integrity_state,'') <> 'HEALTHY' then 'BLOCKED_V2R3_INTEGRITY'
    else 'WAITING_FROZEN_LABEL_CONTRACT'
  end as readiness_state,
  'Readiness only. Meta TAKE/NO-TAKE training is blocked until V2R3 final review is mature and a separate point-in-time label/cost/split contract is frozen. No model training, feature selection, strategy change or trade action is authorized by this view.'::text as interpretation_guardrail
from review r
left join activation a on true;
