create or replace view public.paper_model_usage_guard
with (security_invoker=true)
as
with base as (
  select
    series_id,
    count(*)::bigint as candidate_outcomes,
    count(*) filter (
      where payload #>> '{decision,decision,decision}' = 'WAIT'
    )::bigint as initial_wait_decisions,
    count(*) filter (
      where nullif(payload #>> '{revalidation,evaluator,response_id}', '') is not null
        and nullif(payload #>> '{decision,evaluator,response_id}', '') is null
    )::bigint as revalidation_without_initial_model
  from public.paper_candidate_outcomes
  group by series_id
),
inv as (
  select
    series_id,
    count(*)::bigint as logical_model_calls,
    count(*) filter (where invocation_phase='INITIAL')::bigint as initial_model_calls,
    count(*) filter (where invocation_phase='REVALIDATION')::bigint as revalidation_model_calls,
    sum(greatest(coalesce(attempt,1),1))::bigint as estimated_http_attempts,
    sum(greatest(coalesce(attempt,1),1)-1)::bigint as retry_overhead_requests,
    count(*) filter (where coalesce(attempt,1)>1)::bigint as retried_logical_calls,
    max(coalesce(attempt,1))::integer as max_attempt,
    count(distinct response_id)::bigint as distinct_response_ids,
    array_agg(distinct model order by model) filter (where model is not null) as models
  from public.paper_model_invocation_events
  group by series_id
)
select
  b.series_id,
  b.candidate_outcomes,
  b.initial_wait_decisions,
  coalesce(i.initial_model_calls,0)::bigint as initial_model_calls,
  coalesce(i.revalidation_model_calls,0)::bigint as revalidation_model_calls,
  coalesce(i.logical_model_calls,0)::bigint as logical_model_calls,
  coalesce(i.estimated_http_attempts,0)::bigint as estimated_http_attempts,
  coalesce(i.retry_overhead_requests,0)::bigint as retry_overhead_requests,
  coalesce(i.retried_logical_calls,0)::bigint as retried_logical_calls,
  coalesce(i.max_attempt,0)::integer as max_attempt,
  greatest(
    coalesce(i.logical_model_calls,0) - coalesce(i.distinct_response_ids,0),
    0
  )::bigint as duplicate_response_ids,
  b.revalidation_without_initial_model,
  case
    when b.candidate_outcomes > 0
      then round(coalesce(i.logical_model_calls,0)::numeric / b.candidate_outcomes, 4)
    else null
  end as logical_calls_per_outcome,
  coalesce(i.models, array[]::text[]) as models,
  case
    when b.revalidation_without_initial_model > 0 then 'ANOMALY'
    when coalesce(i.max_attempt,0) > 2 then 'ANOMALY'
    when coalesce(i.revalidation_model_calls,0) > b.initial_wait_decisions then 'ANOMALY'
    when coalesce(i.logical_model_calls,0) - coalesce(i.distinct_response_ids,0) > 0 then 'ANOMALY'
    when coalesce(i.logical_model_calls,0) > b.candidate_outcomes + b.initial_wait_decisions then 'ANOMALY'
    else 'HEALTHY'
  end as usage_state,
  'CALL_COUNT_ONLY_NO_TOKEN_OR_DOLLAR_DATA'::text as cost_precision,
  false as automatic_budget_change_allowed
from base b
left join inv i using (series_id);
