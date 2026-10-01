create or replace view public.v2r3_release_review_snapshot
with (security_invoker = true)
as
with ready as (
  select *
  from public.paper_series_completion_readiness
  limit 1
),
integrity as (
  select *
  from public.v2r3_clean_integrity_summary
  limit 1
),
timing as (
  select coalesce(jsonb_agg(to_jsonb(t) order by t.decision), '[]'::jsonb) as rows
  from public.v2r3_runtime_timing_summary t
  join ready r on r.series_id = t.series_id
),
revalidation as (
  select to_jsonb(x) as row
  from public.v2r3_revalidation_timing_summary x
  join ready r on r.series_id = x.series_id
),
outcomes as (
  select coalesce(jsonb_agg(to_jsonb(o) order by o.decision), '[]'::jsonb) as rows
  from public.v2r3_outcome_summary o
  join ready r on r.series_id = o.series_id
),
interim as (
  select coalesce(jsonb_agg(to_jsonb(i) order by i.decision), '[]'::jsonb) as rows
  from public.v2r3_interim_horizon_summary i
  join ready r on r.series_id = i.series_id
),
reason_families as (
  select coalesce(jsonb_agg(to_jsonb(z) order by z.reason_instances desc, z.decision, z.reason_family, z.reason_polarity), '[]'::jsonb) as rows
  from (
    select f.*
    from public.v2r3_reason_family_rollup f
    join ready r on r.series_id = f.series_id
    order by f.reason_instances desc, f.decision, f.reason_family, f.reason_polarity
    limit 100
  ) z
),
missed_moves as (
  select coalesce(jsonb_agg(to_jsonb(z) order by z.mfe_24h_pct desc nulls last, z.evaluated_at), '[]'::jsonb) as rows
  from (
    select m.*
    from public.v2r3_missed_move_candidates m
    join ready r on r.series_id = m.series_id
    where m.mature_24h is true
    order by m.mfe_24h_pct desc nulls last, m.evaluated_at
    limit 100
  ) z
),
activation as (
  select *
  from public.v2r4_activation_readiness
  limit 1
)
select
  now() as generated_at,
  r.series_id,
  r.test_id,
  r.strategy_revision,
  r.started_at,
  r.series_age_days,
  r.target_completed_trades,
  r.candidate_outcomes,
  r.completed_trades,
  r.eligible_24h,
  r.complete_24h,
  r.coverage_24h_pct,
  r.gate_state,
  r.completion_ready,
  i.integrity_state,
  i.duplicate_candidate_ids,
  i.duplicated_queue_ids,
  i.distinct_strategy_fingerprints,
  i.distinct_runtime_fingerprints,
  case
    when coalesce(r.completion_ready,false) is not true then 'WAITING_COMPLETION'
    when coalesce(i.integrity_state,'') <> 'HEALTHY' then 'BLOCKED_INTEGRITY'
    else 'READY_FOR_FINAL_REVIEW'
  end as review_state,
  (
    coalesce(r.completion_ready,false) is true
    and coalesce(i.integrity_state,'') = 'HEALTHY'
  ) as final_review_allowed,
  t.rows as runtime_timing,
  rv.row as revalidation_timing,
  o.rows as outcome_summary,
  h.rows as interim_horizons,
  f.rows as reason_family_rollup,
  mm.rows as mature_missed_move_candidates,
  to_jsonb(a) as v2r4_activation_control,
  false as automatic_strategy_change_allowed,
  'Single-row read-only evidence pack. final_review_allowed only means the documented V2R3 evidence review may begin; it does not authorize V2R4 activation, rule changes, or real-money trading.'::text as interpretation_guardrail
from ready r
cross join integrity i
cross join timing t
left join revalidation rv on true
cross join outcomes o
cross join interim h
cross join reason_families f
cross join missed_moves mm
left join activation a on true;
