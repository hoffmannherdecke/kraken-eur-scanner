# PROJECT_BACKLOG — Aktien & Krypto Chancen

Status: **KANONISCHER MASTER-BACKLOG**  
Letzte Vollsicht: 2026-09-29  
Aktive Vergleichsbasis: `V2R3-2026-09-28` / `PAPER-V2R3-CLEAN-20261001T0925Z`

## Zweck und Pflege-Regeln

Diese Datei ist der zentrale Kontrollpunkt gegen das Vergessen offener Projektpunkte.

Sie enthält **nur offene, blockierte oder bewusst zurückgestellte Punkte**. Erledigte Arbeiten werden nicht als lange Historie weitergeführt; Nachweise gehören in Commits, Issues, Logs oder die jeweilige kanonische Fachdokumentation.

Ab jetzt gilt:
- Alles, was ausdrücklich als „merken“, „später“, „noch testen“, „bei der Mini-PC-Einrichtung wieder aufgreifen“ oder „offener Punkt“ festgelegt wird, muss entweder hier stehen oder in einer hier verlinkten kanonischen Fachdokumentation.
- Keine Doppelpflege derselben Detailregeln. Diese Datei hält Aufgabe, Reihenfolge, Abhängigkeit und Abschlusskriterium; Fachdokumente halten die Details.
- Erst einen Baustein stabil und mit kleinem End-to-End-Smoke-Test nachweisen, dann den nächsten hinzufügen.
- Keine stillen Strategieänderungen. V2R3 bleibt bis zum Ende seiner laufenden Vergleichsserie eingefroren.
- Routinearbeit lokal / GitHub / API zuerst; ChatGPT Work nur für kleine, nicht sinnvoll auslagerbare Aufgaben.
- **Autonomie-Protokoll:** Innerhalb des freigegebenen Projektumfangs arbeitet ChatGPT ohne erneutes Okay in einem durch. Nach einem Nutzer-Gate wird automatisch weitergearbeitet. Blockierte Pfade führen nicht zum Stillstand; stattdessen den nächsten unabhängigen offenen Punkt bearbeiten und Blocker dokumentieren.
- Nutzer nur dann unterbrechen, wenn seine Mitwirkung technisch zwingend ist (physischer MINI-PC/Heimnetz/BIOS/Gerät, Login/Secret/Account-Bestätigung, echte UI-Interaktion) oder wenn ein bestehendes Sicherheits-/Release-Gate bewusst eine menschliche Entscheidung verlangt.
- Lokale Nutzeraktionen nach Möglichkeit bündeln; keine Serien einzelner „bitte noch diesen Befehl“-Rückfragen, wenn ein sicherer Sammeltest möglich ist.
- Keine Zwischenfreigaben für GitHub-/Supabase-/öffentliche API-/Read-only-Test-/Dokumentations-/Analysearbeiten einholen, solange die bestehenden Guardrails eingehalten werden.
- Architektur schlank halten: wenig Rohdaten, kurze TTLs, Log-Rotation, Kompaktierung, keine unnötigen Datenkopien.
- Technische Fehler und statistische/strategische Schwäche getrennt behandeln.
- Kein einzelner Dienst darf alleiniger Trigger oder Single Point of Failure sein.

Kanonische Detailquellen:
- Strategie-Versionen / Routing V2R3 ↔ V2R4 ↔ V3: `docs/strategy-version-map.md`
- V2R4 Release-/Readiness-Kontrollpunkt: `docs/v2r4-release-readiness.md`
- V2R3→V2R4 Verhaltens-/Release-Diff: `docs/v2r4-v2r3-release-diff.md`
- V2R4 Paper-Aktivierungs-/Rollback-Checkliste: `docs/v2r4-paper-activation-checklist.md`
- Fail-closed V2R4 Aktivierungsstatus: Supabase View `public.v2r4_activation_readiness` (`automatic_activation_allowed=false`)
- V3 Research / Promotion: `docs/v3-research-framework.md`
- V3 Research-Chronik: GitHub Issue #7
- Action-Push / Slack-E2E: GitHub Issue #1

---

## P0 — Laufende V2R3-Serie sauber beenden und auswerten
- [x] Runtime-Persistenzfehler 2026-10-01 erkannt und repariert: Follow-up-No-op-Churn + `status|grep -q` unter pipefail konnte reale Änderungen als „keine Änderungen“ behandeln; reale Logs zeigen wiederholte Evaluation derselben Kandidaten vor Commit. Vorgänger-Serie mit 712 Outcomes als `DIAGNOSTIC_COMPROMISED` eingefroren, saubere identische V2R3-Serie ab 09:25 UTC neu gestartet.
- [x] Clean-Series-Persistenzproof bestanden: erster echter Post-Repair-Scannerlauf → 3 Kandidaten → 3 Entscheidungen im selben Runtime-Lauf committed; separater Repeat-Guard-Lauf selektierte danach `[]`, Follow-up änderte 0 Dateien, Process-Health HEALTHY mit 3/3 vollständiger Provenance und 0 Orphans.
- [x] Auswertungsinfrastruktur für die spätere Abschlussanalyse vorbereitet, ohne V2R3 zu verändern: `public.v2r3_interim_horizon_summary` bündelt unreife 30/60/120/360m-/Post-Detection-Horizonte mit Interpretations-Guardrail; `public.v2r3_reason_family_events` / `public.v2r3_reason_family_rollup` normalisieren die stark variierenden freien Reason-Codes nur **post-hoc/deskriptiv** in Familien. Keine dieser Views darf vor dem Abschluss-Gate zum Tuning genutzt werden.

- [ ] Homogene V2R3-Serie `PAPER-V2R3-CLEAN-20261001T0925Z` unverändert weiterlaufen lassen; keine Entry-/Stop-/Sizing-/Scanner-Regel während der Serie verändern. Vorgänger mit 708 Outcomes ist als `DIAGNOSTIC_COMPROMISED` eingefroren, nachdem ein Runtime-Persistenzfehler wiederholte Evaluierungen vor Commit erlaubte. **Freeze-Guard aktiv:** Strategie-/Runtime-Fingerprints, Scanner-Paket, 10-Minuten-Takt und zentrale Scanner-Settings sind jetzt fail-closed eingefroren; CI `V2R3 clean-series freeze guard` Run #1 SUCCESS.
- [x] Alternativer V2R3-Abschlussmechanismus festgelegt: 20 Trades **oder** frühestens 7 volle Tage + mindestens 1.000 Candidate-Outcomes; anschließend Follow-ups bis 24h ausreifen lassen und mindestens 95 % 24h-Coverage der fälligen Kandidaten verlangen. Regel gilt für die aktuell saubere Serie `PAPER-V2R3-CLEAN-20261001T0925Z`; der frühere 708-Outcomes-Snapshot bleibt nur diagnostisch.
- [ ] Alle relevanten Kandidatenpfade auswerten, nicht nur tatsächliche Entries: BUY/Scout, WAIT, REJECT/NO-TRADE sowie späteren Kursverlauf.
- [ ] MAE/MFE, 30/60/120/360-Minuten-Follow-up, Edge-Decay, „gestoppt und später erholt“, verpasste Moves und Gebührenwirkung systematisch zusammenführen.
- [x] Zeitkette messen: Scanner-Erkennung → Persistenz/Handoff → Evaluator → Revalidation → möglicher Entry. Verzögerung als eigene Fehlerklasse behandeln. **Prospektiv umgesetzt:** `public.v2r3_runtime_timing_summary` + `public.v2r3_revalidation_timing_summary`. Clean-Serie aktuell: initiale Evaluation p50 ~37s / p90 ~55–56s; WAIT-TTL p50 30 min, zusätzliche TTL-Latenz p50 **262s**, p90 **909s**, max **1.401s**; 42/52 Revalidierungen >60s und 22/52 >300s über dem angeforderten TTL-Zeitpunkt. Das bestätigt: Initial-Evaluation ist inzwischen vergleichsweise sauber, die one-shot WAIT-Revalidation bleibt eine eigene Timing-Infrastrukturklasse. Keine Regeländerung während der Serie.
- [ ] Gewinner-/Verlierer- und Positionsgrößenanalyse durchführen; insbesondere prüfen, ob hohe Scores tatsächlich höhere Netto-Edge tragen.
- [ ] Missed-Move-Audit gegen frühe starke Bewegungen weiterverwenden und prüfen, welche Filter gute Moves verhindert bzw. schlechte Trades verhindert haben. **Diagnostischer Vorgänger-Hinweis:** 81 mature REJECTs erreichten später >=10% 24h-MFE; 71 davon hatten persistierte Evaluation <=60s und 42 waren nicht als „already run“ markiert. Das spricht neben Timing auch für mögliche Filter-/Continuation-Probleme, ist wegen der kompromittierten Vorgängerserie aber nur Hypothese bis zur prospektiven Bestätigung in der Clean-Serie.
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
- [x] Externer Fernzugriff: echter Außentest am 2026-10-01 über Mobilfunk/iPhone-Hotspot erfolgreich bestanden; WireGuard aktiv, RDP auf den MINI-PC unter `192.168.178.179` ohne Einschränkungen nutzbar; keine direkte RDP-Portfreigabe ins Internet.
- [x] ChatGPT auf dem Mini-PC mit demselben Konto einrichten; iPhone bleibt bevorzugte Sprach-/Diktieroberfläche. Work nur bei echtem Desktop-/Browser-/Dateikontext; keine Credits vorsorglich kaufen.
- [x] Secrets/API-Schlüssel lokal und mit minimalen Rechten halten; niemals in Repo oder Logs schreiben. Read-only Secret-Hygiene-Audit am MINI-PC 2026-10-01 **HEALTHY**: Critical 0, Warning 0, Findings none; keine Live-Secret-Muster/verbotswürdigen Key-Dateien oder offensichtlich zu breiten Secret-ACLs gefunden. Secretwerte wurden nie ausgegeben.
- [x] Klare lokale Verzeichnisstruktur für Runtime, State, Logs, temporäre Daten, Archiv und Backup festgelegt.
- [ ] Externes Laufwerk D: enthält wichtige Altdateien und FAT32-Fehler; Sicherung/Reparatur bewusst in Runbook **Phase H ganz nach hinten verschoben**. Bis dahin **keine Live-Abhängigkeit / keine aktive Projektablage**.
- [x] Speicherlimits/TTLs/Log-Rotation für lokale Basis eingerichtet; weitere komponentenspezifische Limits folgen jeweils mit der Runtime.

**Abschlusskriterium P1:** Mini-PC läuft nach Neustart/Stromunterbrechung selbstständig wieder stabil und ist lokal administrierbar.

---

## P2 — Lokaler Runtime-/Watchdog-/Recovery-Layer

- [x] Lokalen Prozess-Supervisor/Watchdog vervollständigen: `CryptoMiniPC-RuntimeSupervisor` HEALTHY, 2-Minuten-Takt + Startup, 10-Minuten-Backoff, Read-only-Runtimes only. Kontrollierter physischer Self-Heal-Proof 2026-10-01 **PASS**: Archive-Support-Task absichtlich gestoppt, Supervisor startete ihn ohne Nutzereingriff neu, Heartbeat lief weiter, Watchdog blieb HEALTHY.
- [x] Watchdog erkennt jetzt auch **„grün aber wirkungslos“**: physischer Effectiveness-Smoke 2026-10-01 **HEALTHY / issues=none**; geprüft werden frische Kraken-Canary-Events, frische Universe-Ticker, frische Shadow-Quelle und aktive Outcome-Samples – nicht nur Prozess-/Heartbeat-Alter.
- [ ] Täglichen sehr kurzen **10:00-Systemstatus** GitHub-basiert erzeugen: Workflow ist timezone-aware für Europe/Berlin vorbereitet und Dry-Run **SUCCESS**; er nutzt echten Remote-Health-State + Kraken/Shadow/Supervisor/Evidence-Daten. Bei OK ohne `@Hoffis`-Push, bei Problem mit echter Mention. Erster regulärer 10:00-Lauf steht noch aus.
- [x] Unabhängige Health-Schicht ohne zusätzlichen Uptime-Kuma-Dienst vorbereitet: Supabase Last-Seen + GitHub-Cloud-Deadman überwacht MINI-PC außerhalb des Geräts und pusht nur bei CRITICAL/>20 min stale sowie einmal bei Recovery. Uptime Kuma bleibt damit vorerst unnötig; nur später neu bewerten, falls zusätzliche externe Checks echten Mehrwert bringen.
- [x] MINI-PC-Status remote aktiviert/E2E-verifiziert: `CryptoMiniPC-StatusSync` HEALTHY; erster echter Remote-Status in Supabase angekommen. Der Pfad deckte unmittelbar zwei stale Read-only-Runtimes auf, daher ist die zentrale Statusschicht praktisch wirksam.
- [x] Health-Zustände klar unterscheiden: Taxonomie (`OK`, `WAITING_NO_DATA`, `FEED_STALE`, `API_DISCONNECTED`, `BACKLOG_STUCK`, `DEGRADED`, `STOPPED`) lokal aktiviert und physisch verifiziert; Effectiveness-Smoke 2026-10-01 **Overall HEALTHY / Operational state OK / State reasons none**.
- [x] Automatischer begrenzter Self-Heal für eindeutig technische Fehler verifiziert: Runtime-Supervisor 2-Minuten-Takt, 10-Minuten-Backoff, physischer Self-Heal-Smoke PASS; keine automatische Strategie-/Threshold-Änderung.
- [x] Kontrollierten Internet-Ausfall/Wiederkehr für die **aktiven Transportpfade** testen: 2026-10-01 PASS; Ethernet-Ausfall wurde erkannt, Kraken HTTPS/Canary/breiter EUR-Feed/Altrady/Watchdog erholten sich automatisch. Stale-Decision/Queue-Replay bleibt erst mit gekoppelter Strategie-Runtime separat zu beweisen.
- [x] Wiederverbindung auf **Strategie-Runtime-Ebene** verifiziert: korrigierter Reconciliation-Audit + Effectiveness-Watchdog liefen am MINI-PC im gebündelten Post-Fix-Test **PASS**; beide Exit-Codes 0, Overall HEALTHY, Operational state OK, Issues none. Kein blindes Replay/kein stale Runtime-Artefakt nach Neustart.
- [x] Neustart-Reconciliation für den aktuellen Paper-/Read-only-Stand verifiziert: lokaler MINI-PC-Zustand und GitHub-Artefakte sind nach dem realen Stromausfall konsistent; korrigierter Audit meldet 0 critical/warning und der physische Post-Fix-Test ist PASS. Exchange-Zustand bleibt erst für die spätere private Kraken-/Trading-API-Phase relevant.
- [x] GitHub-Cloudpfad als unabhängigen Fallback erhalten: der reale MINI-PC-Stromausfall am 2026-10-01 lieferte den Praxisnachweis. Während der MINI-PC/RDP offline war, liefen `Kraken EUR early sensor` und `Paper runtime evaluator and lifecycle` in GitHub weiter erfolgreich; weder MINI-PC noch Altrady sind alleiniger Trigger.
- [x] Tägliche Sicherung um 04:00 lokal aktiv; 14 Tage Retention; Watchdog alarmiert erst nach mindestens 7 Tagen ohne erfolgreiche Sicherung.
- [x] Restore-/Recovery-Smoke-Test vorhanden und nicht-destruktiv verifiziert; Restore erfolgt in temporäres Verzeichnis und überschreibt keinen Live-State.
- [ ] Grafana-Statusseite erst ergänzen, wenn stabile Metriken vorhanden sind; kein Dashboard nur um des Dashboards willen.

**Abschlusskriterium P2:** definierte Strom-, Internet-, Prozess- und Datenfehler können ohne Datenchaos und ohne stale Decisions überstanden werden.

---

## P3 — Realtime-Daten und Trigger: Kraken + Altrady + redundanter Pfad

- [x] Kraken WebSocket/REST auf dem Mini-PC als kontinuierliche, strategie-neutrale Primärdatenquelle aufgebaut und Recovery nachgewiesen: `CryptoMiniPC-KrakenUniverse`, Aktivierungsproof 500/500 Online-EUR-Paare bei 100% Coverage/0 Subscription-Errors; aktueller Universe-Stand wird live aus `AssetPairs` geladen (zuletzt 501/501 beobachtet). REST `AssetPairs` = Universe-Gate, WS-v2-Ticker = Event-Feed, Latest-Snapshot + Heartbeat only. Windows-Restart sowie kontrollierter Internet-Ausfall/Wiederkehr **PASS**. Die spätere Strategie-/Fresh-Recheck-Kopplung bleibt bewusst als separater V2R4-Releasepunkt offen.
- [x] Rohdatenhaltung begrenzt: Kraken-Universe hält nur Latest-Snapshot + Heartbeat, Shadow/Outcome speichert selektive Ereignis-/Ergebnis-Evidenz, keine endlosen Tick-/Orderbucharchive.
- [ ] Altrady als **zusätzlichen echten Echtzeit-Trigger** fertig anbinden, niemals als einzigen Trigger. Transportpfad + echter One-shot-Price-Alert E2E sind verifiziert. In Draft-PR #9 ist jetzt zusätzlich eine **inaktive, CI-grüne WAIT-Runtime-Kopplung** vorbereitet: lokal konsumierte Altrady-Ereignisse dürfen nur einen same-pair Kraken-Fresh-Check vorziehen; Kraken bleibt Bedingungswahrheit, Trigger-Match bleibt `FRESH_PAPER_RECHECK_ONLY`, kein Direktkauf. Offen bleibt der physische kombinierte Altrady→Kraken-Fresh-Recheck-Nachweis am Release-Gate sowie der belastbare Latenzvergleich mit Kraken-native/Legacy-Scanner. Kein erneuter reiner Transporttest nötig. Zusätzlich ist der kombinierte **lokale** Wakeup→Kraken-Condition→Fresh-Recheck-Pfad im Windows-shaped `MINI-PC V2R4 WAIT runtime smoke #1` PASS: 1 Wakeup, 1 Condition-Match, 1 Fresh-Recheck, 0 Duplikat-Rechecks; Trigger→Recheck-Start 0,002s. Offen bleibt nur noch der gleiche Nachweis mit einem **real transportierten** Altrady-Event am physischen MINI-PC im Release-Gate. Der noch offene reale Transportnachweis ist jetzt als isolierter, plan-only-default Harness `tools/minipc-v2r4-real-altrady-release-smoke.ps1` vorbereitet; am Release-Gate genügt ein frisches echtes Altrady-Event + ein expliziter Einmal-Lauf.
- [x] Altrady-Heartbeat/Fehlerrückmeldung überwachen: lokaler Watchdog + Runtime-Supervisor überwachen `CryptoMiniPC-AltradyTrigger`; der Pfad ist ausdrücklich zusätzlicher Trigger, Kraken-native/GitHub laufen unabhängig weiter.
- [x] V2R4 WS-Shadow auf dem MINI-PC aktivieren: 2026-10-01 physischer Smoke **PASS**, `CryptoMiniPC-V2R4WSShadow` **HEALTHY**, 500/500 Kraken-EUR-Paare, 0 stale inputs, Smoke-Quellalter Ø ~0,706 s / max ~2,175 s; Shadow bleibt ohne Evaluator/Orders.
- [x] **WS-shadow Zwischenfall 2026-10-01 geschlossen:** der Support-Prozess ist unter laufendem Supervisor wieder natürlich auf `HEALTHY / OK` zurückgekehrt; spätere zentrale Stichprobe zeigte frischen WS-shadow + frische Kraken-Quelle, Outcome/Cloud-Sync/Canary/Universe/Altrady/Supervisor gesund und `issues=[]`. Repository-Härtung gegen Heartbeat-Jitter/Fehlklassifikation ist CI-grün. Kein separater Notfall-Eingriff mehr nötig; der lokale Fast-Forward-Pull der Härtung bleibt im gebündelten Wartungs-/Release-Sync `tools/minipc-v2r4-readiness-sync.ps1`.
- [ ] V2R4 WS-Shadow prospektiv laufen lassen und auswerten: Feed→Discovery-Latenz, Eventrate/Triggergründe sowie **Post-Detection-Outcome (5m/15m/30m/1h/3h/6h, MFE/MAE)** messen. **Readiness-Snapshot 2026-10-01 15:01 UTC:** 335 prospektive Events, 34/34 fällige 6h-Outcomes archiviert (100%), davon 16 gap-free / 18 tracker-gap-affected; weiterhin nur operative Evidenz, keine Strategie-Performance-Freigabe. Restart-/Internet-Recovery des Shadow-Prozesses ist 2026-10-01 **PASS** (runtime=0, Internet=0, evidence=0, issues=none). Read-only Supabase-View `public.v2r4_shadow_completion_readiness` überwacht inzwischen Kohortenreife/6h-Archivabdeckung ohne Strategieeingriff. Erst nach belastbarer Evidenz separate V2R4-Paper-Aktivierung.
- [x] Prospektiven V2R4-Shadow-Outcome-Tracker lokal aktivieren: `CryptoMiniPC-V2R4ShadowOutcomes` seit 2026-10-01 **HEALTHY**; Startzustand 0 aktive/0 neu eingeschriebene Events, 18 ältere Events bewusst als pre-tracker ignoriert; nur neue Events zählen, kein retrospektives Backfill.
- [x] V2R4-Shadow-/Outcome-Evidenz automatisch in Supabase archivieren: `CryptoMiniPC-V2R4ShadowCloudSync` seit 2026-10-01 **HEALTHY**; erster echter Upload **23 Records / 1 Batch**, danach pending=0; Supabase unabhängig mit 23 Zeilen verifiziert. Fail-soft, server-only RLS, kein Admin-Key auf dem MINI-PC.
- [ ] Detektionslatenz Kraken-native vs. Scanner vs. Altrady weiter messen. Kraken-native WS-shadow + Legacy-Scanner bleiben zentral vergleichbar; für die eigentliche Pfadvergleichs-Freigabe ist jetzt zusätzlich `public.realtime_path_comparison_readiness` aktiv: enger same-pair-Match nur ±30m, separate ±5m/±15m-Zählung, Altrady-Transport separat, `ranking_allowed=false`. Snapshot ~16:12 UTC: 385 Shadow-Events, 27 Scanner-Matches <=30m / 21 <=15m / 11 <=5m; Altrady weiterhin nur 2 Transportfälle. Beide Vergleichsstati bleiben absichtlich `INSUFFICIENT_*`. **Keine Rangfolge ableiten**, bis identische Impulse explizit event-gematcht und die Stichproben ausreichend sind.
- [ ] Nach stabiler Basis den Takt anhand realer Messungen verkürzen; Ziel grob ~7–8 Minuten, wo ein periodischer Takt nötig ist, ergänzt durch schnellere eventbasierte Trigger.
- [x] Evaluator/KI nur ereignis-/kandidatenbezogen: `paper-evaluator.yml` hat keinen Cron-Dauerpoller; der Scanner dispatcht den Runtime-Lauf, das Modell wird nur für neue ungesehene Kandidaten <=60m bzw. fällige einmalige WAIT-Revalidierungen aufgerufen. Follow-up/Health laufen deterministisch ohne Modell.
- [ ] V2R4-Fast-Trigger-Pfad aus **Draft-PR #9**: alter PR #8 superseded/geschlossen; ursprünglicher V2R4-Delta auf aktuelle Architektur übertragen und anschließend um die fehlende **inaktive 24/7-WAIT-Plan-Lifecycle-Runtime** ergänzt. V2R4 PR validation **Run #14 SUCCESS** inkl. neuer Runtime-Tests; refreshed MINI-PC-Preflight **Run #4 SUCCESS**; Trigger→Fresh-Recheck E2E-Smoke **Run #2 SUCCESS** gegen PR #9. Kraken `AssetPairs` bleibt Universe-Wahrheit; Altrady ist nur Wakeup-Hinweis, nie Bedingungswahrheit/Direktkauf. Laufende Paper-State-Commits dürfen `main` weiterbewegen; finaler Sync erst am Aktivierungsreview. Offen: V2R3-Reife/Release-Review, expliziter Sizing-Entscheid, physischer kombinierter Altrady→Kraken-Recheck-Smoke und separater Paper-Aktivierungsentscheid. Windows-shaped WAIT-runtime-smoke #1 ist ebenfalls SUCCESS und beweist Kraken-Wahrheit + Altrady-Wakeup-only + Idempotenz.
- [ ] Nach bestandenem technischen Smoke **und** abgeschlossenem dokumentierten V2R3-Release-Review eine **separate V2R4-Paper-Serie** starten. Es besteht keine starre Pflicht auf genau 20 V2R3-Trades, weil der festgelegte alternative V2R3-Abschlussweg (7 Tage + >=1.000 Outcomes + >=95% fällige 24h-Coverage) gleichwertig gilt. V2R3-Artefakte bleiben danach unverändert als Vergleichsbasis.
- [x] Datenfrische und Entscheidungstimestamp technisch nachvollziehbar: im eingefrorenen V2R3-Vorgänger waren 708/708 geprüfte Outcomes vollständig mit candidate_detected_at, handoff_written_at, evaluation_started_at, evaluation_completed_at und fresh_kraken_ticker. Dieselbe unveränderte Record-/Schema-Pflicht gilt für die neue saubere Serie und wird dort erneut prospektiv überwacht.

**Abschlusskriterium P3:** derselbe relevante Move kann über mehr als einen unabhängigen Pfad erkannt werden und Timing ist messbar.

---

## P4 — Integrationen, Benachrichtigung und Kostenkontrolle

### Slack / Push
- [x] GitHub → Relay → Slack → iPhone-**echten Push** unter Realbedingungen nachgewiesen: 2026-10-01 echter GitHub-Relay/Webhook-Post mit realer `@Hoffis`-Mention, Workflow SUCCESS, Slack HTTP 200/ok und iPhone-Push angekommen.
- [x] Push-Regel technisch festgelegt/verifiziert: `#krypto-signale` mobil auf **Nur Erwähnungen**; Rohkandidaten ohne Mention bleiben still, Push nur für echte Handlung, wichtigen Fehler oder definiertes Abschlussereignis mit realer `@Hoffis`-Mention.
- [ ] Später unabhängigen zweiten Pushweg nur dann ergänzen, wenn er die Ausfallsicherheit wirklich verbessert.

### Supabase
- [x] Supabase-Archivpfad operativ und E2E-verifiziert: sichere GitHub-Backend-Credentials, minimales Schema, klarer Sync-Pfad; automatischer Nachzug nach erfolgreichem Paper-Runtime-Workflow.
- [x] Supabase bleibt strukturierte State-/Ergebnis-/Research-Schicht: Candidate-Outcomes, Trade-Results, Shadow-/Timing-Evidenz, Health-/Completion-State und kompakte Views; keine vollständige Tick-/Orderbuch-Rohdatenkopie.
- [x] Supabase bleibt fail-soft/sekundär; Ausfall stoppt Scanner/Paper-Pfad nicht.

### ChatGPT / Work / API
- [x] Projekt-Routinejobs sind aus ChatGPT Work herausgelöst, soweit technisch sinnvoll: Scanner/Evaluator-Lifecycle läuft in GitHub, Realtime/Watchdog/Backup/Shadow auf dem MINI-PC, strukturierter State in Supabase. Für den Regelbetrieb besteht keine Work-Dauerabhängigkeit.
- [x] Work-Rolle verbindlich begrenzt: nur gezielte, nicht sinnvoll über GitHub/MINI-PC/API lösbare Analyse-/Desktopaufgaben; **keine Dauerpoller und keine kritische Runtime-Abhängigkeit**.
- [ ] API-Verbrauch und Work-Credits getrennt überwachen und Kostenlimits/Guardrails festlegen.
- [x] Ereignisgesteuerte Analyse bevorzugt: Scanner→Evaluator ist Dispatch-basiert; ohne neue Kandidaten/fällige WAIT-Revalidation erfolgt kein neuer Modellentscheid. Health-, Archive-, Timing- und Completion-Watches laufen ohne KI.
- [ ] n8n Community erst später prüfen, wenn echte Orchestrierungs-Komplexität vorhanden ist; nicht vorsorglich einführen.

**Abschlusskriterium P4:** Benachrichtigung, State-Sync und KI-Aufrufe funktionieren sparsam, entkoppelt und ohne unnötige doppelte Dienste.

---

## P5 — Historische Daten-/Backtest-Schicht

- [x] **Preflight/Architektur ohne Bulk-Download abgeschlossen:** offizielle Kraken-OHLCVT-/Time-&-Sales-Quellen bis 30.06.2026, Checksummen/Part-Layout, C:-Speicherlayout, strikter Point-in-time-Vertrag, Kosten-/Fill-Guardrails, chronologische Walk-Forward/Purging/Embargo-Topologie und Trial-Ledger-Schema sind in `docs/historical-backtest-preflight.md` / `research/historical/` kanonisch festgelegt. GitHub-CI darf ausdrücklich **keine** großen Archive laden; Drive D bleibt gesperrt. Synthetischer Point-in-time-Smoke + Manifest-Preflight sind grün. **Physischer MINI-PC-Preflight 2026-10-01 PASS:** Historical-Verzeichnisbaum auf C: angelegt, Trial-Ledger init/verify PASS, 237.38 GB gesamt / 189.49 GB frei, keine Downloads und keine V2R3/V2R4-Runtimeänderung.
- [x] Kraken historische OHLCVT-Daten bis 30.06.2026 lokal/kompakt verfügbar: offizielles Full-Archive heruntergeladen + SHA-256 verifiziert; EUR/15m selektiv extrahiert und in **648** komprimierte normalisierte Dateien mit **20.960.798** Zeilen überführt. Historical Replay H1 wurde verworfen/insuffizient; der separat preregistrierte Second-Leg-**H2** wurde anschließend physisch auf Pre-2026-Development ausgeführt und **verfehlte den preregistrierten Gate** (positive-net-rate failed, Konzentrationsgate passed). 2026H1-Holdout blieb vollständig versiegelt: 0 Events, keine Metriken, keine Rule-Selection. Gemäß Vorabregel ist der H1/H2-Performancezweig geschlossen; kein H3/H4-Nachsuchen.
- [ ] Kraken historische Time-&-Sales-/Tickdaten gezielt für Fill-, Mikrostruktur- und Entry/Exit-Fragen nutzbar machen.
- [ ] Binance nur ergänzend für Cross-Market-/Derivatehistorie nutzen; Kraken-EUR bleibt Ausführungs- und Fill-Referenz.
- [ ] Public-Access/Verfügbarkeit von Binance auf der späteren Infrastruktur praktisch prüfen; Account nur einbinden, wenn für den vorgesehenen Datenpfad tatsächlich nötig.
- [x] Point-in-time Feature-Erzeugung mit sauberer Timestamp-Semantik technisch nachgewiesen: closed-bar cutoff, keine Zero-Fills, Post-Decision-Labels und Future-data-injection-Rejection in Smokes/Replay-Validatoren verankert.
- [x] Immutable Trial Ledger/Search Accounting für historische Research-Trials eingeführt; Duplicate-Trial-Rejection + Ledger-Verify grün. Neue Varianten dürfen nur als neuer preregistrierter Trial hinzukommen.
- [x] Chronologische Entwicklungs-/Validation-/Holdout-Trennung inklusive Purging/Embargo-Topologie und versiegeltem 2026H1-Holdout technisch abgebildet; H2-Gate-Failure bestätigte praktisch, dass der Holdout geschlossen bleibt.
- [ ] Kostenmodell weiter verfeinern: H1/H2 nutzten bewusst den preregistrierten konservativen Primäransatz **1,40 % Roundtrip**; für spätere echte Entry/Exit-/Fill-Fragen bleiben per-event Kraken-Spread, Slippage, Turnover und Re-Entry-Kosten über gezielte Time-&-Sales/Mikrostrukturtests offen.
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
- [x] Kraken-Tradability nicht mehr über statische Chat-/Whitelist pflegen: operative Quelle ist live pro Lauf/Watcher-Zyklus die aktuelle öffentliche Kraken-`AssetPairs`-Liste; nur `online` Spot-EUR zählt. Ein ~14-Tage-Audit darf höchstens als Alias-/Listing-Integritätscheck bleiben, ist aber **nicht** die operative Handelbarkeitsquelle.
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

- [x] Jede Entscheidung mit Strategieversion + Fingerprints nachvollziehbar: im diagnostisch eingefrorenen Vorgänger enthielten 708/708 geprüfte Outcomes `strategy_revision`, `strategy_fingerprint_sha256` und `runtime_code_fingerprint_sha256`; dieselbe unveränderte Provenance-Pflicht bleibt für `PAPER-V2R3-CLEAN-20261001T0925Z` aktiv.
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

- [ ] **V2R4 Paper-Aktivierungsentscheid** bleibt separat offen. Technische Kernpfade sind weitgehend vorbereitet/CI-grün; aktueller Fail-Closed-Control-State ist `BLOCKED_V2R3_COMPLETION`. Vor Aktivierung: reife V2R3-Evidenzsicht, expliziter Sizing-Entscheid (Timing-Isolation 50+50 methodisch bevorzugt, nicht automatisch autorisiert), finaler PR-Sync, gebündelter MINI-PC-Readiness-Sync, kleiner Release-Smoke, klarer Serienstart/Rollback. Keine Echtgeldaktion.
