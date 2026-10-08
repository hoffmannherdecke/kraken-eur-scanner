-- H10 view security hardening applied to the connected Supabase project on 2026-10-08.
-- Purpose: make all H10 public-schema analytical views explicit SECURITY INVOKER views.
-- Existing grants remain service-role only; anon/authenticated SELECT stays revoked.

alter view public.v3_h10_asset_consensus_30m set (security_invoker = true);
alter view public.v3_h10_asset_consensus_30m_history set (security_invoker = true);
alter view public.v3_h10_current_position_consensus set (security_invoker = true);
alter view public.v3_h10_wallet_asset_30m_history set (security_invoker = true);
alter view public.v3_h10_wallet_asset_activity_30m set (security_invoker = true);
