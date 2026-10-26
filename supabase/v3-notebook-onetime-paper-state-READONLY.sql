-- V3 Paper Notebook: one manual READ-ONLY snapshot before/after the controlled CAS.
-- No grants, role changes, network services or CAS invocation. The user copies
-- the single notebook_snapshot JSON cell to a local file on the Notebook.
-- The laptop is a pragmatic second copy, NOT a WORM or auth certificate.
SELECT pg_catalog.jsonb_build_object(
 'kind','V3_PAPER_NOTEBOOK_SNAPSHOT_V1',
 'project_ref','nlgzjmqgwueojlyqmoru',
 'observed_at_utc',pg_catalog.to_char(
  pg_catalog.clock_timestamp() AT TIME ZONE 'UTC',
  'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
 'active_total',(SELECT count(*) FROM public.paper_series WHERE status='active'),
 'active_v2r4',(SELECT count(*) FROM public.paper_series
    WHERE status='active' AND series_id='PAPER-V2R4-20261009T110135Z'),
 'active_v3',(SELECT count(*) FROM public.paper_series
    WHERE status='active' AND series_id LIKE 'PAPER-V3%'),
 'audit_intent_count',(SELECT count(*) FROM v3_cas_audit.intent_v1),
 'cas_function_present',pg_catalog.to_regprocedure(
  'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
 ) IS NOT NULL
) AS notebook_snapshot;
