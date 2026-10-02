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
- Test-Triage / Autonomie / No-Repeat: `docs/test-strategy-runbook.md`
- V3 Research-Chronik: GitHub Issue #7
- Action-Push / Slack-E2E: GitHub Issue #1

---

## P0 — Laufende V2R3-Serie sauber beenden und auswerten
- [x] Runtime-Persistenzfehler 2026-10-01 erkannt und repariert: Follow-up-No-op-Churn + `status|grep -q` unter pipefail konnte reale Änderungen als „keine Änderungen“ behandeln; reale Logs zeigen wiederholte Evaluation derselben Kandidaten vor Commit. Vorgänger-Serie mit 712 Outcomes als `DIAGNOSTIC_COMPROMISED` eingefroren, saubere identische V2R3-Serie ab 09:25 UTC neu gestartet.
- [x] Clean-Series-Persistenzproof bestanden: erster echter Post-Repair-Scannerlauf → 3 Kandidaten → 3 Entscheidungen im selben Runtime-Lauf committed; separater Repeat-Guard-Lauf selektierte danach `[]`, Follow-up änderte 0 Dateien, Process-Health HEALTHY mit 3/3 vollständiger Provenance und 0 Orphans.
- [x] Auswertungsinfrastruktur für die spätere Abschlussanalyse vorbereitet, ohne V2R3 zu verändern: `public.v2r3_interim_horizon_summary` bündelt unreife 30/60/120/360m-/Post-Detection-Horizonte mit Interpretations-Guardrail; `public.v2r3_reason_family_events` / `public.v2r3_reason_family_rollup` normalisieren freie Reason-Codes nur post-hoc/deskriptiv. `public.v2r3_release_review_snapshot` bleibt der single-row Evidence-Pack; zusätzlich rendert `tools/render-v2r3-final-review.py` daraus erst bei `final_review_allowed=true` einen Markdown-Abschlussreview. Unreife Snapshots werden fail-closed als BLOCKED behandelt; Strategy-/V2R4-/Echtgeld-Automatik bleibt verboten. **V2R3 final review renderer guard Run #1 SUCCESS**. Keine dieser Ebenen darf vor dem Abschluss-Gate zum Tuning genutzt werden.

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
- [ ] Altrady als **zusätzlichen echten Echtzeit-Trigger** fertig anbinden, niemals als einzigen Trigger. Transportpfad + echter One-shot-Price-Alert E2E sind verifiziert. In Draft-PR #9 ist jetzt zusätzlich eine **inaktive, CI-grüne WAIT-Runtime-Kopplung** vorbereitet: lokal konsumierte Altrady-Ereignisse dürfen nur einen same-pair Kraken-Fresh-Check vorziehen; Kraken bleibt Bedingungswahrheit, Trigger-Match bleibt `FRESH_PAPER_RECHECK_ONLY`, kein Direktkauf. Offen bleibt der physische kombinierte Altrady→Kraken-Fresh-Recheck-Nachweis am Release-Gate sowie der belastbare Latenzvergleich mit Kraken-native/Legacy-Scanner. Kein erneuter reiner Transporttest nötig. Zusätzlich ist der kombinierte **lokale** Wakeup→Kraken-Condition→Fresh-Recheck-Pfad im Windows-shaped `MINI-PC V2R4 WAIT runtime smoke #1` PASS: 1 Wakeup, 1 Condition-Match, 1 Fresh-Recheck, 0 Duplikat-Rechecks; Trigger→Recheck-Start 0,002s. Offen bleibt nur noch der gleiche Nachweis mit einem **real transportierten** Altrady-Event am physischen MINI-PC im Release-Gate. Der noch offene reale Transportnachweis ist jetzt als isolierter, plan-only-default Harness `tools/minipc-v2r4-real-altrady-release-smoke.ps1` vorbereitet; am Release-Gate genügt ein frisches echtes Altrady-Event + ein expliziter Einmal-Lauf. Harness-CI ist jetzt vollständig grün: MINI-PC tools smoke **Run #111 SUCCESS**.
- [x] Altrady-Heartbeat/Fehlerrückmeldung überwachen: lokaler Watchdog + Runtime-Supervisor überwachen `CryptoMiniPC-AltradyTrigger`; der Pfad ist ausdrücklich zusätzlicher Trigger, Kraken-native/GitHub laufen unabhängig weiter.
- [x] V2R4 WS-Shadow auf dem MINI-PC aktivieren: 2026-10-01 physischer Smoke **PASS**, `CryptoMiniPC-V2R4WSShadow` **HEALTHY**, 500/500 Kraken-EUR-Paare, 0 stale inputs, Smoke-Quellalter Ø ~0,706 s / max ~2,175 s; Shadow bleibt ohne Evaluator/Orders.
- [x] **WS-shadow Zwischenfall 2026-10-01 geschlossen:** der Support-Prozess ist unter laufendem Supervisor wieder natürlich auf `HEALTHY / OK` zurückgekehrt; spätere zentrale Stichprobe zeigte frischen WS-shadow + frische Kraken-Quelle, Outcome/Cloud-Sync/Canary/Universe/Altrady/Supervisor gesund und `issues=[]`. Repository-Härtung gegen Heartbeat-Jitter/Fehlklassifikation ist CI-grün. Der gebündelte lokale Fast-Forward-/Readiness-Sync wurde anschließend physisch durchgeführt: MINI-PC auf `29cafc3d4479604c0ec549b43f9de91ba6007d91`, Watchdog-Effectiveness PASS, V2R4-Preflight PASS, Backup-Restore PASS. Die korrigierte Taxonomie klassifiziert bei frischer Kraken-Quelle einen alten Shadow-Support-Heartbeat nun als `DEGRADED` statt fälschlich `FEED_STALE`.
- [ ] V2R4 WS-Shadow prospektiv laufen lassen und auswerten: Feed→Discovery-Latenz, Eventrate/Triggergründe sowie **Post-Detection-Outcome (5m/15m/30m/1h/3h/6h, MFE/MAE)** messen. **Readiness-Snapshot 2026-10-01 15:01 UTC:** 335 prospektive Events, 34/34 fällige 6h-Outcomes archiviert (100%), davon 16 gap-free / 18 tracker-gap-affected; weiterhin nur operative Evidenz, keine Strategie-Performance-Freigabe. Restart-/Internet-Recovery des Shadow-Prozesses ist 2026-10-01 **PASS** (runtime=0, Internet=0, evidence=0, issues=none). Read-only Supabase-View `public.v2r4_shadow_completion_readiness` überwacht inzwischen Kohortenreife/6h-Archivabdeckung ohne Strategieeingriff. Erst nach belastbarer Evidenz separate V2R4-Paper-Aktivierung.
- [x] Prospektiven V2R4-Shadow-Outcome-Tracker lokal aktivieren: `CryptoMiniPC-V2R4ShadowOutcomes` seit 2026-10-01 **HEALTHY**; Startzustand 0 aktive/0 neu eingeschriebene Events, 18 ältere Events bewusst als pre-tracker ignoriert; nur neue Events zählen, kein retrospektives Backfill.
- [x] V2R4-Shadow-/Outcome-Evidenz automatisch in Supabase archivieren: `CryptoMiniPC-V2R4ShadowCloudSync` seit 2026-10-01 **HEALTHY**; erster echter Upload **23 Records / 1 Batch**, danach pending=0; Supabase unabhängig mit 23 Zeilen verifiziert. Fail-soft, server-only RLS, kein Admin-Key auf dem MINI-PC.
- [ ] Detektionslatenz Kraken-native vs. Scanner vs. Altrady weiter messen. Kraken-native WS-shadow + Legacy-Scanner bleiben zentral vergleichbar; für die eigentliche Pfadvergleichs-Freigabe ist jetzt zusätzlich `public.realtime_path_comparison_readiness` aktiv: enger same-pair-Match nur ±30m, separate ±5m/±15m-Zählung, Altrady-Transport separat, `ranking_allowed=false`. Snapshot ~16:12 UTC: 385 Shadow-Events, 27 Scanner-Matches <=30m / 21 <=15m / 11 <=5m; Altrady weiterhin nur 2 Transportfälle. Beide Vergleichsstati bleiben absichtlich `INSUFFICIENT_*`. **Keine Rangfolge ableiten**, bis identische Impulse explizit event-gematcht und die Stichproben ausreichend sind.
- [ ] Nach stabiler Basis den Takt anhand realer Messungen verkürzen; Ziel grob ~7–8 Minuten, wo ein periodischer Takt nötig ist, ergänzt durch schnellere eventbasierte Trigger.
- [x] Evaluator/KI nur ereignis-/kandidatenbezogen: `paper-evaluator.yml` hat keinen Cron-Dauerpoller; der Scanner dispatcht den Runtime-Lauf, das Modell wird nur für neue ungesehene Kandidaten <=60m bzw. fällige einmalige WAIT-Revalidierungen aufgerufen. Follow-up/Health laufen deterministisch ohne Modell.
- [ ] V2R4-Fast-Trigger-Pfad aus **Draft-PR #9**: alter PR #8 superseded/geschlossen; ursprünglicher V2R4-Delta auf aktuelle Architektur übertragen und anschließend um die fehlende **inaktive 24/7-WAIT-Plan-Lifecycle-Runtime** ergänzt. V2R4 PR validation **Run #14 SUCCESS** inkl. neuer Runtime-Tests; refreshed MINI-PC-Preflight **Run #4 SUCCESS**; Trigger→Fresh-Recheck E2E-Smoke **Run #2 SUCCESS** gegen PR #9. Kraken `AssetPairs` bleibt Universe-Wahrheit; Altrady ist nur Wakeup-Hinweis, nie Bedingungswahrheit/Direktkauf. Laufende Paper-State-Commits dürfen `main` weiterbewegen; finaler Sync erst am Aktivierungsreview. Offen: V2R3-Reife/Release-Review, expliziter Sizing-Entscheid, physischer kombinierter Altrady→Kraken-Recheck-Smoke und separater Paper-Aktivierungsentscheid. Windows-shaped WAIT-runtime-smoke #1 ist ebenfalls SUCCESS und beweist Kraken-Wahrheit + Altrady-Wakeup-only + Idempotenz.
- [ ] Nach bestandenem technischen Smoke **und** abgeschlossenem dokumentierten V2R3-Release-Review eine **separate V2R4-Paper-Serie** starten. Es besteht keine starre Pflicht auf genau 20 V2R3-Trades, weil der festgelegte alternative V2R3-Abschlussweg (7 Tage + >=1.000 Outcomes + >=95% fällige 24h-Coverage) gleichwertig gilt. V2R3-Artefakte bleiben danach unverändert als Vergleichsbasis.
- [x] Datenfrische und Entscheidungstimestamp technisch nachvollziehbar: im eingefrorenen V2R3-Vorgänger waren 708/708 geprüfte Outcomes vollständig mit candidate_detected_at, handoff_written_at, evaluation_started_at, evaluation_completed_at und fresh_kraken_ticker. Dieselbe unveränderte Record-/Schema-Pflicht gilt für die neue saubere Serie und wird dort erneut prospektiv überwacht.

- [x] Gebündelter MINI-PC-Wartungs-/Readiness-Sync am 2026-10-01 erfolgreich abgeschlossen: lokaler Altstand war direkter Vorfahr von `main` (123 Commits Rückstand, 0 Divergenz), Fast-Forward ohne Merge/Rebase; `.paper-work/` als reproduzierbares Audit-Artefakt dauerhaft aus Git-Status ausgeschlossen; Post-Pull-Helpers, Watchdog-Effectiveness, isolierter V2R4-Preflight und Backup-Restore jeweils **PASS**. Keine Strategie-/Evaluator-/Paper-Aktivierung und keine Order-/Echtgeldaktion. Ein finaler Release-Boundary-Sync bleibt nur deshalb später erneut vorgesehen, weil laufende Runtime-/Dokumentations-Commits `main` bis dahin weiterbewegen dürfen.

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
- [x] **API-Aufrufverbrauch strukturell überwacht:** Supabase `paper_model_invocation_events`, `paper_model_usage_daily` und `paper_model_usage_guard` zählen Initial-/Revalidation-Calls, HTTP-Attempts, Retry-Overhead, Duplicate-Response-IDs und unzulässige Revalidation-Pfade ohne Änderung des eingefrorenen V2R3-Evaluators. Clean-Serie bei Einführung: 78 Outcomes / 141 logische Calls / 141 HTTP-Attempts / 0 Retries / 0 Duplicate-IDs / max Attempt 1 → `HEALTHY`. Der bestehende Completion-Watch prüft Usage-Anomalien still und pusht nur beim Übergang auf `ANOMALY`; Workflow-Run #5 SUCCESS. Details: `docs/ai-api-cost-guardrails.md`.
- [ ] **Exakte Token-/€-Kosten und ChatGPT-Work-Credits getrennt abschließen:** V2R3 persistiert aktuell keine Responses-`usage`-Tokens; eine Instrumentierung würde den eingefrorenen Runtime-Fingerprint ändern und bleibt daher bis zur nächsten expliziten Runtime-Version gesperrt. Work-Credits sind ein separates Produktkonto und dürfen nicht aus API-Calls geschätzt werden. Vor späterer monetärer Hard-Cap: Token-Usage in neuer Runtime-Version + versionierte Preistabelle + nutzerfreigegebener Budgetwert; keine automatische Strategie-/Budgetänderung.
- [x] Ereignisgesteuerte Analyse bevorzugt: Scanner→Evaluator ist Dispatch-basiert; ohne neue Kandidaten/fällige WAIT-Revalidation erfolgt kein neuer Modellentscheid. Health-, Archive-, Timing- und Completion-Watches laufen ohne KI.
- [ ] n8n Community erst später prüfen, wenn echte Orchestrierungs-Komplexität vorhanden ist; nicht vorsorglich einführen.

**Abschlusskriterium P4:** Benachrichtigung, State-Sync und KI-Aufrufe funktionieren sparsam, entkoppelt und ohne unnötige doppelte Dienste.

---

## P5 — Historische Daten-/Backtest-Schicht

- [x] **Preflight/Architektur ohne Bulk-Download abgeschlossen:** offizielle Kraken-OHLCVT-/Time-&-Sales-Quellen bis 30.06.2026, Checksummen/Part-Layout, C:-Speicherlayout, strikter Point-in-time-Vertrag, Kosten-/Fill-Guardrails, chronologische Walk-Forward/Purging/Embargo-Topologie und Trial-Ledger-Schema sind in `docs/historical-backtest-preflight.md` / `research/historical/` kanonisch festgelegt. GitHub-CI darf ausdrücklich **keine** großen Archive laden; Drive D bleibt gesperrt. Synthetischer Point-in-time-Smoke + Manifest-Preflight sind grün. **Physischer MINI-PC-Preflight 2026-10-01 PASS:** Historical-Verzeichnisbaum auf C: angelegt, Trial-Ledger init/verify PASS, 237.38 GB gesamt / 189.49 GB frei, keine Downloads und keine V2R3/V2R4-Runtimeänderung.
- [x] Kraken historische OHLCVT-Daten bis 30.06.2026 lokal/kompakt verfügbar: offizielles Full-Archive heruntergeladen + SHA-256 verifiziert; EUR/15m selektiv extrahiert und in **648** komprimierte normalisierte Dateien mit **20.960.798** Zeilen überführt. Historical Replay H1 wurde verworfen/insuffizient; der separat preregistrierte Second-Leg-**H2** wurde anschließend physisch auf Pre-2026-Development ausgeführt und **verfehlte den preregistrierten Gate** (positive-net-rate failed, Konzentrationsgate passed). 2026H1-Holdout blieb vollständig versiegelt: 0 Events, keine Metriken, keine Rule-Selection. Gemäß Vorabregel ist der H1/H2-Performancezweig geschlossen; kein H3/H4-Nachsuchen.
- [ ] Kraken historische Time-&-Sales-/Tickdaten gezielt für Fill-, Mikrostruktur- und Entry/Exit-Fragen nutzbar machen. **Remote-Methodik vorbereitet 2026-10-01:** `research/historical/kraken-trades-targeted-preflight-v1.json` + `tools/kraken-trades-targeted-smoke.py` definieren einen strikt gezielten, point-in-time-sauberen Parser-/Mikrostrukturpfad ohne Download. Erlaubt sind u. a. Arrival→Next-Public-Trade-Latenz, Trade-Dichte/Intertrade-Gaps, VWAP und Buy/Sell-Flow; ausdrücklich **nicht** aus Public Trades allein ableitbar sind echter Bid/Ask-Spread, Orderbuch-Tiefe, Queue-Position oder Maker-Fill-Wahrscheinlichkeit. Zusätzlich sperrt `research/historical/kraken-trades-storage-benefit-gate-v1.json` den ca. 26-GB-Full-Download fail-closed, bis konkrete nicht anderweitig beantwortbare Mikrostrukturfragen, definierte Pair/Window-Scope, PIT-Smoke und ausreichende Speicherreserve belegt sind. `tools/run-minipc-kraken-trades-targeted-smoke.ps1` ist plan-only by default und darf im Execute-Modus ausschließlich eine bereits lokal unter `Trading\Historical` vorhandene CSV lesen; kein Netzwerk/Download. Performance-Selektion/Holdout-Öffnung bleiben gesperrt. Repository-/CI-Gate ist inzwischen vollständig grün: synthetischer PIT-Smoke, Identifiability-Guardrails, Storage-Benefit-Gate und plan-only MINI-PC-Orchestrator; Historical data preflight **Run #57 SUCCESS**.
- [ ] Binance nur ergänzend für Cross-Market-/Derivatehistorie nutzen; Kraken-EUR bleibt Ausführungs- und Fill-Referenz. **Methodik remote vorbereitet/CI-grün 2026-10-01:** `research/historical/binance-derivatives-context-preflight-v1.json` + `tools/binance-derivatives-context-smoke.py` frieren öffentliche USD-M-Funding/OI/Taker/Basis/Long-Short-Metriken strikt am Event-Zeitpunkt ein; zukünftige Zeilen, Silent Gap Fill, aktuelle-Universe-Survivorship und jede Kraken-EUR-Fill-/Spread-/Tradability-Autorität sind gesperrt. Historische API-Fenster werden nicht als Vollhistorie ausgegeben; Bulk-/Archivdownload bleibt unautorisiert. Historical data preflight **Run #61 SUCCESS**. Offen bleibt erst die spätere Verwendung in einem preregistrierten Research-Trial.
- [x] Public-Access/Verfügbarkeit von Binance auf der späteren Infrastruktur praktisch geprüft: MINI-PC **HEALTHY** ohne API-Key/Konto/Orders; Spot Server Time 327,3 ms, BTCUSDT Premium/Funding 300,4 ms, Open Interest 260,7 ms. Evidence: `research/v3/physical-gates/v3-physical-gate-evidence-20261002.json`. Binance bleibt ausschließlich supplementärer Cross-Market-/Derivatekontext; Kraken-EUR bleibt Ausführungs-/Tradability-Wahrheit.
- [x] Point-in-time Feature-Erzeugung mit sauberer Timestamp-Semantik technisch nachgewiesen: closed-bar cutoff, keine Zero-Fills, Post-Decision-Labels und Future-data-injection-Rejection in Smokes/Replay-Validatoren verankert.
- [x] Immutable Trial Ledger/Search Accounting für historische Research-Trials eingeführt; Duplicate-Trial-Rejection + Ledger-Verify grün. Neue Varianten dürfen nur als neuer preregistrierter Trial hinzukommen.
- [x] Chronologische Entwicklungs-/Validation-/Holdout-Trennung inklusive Purging/Embargo-Topologie und versiegeltem 2026H1-Holdout technisch abgebildet; H2-Gate-Failure bestätigte praktisch, dass der Holdout geschlossen bleibt.
- [ ] Kostenmodell weiter verfeinern: H1/H2 nutzten bewusst den preregistrierten konservativen Primäransatz **1,40 % Roundtrip**; für spätere echte Entry/Exit-/Fill-Fragen bleiben per-event Kraken-Spread, Slippage, Turnover und Re-Entry-Kosten über gezielte Time-&-Sales/Mikrostrukturtests offen.
- [ ] Rohdaten nach Testzweck komprimieren/aggregieren/löschen; historische Daten nicht in GitHub aufblasen. **Lifecycle remote vorbereitet/CI-grün 2026-10-01:** `docs/historical-storage-lifecycle.md` + read-only `tools/plan-historical-storage-cleanup.py` klassifizieren Raw-Archive als Provenance-KEEP, Catalog/Trials/Reports/Normalized/Derived als geschützt, alte `staging/`-/`tmp/`-Dateien nur als `DELETE_CANDIDATE`, unbekannte Pfade als `HOLD_UNKNOWN`; der Planner löscht selbst nichts. Redundante Kraken-OHLCVT-Parts bleiben ausschließlich über den separaten checksum-gated Cleanup löschbar. Historical data preflight **Run #62 SUCCESS**. Offen bleibt der spätere lokale Audit/ggf. bestätigte Cleanup tatsächlicher Kandidaten.

**Abschlusskriterium P5:** reproduzierbarer historischer Test mit point-in-time Daten, realistischen Kosten und klarer Versions-/Trial-Historie.

---

## P6 — V3 aus Evidenz bauen, nicht aus Bauchgefühl

Detailregeln bleiben in `docs/v3-research-framework.md` und Issue #7. Die Abgrenzung zu V2R4 ist verbindlich in `docs/strategy-version-map.md` festgelegt.

- [ ] V2R3-Abschlussbefunde vollständig in den V3-Aufbau übernehmen; V3 startet vom besten validierten V2/V2R4-Gesamtstand, nicht bei null.
- [x] V2/V2R4→V3-Migrationsledger ist als lebender, maschinenlesbarer Kontrollpunkt eingerichtet: `research/v3-migration-ledger.json` klassifiziert aktuell 23 materielle Komponenten mit den verbindlichen Statuswerten; ungelöste Strategiebausteine bleiben bewusst `OPEN_RESEARCH` mit benanntem Next-Gate. `tools/validate-v3-migration-ledger.py` + selbsttestender Workflow sind fail-closed; **V3 migration ledger guard Run #1 SUCCESS**. Der Ledger wird mit neuer Evidenz fortgeschrieben, ersetzt aber nicht das jeweilige Research-/Release-Gate.
- [x] Literaturbefunde sind verbindlich nur Hypothesenquelle: `docs/v3-research-framework.md` verbietet Promotion allein wegen Publikation und verlangt lokale PIT/OOS-/prospektive Evidenz, Kosten, Trial-Ledger und Promotion-Gate; ein Search darf ausdrücklich **keinen Gewinner** liefern. H1/H2-Performancezweig hat diese Regel praktisch bereits durch Fail/Stop statt Nachoptimierung bestätigt.
- [x] Mini-PC-/Altrady-Timingdaten sind als eigener V3-Evidenzpfad zentralisiert: `public.v3_timing_evidence_snapshot` bündelt die aktive V2R3-Initial-/WAIT-Revalidation-Timingkette, V2R4-Shadow-Reife und den Kraken-native/Scanner/Altrady-Vergleich. Der Snapshot setzt `infrastructure_variant_before_rule_relaxation=true`, während `automatic_entry_rule_change_allowed=false` und `automatic_strategy_promotion_allowed=false` bleiben. Aktuell: Initial-Eval p50 ~38–40 s; WAIT-TTL-Lag p50 ~252 s / p90 ~912 s; Pfad-Ranking weiterhin gesperrt wegen unzureichender Scanner-/Altrady-Vergleichssamples. Die spätere strategische Interpretation bleibt in den jeweiligen V3-Komponenten offen.
- [x] **One-change Shadow-Candidate-Contract technisch erzwungen:** `research/v3/shadow-candidate-contract-v1.json` + `tools/validate-v3-shadow-candidate.py` verlangen exakt einen `changed_components`-Baustein, gleiche Candidate-Stream/Market-Clock, frozen Config-Hash, vorab definierte Sample-/Kosten-/Promotion-Gates und verbieten Mid-run-Tuning/Auto-Promotion. Multi-Change und unfertige Frozen-Candidates werden fail-closed abgelehnt; Guard **Run #1 SUCCESS**.
- [ ] Tatsächliche V3-Shadow-Varianten nach dieser One-change-Regel erst starten, sobald der jeweilige Hypothesen-/Daten-Gate reif ist; Beispiele: früherer Entry **oder** TTL **oder** Stop/Trailing **oder** Exit, niemals als untrennbares Bundle.
- [ ] Erfolgreiche Shadow-Trades auf gemeinsame Mechanismen untersuchen; Gewinnerbeobachtung anschließend historisch/OOS gegenprüfen.
- [ ] H1 Cross-Crypto Lead/Lag + Breadth testen. **Incremental physical execution PASS:** `V3-H1-INCR-001` lief am MINI-PC im gebündelten H1/H6-Gate erfolgreich; Trial-Ledger verify PASS, Gesamtstand 8 Trials / `corrupt_trial_ids=[]`, Holdout CLOSED. Lokaler Report: `v3-h1-incremental-001-20261002-095841.json`. Kanonischer Ausführungsstatus: `research/v3/h1-h6-incremental-execution-status-20261002.json`. Der exakte Report-Payload/Hash ist noch nicht in GitHub importiert; deshalb bleibt die quantitative Effektgrößenbewertung ausdrücklich offen und es gibt keine Winner-/Threshold-/Promotion-Freigabe. **Nächster Gate:** Report-Payload importieren und die fest vorregistrierten Partial-Correlation-Effektgrößen mit Search Accounting bei weiter versiegeltem Holdout reviewen.
- [ ] H2 Basis/Premium/Funding/OI als State/Conditioning testen. **Precheck/Association-Contract/Response-Shape/Parser + isolierter Candidate-Capture jetzt grün:** H2 Guard Run #8 SUCCESS. Smoke: XBT-Candidate → `PF_XBTUSD` in 0,37 s Mapping-Lag; `open-interest`, `funding`, `future-basis` jeweils CAPTURED aus demselben 5m-Bucket mit 32 s Metric-Age. 4er-Payloads bleiben opak, Timestamp-Einheiten werden strikt normalisiert, `to=candidate_time`, Future-Row fail-closed, Missing behält Candidate. Der Capture-CLI ist **nicht** an Scanner/Handoff/Timer gekoppelt und hat keinen Auto-Schedule; Candidate-Entscheidung, V2R3/V2R4, Orders und Holdout bleiben unangetastet. Nächster Gate = erst nach separatem Review einen echten prospektiven Candidate in einen Research-Stream capturen; bis dahin keine automatische Kopplung und kein Performance-/Threshold-Test.
- [ ] H4 regimeabhängige Stop-/TTL-Logik aus MAE/MFE testen. **Data-Readiness-Precheck grün:** `research/v3/h4-regime-stop-ttl-precheck-v1.json` friert die spätere Testlogik fail-closed ein. Snapshot: 84 Kandidaten; MAE/MFE reif bei 30m/60m/120m/360m = 75/66/57/28, aber **0 reife 24h-MAE/MFE und 0 Trade-Returns**. Deshalb noch kein Stop-/TTL-/Trailing-Tuning. Später exakt eine Änderung pro Trial, gleiches Candidate-Stream/Clock, PIT-Regime vor Metrics einfrieren; kein Holdout/keine Runtime-Änderung. H4 Guard **SUCCESS**.
- [ ] H5 Makro-Event-Risk-Gate testen. **PRECHECK/PIT-Methodik grün + offizieller Kalender-Capture validiert + exakt eine Risk-Variante preregistriert:** `V3-H5-FOMC-STATEMENT-NO-NEW-ENTRY-30M30M-V1` ändert ausschließlich `RISK_GATE`: im späteren Candidate-Shadow keine neuen Entries von 30 Min. vor bis 30 Min. nach dem FOMC-Policy-Statement; Baseline-Runtime, bestehende Positionen, Sizing, Stop, Trailing, WAIT/TTL und Signal-Score bleiben unverändert. Auswahl erfolgte vor jedem realen FOMC-Performance-Trial aus dem bereits synthetisch geprüften 30/30-Minuten-Method-Smoke; kein Parameter-Sweep/Holdout. Aktiver V2R3/V2R4-Pfad bleibt unangetastet. Nächster Gate = nach finalem Baseline-Freeze als One-Change-V3-Shadow-Candidate materialisieren und erst dann prospektiv laufen lassen.
- [ ] H6 einfache Price×Volume-Trend-Primitiven testen. **Incremental physical execution PASS:** `V3-H6-INCR-001` lief am MINI-PC im selben gebündelten Gate erfolgreich; Trial-Ledger verify PASS, Gesamtstand 8 Trials / `corrupt_trial_ids=[]`, Holdout CLOSED. Lokaler Report: `v3-h6-incremental-001-20261002-095841.json`. Kanonischer Ausführungsstatus: `research/v3/h1-h6-incremental-execution-status-20261002.json`. Der exakte Report-Payload/Hash ist noch nicht in GitHub importiert; deshalb bleibt die quantitative Volumen-Zusatznutzenbewertung ausdrücklich offen und es gibt keine Winner-/Threshold-/Promotion-Freigabe. **Nächster Gate:** Report-Payload importieren und den fest vorregistrierten inkrementellen Volumenbeitrag mit Search Accounting bei weiter versiegeltem Holdout reviewen.
- [ ] H3 Orderflow/Depth/Imbalance erst mit Mini-PC-WebSocket-Daten produktiv erforschen. **`V3-H3-ASSOC-001` technisch INVALID, kein Marktergebnis:** erste 1800-s-MINI-PC-Ausführung schrieb BTC/ETH/SOL jeweils 0 Samples und endete FAIL. Root Cause: Sampling-Zweig im Runner war logisch unerreichbar (`timeout>=0.01`, danach Prüfung `timeout<=0`). Ledger blieb integer (9 Trials, 0 korrupt); der fehlerhafte Trial bleibt immutable dokumentiert, zählt aber weder als gültige Session noch als Effekt-Evidenz. Ersatztrial **`V3-H3-ASSOC-002`** behält Forschungsfrage, Symbole, Features, Horizonte und Collection-Gate unverändert; nur Scheduler-Implementierung wurde korrigiert. **Cloud-Real-WS Regression-Smoke Run #10 SUCCESS:** 30 s, BTC/ETH/SOL jeweils 6 feste 5-s-Samples, `status=PASS`; Compile/Self-Test/Ledger-/Wrapper-/Contract-Guards ebenfalls grün. **Physischer MINI-PC-Smoke PASS:** 30 s, BTC=6 / ETH=6 / SOL=5 Samples, 913 Wire-Messages, 3 Subscription-Acks; Smoke zählt ausdrücklich nicht zum Collection-Gate. Kanonische Evidenz: `research/v3/h3-assoc-002-minipc-smoke-evidence-20261002.json`. **Erste gültige 1800-s-MINI-PC-Session PASS:** `V3-H3-ASSOC-002-20261002T093220Z`, BTC=352 / ETH=348 / SOL=344 Rows; Ledger PASS bei 10 Trials / 0 korrupt. Collection-Gate aktuell: 1 eligible Session, 1 UTC-Tag, gate_met=false. Kanonische Evidenz: `research/v3/h3-assoc-002-valid-session-001-20261002.json`. **Zweite gültige 1800-s-MINI-PC-Session PASS:** `V3-H3-ASSOC-002-20261002T101132Z`, BTC=353 / ETH=349 / SOL=349 Rows. Collection-Gate kumuliert: 2 eligible Sessions, 1 UTC-Tag, BTC=705 / ETH=697 / SOL=693, gate_met=false. Kanonische Evidenz: `research/v3/h3-assoc-002-valid-session-002-20261002.json`. **Nächster Gate:** genau eine weitere gültige 1800-s-Session an einem zweiten UTC-Tag; bei ähnlicher Row-Zahl sollte damit zugleich die 1000er-Grenze je Symbol erreicht werden. Gültiges Collection-Gate bleibt >=3 Sessions à >=1800 s über >=2 UTC-Tage und >=1000 valide Feature-Rows je Symbol.
- [ ] H7 Meta TAKE/NO-TAKE erst nach genügend sauberen Labels. **Readiness-Gate aktiv:** `research/v3/h7-meta-gate-readiness-v1.json` + `public.v3_h7_meta_gate_readiness` blockieren Training fail-closed. Aktuell: V2R3 `completion_ready=false`, 84 Outcomes, 0 Trades, 0 reife 24h-Fälle, Integrität `HEALTHY`, Labeldefinition `NOT_FROZEN`, `meta_training_allowed=false`. Vor Training zwingend: finaler V2R3-Review, frozen Label-/Kostenvertrag, PIT-Features, chronologische Splits/Purging/Embargo und Trial-Ledger. **H7 readiness guard SUCCESS**.
- [ ] H8 On-chain erst nach Daten-/Timing-Preflight. **Zwei getrennte prospektive EOD-Zyklen jetzt grün:** Run #8 beobachtete 2026-09-30, Run #10 beobachtete 2026-10-01; BTC/ETH/XRP/ADA lieferten erneut Daten, SOL blieb `NO_ROW`. Wichtig: Zyklus 1 hatte ETH-Flow-`status-time` deutlich **nach** `AssetEODCompletionTime`, Zyklus 2 hatte BTC/ETH-Flow-Statuszeiten **vor** der jeweiligen Completion. Daher bleibt `AssetEODCompletionTime` als Einzelmetrik-Finalitätszeit unzulässig und historische Known-at-/Backfill-Performance bleibt gesperrt. `retrieved_at` ist dagegen als konservativer prospektiver Known-at-Upper-Bound über zwei Zyklen belegt; Missing/Revisions bleiben fail-closed/versioniert. Review: `research/v3/h8-known-at-two-cycle-review-20261002.json`. **Nächster Gate:** prospective-only H8-State-Capture/Association mit fixen Assets/Metriken preregistrieren; keine historische Rekonstruktion, kein Threshold-/Trade-Gate, Holdout geschlossen. **Prospective-only State-Contract now frozen:** fixed BTC/ETH/SOL/XRP/ADA × the same six metrics, `retrieved_at` as fail-closed known-at upper bound, no historical backfill/outcome join/threshold/model/scheduler. A single bounded public capture smoke is CI-gated. **State-Smoke Run #12 PASS:** 5/5 feste Assets verarbeitet, 4 `ROW_RETURNED`, SOL bleibt Missing; keine Outcomes/Thresholds/Trades und kein Auto-Schedule. Für Association ist jetzt erst zusätzliche prospective Datentiefe nötig; keine neue Dauer-Action/Mailquelle wird dafür automatisch aktiviert.
- [ ] H9 Maker-vs-Taker/Fill-Wahrscheinlichkeit erst vor späterer Live-Ausführung. **Öffentliche Book+Trade-Clock jetzt cloud + physisch PASS; Fill-Modell bleibt blockiert:** MINI-PC H9: 23 Trades / 23 sicher gegen ein bereits CRC-reconciliertes Book gejoint; BTC 9, ETH 1, SOL 13; 0 `no_book_yet`, 0 Trade-ID-Duplikate/out-of-order, 0 Book-Checksum-Fehler. **Nächster Gate:** Maker/Taker-Kosten versionieren, danach feste Deadline+Cleanup-Taker-Regel und explizite/testbare Queue-Annahme preregistrieren; vorher keine Fill-Wahrscheinlichkeit und kein Routing. **Public fees versioned 2026-10-02:** Kraken standard Spot Crypto reference Tier 1 = 0,40% maker / 0,80% taker, Tier 2 = 0,30% / 0,60%; BTC/EUR, ETH/EUR, SOL/EUR are not listed on the current maker-rebate eligible-pair page. Account-specific current fee tier remains UNVERIFIED and is not guessed; routing/fill modelling stays blocked until separate account-tier evidence plus deadline/cleanup/queue contracts.
- [ ] V3-Kandidat einfrieren und auf identischem Kandidatenstrom im Shadow/Paper direkt gegen V2R3 vergleichen. **Readiness-Snapshot aktiv:** `research/v3/shadow-candidate-readiness-20261002.json` trennt candidate-nahe Einzelgates (H1/H3/H5/H6) von optionalen/data-maturity/later-execution Zweigen. Noch kein Kandidat ausgewählt oder eingefroren. Nächster Schritt nach den bereits begonnenen H1/H3/H6-Evidence-Gates: höchstens **eine** geänderte Komponente materialisieren, frozen Minimum-/Kosten-/Promotion-Gate setzen und kleinsten Shadow-E2E-Smoke ausführen; optionale H2/H4/H7/H8/H9/H10/H11-Zweige blockieren dies nicht, sofern sie nicht ausgewählt werden.
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

- [x] **Teststrategie ist jetzt kanonisch triagiert:** `docs/test-strategy-runbook.md` definiert verbindlich Test-Value-Gate, Autonomy-first, No-Repeat, Smoke-before-Duration, physisches Nutzerbudget und phasenabhängige Pflichtgates. Offene Aufgaben bleiben ausschließlich hier im Master-Backlog; das Runbook ist keine zweite To-do-Liste. Grundsatz: nur entscheidungs-/sicherheitsrelevante Tests, autonome GitHub/Supabase/Public-API-Arbeit ohne Nutzerunterbrechung, physische Nutzeraktionen nur wenn technisch unvermeidbar und möglichst gebündelt. Bereits bestandene Tests werden ohne relevante Änderung/Incident/Freshness-Grund nicht wiederholt.

- [x] Jede Entscheidung mit Strategieversion + Fingerprints nachvollziehbar: im diagnostisch eingefrorenen Vorgänger enthielten 708/708 geprüfte Outcomes `strategy_revision`, `strategy_fingerprint_sha256` und `runtime_code_fingerprint_sha256`; dieselbe unveränderte Provenance-Pflicht bleibt für `PAPER-V2R3-CLEAN-20261001T0925Z` aktiv.
- [x] Last-known-good Konfiguration und schneller Rollback erhalten: `research/v2r3/clean-series-freeze-20261001.json` schützt die aktive V2R3-Referenz; `tools/paper-release-rollback-snapshot.py` erzeugt daraus fail-closed einen content-addressed Release-/Rollback-Snapshot mit Control-/Spec-/Runtime-/Scanner-Dateihashes. Whole-repo reset und Evidenz-/State-Rewind sind ausdrücklich verboten; nur geschützte Code-/Konfigurationsdateien dürfen auf den Snapshot-Stand zurückgeführt werden. V2R3 freeze guard ist selbsttestend und Snapshot-Smoke **SUCCESS**.
- [x] Smoke-before-Scale ist als verbindliche Change-Gate-Regel in `docs/change-gate-policy.md` festgelegt: plan-only/static → kleinster deterministischer Smoke → ggf. ein gebundener realer E2E-Fall → erst danach Skalierung/Sammlung. Ein bestandener Smoke autorisiert nur den nächsten dokumentierten Gate, niemals automatisch Strategie-Promotion, Kapital, private Rechte oder Orders.
- [x] Neue Quellen/Apps werden nur über den kanonischen Source-Intake-Gate aufgenommen: `docs/source-intake-policy.md` + `research/source-registry.json` verlangen Unique Value, Authority-Grenzen, Overlap-Strategie, Persistenz-/Retention-Rolle und Rechteumfang. `tools/validate-source-registry.py` + `source-intake-governance.yml` prüfen das automatisch; erster echter Lauf **Run #1 SUCCESS**.
- [x] Stille doppelte Datenspeicherung ist durch Source-/Storage-Governance explizit gesperrt: jede Quelle deklariert `persistence_mode`, `overlap_with`, `overlap_strategy` und `duplicate_raw_storage_allowed`; unbegründetes `duplicate_raw_storage_allowed=true` wird vom CI-Validator fail-closed abgelehnt. Retention/Provenance bleibt zusätzlich in `docs/storage-retention-policy.md` geregelt.
- [x] Periodische Storage-/Retention-Hygiene ist umgesetzt und kanonisch in `docs/storage-retention-policy.md` dokumentiert: MINI-PC Logs 14 Tage, Temp 2 Tage, State-Backups 14 Tage; GitHub `paper-market-tape-*` >36 h wird täglich entfernt, Scanner-Caches werden auf 12 Generationen begrenzt. Immutable Paper-/Trial-/Provenance-Evidenz wird ausdrücklich **nicht** automatisch gelöscht. GitHub Artifact-Cleanup ist real SUCCESS-verifiziert; lokale Cleanup-/Backup-Tasks sind Bestandteil der installierten MINI-PC-Baseline.
- [x] Offene GitHub Issues werden automatisch gegen den Master-Backlog abgeglichen: `tools/validate-backlog-issue-reconciliation.py` + `.github/workflows/backlog-issue-reconciliation.yml` laufen fail-closed bei Issue-Änderungen sowie täglich. Jeder offene Issue muss als `#Nummer` in `PROJECT_BACKLOG.md` verankert sein; PRs werden nicht als To-do-Issues gezählt. Erster echter Reconciliation-Lauf **Run #1 SUCCESS**; aktuell ist nur Issue #7 offen und korrekt verlinkt.
- [x] Dauerhaft projektrelevante „merk dir/später“-Beschlüsse werden nach der verbindlichen Governance in `docs/master-version-register.md` zeitnah an der passenden kanonischen GitHub-Stelle dokumentiert; `PROJECT_BACKLOG.md` bleibt die einzige Master-To-do-Liste, Fachdokumente tragen Details. Diese Regel gilt unabhängig davon, ob der Nutzer ausdrücklich „speichern“ sagt.

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
