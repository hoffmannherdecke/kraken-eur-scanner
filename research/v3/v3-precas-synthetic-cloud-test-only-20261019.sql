-- SYNTHETIC-ONLY V3 originalhost Offline-Canary Cloud acceptance fixture.
-- Apply ONLY to the SEPARATE, already user-approved FREE Supabase test project:
-- zxyhunwpviafyxyqysne (NEVER production nlgzjmqgwueojlyqmoru).
-- A receipt here can never certify a genuine market/model/production release gate.
-- The original Edge relay implementation, reused unchanged, authenticates a
-- dedicated SHA256 bearer token. No project/account/Trading credentials copied.

CREATE TABLE public.internal_relay_credentials (
  relay_id text PRIMARY KEY
    CHECK (relay_id = 'v3-paper-evidence-relay'),
  token_sha256 text NOT NULL
    CHECK (token_sha256 ~ '^[0-9a-f]{64}$'),
  enabled boolean NOT NULL DEFAULT false,
  rotated_at timestamptz NOT NULL DEFAULT now(),
  note text
);
INSERT INTO public.internal_relay_credentials
  (relay_id, token_sha256, enabled, note)
VALUES
  ('v3-paper-evidence-relay', repeat('0',64), false,
   'TEST PROJECT ONLY: awaiting distinct locally-generated offline sandbox bearer token SHA256');

CREATE TABLE public.v3_paper_event_receipts (
  event_id text PRIMARY KEY CHECK (event_id ~ '^[0-9a-f]{64}$'),
  series_id text NOT NULL
    CHECK (series_id = 'PAPER-V3-CANARY-PRECAS-OFFLINE-C0D55C6C07B2'),
  revision text NOT NULL
    CHECK (revision = 'V3-EXPERIMENTAL-PAPER-20261011-ALL-LESSONS-001'),
  candidate_id text NOT NULL
    CHECK (candidate_id IN ('V3-OFFLINE-HOST-BUY','V3-OFFLINE-HOST-REJECT')),
  pair text NOT NULL CHECK (right(pair,4) = '/EUR'),
  phase text NOT NULL CHECK (phase ~ '^[A-Z][A-Z0-9_]+$'),
  result text NOT NULL CHECK (result ~ '^[A-Z][A-Z0-9_]+$'),
  source_known_at timestamptz NOT NULL,
  payload jsonb NOT NULL CHECK (
    payload->>'kind' = 'V3_EXPERIMENTAL_PAPER_CANDIDATE_EVENT_V1'
    AND payload->>'series_id' = series_id
    AND payload->>'candidate_id' = candidate_id
    AND payload->>'orders' = 'false'
    AND payload->>'real_money_actions' = 'false'
  ),
  content_sha256 text NOT NULL
    CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
  received_at timestamptz NOT NULL DEFAULT now(),
  fixture_only boolean NOT NULL DEFAULT true CHECK (fixture_only),
  evidence_class text NOT NULL DEFAULT 'SYNTHETIC_MODEL_STUB_NOT_ORIGINAL_MARKET'
    CHECK (evidence_class = 'SYNTHETIC_MODEL_STUB_NOT_ORIGINAL_MARKET'),
  CONSTRAINT only_synthetic_buy_has_fill
    CHECK (phase <> 'PAPER_FILL'
           OR (candidate_id = 'V3-OFFLINE-HOST-BUY' AND result = 'PAPER_FILLED')),
  CONSTRAINT expected_p4_outcome
    CHECK (phase <> 'P4_VALIDATION'
           OR ((candidate_id = 'V3-OFFLINE-HOST-BUY' AND result = 'BUY_SCOUT')
            OR (candidate_id = 'V3-OFFLINE-HOST-REJECT' AND result = 'REJECT')))
);
CREATE UNIQUE INDEX v3_paper_receipt_unique_event
  ON public.v3_paper_event_receipts(series_id,candidate_id,phase,event_id);
CREATE INDEX v3_paper_receipts_candidate_phase_idx
  ON public.v3_paper_event_receipts(candidate_id,phase);
CREATE INDEX v3_paper_receipts_series_known_at_idx
  ON public.v3_paper_event_receipts(series_id,source_known_at);

-- The test-only schemas are not exposed to browser or other app roles.
ALTER TABLE public.internal_relay_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.v3_paper_event_receipts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.internal_relay_credentials FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.v3_paper_event_receipts FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.internal_relay_credentials TO service_role;
GRANT SELECT, INSERT ON public.v3_paper_event_receipts TO service_role;

-- No UPDATE/DELETE grants. Only the separate project's privileged SQL
-- operator may rotate this SANDBOX credential or inspect receipts.
-- The unchanged V3 relay uses its own project-scoped service key via env.
