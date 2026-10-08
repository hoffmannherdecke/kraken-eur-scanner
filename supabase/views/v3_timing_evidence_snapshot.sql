create or replace view public.v3_timing_evidence_snapshot
with (security_invoker=true) as
with predecessor as (
  select predecessor_series_id as series_id
  from public.strategy_release_decisions
  where release_id='V2R3_TO_V2R4_20261005'
  limit 1
),
v2r3_runtime as (
  select coalesce(jsonb_agg(to_jsonb(t) order by t.decision),'[]'::jsonb) as rows
  from public.v2r3_runtime_timing_summary t join predecessor p using(series_id)
),
v2r3_revalidation as (
  select to_jsonb(t) as row
  from public.v2r3_revalidation_timing_summary t join predecessor p using(series_id)
),
path_compare as (
  select to_jsonb(t) as row from public.realtime_path_comparison_readiness t limit 1
),
shadow as (
  select to_jsonb(t) as row from public.v2r4_shadow_completion_readiness t limit 1
)
select
  now() as generated_at,
  p.series_id as v2r3_series_id,
  rt.rows as v2r3_runtime_timing,
  rv.row as v2r3_revalidation_timing,
  pc.row as realtime_path_comparison,
  sh.row as v2r4_shadow_readiness,
  coalesce(pc.row->>'scanner_comparison_state','UNAVAILABLE') as scanner_comparison_state,
  coalesce(pc.row->>'altrady_comparison_state','UNAVAILABLE') as altrady_comparison_state,
  coalesce((pc.row->>'ranking_allowed')::boolean,false) as path_ranking_allowed,
  case
    when pc.row is null then 'WAITING_PATH_EVIDENCE'
    when coalesce((pc.row->>'ranking_allowed')::boolean,false) is false then 'COLLECTING_COMPARABLE_TIMING_EVIDENCE'
    else 'COMPARATIVE_TIMING_REVIEW_ALLOWED'
  end as timing_evidence_state,
  true as infrastructure_variant_before_rule_relaxation,
  false as automatic_entry_rule_change_allowed,
  false as automatic_strategy_promotion_allowed,
  'V3 timing evidence is anchored to the frozen V2R3 predecessor from the release decision, never to whichever Paper series is currently active. Timing evidence is observational only and cannot change entry rules or promote a strategy automatically.'::text as interpretation_guardrail
from predecessor p
cross join v2r3_runtime rt
left join v2r3_revalidation rv on true
left join path_compare pc on true
left join shadow sh on true;
