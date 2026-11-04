-- Read only; run in a NEW connection after the one-time epoch transaction.
SELECT pg_catalog.json_build_object(
 'kind','V3_STAGE4_EPOCH_COMMITTED_READBACK_V1',
 'observed_at_utc',pg_catalog.clock_timestamp(),
 'epoch_count',(SELECT count(*) FROM v3_cas_audit.epoch_v1),
 'epoch_id',(SELECT epoch_id FROM v3_cas_audit.epoch_v1 LIMIT 1),
 'source_sha256',(SELECT source_sha256 FROM v3_cas_audit.epoch_v1 LIMIT 1),
 'original_fence_sha256',(SELECT original_fence_sha256 FROM v3_cas_audit.epoch_v1 LIMIT 1),
 'approved_caller_acl_sha256',(SELECT approved_caller_acl_sha256 FROM v3_cas_audit.epoch_v1 LIMIT 1),
 'predecessor_series_id',(SELECT predecessor_series_id FROM v3_cas_audit.epoch_v1 LIMIT 1),
 'expected_rpc',(SELECT expected_rpc FROM v3_cas_audit.epoch_v1 LIMIT 1),
 'next_ordinal',(SELECT next_ordinal FROM v3_cas_audit.epoch_v1 LIMIT 1),
 'sealed',(SELECT sealed FROM v3_cas_audit.epoch_v1 LIMIT 1),
 'intent_count',(SELECT count(*) FROM v3_cas_audit.intent_v1),
 'attempt_count',(SELECT count(*) FROM v3_cas_audit.attempt_v1),
 'inhibit_count',(SELECT count(*) FROM v3_cas_audit.executor_inhibit_v1),
 'abort_count',(SELECT count(*) FROM v3_cas_audit.prepared_fence_abort_v1),
 'postgres_temp_insert',(SELECT pg_catalog.has_table_privilege('postgres','v3_cas_audit.epoch_v1','INSERT')),
 'postgres_temp_set_owner',(SELECT pg_catalog.pg_has_role('postgres','v3_cas_audit_table_owner','SET')),
 'predecessor_active',(SELECT count(*) FROM public.paper_series WHERE status='active' AND series_id='PAPER-V2R4-20261009T110135Z')
)::text;
