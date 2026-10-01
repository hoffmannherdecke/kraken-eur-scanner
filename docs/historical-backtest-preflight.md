# Historical Kraken / Backtest Preflight

Status: **PREPARED / METADATA-ONLY / NO BULK DOWNLOAD**
Date: 2026-10-01

This document defines the historical-data and backtest layer before any large
archive is downloaded. It is deliberately isolated from the active V2R3 clean
series, V2R4 shadow collection and all real-time MINI-PC runtimes.

## 1. Goals

The historical layer must answer questions that the live Paper/Shadow series
cannot answer quickly enough:

- whether scanner/evaluator features had repeatable historical edge;
- which filters prevented good moves and which prevented bad trades;
- continuation, pullback/re-entry and second-leg behavior after first detection;
- realistic MAE/MFE, entry/exit timing and fee/spread/slippage sensitivity;
- whether score/sizing tiers correlate with net edge;
- robustness across regimes and time rather than one favorable sample.

It must **not** silently tune V2R3 or V2R4 while those prospective tests run.

## 2. Official Kraken sources verified 2026-10-01

Kraken currently publishes downloadable public historical archives through
30 June 2026, plus quarterly incremental updates.

### OHLCVT

Full snapshot: Kraken_OHLCVT_Full_2026Q2.zip

- five approximately 2 GB parts;
- full-history cutoff: 2026-06-30;
- published full ZIP SHA-256:
  fc81b54cba6e12af3e9422dde9416179e6ef76af4831d48d839fbdb43018eaa4;
- pair CSV rows: timestamp, open, high, low, close, volume, trades;
- no header row;
- intervals include 1/5/15/30/60/240/720/1440 minutes;
- intervals with no trades are absent and must not be silently zero-filled.

Official source page:
https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data

### Time & Sales / public trades

Full snapshot: Kraken_Trades_Full_2026Q2.zip

- thirteen approximately 2 GB parts;
- full-history cutoff: 2026-06-30;
- published full ZIP SHA-256:
  554184802aa7367c02cfde9230411d0069ef5b0b4d6f9617c4ec1a7ec8726e16;
- one CSV per pair;
- columns: timestamp, price, volume, type, order_type, misc, trade_id;
- rows are ordered by timestamp.

Official source page:
https://support.kraken.com/articles/360047543791-downloadable-historical-market-data-time-and-sales-

The repository manifest is:
research/historical/kraken-historical-manifest.json.

## 3. Download policy

**Default remains NO DOWNLOAD.**

The preflight manifest has download_enabled=false for every large archive.
No workflow, CI job or normal runtime may download these files automatically.

Promotion sequence:

1. metadata/URL/checksum plan only;
2. parser + point-in-time semantics on synthetic/tiny fixtures;
3. local free-space check on MINI-PC;
4. OHLCVT archive first;
5. extract only required EUR pairs/intervals;
6. prove one small end-to-end historical replay;
7. only then decide whether full Time & Sales is justified.

Time & Sales is intentionally second because the full compressed archive is
roughly thirteen ~2 GB parts before extraction. It should initially be used only
for targeted fill/microstructure questions where OHLCVT cannot answer the
question.

## 4. Storage layout

Use the existing MINI-PC system drive only for now. **Do not use drive D** until
its separate backup/FAT32 repair task is completed.

Proposed root:

C:\\Users\\ADMIN\\Trading\\Historical\\

Layout:

- raw/kraken/ohlcvt/archives/ — immutable downloaded ZIP/parts;
- raw/kraken/trades/archives/ — immutable trade ZIP/parts;
- staging/ — temporary join/extract work, deletable;
- normalized/kraken/eur/ — selected normalized pair/interval partitions;
- catalog/ — manifests, checksums, source provenance, pair lifecycle metadata;
- derived/ — reproducible features/labels only;
- trials/ — trial ledger/search-accounting outputs;
- reports/ — compact backtest summaries;
- tmp/ — bounded disposable workspace.

Rules:

- never commit raw market data to GitHub;
- never copy full raw archives into Supabase;
- immutable raw archive + checksum is the provenance root;
- derived files must record the raw source checksum and generator version;
- temporary extraction is deleted after verified normalized partitions exist.

## 5. Initial data scope

Start with OHLCVT only.

First functional replay should use a very small EUR set and 15-minute data,
because that matches the legacy early sensor's main decision cadence. The smoke
is a parser/timestamp/reproducibility proof, **not a strategy result**.

After the replay is proven:

- add 1-minute data only where entry/stop/MAE/MFE precision needs it;
- add Time & Sales only for selected pairs/windows requiring fill/order-flow
  realism;
- keep higher intervals derived from the most appropriate source rather than
  duplicating unnecessary raw files.

## 6. Point-in-time contract

Every historical decision row must contain at least:

- event_time — market event/candidate time;
- data_cutoff_time — latest timestamp allowed into features;
- decision_time — simulated decision time;
- feature_schema_version;
- strategy_revision;
- runtime/code fingerprint;
- source archive + SHA-256;
- pair and pair/universe quality flag.

Hard rules:

1. No feature may use observations after data_cutoff_time.
2. Closed-candle features use only candles closed by the decision cutoff.
3. A live/incomplete candle is allowed only when the tested strategy explicitly
   used a live candle and the partial-bar cutoff is reconstructed.
4. Missing OHLCVT intervals mean no trade occurred; do not silently create a
   normal-volume zero candle.
5. Any synthetic gap-fill used for chart continuity must be explicitly flagged
   and excluded from volume/trade-count evidence.
6. Label horizons (future MFE/MAE/return) are generated only after the decision
   record has been frozen.
7. Historical pair membership must not be filtered by today's online Kraken
   universe. If exact historical listing/status metadata is unavailable,
   lifecycle is inferred from first/last observed data and marked
   INFERRED_FROM_MARKET_DATA.
8. Current Kraken AssetPairs remains the operational source for **live**
   tradability, not a survivorship filter for historical samples.

## 7. Cost / execution contract

Baseline backtest assumptions remain conservative and explicit:

- Kraken taker fee assumption: **0.60% per side** until a versioned alternative
  fee model is intentionally tested;
- spread measured from available point-in-time execution evidence where
  possible;
- OHLC-only tests must not pretend to know intrabar fill ordering;
- stop and target touched in the same bar => ambiguous unless lower-resolution
  data resolves the sequence; use fail-conservative handling;
- slippage model is versioned and reported separately;
- two-stage/scout entries must be simulated as two separate actions;
- no leverage.

Changing fee, slippage, fill priority, stop logic, feature set or sizing mapping
creates a new trial/configuration, never a silent overwrite.

## 8. Validation topology

Historical testing must be chronological:

1. **Research/train window** — hypothesis formation only.
2. **Calibration window** — thresholds/mapping.
3. **Validation window** — compare a frozen candidate.
4. **Purged/embargoed separation** — prevent label/feature overlap leakage.
5. **Sealed holdout** — opened once for the frozen candidate.
6. **Prospective Paper/Shadow** — final confirmation before promotion.

After a holdout has influenced a strategy decision, it is no longer a pristine
holdout for that strategy family.

## 9. Search accounting / trial ledger

Each tested variant gets an immutable trial ID and records:

- parent hypothesis/issue;
- code/strategy fingerprints;
- dataset snapshot/checksum;
- train/calibration/validation/holdout windows;
- features and parameters;
- fee/spread/slippage/fill model;
- stop/TTL/sizing configuration;
- outcome metrics;
- whether the trial influenced later design.

Parameter sweeps count as multiple trials. Later robustness work can therefore
apply FDR/Deflated-Sharpe/PBO or another explicit multiple-testing check instead
of reporting only the best in-sample result.

## 10. Minimal end-to-end smoke gate

Before any broad backtest:

1. verify raw archive checksum;
2. parse one small EUR pair/interval fixture;
3. build deterministic timestamp-normalized rows;
4. produce one feature row using only allowed prior data;
5. freeze one decision row;
6. generate future label/MFE/MAE afterward;
7. rerun and require byte/field-equivalent deterministic output;
8. verify deliberate future-data injection is rejected;
9. verify a missing/no-trade candle is not mistaken for a traded zero-volume
   candle;
10. write one trial-ledger row.

Only after this gate passes should the first meaningful historical strategy
experiment run.

## 11. Resource guardrails

- no full archive download from GitHub Actions;
- no raw archive in GitHub artifacts;
- no background bulk downloader yet;
- keep a substantial local free-space reserve before extraction;
- download parts/checksums first, join only after every part validates;
- extraction must be restartable and idempotent;
- Time & Sales bulk download requires a separate explicit storage-benefit
  decision after OHLCVT proves useful.

## 12. Current status / next autonomous steps

Prepared now:

- official-source snapshot/checksum facts recorded;
- no-download manifest added;
- local storage layout fixed;
- point-in-time contract fixed;
- chronological validation/search-accounting rules fixed;
- minimal smoke gate fixed.

Next safe engineering work:

- validate the manifest in CI without downloading archives;
- add small synthetic parser/point-in-time fixtures;
- create the trial-ledger schema;
- build a metadata-only/local-disk preflight command.

None of these steps changes V2R3/V2R4 runtime or strategy behavior.
