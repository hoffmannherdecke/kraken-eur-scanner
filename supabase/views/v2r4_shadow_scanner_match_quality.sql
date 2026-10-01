-- Read-only quality view for tighter V2R4 WS-shadow <-> legacy scanner comparison.
-- Unlike the broad +/-6h timing aid, this view exposes only the nearest same-pair
-- scanner detection within +/-30 minutes and labels the temporal proximity.
-- Temporal proximity is NOT proof that the two rows represent the identical impulse.

create or replace view public.v2r4_shadow_scanner_match_quality as
select
    e.event_id,
    e.pair,
    e.observed_at as shadow_observed_at,
    e.event_payload -> 'reasons' as shadow_reasons,
    nullif(e.event_payload #>> '{returns,ret10m}', '')::numeric as shadow_ret10m_pct,
    nullif(e.event_payload #>> '{returns,ret30m}', '')::numeric as shadow_ret30m_pct,
    nullif(e.event_payload ->> 'feed_to_shadow_latency_ms', '')::numeric as feed_to_shadow_latency_ms,
    e.event_payload ->> 'liquidity_class_without_depth' as shadow_liquidity_class,

    s.handoff_id as scanner_handoff_id,
    s.detected_at as scanner_detected_at,
    case
        when s.detected_at is null then null
        else extract(epoch from (s.detected_at - e.observed_at))
    end as scanner_minus_shadow_seconds,
    case
        when s.detected_at is null then null
        else abs(extract(epoch from (s.detected_at - e.observed_at)))
    end as absolute_time_delta_seconds,
    s.score as scanner_score,
    nullif(s.payload #>> '{scanner_candidate,ret15_live}', '')::numeric as scanner_ret15_live_pct,
    nullif(s.payload #>> '{scanner_candidate,ret1h}', '')::numeric as scanner_ret1h_pct,
    nullif(s.payload #>> '{scanner_candidate,ret3h}', '')::numeric as scanner_ret3h_pct,
    s.source_run_id as scanner_source_run_id,

    case
        when s.detected_at is null then 'NO_MATCH_WITHIN_30M'
        when abs(extract(epoch from (s.detected_at - e.observed_at))) <= 300 then 'WITHIN_5M'
        when abs(extract(epoch from (s.detected_at - e.observed_at))) <= 900 then 'WITHIN_15M'
        else 'WITHIN_30M'
    end as temporal_match_class,

    'Nearest same-pair detection within +/-30m only. Temporal proximity and similar returns may support later event matching, but do not by themselves prove identical market impulse.'::text
        as interpretation_guardrail
from public.v2r4_shadow_evidence e
left join lateral (
    select s.*
    from public.scanner_detection_evidence s
    where s.pair = e.pair
      and s.detected_at between e.observed_at - interval '30 minutes'
                            and e.observed_at + interval '30 minutes'
    order by abs(extract(epoch from (s.detected_at - e.observed_at))) asc,
             s.detected_at asc
    limit 1
) s on true;
