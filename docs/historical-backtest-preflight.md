# Historical Kraken / Backtest Preflight

Status: **PREPARED / CI VERIFIED / METADATA-ONLY / NO BULK DOWNLOAD**
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

## 11k. Windows checkout checksum mismatch caught before V1 execution 2026-10-01

The first physical MINI-PC launch of the frozen V1 replay stopped **before scanning any historical data** because the working-tree JSON file had Windows CRLF line endings while the frozen checksum had been computed from the repository LF representation.

Observed safety outcome:

- frozen-spec guard stopped the run before the performance replay began;
- no historical performance result was produced;
- no Trial Ledger performance entry was written;
- the user-entered `PERF_V1_SCAN ...` lines afterward were only mistaken copies of example progress text and had no effect on project state;
- active V2R3/V2R4 runtime remained unchanged.

Fix:

- frozen spec identity is now computed from UTF-8 text after LF line-ending normalization;
- validator, replay engine, Trial Ledger recorder and MINI-PC orchestrator use the same checkout-independent identity;
- CI now explicitly validates both LF and synthetic CRLF copies against the same frozen SHA-256;
- frozen spec content and thresholds were **not changed**;
- frozen identity remains `e8f82b9992228050188e334900b5ee35aeaa47111a526e38b1d0ae4234d33d27`;
- Historical data preflight **run #40: SUCCESS**.

The physical V1 execution may now be retried after pulling the fix.

## 11j. First performance-oriented replay V1 frozen and execution-ready 2026-10-01

After the physical broad PIT V2 methodology gate passed, the first performance-oriented historical replay was pre-registered **before** any aggregate real-data performance result was computed.

Frozen artifacts:

- spec: `research/historical/performance-replay-spec-v1.json`;
- lock: `research/historical/performance-replay-spec-v1.lock.json`;
- frozen spec SHA-256: `e8f82b9992228050188e334900b5ee35aeaa47111a526e38b1d0ae4234d33d27`;
- frozen baseline role: OHLCVT-only price×volume continuation event study;
- fixed 15m point-in-time features and fixed 4h horizon;
- fixed baseline cost model: 0.60% taker fee per side + 0.10% slippage proxy per side = 1.40% round trip;
- 2026-01-01 through 2026-06-30 remains a **sealed holdout** and is not read for V1 selection/results;
- no threshold sweep, pair ranking or parameter optimization is permitted in V1.

Prepared tooling:

- frozen-spec validator;
- local performance replay engine;
- immutable Trial Ledger recorder;
- guarded MINI-PC orchestrator with plan-only default and explicit execution token.

CI evidence:

- synthetic chronology spans research/calibration/validation windows;
- validation report generation PASS;
- sealed holdout generated **0 events** and **0 metrics**;
- immutable performance-trial recorder PASS and idempotency verified;
- MINI-PC orchestrator plan-only guard PASS;
- Historical data preflight **run #35: SUCCESS**.

Next physical gate: execute the frozen V1 replay on the actual normalized MINI-PC dataset, record its validation result immutably, and review that validation result **without opening the sealed holdout**.

## 11i. Physical broad PIT V2 methodology smoke verified 2026-10-01

The contiguous-wall-clock V2 replay and the deterministic broad methodology smoke were executed on the physical MINI-PC dataset.

Observed result:

- overall MINI-PC orchestrator status: **PASS**;
- V2 real-pair replay status: **PASS**;
- V2 contiguous eligible windows on the selected replay pair: **399,700**;
- normalized file count checked: **648**;
- pairs with at least one eligible contiguous history/future window: **461**;
- pairs skipped for insufficient contiguous windows: **187**;
- deterministically selected pairs: **12**;
- replay anchors per selected pair: **3**;
- total broad real-data methodology cases: **36**;
- future feature leakage cases: **0**;
- labels generated before decision freeze: **0**;
- non-contiguous history cases: **0**;
- non-contiguous future-horizon cases: **0**;
- unique decision hashes: **36**;
- Trial Ledger verification after V2 methodology append: **PASS**, corrupt IDs: **0**, trial count: **2**;
- no performance backtest was started;
- no network, active-strategy, Paper or Shadow runtime mutation occurred.

This closes the broad methodology gate. The next step is to freeze the first performance-oriented historical replay specification **before** any aggregate performance result is computed or inspected.

## 11h. Replay methodology V2 prepared after wall-clock semantic review 2026-10-01

Before expanding the historical replay, the V1 real-pair methodology was reviewed against the explicit no-gap-fill contract. A subtle semantic issue was identified:

- V1 was still point-in-time safe (no future bar leakage), but its labels/features such as "4 rows = 1h" and "12 rows = 3h" could span more wall-clock time if a pair had omitted no-trade intervals inside that row window.
- The already-recorded V1 Trial Ledger entry remains immutable and valid as **methodology/integrity evidence only**; it must not be reinterpreted as performance evidence.
- V2 therefore requires exact 15-minute contiguity for the feature history and future label horizon before a replay observation is eligible.
- A separate deterministic broad methodology smoke selects pairs/anchors without using performance labels and verifies the same invariants across multiple real-pair windows.

CI status:

- contiguous wall-clock real-pair replay V2: PASS;
- broad deterministic PIT methodology smoke: PASS;
- Historical data preflight run **#28: SUCCESS**.

Next physical gate: run V2 + the broad methodology smoke on the actual 648-pair normalized MINI-PC dataset before freezing any first performance-oriented historical replay specification.

## 11g. Real-pair methodology replay recorded immutably 2026-10-01

The physical MINI-PC replay was appended to the local immutable Trial Ledger.

Observed result:

- recorder status: **PASS_RECORDED**;
- Trial Ledger verification: no corrupt trial IDs;
- ledger trial count after append: **1**;
- trial ID: `REALPAIR-PIT-6C140F81717299F89A9C3`;
- decision hash retained: `6c140f81717299f89a9c285bafef6d4e4a2ae8461154e5cdab4a69b8e0c3e94b`;
- the record is explicitly tagged methodology/integrity-only and may not be interpreted as strategy-performance evidence;
- active V2R3/V2R4 runtime remained unchanged.

The immutable entry is retained even if later methodology revisions supersede it; revisions must create a new trial rather than overwriting this record.

## 11f. Physical MINI-PC EUR 15m normalization + real-pair replay verified 2026-10-01

The guarded normalization orchestrator was executed on the physical MINI-PC.

Observed result:

- overall orchestrator status: **PASS**;
- normalized files: **648**;
- total normalized OHLCVT rows: **20,960,798**;
- pairs with at least one preserved historical gap: **647**;
- total gap events preserved: **5,854,568**;
- total missing 15m intervals intentionally **not filled**: **31,577,413**;
- normalization catalog written to `Trading\\Historical\\catalog\\kraken-eur15-normalization.json`;
- methodology replay pair: `XBTEUR_15.normalized.csv.gz`;
- real-pair replay report status: **PASS**;
- decision hash: `6c140f81717299f89a9c285bafef6d4e4a2ae8461154e5cdab4a69b8e0c3e94b`;
- replay is explicitly methodology/integrity evidence only, not strategy-performance evidence;
- `network_used=false`;
- `raw_source_modified=false`;
- `active_strategy_changed=false`;
- `paper_shadow_runtime_changed=false`;
- next gate: record the real-pair replay immutably in the Trial Ledger, then begin a broader historical replay.

This closes the physical normalization gate. The large historical gap counts are expected to remain explicit because Kraken OHLCVT omits no-trade intervals and many listed pairs have discontinuous histories. No zero-filling or future-data synthesis is permitted.

## 11e. Redundant Kraken OHLCVT download parts removed 2026-10-01

The checksum-gated cleanup was executed on the physical MINI-PC after the final joined archive and selective EUR/15m extraction were both verified.

Observed result:

- cleanup status: **PASS**;
- source archive SHA-256 matched the pinned Kraken checksum before deletion;
- verified download parts found: **5**;
- reclaimable bytes: **8,972,380,104** (~**8.36 GB**);
- `deleted=true`;
- `parts_remaining=0`;
- final joined ZIP retained unchanged as immutable provenance;
- selective 648× EUR/15m raw extraction retained;
- `active_strategy_changed=false`;
- `paper_shadow_runtime_changed=false`.

This closes the redundant-part cleanup gate. The next historical-data step is the normalized point-in-time EUR/15m layer.

## 11d. Selective Kraken EUR 15m extraction verified 2026-10-01

The physical MINI-PC extraction completed successfully against the checksum-pinned full archive.

Observed result:

- progress reached **648/648**;
- final extractor status: **PASS**;
- extracted file count: **648**;
- CSV validation enabled: `validate_csv=true`;
- source archive SHA-256 matched the pinned Kraken full-archive checksum;
- destination: `Trading\\Historical\\raw\\kraken\\ohlcvt\\selected\\eur\\15m`;
- extraction catalog written under `Trading\\Historical\\catalog\\kraken-ohlcvt-eur15-extraction.json`;
- `network_used=false`;
- `active_strategy_changed=false`;
- `paper_shadow_runtime_changed=false`;
- next gate reported by the extractor: **normalize_eur15_point_in_time_dataset**.

This closes the selective raw-extraction gate. The original verified full ZIP remains the immutable provenance source. The five verified download parts are now redundant and may be removed through the checksum-gated cleanup tool before normalization work continues.

## 11c. Full Kraken OHLCVT archive inventory verified 2026-10-01

Read-only inspection of the verified full archive on the physical MINI-PC completed successfully:

- inspector status: **PASS**;
- ZIP integrity test: no bad member;
- CSV members: **12,035**;
- interval inventory includes **1,713 15-minute CSVs**;
- Kraken-EUR 15-minute members detected after aligning the inventory matcher with the extractor: **648**;
- archive MANIFEST present and parsed successfully;
- MANIFEST product: OHLCVT;
- no extraction performed;
- no active strategy/runtime changes;
- next gate reported by the inspector: **selective_eur_15m_extraction**.

The first inventory heuristic undercounted short compact Kraken pair symbols and reported 608; the extractor's fail-closed count exposed this before any extraction. The inventory matcher is now aligned to the extractor, yielding the correct physical-archive count of 648. This closes the archive naming/inventory gate. The next extraction must remain selective to EUR/15m and must preserve the original verified ZIP as the immutable provenance source.

## 11b. Full Kraken OHLCVT archive downloaded and verified 2026-10-01

The guarded downloader was executed on the actual MINI-PC against Kraken's official public 2026Q2 full-history OHLCVT archive.

Observed final result:

- all five archive parts downloaded and individually SHA-256 verified;
- parts 02/03/04 were visibly confirmed VERIFIED in the terminal output, and the script could only reach its final PASS report after all five part checks succeeded;
- joined archive SHA-256 matched the pinned Kraken full-archive checksum;
- final status: **PASS_ARCHIVE_VERIFIED_NO_EXTRACTION**;
- free disk before: **189.49 GB**;
- free disk after: **172.78 GB**;
- part files were deliberately retained for now (`parts_deleted_after_verification=false`);
- `downloads_performed=true`;
- `extraction_performed=false`;
- `active_strategy_changed=false`;
- `paper_shadow_runtime_changed=false`;
- next gate: archive inventory / MANIFEST inspection, then selective EUR 15m extraction only.

The temporary disk usage is intentionally higher because the verified part files and the reassembled archive currently coexist. After archive inspection succeeds, the redundant verified part files may be removed to reclaim space while retaining the final immutable ZIP + official checksum provenance.

## 11a. Physical MINI-PC local preflight verified 2026-10-01

The prepared local preflight was executed on the actual MINI-PC with `-Apply`.

Observed result:

- overall status: **PASS**;
- historical root created at `C:\\Users\\ADMIN\\Trading\\Historical`;
- all planned research directories created on C:;
- actual disk probe: **237.38 GB total / 47.89 GB used / 189.49 GB free**;
- metadata preflight: **PASS / errors=[]**;
- archive plan still estimates roughly **36 GB compressed** if both complete OHLCVT and Time & Sales families were ever enabled;
- `downloads_performed=false`;
- `active_strategy_changed=false`;
- `paper_shadow_runtime_changed=false`;
- trial ledger local init/verify was already **PASS** with 0 corrupt rows.

This closes the physical storage/layout preflight gate. It does **not** authorize a bulk download by itself. OHLCVT remains the only candidate for a first controlled historical download; full Time & Sales remains behind its separate benefit/storage gate.

## 12. Current status / next autonomous steps

Prepared and verified now:

- official-source snapshot/checksum facts recorded;
- no-download manifest added and CI-validated;
- local C:-storage layout fixed; drive D remains blocked;
- point-in-time contract fixed;
- chronological validation/search-accounting rules fixed;
- synthetic 15m fixture deliberately contains a no-trade gap;
- point-in-time smoke is green: closed-bar cutoff, no zero-fill, post-decision labels and deterministic output verified;
- immutable SQLite trial-ledger implementation + duplicate-trial rejection smoke are green;
- MINI-PC preparation script has a plan-only default and passed CI without creating data or downloading archives;
- Historical data preflight GitHub Action run #4: SUCCESS.

Current CI preflight estimates that enabling both complete compressed archive families later would imply roughly 36 GB of downloads before extraction. This is why Time & Sales remains behind a separate benefit/storage gate.

Additional guarded tooling now prepared and CI-verified:

- `tools/download-kraken-ohlcvt-full.ps1`: resumable official-part downloader with an explicit execution token, minimum-free-space gate, per-part SHA-256 verification, full joined-archive SHA-256 verification and **no automatic extraction**;
- `tools/inspect-kraken-ohlcvt-archive.py`: read-only ZIP/MANIFEST inventory for the next selective EUR/15m extraction gate;
- Historical data preflight GitHub Action run #8: **SUCCESS**, including plan-only downloader and synthetic archive-inspector smoke.

Current execution state:

- physical MINI-PC preflight: PASS;
- full official OHLCVT archive: downloaded and SHA-256 verified;
- archive inventory: PASS;
- selective EUR/15m raw extraction: PASS 648/648 with CSV validation;
- redundant download parts: deleted after checksum recheck, 8.36 GB reclaimed;
- deterministic point-in-time EUR/15m normalizer: CI PASS;
- real-pair point-in-time replay smoke: CI PASS;
- guarded MINI-PC normalization orchestrator: CI PASS (Historical data preflight run #24).

Next safe engineering work:

- execute the guarded normalization orchestrator on the physical MINI-PC;
- verify the resulting normalization catalog and real-pair replay report;
- append that real replay as an immutable search-accounting/trial-ledger entry;
- only then expand from methodology smoke to a broader historical replay;
- do not enable Time & Sales bulk download until OHLCVT replay proves a concrete need.

None of these steps changes V2R3/V2R4 runtime or strategy behavior.
