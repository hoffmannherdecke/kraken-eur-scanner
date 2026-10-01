# PROJECT_BACKLOG — Aktien & Krypto Chancen

Status: **KANONISCHER MASTER-BACKLOG**  
Letzte Vollsicht: 2026-09-29  
Aktive Vergleichsbasis: `V2R3-2026-09-28` / `PAPER-V2R3-FINAL-20260928T1752Z`

## Zweck und Pflege-Regeln

Diese Datei ist der zentrale Kontrollpunkt gegen das Vergessen offener Projektpunkte.

Sie enthält **nur offene, blockierte oder bewusst zurückgestellte Punkte**. Erledigte Arbeiten werden nicht als lange Historie weitergeführt; Nachweise gehören in Commits, Issues, Logs oder die jeweilige kanonische Fachdokumentation.

Ab jetzt gilt:
- Alles, was ausdrücklich als „merken“, „später“, „noch testen“, „bei der Mini-PC-Einrichtung wieder aufgreifen“ oder „offener Punkt“ festgelegt wird, muss entweder hier stehen oder in einer hier verlinkten kanonischen Fachdokumentation.
- Keine Doppelpflege derselben Detailregeln. Diese Datei hält Aufgabe, Reihenfolge, Abhängigkeit und Abschlusskriterium; Fachdokumente halten die Details.
- Erst einen Baustein stabil und mit kleinem End-to-End-Smoke-Test nachweisen, dann den nächsten hinzufügen.
- Keine stillen Strategieänderungen. V2R3 bleibt bis zum Ende seiner laufenden Vergleichsserie eingefroren.
- Routinearbeit lokal / GitHub / API zuerst; ChatGPT Work nur für kleine, nicht sinnvoll auslagerbare Aufgaben.
- Architektur schlank halten: wenig Rohdaten, kurze TTLs, Log-Rotation, Kompaktierung, keine unnötigen Datenkopien.
- Technische Fehler und statistische/strategische Schwäche getrennt behandeln.
- Kein einzelner Dienst darf alleiniger Trigger oder Single Point of Failure sein.

Kanonische Detailquellen:
- Strategie-Versionen / Routing V2R3 ↔ V2R4 ↔ V3: `docs/strategy-version-map.md`
- V3 Research / Promotion: `docs/v3-research-framework.md`
- V3 Research-Chronik: GitHub Issue #7
- Action-Push / Slack-E2E: GitHub Issue #1

---

## P0 — Laufende V2R3-Serie sauber beenden und auswerten

- [ ] Homogene V2R3-Serie unverändert weiterlaufen lassen; keine Entry-/Stop-/Sizing-/Scanner-Regel während der Serie verändern.
- [ ] Zusätzlich zum Ziel „20 abgeschlossene Paper-Trades“ einen **vorab definierten alternativen Abschlussmechanismus** festlegen, falls die Strategie zu wenige Trades erzeugt (z. B. ausreichende Kandidatenzahl und/oder Beobachtungszeit), damit eine überstrenge Strategie nicht endlos im Test bleibt.
- [ ] Alle relevanten Kandidatenpfade auswerten, nicht nur tatsächliche Entries: BUY/Scout, WAIT, REJECT/NO-TRADE sowie späteren Kursverlauf.
- [ ] MAE/MFE, 30/60/120/360-Minuten-Follow-up, Edge-Decay, „gestoppt und später erholt“, verpasste Moves und Gebührenwirkung systematisch zusammenführen.
- [ ] Zeitkette messen: Scanner-Erkennung → Persistenz/Handoff → Evaluator → Revalidation → möglicher Entry. Verzögerung als eigene Fehlerklasse behandeln.
- [ ] Gewinner-/Verlierer- und Positionsgrößenanalyse durchführen; insbesondere prüfen, ob hohe Scores tatsächlich höhere Netto-Edge tragen.
- [ ] Missed-Move-Audit gegen frühe starke Bewegungen weiterverwenden und prüfen, welche Filter gute Moves verhindert bzw. schlechte Trades verhindert haben.
- [ ] Abschlussanalyse strikt klassifizieren: **Strategieproblem / Timing-Infrastruktur / Datenqualität / technischer Betriebsfehler / Kostenproblem**.
- [ ] Aus V2R3 nur testbare Hypothesen für V3 ableiten; keine automatische Promotion.

**Abschlusskriterium P0:** belastbarer V2R3-Abschlussbericht mit klaren Ursachen, nicht nur einer Gewinn-/Verlustzahl.

---

## P1 — Dell OptiPlex 5060 Micro als stabile 24/7-Basis

Start erst nach Eintreffen des Geräts; Einrichtung schrittweise.

- [x] Hardware-/OS-Preflight: BIOS, Windows, Treiber, SSD-Zustand, Uhrzeit/Zeitsynchronisation, Netzwerk.
- [x] Dauerbetrieb konfigurieren: kein unerwünschter Schlafmodus, kontrollierter Neustart, Dienste automatisch starten.
- [x] Automatisches Wiederanlaufen nach Stromausfall konfigurieren und praktisch testen.
- [x] Stabiles LAN als primärer Dauerpfad einrichten.
- [x] **Internen Windows-Remotezugriff sehr früh einrichten**: interner RDP-Zugriff nach Neustart/Strom-Recovery verifiziert.
- [ ] Externer Fernzugriff: WireGuard ist vorbereitet; echter Außentest über Mobilfunk/iPhone-Hotspot ist bewusst in Runbook **Phase H ganz nach hinten verschoben**; keine direkte RDP-Portfreigabe ins Internet.
- [x] ChatGPT auf dem Mini-PC mit demselben Konto einrichten; iPhone bleibt bevorzugte Sprach-/Diktieroberfläche. Work nur bei echtem Desktop-/Browser-/Dateikontext; keine Credits vorsorglich kaufen.
- [ ] Secrets/API-Schlüssel lokal und mit minimalen Rechten halten; niemals in Repo oder Logs schreiben.
- [x] Klare lokale Verzeichnisstruktur für Runtime, State, Logs, temporäre Daten, Archiv und Backup festgelegt.
- [ ] Externes Laufwerk D: enthält wichtige Altdateien und FAT32-Fehler; Sicherung/Reparatur bewusst in Runbook **Phase H ganz nach hinten verschoben**. Bis dahin **keine Live-Abhängigkeit / keine aktive Projektablage**.
- [x] Speicherlimits/TTLs/Log-Rotation für lokale Basis eingerichtet; weitere komponentenspezifische Limits folgen jeweils mit der Runtime.

**Abschlusskriterium P1:** Mini-PC läuft nach Neustart/Stromunterbrechung selbstständig wieder stabil und ist lokal administrierbar.

---

## P2 — Lokaler Runtime-/Watchdog-/Recovery-Layer

- [ ] Lokalen Prozess-Supervisor/Watchdog vervollständigen: Basis-Watchdog/Tasks, Kraken-Canary, breiter Kraken-EUR-Feed und Altrady-Transport sind aktiv; **voller Windows-Neustart-Recovery-Test 2026-10-01 PASS (6/6 Tasks, alle Heartbeats HEALTHY, Kraken HTTP 200)**. Transport-Recovery bei Internet-Ausfall ist verifiziert. Offen bleiben Queue-/Runtime-Wirkung, stale-signal/TTL/Dedup-Reconciliation und der konkrete Strategie-/Watcher-Prozess.
- [ ] Watchdog muss auch „grün aber wirkungslos“ erkennen, nicht nur Prozessstatus.
- [ ] Täglichen sehr kurzen **10:00-Systemstatus** später lokal/GitHub-basiert erzeugen: tatsächliche End-to-End-Gesundheit statt nur „Workflow aktiv“; Work dafür nicht als Dauerlösung verwenden.
- [ ] Uptime Kuma als kostenlose, unabhängige Health-Schicht prüfen/einrichten, sofern es echten Zusatznutzen liefert.
- [ ] Health-Zustände klar unterscheiden: OK, waiting/no-data, feed stale, API disconnected, backlog/queue stuck, degraded, stopped.
- [ ] Automatischer begrenzter Self-Heal für eindeutig technische Fehler; keine automatische Strategie-/Threshold-Änderung.
- [x] Kontrollierten Internet-Ausfall/Wiederkehr für die **aktiven Transportpfade** testen: 2026-10-01 PASS; Ethernet-Ausfall wurde erkannt, Kraken HTTPS/Canary/breiter EUR-Feed/Altrady/Watchdog erholten sich automatisch. Stale-Decision/Queue-Replay bleibt erst mit gekoppelter Strategie-Runtime separat zu beweisen.
- [ ] Wiederverbindung auf **Strategie-Runtime-Ebene** testen: Dedup, TTL alter Signale, **kein blindes Replay** veralteter Kandidaten. Transport-Reconnect selbst ist seit 2026-10-01 verifiziert.
- [ ] Neustart-Reconciliation: lokaler Zustand, GitHub-Zustand und spätere Exchange-Zustände müssen konsistent zusammengeführt werden.
- [ ] GitHub-Cloudpfad als unabhängigen Fallback erhalten; weder Mini-PC noch Altrady dürfen alleiniger Trigger sein.
- [ ] Tägliche Sicherung um 04:00 lokal; Alarm nur, wenn Backup mindestens eine Woche tatsächlich ausgefallen ist.
- [ ] Restore-/Recovery-Smoke-Test einplanen.
- [ ] Grafana-Statusseite erst ergänzen, wenn stabile Metriken vorhanden sind; kein Dashboard nur um des Dashboards willen.

**Abschlusskriterium P2:** definierte Strom-, Internet-, Prozess- und Datenfehler können ohne Datenchaos und ohne stale Decisions überstanden werden.

---

## P3 — Realtime-Daten und Trigger: Kraken + Altrady + redundanter Pfad

- [ ] Kraken WebSocket/REST auf dem Mini-PC als kontinuierliche Primärdatenquelle für relevante Live-Mikrostruktur aufbauen. **Breiter strategie-neutraler EUR-Realtime-Transport ist seit 2026-10-01 lokal aktiv/verifiziert:** `CryptoMiniPC-KrakenUniverse`, 500/500 Online-EUR-Paare im Aktivierungsproof, 100% Coverage, 0 Subscription-Errors; REST `AssetPairs` = Universe-Gate, WS-v2-Ticker = Event-Feed, nur Latest-Snapshot + Heartbeat. Offen innerhalb dieses größeren Punkts: Restart-/Internet-Recovery beweisen, Timingmessung gegen Scanner/Altrady und erst danach eine explizite Strategie-/Fresh-Recheck-Kopplung separat freigeben.
- [ ] Nur benötigte Rohdaten kurzfristig speichern; langfristig Features/Aggregate statt endloser Tick-/Orderbucharchive behalten.
- [ ] Altrady als **zusätzlichen echten Echtzeit-Trigger** fertig anbinden, niemals als einzigen Trigger. Der Transportpfad ist synthetisch und durch einen echten One-shot-Price-Alert E2E verifiziert; offen bleibt die spätere explizite Fresh-Recheck-Kopplung sowie der Latenzvergleich mit Kraken-native und dem Legacy-Scanner. Kein erneuter manueller Altrady-Transporttest nötig, solange die Konfiguration unverändert bleibt.
- [ ] Altrady-Heartbeat/Fehlerrückmeldung überwachen; Ausfall darf die restliche Kette nicht stoppen.
- [ ] V2R4 WS-Shadow auf dem MINI-PC aktivieren: Adapter/Unit-/Synthetic-CI + Installer/Rollback sind vorbereitet und grün; nächster physischer Gate ist der gebündelte Live-Snapshot-Smoke + Start von `CryptoMiniPC-V2R4WSShadow`. Shadow bleibt ohne Evaluator/Orders und sammelt Feed→Discovery-Timing sowie stale/dedup/recovery Evidenz.
- [ ] Detektionslatenz Kraken-native vs. Scanner vs. Altrady messen.
- [ ] Nach stabiler Basis den Takt anhand realer Messungen verkürzen; Ziel grob ~7–8 Minuten, wo ein periodischer Takt nötig ist, ergänzt durch schnellere eventbasierte Trigger.
- [ ] Evaluator/KI nur bei echten Kandidaten oder klaren Analyseblockern aufrufen; kein dauerndes KI-Polling.
- [ ] V2R4-Fast-Trigger-Pfad aus Draft-PR #8: V2R3-Evidenzsnapshot, Compile/Unit-/Live-Public-Kraken-/Model-Contract-Smokes, **physischer MINI-PC trigger→fresh-recheck E2E-Gate** und Altrady-Transport-E2E sind jetzt grün; live Kraken-AssetPairs statt statischer Blacklist, maschinenlesbare WAIT-Bedingungen und lokaler Fresh-Recheck-Bridge sind vorbereitet. Offen: separater V2R4-Paper-Aktivierungsentscheid nach Evidenzsicht; kein stilles Merge/Activation.
- [ ] Bei bestandenem Smoke-Test eine **separate V2R4-Paper-Serie** starten; dafür nicht künstlich auf 20 V2R3-Trades warten. V2R3-Artefakte bleiben unverändert als Vergleichsbasis.
- [ ] Datenfrische und Entscheidungstimestamp in jedem Kandidaten nachvollziehbar halten.

**Abschlusskriterium P3:** derselbe relevante Move kann über mehr als einen unabhängigen Pfad erkannt werden und Timing ist messbar.

---

## P4 — Integrationen, Benachrichtigung und Kostenkontrolle

### Slack / Push
- [ ] GitHub → Relay → Slack → iPhone-**echten Push** unter Realbedingungen nachweisen; Issue #1 erst dann als erledigt betrachten.
- [ ] Rohkandidaten bleiben ohne Push; Push nur bei echter Handlung, wichtigem Fehler oder definiertem Abschlussereignis.
- [ ] Später unabhängigen zweiten Pushweg nur dann ergänzen, wenn er die Ausfallsicherheit wirklich verbessert.

### Supabase
- [x] Supabase-Archivpfad operativ und E2E-verifiziert: sichere GitHub-Backend-Credentials, minimales Schema, klarer Sync-Pfad; automatischer Nachzug nach erfolgreichem Paper-Runtime-Workflow.
- [ ] Supabase weiterhin nur für strukturierten State/Ergebnis-/Research-Nutzen verwenden, nicht als zweite Kopie großer Rohdatenmengen.
- [x] Supabase bleibt fail-soft/sekundär; Ausfall stoppt Scanner/Paper-Pfad nicht.

### ChatGPT / Work / API
- [ ] Routinejobs vollständig aus Work heraushalten, soweit GitHub/Mini-PC/API sie zuverlässig übernehmen können.
- [ ] Work nur für kleine unvermeidbare Aufgaben oder gezielte Analyse verwenden; keine Dauerpoller.
- [ ] API-Verbrauch und Work-Credits getrennt überwachen und Kostenlimits/Guardrails festlegen.
- [ ] Ereignisgesteuerte Analyse bevorzugen; bei „kein Handlungsbedarf“ keine unnötige KI-Kette.
- [ ] n8n Community erst später prüfen, wenn echte Orchestrierungs-Komplexität vorhanden ist; nicht vorsorglich einführen.

**Abschlusskriterium P4:** Benachrichtigung, State-Sync und KI-Aufrufe funktionieren sparsam, entkoppelt und ohne unnötige doppelte Dienste.

---

## P5 — Historische Daten-/Backtest-Schicht

- [ ] Kraken historische OHLCVT-Daten vom Marktstart bis 30.06.2026 plus spätere Updates lokal/kompakt verfügbar machen.
- [ ] Kraken historische Time-&-Sales-/Tickdaten gezielt für Fill-, Mikrostruktur- und Entry/Exit-Fragen nutzbar machen.
- [ ] Binance nur ergänzend für Cross-Market-/Derivatehistorie nutzen; Kraken-EUR bleibt Ausführungs- und Fill-Referenz.
- [ ] Public-Access/Verfügbarkeit von Binance auf der späteren Infrastruktur praktisch prüfen; Account nur einbinden, wenn für den vorgesehenen Datenpfad tatsächlich nötig.
- [ ] Point-in-time Feature-Erzeugung mit sauberer Timestamp-Semantik sicherstellen.
- [ ] Trial Ledger/Search Accounting für alle getesteten Parameter-/Feature-/Stop-/Sizing-Varianten einführen.
- [ ] Chronologisches Walk-Forward, Purging/Embargo und versiegelten Holdout technisch abbilden.
- [ ] Reale Kraken-Gebühren (~0,60 % Taker je Seite), Spread, Slippage, Turnover und Re-Entry-Kosten berücksichtigen.
- [ ] Rohdaten nach Testzweck komprimieren/aggregieren/löschen; historische Daten nicht in GitHub aufblasen.

**Abschlusskriterium P5:** reproduzierbarer historischer Test mit point-in-time Daten, realistischen Kosten und klarer Versions-/Trial-Historie.

---

## P6 — V3 aus Evidenz bauen, nicht aus Bauchgefühl

Detailregeln bleiben in `docs/v3-research-framework.md` und Issue #7. Die Abgrenzung zu V2R4 ist verbindlich in `docs/strategy-version-map.md` festgelegt.

- [ ] V2R3-Abschlussbefunde vollständig in den V3-Aufbau übernehmen; V3 startet vom besten validierten V2/V2R4-Gesamtstand, nicht bei null.
- [ ] V2/V2R4→V3-Migrationsledger führen: jeder relevante Baustein = übernommen / modifiziert / ersetzt / verworfen / offen.
- [ ] Literaturbefunde nur als Hypothesenquelle nutzen; nichts allein wegen Publikation übernehmen.
- [ ] Mini-PC-/Altrady-Timingdaten gezielt einfließen lassen. Wenn Timing das Problem ist, zuerst Infrastrukturvariante testen, nicht sofort Entry-Regeln lockern.
- [ ] Shadow-Varianten mit **einer klaren Änderung pro Kandidat** testen, z. B. früherer Entry, anderer TTL, anderer Stop/Trailing, anderer Exit.
- [ ] Erfolgreiche Shadow-Trades auf gemeinsame Mechanismen untersuchen; Gewinnerbeobachtung anschließend historisch/OOS gegenprüfen.
- [ ] H1 Cross-Crypto Lead/Lag + Breadth testen.
- [ ] H2 Basis/Premium/Funding/OI als State/Conditioning testen.
- [ ] H4 regimeabhängige Stop-/TTL-Logik aus MAE/MFE testen.
- [ ] H5 Makro-Event-Risk-Gate testen.
- [ ] H6 einfache Price×Volume-Trend-Primitiven testen.
- [ ] H3 Orderflow/Depth/Imbalance erst mit Mini-PC-WebSocket-Daten produktiv erforschen.
- [ ] H7 Meta TAKE/NO-TAKE erst nach genügend sauberen Labels.
- [ ] H8 On-chain erst nach Daten-/Timing-Preflight.
- [ ] H9 Maker-vs-Taker/Fill-Wahrscheinlichkeit erst vor späterer Live-Ausführung.
- [ ] V3-Kandidat einfrieren und auf identischem Kandidatenstrom im Shadow/Paper direkt gegen V2R3 vergleichen.
- [ ] Nur nach bestandenem Promotion-Gate neue explizite Strategieversion erstellen.
- [ ] Höhere Positionsgrößen/zusätzliches Kapital erst **nach** belastbarer Validierung separat prüfen.

**Abschlusskriterium P6:** V3 hat den relevanten validierten V2/V2R4-Stand vollständig klassifiziert und integriert, besitzt historische/OOS- plus prospektive Shadow/Paper-Evidenz und ist als einheitlicher versionierter Nachfolger promotionsfähig.

---

## P7 — Separater Smart-Money-/Trader-Sensor als Shadow-Forschungszweig

Erst nach stabilem Kernsystem. Keine Schreibrechte auf Hauptqueue, keine Orders.

- [ ] Eigenständige lokale Shadow-Architektur anlegen; Hauptsystem unverändert lassen.
- [ ] Hyperliquid zuerst: genau einen kleinen End-to-End-Daten-/Wallet-Test durchführen.
- [ ] Provenance, Zeitstempel, Datenqualität und Reproduzierbarkeit nachweisen.
- [ ] Binance später für Spot-Trader-Finder/Qualitätsvergleich/Crowding-Forschung ergänzen.
- [ ] Prospektiv messen, ob beobachtete Smart-Money-Signale tatsächlich vor verwertbaren Kraken-EUR-Moves liegen.
- [ ] Realistischen Paper-Simulator/A-B-Vergleich bauen.
- [ ] Arkham erst danach für Entity-/Wallet-Cluster/Webhooks testen.
- [ ] Nansen nur dann erwägen, wenn kostenlose Quellen eine klar belegte Lücke lassen.
- [ ] Lokale ML-/Scoring-Variante erst nach genügend sauberen Shadow-Daten.
- [ ] Ergebnisse dürfen erst nach normalem V3-Evidenzweg als Feature/State in die Hauptstrategie gelangen.

**Abschlusskriterium P7:** belegter inkrementeller Nutzen gegenüber normalen Markt-/Orderflowdaten; sonst Zweig verwerfen.

---

## P8 — Spätere Live-/Execution-Stufe

Erst nach stabiler Infrastruktur und validierter Strategie.

- [ ] Self-hosted GitHub Runner erst nach stabilem Mini-PC-Grundbetrieb einführen.
- [ ] Vor Trading-Rechten private Kraken-Kontoinformationen/Tradability/Orders/Zustand minimal und read-only integrieren, soweit für sichere Reconciliation nötig.
- [ ] Kraken-Tradability-/Whitelist-Stand regelmäßig aktualisieren; bisher vorgesehener Rhythmus ~14 Tage.
- [ ] Trading-API nur mit minimalen Rechten, **ohne Auszahlungsrechte**.
- [ ] Persistent Kill-Switch über Neustarts.
- [ ] Startup-Reconciliation gegen Kraken-Konto.
- [ ] Stale-data rejection ohne Fallback auf alten Preis.
- [ ] Duplicate-Order-, Größen-, Positions- und Price-Deviation-Gates.
- [ ] Order Lifecycle als Zustandsmaschine mit Audit-Trail und Fill/Cancel-Race-Behandlung.
- [ ] Circuit Breaker für Drawdown, Daily Loss, Consecutive Losses, Latenz/Feed-Probleme; Wiederaufnahme nicht nur nach Timer.
- [ ] Maker-vs-Taker nur mit Fill-Wahrscheinlichkeit und Edge-Decay entscheiden.
- [ ] Zunächst kontrollierte/manual bestätigte Ausführung möglich halten; Vollautomatisierung erst als separate spätere Freigabe.
- [ ] Keine Ausweitung auf Leverage als Bestandteil dieses Pfades.
- [ ] Vor Echtgeld: echter E2E-Alarmweg, Kill-Switch, Recovery und Rollback praktisch beweisen.

**Abschlusskriterium P8:** technische Execution-Sicherheit und Strategie-Evidenz sind separat bestanden; Echtgeld-Aktivierung bleibt eigener Freigabeschritt.

---

## P9 — Dauerhafte Governance / „nicht wieder vergessen“\n\nKanonischer Komponenten-/Versionsindex: `docs/master-version-register.md`. Mini-PC-Runbook: `docs/minipc-preflight-runbook.md`.

- [ ] Jede Entscheidung mit Strategieversion + Config-Hash/Revision nachvollziehbar machen.
- [ ] Last-known-good Konfiguration und schneller Rollback erhalten.
- [ ] Vor größeren Änderungen immer kleiner End-to-End-Smoke-Test.
- [ ] Neue Quellen/Apps nur aufnehmen, wenn sie einen klaren zusätzlichen Informations- oder Robustheitsnutzen liefern.
- [ ] Datenquellen und Apps dürfen nicht still dieselben Daten mehrfach speichern.
- [ ] Periodisch prüfen, welche Logs/Rohdaten/Artifacts abgelaufen sind und automatisch weg können.
- [ ] Offene GitHub Issues regelmäßig gegen diesen Master-Backlog abgleichen; keine zweite konkurrierende To-do-Liste entstehen lassen.
- [ ] Bei jedem neuen „merk dir das/später“-Beschluss diese Datei oder das verlinkte Fachdokument aktualisieren.

---

## Separate spätere Erweiterungen — ausdrücklich erst nach stabilem Trading-Kern

Diese Punkte gehören nicht in die Trading-Laufzeit und dürfen den Kernaufbau nicht verzögern:

- [ ] Bosch Smart Home / Home-Assistant-Anbindung.
- [ ] SmartLife/Matter-Steckdosen.
- [ ] Deye- und Hoymiles-/S-Miles-Balkonkraftwerk-Daten.
- [ ] Wetter-/Energie-Automationen erst nach den obigen Smart-Home-Grundpfaden.

---

## Reihenfolge in einem Satz

**V2R3 sauber messen → Mini-PC stabil → Watchdog/Recovery → Kraken/Altrady-Realtime → V2R4-Fast-Trigger Paper → schlanke Integrationen + Historik/Backtests → V3 Research/Shadow/Paper → Smart-Money-Forschung → Self-hosted/Trading-API zuletzt.**

- [ ] **V2R4 Paper-Aktivierungsentscheid** bleibt separat offen. Der physische trigger→fresh-recheck Nachweis auf dem MINI-PC und der Altrady-Transport-E2E sind bestanden; vor Aktivierung weiterhin Evidenzsicht, klarer Serienstart und Rollback-Punkt, keine Echtgeldaktion.
