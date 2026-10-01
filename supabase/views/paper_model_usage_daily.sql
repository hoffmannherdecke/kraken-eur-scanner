create or replace view public.paper_model_usage_daily
with (security_invoker=true)
as
select
  series_id,
  (invoked_at at time zone 'UTC')::date as utc_date,
  count(*)::bigint as logical_model_calls,
  count(*) filter (where invocation_phase='INITIAL')::bigint as initial_model_calls,
  count(*) filter (where invocation_phase='REVALIDATION')::bigint as revalidation_model_calls,
  sum(greatest(coalesce(attempt,1),1))::bigint as estimated_http_attempts,
  sum(greatest(coalesce(attempt,1),1)-1)::bigint as retry_overhead_requests,
  count(*) filter (where coalesce(attempt,1)>1)::bigint as retried_logical_calls,
  array_agg(distinct model order by model) filter (where model is not null) as models
from public.paper_model_invocation_events
group by series_id, (invoked_at at time zone 'UTC')::date;
