-- V3 experimental Paper / PRE-COMMIT / PRODUCTIVE CLOUD READ-ONLY INVENTORY.
-- Source-only SQL. NEVER a migration, CAS RPC, privilege grant or writer.
-- Original owner: existing Issue #99 and paper_series Supabase owner.
-- Execute with existing independently authorized production read-only access.
-- Do not interpret current observations as proof that a CAS was NEVER CALLED.
-- PostgreSQL transaction visibility only covers its current committed state.
select
 'V3_PRECOMMIT_CURRENT_CLOUD_INVENTORY_V1'::text as kind,
 pg_catalog.clock_timestamp() as observed_at_utc,
 (select count(*) from public.paper_series where status='active') as active_series_count,
 (select count(*) from public.paper_series where series_id='PAPER-V2R4-20261009T110135Z' and status='active') as exact_original_active_count,
 (select count(*) from public.paper_series where series_id like 'PAPER-V3-%') as recorded_v3_series_count,
 (select count(*) from public.paper_technical_rotations where successor_series_id like 'PAPER-V3-%') as recorded_v3_rotation_count,
 (select count(*) from public.strategy_release_decisions where successor_revision ilike 'V3%') as recorded_v3_release_decision_count,
 (select count(*) from pg_catalog.pg_proc p join pg_catalog.pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and p.proname='rotate_v2r4_to_v3_experimental_paper') as installed_v3_cas_function_count,
 (select count(*) from pg_catalog.pg_index ix join pg_catalog.pg_class idx on idx.oid=ix.indexrelid join pg_catalog.pg_namespace ns on ns.oid=idx.relnamespace where ns.nspname='public' and idx.relname='paper_series_single_active_idx' and ix.indrelid=pg_catalog.to_regclass('public.paper_series') and ix.indisunique and ix.indisvalid and ix.indisready and ix.indislive and pg_catalog.pg_get_expr(ix.indpred,ix.indrelid)='(status = ''active''::text)') as valid_single_active_index_count,
 false as historically_cas_never_invoked_proven,
 false as precommit_restore_authorized;
