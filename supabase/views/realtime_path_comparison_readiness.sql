-- Fail-closed readiness view for comparing realtime trigger paths.
-- This view deliberately does not rank Kraken-native, scanner or Altrady.
-- It exposes sample/matching sufficiency and keeps the distinction between
-- transport latency and market-event detection latency explicit.

create or replace view public.realtime_path_comparison_readiness
with (security_invoker=true) as
with shadow as (
    select
        count(*)::integer as shadow_events,
        percentile_cont(0.5) within group (
            order by nullif(event_payload ->> 'feed_to_shadow_latency_ms','')::numeric
        ) filter (
            where nullif(event_payload ->> 'feed_to_shadow_latency_ms','') is not null
        ) as shadow_feed_p50_ms,
        percentile_cont(0.9) within group (
            order by nullif(event_payload ->> 'feed_to_shadow_latency_ms','')::numeric
        ) filter (
            where nullif(event_payload ->> 'feed_to_shadow_latency_ms','') is not null
        ) as shadow_feed_p90_ms
    from public.v2r4_shadow_evidence
),
tight as (
    select
        count(*)::integer as shadow_rows,
        count(*) filter (where scanner_detected_at is not null)::integer as same_pair_within_30m,
        count(*) filter (where absolute_time_delta_seconds <= 900)::integer as same_pair_within_15m,
        count(*) filter (where absolute_time_delta_seconds <= 300)::integer as same_pair_within_5m,
        percentile_cont(0.5) within group (
            order by absolute_time_delta_seconds
        ) filter (
            where absolute_time_delta_seconds is not null
        ) as matched_abs_delta_p50_sec
    from public.v2r4_shadow_scanner_match_quality
),
altrady as (
    select
        count(*)::integer as transport_events,
        percentile_cont(0.5) within group (
            order by relay_to_minipc_seconds
        ) filter (
            where relay_to_minipc_seconds is not null
        ) as relay_to_minipc_p50_sec,
        percentile_cont(0.9) within group (
            order by relay_to_minipc_seconds
        ) filter (
            where relay_to_minipc_seconds is not null
        ) as relay_to_minipc_p90_sec
    from public.altrady_transport_timing
)
select
    now() as generated_at,
    shadow.shadow_events,
    round(shadow.shadow_feed_p50_ms,3) as shadow_feed_p50_ms,
    round(shadow.shadow_feed_p90_ms,3) as shadow_feed_p90_ms,
    tight.same_pair_within_30m as scanner_same_pair_within_30m,
    tight.same_pair_within_15m as scanner_same_pair_within_15m,
    tight.same_pair_within_5m as scanner_same_pair_within_5m,
    case
        when tight.shadow_rows > 0
        then round(100.0 * tight.same_pair_within_5m / tight.shadow_rows,2)
        else null
    end as scanner_within_5m_share_pct,
    round(tight.matched_abs_delta_p50_sec::numeric,3) as scanner_matched_abs_delta_p50_sec,
    altrady.transport_events as altrady_transport_events,
    round(altrady.relay_to_minipc_p50_sec::numeric,3) as altrady_relay_to_minipc_p50_sec,
    round(altrady.relay_to_minipc_p90_sec::numeric,3) as altrady_relay_to_minipc_p90_sec,
    case
        when tight.same_pair_within_5m < 30 then 'INSUFFICIENT_TEMPORAL_MATCH_SAMPLE'
        else 'TEMPORAL_SAMPLE_PRESENT_IDENTITY_NOT_PROVEN'
    end as scanner_comparison_state,
    case
        when altrady.transport_events < 20 then 'INSUFFICIENT_TRANSPORT_SAMPLE'
        else 'TRANSPORT_SAMPLE_PRESENT_NOT_EVENT_MATCHED'
    end as altrady_comparison_state,
    false as ranking_allowed,
    'Fail-closed comparison control. Kraken-shadow feed latency, scanner temporal proximity, and Altrady relay transport latency measure different things. Same-pair temporal proximity is not identical-impulse proof; Altrady transport events are not market-detection matches. Do not rank paths until identical impulses are explicitly event-matched with adequate samples.'::text
        as interpretation_guardrail
from shadow, tight, altrady;
