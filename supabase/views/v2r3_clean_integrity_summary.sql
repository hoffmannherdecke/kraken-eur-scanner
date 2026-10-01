-- Read-only integrity summary for the active clean V2R3 prospective series.
-- No strategy/runtime behavior is changed.

create or replace view public.v2r3_clean_integrity_summary as
with rows as (
    select
        candidate_id,
        pair,
        decision as table_decision,
        evaluated_at,
        payload,
        payload #>> '{decision,queue_id}' as queue_id,
        payload #>> '{decision,timing,candidate_detected_at_utc}' as candidate_detected_at_utc,
        payload #>> '{decision,timing,handoff_written_at_utc}' as handoff_written_at_utc,
        payload #>> '{decision,timing,evaluation_started_at_utc}' as evaluation_started_at_utc,
        payload #>> '{decision,timing,evaluation_completed_at_utc}' as evaluation_completed_at_utc,
        payload #>> '{decision,strategy_fingerprint_sha256}' as strategy_fingerprint,
        payload #>> '{decision,runtime_code_fingerprint_sha256}' as runtime_fingerprint,
        payload #>> '{decision,decision,decision}' as initial_decision,
        payload #>> '{revalidation,decision,decision}' as revalidation_decision,
        coalesce(
            payload #>> '{revalidation,decision,decision}',
            payload #>> '{decision,decision,decision}'
        ) as final_payload_decision,
        payload #> '{decision,fresh_kraken_ticker}' as fresh_kraken_ticker
    from public.paper_candidate_outcomes
    where series_id = 'PAPER-V2R3-CLEAN-20261001T0925Z'
),
queue_dupes as (
    select queue_id
    from rows
    where queue_id is not null
    group by queue_id
    having count(*) > 1
)
select
    now() as generated_at,
    count(*)::integer as candidate_outcomes,
    count(distinct candidate_id)::integer as distinct_candidate_ids,
    greatest(count(*) - count(distinct candidate_id), 0)::integer as duplicate_candidate_ids,
    count(*) filter (where queue_id is null)::integer as missing_queue_id,
    (select count(*)::integer from queue_dupes) as duplicated_queue_ids,
    count(*) filter (where candidate_detected_at_utc is null)::integer as missing_candidate_detected_at,
    count(*) filter (where handoff_written_at_utc is null)::integer as missing_handoff_written_at,
    count(*) filter (where evaluation_started_at_utc is null)::integer as missing_evaluation_started_at,
    count(*) filter (where evaluation_completed_at_utc is null)::integer as missing_evaluation_completed_at,
    count(*) filter (where fresh_kraken_ticker is null)::integer as missing_fresh_kraken_ticker,
    count(*) filter (where strategy_fingerprint is null)::integer as missing_strategy_fingerprint,
    count(*) filter (where runtime_fingerprint is null)::integer as missing_runtime_fingerprint,
    count(distinct strategy_fingerprint)::integer as distinct_strategy_fingerprints,
    count(distinct runtime_fingerprint)::integer as distinct_runtime_fingerprints,
    count(*) filter (
        where final_payload_decision is null
           or final_payload_decision is distinct from table_decision
    )::integer as decision_field_mismatches,
    count(*) filter (where revalidation_decision is not null)::integer as revalidated_candidates,
    count(*) filter (
        where revalidation_decision is not null
          and revalidation_decision is distinct from initial_decision
    )::integer as decision_changes_on_revalidation,
    count(*) filter (where table_decision = 'BUY_SCOUT')::integer as buy_scouts,
    count(*) filter (where table_decision = 'WAIT')::integer as waits,
    count(*) filter (where table_decision = 'REJECT')::integer as rejects,
    case
        when count(*) = 0 then 'WAITING_NO_DATA'
        when greatest(count(*) - count(distinct candidate_id), 0) > 0 then 'INTEGRITY_FAIL'
        when (select count(*) from queue_dupes) > 0 then 'INTEGRITY_FAIL'
        when count(*) filter (
            where candidate_detected_at_utc is null
               or handoff_written_at_utc is null
               or evaluation_started_at_utc is null
               or evaluation_completed_at_utc is null
               or fresh_kraken_ticker is null
               or strategy_fingerprint is null
               or runtime_fingerprint is null
               or final_payload_decision is null
               or final_payload_decision is distinct from table_decision
        ) > 0 then 'INTEGRITY_FAIL'
        when count(distinct strategy_fingerprint) <> 1 then 'INTEGRITY_FAIL'
        when count(distinct runtime_fingerprint) <> 1 then 'INTEGRITY_FAIL'
        else 'HEALTHY'
    end as integrity_state,
    'Prospective data-integrity check only. Table decision is compared with revalidation decision when present, otherwise with initial decision. This view does not evaluate strategy performance.'::text
        as interpretation_guardrail
from rows;