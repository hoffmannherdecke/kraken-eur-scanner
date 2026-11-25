# KRYPTO App 0.5
Static PWA only, derived from notebook-proven 0.4. Public frontend; data access remains authenticated by existing krypto-app-read API. No access code, snapshot or credential is included. No offline caching of trading data. Deploy this branch root via GitHub Pages (HTTPS). The app updates on subsequent page loads; change version query strings for JS/CSS on updates. No changes to trading main. Canonical project decision #353/7156940581 and deployment #353/7157132218.

## 0.6
Writer status uses the existing MINI-PC cloud report, with a 10-minute freshness limit (5-minute existing upload cadence). Positive results are historical confirmations, failure or stale data is clearly shown. API v2 adds only the existing check. No new runtime monitor, scheduler or trading action.

## 0.7
Trade view on unchanged API v2: 24-hour entry/exit receipt counts, recent available trade decisions, explicit absence of live position inventory and net P&L. No realized results inferred from followup estimates. The separate richer ledger backend is not deployed.

## 0.8
Market tab reads only existing public GitHub research Issue #7 phase-change records and the existing source registry / research candidate catalog, on first opening or explicit refresh. Distinguishes historical phase changes from current market phase, registered source roles from runtime use and source quality. No credential is sent to GitHub. No change to Cloud API v2, trader, scheduler, or source routing. Market parser supports both existing episode formats; bounded latest comment pages, not full history.
