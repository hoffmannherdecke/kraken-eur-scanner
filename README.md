# KRYPTO App 0.5
Static PWA only, derived from notebook-proven 0.4. Public frontend; data access remains authenticated by existing krypto-app-read API. No access code, snapshot or credential is included. No offline caching of trading data. Deploy this branch root via GitHub Pages (HTTPS). The app updates on subsequent page loads; change version query strings for JS/CSS on updates. No changes to trading main. Canonical project decision #353/7156940581 and deployment #353/7157132218.

## 0.6
Writer status uses the existing MINI-PC cloud report, with a 10-minute freshness limit (5-minute existing upload cadence). Positive results are historical confirmations, failure or stale data is clearly shown. API v2 adds only the existing check. No new runtime monitor, scheduler or trading action.

## 0.7
Trade view on unchanged API v2: 24-hour entry/exit receipt counts, recent available trade decisions, explicit absence of live position inventory and net P&L. No realized results inferred from followup estimates. The separate richer ledger backend is not deployed.

## 0.8
Market tab reads only existing public GitHub research Issue #7 phase-change records and the existing source registry / research candidate catalog, on first opening or explicit refresh. Distinguishes historical phase changes from current market phase, registered source roles from runtime use and source quality. No credential is sent to GitHub. No change to Cloud API v2, trader, scheduler, or source routing. Market parser supports both existing episode formats; bounded latest comment pages, not full history.

## 0.9
Learning tab: existing Cloud API v2 for 24h candidate/entry/exit evidence and bounded decision list; existing public original historical V2R3/V2R4 reviews, V3 lesson matrix, policy bundle and dated operational release snapshot. Design, operational milestone, current evidence and economic proof are separated. No new permissions, API, model, scheduler, or runtime changes; no followup/position/net-result completeness claims. Read-only GitHub fetch on first open/manual refresh. Logout clears learning display and discards in-flight results. Six tabs wrap on small screens.

## 0.10
In-app lease preparation notice on the overview only when the existing project controller's <=72h rule is due, or the last documented expiry has passed. System shows the last documented lease, verified from the existing public #99 current owner marker and matching original comment, bound to the active Cloud API v2 series. No runtime authorization claim; missing, stale, mismatched evidence is unknown. The existing open-app refresh piggybacks a bounded owner read at most once per 15 minutes per series; no additional timer or background job. Existing Slack/iPhone alert router stays unchanged; no new native app push or duplicate routing. No secrets sent to GitHub.

## 0.11
System tab: local, copyable review-request drafts for pause of new entries, controlled HOLD, authorized resumption and configuration review. Current unambiguous V3 Cloud series and recent snapshot required; no remote command or POST, no execution approval, no new credentials, no host changes. Existing #99/#353 and working chat remain the only execution route. Old V2R4 STOP and read-only PaperResume are not reused as controls. Direct control and safe selective entry-pause contract remain open. Draft is cleared on logout or changed series.

## 0.13
Existing 60s foreground Cloud refresh also calls market refresh (phase max every 15 minutes, catalogs hourly) and public Kraken EUR ticker (one batch max 15 pairs including BTC ETH SOL, cached AssetPairs for 1h). Only when market section visible; no added scheduler or timer except request timeouts. Public symbols only to Kraken, no App code. Charts on demand: last up to 24h of closed 15m candles, final uncommitted candle removed, gaps not bridged, separate decision evidence. Market/quotes reset on logout; no new Cloud API, no trading writes, no position or net P&L derivation. Mobile layout tweaks. 10 isolated parser/data tests PASS; live browser CORS, chart and iPhone acceptance pending. No push, no actual entry signal price from API v2.
