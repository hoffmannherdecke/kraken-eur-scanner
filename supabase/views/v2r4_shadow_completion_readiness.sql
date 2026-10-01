-- Read-only operational readiness view for the prospective V2R4 WS-shadow evidence.
-- This does not change strategy/runtime behavior and does not infer performance.
-- It answers only whether time-matured shadow events have corresponding archived outcomes.

create or replace view public.v2r4_shadow_completion_readiness as
with base as (
    select
        count(*)::integer as events_total,
        min(observed_at) as first_event_at,
        max(observed_at) as last_event_at,
        count(*) filter (where observed_at <= now() - interval '5 minutes')::integer as due_5m,
        count(*) filter (where observed_at <= now() - interval '15 minutes')::integer as due_15m,
        count(*) filter (where observed_at <= now() - interval '30 minutes')::integer as due_30m,
        count(*) filter (where observed_at <= now() - interval '1 hour')::integer as due_1h,
        count(*) filter (where observed_at <= now() - interval '3 hours')::integer as due_3h,
        count(*) filter (where observed_at <= now() - interval '6 hours')::integer as due_6h,
        count(*) filter (where outcome_status = 'COMPLETE')::integer as completed_total,
        count(*) filter (where outcome_status = 'INCOMPLETE_TIMEOUT')::integer as incomplete_timeout_total,
        count(*) filter (
            where observed_at <= now() - interval '6 hours'
              and outcome_status = 'COMPLETE'
        )::integer as completed_due_6h,
        count(*) filter (
            where observed_at <= now() - interval '6 hours'
              and outcome_status = 'INCOMPLETE_TIMEOUT'
        )::integer as incomplete_timeout_due_6h,
        count(distinct source_runtime_commit)::integer as runtime_commits
    from public.v2r4_shadow_evidence
)
select
    now() as generated_at,
    events_total,
    first_event_at,
    last_event_at,
    case when first_event_at is null then null else first_event_at + interval '6 hours' end as first_6h_maturity_at,
    due_5m,
    due_15m,
    due_30m,
    due_1h,
    due_3h,
    due_6h,
    completed_total,
    completed_due_6h,
    incomplete_timeout_total,
    incomplete_timeout_due_6h,
    greatest(due_6h - completed_due_6h - incomplete_timeout_due_6h, 0)::integer as unresolved_due_6h,
    case
        when due_6h = 0 then null
        else round(100.0 * completed_due_6h / nullif(due_6h, 0), 2)
    end as complete_6h_coverage_pct,
    runtime_commits,
    case
        when events_total = 0 then 'WAITING_NO_EVENTS'
        when due_6h = 0 then 'COLLECTING_AGE'
        when (completed_due_6h + incomplete_timeout_due_6h) = due_6h then 'MATURE_COHORT_ARCHIVED'
        else 'MATURE_OUTCOMES_PENDING'
    end as readiness_state,
    'Operational maturity/archival view only. Do not interpret as strategy-performance evidence.'::text
        as interpretation_guardrail
from base;
