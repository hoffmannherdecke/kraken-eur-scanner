create or replace view public.v2r4_activation_readiness
with (security_invoker=true) as
with paper as (
  select *
  from public.paper_series_completion_readiness
  limit 1
),
shadow as (
  select *
  from public.v2r4_shadow_completion_readiness
  limit 1
),
integrity as (
  select *
  from public.v2r3_clean_integrity_summary
  limit 1
),
minipc as (
  select
    observed_at,
    status,
    payload ->> 'health_state' as health_state
  from public.minipc_status_current
  where node_id = 'MINI-PC'
  limit 1
)
select
  now() as generated_at,

  paper.series_id as v2r3_series_id,
  paper.gate_state as v2r3_gate_state,
  paper.completion_ready as v2r3_completion_ready,
  paper.candidate_outcomes as v2r3_candidate_outcomes,
  paper.completed_trades as v2r3_completed_trades,
  paper.eligible_24h as v2r3_eligible_24h,
  paper.complete_24h as v2r3_complete_24h,
  paper.coverage_24h_pct as v2r3_coverage_24h_pct,
  paper.outcomes_remaining_to_alt_gate as v2r3_outcomes_remaining,
  round(paper.hours_remaining_to_age_gate, 2) as v2r3_hours_remaining_to_age_gate,

  shadow.readiness_state as v2r4_shadow_readiness_state,
  shadow.prospective_events as v2r4_shadow_prospective_events,
  shadow.due_6h as v2r4_shadow_due_6h,
  shadow.completed_due_6h as v2r4_shadow_completed_due_6h,
  shadow.unresolved_due_6h as v2r4_shadow_unresolved_due_6h,
  shadow.complete_6h_coverage_pct as v2r4_shadow_complete_6h_coverage_pct,

  minipc.observed_at as minipc_observed_at,
  round(extract(epoch from (now() - minipc.observed_at)) / 60.0, 2) as minipc_status_age_minutes,
  minipc.status as minipc_status,
  minipc.health_state as minipc_health_state,

  false as automatic_activation_allowed,

  case
    when coalesce(paper.completion_ready, false) is not true
      then 'BLOCKED_V2R3_COMPLETION'
    when coalesce(integrity.integrity_state, '') <> 'HEALTHY'
      then 'BLOCKED_V2R3_INTEGRITY'
    when coalesce(shadow.readiness_state, '') <> 'MATURE_COHORT_ARCHIVED'
      then 'BLOCKED_V2R4_SHADOW_MATURITY'
    when minipc.observed_at is null
      or minipc.observed_at < now() - interval '20 minutes'
      or coalesce(minipc.status, '') <> 'HEALTHY'
      or coalesce(minipc.health_state, '') <> 'OK'
      then 'BLOCKED_MINIPC_HEALTH'
    else 'MANUAL_RELEASE_REVIEW_REQUIRED'
  end as activation_review_state,

  'Readiness/control view only. It can block activation but can never authorize activation automatically. V2R4 remains paper-only until the documented V2R3 review is completed and a separate explicit manual release decision is made.'::text as interpretation_guardrail,

  integrity.integrity_state as v2r3_integrity_state,
  integrity.duplicate_candidate_ids as v2r3_duplicate_candidate_ids,
  integrity.duplicated_queue_ids as v2r3_duplicated_queue_ids,
  integrity.distinct_strategy_fingerprints as v2r3_strategy_fingerprints,
  integrity.distinct_runtime_fingerprints as v2r3_runtime_fingerprints
from paper
cross join shadow
cross join integrity
left join minipc on true;
