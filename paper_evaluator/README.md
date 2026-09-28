# Paper V2R3 evaluator

Paper-only consumer for canonical files in `handoff_queue/`.

## Safety and methodology

- No private Kraken credential or order endpoint is used.
- `real_money_actions_enabled` is always false.
- Candidate identity is revalidated before evaluation.
- Decisions are idempotent by candidate ID.
- Scanner detection and strategy decisions remain separate.
- Raw scanner candidates are **not** user Slack alerts.
- BUY_SCOUT requires a valid structural stop and explicit second-stage confirmation trigger.
- Public Kraken pair status, cost minimum and order minimum are hard technical gates.
- Scout and stage 2 are simulated at 50 EUR each.
- Taker fee assumption is 0.60% per side.
- Open positions require contiguous Kraken 1-minute coverage. A gap produces `UNVERIFIED`, never a guessed result.
- Trailing tiers are defined in `paper_strategy_spec.json`.
- A finite 72-hour maximum hold closes otherwise unresolved paper positions.
- WAIT is revalidated once at TTL; WAIT -> BUY is excluded from missed-move statistics.
- REJECT/WAIT follow-up uses compact 1-minute Kraken OHLC at 30/60/120/360 minutes.
- Strategy revision, strategy fingerprint, evaluator model, repository SHA and code fingerprint are persisted.

## Data context

The evaluator can use:
- Kraken Spot EUR ticker and pair metadata,
- scanner cross-sectional breadth/rotation context,
- BTC/ETH/SOL Kraken market-regime proxies,
- Kraken Futures funding/open interest plus same-pair change when a prior observation exists,
- Binance derivatives only as an optional fallback,
- official Federal Reserve and SEC headlines.

Unavailable data remains explicitly unavailable. On-chain data and account-specific private
Kraken tradability are not fabricated.

The active series and measurement target are controlled by `paper_runtime_control.json`.
