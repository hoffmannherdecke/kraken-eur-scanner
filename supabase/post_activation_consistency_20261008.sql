-- Post-activation consistency hardening, 2026-10-08.
-- Governance/analytics only: no strategy thresholds, entries, exits, sizing or order paths change.
create or replace view public.v2r4_activation_readiness
with (security_invoker=true) as
with candidate_stats as (
  select
    count(*)::integer as candidate_outcomes,
    count(*) filter (where evaluated_at <= now() - interval '24 hours')::integer as eligible_24h,
    count(*) filter (
      where evaluated_at <= now() - interval '24 hours'
        and (
          (followup -> 'horizons') ? '1440'
          or (followup -> 'opportunity_audit' -> 'horizons') ? '1440'
        )
    )::integer as complete_24h
  from public.paper_candidate_outcomes
  where series_id = 'PAPER-V2R3-CLEAN-20261001T0925Z'
),
trade_stats as (
  select count(*) filter (where closed_at is not null)::integer as completed_trades
  from public.paper_trade_results
  where series_id = 'PAPER-V2R3-CLEAN-20261001T0925Z'
),
paper as (
  select
    ps.series_id,
    case when ps.status = 'closed_complete' then 'CLOSED_COMPLETE' else 'PREDECESSOR_NOT_CLOSED' end::text as gate_state,
    (ps.status = 'closed_complete') as completion_ready,
    cs.candidate_outcomes,
    ts.completed_trades,
    cs.eligible_24h,
    cs.complete_24h,
    case when cs.eligible_24h = 0 then null::numeric
         else round(100.0 * cs.complete_24h::numeric / cs.eligible_24h::numeric, 2) end as coverage_24h_pct,
    case when ps.status = 'closed_complete' then 0 else greatest(0,1000-cs.candidate_outcomes) end::integer as outcomes_remaining_to_alt_gate,
    case when ps.status = 'closed_complete' then 0::numeric else null::numeric end as hours_remaining_to_age_gate,
    (ps.status = 'closed_complete') as intake_should_stop,
    'EVIDENCE_DIVERSITY_FASTTRACK_V2'::text as fasttrack_policy_version,
    (
      ps.status = 'closed_complete'
      and cs.candidate_outcomes >= 1000
      and cs.eligible_24h >= 950
      and cs.complete_24h >= 950
      and (cs.eligible_24h = 0 or 100.0 * cs.complete_24h::numeric / cs.eligible_24h::numeric >= 95.0)
    ) as qualifying_maturity_ready
  from public.paper_series ps
  cross join candidate_stats cs
  cross join trade_stats ts
  where ps.series_id = 'PAPER-V2R3-CLEAN-20261001T0925Z'
),
shadow as (
  select * from public.v2r4_shadow_completion_readiness limit 1
),
integrity as (
  select * from public.v2r3_clean_integrity_summary limit 1
),
minipc as (
  select observed_at,status,payload ->> 'health_state' as health_state
  from public.minipc_status_current
  where node_id='MINI-PC'
  limit 1
),
release_decision as (
  select release_id,predecessor_series_id,successor_revision,status,decided_at,decision_evidence,
         updated_at,final_review_completed_at,migration_review_completed_at
  from public.strategy_release_decisions
  where release_id='V2R3_TO_V2R4_20261005'
  limit 1
),
successor as (
  select ps.series_id,ps.status,ps.strategy_revision
  from public.paper_series ps
  cross join release_decision rd
  where ps.series_id = rd.decision_evidence ->> 'activation_series_id'
  limit 1
)
select
  now() as generated_at,
  paper.series_id as v2r3_series_id,
  paper.gate_state as v2r3_gate_state,
  paper.completion_ready as v2r3_completion_ready,
  paper.candidate_outcomes as v2r3_candidate_outcomes,
  paper.completed_trades as v2r3_completed_trades,
  paper.eligible_24h as v2r3_eligible_24h,
  paper.complete_24h as v2r3_complete_24h,
  paper.coverage_24h_pct as v2r3_coverage_24h_pct,
  paper.outcomes_remaining_to_alt_gate as v2r3_outcomes_remaining,
  round(paper.hours_remaining_to_age_gate,2) as v2r3_hours_remaining_to_age_gate,
  shadow.readiness_state as v2r4_shadow_readiness_state,
  shadow.prospective_events as v2r4_shadow_prospective_events,
  shadow.due_6h as v2r4_shadow_due_6h,
  shadow.completed_due_6h as v2r4_shadow_completed_due_6h,
  shadow.unresolved_due_6h as v2r4_shadow_unresolved_due_6h,
  shadow.complete_6h_coverage_pct as v2r4_shadow_complete_6h_coverage_pct,
  minipc.observed_at as minipc_observed_at,
  round(extract(epoch from (now()-minipc.observed_at))/60.0,2) as minipc_status_age_minutes,
  minipc.status as minipc_status,
  minipc.health_state as minipc_health_state,
  false as automatic_activation_allowed,
  case
    when successor.series_id is not null
      and successor.status='active'
      and release_decision.status='APPROVED_PAPER'
      and successor.strategy_revision like 'V2R4%'
      then 'PAPER_RELEASE_ALREADY_ACTIVATED'
    when coalesce(paper.completion_ready,false) is not true then 'BLOCKED_V2R3_COMPLETION'
    when coalesce(integrity.integrity_state,'') <> 'HEALTHY' then 'BLOCKED_V2R3_INTEGRITY'
    when coalesce(shadow.readiness_state,'') not in ('MATURE_COHORT_ARCHIVED','MATURE_OUTCOMES_PENDING')
      then 'BLOCKED_V2R4_SHADOW_MATURITY'
    when minipc.observed_at is null
      or minipc.observed_at < now()-interval '20 minutes'
      or coalesce(minipc.status,'') <> 'HEALTHY'
      or coalesce(minipc.health_state,'') <> 'OK'
      then 'BLOCKED_MINIPC_HEALTH'
    when release_decision.final_review_completed_at is null then 'MANUAL_V2R3_FINAL_REVIEW_REQUIRED'
    when release_decision.migration_review_completed_at is null then 'MANUAL_MIGRATION_REVIEW_REQUIRED'
    when coalesce(release_decision.status,'PENDING') <> 'APPROVED_PAPER' then 'MANUAL_RELEASE_DECISION_REQUIRED'
    else 'PAPER_RELEASE_APPROVED_NOT_AUTOMATICALLY_ACTIVATED'
  end as activation_review_state,
  'Post-activation-safe control view. V2R3 evidence is pinned to PAPER-V2R3-CLEAN-20261001T0925Z and can never follow the current active series. Once the approved successor series is active, the completed V2R3 release gate is treated as closed history and is never reopened. This view never activates a strategy automatically.'::text as interpretation_guardrail,
  integrity.integrity_state as v2r3_integrity_state,
  integrity.duplicate_candidate_ids as v2r3_duplicate_candidate_ids,
  integrity.duplicated_queue_ids as v2r3_duplicated_queue_ids,
  integrity.distinct_strategy_fingerprints as v2r3_strategy_fingerprints,
  integrity.distinct_runtime_fingerprints as v2r3_runtime_fingerprints,
  paper.intake_should_stop as v2r3_intake_should_stop,
  paper.fasttrack_policy_version,
  paper.qualifying_maturity_ready as v2r3_qualifying_maturity_ready,
  case
    when release_decision.final_review_completed_at is not null then 'FINAL_REVIEW_COMPLETE'
    when coalesce(paper.completion_ready,false) is not true then 'WAITING_COMPLETION'
    when coalesce(integrity.integrity_state,'') <> 'HEALTHY' then 'BLOCKED_INTEGRITY'
    else 'READY_FOR_FINAL_REVIEW'
  end as v2r3_final_review_state,
  (coalesce(paper.completion_ready,false) is true and coalesce(integrity.integrity_state,'')='HEALTHY') as v2r3_final_review_allowed,
  release_decision.status as explicit_release_decision_status,
  release_decision.decided_at as explicit_release_decided_at,
  release_decision.final_review_completed_at,
  release_decision.migration_review_completed_at
from paper
cross join shadow
cross join integrity
cross join release_decision
left join minipc on true
left join successor on true;

create or replace view public.v2r3_release_review_snapshot
with (security_invoker=true) as
with activation as (
  select * from public.v2r4_activation_readiness limit 1
),
ready as (
  select
    ps.series_id,ps.test_id,ps.strategy_revision,ps.started_at,
    round(extract(epoch from (now()-ps.started_at))/86400.0,3) as series_age_days,
    ps.target_completed_trades,
    a.v2r3_candidate_outcomes as candidate_outcomes,
    a.v2r3_completed_trades as completed_trades,
    a.v2r3_eligible_24h as eligible_24h,
    a.v2r3_complete_24h as complete_24h,
    a.v2r3_coverage_24h_pct as coverage_24h_pct,
    a.v2r3_gate_state as gate_state,
    a.v2r3_completion_ready as completion_ready
  from public.paper_series ps
  cross join activation a
  where ps.series_id=a.v2r3_series_id
),
integrity as (
  select * from public.v2r3_clean_integrity_summary limit 1
),
timing as (
  select coalesce(jsonb_agg(to_jsonb(t) order by t.decision),'[]'::jsonb) as rows
  from public.v2r3_runtime_timing_summary t join ready r on r.series_id=t.series_id
),
revalidation as (
  select to_jsonb(x) as row
  from public.v2r3_revalidation_timing_summary x join ready r on r.series_id=x.series_id
),
outcomes as (
  select coalesce(jsonb_agg(to_jsonb(o) order by o.decision),'[]'::jsonb) as rows
  from public.v2r3_outcome_summary o join ready r on r.series_id=o.series_id
),
interim as (
  select coalesce(jsonb_agg(to_jsonb(i) order by i.decision),'[]'::jsonb) as rows
  from public.v2r3_interim_horizon_summary i join ready r on r.series_id=i.series_id
),
reason_families as (
  select coalesce(jsonb_agg(to_jsonb(z) order by z.reason_instances desc,z.decision,z.reason_family,z.reason_polarity),'[]'::jsonb) as rows
  from (
    select f.* from public.v2r3_reason_family_rollup f
    join ready r on r.series_id=f.series_id
    order by f.reason_instances desc,f.decision,f.reason_family,f.reason_polarity
    limit 100
  ) z
),
missed_moves as (
  select coalesce(jsonb_agg(to_jsonb(z) order by z.mfe_24h_pct desc nulls last,z.evaluated_at),'[]'::jsonb) as rows
  from (
    select m.* from public.v2r3_missed_move_candidates m
    join ready r on r.series_id=m.series_id
    where m.mfe_24h_pct is not null
    order by m.mfe_24h_pct desc nulls last,m.evaluated_at
    limit 100
  ) z
)
select
  now() as generated_at,
  r.series_id,r.test_id,r.strategy_revision,r.started_at,r.series_age_days,r.target_completed_trades,
  r.candidate_outcomes,r.completed_trades,r.eligible_24h,r.complete_24h,r.coverage_24h_pct,
  r.gate_state,r.completion_ready,
  i.integrity_state,i.duplicate_candidate_ids,i.duplicated_queue_ids,
  i.distinct_strategy_fingerprints,i.distinct_runtime_fingerprints,
  case
    when a.final_review_completed_at is not null then 'FINAL_REVIEW_COMPLETE'
    when coalesce(r.completion_ready,false) is not true then 'WAITING_COMPLETION'
    when coalesce(i.integrity_state,'') <> 'HEALTHY' then 'BLOCKED_INTEGRITY'
    else 'READY_FOR_FINAL_REVIEW'
  end as review_state,
  (coalesce(r.completion_ready,false) is true and coalesce(i.integrity_state,'')='HEALTHY') as final_review_allowed,
  t.rows as runtime_timing,rv.row as revalidation_timing,o.rows as outcome_summary,h.rows as interim_horizons,
  f.rows as reason_family_rollup,mm.rows as mature_missed_move_candidates,
  to_jsonb(a) as v2r4_activation_control,
  false as automatic_strategy_change_allowed,
  'Frozen V2R3 evidence pack pinned to PAPER-V2R3-CLEAN-20261001T0925Z. The final review is historical once completed; successor activity can never reopen or relabel this gate. No automatic strategy change or real-money action is authorized.'::text as interpretation_guardrail
from ready r
cross join integrity i
cross join timing t
left join revalidation rv on true
cross join outcomes o
cross join interim h
cross join reason_families f
cross join missed_moves mm
cross join activation a;

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

create or replace view public.paper_reason_family_events
with (security_invoker=true) as
with active as (
  select series_id from public.paper_series where status='active' order by started_at desc limit 1
),
expanded as (
  select
    p.series_id,p.candidate_id,p.pair,p.decision,p.evaluated_at,
    case when p.payload->'recheck' is not null then 'RECHECK' else 'INITIAL' end::text as reason_source,
    rc.reason_code
  from public.paper_candidate_outcomes p
  join active a using(series_id)
  cross join lateral jsonb_array_elements_text(
    coalesce(
      p.payload->'recheck'->'decision'->'reason_codes',
      p.payload->'decision'->'decision'->'reason_codes',
      '[]'::jsonb
    )
  ) rc(reason_code)
)
select
  series_id,candidate_id,pair,decision,evaluated_at,reason_source,
  reason_code as raw_reason_code,
  lower(regexp_replace(reason_code,'[^a-zA-Z0-9]+','_','g')) as normalized_reason_code,
  case
    when lower(reason_code) ~ 'tradab|account_specific|pair_verified|pair online|pair_online' then 'TRADABILITY_DATA'
    when lower(reason_code) ~ 'cost|fee|headroom|remaining_move|remaining move|risk_reward|risk reward|upside|reward' then 'COST_EDGE'
    when lower(reason_code) ~ 'resistance|breakout' then 'RESISTANCE_BREAKOUT'
    when lower(reason_code) ~ 'volume' then 'VOLUME_CONFIRMATION'
    when lower(reason_code) ~ 'extended|already[_ ]?run|late|chase|near[_ ]?.*high|prior[_ ]?run|runup|recent[_ ]?(move|run)|entry[_ ]?efficiency|strong[_ ]?prior[_ ]?run' then 'EXTENSION_LATE_ENTRY'
    when lower(reason_code) ~ 'breadth|major[s]?[_ ]|market.*(regime|context)|regime' then 'MARKET_REGIME'
    when lower(reason_code) ~ 'open_interest|open interest|(^|_)oi(_|$)|funding|derivative' then 'DERIVATIVES'
    when lower(reason_code) ~ 'catalyst|headline|news' then 'CATALYST_CONTEXT'
    when lower(reason_code) ~ 'stop|invalidation|two_stage|two stage|stage2' then 'RISK_ENTRY_PLAN'
    when lower(reason_code) ~ 'liquid|turnover|depth' then 'LIQUIDITY'
    when lower(reason_code) ~ 'spread' then 'SPREAD'
    when lower(reason_code) ~ 'ttl|expired|expiry' then 'WAIT_TTL'
    when lower(reason_code) ~ 'continu|higher[_ ]?low|trend|return|reversal|support|momentum|relative[_ ]?strength|ret[0-9]+h|positive_[0-9]+h|negative_[0-9]+h' then 'TREND_CONTINUITY'
    when lower(reason_code) ~ 'confirm|trigger' then 'CONFIRMATION_OTHER'
    else 'OTHER'
  end::text as reason_family,
  case
    when lower(reason_code) ~ 'unavailable|unconfirmed|weak|negative|absent|zero|declin|insufficient|hurdle|unclear|unproven|not[_ ]|no[_ ]|below|near[_ ]?resistance|at[_ ]?resistance|extended|exceed|material|limits|without|missing|flat|expired' then 'BLOCKING_OR_CAUTION'
    when lower(reason_code) ~ 'acceptable|adequate|good|verified|tight|positive|strong|improving|online|pass' then 'SUPPORTIVE'
    else 'CONTEXT_OR_MIXED'
  end::text as reason_polarity
from expanded;

create or replace view public.paper_reason_family_rollup
with (security_invoker=true) as
select
  series_id,decision,reason_family,reason_polarity,
  count(*)::integer as reason_instances,
  count(distinct candidate_id)::integer as candidates,
  count(distinct normalized_reason_code)::integer as distinct_raw_variants
from public.paper_reason_family_events
group by series_id,decision,reason_family,reason_polarity
order by reason_instances desc,decision,reason_family,reason_polarity;

revoke all on public.paper_reason_family_events from anon, authenticated;
revoke all on public.paper_reason_family_rollup from anon, authenticated;

