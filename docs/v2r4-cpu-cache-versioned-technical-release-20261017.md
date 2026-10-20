# Issue #353 — eigenständiger versionierter V2R4-CPU-Release

Status **OFFLINE-VERTRAG IN ENTWICKLUNG / PRODUKTIVER WECHSEL GESPERRT** (17.10.2026). Der Nutzer hat die eigenständige technische Entwicklung einschließlich Tests freigegeben, **nicht** die Ausführung eines ungeprüften Live-Cutovers.

## Kanonischer physischer Ausgangszustand

- Aktive Paper-Serie `PAPER-V2R4-20261009T110135Z`, Release `d8b35a8ec2e6f392f219b1c36cad95f3ad629b64`.
- Original-Bundle-Fingerprint `604d5d460f17c4548b2d69db8ceb2f5368e702a6d51860ce8916e2e7fbba5b30`; Strategie `55c15f6c0735e524409594ece173ab30e4d84eecafefa18b57f8dc9c48cca32c`, Paper-only, 50+50 EUR, kein Echtgeld.
- Originale physische Candidates/Lifecycle-Datei `v2r4-paper-local-runtime.py` SHA256 `8371CAB2D7D18F9651E604DBAB88768F77B2DFF5EB88565122858F6428DC50D0`; getrennter PR326-WAIT-Runtime-Originalhash `C84533E1042C9D89D6F6EDC31DD22DE6DD3AB3B7AAE2B202EF344495A72BA6A2`.
- PR360 Quellstand `c8f37da865314ac91d36c786b66d107aad4a28d1`, fünf Dateien aus PR362 auf Mini-PC isoliert/inaktiv staged. Quell-/Task-/Manifest-Read-only-Gate PR369 **physisch PASS**.
- Genau **eine** verifizierte Zwei-Datei-Vorsicherung `D:\Krypto-Sicherungen\ISSUE353-CPU-VORHER-20261017-091646-93265fff`; Prüfsummenprüfung PR374 **physisch PASS**. Backup erhalten, nicht neu anlegen oder überschreiben.
- Windows Tasks: Candidates = `--mode candidates`, Lifecycle = `--mode lifecycle`, jeweils `IgnoreNew`. Ein anderer Python-Prozessbaum darf nicht fälschlich als Doppel-Candidates bezeichnet werden. PR326 WAIT eigener isolierter Launcher/Watcher.
- Cloud-Gesundheit und Paper-Wirtschaftlichkeit sind **keine** Belege für CPU-Entlastung oder physische Stop-/Wiederanlaufsicherheit.

## Verbindliches Einbau- und Inbetriebnahmeprotokoll i7-8700T – Pflichtnachlauf V3 PR #419 (19.10.2026)

**Aktueller Stand: CPU-Tausch nicht physisch bestätigt; neuer V3-STOP-Prüfcode in GitHub fertig, aber auf dem Original-Mini-PC noch nicht übernommen/abgenommen.** Dieser Punkt ist ein vom Nutzer ausdrücklich verlangter Teil des vorhandenen gemeinsamen i7-8700T-Wartungsablaufs (nicht nur eine Chat-Notiz). Kanonische Wartungsentscheidung: [Issue #353, Pflicht-Checkpoint](https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/353#issuecomment-6264804080); fachlicher Single-Writer-/No-Rearm-Release-Owner: [Issue #99](https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/99). Der CPU-Umbau ersetzt kein V3-Release-Gate.

- [ ] **Vorbereitungsprüfung vor dem Herunterfahren:** aktive V2R4-Serie und echte Task-/Supervisor-/Lifecycle-/PR326-WAIT-/PR332-CloudSync-Health, aktuelle BIOS-Version/Kompatibilität und BitLocker/Recovery-Key, Windows-Update-/Rebootstatus und die bis 31.10. pausierten Updates original am Mini-PC prüfen. Noch keinen Neustart anstoßen; CPU- oder Windows-Neustart nur kontrolliert, kein unbemerkter V3-Cutover.
- [ ] **PFLICHT VOR CPU-AUSBAU / REVISIONS- UND WARTUNGSARBEITEN — GitHub-Mini-PC-Runner vollständig in Safe-Pause versetzen (separates Stop-Gate):** Auf dem Original-Mini-PC vor dem geplanten Shutdown die **exakte** Windows-Aufgabe `CryptoSupport - Bounded Runner Window` identifizieren; ein gerade laufendes Zeitfenster und zugehörige `Runner.Worker.exe`-Jobs **kontrolliert auslaufen lassen**. Danach **diese Aufgabe ausdrücklich deaktivieren** (nicht nur den Runner-Dienst); TaskScheduler-Readback `Enabled=False` und `State=Disabled` verlangen. Anschließend den ursprünglichen Dienst `actions.runner.hoffmannherdecke-kraken-readonly-bridge.MINI-PC-CryptoSupport` direkt am Host unabhängig mit `Win32_Service` prüfen: **`State=Stopped`, `StartMode=Disabled`**, keine noch laufenden zugehörigen Runner-Worker. **Nur bei sämtlichen positiven Original-Host-Readbacks** Quittung `CPU_MAINTENANCE_RUNNER_SAFE_PAUSE=PASS` mit Datum/Uhrzeit und tatsächlichem Task-/Dienst-/Workerzustand protokollieren und Shutdown/CPU-Tausch freigeben. Bei aktivem Fenster, fehlender Abschaltbestätigung, laufendem Worker oder unklarem Readback: `BLOCKED`, **kein CPU-/Update-Neustart**, keine gewaltsame Beendigung/Blind-Reaktivierung; Ursache zuerst kontrolliert beseitigen. Der am **19.10. um 15:20:26 MESZ** bereits belegte natürliche Fensterabschluss `Ready / LastTaskResult=0 / Stopped / Disabled` ist **nur ein historischer Betriebsnachweis**, keine aktuell gültige Wartungssperre: Er beweist insbesondere **nicht** `Enabled=False`. Owner [Issue #353](https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/353), vorhandener [Runner-Runbook](https://github.com/hoffmannherdecke/kraken-eur-scanner/blob/main/docs/minipc-runner-bounded-windows-v1.md).

- [ ] **CPU + Windows:** Dell OptiPlex 5060 Micro von i5-8500T auf i7-8700T mit Wärmeleitpaste kontrolliert umbauen. BIOS-/CPU-/32-GB-RAM-Erkennung, Kühlung/Temperaturen, Windows-Start, LAN/Dienststatus und Systemstabilität belegen. Frühere Windows-11-26H2-/USB-Treiber-Update-Warteschlange und die bis 31.10. gesetzte Pause **erst danach** überprüfen, erforderliche Updates/zusätzliche Reboots abgestimmt durchführen und am Ende regulären Update-Schutz statt dauerhafter Zwangspause bestätigen. Hardware- und Softwarefehler getrennt protokollieren.
- [ ] **Produktions-Rückkehr:** bestehende V2R4-Candidates+WAIT, Lifecycle, CloudSync und Supervisor müssen nach CPU/OS-Wartung wieder original und in Cloud eindeutig `HEALTHY/OK` sein, mit weiterhin genau einer tatsächlich aktiven V2R4-Paper-Serie. Die vorher deaktivierte Aufgabe `CryptoSupport - Bounded Runner Window` **bleibt bis zur getrennten, bewussten Wiedereinschaltfreigabe `Disabled`**; erst nach aktuellem Sicherheits-/Prejob-/SHA-/Dienst-Endzustands-Check darf sie gezielt wieder aktiviert und `POST_MAINTENANCE_RUNNER_REARM=PASS` eigenständig belegt werden. Kein automatisches Wieder-Einschalten durch den CPU-Neustart. CPU-Umrüstung aktiviert weder V3 noch ein Trading-/Modellbudget.
- [ ] **VERPFLICHTENDER V3-Prüfskript-Nachlauf A – PR419 auf dem Host:** Das bereits geprüfte [PR #419](https://github.com/hoffmannherdecke/kraken-eur-scanner/pull/419) (Merge `143420f219e2fc0865f12356ee9cccd9b88b7863`) auf dem Mini-PC **isoliert/inaktiv** als echtes Original-Admin-Source-Staging übernehmen und das vorhandene `tools/minipc-v3-originalhost-norearm-stop-only.ps1` byte-/versionsgenau per **Git-Blob `a0e4f1b96fefbc5e9ff8d12a38e2403c67608248`** gegen die tatsächlich staged Datei prüfen. Die früher am Originalhost verwendete alte Git-Blob-Version `8941634e7fcb99e4d44d85df611db512914ee4bc` **nicht** als PR419 deklarieren. Keine aktive V2R4- oder V3-Runtime-/Task-/Backup-Datei stillschweigend überschreiben. **Read-only** Parse/Hash/Standard-PREVIEW mit Originalhost-Zeit, Pfad, Quelle und eindeutigem ACK nach Issue #99; `PR419_HOST_STAGE_SHA_PREVIEW=PASS` ausschließlich bei echter physischer Bestätigung, nicht aufgrund GitHub-CI.
- [ ] **VERPFLICHTENDER V3-Prüfskript-Nachlauf B – echte No-Rearm-Abnahme (eigenständiges freizugebendes Risiko-Gate):** Im selben Wartungsfenster **nur wenn** CPU/Windows/V2R4 bereits stabil, Cloud-Autorität `OLD-V2R4-ONLY-AND-V3-CAS-ABSENT` aktuell unabhängig belegt und gepinnte Stop-/Restore-Skripte plus Operator/Recovery vorbereitet sind: beaufsichtigten STOP nur Candidates+WAIT, keine alten Lifecycle-/CloudSync-Stops, **zwei neue unterschiedliche vollständig gültige** `QUIESCED`-Supervisor+CloudSync-ACKs (neu: 360s Zeitbudget, unveränderte Sicherheitsprädikate), kein automatisches Re-Arm; danach getrennte und unabhängig Cloud-geprüfte Wiederherstellung auf V2R4, frische Heartbeats und Produktions-`HEALTHY`. Bei Marker-/Quelle-/CAS-Unklarheit oder Chat-Abbruch **fail closed**, keine blinde Task-Reaktivierung. Kein automatischer Test allein wegen des CPU-Tauschs.
- [ ] **Getrennte Abschluss-Quittungen:** `CPU_HARDWARE_BOOT`, `POST_CPU_WINDOWS_UPDATE_REVIEW`, `PR419_HOST_STAGE_SHA_PREVIEW` und `PR419_PHYSICAL_TWO_CYCLE_STOP_RESTORE_E2E` jeweils als `PASS/OPEN` mit originalem Zeitpunkt, Host-/Cloud-Evidenz und Owner dokumentieren. **Wenn ein echter V3-STOP-Test beim CPU-Termin unsicher ist, dann `OPEN_DEFERRED_TO_NEXT_CONTROLLED_WINDOW` mit Owner Issue #99 und Wiedervorlage im bestehenden Issue #353; niemals stillschweigend als PASS oder vergessen.** Der Hardware-Umbau kann separat abgeschlossen werden, das ursprüngliche V3-Single-Writer-Sechsgate bleibt bis zur echten Originalhost-Abnahme offen.

## Dienstag/Mittwoch 20.–21.10.: gebündelte V3-Vorarbeit statt weiterer punktueller Freigabe-Härterei

**Einmalige strategische Priorisierung für den möglichen Wartungstermin Donnerstag,
22.10.2026.** Die tatsächliche Hardware-Lieferung und Terminzusage stehen
aus. Deshalb heute/morgen ausschließlich **SOURCE / INACTIVE / READ-ONLY**,
keine Änderung an aktivem V2R4, Task, Windows, Supabase-Migration oder
Modellbudget. Reifegrad statt PR-Anzahl zählt. Nicht auf wirtschaftlich
profitable BUYs oder 72h-Paper-Maturity *vor* dem technischen
`EXPERIMENTAL_PAPER_ONLY`-Start warten.

**Vor der Wartung abschließbare Arbeit (ohne neuen Manager/zweite Release-Stufe):**

1. Bestehende Originalhost-Windows-One-Shot-Quellen #464–#474,
   Altserien-CloudSync/Edge-Relay (bereits deployed, nicht erneut
   installieren), sechs technischen Proof-Gates und V3 Full-Model/P4-
   /WAIT/No-BUY/1m/6h/24h/72h-Kette in **einem** Release-Snapshot
   konsolidieren. Alle Open-Punkte gehören zum bisherigen Fach-Owner #99.
2. Den vorhandenen `assess_v3_experimental_source_inventory` im
   originalen `tools/v3_experimental_paper_technical_gate.py` als
   Quell-Einstieg nutzen. Die reine
   `assess_v3_native_source_import_closure`-Ergänzung durchläuft
   dazu statisch die lokal importierten Python-Dateien einschließlich
   des nativen Launchers, protokolliert deren unveränderliche SHA256,
   externe Import-Namensräume und dynamische Importstellen. Vor
   Wartungsfenster und **nach finalem Commit-Freeze** genau denselben
   Snapshot aus dem geprüften protected-main-Checkout erzeugen.
   `static_local_import_closure_complete` ist *keine* Erklärung,
   dass alle Laufzeit-/Paketversionen/geladene Bytes physisch stimmen;
   dynamische Imports/externes Paket müssen tatsächlich separat
   im vorhandenen Wartungs-Smoke und Windows-PID-Quellen-ACK geprüft werden.
3. Der eigentliche Produktionsstart bleibt bewusst eine
   **eigene, später freizugebende** Originalhost-Operation:
   aktuelle Windows-Task Action und SYSTEM-/PID-/OS-Startzeit,
   **geladene** Source, native Singleton, No-Rearm-V2R4-Fence,
   V2R4-Lifecycle-/CloudSync-Alt-Nachpflege, sechs echte
   E2E-Original-Host-/Cloud-/GitHub-/Work-Belege, CAS und aktiver
   Serien-Readback. **Kein erneuter 28h-CANARY, keine Wiederholung
   abgeschlossener historischer Positivbelege**, sondern nur
   fehlende aktuelle und original erforderliche Nachweise.
4. **Restarbeiten vor Freigabe objektiv zusammenhalten:** Noch kein
   produktiv ausführbarer freigegebener Windows-V3-Phasen-CLI-/Task,
   kein physisch authentifizierter separater Release-Owner und kein
   V3-CAS-Deployment. Diese Teile dürfen nicht über nominale Hashes,
   positive CI- oder synthetische `true`-Belege als fertig gelten.
   Den nach Wartung erforderlichen **einen** Stop/CAS/Start-
   Operatorpfad erst anhand dieser Originalnachweise und ausdrücklicher
   letzter Nutzerfreigabe in Betrieb nehmen.
5. Donnerstag: zuerst Wartung nach Ausführungsreihenfolge und
   V2R4-Recovery. **Danach** die bereits vorbereitete
   V3-Releasequelle/echten E2E-Proofs/Fence/CAS/Phasenstart kontrolliert
   abnehmen. Ist ein kritischer Originalbeleg nicht verfügbar:
   nur den konkreten fehlenden Gate-Owner nacharbeiten, V2R4 bleibt
   aktiv. Kein Terminversprechen für Go-live ohne die Fakten.

**Nicht vorziehen:** optionale H1–H11-Forschungsalternativen,
zusätzliche Quellen- oder KI-Autonomie-Pakete, flächendeckende neue
Performance-/Profitabilitäts-Audits, 50+ weitere Probe-Käufe,
neue Cloud-/Runner-/Scheduler-Komponenten oder Upgrade-Kosten.
Bestehende Work-/Research-Routinen und Source-Registry unverändert.

### Einheitlicher Quell-/Abhängigkeits-Readback für den bereits vorhandenen V3-Gate-Owner

Um vor und nach dem Wartungs-Staging keine unterschiedlichen GitHub-/Windows-
Abhängigkeitslisten per Hand zu pflegen, bietet **dieselbe** vorhandene
`tools/v3_experimental_paper_technical_gate.py` jetzt einen einmaligen
read-only CLI-Ausdruck (aus dem überprüften, bewusst isolierten Checkout):

```powershell
python -B tools/v3_experimental_paper_technical_gate.py --source-closure-readonly
```

Dieser ausschließlich statische Quellen-CLI-Leselauf verwendet `-B`
(keine Bytecode-Cache-Dateien), **nicht `-I`**: Python `-I`
entfernt auch das Skriptverzeichnis vom Importpfad, den das vorhandene
technische Gate für seine ursprünglichen lokalen Kompatibilitätsimporte
benötigt. Der separate **tatsächliche native Runtime-Import-Smoke
`python -I -B`** nach Wartung bleibt weiterhin erforderlich. Die
bestehende Pflicht-CI testet den gezeigten echten Direktaufruf separat.

Die standardmäßig erzeugte JSON-Ausgabe auf **stdout** enthält dieselbe
deterministische `candidate_transitive_source_sha256`, Einzeldaten
`candidate_transitive_files` und getrennte Listen für erkannte
Standardbibliotheksimporte, **potenziell externe** Importpräfixe sowie
lokale dynamische Importstellen. Sie speichert keine Datei, installiert
nichts, startet keine Tasks, Cloud-Funktionen, Modelle oder Paper-Writer.
Die schon geschützte Architektur-CI prüft den CLI-Parser zusammen mit der
Quelleninventur und zeigt eine kompakte Zusammenfassung der konkreten
externen/dynamischen Kandidaten; der **volle** Bericht kann ausschließlich
am tatsächlich festgepinten Stage-Checkout während Wartung ausgegeben werden.

**Freigabegrenze:** Das ist statische Importgraph-Beobachtung, keine
installierte/geladene Modulidentität oder Paketversionen-Verifikation.
Der technisch notwendige `python -I -B`-Original-Windows-Smoke,
lokale pip-/Python-Paketversionen, dynamische Imports, originale Task/PID/
Loaded-Module-Quittungen und die sechs tatsächlichen Release-E2Es bleiben
im bestehenden Wartungs-/Release-Owner offen. Ein grünes JSON ist nie
CAS-/PAPER-Go-live-Freigabe.

## Rollierende, versionsgebundene Skript-/Runtime-Abnahme beim CPU-/Windows-Wartungstermin (Nutzerentscheidung 20.10.2026)

**Keine starre PR419-only-Dateikopie:** Die Wartung übernimmt nicht blind den GitHub-Stand von heute. Als Quellen gelten der **unmittelbar vor Wartungsbeginn neu abgerufene geschützte `main`** (mit dokumentiertem Commit-SHA), die bestehenden Owner/Backlog-/Issue-#353-Belege, die exakten bereits gemergten und CI-geprüften PRs und **frische Originalhost-/Cloud-Readbacks**. Reine GitHub-Merges sind weder Mini-PC-Installation noch Betriebsnachweise; noch offene PRs nicht vorzeitig als installiert oder freigegeben behandeln. **Wartungs-Stichtag:** Den vollständig gelesenen HEAD mit Datum unmittelbar vor der tatsächlichen Safe-Pause als festen Ausführungs-Snapshot protokollieren; spätere PR-Merges während der Hardware-/Windows-Arbeit nicht unbemerkt hineinziehen, sondern erneut ausdrücklich auf Eignung und Freigabe prüfen.

- [ ] **`SCRIPT_RELEASE_CANDIDATE_INVENTORY` vor Shutdown erstellen:** Seit der letzten wirklich physisch bestätigten Host-Version alle Mini-PC-relevanten Änderungen und offenen Installations-/Originalhost-ACKs erfassen (historischer PR419-STOP-/Restore-Nachlauf, PR425/442/444, PR451–457 und alle **bis zum Wartungstermin danach** gemergten Nachfolger; CPU-/V2R4-Cache PR360/382, Runner-/Windows-/CloudSync-Änderungen nur wenn tatsächlich betroffen). Für jeden Kandidaten festhalten: **Quelle + Commit/Datei-SHA, physisch laufender Task/Prozess und dessen echte Quelle, abhängige Imports/Dateien, Freigabe-/Teststatus, Rollback, Zielort und Verantwortlicher**. Bereits abgenommene Tests nur bei einer nachweislich relevanten Änderung erneut öffnen. Unveränderte aktive Runtime/Strategie nicht allein wegen neuem Repo-Code als veraltet ersetzen.
- [ ] **Entscheidung pro Änderung statt Sammel-`git pull`:** `KEEP_EXISTING` (läuft korrekt), `STAGE_AND_ACCEPT` (im Wartungsfenster autorisiert, vollständig testbar), `SEPARATE_RELEASE_GATE` (V3-/Cloud-/CAS-/Modell-/Writer- oder V2R4-Strategie-/Serienwechsel) oder `DEFER_WITH_OWNER` (noch nicht reif). Quellübernahme nur aus einem festen, aktuell getesteten Commit mit Manifest und echten Hashes. Originales Arbeitsrepo mit lokalen Änderungen, bestehende Backups, aktive V2R4-Tasks und altes deaktiviertes V3-Staging **niemals blind überschreiben**; bei V3 immer einen getrennten inaktiven versionsgebundenen Stage-Pfad verwenden.
- [ ] **Tatsächlich ausführbaren Quellumfang prüfen:** Für den neuen V3-Native-Launcher die vollständigen transitiven Python-Imports, originalen Sechs-Belege-Gate-Module und den `python -I -B`-Read-only-Smoke aus PR457 einschließlich aktueller Nachfolger nachweisen. Die bestehenden Windows-Task-Actions, Originalhost-Task→Prozess-Abstammung, SHA und die aktuelle Cloud-/CAS-/Altserien-Nachpflege-Linie unabhängig abgleichen. Eine source-grüne Prüfung ersetzt weder sechs echte technische Original-E2E-Quittungen noch eine aktive V3-Paper-Freigabe.
- [ ] **Nach CPU/Windows-/USV-Setup kontrolliert abnehmen:** Erst Hardware/Windows und bislang aktive V2R4-/Cloud-Health stabil verifizieren, dann **nur** die als `STAGE_AND_ACCEPT` klassifizierten aktuellen und gehashten Skripte isoliert einspielen bzw. reine Vorschau/Readback original am Mini-PC ausführen. PR419-/No-Rearm-STOP-/Restore-Eingriffe oder eine echte Paper-/Cloud-CAS-/Single-Writer-Umschaltung nur mit ihren **gesonderten** Originalhost-/Cloud-/Rollback-/Freigabegates; aus CPU-Wartung folgt **keine** automatische Ausführung. Bereits belegte PR419-STOP-/Restore-Nachweise nicht unnötig wiederholen; geänderte Skriptbytes erfordern hingegen frische Hash-/Preview-Abnahme.
- [ ] **Abschlussmatrix und ehrliche Übergabe:** Pro Kandidat `SOURCE_VERIFIED`, `STAGED_SHA_VERIFIED`, `ORIGINALHOST_ACK`, `LIVE_DEPLOYED` oder `DEFERRED/BLOCKED` nur mit tatsächlichem Beleg setzen; finalen Wartungs-`main`-SHA, Stage-/Task-Identitäten und offene Restpunkte im **vorhandenen** Issue #353 und jeweiligen Fach-Owner festhalten. CPU-/Windows-/USV-Setup darf separat abgeschlossen werden; ungeklärte V3-Gates bleiben offen. **Keine** zusätzliche Verwaltung, Task, Work-Automation oder V3-Aktivierung.

## Verbindlicher USV-Anschluss und Konfiguration im selben CPU-/Windows-Wartungsfenster — Green Cell UPS01LCD (Nutzerentscheidung 20.10.2026)

**Status:** Green Cell UPS Micropower 600VA LCD, Modell `UPS01LCD` (600 VA / 360 W), bestellt; Green-Cell-Hersteller-App vom Nutzer bereits heruntergeladen. **Noch nicht physisch angeschlossen, konfiguriert oder getestet.** Nachtrag und Original-Owner im [bestehenden Issue #353](https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/353#issuecomment-6285335488). Dieses Paket gehört zur **bereits vereinbarten** Wartung i7-8700T + Windows-11-Updates + BIOS-AC-Recovery + PR419-Skript-Nachlauf; kein zusätzlicher Live- oder V3-Cutover.

### Während des geplanten CPU-/Windows-Termins verbindlich

- [ ] **USV-Aufbau / Anschluss:** Herstelleranleitung, Steckdosen, sichere Aufstellung, Leistungsreserve und die tatsächliche PC-Last prüfen; USV ans Stromnetz, Mini-PC ans batteriegepufferte Ausgangsnetz, USV-Kommunikationsport via USB mit Mini-PC verbinden; LCD-/Batterie-/USB-/Windows-Geräteerkennung und Ladezustand ohne Unterbrechung des Netzstroms prüfen. Kein Live-Stromausfalltest während der Inbetriebnahme.
- [ ] **Hersteller-App:** Bereits heruntergeladenes Programm mit geprüfter Herstellerherkunft/Version korrekt installieren oder vorhandene Installation abschließen, USB-Handshake und angezeigte Messwerte prüfen, Hintergrundbetrieb/Autostart soweit erforderlich konfigurieren; tatsächliche Menüs/Optionen und gewählte Werte mit Version dokumentieren.
- [ ] **Geordneter Shutdown:** In der App ausreichend konservative Netzausfall-Wartezeit beziehungsweise niedrigen Batterie-Schwellenwert mit echter Windows-Shutdown-Reserve einstellen. Nach Auslöser ordentlich Windows herunterfahren (kein Sleep/Ruhezustand/hartes Abschalten). V2R4-/Altserien-/CloudSync-/Runner-Zustand und geordneten Writer-Stopp bei der Konfiguration berücksichtigen. Sicherstellen, dass vorhandene CPU-Runner-Safe-Pause / aktive Wartungsschritte nicht durch UPS-Ereignisse konterkariert werden. Die Auswahl an Schwellwerten anhand realer USV-App, Last und Restlaufzeit festlegen, **keine ungeprüften Minuten-/Prozentwerte behaupten**.
- [ ] **Wiederanlaufkonfiguration:** Dell BIOS `AC Recovery / Restore on AC Power Loss` kontrollieren, `Power On` ist bevorzugt. **Gesondert** die tatsächliche Modell-/App-Fähigkeit für Abschalten des USV-Ausgangs *nach* OS-Shutdown und automatische AC-Ausgangswiederkehr nach Netzrückkehr ermitteln. BIOS-`Power On` allein bootet den PC nur bei einer echten neuen AC-Einschaltflanke; bleibt die USV trotz Windows-Shutdown durchgehend am Ausgang aktiv, findet womöglich kein automatischer Boot statt. Nicht ohne Beleg als gelöst markieren. Eine abweichende Realität als `UPS01LCD_AUTOSTART_DEPENDENCY_OPEN` dokumentieren, statt unbestätigte Funktion zu versprechen.
- [ ] **Software-/Projekt-Neustart:** Nach *geplanter* CPU-/Windows-Wartung App-Verbindung, BIOS-Setting, Windows-Autostart, notwendige V2R4-/CloudSync-/LAN-Dienste prüfen; bestehende `CPU_MAINTENANCE_RUNNER_SAFE_PAUSE` und getrenntes bewusstes `POST_MAINTENANCE_RUNNER_REARM` strikt erhalten. Keine stillschweigende V3- oder Echtgeldfreigabe. `UPS01LCD_CONNECTED_AND_CONFIGURED` nur bei tatsächlich belegtem Setup als PASS quittieren.

### Absichtlich späteres separates Wartungsfenster — keine Verlängerung des CPU-Termins

- [ ] **Nach geladenem Akku und mit beaufsichtigtem Testplan** kurze Netzunterbrechung (Mini-PC bleibt auf USV an), lange Unterbrechung (App löst einen echten kontrollierten Windows-Shutdown aus), Netzrückkehr *nach* OS-Shutdown (tatsächliches USV-Ausgangs-Aus/An und Dell-Reboot) und Wiederherstellung von App, LAN, Windows-Tasks, V2R4-/Cloud-Health verifizieren. Kein blinder Stromstecker-Test bei ungeklärter aktiver Last oder ungeplantem Host-Stopp.
- [ ] **Getrennte Prüfergebnisse:** `UPS01LCD_CONTROLLED_SHUTDOWN_E2E` und `UPS01LCD_POWER_RETURN_AUTOSTART_E2E` bleiben bis zum echten Originalhost-/USV-Nachweis `OPEN_DEFERRED_LATER_MAINTENANCE`. CPU-/Windows-Wartung darf separat abgeschlossen werden; UPS-Setup ersetzt die späteren Tests nicht. Falls Modell/App automatisches AC-Output-Cycling nicht unterstützt, technische Grenze und nächste begrenzte Lösung dokumentieren, keine grüne Abnahme fingieren.

Kein neuer Scheduler, Work-Aufruf, Projektmanager, V3-Test-Task oder siebtes V3-Release-Gate. Die Vorab-KI- und GitHub-Prüfungen belegen **nur** den gemergten Quellcode (4/4 CI PASS), keine Host-Übernahme.

## Physische CPU-Meilensteine, Quellübernahme und exakte Zustände (17.10.2026)

- **PR #360** (main `c8f37da865314ac91d36c786b66d107aad4a28d1`): vorhandene V2R4 Candidates- und PR326-WAIT-JSON-Caches mit begrenzten Einträgen/Bytes, synthetische Ergebnisparität bei **16.907** Candidates-Ereignissen und **4.767** WAIT-Dateien. Kein Live-Deployment aus CI.
- **PR #382** (main `c2ff676196a08d89dbe2584144c70555149d49ca`): zusätzlich zu PR360 im **gleichen Candidates-Quellmodul** revisiongebundene Memoisierung von beobachtetem UTC-Zeitpunkt und Event-ID. Geänderte/quellkorrigierte Ereignisse werden erneut ausgewertet; frische Zeit-/Recovery-/Paper-Regeln bleiben aktiv. 185 V2R4-Tests und GitHub-Context-/Architekturchecks bestanden. **PR362s zuvor isoliert bereitgestellter PR360-Stand ist nicht nachträglich PR382**: ein zukünftiges Bundle muss die tatsächlich gewünschten, vollständigen und erneut gepinnten Dateien verwenden. Keine stillschweigende Quellüberschreibung.
- **Einmalige Originalhost-Baseline PR #378, bereits vorhanden:** 30-Sekunden-Messung, Windows-CPU durchschnittlich **46,5 %**, Spitze **86 %**, **22 Python-PIDs** in **11 sichtbaren Eltern-Kind-Paaren**. PR326 WAIT ca. 12,07 % CPU, damals nicht eindeutig klassifizierter V2R4-Anteil ca. 11,12 %, sonstiges Python ca. 5,66 %. Kein Nachweis doppelter Worker und kein nachgewiesener CPU-Gewinn der neuen Module. Messung/Sicherung nicht lediglich zur Dokumentation wiederholen.
- **Geltende Entscheidung:** Kein neuer Daueragent, keine zweite CPU-Wartungsplattform und kein gesonderter Work-/Controlling-Lauf. Die laufende eingefrorene 09.10.-V2R4-Paper-Serie und originale PR326-WAIT-Nachpflege bleiben unberührt. Prüfe bei einem ohnehin genehmigten **Versions-/V3-Release-Gate** `KEEP/TEST/DEFER` dieser belegten Hotloop-Erkenntnisse in den *tatsächlich verwendeten* Nachfolgerkomponenten. V3 ist eine andere Runtime: V2R4-Dateien nicht unbesehen in V3 kopieren. Für einen getrennten V2R4→V2R4-Wechsel gelten die nachfolgenden Cloud-CAS-, Altserien-Nachpflege-, Supervisor- und Release-Gates uneingeschränkt.
- **Abnahme:** Nur ein durch aktuelle Quell-Fingerprints, echte Laufzeit/Cloud-ACKs, vergleichbare CPU- und Latenzmessung und fortschreitende WAIT-/TTL-/6h-/24h-Rechnungen belegter Nachfolger ist `LIVE_CPU_IMPROVEMENT_VERIFIED`. PR-Merge, synthetischer Cache-Speedup oder ein grüner Windows-Host-Read-only-Gate allein reichen ausdrücklich nicht.

## Gemeinsame V3-Go-live-Übernahme statt separater V2R4-CPU-Rotation (Nutzerentscheidung 17.10.2026)

**Priorität geändert:** Diesen eigenständigen V2R4→V2R4-Release-Vertrag als sichere historische technische Alternative aufbewahren, aber **nicht** weiter als separaten produktiven CPU-Cutover verfolgen, solange der ohnehin vorbereitete V2R4→V3-Paper-Go-live der natürliche Nachfolger ist. Dies ist keine Behauptung, dass die V2R4→V2R4-Altserien-Nachpflege schon einsatzbereit sei. Aktive Oct09-Tasks, PR326 WAIT und alte Serien bleiben bis zur echten V3-Release-Entscheidung unverändert. Kein CAS-/Stop-/Installationsoperator aus diesem Offline-Vertrag ausführen.

Die bestehende V3-Freigabe in `docs/v3-controlled-paper-cutover-20261011.md#1b` ist ab jetzt der **bevorzugte einzige produktive Übernahmeweg**: sowohl alten Candidates-Scanner als auch **PR326 WAIT** im gleichen vorhandenen No-Rearm-Intake-Fence kontrolliert stoppen. Ein `PR326 WAIT`-Worker darf **keine neuen V2R4-Rechecks nach V3-Cutoff** auslösen; die originale `run_closed_aftercare_once` lehnt sie ausdrücklich ab. Vor Cutover offene/abgelaufene/ungeklärte WAIT-Pläne korrekt klassifizieren, keine spätere Beobachtung erfinden und keine offenen Pläne als bewiesene NO_TRADE abschließen. **Getrennte** originale Lifecycle-/Exit-/STOP-/TTL- und 6h/24h/72h-Folgeprozesse und der geschützte PR332-CloudSync bleiben für die Altserien-Nachpflege in ihrem echten vorhandenen Owner erhalten. PR360-WAIT- und PR382-Candidates-Caches werden **nicht** in stillgelegte Alt-Intake-Prozesse hinein aktiviert; die Entlastung ist deren nachgewiesener Wegfall. Im neuen V3-Journal/WAIT nur tatsächlich gemessene Engpässe optimieren. Ein fehlender sicherer Alt-WAIT-Abschlussbeleg ist ein offener bestehender V3-Go/No-Go-Punkt, kein Anlass für in-place Umschreiben oder zusätzliches sechstes-plus-eins-Gate.

Bereits vorhandene Original-CPU-Baseline, Sicherung, PR360-/PR382-Regressionen und Staging bleiben gültig und werden nicht wiederholt, sofern nicht eine konkrete neue Änderung ihren Prüfwert aufhebt. Alles Neue am echten V3-Paket vor physischem Cutover technisch verifizieren; tatsächlicher CPU-Effekt wird mit ohnehin nötigen V3-Poststart-Readbacks geprüft. Das ist **keine siebte V3-Freigabe**, kein zweiter Projektmanager und keine implizite Aktivierung.

## Entscheidung zur Versionierung

**Kein schneller In-Place-Quellenaustausch innerhalb der eingefrorenen Serie.** Die vorhandene `paper_runtime_control.json` und die Supabase-Release-/Bundle-Fingerprints bezeichnen die bisherigen Originalbytes. Sie dürfen nicht nachträglich auf einen neuen Codezustand umgedeutet, überschrieben oder als „unverändert“ ausgewiesen werden.

Ziel ist ein eigenständiger **technischer Nachfolger innerhalb V2R4** mit **neuer Serien-ID, neuer Release-SHA und neuem tatsächlichem Bundle-Fingerprint**. Der Strategie-Fingerprint und die Paper-Regeln bleiben identisch (50+50, kein Echtgeld). Alte Outcomes bleiben der alten Serie zugeordnet. Laufende alte Trade-Exit-/Stop-/Stage2-/WAIT-/6h-/24h-Follow-ups brauchen einen expliziten, nachgewiesenen **Altserien-Nachpflege-Owner**, während nur ein neuer Kandidatenschreiber aufgenommen wird. Kein Reset, Umschreiben oder vorgetäuschtes Complete.

Die existierende `v2r4-technical-cutover` Edge-Funktion und `tools/minipc-v2r4-technical-cutover-operator.ps1` sind auf die **Serie vom 07.10.** gepinnt. Sie dürfen **nicht** für die Serie vom 09.10. als bereits funktionsfähige Release-Methode gelten. Die vorhandene Oct07-Supervisor-Maintenance-Datei ebenfalls nicht verwenden. Ein getrennt reviewtes neues Cloud-CAS-/Supervisor-Fence-/Altserien-Nachpflege-Verfahren ist nötig, bevor man produktive Tasks anfasst. Auch ein neues `v3-experimental-paper-old-intake-fence` darf nicht als CPU-Wartungsersatz verwendet werden.

## Neu bestätigte Cloud- und Folgeprozess-Abhängigkeiten

Direkte Quelle `supabase/functions/v2r4-paper-evidence-relay/index.ts`:
- `action=sync` synchronisiert nur eine wirklich **aktive** V2R4-Serie, nicht alte offene Nachpflege unter `technical_closed`.
- Der besondere Pfad `closed_original_*` verlangt derzeit explizit einen **aktiven V3-Nachfolger** (Release-Identity `PAPER-V3-...`). Er ist **kein** Nachweis dafür, dass ein *weiterer V2R4*-technischer Nachfolger alte WAIT-/Stop-/Follow-up-Ergebnisse aktualisieren könnte.
- `tools/v2r4-paper-cloud-sync.py` übernimmt diesen Spezialpfad bislang nur bei explizitem V3-Marker. Ohne technische Erweiterung würden `technical_closed`-V2R4-Nachpflege und laufende neue V2R4-Kandidaten gegeneinander laufen.
- Die historische `paper_technical_rotations` enthält bereits den Übergang vom **07.10. zum 09.10.**. Die bisherige Cloud-Rotationsfunktion und der lokale Operator sind auf diesen alten Vorgänger festgelegt.
- `tools/project_milestone_controller.py` sowie der Cloud-Paper-Completion-Reader dürfen nicht unbeabsichtigt historische V2R4-Perioden als neue Strategie-Fortschritte, nicht gereifte 6h/24h-Ergebnisse als geschlossen oder den neuen technischen Teilabschnitt als V3 behandeln.

**Verpflichtende zusätzliche V2R4-zu-V2R4-Gates** (kein Programmcode-/Cloud-Nachweis aus einem booleschen Testfixture): (1) eigener schreibberechtigter, aber streng altseriengebundener Nachpflege-/Idempotenzpfad, (2) keine neue alte Kandidatenaufnahme, (3) eindeutiger alten Serie zugeordneter Follow-up-Owner und passende Exit-/Recheck-Receipts, (4) getrennte neue Nachfolgerserie mit genau einem neuen Kandidatenschreiber, (5) nachweislich dynamisches Milestone-/Alert-Routing, (6) zwei unabhängige frische Cloud-ACKs nach echter Übernahme. Die Offline-Tests simulieren nur diese Bedingungen und halten `production_release_authorized=false`.

## Isolierte technische Release-Reihenfolge

1. **Stand prüfen:** Exakte aktuell aktive Serie in lokaler Runtime + Cloud; Einzelschreiber, drei Task-Modi und Supervisor; alte PR326-Originale; erneut nur bei neuem eigentlichen Release-Termin. Vorhandene physisch bestätigte PR369/374-Gates und sechs Windows-Cache-Tests **nicht grundlos wiederholen**.
2. **Neuen versionierten Kandidaten bauen:** Komplettes, separates, unveränderliches App-/WAIT-Paket mit dem tatsächlichen neuesten, neu gehashten Candidates-Quellstand **PR360 + PR382**, dem originalen begrenzten WAIT-Cache aus **PR360**, originalen PR326-Watcher/Launcher/Public-Budget-Abhängigkeiten und *neuem tatsächlichem* vollständigem Bundle-Fingerprint; Strategie identisch; keine aktive Task-/Runtime-/Control-Datei überschreiben. Vollständige Python-Importbasis, gepinnte relative Pfade, eigene neue Series-Control und isolierte Persistenz gegen Original prüfen. Testausgaben niemals in Live-Ordner schreiben.
3. **Sicherheits- und Fehlertests:** Vollständiger offline-seitiger Fehlerbaum und reine Entscheidungslogik in `tools/v2r4_cpu_versioned_release_contract.py` + `tests/test_v2r4_cpu_versioned_release_contract.py`. Unter anderem unerwartete Besitzer/PIDs, `IgnoreNew`-Grenze, fehlende Kindprozesse, unvollständige Heartbeats, Nullbackup beim atomaren Markerwechsel, fremdes Stop-Owner-Rearm, unvollständiger Abschluss/Cloud-Timeout, doppelte CAS-Nachrichten, offen gelassene alte Follow-ups, vordefinierte sichere Pfade. **Ein Test mit künstlichen ACKs ist ausdrücklich kein echter Host-/Cloud-Nachweis.**
4. **Separaten, expliziten Release-Operator sicher bauen/testen:** Standard = nur Lesen/Plan anzeigen. Ein produktiver Modus darf erst nach eigenem Review, geprüften Negativtests und explizitem Go/No-Go existieren. Vor Stopp: alten Supervisor-Timer/Runner und andere Recovery-Eigentümer zuverlässig kontrollieren, native Task-Konfiguration archivieren. Supervisor-Owner-ACK *vor* produktiven Task-Stops. Stoppen und *tatsächliches Ende aller exakten Original-Python-Prozessabkömmlinge* prüfen. PID-Neuverwendung absichern (PID + Startzeit + Eigentümer/Root); keine PowerShell-Argumenterwähnung als Worker zählen. Im Zweifel **fail closed**, keine Quelle ersetzen.
5. **Entscheidungs-/Commit-Grenze:** Finales Cloud-/lokales Ledger- und Kandidaten-ID-Digest; offene Wait/Stop/TTL/Rechecks erhalten; Cloud-CAS mit erwarteter aktiver 09Oct-Serie, einem expliziten neuen versionierten Release-Bundle und atomar maximal **einer** aktiven Paper-Serie. Cloud-Timeout nach CAS ist **unklarer Zustand**, kein Signal für erneutes Commit oder blindes altes Worker-Restart. Separater Altserien-Nachpflegepfad nachgewiesen.
6. **Wiederanlauf:** Nur einmalige verifizierte neue Task-Owner, korrekte `--mode`-Pfade und neue Bundle-Pins; originaler Alt-Followup-Owner beibehalten, alte Kandidatenaufnahme bleibt gestoppt. Native Windows-Task-States + echte Python Worker-PIDs/Startzeiten und mindestens zwei verschiedene frische Cloud-/Host-ACKs sowie vorwärtslaufende Heartbeats, reale Paper-Entscheidungen ohne Duplikate. Supervisor erst nach erwiesener Task-Quittung in konsistenten Originalbetrieb bringen.
7. **Rückfall:** *Vor* einer bestätigten Cloud-CAS: alte zwei SHA-geprüfte Originale aus vorhandener Sicherung in einer vollständig quieszenten Umgebung zulässig; nur nach unabhängiger Bestätigung alter Cloud-Serien-Autorität, wirklichem Einzel-Writer und zweimal fortgeschrittenen Heartbeats. *Nach* bestätigtem oder unklarem CAS: alte Tasks **nicht blind reaktivieren**. Gesichert halten, Cloud/Writer/Belege manuell abgleichen; versionierter Recovery-Entscheid, ggf. neue explizite CAS-Operation.
8. **Nutzenmessung:** 30-Sekunden-Ursprungsstichprobe (Candidates ~11,1 %, WAIT ~11,7 %, Lifecycle ~2,2 %, zusammen ~25 %) ist **nur Kurzzeit-Momentaufnahme**, keine vergleichbare Dauerlast. Vergleich über gleichartige Zeitfenster, Event-/Plan-Mengen, Cache-Treffer, p95 Latenz, CPU-Verbrauch und fehlende Receipts; keine Steigerung behaupten, nur weil GitHub-Tests grün sind.

## Explizite Sperren und Eigentümer

Aktiver 09Oct Paper-Owner bleibt unverändert; PR326 WAIT unter seinem ursprünglichen Schutz, V3 hat eigene Release-Control-Plane und wird nicht automatisch umgeschaltet. Keine Echtgeldaktionen. Kein zweiter Scheduler/Watchdog/Work-Lauf. Owner/Backlog bleibt [Issue #353](https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/353). Budget-, User-/Admin-, Cloud-/Supabase- oder neuen Runtime-Rechte-Gates nicht durch den Offline-Simulator ersetzen.

Der Python-Vertragsprüfer ist **ohne irgendeinen ausführbaren Stop-/CAS-/Installationsmodus**. Das maximale Ergebnis `SYNTHETIC_SEQUENCE_PASS_NOT_PHYSICAL_RELEASE_ACK` bleibt eine **synthetische Vorprüfung** und genehmigt keine Live-Aktion. Nächster sinnvoller implementierbarer Baustein: isolierte neue Bundle-Identität und nachweislich inaktive getrennte Cloud-/Runtime-Release-Schnittstelle, dann Mock-/Windows-Originaltests und einmalige physische Release-Abnahme.
