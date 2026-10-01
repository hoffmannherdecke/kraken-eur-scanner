create or replace view public.paper_model_invocation_events
with (security_invoker=true)
as
select
  p.candidate_id,
  p.series_id,
  p.pair,
  'INITIAL'::text as invocation_phase,
  coalesce(
    nullif(p.payload #>> '{decision,evaluated_at_utc}', '')::timestamptz,
    p.evaluated_at
  ) as invoked_at,
  p.payload #>> '{decision,evaluator,model}' as model,
  p.payload #>> '{decision,evaluator,response_id}' as response_id,
  case
    when (p.payload #>> '{decision,evaluator,attempt}') ~ '^[0-9]+$'
      then (p.payload #>> '{decision,evaluator,attempt}')::integer
    else null
  end as attempt,
  p.payload #>> '{decision,decision,decision}' as resulting_decision
from public.paper_candidate_outcomes p
where nullif(p.payload #>> '{decision,evaluator,response_id}', '') is not null

union all

select
  p.candidate_id,
  p.series_id,
  p.pair,
  'REVALIDATION'::text as invocation_phase,
  nullif(p.payload #>> '{revalidation,revalidated_at_utc}', '')::timestamptz as invoked_at,
  p.payload #>> '{revalidation,evaluator,model}' as model,
  p.payload #>> '{revalidation,evaluator,response_id}' as response_id,
  case
    when (p.payload #>> '{revalidation,evaluator,attempt}') ~ '^[0-9]+$'
      then (p.payload #>> '{revalidation,evaluator,attempt}')::integer
    else null
  end as attempt,
  p.payload #>> '{revalidation,decision,decision}' as resulting_decision
from public.paper_candidate_outcomes p
where nullif(p.payload #>> '{revalidation,evaluator,response_id}', '') is not null;
