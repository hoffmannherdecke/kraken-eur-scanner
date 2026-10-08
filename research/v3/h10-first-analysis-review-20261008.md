# V3 H10 First Prospective Review — 2026-10-08

**Classification: MORE_TESTING_REQUIRED**  
**Strategy effect: none. H10 remains shadow-only.**

## Gate result

The preregistered first H10 analysis gate is mature: **131.53 h**, **199 capture batches**, **5,172/5,174 successful wallet requests (99.961%)**, **376 primary wallet/asset 30m windows**, and **21 primary multi-wallet same-asset 30m windows**. Every minimum in `V3-H10-ANALYSIS-GATE-001` is satisfied.

## Capture reliability / source lag

The capture layer is operationally strong. In the retained 48h exact-fill diagnostic window, Primary source-fill → first-seen lag is p50 **786.59 s**, p90 **1,882.00 s**, p99 **2,666.23 s**; Control p50 **768.14 s**, p90 **1,671.32 s**. This is consistent with the intentionally coarse 30-minute GitHub bootstrap. It is usable as lower-frequency context, **not** as a fast execution trigger.

## Primary vs active controls

Primary: 20 selected / 17 active wallets, 376 wallet-asset windows, **18.80 windows per selected wallet**, 4,093 fills (**204.65 fills per selected wallet**), 41 assets.  
Control: 6 selected / 5 active wallets, 110 wallet-asset windows, **18.33 windows per selected wallet**, 392 fills (**65.33 fills per selected wallet**), 27 assets.

Active-window frequency per selected wallet is therefore nearly the same, while Primary wallets trade much more densely. Multi-wallet same-asset clustering occurred in **21/347 = 6.05%** of active Primary asset-windows versus **2/108 = 1.85%** for controls. This is descriptive only; different cohort sizes and selection roles mean it is **not** yet a predictive-value result.

## Multi-wallet consensus structure

The 21 Primary multi-wallet events span: BTC 9, HYPE 3, LINK 3, NEAR 2, ZEC 2, ENA 1, and one non-simple Hyperliquid symbol `@107`.

Direction semantics are not clean enough for confirmatory scoring yet:
- 8/21 events (**38.1%**) are tied by independent-wallet count.
- Among 13 non-tie events, 2 (**15.38%**) have independent-wallet majority direction opposite to aggregate net-notional sign.

This means the next outcome join must freeze one deterministic direction rule before looking at Kraken outcomes.

## Why no Kraken predictive claim is made now

The frozen gate requested fixed-horizon Kraken-EUR MFE/MAE/close, one frozen false-positive label, lead-time and incremental comparison against Kraken price/volume/orderflow context. The current archive does **not** contain all prerequisites required to calculate those without post-hoc choices:

1. no per-event archived point-in-time Kraken Spot-EUR online mapping;
2. no dedicated contemporaneous Kraken market-context snapshot for all H10 events;
3. the gate names “one frozen outcome label” but does not define/materialize that label;
4. only **2/20** simple-symbol consensus events overlap existing Paper-candidate context within ±30m, **3/20** within ±60m.

Using only those overlapping candidates or inventing a label now would introduce selection bias. Therefore the evidence-only classification is **MORE_TESTING_REQUIRED**, not KEEP or REJECT.

## Decision

- Continue H10 capture unchanged.
- H10 remains **shadow-only**.
- No wallet re-selection, coin subset selection, threshold/horizon search, V2R4 change, V3 promotion, copy-trading or orders.
- Before any predictive claim, freeze a dedicated Kraken outcome/context join contract and then evaluate prospectively under that fixed contract.
