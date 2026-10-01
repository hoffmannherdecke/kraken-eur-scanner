# MASTER VERSION REGISTER — Aktien & Krypto Chancen

Status: **KANONISCHE KOMPONENTEN-/VERSIONSÜBERSICHT**  
Stand: 2026-09-29  
Zweck: Single Source of Truth für Strategie, Paper, Infrastruktur, Datenpfade und Integrationen.

## Governance

- Kein relevanter Bestandteil wird nur über Chat-Erinnerung verwaltet.
- Dauerhaft projektrelevante Informationen aus Gesprächen werden proaktiv kanonisch dokumentiert, auch wenn der Nutzer nicht ausdrücklich „merk dir das“ sagt. Dazu zählen insbesondere Entscheidungen, Anforderungen, neue Daten-/Informationsquellen, Hypothesen, Testregeln, offene Punkte, Fehlerursachen, Architektur-/Strategieänderungen und verbindliche Arbeitsprinzipien. Reine Zwischenüberlegungen oder verworfene Ideen werden nur dann dauerhaft aufgenommen, wenn sie für die Nachvollziehbarkeit relevant sind.
- **Autonome Arbeitsregel (verbindlich, 2026-10-01 nachgeschärft):** Innerhalb des bereits freigegebenen Projektumfangs arbeitet ChatGPT selbstständig und ohne erneute Zwischenfreigaben weiter, solange keine zwingende Nutzeraktion erforderlich ist. Kein Stoppen nach jedem Teilresultat, kein „Soll ich weitermachen?“, kein Warten auf ein Okay. Nach jeder vom Nutzer geleisteten Hilfestellung wird automatisch weitergearbeitet.
  - Wenn ein Pfad vorübergehend blockiert ist (z. B. CI läuft, Evidenz muss reifen, externer Dienst wartet), wird parallel an anderen unabhängigen offenen Punkten weitergearbeitet statt untätig zu warten.
  - Nutzerinteraktion wird möglichst gebündelt: mehrere lokale Prüfungen/Schritte nach Möglichkeit in einen einzigen sicheren Befehl oder ein einziges physisches Gate packen.
  - Der Nutzer wird erst aktiv benötigt bei zwingend physischem MINI-PC-/Netzwerk-/BIOS-/Gerätezugriff, Account-/Login-/Secret-Handhabung, einer tatsächlich erforderlichen UI-Bestätigung oder einer Entscheidung, die bewusst außerhalb bestehender Release-/Sicherheits-Gates liegt.
  - Bestehende Schutzgrenzen bleiben trotz Arbeitsfreigabe verbindlich: keine Echtgeldorder, keine Auszahlungsrechte, keine stille Strategie-/Threshold-Änderung, keine Promotion einer neuen Strategieversion ohne das dokumentierte Release-Gate, keine absichtlich destruktive Daten-/Repo-Aktion ohne vorherigen Sicherheits-/Rollback-Punkt.
  - Zwischenstände werden nicht als Rückfrage verwendet. ChatGPT meldet sich proaktiv nur bei einem echten Nutzer-Gate, einem relevanten Fehler/Blocker, einem definierten Abschlussereignis oder einem sinnvollen kompakten Meilenstein.
- Jede Mechanik-/Infrastrukturänderung erhält eine eindeutige Version oder einen dokumentierten Draft.
- Eingefrorene Referenzstände bleiben unverändert.
- Unklare Zuordnungen werden als **NICHT VERIFIZIERT / ZUORDNUNG OFFEN** markiert; niemals raten.
- Vor einem Release: aktuelle Version vollständig auswerten → Erkenntnisse klassifizieren → relevante Erkenntnisse migrieren → Smoke-Test → Freigabe → Rollback-Punkt.
- Strategie- und Infrastrukturversionen werden getrennt geführt und miteinander verknüpft.
- V3 gilt erst dann als vollständig integriert, wenn jeder relevante V2/V2R4-Baustein einen Migrationsstatus besitzt.

## Strategie / Paper

| Komponente | Version / ID | Status | Rolle / nächste Aktion |
|---|---|---|---|
| Strategie | `V2R3-2026-09-28` | ACTIVE / PAPER / FROZEN | Aktive Vergleichsbasis; Regeln während Serie nicht ändern |
| Paper-Serie | `PAPER-V2R3-CLEAN-20261001T0925Z` | ACTIVE / CLEAN / PERSISTENCE E2E VERIFIED | Aktuelle homogene V2R3-Serie nach Runtime-only Persistenzrepair; erster realer 3-Kandidaten-Cycle im selben Lauf committed, Repeat-Guard danach 0 Reselections/0 No-op-Follow-up-Changes; Process-Health 3/3 Provenance, 0 Orphans. Strategie `V2R3-2026-09-28` unverändert. |
| Paper-Serie predecessor | `PAPER-V2R3-FINAL-20260928T1752Z` | DIAGNOSTIC_COMPROMISED / FROZEN | 708 Candidate-Outcomes bleiben für Fehler-/Missed-Move-/Timinganalyse nutzbar, aber nicht als saubere prospektive Abschlussserie; Persistenzbug am 2026-10-01 nachgewiesen und repariert. |
| Strategie | V2R4 | PREPARED / NOT ACTIVE / PHYSICAL MINI-PC E2E GREEN | Draft-PR #8; compile/unit/live evaluator/model-contract/public Kraken + exact Windows and physical MINI-PC trigger→fresh-recheck gates green; local OpenAI secret provisioned; Altrady synthetic and real transport E2E verified; separate V2R4 paper-activation decision still open |
| Strategie | V3 | ACTIVE RESEARCH / NOT ACTIVE TRADING | Integrierter Nachfolger; Issue #7 + `docs/v3-research-framework.md` |

### Release-Gate V2R3 → V2R4

Vor V2R4-Aktivierung zwingend:
1. V2R3 restlos und gründlich auswerten.
2. BUY/WAIT/REJECT/NO-TRADE, verpasste Chancen, Fehler, Latenzen, MFE/MAE, Kosten/Spread/Slippage und Infrastrukturprobleme berücksichtigen.
3. Erkenntnisse klassifizieren: bestätigen / ändern / neu / verwerfen / weiter testen.
4. Belastbare Erkenntnisse in V2R4-Spezifikation übernehmen.
5. Offene Hypothesen dokumentiert weiterführen.
6. Mini-PC-Infrastruktur separat per V2R3-Shadow/Smoke testen.
7. V2R4 erst danach als eigene Paper-Serie starten.

### Aktuelle neue Erkenntnis 2026-09-29

**„Ersten Impuls verpasst“ ≠ „Trade verpasst“.**  
Pflicht für Auswertung und nächste Version:
- Zeitachse: Bewegungsbeginn → Scanner-Erkennung → Entscheidung → realistischer Entry → weiterer Verlauf.
- Follow-up mindestens 15m / 1h / 4h / 12h / 24h, bei Bedarf mehrere Tage.
- MFE/MAE nach tatsächlicher Erkennung.
- Klassifikation: wirklich zu spät / Continuation / Pullback-Re-Entry / Second Leg / mehrstündiger Trend / korrekt kein Trade / Systemfehler.
- Scanner-Latenz getrennt von zu restriktiver Entry-/Revalidation-Logik messen.
- V2R4: als verpflichtende Mess-/Revalidation-Anforderung und – sofern vor Freigabe validiert – als explizite Paper-Entry-Variante aufnehmen.
- V3: Pflichtpunkt im Migrationsledger.
- **Runtime-Messung seit 2026-09-29 aktiv:** `paper_followup.py` führt zusätzlich einen rein beobachtenden Post-Detection-Opportunity-Audit für WAIT/REJECT der aktiven V2R3-Serie. Er speichert Scanner-Erkennung, Evaluationslatenz, Detection-Preis, einen explizit als Proxy markierten Vorimpuls-Anker sowie MFE/MAE/Endkurs nach 15m / 1h / 4h / 12h / 24h. Die V2R3-Entscheidungs-, Entry-, Stop- und Sizing-Logik bleibt unverändert; der Evaluator-Fingerprint umfasst diesen Follow-up-Code nicht.

## Infrastruktur

| Komponente | Version / Stand | Status | Verknüpfung |
|---|---|---|---|
| Mini-PC Hardware | Dell OptiPlex 5060 Micro, i5-8500T, 16 GB, 256 GB SSD | RECEIVED / BASE CONFIGURED | Windows/LAN/RDP/Git/Python/venv + read-only Kraken smoke verified; remaining physical/recovery/integration gates in Mini-PC runbook |
| Betriebssystem | Windows 11 Pro, Build 26200 | VERIFIED | lokaler Sammeltest / next-gate |
| Netzwerk lokal | LAN über FRITZ!Box 7590 AX | ACTIVE / VERIFIED | lokaler Kraken HTTPS/WebSocket-Smoke erfolgreich |
| Interner Fernzugriff | Windows RDP im LAN | ACTIVE | MINI-PC während Einrichtung erfolgreich per RDP administriert |
| Externer Fernzugriff | FRITZ!Box-VPN/WireGuard → internes RDP | ACTIVE / EXTERNAL E2E VERIFIED | echter Außentest 2026-10-01 über Mobilfunk/iPhone-Hotspot bestanden; WireGuard aktiv, RDP auf MINI-PC `192.168.178.179` ohne Einschränkungen; kein direktes RDP-Portforwarding |
| Stromausfall-Recovery | Dell BIOS AC Recovery = Power On | ACTIVE / VERIFIED | echter Stromverlust-/Umplatzierungs-Test bestanden; automatischer Boot ohne Tastendruck, RDP danach wieder erreichbar |
| Watchdog/Recovery | lokaler Supervisor + unabhängiger GitHub-Fallback | CLOUD VERIFIED / LOCAL BASELINE ACTIVE | GitHub-Watchdog + Startup-Recovery aktiv; lokale SYSTEM-Tasks alle 5 Min + Startup und tägliche Log-Bereinigung 04:20 installiert; Immediate Health exit 0; prozessspezifischer Self-Heal folgt erst mit lokaler Runtime |
| Backup/Restore | lokales State-Backup + Restore-Smoke | ACTIVE / VERIFIED | 04:00 daily, 14-day retention, no Secrets/Logs/Repo; immediate seed + restore smoke passed locally; watchdog warns only after 7 days without backup |
| Externer Datenträger | `D:` / `Mistral_450`, ~304 GB frei | ATTACHED / DEFERRED TO FINAL RUNBOOK PHASE | physische Platte Healthy, FAT32-Volume mit logischen Fehlern; wichtige Altdateien vorhanden; Sicherung/Reparatur bewusst erst ganz am Ende, bis dahin keine aktive Projektablage |
| Kraken local realtime data | Public WebSocket v2 book + trades via isolated venv | ACTIVE / SMOKE VERIFIED | 45s local smoke: 1544 verified book events, 103 trades, 0 gaps, 0 subscription errors; public/read-only only |
| Kraken runtime canary | continuous BTC/EUR public WebSocket heartbeat | ACTIVE / LOCAL+CI VERIFIED | SYSTEM startup task running; heartbeat HEALTHY; watchdog check HEALTHY; 0 gaps / 0 subscription errors at activation; transport-only, no account/order/strategy action |
| V2R4 local recheck gate | deterministic trigger → fresh paper evaluator recheck | PHYSICAL MINI-PC + WINDOWS-CI E2E VERIFIED | physical MINI-PC gate passed with fresh Kraken trigger, real OpenAI paper evaluator and paper-only safety; observed local trigger→recheck start 0.228 s, evaluator runtime 12.348 s; no order API/real money |
| Altrady | zusätzlicher Echtzeit-Trigger | REAL ALERT E2E VERIFIED / TRANSPORT ACTIVE | Supabase Edge Function `altrady-trigger-relay` ACTIVE; gemeinsames Secret gesetzt; `CryptoMiniPC-AltradyTrigger` läuft; synthetic relay→MINI-PC→ack smoke PASS and real one-shot Price Alert verified. Real event 2026-09-30 22:49:22 UTC → relay 22:49:24.244 UTC → MINI-PC ack 22:49:27.541 UTC; about 2.244 s event→relay, 3.297 s relay→ack, 5.541 s event→ack. Strategy action remains NONE_TRANSPORT_ONLY; explicit Fresh-Recheck coupling still separate; never sole trigger/SPOF. |
| Kraken realtime | Public REST/WebSocket lokal | BROAD FEED ACTIVE / LOCAL VERIFIED | primäre Marktwahrheit; BTC/EUR Canary bleibt unabhängig aktiv; `CryptoMiniPC-KrakenUniverse` überwacht im Aktivierungsproof 500/500 online EUR-Paare (100% Coverage), 0 Subscription-Errors; REST `AssetPairs` = Universe-Gate, WS-v2-Ticker = Event-Feed; Latest-Snapshot/Heartbeat only; public data / no account / no orders / no strategy action |
| V2R4 WS shadow | local Kraken WS snapshot → observation-only discovery | ACTIVE / PHYSICAL SMOKE VERIFIED | `CryptoMiniPC-V2R4WSShadow` active; 500/500 source universe; physical smoke 13 fresh cycles, 0 stale, source age avg ~0.706 s / max ~2.175 s; pinned prep commit `ab78c9a`; no evaluator/account/order/real-money path |
| V2R4 shadow outcomes | prospective post-detection evidence | ACTIVE / LOCAL VERIFIED | `CryptoMiniPC-V2R4ShadowOutcomes` HEALTHY; only events after tracker start enrolled; 5m/15m/30m/1h/3h/6h + MFE/MAE; 18 earlier shadow events deliberately excluded from outcome backfill |
| V2R4 shadow cloud archive | Supabase `v2r4_shadow_evidence` + authenticated Edge relay | ACTIVE / E2E VERIFIED | `CryptoMiniPC-V2R4ShadowCloudSync` HEALTHY; first real upload 23 records/1 batch; 23 rows independently verified; pending=0 after install; server-only RLS/no client policy; fail-soft/idempotent |
| MINI-PC remote status | local watchdog → authenticated Edge relay → Supabase `minipc_status_current` | ACTIVE / E2E VERIFIED | `CryptoMiniPC-StatusSync` HEALTHY; first real row verified; first reported health WARNING correctly exposed stale WS-shadow + outcome-tracker heartbeats; cloud deadman external to MINI-PC is active |
| MINI-PC daily status | GitHub hourly gate → 10:00 Europe/Berlin → Slack + Supabase history | PREPARED / DRY-RUN VERIFIED | actual remote health + Kraken/Shadow/Supervisor/Evidence; OK posts silently, problem states use real `@Hoffis` push; timezone-safe across CET/CEST |
| MINI-PC health taxonomy | local watchdog operational state | ACTIVE / PHYSICALLY VERIFIED | `OK`, `WAITING_NO_DATA`, `FEED_STALE`, `API_DISCONNECTED`, `BACKLOG_STUCK`, `DEGRADED`, `STOPPED`; physical effectiveness smoke = HEALTHY / OK / no reasons |
| MINI-PC runtime supervisor | bounded Task Scheduler liveness recovery | ACTIVE / SELF-HEAL VERIFIED | 2-min cadence + startup; 10-min per-task restart backoff; controlled stop of archive-only support task recovered automatically; heartbeat advanced; local watchdog HEALTHY; no strategy/evaluator/order path |
| GitHub Cloudpfad | bestehend | ACTIVE | unabhängiger Fallback bleibt erhalten |
| Supabase archive | `paper_series` / `paper_candidate_outcomes` / `paper_trade_results` | ACTIVE / VERIFIED / FAIL-SOFT | push/manual + opportunistic workflow_run + unabhängige Reconciliation :07/:37; zuletzt 578 V2R3-Outcomes archiviert, 0 Trades |
| Historical/backtest research layer | Kraken OHLCVT + targeted Time & Sales, local research-only | PERFORMANCE V1 VALIDATED / INSUFFICIENT / HOLDOUT SEALED | `docs/historical-backtest-preflight.md`; normalized EUR-15m research layer and broad PIT V2 methodology are physically verified. Frozen OHLCVT Performance-Replay V1 executed on the MINI-PC: validation n=2,600, fixed 1.40% round-trip cost, mean net -0.7207%, median net -1.5823%, positive-net rate 35.85%. 2026H1 holdout remained unopened (0 events/0 metrics), no threshold optimization, no active V2R3/V2R4 mutation. V1 is retained as an insufficient baseline; next = validation-only failure-mode review, then any changed hypothesis must become V2/new trial. Time & Sales remains separately gated |
| Slack Push | GitHub owner-approved action relay → Slack webhook → real `@Hoffis` mention → iPhone | ACTIVE / E2E VERIFIED | 2026-10-01 relay workflow SUCCESS, Slack HTTP 200/ok, physical iPhone push received; `#krypto-signale` mobile setting = Nur Erwähnungen; raw candidates remain silent |
| ChatGPT Desktop/Work | ChatGPT auf MINI-PC eingerichtet; Work sparsam | BASE ACTIVE | ChatGPT-Konto/Browserzugriff vorhanden; Work weiterhin nur bei echtem Desktop-/Browsermehrwert |

## Kraken-Handelbarkeit / Market-Universe

Verbindliche Datenqualitätsregel ab 2026-09-30:

- Operative Quelle der Wahrheit ist die **aktuelle öffentliche Kraken-`AssetPairs`-Antwort**, nicht Chat-Memory und keine statische Whitelist.
- Für den aktiven Scanner wird der aktuelle Kraken-Spot-EUR-Universe bereits pro Lauf geladen und auf `online` gefiltert.
- Für V2R4 gilt dieselbe Regel: Live-Abgleich je Watcher-Zyklus; nur `online` Spot-EUR-Paare; Symbolauflösung über Kraken-Metadaten (`wsname`, `altname`, Pair-Key).
- Der frühere 14-Tage-Abgleich bleibt höchstens als **Integritäts-/Listing-/Alias-Audit** bestehen. Er ist nicht die operative Entscheidung, ob ein Coin auf Kraken handelbar ist.
- Bei manuellen/Chat-Analysen eines konkreten Coins muss vor einer Aussage „nicht auf Kraken handelbar“ der aktuelle Kraken-Universe-Stand geprüft werden.
- Anlass/Korrekturfall: KSM/TRAC am 2026-09-30. Beide dürfen nicht wegen eines veralteten oder nicht konsultierten Chat-Kontexts übersehen werden.
- Diese Regel ist Infrastruktur-/Datenqualitätslogik und verändert die eingefrorenen V2R3-Entry-/Stop-/Sizing-/Scoring-Regeln nicht.

## GitHub-Actions Recovery / Incident 2026-09-30

- Scanner-Run #611 (`startup_failure`) erzeugte **keinen Job**; die unveränderte `scan.yml` war zuvor und danach erfolgreich. Damit ist der konkrete Fehler als GitHub-Actions-Start-/Scheduler-Ereignis und nicht als Scanner-/Strategiefehler einzuordnen.
- Folgeeffekt: Ein VVV-`WAIT` wurde nach Ablauf seiner 45-Minuten-TTL nicht im nächsten Zyklus revalidiert, weil genau dieser Scanner-Zyklus ausfiel. Der Process-Health-Watchdog erkannte den überfälligen WAIT und den Scannerfehler und dispatchte Scanner + Paper-Runtime; VVV wurde anschließend revalidiert und auf `REJECT` geschlossen.
- Härtegrad: als **echter Infrastrukturfehler mit erfolgreichem Self-Heal** behandeln; keine Strategieparameter ändern.
- Neu ab 2026-09-30: `.github/workflows/scanner-startup-recovery.yml` reagiert ereignisgesteuert auf einen **scheduled** Scanner-`startup_failure` und dispatcht genau **einen** sofortigen `workflow_dispatch`-Retry. Ein fehlgeschlagener Recovery-Run wird nicht erneut automatisch retried (Loop-Schutz).
- Der bestehende `process-health.yml` bleibt die zweite, zeitbasierte Recovery-/Escalation-Schicht. Damit hängt die Erstreaktion auf einen Scanner-Startfehler nicht mehr ausschließlich am nächsten Cron-Tick.
- Späterer Mini-PC-Betrieb bleibt die geplante weitere Entkopplung vom GitHub-Scheduler; GitHub bleibt unabhängiger Cloud-Fallback.

## GitHub

Aktuell verbundene Repositories:
- `hoffmannherdecke/kraken-eur-scanner` — aktiver Scanner/Paper-Hauptpfad und kanonischer Backlog.
- `hoffmannherdecke/kraken-readonly-bridge` — private read-only Kraken-Kontosnapshots.
- `hoffmannherdecke/canonical-evaluator-runtime-v1` — archivierter historischer Referenzpfad, nicht aktiv.

Wichtige Referenzen:
- `PROJECT_BACKLOG.md`
- `docs/strategy-version-map.md`
- `docs/v3-research-framework.md`
- Draft-PR #8 — V2R4 Fast WAIT Triggers / Mini-PC
- Issue #7 — V3 Research Track

## Supabase

Stand 2026-09-29:
- Projekt vorhanden und **ACTIVE_HEALTHY**, Region `eu-west-1`, Postgres 17.
- Tabellen:
  - `public.paper_series`
  - `public.paper_candidate_outcomes`
  - `public.paper_trade_results`
  - `public.altrady_trigger_events` — Transportpuffer für optionalen Altrady-Zusatztrigger; RLS aktiv, keine Client-Policies
- Migrationen:
  - `20260928165535_create_paper_archive_tables`
  - `20260928173804_allow_unverified_paper_trade_status`
  - `create_altrady_trigger_events` (2026-09-30)
- RLS ist auf allen vier Tabellen aktiviert; aktuell existieren keine RLS-Policies. Das ist bis zur bewusst definierten Zugriffsschicht fail-closed und wird nicht vorschnell geöffnet.
- `Supabase paper archive sync` ist **ACTIVE / VERIFIED / FAIL-SOFT**. Das GitHub-Secret `SUPABASE_SECRET_KEY` ist konfiguriert; der Workflow auditiert den Repository-Quellbestand und synchronisiert die aktive Serie.
- Der Sync besitzt einen opportunistischen `workflow_run`-Hook nach `Paper runtime evaluator and lifecycle`, verlässt sich darauf aber nicht allein. Zusätzlich läuft eine unabhängige Reconciliation um **:07/:37** jeder Stunde, weil ein erster Paper-Runtime-Abschluss nach Einführung des Hooks keinen beobachtbaren Archive-Run erzeugte.
- Historischer Stand des später kompromittiert eingestuften V2R3-Vorgängers: final **712 archivierte Candidate-Outcomes**, **0 Trade-Results**; nur diagnostisch verwenden. Aktive saubere Vergleichsserie ist `PAPER-V2R3-CLEAN-20261001T0925Z`.
- Supabase bleibt sekundär/fail-soft: ein Archivfehler darf Scanner oder Paper-Evaluator nicht blockieren.
- Supabase bleibt sekundäre State-/Ergebnis-/Research-Schicht; kein Single Point of Failure und keine zweite Rohdatenkopie.

## V3 Migration Ledger — Pflichtstatus

Jeder relevante V2/V2R4-Baustein erhält genau einen Status:
- `INHERITED_UNCHANGED`
- `INHERITED_MODIFIED`
- `REPLACED_BY_TESTED_V3_COMPONENT`
- `REJECTED_WITH_EVIDENCE`
- `NOT_APPLICABLE`
- `OPEN_RESEARCH`

## Speicher-/Ablageregel für Chat-Beschlüsse

Für jede dauerhaft projektrelevante Information aus einem Gespräch – unabhängig davon, ob der Nutzer ausdrücklich „bitte speichern“ / „merk dir das“ sagt – gilt:
1. Inhalt zeitnah sichern.
2. Fachlich klassifizieren: Entscheidung / Anforderung / Idee-Hypothese / Datenquelle / Testregel / Fehler / offener Punkt / Architektur / Arbeitsprinzip.
3. Der passenden kanonischen GitHub-Stelle, Komponente und Version zuordnen; bestehende Dokumentation bevorzugen statt unnötig neue Einzeldokumente anzulegen.
4. Abhängigkeiten, Status und ggf. Migrationsbezug dokumentieren.
5. Relevante offene Punkte einzeln weiterführen und nicht durch Sammelzusammenfassungen verschwinden lassen.
6. Bei unklarer Zuordnung nicht raten, sondern **ZUORDNUNG OFFEN** markieren.
7. ChatGPT-Memory nur als knappen Projektindex für wenige dauerhafte Leitplanken nutzen; Detailwissen bleibt in GitHub.
8. Reine Gesprächsfüllung, kurzfristige Zwischenstände und bewusst verworfene Ideen nicht unnötig dauerhaft speichern, sofern sie keinen Nachweis-/Historienwert haben.
