-- ONLY disposable PostgreSQL17 fixture. NEVER run against production Supabase.
\set ON_ERROR_STOP on
DO $roles$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN CREATE ROLE anon NOLOGIN; END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN CREATE ROLE authenticated NOLOGIN; END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='service_role') THEN CREATE ROLE service_role NOLOGIN; END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='v3_cas_audit_reader') THEN CREATE ROLE v3_cas_audit_reader NOLOGIN NOINHERIT; END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='v3_cas_audit_reader_actor') THEN CREATE ROLE v3_cas_audit_reader_actor LOGIN NOINHERIT; END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='v3_cas_audit_writer') THEN CREATE ROLE v3_cas_audit_writer NOLOGIN; END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='v3_cas_executor_actor') THEN CREATE ROLE v3_cas_executor_actor NOLOGIN; END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='v3_cas_operator_login') THEN CREATE ROLE v3_cas_operator_login NOLOGIN; END IF;
END $roles$;
ALTER ROLE v3_cas_audit_reader_actor LOGIN NOINHERIT;
GRANT v3_cas_audit_reader TO v3_cas_audit_reader_actor WITH INHERIT FALSE, SET TRUE;

CREATE SCHEMA v3_cas_audit;
GRANT USAGE ON SCHEMA v3_cas_audit TO v3_cas_audit_reader;
CREATE TABLE public.paper_series(series_id text PRIMARY KEY,status text NOT NULL);
INSERT INTO public.paper_series VALUES ('PAPER-V2R4-20261009T110135Z','active');
CREATE TABLE v3_cas_audit.epoch_v1(epoch_id text PRIMARY KEY);
CREATE TABLE v3_cas_audit.intent_v1(intent_id uuid PRIMARY KEY);
CREATE TABLE v3_cas_audit.attempt_v1(state text NOT NULL);
CREATE TABLE v3_cas_audit.executor_inhibit_v1(epoch_id text PRIMARY KEY);
ALTER TABLE v3_cas_audit.epoch_v1 ENABLE ROW LEVEL SECURITY;
ALTER TABLE v3_cas_audit.epoch_v1 FORCE ROW LEVEL SECURITY;
ALTER TABLE v3_cas_audit.intent_v1 ENABLE ROW LEVEL SECURITY;
ALTER TABLE v3_cas_audit.intent_v1 FORCE ROW LEVEL SECURITY;
ALTER TABLE v3_cas_audit.attempt_v1 ENABLE ROW LEVEL SECURITY;
ALTER TABLE v3_cas_audit.attempt_v1 FORCE ROW LEVEL SECURITY;
ALTER TABLE v3_cas_audit.executor_inhibit_v1 ENABLE ROW LEVEL SECURITY;
ALTER TABLE v3_cas_audit.executor_inhibit_v1 FORCE ROW LEVEL SECURITY;
-- The newly added witness is installed ONLY in this disposable test DB.
\i __T0_SOURCE_CI_ONLY__

DO $acl$
BEGIN
 IF has_table_privilege('v3_cas_audit_reader','v3_cas_audit.attempt_v1','SELECT')
 OR has_table_privilege('v3_cas_audit_reader','v3_cas_audit.executor_inhibit_v1','SELECT')
 OR has_function_privilege('service_role','v3_cas_audit.read_forward_t0_current_v1()','EXECUTE')
 OR has_function_privilege('anon','v3_cas_audit.read_forward_t0_current_v1()','EXECUTE')
 THEN RAISE EXCEPTION 'V3_T0_READER_LEAKED_DIRECT_TABLE_OR_EXECUTE'; END IF;
END $acl$;

SET SESSION AUTHORIZATION v3_cas_audit_reader_actor;
-- LOGIN without explicit SET ROLE cannot call the private witness.
DO $actor_without_role$
BEGIN
 BEGIN
  PERFORM v3_cas_audit.read_forward_t0_current_v1();
  RAISE EXCEPTION 'V3_T0_DIRECT_ACTOR_EXECUTE_UNEXPECTED';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
END $actor_without_role$;
SET ROLE v3_cas_audit_reader;
-- Role grants execute but not raw underlying table SELECT.
DO $negative_direct_select$
BEGIN
 BEGIN
  PERFORM * FROM v3_cas_audit.attempt_v1;
  RAISE EXCEPTION 'V3_T0_DIRECT_ATTEMPT_SELECT_UNEXPECTED';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
END $negative_direct_select$;
DO $negative_inhibit_select$
BEGIN
 BEGIN
  PERFORM * FROM v3_cas_audit.executor_inhibit_v1;
  RAISE EXCEPTION 'V3_T0_DIRECT_INHIBIT_SELECT_UNEXPECTED';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
END $negative_inhibit_select$;
DO $positive_witness$
DECLARE evidence jsonb;
BEGIN
 evidence=v3_cas_audit.read_forward_t0_current_v1();
 IF evidence->>'kind' <> 'V3_CAS_FORWARD_T0_CURRENT_CATALOG_READONLY_V1'
 OR evidence->>'actor' <> 'v3_cas_audit_reader_actor'
 OR (evidence->>'active_series_count')::integer <> 1
 OR (evidence->>'attempt_count')::integer <> 0
 OR (evidence->>'inhibit_count')::integer <> 0
 OR evidence->>'t0_authenticated' <> 'false'
 OR evidence->>'complete_attempt_unknown_custody_authenticated' <> 'false'
 THEN RAISE EXCEPTION 'V3_T0_READER_CURRENT_NEGATIVE_OR_FALSE_RELEASE_HOLD'; END IF;
END $positive_witness$;
RESET ROLE;
RESET SESSION AUTHORIZATION;

-- A newer durable UNKNOWN remains visible through the narrow witness,
-- but never changes its T0 or continuity fields to an authorization.
INSERT INTO v3_cas_audit.attempt_v1 VALUES ('DISPATCH_UNKNOWN');
SET SESSION AUTHORIZATION v3_cas_audit_reader_actor;
SET ROLE v3_cas_audit_reader;
DO $unknown$
DECLARE evidence jsonb;
BEGIN
 evidence=v3_cas_audit.read_forward_t0_current_v1();
 IF (evidence->>'attempt_count')::integer <> 1
 OR (evidence->>'dispatch_unknown_count')::integer <> 1
 OR evidence->>'complete_attempt_unknown_custody_authenticated' <> 'false'
 OR evidence->>'armed_marker_cancel_authorized' <> 'false'
 THEN RAISE EXCEPTION 'V3_T0_UNKNOWN_MUST_BLOCK_RELEASE'; END IF;
END $unknown$;
RESET ROLE;
RESET SESSION AUTHORIZATION;
SELECT 'V3_T0_DISPOSABLE_PRIVATE_READER_ROLE_RLS_PASS' AS gate;
