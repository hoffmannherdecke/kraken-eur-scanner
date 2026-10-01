create or replace view public.v3_timing_evidence_snapshot
with (security_invoker=true)
as
with active as (
  select series_id
  from public.paper_series_completion_readiness
  limit 1
),
v2r3_runtime as (
  select coalesce(jsonb_agg(to_jsonb(t) order by t.decision), '[]'::jsonb) as rows
  from public.v2r3_runtime_timing_summary t
  join active a using (series_id)
),
v2r3_revalidation as (
  select to_jsonb(t) as row
  from public.v2r3_revalidation_timing_summary t
  join active a using (series_id)
),
path_compare as (
  select to_jsonb(t) as row
  from public.realtime_path_comparison_readiness t
  limit 1
),
shadow as (
  select to_jsonb(t) as row
  from public.v2r4_shadow_completion_readiness t
  limit 1
)
select
  now() as generated_at,
  a.series_id as v2r3_series_id,
  rt.rows as v2r3_runtime_timing,
  rv.row as v2r3_revalidation_timing,
  pc.row as realtime_path_comparison,
  sh.row as v2r4_shadow_readiness,
  coalesce((pc.row->>'scanner_comparison_state'),'UNAVAILABLE') as scanner_comparison_state,
  coalesce((pc.row->>'altrady_comparison_state'),'UNAVAILABLE') as altrady_comparison_state,
  coalesce((pc.row->>'ranking_allowed')::boolean,false) as path_ranking_allowed,
  case
    when pc.row is null then 'WAITING_PATH_EVIDENCE'
    when coalesce((pc.row->>'ranking_allowed')::boolean,false) is false
      then 'COLLECTING_COMPARABLE_TIMING_EVIDENCE'
    else 'COMPARATIVE_TIMING_REVIEW_ALLOWED'
  end as timing_evidence_state,
  true as infrastructure_variant_before_rule_relaxation,
  false as automatic_entry_rule_change_allowed,
  false as automatic_strategy_promotion_allowed,
  'V3 timing evidence only. Separate scanner/evaluator/revalidation/transport/feed delays from strategy-filter effects. When timing remains a plausible cause, test the infrastructure/timing variant before relaxing entry rules. No path ranking or strategy change is allowed unless the underlying comparison gate itself is mature.'::text as interpretation_guardrail
from active a
cross join v2r3_runtime rt
left join v2r3_revalidation rv on true
left join path_compare pc on true
left join shadow sh on true;
