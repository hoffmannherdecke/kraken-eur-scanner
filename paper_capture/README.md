# Public market capture — diagnostic only

This subsystem is a **manual diagnostic tool**, not part of the normal Paper runtime.

## Current operating mode

- No scheduled continuous raw capture.
- Normal Paper operation uses compact Kraken public data, persisted candidate decisions,
  1-minute position lifecycle data and compact follow-up files.
- A manual diagnostic capture runs for **5 minutes**.
- Diagnostic raw artifacts use **1-day retention**.
- The daily storage cleanup preserves fresh manual diagnostics and only removes stale leftovers.
- No account keys, private Kraken endpoints, order methods or real-money actions exist here.

Kraken WebSocket transport, market metrics and REST context are implemented in the shared
`market_data/` package. This directory is only the Paper diagnostic capture/replay adapter.

## Why raw capture is not continuous

Earlier long overlapping sessions generated multi-GB artifacts. That is unnecessary for
normal prospective Paper measurement and creates cost/storage/failure risk. Raw book/trade
capture is therefore reserved for investigating a concrete execution/data-quality question.

## Evidence quality

Every diagnostic wire message keeps exchange/reception timing and local sequence metadata.
Order books use Decimal precision and checksum verification. Reconnects create a new coverage
segment; ambiguous or uncovered windows remain unknown rather than interpolated.

The controlled replay tests are technical fixtures only. They never enter the live Paper
trade count and they do not define discretionary strategy rules.

For normal Paper positions, the lifecycle tracker uses Kraken 1-minute OHLC plus historical
spread observations when available. If required 1-minute coverage is not contiguous, the
position is marked `UNVERIFIED`; it is never silently reconstructed across a data gap.

Useful commands:

- Tests: `python -m unittest discover -s paper_capture -p 'test_*.py' -v`
- Live connectivity probe: `python paper_capture/market.py --seconds 60 --out probe --smoke`
- Manual bounded diagnostic: `python paper_capture/market.py --seconds 300 --out capture`
