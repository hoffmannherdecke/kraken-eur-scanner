create or replace view public.v2r3_reason_family_events
with (security_invoker=true) as
select
  m.series_id,
  m.series_status,
  m.candidate_id,
  m.pair,
  m.initial_decision,
  coalesce(m.revalidation_decision, m.initial_decision) as final_decision,
  m.setup_lane,
  rc.reason_code,
  lower(regexp_replace(rc.reason_code, '[^a-zA-Z0-9]+', '_', 'g')) as normalized_reason_code,
  case
    when lower(rc.reason_code) ~ 'tradab|account_specific|account tradab'
      then 'TRADABILITY_DATA'
    when lower(rc.reason_code) ~ 'cost|fee|headroom|remaining_move|remaining move|risk_reward|risk reward|upside'
      then 'COST_EDGE'
    when lower(rc.reason_code) ~ 'resistance|breakout'
      then 'RESISTANCE_BREAKOUT'
    when lower(rc.reason_code) ~ 'volume'
      then 'VOLUME_CONFIRMATION'
    when lower(rc.reason_code) ~ 'extended|already[_ ]?run|late|chase|near_high|near high|prior_run|prior run'
      then 'EXTENSION_LATE_ENTRY'
    when lower(rc.reason_code) ~ 'breadth|major_market|major market|market_regime|market regime'
      then 'MARKET_REGIME'
    when lower(rc.reason_code) ~ 'open_interest|open interest|\moi\M|funding|derivative'
      then 'DERIVATIVES'
    when lower(rc.reason_code) ~ 'catalyst|headline|news'
      then 'CATALYST_CONTEXT'
    when lower(rc.reason_code) ~ 'stop|invalidation|two_stage|two stage|stage2'
      then 'RISK_ENTRY_PLAN'
    when lower(rc.reason_code) ~ 'liquid|turnover'
      then 'LIQUIDITY'
    when lower(rc.reason_code) ~ 'spread'
      then 'SPREAD'
    when lower(rc.reason_code) ~ 'continu|higher_low|higher low|trend|return|reversal|support|momentum'
      then 'TREND_CONTINUITY'
    when lower(rc.reason_code) ~ 'confirm|trigger'
      then 'CONFIRMATION_OTHER'
    else 'OTHER'
  end as reason_family,
  case
    when lower(rc.reason_code) ~ 'unavailable|unconfirmed|weak|negative|absent|zero|declin|insufficient|hurdle|unclear|unproven|not[_ ]|no[_ ]|below|near[_ ]?resistance|at[_ ]?resistance|extended|exceed|material|limits|without|missing|flat'
      then 'BLOCKING_OR_CAUTION'
    when lower(rc.reason_code) ~ 'acceptable|adequate|good|verified|tight|positive|strong|improving|ok'
      then 'SUPPORTIVE'
    else 'CONTEXT_OR_MIXED'
  end as reason_polarity,
  m.mfe_30m_pct,
  m.mae_30m_pct,
  m.mfe_60m_pct,
  m.mae_60m_pct,
  m.mfe_120m_pct,
  m.mae_120m_pct,
  m.post_detect_mfe_4h_pct,
  m.post_detect_mfe_24h_pct
from public.v2r3_candidate_analysis_matrix m
cross join lateral jsonb_array_elements_text(coalesce(m.reason_codes, '[]'::jsonb)) as rc(reason_code);

create or replace view public.v2r3_reason_family_rollup
with (security_invoker=true) as
select
  series_id,
  final_decision as decision,
  reason_family,
  reason_polarity,
  count(*)::integer as reason_instances,
  count(distinct candidate_id)::integer as candidates,
  count(mfe_30m_pct)::integer as mature_30m,
  round(percentile_cont(0.5) within group (order by mfe_30m_pct)::numeric, 3) as p50_mfe_30m_pct,
  count(*) filter (where mfe_30m_pct >= 2)::integer as instances_mfe_30m_ge_2pct,
  count(mfe_120m_pct)::integer as mature_120m,
  round(percentile_cont(0.5) within group (order by mfe_120m_pct)::numeric, 3) as p50_mfe_120m_pct,
  count(*) filter (where mfe_120m_pct >= 2)::integer as instances_mfe_120m_ge_2pct,
  count(post_detect_mfe_4h_pct)::integer as mature_post_detect_4h,
  round(percentile_cont(0.5) within group (order by post_detect_mfe_4h_pct)::numeric, 3) as p50_post_detect_mfe_4h_pct,
  count(post_detect_mfe_24h_pct)::integer as mature_post_detect_24h,
  round(percentile_cont(0.5) within group (order by post_detect_mfe_24h_pct)::numeric, 3) as p50_post_detect_mfe_24h_pct,
  'Descriptive post-hoc taxonomy for analysis only. Pattern families/polarity are not strategy rules and must not be used to tune the active clean series before its completion gate.'::text as interpretation_guardrail
from public.v2r3_reason_family_events
group by series_id, final_decision, reason_family, reason_polarity;
