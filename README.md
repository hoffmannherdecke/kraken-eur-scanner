# Kraken EUR Early Sensor

Read-only 15-minute early-momentum sensor for **Kraken Spot EUR** markets. It uses only Kraken public market-data endpoints. It does **not** hold a Kraken API key and cannot place trades.

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

## GitHub setup

Use a **public repository** if you want standard GitHub-hosted Actions to remain free. Public repo code/state is visible, so never put secrets in code.

Create one repository secret:

`Settings -> Secrets and variables -> Actions -> New repository secret`

Name: `SLACK_WEBHOOK_URL`

Value: the Incoming Webhook URL for `#krypto-signale`.

Do not paste that URL into source files or chat.

The repository is deliberately configured **manual-only for the first live validation**. After a successful end-to-end test, the schedule is enabled at :07, :22, :37 and :52 minute-of-hour.

## Important GitHub limitation

GitHub documents that scheduled workflows in public repositories can be automatically disabled after 60 days without repository activity. Keep this on the maintenance checklist.

## Local test

```bash
python -m unittest discover -s tests -v
```

No third-party Python packages are required.
