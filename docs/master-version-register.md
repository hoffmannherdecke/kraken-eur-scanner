# MASTER VERSION REGISTER — Aktien & Krypto Chancen

Status: **KANONISCHE KOMPONENTEN-/VERSIONSÜBERSICHT**  
Stand: 2026-09-29  
Zweck: Single Source of Truth für Strategie, Paper, Infrastruktur, Datenpfade und Integrationen.

## Governance

- Kein relevanter Bestandteil wird nur über Chat-Erinnerung verwaltet.
- Offene GitHub Issues dürfen keine zweite To-do-Liste bilden: `backlog-issue-reconciliation.yml` prüft automatisch, dass jeder offene Issue im kanonischen `PROJECT_BACKLOG.md` referenziert ist.
- Storage-/Retention-Governance ist in `docs/storage-retention-policy.md` zentral festgelegt: kurzlebige Logs/Temp/diagnostische Artifacts/Caches werden begrenzt, immutable Paper-/Trial-/Provenance-Evidenz bleibt erhalten.
- Externe Quellen/Apps unterliegen `docs/source-intake-policy.md` + `research/source-registry.json`: kein neuer Pfad ohne dokumentierten Zusatznutzen, Authority-Grenze, Overlap-/Persistenzregel und minimal nötige Rechte; unbegründete doppelte Rohdatenspeicherung wird CI-seitig abgelehnt.
- Dauerhaft projektrelevante Informationen aus Gesprächen werden proaktiv kanonisch dokumentiert, auch wenn der Nutzer nicht ausdrücklich „merk dir das“ sagt. Dazu zählen insbesondere Entscheidungen, Anforderungen, neue Daten-/Informationsquellen, Hypothesen, Testregeln, offene Punkte, Fehlerursachen, Architektur-/Strategieänderungen und verbindliche Arbeitsprinzipien. Reine Zwischenüberlegungen oder verworfene Ideen werden nur dann dauerhaft aufgenommen, wenn sie für die Nachvollziehbarkeit relevant sind.
- **Analyse→Konsequenz ist verpflichtend:** Eine substanzielle gezielte Zwischen-/Abschlussanalyse gilt erst als abgeschlossen, wenn belastbare Lerneffekte dedupliziert, in zulässige Konsequenzen übersetzt, kanonisch geroutet und alle innerhalb der bestehenden Autonomiegrenzen sicheren Folgeschritte unmittelbar verarbeitet wurden. Detailregel: `docs/test-strategy-runbook.md`, Abschnitt 12. Keine stille Strategie-/Threshold-/Release-/Echtgeldänderung.
- **Gated-Change-Eskalation:** Wenn eine Analyse eine materielle, aber genehmigungspflichtige Strategie-/Release-Änderung rechtfertigt, darf sie nicht als passive Notiz liegen bleiben. Es ist automatisch ein kompakter `ENTSCHEIDUNG ERFORDERLICH`-Fall mit exakter Änderung, Evidenz, Nutzen, Risiko, Implementierungsdiff, Validierung, Rollback und Empfehlung an den Nutzer zu erzeugen. Nach Freigabe wird der sichere Release-/Testpfad autonom weitergeführt.
- **Dauerhafte Strategie-Linienvererbung:** Die Lern-/Übernahmeregel gilt nicht nur für V2R3→V2R4 oder V2/V2R4→V3, sondern für jede zukünftige Generation. Jede neue aktive Version muss alle materiellen Erkenntnisse ihrer Vorgänger explizit disponieren (`INHERIT_UNCHANGED`, `INHERIT_MODIFIED`, `REPLACE_WITH_VALIDATED_SUCCESSOR`, `DEFER_TO_LATER_GENERATION`, `MORE_TESTING_REQUIRED`, `REJECT_WITH_EVIDENCE`, `NO_SUCCESSOR_CHANGE`). Ungeklärte materielle Erkenntnisse blockieren den Release. Für jede neue Generation ist ein eigener bzw. fortgeschriebener predecessor→successor Migration-Ledger/Diff Pflicht; bestätigte Verbesserungen sollen sich über Versionen kumulieren und dürfen nicht an einem Versionswechsel verloren gehen.
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
- Material changes follow `docs/change-gate-policy.md`: static/plan-only → smallest deterministic smoke → bounded real E2E if needed → only then scale/collect.
- **Fast-Track-Iterationsregel (2026-10-03):** unabhängige V2R4-/V3-Vorbereitung wird parallel zu ausreifender eingefrorener Evidenz durchgeführt; neue Kandidaten erhalten ~24h Technik-, ~72h Produktivitäts- und ~7-Tage-Entscheidungsgates; bestandene unveränderte Tests werden nicht wiederholt; klar unproduktive Strategieäste werden früh beendet. Keine Mid-Run-Strategieänderung und keine Abkürzung von Freeze-, Holdout-, Release- oder Live-Sicherheitsgates. Kanonische Details: `docs/test-strategy-runbook.md` Abschnitt 11, `docs/strategy-version-map.md` Fast-Track-Beschluss 2026-10-03 und `PROJECT_BACKLOG.md` Fast-Track execution block.
- Test-Triage / Autonomy / No-Repeat is governed by `docs/test-strategy-runbook.md`: only decision-/safety-relevant tests are pursued; previous PASS evidence is reused absent relevant change/incident/freshness expiry; autonomous GitHub/Supabase/public-API work is preferred, and physical user actions are reserved for proofs that truly require the MINI-PC/account/hardware.
- Last-known-good/Rollback wird content-addressed festgehalten: `tools/paper-release-rollback-snapshot.py` validiert den aktiven Freeze und schreibt exakte Control-/Spec-/Runtime-/Scanner-Hashes. Whole-repo reset oder Evidenz-/State-Rewind ist ausdrücklich verboten; der Snapshot gilt nur für die geschützten Code-/Konfigurationspfade.
- Strategie- und Infrastrukturversionen werden getrennt geführt und miteinander verknüpft.
- V3 gilt erst dann als vollständig integriert, wenn jeder relevante V2/V2R4-Baustein einen Migrationsstatus besitzt.

## Strategie / Paper

| Komponente | Version / ID | Status | Rolle / nächste Aktion |
|---|---|---|---|
| Strategie | `V2R3-2026-09-28` | ACTIVE / PAPER / FROZEN | Aktive Vergleichsbasis; Regeln während Serie nicht ändern |
| Paper-Serie | `PAPER-V2R3-CLEAN-20261001T0925Z` | ACTIVE / CLEAN / FROZEN / PERSISTENCE E2E VERIFIED | Aktuelle homogene V2R3-Serie nach Runtime-only Persistenzrepair; erster realer 3-Kandidaten-Cycle im selben Lauf committed, Repeat-Guard danach 0 Reselections/0 No-op-Follow-up-Changes; Process-Health Provenance sauber. Strategie `V2R3-2026-09-28` unverändert. Fail-closed Freeze-Guard prüft Series/Test/Strategy, Strategy-/Runtime-Fingerprints, Scanner-Paket, 10-Minuten-Takt/Scanner-Settings und seit Full-System-Audit 2026-10-02 zusätzlich die behaviorally relevanten `paper-evaluator.yml`-Runtime-Semantiken; Post-Fix Guard SUCCESS. Audit: `docs/full-system-audit-20261002.md`. |
| Strategie-Hypothesenkarte | `V2R3-ADJ-HYP-20261002-V1` | CAPTURED / HYPOTHESIS ONLY / NOT ACTIVE | Versionierter Clean-Series-Zwischenstand für nächste Strategieüberarbeitung: WAIT-Lifecycle, Continuation/Second-Leg, Resistance/Breakout-Routing, Extended-Pullback, Cost-Edge-Routing und Kraken-Tradability-Autorität. Human: `research/v2r3/strategy-adjustment-hypotheses-v1.md`; Machine: `research/v2r3/strategy-adjustment-hypotheses-v1.json`. V1 nicht überschreiben; finale Disposition erst am V2R3-Release-Review. |
| Paper-Serie predecessor | `PAPER-V2R3-FINAL-20260928T1752Z` | DIAGNOSTIC_COMPROMISED / FROZEN | 708 Candidate-Outcomes bleiben für Fehler-/Missed-Move-/Timinganalyse nutzbar, aber nicht als saubere prospektive Abschlussserie; Persistenzbug am 2026-10-01 nachgewiesen und repariert. |
| Strategie | V2R4 | PREPARED / NOT ACTIVE / PHYSICAL MINI-PC E2E GREEN | **Draft-PR #9** refreshed candidate; old PR #8 superseded. Original V2R4 delta remains and the readiness review additionally prepared an inactive bounded 24/7 WAIT-plan runtime with Kraken as condition truth and Altrady as optional wakeup. V2R4 PR validation through **Run #17 SUCCESS**; refreshed trigger-to-fresh-recheck E2E Run #2 SUCCESS; Windows-shaped WAIT-runtime smoke #1 SUCCESS (1 wakeup/1 Kraken match/1 fresh recheck/0 duplicate rechecks); real-Altrady physical release harness prepared and CI-green in MINI-PC tools smoke #111. Fail-closed `public.v2r4_activation_readiness` keeps automatic activation disabled and now also blocks on V2R3 integrity. Current blocker: V2R3 clean-series completion/review plus explicit sizing/release decision |
| Strategie | V3 | ACTIVE RESEARCH / NOT ACTIVE TRADING | Integrierter Nachfolger; Issue #7 + `docs/v3-research-framework.md` |
| V3 H10 Smart-Money | `V3-H10-COHORT-001 / V3-H10-CAPTURE-001` | PROSPECTIVE SHADOW ACTIVE / NO STRATEGY COUPLING | Hyperliquid public read-only; frozen 20 Primary + 6 Controls; first capture 26/26 / 0 errors / HEALTHY. Coarse GitHub bootstrap :17/:47 → Supabase compact state/fills. First analysis gate frozen at 72h + sample/health minima; no copy-trading/orders. |

### Prospective V2R3 review controls — 2026-10-01

- Active clean series is protected by `research/v2r3/clean-series-freeze-20261001.json` + CI freeze guard Run #1 SUCCESS.
- Initial evaluator timing is now separated from one-shot WAIT-TTL lateness; `public.v2r3_revalidation_timing_summary` measures the scheduler/runtime delay beyond requested TTL without changing V2R3.
- `public.v2r3_release_review_snapshot` is the fail-closed single-row evidence pack for the eventual final review; `final_review_allowed=false` until completion gate + clean integrity pass.
- `public.v3_timing_evidence_snapshot` is the read-only V3 timing intake: V2R3 initial/revalidation timing + V2R4 shadow maturity + realtime path comparison, with path ranking and automatic rule changes fail-closed.
- `tools/render-v2r3-final-review.py` is the fail-closed report renderer for that snapshot: blocked before maturity, evidence-only after maturity; renderer guard Run #1 SUCCESS.
- `public.v2r4_activation_readiness` additionally blocks on `BLOCKED_V2R3_INTEGRITY` if clean-series integrity drifts; automatic activation stays permanently false.

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
| Mini-PC Hardware | Dell OptiPlex 5060 Micro, i5-8500T, 16 GB, 256 GB SSD | CORE COMMISSIONING COMPLETE / OPTIONAL HARDENING DEFERRED | Windows/LAN/RDP/WireGuard/Git/Python, power/restart/Internet recovery, watchdog/supervisor, Kraken realtime, Altrady transport, backup/restore, D: NTFS and post-reboot 11-task recovery verified; Defender active; no extra AV/native-app/weekly-reboot requirement adopted. RDP firewall scope was audited and rollback snapshot exported; broad Windows RDP Any/Any scope is documented as optional hardening, not a commissioning blocker, because approved external administration is VPN-first and already physically verified. |
| Betriebssystem | Windows 11 Pro, Build 26200 | VERIFIED | lokaler Sammeltest / next-gate |
| Netzwerk lokal | LAN über FRITZ!Box 7590 AX | ACTIVE / VERIFIED | lokaler Kraken HTTPS/WebSocket-Smoke erfolgreich |
| Interner Fernzugriff | Windows RDP im LAN | ACTIVE | MINI-PC während Einrichtung erfolgreich per RDP administriert |
| Externer Fernzugriff | FRITZ!Box-VPN/WireGuard → internes RDP | ACTIVE / EXTERNAL E2E VERIFIED | echter Außentest 2026-10-01 über Mobilfunk/iPhone-Hotspot bestanden; WireGuard aktiv, RDP auf MINI-PC `192.168.178.179` ohne Einschränkungen; kein direktes RDP-Portforwarding |
| Stromausfall-Recovery | Dell BIOS AC Recovery = Power On | ACTIVE / VERIFIED | echter Stromverlust-/Umplatzierungs-Test bestanden; automatischer Boot ohne Tastendruck, RDP danach wieder erreichbar |
| Watchdog/Recovery | lokaler Health-Watchdog + Runtime-Supervisor + unabhängiger GitHub-Cloud-Deadman + Cloud-Paper-Sentinel | ACTIVE / SELF-HEAL VERIFIED / CLOUD E2E VERIFIED / LOW-NOISE ROUTING VERIFIED 2026-10-04 | Lokaler Watchdog prüft Prozesse plus Effektivität/Freshness von Kraken Canary, 501er EUR-Universe, V2R4 WS-Shadow, Outcome-Tracker, Shadow-Cloud-Sync und Altrady sowie Disk/Backup/Repo/Netzwerk/Status-Sync. Runtime-Supervisor läuft alle 2 Min + Startup mit 10-Minuten-Backoff und darf ausschließlich technische Read-only-Runtimes neu starten. Der Cloud-Paper-Sentinel prüft jetzt alle 5 Min die V2R3-Paper-Kette; Scanner-Stale wird ab 20 Min, Paper-Runtime-Stale ab 25 Min technisch selbstgeheilt. Reparierbare CRITICAL-Zustände erhalten 15 Min Self-Heal-Grace und bleiben bei rechtzeitiger Erholung push-still; nur persistierende Fälle werden mit @Hoffis eskaliert, identische Dauerfehler frühestens nach 6 h erneut. Nicht reparierbare Integritäts-/Safety-CRITICALs bleiben sofortig. Alertzustand liegt persistent in Supabase; Recovery-Push E2E am 2026-10-04 verifiziert. Keine Strategie-/Threshold-/Order-Aktion. |
| Backup/Restore | lokales State-Backup + Restore-Smoke | ACTIVE / VERIFIED | 04:00 daily, 14-day retention, no Secrets/Logs/Repo; immediate seed + restore smoke passed locally; watchdog warns only after 7 days without backup |
| Externer Datenträger | `D:` / `Mistral_450` | ACTIVE / NTFS / VERIFIED | FAT32-Fehler repariert, Bestandsdaten erhalten, in-place nach NTFS konvertiert; `PASS_NTFS_VERIFIED`, 53.920 Bestandsdateien geprüft, 0 fehlend, 0 Größenänderungen, 0 Nutzerdaten-Zugriffsfehler, RW/Delete-Smoke PASS; keine Formatierung. Freigegeben für Bulk/Archiv/Capture/sekundäres Backup; Runtime/Secrets/primärer State bleiben auf C:. |
| Kraken local realtime data | Public WebSocket v2 book + trades via isolated venv | ACTIVE / SMOKE VERIFIED | 45s local smoke: 1544 verified book events, 103 trades, 0 gaps, 0 subscription errors; public/read-only only |
| Kraken runtime canary | continuous BTC/EUR public WebSocket heartbeat | ACTIVE / LOCAL+CI VERIFIED | SYSTEM startup task running; heartbeat HEALTHY; watchdog check HEALTHY; 0 gaps / 0 subscription errors at activation; transport-only, no account/order/strategy action |
| V2R4 local recheck gate | deterministic trigger → fresh paper evaluator recheck | PHYSICAL MINI-PC + WINDOWS-CI E2E VERIFIED | physical MINI-PC gate passed with fresh Kraken trigger, real OpenAI paper evaluator and paper-only safety; observed local trigger→recheck start 0.228 s, evaluator runtime 12.348 s; no order API/real money |
| Altrady | zusätzlicher Echtzeit-Trigger | REAL ALERT E2E VERIFIED / TRANSPORT ACTIVE | Supabase Edge Function `altrady-trigger-relay` ACTIVE; gemeinsames Secret gesetzt; `CryptoMiniPC-AltradyTrigger` läuft; synthetic relay→MINI-PC→ack smoke PASS and real one-shot Price Alert verified. Real event 2026-09-30 22:49:22 UTC → relay 22:49:24.244 UTC → MINI-PC ack 22:49:27.541 UTC; about 2.244 s event→relay, 3.297 s relay→ack, 5.541 s event→ack. Strategy action remains NONE_TRANSPORT_ONLY; explicit Fresh-Recheck coupling still separate; never sole trigger/SPOF. |
| Kraken realtime | Public REST/WebSocket lokal | BROAD FEED ACTIVE / LOCAL VERIFIED | primäre Marktwahrheit; BTC/EUR Canary bleibt unabhängig aktiv; `CryptoMiniPC-KrakenUniverse` überwacht im Aktivierungsproof 500/500 online EUR-Paare (100% Coverage), 0 Subscription-Errors; REST `AssetPairs` = Universe-Gate, WS-v2-Ticker = Event-Feed; Latest-Snapshot/Heartbeat only; public data / no account / no orders / no strategy action |
| V2R4 WS shadow | local Kraken WS snapshot → observation-only discovery | ACTIVE / PHYSICAL SMOKE VERIFIED | `CryptoMiniPC-V2R4WSShadow` active; 500/500 source universe; physical smoke 13 fresh cycles, 0 stale, source age avg ~0.706 s / max ~2.175 s; pinned prep commit `ab78c9a`; no evaluator/account/order/real-money path |
| V2R4 shadow outcomes | prospective post-detection evidence | ACTIVE / LOCAL VERIFIED | `CryptoMiniPC-V2R4ShadowOutcomes` HEALTHY; only events after tracker start enrolled; 5m/15m/30m/1h/3h/6h + MFE/MAE; 18 earlier shadow events deliberately excluded from outcome backfill |
| V2R4 shadow cloud archive | Supabase `v2r4_shadow_evidence` + authenticated Edge relay | ACTIVE / E2E VERIFIED | `CryptoMiniPC-V2R4ShadowCloudSync` HEALTHY; first real upload 23 records/1 batch; 23 rows independently verified; pending=0 after install; server-only RLS/no client policy; fail-soft/idempotent |
| MINI-PC remote status | local watchdog → authenticated Edge relay → Supabase `minipc_status_current` | ACTIVE / E2E VERIFIED | `CryptoMiniPC-StatusSync` HEALTHY; first real row verified; first reported health WARNING correctly exposed stale WS-shadow + outcome-tracker heartbeats; cloud deadman external to MINI-PC is active |
| MINI-PC daily status | GitHub hourly gate → 10:00 Europe/Berlin → Slack + Supabase history | ACTIVE / FIRST REGULAR RUN VERIFIED | Scheduled Run #27 SUCCESS on 2026-10-02; `public.minipc_daily_status` dry_run=false, HEALTHY/OK, Kraken 501/501, Supervisor HEALTHY, Issues none. OK remains silent; problem states use real `@Hoffis` push. |
| MINI-PC health taxonomy | local watchdog operational state | ACTIVE / PHYSICALLY VERIFIED | `OK`, `WAITING_NO_DATA`, `FEED_STALE`, `API_DISCONNECTED`, `BACKLOG_STUCK`, `DEGRADED`, `STOPPED`; physical effectiveness smoke = HEALTHY / OK / no reasons |
| MINI-PC runtime supervisor | bounded Task Scheduler liveness recovery | ACTIVE / SELF-HEAL VERIFIED | 2-min cadence + startup; 10-min per-task restart backoff; controlled stop of archive-only support task recovered automatically; heartbeat advanced; local watchdog HEALTHY; no strategy/evaluator/order path |
| MINI-PC GitHub cadence recovery | lokaler 5-Minuten-Liveness-Guard → bestehendes `scan.yml` workflow_dispatch | **ACTIVE / LOCAL E2E VERIFIED 2026-10-04** | Reagiert nur recovery-only auf fehlenden/verzögerten Scanner (>20 Min) oder fehlgeschlagenen Run nach Grace; 15-Min-Dispatch-Backoff, aktiver Run blockiert Doppelstart. Fine-grained PAT nur für dieses Repo + Actions Read/write, lokal unter `Trading\\Secrets` mit restriktiver ACL; Secret nie geloggt. No-op-Auth-Smoke Run `37184784133` SUCCESS; erster realer Recovery-Dispatch startete Scanner Run `37184786088`, der SUCCESS abschloss und regulär den Paper-Evaluator auslöste. Guard-Heartbeat HEALTHY; lokaler Watchdog nach Recovery `issues: []` = HEALTHY/OK. GitHub-Cron bleibt unabhängiger Cloud-Fallback. Kein Strategie-/Evaluator-direkt-/Account-/Orderpfad. |
| GitHub Cloudpfad | bestehend | ACTIVE | unabhängiger Fallback bleibt erhalten |
| Supabase archive | `paper_series` / `paper_candidate_outcomes` / `paper_trade_results` | ACTIVE / VERIFIED / FAIL-SOFT | push/manual + opportunistic workflow_run + unabhängige Reconciliation :07/:37; zuletzt 578 V2R3-Outcomes archiviert, 0 Trades |
| Historical/backtest research layer | Kraken OHLCVT + targeted Time & Sales + supplementary Binance derivatives context, local research-only | **H1/H2 PERFORMANCE BRANCH CLOSED / HOLDOUT SEALED / T&S+BINANCE METHOD PREP GREEN** | `docs/historical-backtest-preflight.md`; H1 insufficient, H2 failed preregistered development gate; 2026H1 holdout remains unopened. Targeted public-trades methodology is now CI-green (**Historical data preflight Run #57 SUCCESS**) with PIT parser, identifiability limits, storage-benefit gate and plan-only MINI-PC wrapper. Full ~26 GB Trades archive remains **NOT AUTHORIZED**; no performance selection or active V2R3/V2R4 mutation. |
| Slack Push | GitHub owner-approved action relay → Slack webhook → real `@Hoffis` mention → iPhone | ACTIVE / E2E VERIFIED | 2026-10-01 relay workflow SUCCESS, Slack HTTP 200/ok, physical iPhone push received; `#krypto-signale` mobile setting = Nur Erwähnungen; raw candidates remain silent |
| ChatGPT Desktop/Work + Codex local | offizielle Windows-Desktop-App auf MINI-PC; Work `Auf deinem Computer`; Codex-Projekt `kraken-eur-scanner` | **ACTIVE / LOCAL AUTONOMY VERIFIED / MINIMAL WORK ANALYSIS ARMED 2026-10-03** | Work/Codex-Local-Smokes **PASS**; `Für mich genehmigen` aktiv; Codex-Repo/Python 3.13.15 über `.venv` verifiziert. Einziger wiederkehrender Work-Pfad ist `Krypto Paper – gezielte Analyse` (ID `6ab431f212488191b072c400bc3cdb86`), ab 04.10.2026 10:15 Europe/Berlin täglich. Jeder Lauf startet gate-only und bleibt bei geschlossenem Gate vollständig still. Tiefe Analyse nur bei >=3 neuen V2R3-24h-reifen Fällen, Serienabschluss/`final_review_allowed`, echtem UNKNOWN/Blocker oder dokumentiertem V2R4-/V3-Gate; Ack/Dedupe über `research/work-analysis-state.json`. Scanner/Watchdog/Realtime/Paper/Follow-up/Slack/Routinechecks bleiben außerhalb Work. `Trading\\Secrets`/Credentials, Echtgeld-/Kontoaktionen und unnötige Admin-Aktionen bleiben ausgeschlossen. |
| OpenAI API / Work quota guard | native API prepaid auto-reload + optional local GET-only cost watcher + separate Work/Codex reserve policy | **PREPARED / ACCOUNT-UI GATES PENDING / LOCAL COST WATCH NOT INSTALLED** | API exact prepaid balance is not exposed by a documented machine endpoint; native auto-reload is authoritative. Optional `tools/minipc-openai-cost-watch.py` reads only `/v1/organization/costs` with 0 model calls and requires a separate local Admin API key; Work/Codex exact weekly remaining percentage has no documented machine endpoint and is not scraped. Canonical detail: `docs/ai-api-cost-guardrails.md`, `research/openai-quota-monitoring-decision-20261003.json`. |

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
- `docs/test-strategy-runbook.md`
- Draft-PR #9 — refreshed V2R4 Fast WAIT Triggers / Mini-PC on current `main` (PR #8 superseded)
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

Canonical ledger: `research/v3-migration-ledger.json` — guarded by `tools/validate-v3-migration-ledger.py` + `v3-migration-ledger-guard.yml`; initial self-test Run #1 SUCCESS. Strategy mechanics remain `OPEN_RESEARCH` until their named evidence gates mature.

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


### V2R3→V2R4 release diff / sizing blocker — 2026-10-01

Canonical behavior matrix: `docs/v2r4-v2r3-release-diff.md`.

The readiness review proved that V2R4 is not literally a timing-only delta:
- deterministic WAIT monitoring, fresh recheck and broad pre-candidate visibility are the core intended timing/discovery changes;
- live Kraken `AssetPairs` replaces legacy static pair blocking;
- the proposal also changes paper sizing from V2R3's 50+50 EUR to a proposed 75+75 EUR default and larger adaptive tiers;
- the proposed spec itself says the adaptive sizing contract is required before a full V2R4 series, while the mapper is still not wired.

No silent sizing choice is permitted. The later activation review must explicitly version either a timing-isolation series that retains V2R3 sizing or a combined timing+sizing series after the adaptive mapper is separately implemented and tested.


### V2R4 paper release checklist

The bounded release/rollback procedure is now canonical in `docs/v2r4-paper-activation-checklist.md`. It preserves a fail-closed manual release boundary, requires final V2R3 review first, requires an explicit sizing decision, and forbids reusing/rewriting the closed V2R3 series as V2R4.
