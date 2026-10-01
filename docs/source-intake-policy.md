# External Source / App Intake Policy

Status: **ACTIVE GOVERNANCE / FAIL-CLOSED BY DEFAULT**  
Date: 2026-10-01

Canonical registry: `research/source-registry.json`.

A new external data source, app, connector, relay, market feed or research dataset
is not added merely because it is available. It must have a documented
incremental role and an explicit overlap/storage/failure policy.

## Required before adoption

Every source/app entry must state:

1. **Unique value** — what concrete information, timing advantage or robustness
   it adds that existing sources do not already provide adequately.
2. **Authority boundary** — what the source is authoritative for and what it is
   explicitly *not* authoritative for.
3. **Overlap strategy** — where data overlaps with existing sources and whether
   the overlap is intentional redundancy, validation/cross-checking, or should be
   avoided.
4. **Persistence mode** — what is stored, where, and why.
5. **Retention/provenance classification** — disposable cache/diagnostic versus
   immutable evidence/provenance.
6. **Access rights** — public read-only, authenticated read-only, transport-only,
   or another explicitly bounded permission set.
7. **Failure behavior** — whether failure is fail-soft, fail-closed, or blocks a
   release gate.
8. **Strategy scope** — context/sensor/state versus an actual strategy mechanic;
   a source does not silently become a buy/sell rule.

## Duplicate-storage rule

Raw market/news/app data must not be silently duplicated across MINI-PC, GitHub,
Supabase and another service.

Permitted overlap must have a purpose, for example:

- independent realtime trigger redundancy;
- compact decision provenance;
- immutable source archive plus reproducible normalized derivatives;
- short-lived diagnostic capture.

"Store it everywhere just in case" is not a valid purpose.

The retention rules in `docs/storage-retention-policy.md` remain binding.

## Authority examples

- Current Kraken public `AssetPairs` = live Kraken Spot-EUR universe truth.
- Kraken Spot EUR public data = execution-price/condition truth for this project.
- Binance derivatives = supplementary cross-market context, never Kraken EUR
  execution truth.
- Altrady = wakeup hint, never direct condition truth or direct-buy authority.
- Public Time & Sales = public trade prints, not historical order-book spread,
  queue position or maker fill probability.

## Adoption gate

Before a new source/app becomes active in a runtime:

- add/update its entry in `research/source-registry.json`;
- pass `tools/validate-source-registry.py`;
- perform the smallest safe end-to-end smoke appropriate to its role;
- prove failure behavior does not create stale decisions or a single point of
  failure unless explicitly intended;
- document any new persisted data and its retention/provenance rule;
- if strategy mechanics change, use a new strategy version/release gate rather
  than treating the source integration as an infrastructure-only change.

## Rights escalation

A source that works with public/read-only access must not receive account,
trading, write, withdrawal or administrative rights for convenience.

Any later rights escalation is a separate explicit security/release decision.

This policy does not authorize new sources or strategy changes by itself.
