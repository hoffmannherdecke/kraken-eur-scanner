# Mini-PC Preflight / Inbetriebnahme-Runbook

Status: **PREPARED BEFORE FIRST BOOT**  
Stand: 2026-09-29  
Gerät: Dell OptiPlex 5060 Micro — i5-8500T / 16 GB RAM / 256 GB SSD / Windows 11 Pro erwartet  
Netz: LAN, FRITZ!Box 7590 AX

## Ziel

So früh wie möglich vom direkten Arbeiten am Gerät auf Fernadministration wechseln, danach den Mini-PC schrittweise zur stabilen 24/7-Basis ausbauen. Keine V2R4-Aktivierung beim ersten Boot.

## Bereits vorab verifiziert

- Windows 11 Pro kann als Microsoft-Remotedesktop-Host dienen.
- Dell OptiPlex 5060 besitzt im BIOS `AC Recovery` mit `Power On` / `Power Off` / `Last Power State`; für 24/7 ist `Power On` vorgesehen.
- GitHub-Hauptpfade und V2R4-Draft existieren.
- Supabase-Projekt ist aktiv/gesund und besitzt bereits Paper-Archivtabellen.
- V2R3 ist technisch als aktive Paper-Serie registriert: `PAPER-V2R3-FINAL-20260928T1752Z`.

## Phase A — direkt am Gerät, nur das Nötigste

1. Hardware prüfen: Netzteil, LAN, Monitor, Tastatur/Maus.
2. BIOS öffnen:
   - Datum/Uhrzeit plausibel.
   - `AC Recovery = Power On`.
   - Boot-/Secure-Boot-Einstellungen zunächst nicht unnötig verändern.
3. Windows starten:
   - Edition tatsächlich Windows 11 Pro bestätigen.
   - Windows Update vollständig durchführen.
   - Dell-Treiber/BIOS-Version prüfen und nur kontrolliert aktualisieren.
   - Zeitsynchronisation prüfen.
   - SSD-Zustand / freier Speicher / Ereignisanzeige grob prüfen.
4. Rechner eindeutig benennen.
5. Starkes lokales/Windows-Kennwort sicherstellen.
6. LAN-Verbindung prüfen.

## Phase B — interner Fernzugriff sehr früh

1. FRITZ!Box: dem Mini-PC eine stabile DHCP-Zuordnung/reservierte IPv4 geben.
2. Windows Remotedesktop aktivieren.
3. Netzwerkprofil/Firewall so prüfen, dass RDP nur im vorgesehenen privaten Netz erreichbar ist.
4. Vom Laptop im selben LAN per PC-Name und zusätzlich testweise per interner IP verbinden.
5. Neustart des Mini-PCs und erneuten RDP-Zugriff testen.

**Gate:** Erst wenn interner RDP-Zugriff nach Neustart zuverlässig funktioniert, wird die weitere Einrichtung überwiegend vom Laptop erledigt.

## Phase C — 24/7-Basis

- Schlafmodus/unerwünschtes Energiesparen deaktivieren.
- Automatischen Neustart/Wiederanlauf nach Stromverlust praktisch testen.
- Windows Update/Neustart-Verhalten kontrollieren.
- Defender/Firewall aktiv lassen.
- keine automatische Echtgeld- oder Trading-Ausführung.
- Verzeichnisstruktur anlegen:
  - Runtime
  - State
  - Logs
  - Temp
  - Archive/Backup
  - Secrets getrennt von Repo/Logs
- TTLs/Log-Rotation/Speicherlimits von Anfang an vorsehen.

## Phase D — Entwicklungs-/Runtime-Basis

Nach stabilem Remotezugriff:
1. Git installieren/verifizieren.
2. Python-Version bewusst festlegen und verifizieren; nicht blind mehrere Versionen mischen.
3. Repositories klonen:
   - `kraken-eur-scanner`
   - `kraken-readonly-bridge` nur soweit lokal nötig
   - archivierten `canonical-evaluator-runtime-v1` nicht als aktiven Runtime-Pfad verwenden.
4. Lokale Environment-/Secrets-Struktur anlegen.
5. Keine API-Secrets in Git, Slack oder Chat kopieren.
6. Tests/Smoke-Test zunächst read-only und paper-only.

## Phase E — Watchdog / Logging / Recovery

Vor Realtime-Strategie:
- Prozess lebt?
- Daten frisch?
- Queue bewegt sich?
- Output plausibel?
- stale/feed-disconnected/degraded/stopped unterscheiden.
- begrenzter Self-Heal nur für eindeutige technische Fehler.
- Neustart-Reconciliation testen.
- Internet-Ausfall + Wiederkehr testen.
- kein blindes Replay alter Kandidaten.
- Backup/Restore-Smoke-Test.

## Phase F — Daten und Integrationen

Reihenfolge:
1. Kraken Public REST/WebSocket lokal.
2. Altrady als **zusätzlicher** Trigger, nie exklusiv.
3. Supabase schlank als sekundäre State-/Ergebnisschicht. Dabei ausdrücklich prüfen, warum aktuell noch keine V2R3-Outcomes in `paper_candidate_outcomes` liegen; Sync-/Persistenzpfad erst nach E2E-Nachweis als funktionsfähig markieren.
4. GitHub/API/Slack.
5. ChatGPT Desktop installieren; Work nur für Aufgaben mit echtem Rechner-/Browserkontext.
6. Uptime Kuma/Grafana nur bei belegtem Zusatznutzen.

## Phase G — V2R3 → neue Infrastruktur → V2R4

1. V2R3 bleibt bis dahin unverändert.
2. Dieselbe V2R3-Logik kurz über die neue Infrastruktur shadow/smoke testen.
3. Latenz, Zeitstempel, Persistenz, Watchdog und Rückkanäle prüfen.
4. V2R3 vollständig auswerten und Erkenntnisse migrieren.
5. Draft-PR #8 / V2R4-Spezifikation gegen alle bis dahin gewonnenen Erkenntnisse prüfen.
6. Ein kleiner E2E-Paper-Smoke-Test.
7. Erst danach V2R4 als separate aktive Paper-Serie.

## Phase H — bewusst ganz zuletzt: externe Restarbeiten

Diese beiden Punkte werden **absichtlich erst ganz am Ende des Runbooks** erledigt und blockieren die weitere MINI-PC-/Trading-Inbetriebnahme nicht.

### H1 — externer Fernzugriff testen

Zielpfad:
`Laptop außerhalb Heimnetz → FRITZ!Box VPN/WireGuard → Heim-LAN → internes RDP → Mini-PC`

Regeln:
- keine direkte RDP-Portfreigabe ins Internet;
- VPN getrennt vom lokalen RDP testen;
- echter Außentest über Mobilfunk/iPhone-Hotspot;
- erst als bestanden markieren, wenn die Verbindung außerhalb des Heimnetzes funktioniert.

Aktueller Stand:
- WireGuard-Konfiguration ist vorbereitet;
- interner RDP-Zugriff ist verifiziert;
- echter Außentest ist **DEFERRED / FINAL PHASE**.

### H2 — Laufwerk D: sichern, reparieren und neu verifizieren

Aktueller Stand:
- `D:` / `MISTRAL_450` enthält wichtige vorhandene Dateien;
- physische Toshiba-USB-Platte meldet `Healthy`;
- FAT32-Volume weist logische Dateisystemfehler / verlorene Ketten auf;
- read/write/delete-Smoke war erfolgreich;
- keine aktive Projektablage auf D:, solange die Dateisystempflege nicht abgeschlossen ist.

Spätere Reihenfolge:
1. wichtige vorhandene Dateien identifizieren und vollständig sichern;
2. kontrollierte Dateisystemreparatur oder bewusste Neuformatierung erst danach;
3. anschließend Volume-Health, Schreib-/Lese-/Löschtest und Kaltstart-Mount erneut prüfen;
4. erst dann D: ggf. als Bulk-/Archiv-/Capture-/sekundäre Backup-Fläche freigeben.

Bis dahin bleibt **C:** die einzige aktive Projekt-/Runtime-/State-Ablage.

## Informationen, die erst am Gerät erhoben werden müssen

Diese Werte werden beim ersten Start erfasst und ins Versionsregister übernommen:
- Service Tag / genaue Hardware-Revision.
- aktuelle BIOS-Version.
- exakte Windows-Build-/Edition.
- SSD-Modell/Zustand.
- aktuelle interne IP/MAC.
- FRITZ!OS-Version der 7590 AX.
- tatsächlich verfügbare CPU-/RAM-/Disk-Auslastung im Grundbetrieb.
- installierte Python/Git/PowerShell/winget-Versionen.
- gemessene Latenz zu Kraken, Supabase und GitHub.
- Verhalten nach Stromverlust, Neustart und Internetunterbrechung.

## Work-Credits

- keine zusätzlichen Work-Credits vorsorglich kaufen.
- Basis-Setup, LAN, RDP, Energie und Sicherheit ohne Work erledigen.
- Work erst bei echtem Mehrwert für Browser-/Datei-/Desktopkontext verwenden.
- falls vor der regulären Freischaltung keine Credits verfügbar sind, erst dann gezielt nachkaufen.

## Inbetriebnahme-Stand 2026-09-30

Erster realer Aufbau des Dell OptiPlex 5060 Micro:

- Rechnername: `MINI-PC`.
- Windows 11 Pro gestartet und vollständig aktualisiert; automatische Updates bleiben aktiv, aggressive/optionale Vorschauupdates nicht priorisiert.
- Lokales Benutzerkonto mit Kennwort vorhanden; automatische Windows-Anmeldung für den 24/7-Betrieb eingerichtet.
- FRITZ!Box-DHCP-Reservierung: interne IPv4 `192.168.178.179`.
- Keine direkte RDP-Portfreigabe ins Internet.
- Windows Remotedesktop aktiviert; interner RDP-Test auf `192.168.178.179` erfolgreich.
- FRITZ!Box-WireGuard-Konfiguration auf dem Notebook eingerichtet; echter Außentest via Mobilfunk/iPhone-Hotspot noch offen.
- Windows-Energie: Bildschirm 15 Minuten, Standby = Nie, Ruhezustand = Nie, Energiesparmodus = Aus, Energiestatus = Ausbalanciert.
- BIOS: `AC Recovery = Power On` gesetzt. Praktischer Stromausfall-/Wiederanlauf-Test nach finaler Geräteplatzierung am 2026-09-30 erfolgreich bestanden: MINI-PC im laufenden Betrieb stromlos gemacht, am Zielort neu verkabelt, Netzstrom wieder angelegt → Gerät startete selbstständig; RDP war anschließend wieder erreichbar.
- Dell Command | Update 5.7.2 installiert. Dell-/Intel-Treiberstand aktualisiert; danach meldet DCU „System auf neuestem Stand“. Geräte-Manager ohne gelbe Warnsymbole.
- Lokale Projektstruktur unter `%USERPROFILE%\Trading` angelegt: `Runtime`, `State`, `Logs`, `Temp`, `Archive`, `Backup`, `Secrets`, `Repos`.
- Git 2.55.0 und Python 3.13.15 installiert; `python` und `py` zeigen beide auf 3.13.15.
- Kanonisches Repository `hoffmannherdecke/kraken-eur-scanner` nach `%USERPROFILE%\Trading\Repos\kraken-eur-scanner` geklont.
- Repository-Check: Branch `main`, clean working tree, `origin` korrekt, Stand bei Commit `c6a93610` (`[paper-runtime] persist active-series state`).
- ChatGPT im Browser auf dem MINI-PC angemeldet, damit Befehle direkt kopiert werden können.

Noch offen aus diesem Block:
- Internet-Ausfall + Wiederkehr / Reconciliation,
- prozessspezifischer lokaler Runtime-Heartbeat/Self-Heal,
- Altrady-Relay-Secret + E2E-Transport-Smoke,
- danach V2R3-Shadow auf der lokalen Dauer-Runtime und das V2R4-Release-Gate.

Bewusst **nicht** in diesem Block: externer WireGuard/RDP-Außentest und Laufwerk-D:-Pflege. Beide stehen gesammelt in **Phase H ganz am Ende**.

## Effizienzregel für weitere Inbetriebnahme

Ab 2026-09-30 gilt für die weitere MINI-PC-Inbetriebnahme:

- ChatGPT übernimmt alle Prüfungen selbst, die über GitHub, GitHub Actions, Supabase, Slack, öffentliche APIs/Marktdaten oder reine Code-/Konfigurationsanalyse möglich sind.
- Der Nutzer soll nur noch Tests ausführen, die zwingend den konkreten MINI-PC, dessen Windows-/Zertifikats-/Netzwerk-/BIOS-Zustand oder den echten Heimnetz-/VPN-Pfad betreffen.
- Mehrere lokale Einzelprüfungen werden nach Möglichkeit in einem einzigen read-only Sammeltest gebündelt.
- Dafür liegt `tools/minipc-selftest.ps1` im kanonischen Repo. Das Skript verändert keine Systemkonfiguration und schreibt nur einen Diagnosebericht nach `%USERPROFILE%\Trading\Logs`.
- Kein wiederholtes manuelles Copy/Paste einzelner Diagnosebefehle, wenn dieselbe Evidenz über den Sammeltest oder direkt aus verbundenen Systemen erhoben werden kann.

### Lokaler Sammeltest 2026-09-30 18:58

`tools/minipc-selftest.ps1` erfolgreich auf dem MINI-PC ausgeführt.

Bestätigt:
- Defender läuft automatisch; alle Windows-Firewallprofile sind aktiv.
- Ethernet-IP `192.168.178.179/24` aktiv.
- DNS-Auflösung für `api.kraken.com` funktioniert.
- TCP/443 zu Kraken erfolgreich.
- PowerShell-HTTPS gegen Kraken AssetPairs: HTTP 200.
- Repo und venv vorhanden; Git `main` auf `origin/main`, sauberer Status.
- Python 3.13.15 / pip 26.2.1 in der venv funktionieren.
- Python-HTTPS gegen Kraken AssetPairs: HTTP 200. Der zuvor einmal beobachtete `CERTIFICATE_VERIFY_FAILED`-Fehler ist damit aktuell **nicht reproduzierbar** und gilt nicht mehr als aktiver Blocker.
- Systemlaufwerk C: 237,4 GB gesamt / 185,1 GB frei.

Beobachtungen ohne aktuellen Blocker-Status:
- Ereignisanzeige enthält u. a. ältere DCOM-10010-Einträge, einen Intel-Grafikdienst-Timeout, einen TPM-WMI-1040-Eintrag sowie während der Einrichtung fehlgeschlagene Updateversuche. Diese werden vor Produktivsetzung nochmals gegen neue, nach der Einrichtung entstandene Ereignisse abgegrenzt.
- Die `Get-ComputerInfo`-Ausgabe meldet `Windows 10 Pro / WindowsVersion 2009 / Build 26200`; die tatsächlich verwendete Oberfläche/Einrichtung ist Windows 11. Exakte Edition/Build daher später einmal direkt mit `winver` bzw. einer zweiten OS-Abfrage verifizieren, bevor der Runbook-Punkt final geschlossen wird.

Damit ist Phase D (lokale Git/Python-Runtime + read-only Smoke-Test) im Wesentlichen bestanden. Die operativen nächsten Schritte liegen in Phase E/F/G; externer Fernzugriff und Laufwerk D bleiben bewusst bis Phase H zurückgestellt.

### Watchdog / Logging / Recovery baseline prepared 2026-09-30

Cloud side verified:
- `.github/workflows/process-health.yml` runs on the scheduled watchdog cadence and performs bounded technical self-heal only; it cannot enable real-money actions or alter strategy.
- `.github/workflows/scanner-startup-recovery.yml` is an independent one-shot fallback for scheduled scanner `startup_failure`, with loop protection.
- Latest verified health audit after recovery: scanner successful, paper runtime successful, zero orphan candidates, zero overdue WAITs, zero missing position states. Remaining status is `WARNING` solely because V2R3 still has 0 `BUY_SCOUT` across 530 terminal decisions; that is a strategy/test finding, not an infrastructure failure.

Local baseline prepared in the repository:
- `tools/minipc-watchdog.ps1`: every-run local health probe for disk, repo/venv presence, DNS/TCP/HTTPS to Kraken, Python HTTPS/TLS path and Git identity. Writes only `Trading\State\minipc-health.json` and `Trading\Logs\minipc-watchdog.log`; no configuration changes, no process restart, no Git mutation, no trading action.
- `tools/minipc-log-cleanup.ps1`: bounded cleanup only inside `Trading\Logs` and `Trading\Temp` (defaults: 14 days / 2 days).
- `tools/install-minipc-baseline-tasks.ps1`: registers SYSTEM tasks `CryptoMiniPC-Health` (every 5 minutes + startup) and `CryptoMiniPC-LogCleanup` (daily 04:20), then performs an immediate health run.
- `tools/uninstall-minipc-baseline-tasks.ps1`: explicit rollback for both scheduled tasks.
- Windows CI-Smoke-Test (`MINI-PC tools smoke`) bestanden: PowerShell-Syntax, begrenzte Log-/Temp-Bereinigung und Watchdog-State/Log-Erzeugung wurden auf `windows-latest` erfolgreich geprüft.

Deliberately **not** enabled yet:
- no automatic restart/self-heal of a local scanner process until the concrete local runtime process/heartbeat contract exists;
- no automatic Git pull/reset;
- no Altrady dependency;
- no real-money execution.

Next local user action: pull the repository once and run the baseline-task installer from an elevated PowerShell. After its immediate health report is verified, Phase F baseline can be marked active.

### Local baseline tasks installed 2026-09-30

Verified from the MINI-PC installer output:
- `CryptoMiniPC-Health` registered successfully: every 5 minutes + at system startup.
- `CryptoMiniPC-LogCleanup` registered successfully: daily at 04:20.
- Immediate local health run completed with `exit code 0`.
- Health report contained no active issues (`issues: []`).
- Guardrails confirmed: no configuration changes by the health probe, no process restart, no Git mutation, no real-money actions.
- Local health state path: `%USERPROFILE%\Trading\State\minipc-health.json`.
- Local health log path: `%USERPROFILE%\Trading\Logs\minipc-watchdog.log`.

This closes the baseline local watchdog/log-rotation installation step. Process-specific self-heal remains intentionally deferred until a concrete local scanner process and heartbeat contract exist.

### Backup / Restore baseline prepared 2026-09-30

Prepared and CI-verified after the initial watchdog installation:
- `tools/minipc-backup.ps1`: daily local state backup, limited to `Trading\State`; explicitly excludes `Secrets`, `Logs` and the Git repository; default retention 14 days.
- `tools/minipc-restore-smoke.ps1`: non-destructive restore verification into a temporary directory; never overwrites live state.
- `CryptoMiniPC-Backup` is now part of `tools/install-minipc-baseline-tasks.ps1` with schedule **04:00 daily**.
- Installer seeds one immediate backup and runs one immediate restore smoke before the health check.
- `minipc-watchdog.ps1` now tracks backup freshness and warns only after **7 full days** without a successful backup.
- Rollback script removes the backup task too.
- Windows CI smoke passed for PowerShell parsing, bounded cleanup, backup creation, non-destructive restore smoke and watchdog state/log creation.

Local activation is still pending: rerun the baseline installer once from elevated PowerShell after pulling the current main branch.

### Backup / Restore baseline activated 2026-09-30

Verified from the MINI-PC installer output:
- `CryptoMiniPC-Health` active: every 5 minutes + system startup.
- `CryptoMiniPC-LogCleanup` active: daily 04:20.
- `CryptoMiniPC-Backup` active: daily 04:00.
- Immediate backup/restore seed completed before the final health probe.
- Watchdog reports no active issues (`issues: []`).
- Immediate health exit code: `0`.
- Guardrails remain intact: no configuration mutation, no process restart, no Git mutation, no real-money action.

Backup/restore baseline is therefore locally active.

### Next software gate prepared 2026-09-30

Without MINI-PC user interaction, the next local verification bundle was prepared and Windows-CI tested:
- `tools/minipc-marketdata-smoke.ps1` uses the existing isolated venv, pins `websockets==15.0.1`, runs shared market-data unit tests, then performs a bounded **public/read-only Kraken WebSocket v2** smoke against book + trades.
- The smoke explicitly verifies verified book events, at least one trade event, no data gap and no subscription error; it writes only a compact JSON report under `Trading\Logs` plus temporary capture evidence under `Trading\Temp`.
- Safety scope remains public data only: no account credentials, no order API, live evaluation disabled, real-money actions disabled.
- The exact Windows path passed in CI twice (`MINI-PC marketdata smoke`).
- `tools/minipc-selftest.ps1` was extended to include a second Windows OS/CIM identity check, physical-disk health/reliability counters where supported, CPU/RAM base-load snapshot, installed CryptoMiniPC task state and latest-backup age.
- Extended PowerShell parsing/backup/watchdog CI remains green.

The local market-data smoke itself still has to be run once on the actual MINI-PC; this will be bundled with the expanded machine self-test so the user only has to perform one next local command block.

### Bundled local next gate prepared 2026-09-30

To minimize user interaction, the remaining immediate local software checks were bundled into `tools/minipc-next-gate.ps1`.

The bundle:
- runs the expanded machine self-test;
- runs the bounded public Kraken WebSocket/book/trade smoke;
- summarizes Windows build, SSD health, CPU/RAM snapshot, scheduled-task state, backup freshness and WebSocket evidence;
- writes a combined JSON report under `Trading\Logs`;
- prints a short `FINAL SUMMARY` designed to be photographed instead of copying multiple command outputs.

Safety:
- public/read-only market data only;
- no order API;
- no real-money action;
- no strategy mutation.

The bundled script and all dependent PowerShell tools pass the Windows CI parse/smoke workflow. Local execution on the actual MINI-PC is the next required user action.

### Local next gate executed 2026-09-30

Actual MINI-PC result from the bundled local gate:
- Windows: **Microsoft Windows 11 Pro**, build **26200**.
- SSD: **KXG50ZNV256G NVMe TOSHIBA 256GB**, reported **Healthy**, ~238.5 GB device size.
- Base-load snapshot: CPU ~**3%**, RAM used ~**34.7%**.
- Local scheduled CryptoMiniPC tasks detected: **3**.
- Latest local state backup age at check: ~**0.97 h**.
- Kraken public WebSocket smoke: **PASS** with **1544** verified book events and **103** observed trades in 45 s; **0** data gaps and **0** subscription errors.
- Safety guardrails remained read-only/public-data only.

The bundle printed `Status: REVIEW` solely because one freshly installed scheduled task had a non-zero Task Scheduler status before its first scheduled execution. This is not an infrastructure failure. The gate logic was corrected to treat Task Scheduler's "has not yet run" result (`267011 / 0x41303`) as neutral rather than failed.

Operational conclusion: the actual machine, isolated Python runtime and Kraken public realtime market-data path are healthy enough to proceed. A re-run is not required solely to clear this false-positive review.

### Supabase archive sync activated 2026-09-30

Verified end-to-end after adding the repository secret `SUPABASE_SECRET_KEY`:
- GitHub workflow `Supabase paper archive sync` run #5 completed successfully.
- Credential check reported configured.
- `supabase_sync.py` archived the active series `PAPER-V2R3-FINAL-20260928T1752Z`.
- Run output: **551 candidate rows**, **0 trade rows**.
- Direct database verification after the run: **4 paper_series**, **554 paper_candidate_outcomes**, **0 paper_trade_results** total.
- Secret value remains only in GitHub Actions secrets and is masked in logs.

The Supabase archive path is now operational and remains secondary/fail-soft: archive failure must not block scanner or paper evaluation.

### Stromausfall-/Umplatzierungs-Test bestanden 2026-09-30

Physischer End-to-End-Test am endgültigen Geräteplatz:
- laufender MINI-PC wurde vollständig vom Netzstrom getrennt;
- Gerät wurde an den endgültigen Standort umgesetzt und LAN/Strom neu verbunden;
- nach erneutem Einstecken des Netzsteckers startete der Dell OptiPlex aufgrund `AC Recovery = Power On` selbstständig ohne manuellen Tastendruck;
- Windows kam wieder hoch;
- die RDP-Verbindung war anschließend wieder erreichbar.

Damit ist der praktische Stromausfall-Recovery-Punkt **VERIFIED**.

Zusätzlich angeschlossen:
- externe Festplatte `Mistral_450`
- Laufwerksbuchstabe: `D:`
- aktuell verfügbar: ca. **304 GB frei**

Speicherrolle vorerst:
- C: bleibt für aktive Runtime, venv, Repo, Secrets, State und kurze Logs.
- D: ist als **Bulk-/Archiv-/Capture-/sekundäre Backup-Fläche** vorgesehen.
- Keine aktiven Secrets, keine primäre Runtime und kein alleiniger State auf D:, solange Mount-/Wiederanlauf-/Ausfallverhalten der externen Platte nicht separat verifiziert wurde.

### Post-recovery local findings 2026-09-30

After the successful physical power-loss recovery test:
- all 3 local `CryptoMiniPC-*` scheduled tasks were present;
- `CryptoMiniPC-Health` had run since the cold boot;
- watchdog state was fresh after boot;
- external drive `D:` / `MISTRAL_450` remounted automatically;
- physical Toshiba USB disk reported `Healthy`;
- reversible write/read/delete smoke on `D:` passed;
- FAT32 volume itself reported `Warning` and read-only `chkdsk D:` found filesystem errors / lost chains. No repair has been authorized yet.
- watchdog warning source was not network/runtime health: Git under the SYSTEM scheduled-task account rejected the ADMIN-owned working tree as `dubious ownership`.
- watchdog Git checks were patched to use a per-command `safe.directory` override. No global Git configuration mutation is used.

Open local action: finish the non-destructive CHKDSK diagnostic (answer `N` to converting lost chains to files), then decide whether to repair/reformat the external FAT32 volume only after considering any data that must be preserved.

### FAT32 diagnosis on external drive D: 2026-09-30

Read-only `chkdsk D:` completed after the post-recovery volume warning:
- filesystem: FAT32;
- volume label: `MISTRAL_450`;
- Windows found logical filesystem errors but did not repair them because `/F` was not specified;
- CHKDSK reported lost chains and estimated that **320 KB** would be freed by repair;
- user answered `N` to converting lost chains into files;
- reported volume size: 488,265,248 KB;
- reported free space: 319,072,384 KB;
- physical disk remains reported `Healthy`, and the reversible write/read/delete smoke had passed.

Operational interpretation:
- this is currently a **filesystem/volume integrity issue**, not evidence of a failing physical disk;
- do not reformat or run `chkdsk /F` blindly while existing data may matter;
- preserve/backup important existing data first, then perform controlled repair and re-verify volume health.

### External drive D: remediation deferred 2026-09-30

User confirmed that `D:` / `MISTRAL_450` still contains files that must be preserved.

Decision:
- no `chkdsk /F`, no format and no migration to NTFS now;
- do not use D: as active project storage until preservation/repair is completed;
- later sequence: identify/preserve important files -> controlled filesystem repair or clean reformat -> re-run health + write/read/delete + cold-mount checks;
- C: remains the only active project/runtime/state location for now.

This storage-maintenance item is intentionally deferred so MINI-PC commissioning can continue. Operative Bearbeitung erfolgt erst in **Phase H2 ganz am Ende des Runbooks**.

### P2 continuous Kraken canary prepared 2026-09-30

To establish a concrete local 24/7 process/heartbeat contract before strategy coupling:
- `tools/minipc-kraken-canary.py` added: continuous public Kraken WebSocket canary on BTC/EUR; no account access, no strategy action, no order API.
- `tools/install-minipc-kraken-canary.ps1` / uninstall rollback added.
- Task name: `CryptoMiniPC-KrakenCanary`; runs as SYSTEM at startup with bounded Task Scheduler restart.
- Heartbeat: `Trading\State\kraken-canary-heartbeat.json`.
- Local watchdog now checks the canary heartbeat only when the task is installed; stale/degraded state becomes a warning while the independent GitHub path remains available.
- `tools/minipc-phase2-enable.ps1` bundles the remaining local activation proof: verifies the fixed SYSTEM Git watchdog check, installs/starts the canary, then re-runs the watchdog against the live heartbeat.
- Windows CI parsing is green.
- Bounded live public Kraken canary smoke is green in `MINI-PC marketdata smoke`.

Next local action is intentionally a single administrator PowerShell bundle after one `git pull --ff-only`. After that evidence is captured, further P2/P3 code work can continue without user interaction until the next truly machine-local or secret-handling gate.

### P2 continuous Kraken canary activated 2026-09-30

Actual MINI-PC activation proof from `tools/minipc-phase2-enable.ps1`:
- existing local watchdog before canary: **HEALTHY**;
- `CryptoMiniPC-KrakenCanary` installed and **Running** as a SYSTEM startup task;
- Task Scheduler `last_result=267009 / 0x41301` means the long-running task is currently running, not failed;
- canary heartbeat: **HEALTHY**;
- observed during activation summary: **509 total events**, **495 book events**, **3 trade events**;
- **0 gaps**, **0 subscription errors**;
- watchdog after canary: **HEALTHY**;
- watchdog canary check: **True**, heartbeat age ~**1.9 s** at capture;
- safety guardrails confirmed: **PUBLIC DATA ONLY / NO ACCOUNT / NO ORDERS / NO STRATEGY ACTION**.

This closes the concrete local continuous-process/heartbeat contract for the Kraken transport canary. The independent GitHub cloud path remains in place. Strategy coupling is still intentionally absent.

### V2R4 prep validation green after MINI-PC canary activation 2026-09-30

After activating the local continuous Kraken canary, the inactive V2R4 draft was revalidated without activating strategy behavior:
- explicit Python compile gate added for all V2R4 prep sources;
- V2R4 unit tests: PASS;
- live public Kraken WAIT-watcher smoke: PASS;
- broad Kraken EUR pre-candidate discovery smoke: PASS;
- GitHub workflow `V2R4 PR validation`: SUCCESS.

Draft-PR #8 remains **draft / prep-only / paper-only / not merged / not active**. The next promotion gate still requires the documented V2R3 evidence review and one small MINI-PC end-to-end paper smoke.

### Altrady relay deployed 2026-09-30

Autonomous infrastructure step completed after the Kraken canary activation:
- Supabase Edge Function `altrady-trigger-relay` deployed successfully;
- function status: **ACTIVE**, version 1;
- JWT verification is intentionally disabled because the function implements its own dedicated shared-token authentication for webhook ingress and MINI-PC poll/ack;
- no Altrady strategy coupling is active;
- no order path exists;
- remaining blocker is the dedicated `ALTRADY_WEBHOOK_TOKEN` secret, which must be configured securely before transport E2E can run.

The MINI-PC poller/task installer and transport CI remain prepared. User interaction is not needed again until the shared secret is actually configured.

