-- Read-only normalized V2R4 WS-shadow completed-outcome metrics.
-- No strategy/runtime changes. Rows appear only after local 6h outcomes are archived.

create or replace view public.v2r4_shadow_outcome_metrics as
select
    e.event_id,
    e.pair,
    e.observed_at,
    e.outcome_status,
    e.source_runtime_commit,
    e.event_payload -> 'reasons' as event_reasons,
    e.event_payload ->> 'liquidity_class_without_depth' as liquidity_class_without_depth,
    nullif(e.event_payload ->> 'feed_to_shadow_latency_ms', '')::numeric as feed_to_shadow_latency_ms,
    nullif(e.event_payload ->> 'spread_pct', '')::numeric as spread_pct,
    nullif(e.event_payload ->> 'turnover24h_eur', '')::numeric as turnover24h_eur,
    coalesce((e.outcome_payload ->> 'tracker_gap_affected')::boolean, false) as tracker_gap_affected,
    nullif(e.outcome_payload ->> 'max_tracker_gap_seconds', '')::numeric as max_tracker_gap_seconds,
    nullif(e.outcome_payload ->> 'entry_price_eur', '')::numeric as entry_price_eur,

    nullif(e.outcome_payload #>> '{horizons,5m,return_pct}', '')::numeric as return_5m_pct,
    nullif(e.outcome_payload #>> '{horizons,15m,return_pct}', '')::numeric as return_15m_pct,
    nullif(e.outcome_payload #>> '{horizons,30m,return_pct}', '')::numeric as return_30m_pct,
    nullif(e.outcome_payload #>> '{horizons,1h,return_pct}', '')::numeric as return_1h_pct,
    nullif(e.outcome_payload #>> '{horizons,3h,return_pct}', '')::numeric as return_3h_pct,
    nullif(e.outcome_payload #>> '{horizons,6h,return_pct}', '')::numeric as return_6h_pct,

    nullif(e.outcome_payload #>> '{horizons,6h,mfe_pct}', '')::numeric as mfe_6h_pct,
    nullif(e.outcome_payload #>> '{horizons,6h,mae_pct}', '')::numeric as mae_6h_pct,

    nullif(e.outcome_payload #>> '{horizons,5m,sample_lag_seconds}', '')::numeric as lag_5m_seconds,
    nullif(e.outcome_payload #>> '{horizons,15m,sample_lag_seconds}', '')::numeric as lag_15m_seconds,
    nullif(e.outcome_payload #>> '{horizons,30m,sample_lag_seconds}', '')::numeric as lag_30m_seconds,
    nullif(e.outcome_payload #>> '{horizons,1h,sample_lag_seconds}', '')::numeric as lag_1h_seconds,
    nullif(e.outcome_payload #>> '{horizons,3h,sample_lag_seconds}', '')::numeric as lag_3h_seconds,
    nullif(e.outcome_payload #>> '{horizons,6h,sample_lag_seconds}', '')::numeric as lag_6h_seconds,

    e.outcome_payload ->> 'completed_at_utc' as completed_at_utc,
    'Outcome evidence only. tracker_gap_affected rows must not be treated as continuous MFE/MAE observations.'::text
        as interpretation_guardrail
from public.v2r4_shadow_evidence e
where e.outcome_payload is not null;
