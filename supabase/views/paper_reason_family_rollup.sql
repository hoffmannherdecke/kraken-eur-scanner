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
