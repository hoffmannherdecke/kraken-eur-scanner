-- Single-pass series-scoped model-usage guard.
-- Retains original output columns, anomaly rules, security_invoker and no budget authority.
-- The BASE row counts each outcome once; invocation rows are emitted only for
-- nonempty response IDs, exactly matching paper_model_invocation_events.
create or replace view public.paper_model_usage_guard
with (security_invoker=true)
as
with agg as (
  select
    p.series_id,
    count(*) filter (where v.phase = 'BASE')::bigint as candidate_outcomes,
    count(*) filter (
      where v.phase = 'BASE'
        and p.payload #>> '{decision,decision,decision}' = 'WAIT'
    )::bigint as initial_wait_decisions,
    count(*) filter (
      where v.phase = 'BASE'
        and nullif(p.payload #>> '{revalidation,evaluator,response_id}', '') is not null
        and nullif(p.payload #>> '{decision,evaluator,response_id}', '') is null
    )::bigint as revalidation_without_initial_model,
    count(*) filter (where v.phase <> 'BASE')::bigint as logical_model_calls,
    count(*) filter (where v.phase = 'INITIAL')::bigint as initial_model_calls,
    count(*) filter (where v.phase = 'REVALIDATION')::bigint as revalidation_model_calls,
    sum(greatest(coalesce(v.attempt,1),1)) filter (where v.phase <> 'BASE')::bigint
      as estimated_http_attempts,
    sum(greatest(coalesce(v.attempt,1),1)-1) filter (where v.phase <> 'BASE')::bigint
      as retry_overhead_requests,
    count(*) filter (where v.phase <> 'BASE' and coalesce(v.attempt,1)>1)::bigint
      as retried_logical_calls,
    max(coalesce(v.attempt,1)) filter (where v.phase <> 'BASE')::integer as max_attempt,
    count(distinct v.response_id)::bigint as distinct_response_ids,
    array_agg(distinct v.model order by v.model)
      filter (where v.phase <> 'BASE' and v.model is not null) as models
  from public.paper_candidate_outcomes p
  cross join lateral (values
    ('BASE'::text, null::text, null::text, null::integer),
    (
      'INITIAL',
      nullif(p.payload #>> '{decision,evaluator,response_id}', ''),
      p.payload #>> '{decision,evaluator,model}',
      case
        when (p.payload #>> '{decision,evaluator,attempt}') ~ '^[0-9]+$'
          then (p.payload #>> '{decision,evaluator,attempt}')::integer
        else null
      end
    ),
    (
      'REVALIDATION',
      nullif(p.payload #>> '{revalidation,evaluator,response_id}', ''),
      p.payload #>> '{revalidation,evaluator,model}',
      case
        when (p.payload #>> '{revalidation,evaluator,attempt}') ~ '^[0-9]+$'
          then (p.payload #>> '{revalidation,evaluator,attempt}')::integer
        else null
      end
    )
  ) v(phase, response_id, model, attempt)
  where v.phase = 'BASE' or v.response_id is not null
  group by p.series_id
)
select
  series_id,
  candidate_outcomes,
  initial_wait_decisions,
  initial_model_calls,
  revalidation_model_calls,
  logical_model_calls,
  coalesce(estimated_http_attempts,0)::bigint as estimated_http_attempts,
  coalesce(retry_overhead_requests,0)::bigint as retry_overhead_requests,
  retried_logical_calls,
  coalesce(max_attempt,0)::integer as max_attempt,
  greatest(logical_model_calls - distinct_response_ids,0)::bigint as duplicate_response_ids,
  revalidation_without_initial_model,
  case when candidate_outcomes > 0
    then round(logical_model_calls::numeric / candidate_outcomes,4)
    else null end as logical_calls_per_outcome,
  coalesce(models, array[]::text[]) as models,
  case
    when revalidation_without_initial_model > 0 then 'ANOMALY'
    when coalesce(max_attempt,0) > 2 then 'ANOMALY'
    when revalidation_model_calls > initial_wait_decisions then 'ANOMALY'
    when logical_model_calls - distinct_response_ids > 0 then 'ANOMALY'
    when logical_model_calls > candidate_outcomes + initial_wait_decisions then 'ANOMALY'
    else 'HEALTHY'
  end as usage_state,
  'CALL_COUNT_ONLY_NO_TOKEN_OR_DOLLAR_DATA'::text as cost_precision,
  false as automatic_budget_change_allowed
from agg;
