-- INACTIVE / REVIEW ONLY: DO NOT RUN AGAINST LIVE SUPABASE WITHOUT
-- EXPLICIT SCHEMA + PERMISSION + H10 SOURCE RUNTIME AUTHORIZATION.
-- Not a migration; no production apply, new collector, new timer, Paper writer,
-- model API, signatory, trading rights or V2R4/28h canary change.
-- Design owner: existing GitHub H10 Hyperliquid source collector and
-- existing Supabase project. Separate from v3_paper_event_receipts.
--
-- Must first verify minimal existing Supabase owner route, cost/retention,
-- completeness of source SELECT and full 48h original fill provenance.
-- Proof source fields are untrusted until verified by actual source owner.
CREATE TABLE IF NOT EXISTS public.v3_h10_selected_source_receipts (
    candidate_id text PRIMARY KEY
        CHECK (candidate_id ~ '^[0-9a-f]{64}$'),
    cohort_id text NOT NULL
        CHECK (cohort_id = 'V3-H10-COHORT-001'),
    cohort_role text NOT NULL
        CHECK (cohort_role IN ('PRIMARY','CONTROL')),
    coin text NOT NULL
        CHECK (coin ~ '^[A-Za-z0-9:_-]{2,40}$'),
    window_start_utc timestamptz NOT NULL,
    evaluated_at_utc timestamptz NOT NULL,
    content_sha256 text NOT NULL
        CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    original_payload jsonb NOT NULL,
    received_at_utc timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT h10_selected_window_clock CHECK
        (window_start_utc < evaluated_at_utc
         AND evaluated_at_utc <= received_at_utc + interval '5 seconds'),
    CONSTRAINT h10_selected_original_payload_size CHECK
        (octet_length(original_payload::text) <= 131072),
    CONSTRAINT h10_selected_original_count CHECK
        (CASE WHEN jsonb_typeof(original_payload->'original_events') = 'array'
              THEN jsonb_array_length(original_payload->'original_events') BETWEEN 3 AND 128
              ELSE false END),
    CONSTRAINT h10_selected_original_kind CHECK
        (original_payload->>'kind' = 'V3_H10_SELECTED_ORIGINAL_SOURCE_RECEIPT_CANDIDATE_V1'),
    CONSTRAINT h10_selected_original_paper_safety CHECK
        (original_payload->'orders' = 'false'::jsonb
         AND original_payload->'no_buy_authority' = 'true'::jsonb
         AND original_payload->'source_owner_authenticated' = 'false'::jsonb
         AND original_payload->'self_dealing_excluded' = 'false'::jsonb),
    CONSTRAINT h10_selected_original_owner_binding CHECK
        (original_payload->>'cohort_id' = cohort_id
         AND original_payload->>'cohort_role' = cohort_role
         AND original_payload->>'coin' = coin),
    CONSTRAINT h10_selected_unique_source_window UNIQUE
        (cohort_id, cohort_role, coin, window_start_utc)
);
-- One owner, one receipt per frozen coin/role/window; replays are SELECT
-- and exact-content-hash comparison, not an INSERT-on-conflict UPDATE.
-- No bulk raw archive; query results only for bounded selected windows.
CREATE INDEX IF NOT EXISTS h10_selected_receipts_window_idx
  ON public.v3_h10_selected_source_receipts (window_start_utc, cohort_role);

ALTER TABLE public.v3_h10_selected_source_receipts ENABLE ROW LEVEL SECURITY;
-- New public-schema tables are not necessarily exposed through Data API
-- by default; explicitly grant ONLY to the server-side existing H10 owner.
REVOKE ALL ON TABLE public.v3_h10_selected_source_receipts
  FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT, INSERT ON TABLE public.v3_h10_selected_source_receipts
  TO service_role;
-- Never grant SELECT/INSERT/UPDATE/DELETE to public users.
-- service_role bypasses RLS: a real immutable trigger is required as a
-- second guard. Do not grant any H10 service token to the MINI-PC.
CREATE OR REPLACE FUNCTION public.v3_h10_refuse_mutating_source_receipt()
RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path = ''
AS $body$
BEGIN
    RAISE EXCEPTION 'immutable H10 source original receipt cannot be changed or deleted';
END;
$body$;
REVOKE ALL ON FUNCTION public.v3_h10_refuse_mutating_source_receipt()
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.v3_h10_refuse_mutating_source_receipt()
  TO service_role;
-- New-only schema; do not silently DROP an existing trigger on rerun.
CREATE TRIGGER v3_h10_selected_source_receipt_immutable_guard
BEFORE UPDATE OR DELETE ON public.v3_h10_selected_source_receipts
FOR EACH ROW EXECUTE FUNCTION public.v3_h10_refuse_mutating_source_receipt();

-- POST-DEPLOY proof (separate explicit authorization required):
-- 1. Verify RLS + effective SELECT/INSERT only for actual H10 owner and
--    no anon/authenticated grants or bypass via other policies/views.
-- 2. SELECT read-back after first insert; compare canonical SHA256, candidate
--    ID, event IDs, original batches and server received_at; failures BLOCK.
-- 3. Reinsert same ID must be read-and-compare no rewrite; any different
--    SHA256 for same window must fail closed and preserve original row.
-- 4. UPDATE/DELETE denied in a controlled permission test, including
--    service-role path; verify actual GitHub H10 run and secret isolation.
-- 5. Reconcile retention size/storage budget; 48h raw table remains bounded.
-- 6. Do not treat this stored source evidence as economic independent-owner,
--    source HMAC, Kraken P0, BUY, model or Paper authorization.
