-- Already applied and independently verified in Supabase production
-- during the 11 Oct V3 PAPER cloud staging. Persist exact runtime permission
-- hardening in main; no modification to paper_series or legacy V2R4.
-- Trigger rejects UPDATE/DELETE, but TRUNCATE requires explicit REVOKE too.
REVOKE UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
  ON TABLE public.v3_paper_event_receipts FROM service_role;
GRANT SELECT, INSERT ON TABLE public.v3_paper_event_receipts TO service_role;
-- Expected checks:
-- has_table_privilege('service_role','public.v3_paper_event_receipts','INSERT')=true;
-- same for SELECT true; UPDATE,DELETE,TRUNCATE all false.
