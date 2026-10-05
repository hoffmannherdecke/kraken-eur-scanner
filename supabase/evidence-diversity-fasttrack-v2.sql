-- EVIDENCE_DIVERSITY_FASTTRACK_V2
-- Effective 2026-10-05.
-- Canonical policy: docs/fasttrack-evidence-diversity-policy.md
-- Production migration: harden_fasttrack_and_internal_surfaces
--
-- This migration changes completion governance only. It does not alter V2R3 strategy,
-- scanner, entry, stop, sizing, fee, or execution mechanics.
--
-- Current production definition was applied to public.paper_series_completion_readiness
-- in Supabase on 2026-10-05. Keep dependent release views fail-closed.

create or replace view public.paper_series_completion_readiness with (security_invoker=true) as
with active as (
  select *
  from public.paper_series
  where status='active'
  order by started_at desc
  limit 1
),
ranked as (
  select p.*,
         row_number() over (
           partition by p.series_id
           order by p.evaluated_at, p.candidate_id
         ) as rn
  from public.paper_candidate_outcomes p
  join active a using (series_id)
),
all_candidates as (
  select series_id,
         count(*)::int as candidate_outcomes,
         count(*) filter (where evaluated_at <= now()-interval '24 hours')::int as eligible_24h,
         count(*) filter (
           where evaluated_at <= now()-interval '24 hours'
             and (
               (followup -> 'horizons') ? '1440'
               or ((followup -> 'opportunity_audit') -> 'horizons') ? '1440'
             )
         )::int as complete_24h
  from ranked
  group by series_id
),
qualifying as (
  select * from ranked where rn <= 1000
),
q_daily as (
  select series_id,
         (evaluated_at at time zone 'UTC')::date as day_utc,
         count(*)::int as day_count
  from qualifying
  group by series_id, (evaluated_at at time zone 'UTC')::date
),
q_rolling as (
  select series_id,
         evaluated_at,
         count(*) over (
           partition by series_id
           order by evaluated_at
           range between interval '24 hours' preceding and current row
         )::int as rolling_24h_count
  from qualifying
),
q_summary as (
  select q.series_id,
         count(*)::int as qualifying_cohort_size,
         min(q.evaluated_at) as qualifying_cohort_first_at,
         max(q.evaluated_at) as qualifying_cohort_last_at,
         round((extract(epoch from (max(q.evaluated_at)-min(q.evaluated_at)))/3600.0)::numeric,3)
           as qualifying_span_hours,
         count(distinct (q.evaluated_at at time zone 'UTC')::date)::int as qualifying_active_days,
         count(*) filter (where q.evaluated_at <= now()-interval '24 hours')::int
           as qualifying_eligible_24h,
         count(*) filter (
           where q.evaluated_at <= now()-interval '24 hours'
             and (
               (q.followup -> 'horizons') ? '1440'
               or ((q.followup -> 'opportunity_audit') -> 'horizons') ? '1440'
             )
         )::int as qualifying_complete_24h
  from qualifying q
  group by q.series_id
),
q_concentration as (
  select qs.series_id,
         round(
           100.0 * coalesce((select max(d.day_count) from q_daily d where d.series_id=qs.series_id),0)
           / nullif(qs.qualifying_cohort_size,0), 2
         ) as qualifying_max_single_day_share_pct,
         round(
           100.0 * coalesce((select max(r.rolling_24h_count) from q_rolling r where r.series_id=qs.series_id),0)
           / nullif(qs.qualifying_cohort_size,0), 2
         ) as qualifying_max_rolling_24h_share_pct
  from q_summary qs
),
trades as (
  select r.series_id,
         count(*)::int as trade_results,
         count(*) filter (where r.closed_at is not null)::int as completed_trades
  from public.paper_trade_results r
  join active a using (series_id)
  group by r.series_id
),
metrics as (
  select a.*,
         coalesce(c.candidate_outcomes,0) as candidate_outcomes,
         coalesce(c.eligible_24h,0) as eligible_24h,
         coalesce(c.complete_24h,0) as complete_24h,
         coalesce(t.trade_results,0) as trade_results,
         coalesce(t.completed_trades,0) as completed_trades,
         coalesce(qs.qualifying_cohort_size,0) as qualifying_cohort_size,
         qs.qualifying_cohort_first_at,
         qs.qualifying_cohort_last_at,
         coalesce(qs.qualifying_span_hours,0) as qualifying_span_hours,
         coalesce(qs.qualifying_active_days,0) as qualifying_active_days,
         coalesce(qc.qualifying_max_single_day_share_pct,0) as qualifying_max_single_day_share_pct,
         coalesce(qc.qualifying_max_rolling_24h_share_pct,0) as qualifying_max_rolling_24h_share_pct,
         coalesce(qs.qualifying_eligible_24h,0) as qualifying_eligible_24h,
         coalesce(qs.qualifying_complete_24h,0) as qualifying_complete_24h
  from active a
  left join all_candidates c using(series_id)
  left join trades t using(series_id)
  left join q_summary qs using(series_id)
  left join q_concentration qc using(series_id)
),
decision as (
  select m.*,
         (
           m.qualifying_span_hours >= 48
           and m.qualifying_active_days >= 3
           and m.qualifying_max_single_day_share_pct <= 50
           and m.qualifying_max_rolling_24h_share_pct <= 60
         ) as temporal_diversity_ready,
         (
           m.qualifying_cohort_size >= 1000
           and m.qualifying_eligible_24h >= 950
           and case when m.qualifying_eligible_24h=0 then false
                    else (100.0*m.qualifying_complete_24h::numeric/m.qualifying_eligible_24h::numeric) >= 95.0
               end
         ) as qualifying_maturity_ready
  from metrics m
)
select
  d.series_id,
  d.test_id,
  d.strategy_revision,
  d.started_at,
  round((extract(epoch from (now()-d.started_at))/86400.0),3) as series_age_days,
  d.target_completed_trades,
  d.candidate_outcomes,
  d.trade_results,
  d.completed_trades,
  d.eligible_24h,
  d.complete_24h,
  case when d.eligible_24h=0 then null::numeric
       else round(100.0*d.complete_24h::numeric/d.eligible_24h::numeric,2)
  end as coverage_24h_pct,
  case
    when d.completed_trades >= d.target_completed_trades and not d.temporal_diversity_ready
      then 'PRIMARY_WAITING_TEMPORAL_DIVERSITY'
    when d.completed_trades >= d.target_completed_trades
         and d.eligible_24h < greatest(1,ceil(d.candidate_outcomes*0.95)::int)
      then 'PRIMARY_WAITING_24H_MATURITY'
    when d.completed_trades >= d.target_completed_trades
         and (
           d.eligible_24h=0
           or (100.0*d.complete_24h::numeric/d.eligible_24h::numeric) < 95.0
         )
      then 'PRIMARY_WAITING_24H_COVERAGE'
    when d.completed_trades >= d.target_completed_trades and d.temporal_diversity_ready
      then 'PRIMARY_READY'
    when d.candidate_outcomes < 1000
      then 'COLLECTING_OUTCOMES'
    when not d.temporal_diversity_ready
      then 'WAITING_TEMPORAL_DIVERSITY'
    when d.qualifying_eligible_24h < 950
      then 'WAITING_24H_MATURITY'
    when (
      case when d.qualifying_eligible_24h=0 then 0
           else 100.0*d.qualifying_complete_24h::numeric/d.qualifying_eligible_24h::numeric
      end
    ) < 95.0
      then 'WAITING_24H_COVERAGE'
    else 'ALTERNATIVE_READY'
  end as gate_state,
  (
    (
      d.completed_trades >= d.target_completed_trades
      and d.temporal_diversity_ready
      and d.eligible_24h >= greatest(1,ceil(d.candidate_outcomes*0.95)::int)
      and d.eligible_24h > 0
      and (100.0*d.complete_24h::numeric/d.eligible_24h::numeric) >= 95.0
    )
    or (
      d.candidate_outcomes >= 1000
      and d.temporal_diversity_ready
      and d.qualifying_maturity_ready
    )
  ) as completion_ready,
  greatest(0,1000-d.candidate_outcomes) as outcomes_remaining_to_alt_gate,
  greatest(0::numeric,48.0-d.qualifying_span_hours) as hours_remaining_to_age_gate,
  'EVIDENCE_DIVERSITY_FASTTRACK_V2'::text as fasttrack_policy_version,
  1000::int as qualifying_sample_target,
  d.qualifying_cohort_size,
  d.qualifying_cohort_first_at,
  d.qualifying_cohort_last_at,
  d.qualifying_span_hours,
  d.qualifying_active_days,
  d.qualifying_max_single_day_share_pct,
  d.qualifying_max_rolling_24h_share_pct,
  d.qualifying_eligible_24h,
  d.qualifying_complete_24h,
  case when d.qualifying_eligible_24h=0 then null::numeric
       else round(100.0*d.qualifying_complete_24h::numeric/d.qualifying_eligible_24h::numeric,2)
  end as qualifying_coverage_24h_pct,
  d.temporal_diversity_ready,
  d.qualifying_maturity_ready,
  greatest(0::numeric,48.0-d.qualifying_span_hours) as hours_remaining_to_temporal_span_gate,
  (
    (d.completed_trades >= d.target_completed_trades and d.temporal_diversity_ready)
    or (d.candidate_outcomes >= 1000 and d.temporal_diversity_ready)
  ) as intake_should_stop,
  (
    d.completed_trades >= d.target_completed_trades
    and d.temporal_diversity_ready
    and d.eligible_24h >= greatest(1,ceil(d.candidate_outcomes*0.95)::int)
    and d.eligible_24h > 0
    and (100.0*d.complete_24h::numeric/d.eligible_24h::numeric) >= 95.0
  ) as primary_maturity_ready
from decision d;


-- Backend-only hardening. No browser client is authorized for these internal surfaces.
alter view public.v3_h10_capture_health set (security_invoker=true);
revoke all on all tables in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;
revoke execute on all functions in schema public from anon, authenticated;
alter default privileges in schema public revoke all on tables from anon, authenticated;
alter default privileges in schema public revoke all on sequences from anon, authenticated;
alter default privileges in schema public revoke execute on functions from anon, authenticated;
