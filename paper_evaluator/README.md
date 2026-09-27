# Paper V2 evaluator

Paper-only consumer for canonical files in `handoff_queue/`.

Safety invariants:
- test ID remains `SHADOW-V2-20260924-01`;
- frozen V2 principles from 24 Sep 2026 are not auto-optimized;
- no private Kraken credential is used;
- no Kraken order endpoint exists here;
- `real_money_actions_enabled` is always false;
- candidate identity is revalidated before evaluation;
- decisions are append-only by candidate ID and therefore idempotent;
- OpenAI gets one retry only;
- DUSK/EUR, QNT/EUR and TION/EUR remain blocked;
- a BUY_SCOUT is only a simulated paper fill at the fresh public Kraken best ask;
- no extra slippage number is invented when no executable depth/slippage measurement is available.

The evaluator intentionally separates scanner detection from strategy decisions. WAIT and REJECT are first-class outcomes and are persisted so missed moves can be audited later.
