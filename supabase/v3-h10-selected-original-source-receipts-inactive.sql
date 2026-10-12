-- INACTIVE / REVIEW ONLY: DO NOT RUN AGAINST LIVE SUPABASE WITHOUT
-- SEPARATE EXPLICIT USER APPROVAL FOR SCHEMA + ROLE PERMISSIONS + H10 OWNER RUNTIME.
-- Not a live migration. No schedule, source worker, signer, trade or cloud writer.
-- Single owner: existing GitHub H10 capture -> this SAME Supabase project.
-- Existing pgcrypto.digest(bytea,text) in extensions schema checked read-only.
-- Create-only intentionally fails on any existing relation/trigger/function.
CREATE TABLE public.v3_h10_selected_source_receipts (
    candidate_id text PRIMARY KEY
        CHECK (candidate_id ~ '^[0-9a-f]{64}$'),
    cohort_id text NOT NULL CHECK (cohort_id = 'V3-H10-COHORT-001'),
    cohort_role text NOT NULL CHECK (cohort_role IN ('PRIMARY','CONTROL')),
    coin text NOT NULL CHECK (coin ~ '^[A-Za-z0-9:_-]{2,40}$'),
    window_start_utc timestamptz NOT NULL,
    evaluated_at_utc timestamptz NOT NULL,
    content_sha256 text NOT NULL
        CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    -- Keep the EXACT Python sorted compact canonical JSON bytes, not JSONB
    -- reserialization. PostgreSQL validates the SHA256 over those bytes.
    original_payload_canonical text NOT NULL,
    received_at_utc timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT h10_selected_window_alignment CHECK
        (mod(extract(epoch FROM window_start_utc), 1800) = 0),
    CONSTRAINT h10_selected_window_clock CHECK
        (evaluated_at_utc >= window_start_utc + interval '30 minutes'
         AND evaluated_at_utc <= window_start_utc + interval '47 hours 55 minutes'
         AND evaluated_at_utc <= received_at_utc + interval '5 seconds'),
    CONSTRAINT h10_selected_original_payload_size CHECK
        (octet_length(original_payload_canonical) <= 65536),
    CONSTRAINT h10_selected_original_canonical_sha CHECK
        (encode(extensions.digest(convert_to(original_payload_canonical, 'UTF8'),
                                  'sha256'), 'hex') = content_sha256),
    CONSTRAINT h10_selected_original_array CHECK (
        (jsonb_typeof(original_payload_canonical::jsonb) = 'object') IS TRUE
        AND (jsonb_typeof(original_payload_canonical::jsonb -> 'original_events')
             = 'array') IS TRUE
        AND (jsonb_array_length(original_payload_canonical::jsonb -> 'original_events')
             BETWEEN 3 AND 128) IS TRUE
    ),
    CONSTRAINT h10_selected_original_binding CHECK (
        (original_payload_canonical::jsonb ?&
          ARRAY['cohort_id','cohort_role','coin','window_start_utc',
                'window_end_utc','evaluated_at_utc','source_event_count']) IS TRUE
        AND (original_payload_canonical::jsonb ->> 'kind' =
             'V3_H10_SELECTED_ORIGINAL_SOURCE_RECEIPT_CANDIDATE_V1') IS TRUE
        AND (original_payload_canonical::jsonb ->> 'cohort_id' = cohort_id) IS TRUE
        AND (original_payload_canonical::jsonb ->> 'cohort_role' = cohort_role) IS TRUE
        AND (original_payload_canonical::jsonb ->> 'coin' = coin) IS TRUE
        AND ((original_payload_canonical::jsonb ->> 'window_start_utc')::timestamptz
             = window_start_utc) IS TRUE
        AND ((original_payload_canonical::jsonb ->> 'window_end_utc')::timestamptz
             = window_start_utc + interval '30 minutes') IS TRUE
        AND ((original_payload_canonical::jsonb ->> 'evaluated_at_utc')::timestamptz
             = evaluated_at_utc) IS TRUE
        AND ((original_payload_canonical::jsonb ->> 'source_event_count')::integer
             = jsonb_array_length(original_payload_canonical::jsonb -> 'original_events')) IS TRUE
        AND ((original_payload_canonical::jsonb ->> 'wallet_address_count')::integer
             BETWEEN 3 AND 26) IS TRUE
    ),
    CONSTRAINT h10_selected_original_nontrade CHECK (
        (original_payload_canonical::jsonb -> 'orders' = 'false'::jsonb) IS TRUE
        AND (original_payload_canonical::jsonb -> 'no_buy_authority' = 'true'::jsonb) IS TRUE
        AND (original_payload_canonical::jsonb -> 'source_owner_authenticated'
             = 'false'::jsonb) IS TRUE
        AND (original_payload_canonical::jsonb -> 'self_dealing_excluded'
             = 'false'::jsonb) IS TRUE
        AND (original_payload_canonical::jsonb -> 'beneficial_owner_independence_verified'
             = 'false'::jsonb) IS TRUE
        AND (original_payload_canonical::jsonb -> 'kraken_eur_tradability_verified'
             = 'false'::jsonb) IS TRUE
    ),
    CONSTRAINT h10_selected_unique_source_window UNIQUE
        (cohort_id, cohort_role, coin, window_start_utc)
);
-- The stored SHA is cryptographically checked; candidate_id remains a
-- caller-calculated deterministic identity additionally verified by the
-- already merged offline builder and future read-after-write owner ACK.
-- A valid SHA is NOT source authenticity, independent ownership or BUY.
CREATE INDEX h10_selected_receipts_window_idx
  ON public.v3_h10_selected_source_receipts (window_start_utc, cohort_role);

ALTER TABLE public.v3_h10_selected_source_receipts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.v3_h10_selected_source_receipts
  FROM PUBLIC, anon, authenticated, service_role;
-- No public access. Existing trusted H10 GitHub server-side secret only;
-- grant INSERT ONLY for source columns, never for received_at_utc.
GRANT SELECT ON TABLE public.v3_h10_selected_source_receipts TO service_role;
GRANT INSERT (candidate_id, cohort_id, cohort_role, coin, window_start_utc,
              evaluated_at_utc, content_sha256, original_payload_canonical)
  ON TABLE public.v3_h10_selected_source_receipts TO service_role;
-- service_role BYPASSES RLS, so a trigger is needed even if DELETE
-- and UPDATE privileges were not granted. The source event is append-only.
CREATE FUNCTION public.v3_h10_refuse_mutating_source_receipt()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = ''
AS $body$
BEGIN
    RAISE EXCEPTION 'immutable H10 source original receipt cannot be changed or deleted';
END;
$body$;
REVOKE ALL ON FUNCTION public.v3_h10_refuse_mutating_source_receipt()
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.v3_h10_refuse_mutating_source_receipt()
  TO service_role;
CREATE TRIGGER v3_h10_selected_source_receipt_immutable_guard
BEFORE UPDATE OR DELETE ON public.v3_h10_selected_source_receipts
FOR EACH ROW EXECUTE FUNCTION public.v3_h10_refuse_mutating_source_receipt();

-- Live release gate, NOT performed by this review branch:
-- (1) Obtain distinct schema + permission authorization, snapshot current
--     GitHub H10 run/branch and approved database state; apply one migration.
-- (2) Verify RLS and effective privileges for anon/auth/service_role,
--     especially no INSERT permission on received_at_utc.
-- (3) From the SAME existing H10 source owner, validate actual complete
--     first-seen/batch evidence before 48h start-based TTL, then INSERT.
-- (4) Require immutable read-back, exact server ACK, timestamp and SHA;
--     verify identical replay NO WRITE and changed digest FAIL NO WRITE.
-- (5) Test UPDATE and DELETE refusal under controlled role transaction
--     and capture true GitHub run success. Never backdate 08.10 PIT5.
-- (6) Recheck storage/cost/retention and Supabase security advisors;
--     never elevate H10 receipts to signatory or trading authority.
