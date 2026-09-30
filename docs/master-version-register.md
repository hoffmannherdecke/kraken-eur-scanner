# MASTER VERSION REGISTER — Aktien & Krypto Chancen

Status: **KANONISCHE KOMPONENTEN-/VERSIONSÜBERSICHT**  
Stand: 2026-09-29  
Zweck: Single Source of Truth für Strategie, Paper, Infrastruktur, Datenpfade und Integrationen.

## Governance

- Kein relevanter Bestandteil wird nur über Chat-Erinnerung verwaltet.
- Dauerhaft projektrelevante Informationen aus Gesprächen werden proaktiv kanonisch dokumentiert, auch wenn der Nutzer nicht ausdrücklich „merk dir das“ sagt. Dazu zählen insbesondere Entscheidungen, Anforderungen, neue Daten-/Informationsquellen, Hypothesen, Testregeln, offene Punkte, Fehlerursachen, Architektur-/Strategieänderungen und verbindliche Arbeitsprinzipien. Reine Zwischenüberlegungen oder verworfene Ideen werden nur dann dauerhaft aufgenommen, wenn sie für die Nachvollziehbarkeit relevant sind.
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
| Paper-Serie | `PAPER-V2R3-FINAL-20260928T1752Z` | ACTIVE | Aktuelle homogene V2R3-Serie; vollständige Abschlussauswertung vor V2R4-Go-live |
| Strategie | V2R4 | PREPARED / NOT ACTIVE / PAPER ONLY | Nächste operative Paper-Version nach Mini-PC-Basis + E2E-Smoke-Test; Draft-PR #8 |
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
| Externer Fernzugriff | FRITZ!Box-VPN/WireGuard → internes RDP | CONFIGURED / TEST DEFERRED TO FINAL RUNBOOK PHASE | kein direktes RDP-Portforwarding; Außentest bewusst erst ganz am Ende |
| Stromausfall-Recovery | Dell BIOS AC Recovery = Power On | ACTIVE / VERIFIED | echter Stromverlust-/Umplatzierungs-Test bestanden; automatischer Boot ohne Tastendruck, RDP danach wieder erreichbar |
| Watchdog/Recovery | lokaler Supervisor + unabhängiger GitHub-Fallback | CLOUD VERIFIED / LOCAL BASELINE ACTIVE | GitHub-Watchdog + Startup-Recovery aktiv; lokale SYSTEM-Tasks alle 5 Min + Startup und tägliche Log-Bereinigung 04:20 installiert; Immediate Health exit 0; prozessspezifischer Self-Heal folgt erst mit lokaler Runtime |
| Backup/Restore | lokales State-Backup + Restore-Smoke | ACTIVE / VERIFIED | 04:00 daily, 14-day retention, no Secrets/Logs/Repo; immediate seed + restore smoke passed locally; watchdog warns only after 7 days without backup |
| Externer Datenträger | `D:` / `Mistral_450`, ~304 GB frei | ATTACHED / DEFERRED TO FINAL RUNBOOK PHASE | physische Platte Healthy, FAT32-Volume mit logischen Fehlern; wichtige Altdateien vorhanden; Sicherung/Reparatur bewusst erst ganz am Ende, bis dahin keine aktive Projektablage |
| Kraken local realtime data | Public WebSocket v2 book + trades via isolated venv | ACTIVE / SMOKE VERIFIED | 45s local smoke: 1544 verified book events, 103 trades, 0 gaps, 0 subscription errors; public/read-only only |
| Kraken runtime canary | continuous BTC/EUR public WebSocket heartbeat | PREPARED / CI+LIVE-SMOKE VERIFIED / LOCAL ACTIVATION PENDING | startup SYSTEM task + heartbeat + watchdog integration; transport-only, no account/order/strategy action |
| Altrady | zusätzlicher Echtzeit-Trigger | TRANSPORT PREPARED / NOT ACTIVE | Supabase-Eventtabelle + Relay-Quellcode + MINI-PC-Poller/Task-Installer vorbereitet und CI-geprüft; niemals alleiniger Trigger/SPOF; Relay-Secret/Deployment + E2E-Smoke noch offen |
| Kraken realtime | Public REST/WebSocket lokal | SMOKE VERIFIED / CONTINUOUS DAEMON PENDING | primäre Marktwahrheit; 45s WS-Smoke ohne Gap/Subscription-Fehler bestanden |
| GitHub Cloudpfad | bestehend | ACTIVE | unabhängiger Fallback bleibt erhalten |
| Slack Push | bestehender Pfad, echter iPhone-Push noch E2E nachzuweisen | OPEN | nur handlungs-/fehlerrelevante Pushs |
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
- `Supabase paper archive sync` ist als fail-soft GitHub-Workflow vorbereitet und der Repository-Quellbestand wird per Audit geprüft. Aktuell fehlen die GitHub-Actions-Backend-Credentials; deshalb wird der Sync bewusst übersprungen und beeinflusst Scanner/Paper nicht.
- **Aktuelle Integrationslücke:** Die vorhandenen `paper_candidate_outcomes`-Zeilen gehören derzeit zu `PAPER-V2R2-20260928T1640Z`; für die aktive V2R3-Serie ist noch kein Outcome dort archiviert. Das ist als Sync-/Persistenzpunkt beim Mini-PC/Supabase-Setup zu prüfen, nicht als Strategieergebnis zu interpretieren.
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
