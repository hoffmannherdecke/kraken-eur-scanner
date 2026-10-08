create or replace view public.v2r4_activation_readiness
with (security_invoker=true) as
with candidate_stats as (
  select
    count(*)::integer as candidate_outcomes,
    count(*) filter (where evaluated_at <= now() - interval '24 hours')::integer as eligible_24h,
    count(*) filter (
      where evaluated_at <= now() - interval '24 hours'
        and (
          (followup -> 'horizons') ? '1440'
          or (followup -> 'opportunity_audit' -> 'horizons') ? '1440'
        )
    )::integer as complete_24h
  from public.paper_candidate_outcomes
  where series_id = 'PAPER-V2R3-CLEAN-20261001T0925Z'
),
trade_stats as (
  select count(*) filter (where closed_at is not null)::integer as completed_trades
  from public.paper_trade_results
  where series_id = 'PAPER-V2R3-CLEAN-20261001T0925Z'
),
paper as (
  select
    ps.series_id,
    case when ps.status = 'closed_complete' then 'CLOSED_COMPLETE' else 'PREDECESSOR_NOT_CLOSED' end::text as gate_state,
    (ps.status = 'closed_complete') as completion_ready,
    cs.candidate_outcomes,
    ts.completed_trades,
    cs.eligible_24h,
    cs.complete_24h,
    case when cs.eligible_24h = 0 then null::numeric
         else round(100.0 * cs.complete_24h::numeric / cs.eligible_24h::numeric, 2) end as coverage_24h_pct,
    case when ps.status = 'closed_complete' then 0 else greatest(0,1000-cs.candidate_outcomes) end::integer as outcomes_remaining_to_alt_gate,
    case when ps.status = 'closed_complete' then 0::numeric else null::numeric end as hours_remaining_to_age_gate,
    (ps.status = 'closed_complete') as intake_should_stop,
    'EVIDENCE_DIVERSITY_FASTTRACK_V2'::text as fasttrack_policy_version,
    (
      ps.status = 'closed_complete'
      and cs.candidate_outcomes >= 1000
      and cs.eligible_24h >= 950
      and cs.complete_24h >= 950
      and (cs.eligible_24h = 0 or 100.0 * cs.complete_24h::numeric / cs.eligible_24h::numeric >= 95.0)
    ) as qualifying_maturity_ready
  from public.paper_series ps
  cross join candidate_stats cs
  cross join trade_stats ts
  where ps.series_id = 'PAPER-V2R3-CLEAN-20261001T0925Z'
),
shadow as (
  select * from public.v2r4_shadow_completion_readiness limit 1
),
integrity as (
  select * from public.v2r3_clean_integrity_summary limit 1
),
minipc as (
  select observed_at,status,payload ->> 'health_state' as health_state
  from public.minipc_status_current
  where node_id='MINI-PC'
  limit 1
),
release_decision as (
  select release_id,predecessor_series_id,successor_revision,status,decided_at,decision_evidence,
         updated_at,final_review_completed_at,migration_review_completed_at
  from public.strategy_release_decisions
  where release_id='V2R3_TO_V2R4_20261005'
  limit 1
),
successor as (
  select ps.series_id,ps.status,ps.strategy_revision
  from public.paper_series ps
  cross join release_decision rd
  where ps.series_id = rd.decision_evidence ->> 'activation_series_id'
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
  round(paper.hours_remaining_to_age_gate,2) as v2r3_hours_remaining_to_age_gate,
  shadow.readiness_state as v2r4_shadow_readiness_state,
  shadow.prospective_events as v2r4_shadow_prospective_events,
  shadow.due_6h as v2r4_shadow_due_6h,
  shadow.completed_due_6h as v2r4_shadow_completed_due_6h,
  shadow.unresolved_due_6h as v2r4_shadow_unresolved_due_6h,
  shadow.complete_6h_coverage_pct as v2r4_shadow_complete_6h_coverage_pct,
  minipc.observed_at as minipc_observed_at,
  round(extract(epoch from (now()-minipc.observed_at))/60.0,2) as minipc_status_age_minutes,
  minipc.status as minipc_status,
  minipc.health_state as minipc_health_state,
  false as automatic_activation_allowed,
  case
    when successor.series_id is not null
      and successor.status='active'
      and release_decision.status='APPROVED_PAPER'
      and successor.strategy_revision like 'V2R4%'
      then 'PAPER_RELEASE_ALREADY_ACTIVATED'
    when coalesce(paper.completion_ready,false) is not true then 'BLOCKED_V2R3_COMPLETION'
    when coalesce(integrity.integrity_state,'') <> 'HEALTHY' then 'BLOCKED_V2R3_INTEGRITY'
    when coalesce(shadow.readiness_state,'') not in ('MATURE_COHORT_ARCHIVED','MATURE_OUTCOMES_PENDING')
      then 'BLOCKED_V2R4_SHADOW_MATURITY'
    when minipc.observed_at is null
      or minipc.observed_at < now()-interval '20 minutes'
      or coalesce(minipc.status,'') <> 'HEALTHY'
      or coalesce(minipc.health_state,'') <> 'OK'
      then 'BLOCKED_MINIPC_HEALTH'
    when release_decision.final_review_completed_at is null then 'MANUAL_V2R3_FINAL_REVIEW_REQUIRED'
    when release_decision.migration_review_completed_at is null then 'MANUAL_MIGRATION_REVIEW_REQUIRED'
    when coalesce(release_decision.status,'PENDING') <> 'APPROVED_PAPER' then 'MANUAL_RELEASE_DECISION_REQUIRED'
    else 'PAPER_RELEASE_APPROVED_NOT_AUTOMATICALLY_ACTIVATED'
  end as activation_review_state,
  'Post-activation-safe control view. V2R3 evidence is pinned to PAPER-V2R3-CLEAN-20261001T0925Z and can never follow the current active series. Once the approved successor series is active, the completed V2R3 release gate is treated as closed history and is never reopened. This view never activates a strategy automatically.'::text as interpretation_guardrail,
  integrity.integrity_state as v2r3_integrity_state,
  integrity.duplicate_candidate_ids as v2r3_duplicate_candidate_ids,
  integrity.duplicated_queue_ids as v2r3_duplicated_queue_ids,
  integrity.distinct_strategy_fingerprints as v2r3_strategy_fingerprints,
  integrity.distinct_runtime_fingerprints as v2r3_runtime_fingerprints,
  paper.intake_should_stop as v2r3_intake_should_stop,
  paper.fasttrack_policy_version,
  paper.qualifying_maturity_ready as v2r3_qualifying_maturity_ready,
  case
    when release_decision.final_review_completed_at is not null then 'FINAL_REVIEW_COMPLETE'
    when coalesce(paper.completion_ready,false) is not true then 'WAITING_COMPLETION'
    when coalesce(integrity.integrity_state,'') <> 'HEALTHY' then 'BLOCKED_INTEGRITY'
    else 'READY_FOR_FINAL_REVIEW'
  end as v2r3_final_review_state,
  (coalesce(paper.completion_ready,false) is true and coalesce(integrity.integrity_state,'')='HEALTHY') as v2r3_final_review_allowed,
  release_decision.status as explicit_release_decision_status,
  release_decision.decided_at as explicit_release_decided_at,
  release_decision.final_review_completed_at,
  release_decision.migration_review_completed_at
from paper
cross join shadow
cross join integrity
cross join release_decision
left join minipc on true
left join successor on true;
