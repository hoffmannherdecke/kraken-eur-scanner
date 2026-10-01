-- Read-only operational readiness view for the prospective V2R4 WS-shadow evidence.
-- This does not change strategy/runtime behavior and does not infer performance.
-- It answers only whether time-matured, outcome-eligible shadow events have
-- corresponding archived outcomes.
--
-- The outcome tracker was activated after exactly 18 older events had already
-- been created. The last deliberately ignored pre-tracker event was observed at
-- 2026-10-01T06:52:12.838Z. Events after this boundary are prospective/eligible.

create or replace view public.v2r4_shadow_completion_readiness with (security_invoker=true) as
with params as (
    select timestamptz '2026-10-01 06:52:12.838+00' as tracker_eligibility_after
),
eligible as (
    select e.*
    from public.v2r4_shadow_evidence e
    cross join params p
    where e.observed_at > p.tracker_eligibility_after
),
base as (
    select
        (select count(*)::integer from public.v2r4_shadow_evidence) as events_total,
        (select count(*)::integer
           from public.v2r4_shadow_evidence e
           cross join params p
          where e.observed_at <= p.tracker_eligibility_after) as pretracker_events,
        count(*)::integer as prospective_events,
        min(observed_at) as first_prospective_event_at,
        max(observed_at) as last_prospective_event_at,
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
    from eligible
)
select
    now() as generated_at,
    p.tracker_eligibility_after,
    events_total,
    pretracker_events,
    prospective_events,
    first_prospective_event_at,
    last_prospective_event_at,
    case
        when first_prospective_event_at is null then null
        else first_prospective_event_at + interval '6 hours'
    end as first_6h_maturity_at,
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
        when prospective_events = 0 then 'WAITING_NO_PROSPECTIVE_EVENTS'
        when due_6h = 0 then 'COLLECTING_AGE'
        when (completed_due_6h + incomplete_timeout_due_6h) = due_6h then 'MATURE_COHORT_ARCHIVED'
        else 'MATURE_OUTCOMES_PENDING'
    end as readiness_state,
    'Operational maturity/archival view only. Pre-tracker events are excluded. Do not interpret as strategy-performance evidence.'::text
        as interpretation_guardrail
from base
cross join params p;
