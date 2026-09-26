# Kraken EUR Early Sensor

The Paper market capture imports the mode-independent, public Kraken market
data implementation from `market_data/`. Paper and any future assessment
consumer must use the same book, order-flow, wall, candle and descriptive-label
calculations. The live assessment and real-money action gates remain disabled;
see `market_data/README.md`.

Read-only early-momentum sensor for **Kraken Spot EUR** markets using 15-minute candles. It uses only Kraken public market-data endpoints. It does **not** hold a Kraken API key and cannot place trades.

## What it does

1. Gets the current Kraken tradable-pair list and keeps only `online` Spot EUR pairs.
2. Uses batched ticker data to remove clearly illiquid/wide-spread markets.
3. Uses a timing guard so a delayed job does not normally scan across a 15m candle boundary, then fetches 15m OHLC sequentially at ~1 request/sec.
4. Computes live/closed 15m momentum, 1h/3h/24h returns, volume acceleration, rank/rank jump, 3h breakout/base structure, higher lows, EMA26/50, ADX14 and fresh impulse distance.
5. For plausible candidates only, adds 7d/30d context from 1h candles and shallow order-book depth.
6. Sends at most three structured **review-only** candidates to Slack. The Slack message explicitly says `REVIEW_ONLY_NOT_ORDER`.
7. Uses a small GitHub Actions cache for N-vs-N-1 ranks and cooldown/dedup state.

## Safety / fail-closed rules

- No Kraken EUR pair / not `online` => never scanned.
- Low turnover, >1.5% ticker spread or stale OHLC => hard sensor veto.
- <80% OHLC coverage => entire run fails closed and sends no candidate.
- Fresh 3h move >12% is marked late and is not sent as a new early candidate.
- Missing 7d/30d or depth data is a warning, not an automatic veto.
- Same pair is suppressed for 45 minutes unless the signal improves materially.
- Slack is a sensor feed only. Final buy/stop/size decisions remain in the ChatGPT strategy using fresh Kraken-EUR execution data.

## Production schedule

Current production schedule: **:07 and :37 each hour** (UTC minute-of-hour; therefore the same minute values in Europe/Berlin), i.e. approximately every 30 minutes. GitHub scheduled runs are best-effort and can start late.

A manual `workflow_dispatch` remains available for troubleshooting.

## Chat-first operating model

ChatGPT Work is not a runtime dependency of the scanner or Paper market capture.
GitHub performs the continuous machine work: scanning, Kraken market-data capture,
telemetry and evidence retention. Each scanner run writes a small machine-readable
`chat-handoff-<run>-<attempt>` artifact containing only candidates actually handed
off for review, their scanner feature snapshot and fresh public Kraken decision
context. It contains no account credentials, private Paper ledger data or order
instructions.

The normal ChatGPT chat can read these compact artifacts for Paper/Shadow review.
Paper decisions are persisted separately in the private append-only ledger.
Work is reserved for occasional repository/code changes rather than continuous
monitoring or strategy evaluation.

To reduce routine runtime and log volume, the scanner's full unit/regression suite
runs on repository changes or manual troubleshooting, not on every scheduled scan.
This does not change scanner thresholds, candidate selection or safety gates.

## Package integrity

The scanner package is stored as Base64 text chunks under `.payload/`. Every run reconstructs the ZIP and verifies this SHA-256 before execution:

`601c00f35a2df01a0f8c28c2cdf463629d7a77450043ea61f174b0b535ae18f6`

It also runs `unzip -t` and the full unit/regression suite before touching live Kraken data.

## Live validation 2026-09-21

- Initial live run correctly failed on a corrupt binary ZIP transfer. No market scan or Slack candidate was allowed to continue.
- Transport was replaced by checksum-verified Base64 chunks.
- Second live run: package checksum OK, ZIP integrity OK, **14/14 regression tests passed**, Kraken live scan succeeded.
- Kraken live universe: **495 EUR pairs**, **61** survived the initial liquidity/spread stage, **100% OHLC coverage (61/61)**.
- End-to-end Slack delivery to `#krypto-signale` was confirmed with real structured `SCANNER_CANDIDATE_V1` messages.
- The GitHub secret remained masked in logs.

## GitHub secret

One repository secret is required:

`SLACK_WEBHOOK_URL`

It contains the Incoming Webhook URL for `#krypto-signale`. Never place it in source code or chat.

## Important GitHub limitation

GitHub documents that scheduled workflows in public repositories can be automatically disabled after 60 days without repository activity. Keep this on the maintenance checklist.

## Local test

```bash
python -m unittest discover -s tests -v
```

No third-party Python packages are required.


## Audit telemetry

Each production run writes machine-readable `AUDIT_ROW` lines for the complete liquid stage-2 universe and an `AUDIT_POSTED` line after each successful Slack candidate delivery. It also records cooldown suppressions in rolling scanner state. This does not change scoring, selection, cooldowns, or Slack behavior.

A separate workflow, **Kraken missed-move audit**, runs daily at 03:18 UTC. It reads the rolling telemetry without ChatGPT Work usage, measures the following six-hour Kraken-EUR move using 15-minute OHLC, and classifies strong early moves as scanner-posted, score-filtered, top-3-capped, cooldown-suppressed, or unresolved. Reports are stored as a 30-day GitHub Actions artifact.

The audit is diagnostic only. It never changes scanner thresholds automatically and never places orders.
