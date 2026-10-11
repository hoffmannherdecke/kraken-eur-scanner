-- CREATE-ONLY, no changes to any V2R4 or paper_series rows.
-- Dedicated append-only V3 PAPER/physical-CANARY journal. Run via reviewed
-- Supabase migration, not by a GitHub Actions CI or Mini-PC service key.
CREATE TABLE IF NOT EXISTS public.v3_paper_event_receipts (
  event_id text PRIMARY KEY CHECK (event_id ~ '^[0-9a-f]{64}$'),
  series_id text NOT NULL CHECK (series_id ~ '^PAPER-V3-[A-Za-z0-9_-]+$'),
  revision text NOT NULL CHECK (revision LIKE 'V3-%'),
  candidate_id text NOT NULL,
  pair text NOT NULL CHECK (pair LIKE '%/EUR'),
  phase text NOT NULL,
  result text NOT NULL,
  source_known_at timestamptz NOT NULL,
  payload jsonb NOT NULL,
  content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
  received_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT v3_paper_receipt_unique_event UNIQUE (series_id,candidate_id,phase,event_id),
  CONSTRAINT v3_paper_receipt_kind CHECK (payload->>'kind'='V3_EXPERIMENTAL_PAPER_CANDIDATE_EVENT_V1'),
  CONSTRAINT v3_paper_receipt_paper_only CHECK
    (payload->'real_money_actions'='false'::jsonb AND payload->'orders'='false'::jsonb)
);
ALTER TABLE public.v3_paper_event_receipts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.v3_paper_event_receipts FROM PUBLIC, anon, authenticated;
GRANT SELECT,INSERT ON TABLE public.v3_paper_event_receipts TO service_role;
CREATE INDEX IF NOT EXISTS v3_paper_receipts_series_known_at_idx
 ON public.v3_paper_event_receipts(series_id,source_known_at);
CREATE INDEX IF NOT EXISTS v3_paper_receipts_candidate_phase_idx
 ON public.v3_paper_event_receipts(candidate_id,phase);
-- No UPDATE/DELETE, even through the service-role Edge; an original Paper
-- receipt must survive a technical series rotation or failed sync.
CREATE OR REPLACE FUNCTION public.v3_paper_refuse_mutating_receipts()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=''
AS $body$
BEGIN
  RAISE EXCEPTION 'immutable V3 Paper event may not be updated/deleted';
END;
$body$;
REVOKE ALL ON FUNCTION public.v3_paper_refuse_mutating_receipts() FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.v3_paper_refuse_mutating_receipts() TO service_role;
DROP TRIGGER IF EXISTS v3_paper_immutable_update_delete_guard
 ON public.v3_paper_event_receipts;
CREATE TRIGGER v3_paper_immutable_update_delete_guard
 BEFORE UPDATE OR DELETE ON public.v3_paper_event_receipts
 FOR EACH ROW EXECUTE FUNCTION public.v3_paper_refuse_mutating_receipts();
