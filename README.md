# KRYPTO App 0.5
Static PWA only, derived from notebook-proven 0.4. Public frontend; data access remains authenticated by existing krypto-app-read API. No access code, snapshot or credential is included. No offline caching of trading data. Deploy this branch root via GitHub Pages (HTTPS). The app updates on subsequent page loads; change version query strings for JS/CSS on updates. No changes to trading main. Canonical project decision #353/7156940581 and deployment #353/7157132218.

## 0.6
Writer status uses the existing MINI-PC cloud report, with a 10-minute freshness limit (5-minute existing upload cadence). Positive results are historical confirmations, failure or stale data is clearly shown. API v2 adds only the existing check. No new runtime monitor, scheduler or trading action.
