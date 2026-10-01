create or replace view public.v2r3_revalidation_timing_summary
with (security_invoker = true)
as
with base as (
  select
    p.series_id,
    p.candidate_id,
    p.decision as final_decision,
    p.evaluated_at,
    nullif(p.payload #>> '{decision,decision,decision}','') as initial_decision,
    nullif(p.payload #>> '{revalidation,decision,decision}','') as revalidation_decision,
    nullif(p.payload #>> '{revalidation,revalidated_at_utc}','')::timestamptz as revalidated_at
  from public.paper_candidate_outcomes p
  join public.paper_series s using (series_id)
  where s.strategy_revision = 'V2R3-2026-09-28'
),
timed as (
  select
    *,
    extract(epoch from (revalidated_at - evaluated_at))::numeric as eval_to_revalidation_seconds
  from base
  where revalidated_at is not null
)
select
  series_id,
  count(*)::integer as revalidated_candidates,
  count(*) filter (where revalidation_decision is distinct from initial_decision)::integer as decision_changes,
  round(percentile_cont(0.5) within group (order by eval_to_revalidation_seconds::double precision)::numeric,3) as p50_eval_to_revalidation_seconds,
  round(percentile_cont(0.9) within group (order by eval_to_revalidation_seconds::double precision)::numeric,3) as p90_eval_to_revalidation_seconds,
  round(percentile_cont(0.99) within group (order by eval_to_revalidation_seconds::double precision)::numeric,3) as p99_eval_to_revalidation_seconds,
  round(max(eval_to_revalidation_seconds),3) as max_eval_to_revalidation_seconds,
  count(*) filter (where eval_to_revalidation_seconds > 600)::integer as over_10m,
  count(*) filter (where eval_to_revalidation_seconds > 1200)::integer as over_20m,
  count(*) filter (where eval_to_revalidation_seconds > 1800)::integer as over_30m,
  'Timing/operations diagnostic only. Revalidation latency is not strategy-performance evidence and must not be used to tune the active clean series before its completion gate.'::text as interpretation_guardrail
from timed
group by series_id;
