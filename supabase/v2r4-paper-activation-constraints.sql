-- Enforce the invariant that at most one paper series is active at any time.
-- V2R4 activation closes the completed predecessor before inserting its successor.
create unique index if not exists paper_series_single_active_idx
  on public.paper_series ((status))
  where status = 'active';
