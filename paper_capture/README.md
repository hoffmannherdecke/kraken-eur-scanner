# Public market capture for the existing shadow test

Kraken market metrics and REST context are implemented in the shared
`market_data/` package. This directory is the Paper-only candidate-discovery,
capture-journal and artifact adapter; do not add another copy of any market
metric calculation here. The future live assessment is not wired and remains
disabled by `market_data/runtime.py`.

Technical data collection only. No account keys, order methods, Slack writes,
strategy logic, candidate scoring, or change to the existing scanner workflow.
The existing private test ledger remains the authority for decisions and counts.
Do not put private plans, amounts, fees, or account data into public artifacts.

`market.py` reads the existing scanner run logs, observes its EUR candidate
symbols, and records Kraken WebSocket v2 raw trade and book messages. BTC/EUR
is a technical connectivity probe, never an extra paper-test candidate.
Discovery runs every 60 seconds after scanner completion. Capture starts only
when subscription succeeds; earlier data is missing, never backfilled as precise.
All seen symbols remain subscribed for the session. New jobs rediscover prior
scanner posts since the existing cutoff. No candidate selection/count is changed.

Every wire message retains original numeric text, exchange timestamps, reception
wall-clock nanoseconds, monotonic time, session/connection and local sequence.
Order books use Decimal precision and check the CRC32 at every update. Raw top-10
depth permits a volume-weighted executable quote; insufficient depth is unknown.
Trade IDs detect sequence discontinuities. Snapshot trades are explicitly marked
and must not be used as fresh prospective triggers. Any reconnect starts a new
coverage segment and invalidates the old book until a new valid snapshot.

Artifacts contain a compressed JSONL hash chain and SHA256 manifest. They are
retained for 90 days, NOT permanently: MAIN must archive the raw evidence needed
for counted cases privately with the existing test record before expiry. A run
is not durable until its artifact upload succeeds. No log summary substitutes
for reading and verifying the raw artifact.

Hourly 70-minute sessions overlap nominally by 10 minutes. GitHub schedules are
best-effort: overlap is NOT a guarantee. Use actual per-symbol subscriptions,
acks, valid snapshots, connection ends, heartbeat/wire receipt and manifest times
to prove a case's full window. Cross-run dedup uses trade ID per symbol; books
must be reconstructed within their own session before comparing overlap.
Uncovered or ambiguous windows remain unauswertbar. No interpolation.

The controlled replay tests cover persisted activation, stage 1, stage 2, stop,
TTL, explicit revalidation/invalidation and subsequent price path. They are
synthetic technical fixtures and never enter the paper-trade count. `replay.py`
accepts explicit barriers; it does not implement the discretionary V2/ALT strategy.
Trailing stops, partial fills, resting-limit queue priority, same-tick multi-stage
liquidity, and discretionary changes require separate evidence/model handling.
Unsupported cases must remain unknown, not approximated as exact executions.

For actual case integration: first persist both decisions in the existing private
ledger (decision_at, persisted_at, valid_from, both stages, quantities, order type,
trigger source, limits, stop, TTL and reasons). Link each to scanner run/pair/time.
Record revalidation/non-price invalidation as new immutable timed decisions.
Then read the archived market tape and check coverage before replay. No activation
before persistence or before verified capture. Capture arrival is not a decision.

Trade timestamps and book timestamps are separate exchange streams, without a
common exchange sequence number. A local receive sequence alone does not prove
exchange matching-engine order. Ties, reordered/delayed messages, stale books or
ambiguous trigger-vs-book chronology need bounds or unknown status. Extra latency
slippage is an explicit prospective assumption; depth impact is measured from the
recorded book. Bid/ask already includes spread; do not charge spread twice.
Fees belong to private replay settings, on each fill's actual notional.

Official protocol references:
- https://docs.kraken.com/exchange/api-reference/spot-websocket-v2/book
- https://docs.kraken.com/exchange/api-reference/spot-websocket-v2/trade
- https://docs.kraken.com/exchange/guides/websockets/book-checksum-v2

Run controlled tests: `python -m unittest discover -s paper_capture -p 'test_*.py' -v`.
Live connectivity probe: `python paper_capture/market.py --seconds 60 --out probe --smoke`.
