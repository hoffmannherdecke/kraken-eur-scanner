create or replace view public.v2r3_interim_horizon_summary with (security_invoker=true) as
select
  series_id,
  initial_decision as decision,
  count(*)::integer as candidates,

  count(mfe_30m_pct)::integer as mature_30m,
  round(percentile_cont(0.5) within group (order by mfe_30m_pct)::numeric, 3) as p50_mfe_30m_pct,
  round(percentile_cont(0.5) within group (order by mae_30m_pct)::numeric, 3) as p50_mae_30m_pct,
  count(*) filter (where mfe_30m_pct >= 2)::integer as mfe_30m_ge_2pct,

  count(mfe_60m_pct)::integer as mature_60m,
  round(percentile_cont(0.5) within group (order by mfe_60m_pct)::numeric, 3) as p50_mfe_60m_pct,
  round(percentile_cont(0.5) within group (order by mae_60m_pct)::numeric, 3) as p50_mae_60m_pct,
  count(*) filter (where mfe_60m_pct >= 2)::integer as mfe_60m_ge_2pct,

  count(mfe_120m_pct)::integer as mature_120m,
  round(percentile_cont(0.5) within group (order by mfe_120m_pct)::numeric, 3) as p50_mfe_120m_pct,
  round(percentile_cont(0.5) within group (order by mae_120m_pct)::numeric, 3) as p50_mae_120m_pct,
  count(*) filter (where mfe_120m_pct >= 2)::integer as mfe_120m_ge_2pct,

  count(mfe_360m_pct)::integer as mature_360m,
  round(percentile_cont(0.5) within group (order by mfe_360m_pct)::numeric, 3) as p50_mfe_360m_pct,
  round(percentile_cont(0.5) within group (order by mae_360m_pct)::numeric, 3) as p50_mae_360m_pct,
  count(*) filter (where mfe_360m_pct >= 2)::integer as mfe_360m_ge_2pct,

  count(post_detect_mfe_15m_pct)::integer as mature_post_detect_15m,
  round(percentile_cont(0.5) within group (order by post_detect_mfe_15m_pct)::numeric, 3) as p50_post_detect_mfe_15m_pct,
  count(post_detect_mfe_1h_pct)::integer as mature_post_detect_1h,
  round(percentile_cont(0.5) within group (order by post_detect_mfe_1h_pct)::numeric, 3) as p50_post_detect_mfe_1h_pct,
  count(post_detect_mfe_4h_pct)::integer as mature_post_detect_4h,
  round(percentile_cont(0.5) within group (order by post_detect_mfe_4h_pct)::numeric, 3) as p50_post_detect_mfe_4h_pct,

  'Interim descriptive horizon rollup only. Do not tune, promote, or alter V2R3/V2R4 from immature horizons; final review still requires the documented clean-series completion gate and mature 24h evidence.'::text as interpretation_guardrail
from public.v2r3_candidate_analysis_matrix
where series_status = 'active'
group by series_id, initial_decision;
