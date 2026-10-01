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
3. Supabase schlank als sekundäre State-/Ergebnisschicht. Der Archiv-Sync ist inzwischen E2E-verifiziert und wird nach erfolgreichem Paper-Runtime-Abschluss automatisch nachgezogen; Supabase bleibt fail-soft und keine Live-Abhängigkeit.
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
- **Arbeitsfluss ab 2026-10-01 verbindlich nachgeschärft:** Keine Zwischenfreigaben mehr für jeden Teilschritt. ChatGPT arbeitet bis zum nächsten echten physischen/Account-/Sicherheits-Gate selbstständig durch. Nach einer Nutzeraktion wird die Arbeit automatisch fortgesetzt, ohne dass ein erneutes „weiter“ nötig ist.
- Wenn ein Test nur Zeit braucht oder Evidenz reifen muss, wird diese Wartezeit für andere unabhängige Runbook-/Backlog-Punkte genutzt. Nutzeraktionen werden nach Möglichkeit als gebündelter Sammeltest vorbereitet.
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

### V2R4 MINI-PC preflight smoke prepared 2026-09-30

A single isolated local smoke bundle is prepared as `tools/minipc-v2r4-preflight-smoke.ps1`.

It does not modify the active V2R3 series:
- verifies the already-running local Kraken canary is fresh/HEALTHY;
- fetches the V2R4 prep branch into a temporary Git worktree;
- compiles evaluator + V2R4 trigger/discovery modules;
- runs deterministic V2R4 tests;
- builds a harmless synthetic BTC/EUR WAIT trigger plan;
- runs the live public Kraken WAIT watcher once and verifies the receipt can only request `FRESH_PAPER_RECHECK_ONLY`;
- runs one broad live Kraken EUR pre-candidate discovery cycle using current public `AssetPairs`;
- removes the temporary worktree/evidence afterward.

Guardrails:
- paper/shadow only;
- no private Kraken account;
- no order endpoint;
- no strategy activation;
- no changes to V2R3 runtime state.

The script passes Windows PowerShell parse CI. Actual MINI-PC execution is the next local-only preflight evidence point.

### V2R4 exact Windows/MINI-PC-shaped preflight + live evaluator smoke 2026-09-30

Additional release-gate evidence completed without activating V2R4:
- exact `tools/minipc-v2r4-preflight-smoke.ps1` executed on Windows CI in a MINI-PC-shaped directory tree: **PASS**;
- isolated prep-branch worktree SHA tested: `6255fb12...` at that run;
- Kraken canary prerequisite: **HEALTHY**;
- synthetic deterministic WAIT receipt: **matched=True** with `FRESH_PAPER_RECHECK_ONLY`;
- live broad pre-candidate smoke observed **500 current online Kraken EUR pairs**;
- tradability contract: **LIVE PUBLIC KRAKEN ASSETPAIRS / NO STATIC BLACKLIST**;
- safety: **PAPER/SHADOW ONLY / NO ACCOUNT / NO ORDERS / NO REAL-MONEY ACTION**.

The actual V2R4 evaluator was then exercised once in an isolated GitHub smoke using:
- current public Kraken BTC/EUR ticker;
- the repository's existing `OPENAI_API_KEY` secret;
- a temporary V2R4 control/spec that was never persisted;
- actual evaluator code from the V2R4 prep branch.

First attempt exposed a real runtime-only prompt-format bug (literal braces in the structured `watch_conditions` schema). The branch was patched and a regression test added. Second attempt: **PASS**.
Observed paper result in that smoke: `REJECT`; no paper entry and no trigger plan were created, which is a valid safe outcome. `real_money_actions_enabled=false` remained enforced.

This materially reduces release risk, but does **not** yet prove the complete local trigger -> fresh evaluator recheck bridge. That final coupling remains a distinct gate before a real V2R4 paper-series activation.

### V2R4 local trigger -> fresh recheck bridge prepared 2026-09-30

The final timing-critical bridge is now implemented on the inactive V2R4 prep branch:
- `paper_evaluator/v2r4_local_recheck.py`;
- accepts only a matched paper-only trigger receipt with `next_action=FRESH_PAPER_RECHECK_ONLY`;
- candidate/receipt identity and pair must match;
- expired/unmatched/unsafe trigger actions fail closed;
- fresh public Kraken ticker/context is re-fetched before the evaluator call;
- no private Kraken credential and no order endpoint are present;
- output is a local paper-only recheck record; BUY, if ever returned, is still only a simulated paper entry;
- WAIT may emit a new bounded structured trigger plan.

Validation status:
- V2R4 complete unit set: PASS;
- Windows/MINI-PC-shaped preflight: PASS with 22 tests;
- live public Kraken WAIT watcher: PASS;
- current online Kraken EUR universe observed in smoke: 500 pairs;
- actual isolated V2R4 evaluator call: PASS after fixing a runtime-only prompt formatting defect.

Still required before V2R4 activation:
- secret provisioning for the chosen local evaluator/transport path;
- one actual MINI-PC trigger -> fresh recheck E2E proof with timestamps and heartbeat;
- no V2R4 activation until that proof passes.

### Exact V2R4 trigger→fresh-recheck gate validated on Windows CI 2026-09-30

The exact local gate intended for the MINI-PC is now implemented as:
- `tools/minipc-v2r4-trigger-recheck-e2e.ps1`.

The script:
- requires a fresh local Kraken canary heartbeat;
- fetches the inactive V2R4 prep branch into an isolated Git worktree;
- builds a synthetic canonical paper candidate;
- creates a deterministic WAIT trigger plan;
- matches that trigger against live public Kraken data;
- writes a real trigger receipt;
- immediately passes that receipt into `v2r4_local_recheck.py`;
- re-fetches fresh Kraken execution/context data;
- performs one actual OpenAI paper evaluator call;
- verifies paper-only/no-order flags and trigger→recheck timestamps;
- removes the temporary isolated test tree afterward.

The **exact PowerShell gate** was executed successfully on `windows-latest` with the real model/API path:
- prep branch SHA: `0e6a64629554f500c4aef8c2a4d4c76c65ea23ff`;
- Kraken canary: HEALTHY;
- trigger → local fresh-recheck start: **0.256 s**;
- evaluator recheck runtime: **12.232 s**;
- decision: REJECT in that harmless synthetic case;
- order API: false;
- real-money action: false;
- result: **PASS**.

This proves the code/runtime shape on Windows. It does **not** replace the required one-time proof on the actual physical MINI-PC.

Additional V2R4 runtime defect caught and fixed before local activation:
- proposed adaptive sizing had no executable top-level `scout_notional_eur` / `stage2_notional_eur` fields although the evaluator/recheck runtime requires them;
- V2R4 now explicitly uses **75 EUR + 75 EUR** as the executable default until a separately validated setup-quality sizing mapper exists;
- dedicated runtime-compatibility tests were added and the Windows preflight is green.

Remaining V2R4 local activation blockers:
1. provision a dedicated local OpenAI API key securely in `Trading\Secrets\openai-api-key.txt`;
2. run the exact trigger→fresh-recheck gate once on the actual MINI-PC;
3. configure the Altrady shared relay token and run the transport E2E smoke;
4. only then decide whether to start a separate V2R4 paper series. No merge/activation has occurred.

### Recurring Supabase archive sync hardened 2026-09-30

The archive path was rechecked after additional V2R3 paper activity:
- repository audit at sync time: **570 active-series candidate rows**, **0 trade rows**;
- GitHub archive sync run #6: **SUCCESS**;
- direct Supabase verification after the run: **570 V2R3 candidate outcomes**, **573 candidate outcomes total**, **0 trade results**;
- subsequent reconciliation run #7 successfully archived **578 V2R3 candidate outcomes**, confirming catch-up after further Paper Runtime activity;
- the prior 551-row archive was therefore successfully brought current.

Root cause of the earlier staleness:
- paper state is persisted by GitHub Actions using `GITHUB_TOKEN`;
- GitHub intentionally does not trigger ordinary downstream `push` workflows from those bot pushes;
- therefore a push-only archive workflow could remain stale despite successful paper persistence.

Fix:
- `supabase-sync.yml` keeps push/manual triggers and an opportunistic `workflow_run` hook for successful `Paper runtime evaluator and lifecycle` completion;
- because the first post-change Paper Runtime completion did not itself produce an observable archive run, that hook is **not treated as the sole guarantee**;
- an independent reconciliation schedule now runs at minute **:07 and :37** each hour;
- the archive remains fail-soft/secondary and can safely lag without blocking scanner or evaluator.

This closes the Supabase persistence gap as an infrastructure issue; it does not change strategy behavior.

### Canonical remaining local core gate prepared 2026-09-30

To minimize further user interaction, the remaining physical V2R4 + secret-preparation steps are now bundled in:

`tools/minipc-local-core-gate.ps1`

Sequence:
1. run the isolated V2R4 MINI-PC preflight against the real local Kraken canary/runtime;
2. securely provision a local OpenAI API key only if `Trading\Secrets\openai-api-key.txt` is still missing (hidden input, restricted ACL, never printed);
3. run the exact physical trigger -> fresh paper recheck E2E through the real evaluator;
4. only if all prior steps pass, prepare the Altrady relay token locally and copy it to the Windows clipboard without printing it.

Safety:
- no exchange account access;
- no order API;
- no real-money action;
- V2R4 remains prep/paper-only;
- Altrady token is generated only after the physical V2R4 E2E passes.

The old `tools/minipc-next-user-step.ps1` now delegates to this canonical gate to avoid two competing local sequences.

Windows PowerShell parsing is green. The only unavoidable user inputs are the actual local OpenAI API key (if not already provisioned) and the later one-time Supabase Edge Function secret entry for `ALTRADY_WEBHOOK_TOKEN`.


### Physical V2R4 core gate + Altrady transport E2E passed 2026-09-30

Actual MINI-PC evidence:
- secure local OpenAI evaluator key provisioned with restricted ACL and authenticated successfully;
- physical V2R4 trigger -> fresh paper recheck E2E: **PASS**;
- observed trigger -> recheck start: **0.228 s**;
- evaluator recheck runtime: **12.348 s**;
- synthetic decision in the harmless BTC/EUR case: **WAIT**;
- next WAIT trigger plan emitted: **true**;
- paper entry simulated: **false**;
- safety remained **PAPER ONLY / PUBLIC KRAKEN / NO EXCHANGE ACCOUNT / NO ORDER API / NO REAL-MONEY ACTION**.

Altrady transport activation:
- dedicated relay token stored locally and as Supabase Edge Function secret `ALTRADY_WEBHOOK_TOKEN`;
- `CryptoMiniPC-AltradyTrigger` installed and running as the local transport poller;
- heartbeat: **HEALTHY**;
- synthetic relay -> MINI-PC -> ack smoke: **PASS**;
- smoke evidence: **1 event received / 1 acknowledged**;
- local Watchdog: **HEALTHY**, Altrady check **true**;
- strategy action remains **NONE_TRANSPORT_ONLY**.

Interpretation:
- the transport and fresh-recheck infrastructure gates are closed;
- Altrady is not yet a live strategy trigger: real Altrady alert/webhook configuration, measured live latency and explicit strategy/Fresh-Recheck coupling remain separate open steps;
- V2R4 itself remains a separate paper-activation decision and has not been silently promoted to live/real-money execution.

### Current continuation checkpoint — real Altrady alert transport verified 2026-10-01

The previously configured one-shot BTC/XBT Price Alert fired after the local 600-second listener had already timed out.

Verified evidence:
- Altrady event time: 2026-09-30 22:49:22 UTC.
- Supabase relay received the event at 2026-09-30 22:49:24.244187 UTC.
- The MINI-PC poller acknowledged it at 2026-09-30 22:49:27.541 UTC.
- Supabase logs show HTTP 200 for both the real incoming webhook POST and the later MINI-PC acknowledgement POST.
- Event -> relay was about 2.244 seconds.
- Relay -> MINI-PC acknowledgement was about 3.297 seconds.
- Event -> acknowledgement was about 5.541 seconds.
- Relay event: exchange Kraken, symbol XXBTZUSD, marker LIVE_ALTRADY_TIME_TEST.
- The transport remains strategy-neutral: NONE_TRANSPORT_ONLY.

Conclusion:
- **Altrady -> Supabase relay -> MINI-PC -> acknowledgement is now REAL ALERT E2E VERIFIED.**
- The earlier listener timeout was only an observation-window timeout, not a transport failure.
- Do not repeat this proof unless a later change invalidates it.
- Time Alerts remain unavailable on the current Altrady plan; the verified proof used an ordinary one-shot Price Alert.
- A dedicated helper mode LivePriceTestPayload is available for any future Price-Alert regression test.

When the user says **Einrichtung weiterführen**, the next main setup item is the broad continuous Kraken realtime watcher across the relevant Kraken-EUR universe. The current BTC/EUR canary remains only a transport/health canary. Altrady stays an additional independent trigger.

Additional read-only audit:
- Supabase Edge Function altrady-trigger-relay remains ACTIVE, version 2.
- Supabase performance advisor: no findings.
- Supabase security advisor: only the four known informational RLS-without-policy findings; these tables are intentionally backend-only/fail-closed at this stage.

### Broad Kraken-EUR realtime feed prepared 2026-10-01

The next setup item after the verified Altrady transport is now prepared in the canonical repository without activating any strategy:

- \`tools/minipc-kraken-universe-feed.py\`:
  - uses current public Kraken \`AssetPairs\` as the online Spot-EUR universe gate;
  - consumes Kraken WebSocket v2 \`ticker\` as the event-driven broad market feed;
  - persists only a compact latest-per-pair snapshot plus heartbeat, not an unbounded raw tick archive;
  - has no account credentials, evaluator, order path or real-money action.
- \`tools/install-minipc-kraken-universe-feed.ps1\`:
  - first runs a bounded live proof;
  - requires at least 80% universe snapshot coverage and zero subscription errors;
  - only after that proof passes registers the SYSTEM startup task \`CryptoMiniPC-KrakenUniverse\`.
- \`tools/uninstall-minipc-kraken-universe-feed.ps1\` is the explicit rollback.
- \`minipc-watchdog.ps1\` now monitors the feed heartbeat when the task is installed.
- Windows CI parse/smoke for the new Python/PowerShell tooling is green.
- Existing BTC/EUR canary remains independent and is not replaced.
- Altrady remains an additional independent trigger; no strategy coupling is introduced here.

**Physical activation verified 2026-10-01:**
- bounded live Kraken-EUR WebSocket proof passed on the actual MINI-PC;
- persistent SYSTEM startup task `CryptoMiniPC-KrakenUniverse` installed;
- status: **HEALTHY**;
- current online EUR pairs: **500 / 500 observed (100.0% coverage)**;
- ticker rows at proof: **502**; live updates observed: **2**;
- subscription errors: **0**;
- connections: **1**; reconnects: **0**;
- compact heartbeat and latest-snapshot files are being written under `Trading\State`;
- safety remained **PUBLIC DATA ONLY / NO ACCOUNT / NO ORDERS / NO STRATEGY ACTION**.

This closes the broad Kraken-EUR realtime transport activation gate. The next infrastructure gate is restart/recovery verification for the full active local stack before any strategy activation.

### Full local runtime recovery gate prepared 2026-10-01

After the broad Kraken-EUR feed activation, a dedicated read-only restart/recovery verification bundle was added and Windows-CI verified:

- `tools/minipc-runtime-recovery-gate.ps1`
- checks all six expected local CryptoMiniPC tasks;
- verifies fresh heartbeats for Kraken BTC/EUR canary, broad Kraken-EUR universe feed and Altrady transport;
- verifies local watchdog state and public Kraken HTTPS reachability;
- writes a compact JSON report under `Trading\Logs`;
- no configuration change, no process restart, no strategy mutation and no real-money action.

**Physical restart/recovery verification passed 2026-10-01:**
- gate status: **PASS** about 1.5 minutes after boot;
- expected local tasks: **6/6**;
- Kraken BTC/EUR canary: **HEALTHY**, heartbeat age ~1.3 s, 975 events;
- broad Kraken-EUR universe: **HEALTHY**, **500/500**, **100.0% coverage**, 0 subscription errors;
- Altrady transport: **HEALTHY**, heartbeat age ~8.7 s;
- local watchdog: **HEALTHY**;
- public Kraken HTTPS: **200**;
- issues: **none**; notes: **none**;
- guardrails remained read-only/no config change/no strategy change/no real-money action.

This closes the controlled Windows restart/recovery gate for the currently active local transport/watchdog stack.

### Controlled Internet-loss recovery gate prepared 2026-10-01

After the successful full Windows restart recovery, the next resilience check is prepared and Windows-CI green:

- `tools/minipc-internet-recovery-gate.ps1`
- temporarily disables only the active default-route network adapter for a short bounded window;
- arms an independent SYSTEM one-shot safety task **before** disabling the adapter so it is automatically re-enabled even if the interactive/RDP session drops;
- verifies that the outage is actually observed;
- then verifies recovery of Kraken HTTPS, BTC/EUR canary, broad Kraken-EUR universe feed, Altrady heartbeat and local watchdog;
- strategy remains uncoupled, so no candidate/order replay can occur in this test;
- no real-money action.

Recommended execution is from the MINI-PC's local console/monitor because an RDP session may disconnect briefly. The network adapter is automatically re-enabled by both the primary script and the pre-armed safety task.

### Controlled Internet-loss recovery verified 2026-10-01

Actual MINI-PC result:
- gate status: **PASS**;
- active adapter: Ethernet; disable was observed and automatic recovery succeeded;
- Kraken outage probe failed during the offline window as expected;
- Kraken HTTPS recovered to **HTTP 200**;
- BTC/EUR canary recovered **HEALTHY**, events advanced **5744 -> 5781**, connection count **1 -> 2**;
- broad Kraken-EUR feed recovered with **500/500 pairs, 100.0% coverage**, ticker rows advanced **1659 -> 1667**; reconnect counter **0 -> 6** during the bounded outage/recovery window;
- Altrady transport recovered **HEALTHY** (heartbeat age ~6.2 s);
- local watchdog: **HEALTHY**;
- issues: **none**; notes: **none**;
- safety remained transport-only; strategy not coupled; no real-money action.

This closes the controlled Internet-loss/reconnect transport gate. Because no strategy runtime is coupled yet, stale candidate replay is not applicable at this stage; that behavior remains a separate strategy-runtime gate before any later live execution.

### V2R4 WS-driven shadow layer prepared 2026-10-01

After the transport/recovery gates passed, the next timing layer was prepared without activating V2R4 decisions:

- Draft-PR #8 now contains `paper_evaluator/v2r4_ws_shadow_watcher.py`;
- it consumes the already-running local `kraken-eur-ticker-latest.json` instead of polling broad REST ticker data;
- it builds rolling point-in-time 10m/30m/1h/3h/6h/12h observations;
- it rejects stale global input, ignores duplicate/stale pair updates and suppresses one trigger cycle after a material feed gap;
- it writes a rotating timing ledger and compact bounded-persistence state;
- it never invokes the evaluator and cannot place orders;
- focused unit tests + bounded synthetic runtime CI are **PASS**;
- Windows parse/smoke for the physical smoke, installer and rollback scripts is **PASS**.

Prepared local tooling on `main`:
- `tools/minipc-v2r4-ws-shadow-smoke.ps1`
- `tools/install-minipc-v2r4-ws-shadow.ps1`
- `tools/uninstall-minipc-v2r4-ws-shadow.ps1`
- local watchdog automatically checks the shadow heartbeat once the task exists.

**Physical activation verified 2026-10-01:**
- bounded physical WS-shadow smoke: **PASS**;
- Kraken EUR snapshot: **500/500**;
- fresh snapshots consumed during smoke: **13**; duplicates skipped: **18**;
- stale inputs: **0**; gap recoveries during smoke: **0**;
- healthy timing-ledger cycles: **13**;
- source age: average **0.706 s**, maximum **2.175 s**;
- shadow discovery events during the short smoke: **0** (valid; observation window only);
- persistent startup task `CryptoMiniPC-V2R4WSShadow`: **HEALTHY**;
- pinned inactive V2R4 prep commit: `ab78c9abaec940c35c96c179b6a16904c5192ad3`;
- initial persistent heartbeat source age: **~0.409 s**;
- V2R3 remained unchanged; no evaluator/account/order/real-money path was enabled.

This closes the physical WS-shadow activation gate. The shadow layer should now run prospectively and collect feed→discovery timing plus stale/dedup/recovery evidence before any separate V2R4 paper-series activation decision.

### V2R4 shadow resilience bundle prepared 2026-10-01

Because the WS-shadow task was installed only after the earlier generic restart/Internet tests, the **shadow process itself** still needs explicit recovery evidence.

Prepared and Windows-CI verified:
- `tools/minipc-runtime-recovery-gate.ps1` now includes the 7th startup task `CryptoMiniPC-V2R4WSShadow` plus its fresh heartbeat/guardrails;
- `tools/minipc-internet-recovery-gate.ps1` now verifies that the shadow advances again after a controlled network outage while remaining `NONE_SHADOW_ONLY`;
- `tools/minipc-v2r4-shadow-resilience-bundle.ps1` arms a **one-shot** SYSTEM post-boot verifier and restarts Windows;
- the one-shot task unregisters itself **before** any disruptive test, waits for startup stabilization, runs the full restart gate, then the guarded Internet-outage gate, then a read-only 6h shadow evidence summary;
- it writes a compact final text report to `Trading\Logs\minipc-v2r4-shadow-resilience-latest.txt`;
- safety remains: V2R3 unchanged / no evaluator / no account / no orders / no real-money action.

**Next physical MINI-PC action:** pull `main` and run the resilience bundle once from elevated PowerShell. After Windows restarts, wait about four minutes before viewing the generated summary. No manual network toggling is required.

### First prospective V2R4 WS-shadow evidence snapshot 2026-10-01

Read-only 6h MINI-PC evidence after the shadow runtime was activated:
- heartbeat: **HEALTHY**;
- cycles: **321**;
- shadow discovery events: **9**;
- triggered-pair observations: **15**;
- cycle status counts: **318 HEALTHY / 3 STALE_INPUT**;
- source age: median **0.502 s**, p90 **0.94 s**, maximum **40.501 s**;
- event feed→shadow latency: median **~2933.9 ms**, p90/max **~3187.5 ms**;
- one gap-suppressed recovery cycle and max recovery epoch **1**, matching the deliberate reconnect exercise;
- observed event pairs included MOVR/EUR, PROMPT/EUR, TRAC/EUR, QNT/EUR, CHEX/EUR, KULA/EUR, NOS/EUR, ORCA/EUR and SYN/EUR;
- observed trigger reason in this first sample: **FAST_10M** (9 events);
- safety remained read-only shadow-only with no evaluator/order/real-money action.

The large cumulative stale-pair observation count is a **per-pair freshness diagnostic**, not a global feed outage count: illiquid pairs whose ticker row has not updated recently are deliberately ignored until a fresh market update arrives. Global source freshness remained sub-second at median/p90 except during the deliberate outage/recovery window.

Formal overall resilience bundle status is recorded separately from the evidence summary and must be checked from the compact JSON status before closing the shadow restart/Internet-recovery gate.

### V2R4 WS-shadow restart / Internet resilience verified 2026-10-01

Physical MINI-PC compact result:
- overall status: **PASS**;
- runtime recovery gate: **exit 0**;
- controlled Internet recovery gate: **exit 0**;
- shadow evidence summary: **exit 0**;
- issues: **none**;
- safety guardrails remained **SHADOW ONLY / V2R3 UNCHANGED / NO EVALUATOR / NO ORDERS / NO REAL-MONEY ACTION**.

This closes the explicit restart + Internet-recovery gate for the active `CryptoMiniPC-V2R4WSShadow` process itself.

### Prospective V2R4 shadow outcome tracker prepared 2026-10-01

After the shadow restart/Internet resilience gate passed, the next evidence layer was prepared without activating V2R4 paper decisions:

- `tools/v2r4-ws-shadow-outcome-tracker.py` watches only **new** WS-shadow discovery events from the moment the tracker starts;
- older events are deliberately not backfilled from the current price, avoiding invalid point-in-time evidence;
- prospective horizons: **5m / 15m / 30m / 1h / 3h / 6h**;
- records point return, running **MFE / MAE**, sample time and sampling lag;
- uses only the already-running local Kraken latest snapshot;
- stale per-pair prices are not used for outcome samples;
- completed outcomes are persisted separately and the tracker state remains bounded;
- persistent task installer/rollback prepared:
  - `tools/install-minipc-v2r4-shadow-outcomes.ps1`
  - `tools/uninstall-minipc-v2r4-shadow-outcomes.ps1`
- local watchdog and restart-recovery tooling now detect the tracker automatically once installed;
- Python/PowerShell/synthetic Windows CI: **PASS**.

Safety remains evidence-only: no evaluator, no exchange account, no order API and no real-money action.

**Physical activation verified 2026-10-01:**
- installer synthetic smoke: **PASS**;
- persistent task `CryptoMiniPC-V2R4ShadowOutcomes`: **HEALTHY**;
- active prospective events at activation: **0**;
- enrolled prospective events at activation: **0**;
- pre-tracker historical events deliberately ignored for outcome tracking: **18**;
- horizons armed: **5m / 15m / 30m / 1h / 3h / 6h + running MFE/MAE**;
- safety remained **EVIDENCE ONLY / NO EVALUATOR / NO ACCOUNT / NO ORDERS / NO REAL-MONEY ACTION**.

The tracker is now waiting for genuinely new WS-shadow events. No retrospective price backfill is allowed for the 18 pre-tracker events.

### V2R4 shadow cloud archive prepared 2026-10-01

To make future shadow/outcome analysis available without repeated MINI-PC screenshots:

- Supabase table `public.v2r4_shadow_evidence` created with RLS enabled and **no client policies**;
- authenticated Edge Function `v2r4-shadow-evidence-relay` deployed ACTIVE;
- function accepts only the already-provisioned shared project relay token and performs server-side upserts through the service role;
- no Supabase service-role/secret key is stored on the MINI-PC;
- local fail-soft sync prepared as `tools/v2r4-shadow-cloud-sync.py`;
- sync uploads only shadow discovery/evidence payloads and completed outcome payloads;
- local state makes uploads idempotent and only re-sends when an outcome becomes available;
- installer/rollback prepared:
  - `tools/install-minipc-v2r4-shadow-cloud-sync.ps1`
  - `tools/uninstall-minipc-v2r4-shadow-cloud-sync.ps1`;
- Watchdog and runtime-recovery tooling detect the sync automatically once installed;
- RLS-with-no-policy advisor result is intentional for this server-only archive path.

**Physical activation verified 2026-10-01:**
- authenticated one-shot archive smoke: **PASS**;
- persistent task `CryptoMiniPC-V2R4ShadowCloudSync`: **HEALTHY**;
- initial upload: **23 records** in **1 batch**;
- persistent heartbeat immediately after install: **pending=0 / uploaded_this_cycle=0**;
- independent Supabase verification: **23 rows** present in `public.v2r4_shadow_evidence`;
- no outcome payloads yet at activation time, as expected because the prospective outcome tracker had only just started;
- secret was not printed;
- safety remained **ARCHIVE ONLY / NO EVALUATOR / NO ACCOUNT / NO ORDERS / NO REAL-MONEY ACTION**.

This closes the MINI-PC shadow cloud-archive activation gate. Future new shadow events and their eventual outcome payloads can now be inspected centrally without repeated manual file transfer from the MINI-PC.

### Slack iPhone action-push E2E verified 2026-10-01

The intended low-noise notification path is now physically verified again:

- channel `#krypto-signale` remains configured on the iPhone for **Nur Erwähnungen**;
- mobile Slack notifications are enabled and mobile delivery is set to **Immer**;
- normal channel messages are intentionally not sufficient for a push;
- the project action-push path uses GitHub Issue #1 -> `Slack action push relay` -> Slack incoming webhook -> real Slack mention `<@U0C39EDQ1H8>`;
- the relay run completed **SUCCESS** and Slack returned **HTTP 200 / ok**;
- the resulting webhook/bot message produced a real iPhone push for the user;
- therefore future push logic remains: raw candidates silent; only explicitly actionable/error/completion messages receive the real Slack mention.

A ChatGPT/Slack-connector message sent as the user's own Slack identity is **not** a valid push-path test and must not be used as evidence.

### Remote MINI-PC status / independent cloud deadman prepared 2026-10-01

After GitHub/API/Slack and the V2R4 evidence paths were verified, the next low-noise operations layer was prepared:

- Supabase table `public.minipc_status_current` stores only the latest compact watchdog snapshot per node;
- authenticated Edge Function `minipc-status-relay` is ACTIVE and accepts only the existing project relay token;
- no Supabase admin/service-role key is placed on the MINI-PC;
- local fail-soft sync prepared as `tools/minipc-status-sync.py`;
- installer/rollback prepared:
  - `tools/install-minipc-status-sync.ps1`
  - `tools/uninstall-minipc-status-sync.ps1`;
- local watchdog and runtime-recovery gate automatically include the status-sync heartbeat once installed;
- Windows parse/compile tooling is green.

An independent cloud deadman was also prepared as `.github/workflows/minipc-cloud-health-watch.yml`:
- runs outside the MINI-PC every 15 minutes;
- does nothing until a real remote MINI-PC status row exists;
- alerts Slack with a real `@Hoffis` mention only for **CRITICAL** state or **>20 min stale** remote status;
- repeated outage alerts are rate-limited to at most once per 2 hours for the same condition;
- sends one recovery push when the status returns;
- WARNING does not trigger push noise;
- no trading action, evaluator or order path.

This makes the cloud layer a genuine independent deadman: if the MINI-PC itself loses power/network, the cloud workflow can still detect the stale last-seen timestamp and push the user.

**Next physical MINI-PC action:** run the status-sync installer once from elevated PowerShell. The first authenticated upload is performed before the persistent task is registered.

### Legacy scanner timing archive activated 2026-10-01

To make the Kraken-native WS shadow vs. legacy GitHub scanner timing comparison measurable without manual log inspection:

- Supabase table `public.scanner_detection_evidence` is active;
- `.github/workflows/scanner-timing-sync.yml` archives canonical handoff timestamps after successful early-sensor runs and on a 30-minute reconciliation schedule;
- canonical nested timing fields are used:
  - `timing.candidate_detected_at_utc`
  - `timing.handoff_written_at_utc`
  - `source_scanner_run_id`
  - scanner score/rank from `scanner_candidate`;
- first successful archive contained **854 scanner detection records** covering 2026-09-27 21:08:25 UTC through 2026-10-01 07:18:30 UTC;
- Supabase view `public.v2r4_shadow_scanner_timing` provides a read-only comparison aid between WS-shadow event times and the nearest same-pair scanner detections before/after within ±6h;
- current early sample: 23 shadow events, 3 scanner detections afterwards within 6h, 8 scanner detections beforehand within 6h; this is **timing evidence only**, not proof that matched rows represent the identical market impulse.

The large Paper archive sync was also hardened after one PostgREST statement timeout: upserts are now bounded into small batches with retry only for transient 429/5xx/timeout failures. The repaired archive run completed SUCCESS.

### Remote MINI-PC status activated; stale read-only runtimes detected 2026-10-01

Physical MINI-PC status-sync activation:
- `CryptoMiniPC-StatusSync`: **HEALTHY**;
- authenticated one-shot upload succeeded;
- persistent heartbeat: **HEALTHY** on node `MINI-PC`;
- independent Supabase read verified the remote row in `public.minipc_status_current`;
- transport/sync path itself is therefore **E2E VERIFIED**.

The first centrally visible local watchdog state was **WARNING**, not because of network, disk, backup, Kraken transport, Altrady or cloud archive:
- broad Kraken universe: HEALTHY, 500/500;
- Kraken canary: HEALTHY;
- Altrady transport: HEALTHY;
- shadow cloud archive: HEALTHY;
- backup fresh and local disk healthy;
- warning sources were specifically:
  - `CryptoMiniPC-V2R4WSShadow`: stale heartbeat (~34 min old at observation);
  - `CryptoMiniPC-V2R4ShadowOutcomes`: stale heartbeat (~9.6 min old) with 5 active prospective events.

This is useful evidence: the new remote status path surfaced a genuine local process-liveness gap that the existing Task Scheduler restart-on-failure settings had not recovered automatically.

Remediation prepared:
- `tools/minipc-runtime-supervisor.ps1` monitors only the already-authorized read-only/runtime tasks;
- stale/stopped tasks are restarted in a bounded way;
- repeated restart attempts are rate-limited by a 10-minute backoff;
- `tools/install-minipc-runtime-supervisor.ps1` performs one immediate recovery, installs the supervisor every 2 minutes + startup, and refreshes the local watchdog;
- outcome tracking now explicitly marks active evidence as `tracker_gap_affected` after a >60s tracker-cycle gap so MFE/MAE continuity is never silently assumed;
- Windows PowerShell/Python smoke validation is green.

The supervisor is deliberately restricted to public-data/transport/shadow/evidence/status tasks. It cannot change strategy, invoke an evaluator, place orders or perform real-money actions.

**Next physical MINI-PC action:** pull `main` and install the runtime supervisor once. This should also recover the currently stale WS-shadow and outcome-tracker tasks and preserve the detected gap in evidence quality.

### MINI-PC runtime supervisor activated 2026-10-01

Physical installer result:
- supervisor status: **HEALTHY**;
- recovered tasks during this install: **none** (all monitored runtimes were healthy by the time of the successful installer run);
- local watchdog after recovery refresh: **HEALTHY**;
- persistent task `CryptoMiniPC-RuntimeSupervisor` installed;
- cadence: **every 2 minutes + at startup**;
- repeated restart attempts for the same task are limited to once per **10 minutes**;
- safety remained **READ-ONLY RUNTIMES ONLY / NO STRATEGY CHANGE / NO EVALUATOR / NO ORDERS / NO REAL-MONEY ACTION**.

The first installer attempt exposed a robustness bug where the installer assumed the supervisor report file existed even after an early supervisor failure. The supervisor/installer were hardened to always emit diagnostics before the successful activation.

Next validation gate: perform one controlled self-heal smoke against a non-strategy, idempotent read-only support task and prove that the supervisor restarts it without user intervention.

### Post-supervisor remote health confirmation 2026-10-01

After the successful supervisor installation, the next remote status-sync cycle independently reported:
- node `MINI-PC`: **HEALTHY**;
- issues: **none**.

This confirms that the earlier stale WS-shadow/outcome warnings cleared after the local recovery path stabilized.

A controlled self-heal smoke is now prepared as `tools/minipc-runtime-supervisor-selfheal-smoke.ps1`. It stops only the idempotent archive-only support task `CryptoMiniPC-V2R4ShadowCloudSync`, waits for the supervisor to recover it automatically, verifies heartbeat advancement and guardrails, then refreshes the local watchdog. Windows CI for the smoke is **PASS**.

### MINI-PC runtime supervisor self-heal verified 2026-10-01

Physical controlled self-heal smoke result:
- status: **PASS**;
- target support task: `CryptoMiniPC-V2R4ShadowCloudSync`;
- target task after test: **Running**;
- target heartbeat advanced after the forced stop;
- runtime supervisor: **HEALTHY**;
- local watchdog after recovery: **HEALTHY**;
- safety remained **ARCHIVE SUPPORT TASK ONLY / NO STRATEGY CHANGE / NO EVALUATOR / NO ORDERS / NO REAL-MONEY ACTION**.

This closes the bounded local self-heal gate for the MINI-PC runtime supervisor.

### Watchdog effectiveness smoke verified 2026-10-01

Physical MINI-PC result:
- overall: **HEALTHY**;
- Kraken canary: **OK**, fresh real WS event age ~2.3s;
- Kraken EUR universe: **OK**, fresh ticker age ~4.2s, 500/500 observed, 100% coverage;
- V2R4 WS shadow: **OK**, fresh upstream source age ~0.286s;
- V2R4 outcome tracker: **OK**, 12 active prospective events with fresh samples;
- runtime supervisor: **OK / HEALTHY**;
- remote status sync: **OK / HEALTHY**;
- issues: **none**.

This closes the "green but ineffective" gate: health now depends on fresh underlying market/event flow, not merely on a running process or recently written heartbeat.

### Explicit health-state taxonomy + daily 10:00 brief prepared 2026-10-01

After the physical effectiveness smoke passed, the operations layer was extended further:

- local watchdog now emits a separate operational `health_state` in addition to coarse HEALTHY/WARNING/CRITICAL;
- supported states:
  - `OK`
  - `WAITING_NO_DATA`
  - `FEED_STALE`
  - `API_DISCONNECTED`
  - `BACKLOG_STUCK`
  - `DEGRADED`
  - `STOPPED`;
- state reason codes are persisted in the local watchdog payload and therefore propagate through the already active remote status sync;
- a timezone-aware GitHub workflow `.github/workflows/minipc-daily-status.yml` is prepared for the very short daily **10:00 Europe/Berlin** system brief;
- because GitHub cron is UTC-only, the workflow runs hourly and gates on the local Europe/Berlin hour, preserving 10:00 across CET/CEST;
- report data is based on real remote MINI-PC health plus Kraken-universe, WS-shadow, outcome-tracker, supervisor and evidence counts;
- healthy daily reports post to Slack **without** an `@Hoffis` mention (therefore no iPhone push with the current channel setting);
- degraded/problem states post with a real `@Hoffis` mention and therefore do push;
- reports are also persisted to `public.minipc_daily_status` for later status-page/history use;
- push-triggered dry-run rendered the actual live data successfully without sending a duplicate Slack message.

One local pull + effectiveness smoke remains to activate/verify the new operational taxonomy on the MINI-PC itself.

### Health taxonomy locally verified; Altrady timing view prepared 2026-10-01

Physical MINI-PC effectiveness result after the taxonomy pull:
- overall: **HEALTHY**;
- operational state: **OK**;
- state reasons: **none**;
- Kraken canary/universe, WS-shadow, outcome tracker, runtime supervisor and status sync all reported OK;
- issues: **none**.

This closes the local operational-state taxonomy activation gate.

For the remaining P3 timing comparison, Supabase now also exposes `public.altrady_transport_timing`:
- derives relay→MINI-PC transport latency directly from the existing authenticated Altrady relay table;
- current evidence contains 2 consumed transport-proof events;
- observed relay→MINI-PC latency sample: min **0.335s**, max **3.297s**, average **1.816s**;
- this is transport evidence only and is not yet a statistically meaningful Altrady-vs-Kraken-vs-scanner performance conclusion.

### Secret hygiene audit prepared 2026-10-01

This parallel hardening step does not depend on V2R4 evidence and is safe to perform while the realtime paths collect data:

- `tools/minipc-secret-hygiene-audit.ps1` is read-only;
- it never prints secret values;
- checks tracked repository files for live Slack/Supabase/private-key patterns and forbidden key file types;
- checks local `Trading\Logs` / `Trading\State` for accidentally persisted live-secret patterns while reporting only filenames;
- checks that `Trading\Secrets` is outside the repository and flags obviously broad Everyone/Guests ACLs;
- current repository-side search found no obvious live Slack webhook, Supabase secret-key or private-key material;
- Windows CI parse validation: **PASS**.

The local MINI-PC audit remains one physical gate before later self-hosted-runner/private-account work.

### 2026-10-01 — session handoff after unexpected LAN RDP loss

Current continuation point is preserved explicitly:

- last completed physical gate: health taxonomy/effectiveness smoke = **HEALTHY / Operational state OK / reasons none**;
- next intended parallel task: run the read-only `tools/minipc-secret-hygiene-audit.ps1`;
- before that audit could be run, the existing internal Windows RDP session to the MINI-PC dropped and reconnect attempts failed with the generic Windows Remote Desktop unavailable error;
- the notebook remained online, so the wider LAN/internet path was still available, but this does **not** yet distinguish MINI-PC power/NIC/IP/RDP-service failure;
- last centrally observed MINI-PC remote status before troubleshooting was at 2026-10-01 08:14:27 UTC (10:14:27 Europe/Berlin), i.e. shortly before the RDP failure;
- do not skip ahead to the secret audit until local reachability/RDP is restored or the outage is classified;
- external WireGuard/RDP testing and drive D remain intentionally deferred to final Phase H.

**Resume keyword:** continue MINI-PC setup after RDP recovery → first restore/diagnose LAN reachability, then run the pending secret-hygiene audit.

### 2026-10-01 — unexpected MINI-PC outage root cause resolved

The internal RDP outage was traced to a **physical power interruption**:
- the IEC mains connector on the MINI-PC power supply was not seated correctly;
- power to the MINI-PC was therefore interrupted;
- the connector was reseated manually and power restored;
- RDP/local operation returned afterwards.

This confirms the earlier simultaneous loss of RDP reachability and remote-status updates was caused by loss of power, not by the LAN, RDP service, firewall, or the MINI-PC software stack.

Resume point remains unchanged: continue with the pending read-only `tools/minipc-secret-hygiene-audit.ps1` once the post-boot services have settled.

### MINI-PC secret hygiene audit verified 2026-10-01

Physical read-only audit result:
- status: **HEALTHY**;
- critical findings: **0**;
- warnings: **0**;
- findings: **none**;
- audit did not print any secret values;
- no files were changed, no credentials rotated, and no network login was performed.

This closes the local secret-hygiene gate before any later private-account/self-hosted-runner work.

### Paper runtime reconciliation audit CI validated 2026-10-01

The read-only `tools/paper-runtime-reconciliation-audit.py` passed Windows tool-smoke CI. It is ready for one physical/local run against the current repository state to verify restart/replay/TTL consistency after the earlier power interruption.

### Reconciliation audit false-positive identified 2026-10-01

The first physical `paper-runtime-reconciliation-audit.py` run printed many `CRITICAL HANDOFF_ID_MISMATCH` findings. These were traced to **historical pre-series handoffs from 2026-09-26**, which legitimately predate the later canonical `candidate_id` field.

The active paper series starts at **2026-09-28 17:52 UTC**. Repository-level reconciliation performed after the failed audit showed:
- total handoff files: 1036;
- historical pre-series handoffs: **328**;
- active-series handoffs: **708**;
- active-series handoffs without matching decision file: **0**;
- revalidation files without matching decision file: **0**;
- the apparent identity failures shown in the physical audit were therefore legacy-schema false positives, not evidence of active-series replay corruption.

The audit implementation must be revised so it filters pre-series diagnostic handoffs before enforcing the canonical candidate identity contract. Until then, the original audit result must not be treated as a real runtime failure.

### Real power-loss fallback evidence 2026-10-01

The accidental MINI-PC power interruption provided a real independence test:
- local MINI-PC/RDP/status-sync became unavailable;
- hosted GitHub `Kraken EUR early sensor` runs continued successfully during the outage (including runs started around 08:21 UTC and 08:38 UTC);
- hosted `Paper runtime evaluator and lifecycle` also continued successfully during the outage;
- after power restoration, the MINI-PC remote status resumed and cloud health returned to a fresh state.

This is practical evidence that the hosted GitHub path remains an independent fallback and the system is not single-trigger-dependent on MINI-PC or Altrady.

### Reconciliation audit corrected and repository-verified 2026-10-01

The false-positive legacy-schema problem was fixed:
- historical pre-series handoffs are filtered before canonical candidate-ID validation;
- paper decisions and revalidations are filtered to the active series before reconciliation checks;
- one-time verification against current `main` completed successfully.

Verification result:
- status: **HEALTHY**;
- active series: `PAPER-V2R3-FINAL-20260928T1752Z`;
- active-series handoffs: **710**;
- active-series decisions: **708**;
- active-series revalidations: **642**;
- historical pre-series handoffs ignored: **328**;
- fresh unprocessed handoffs: **2**;
- stale unprocessed handoffs: **0**;
- due WAIT revalidations: **0**;
- critical findings: **0**;
- warnings: **0**.

The two fresh unprocessed handoffs are normal in-flight candidates, not replay/stale artifacts.

One final local MINI-PC rerun of the corrected audit remains as the physical proof before closing the restart/reconciliation gate.

### Autonomous post-outage hardening completed 2026-10-01

While the user was not needed, the following were completed:
- corrected the reconciliation audit's legacy/pre-series false positives;
- verified corrected reconciliation against current `main`: **HEALTHY**, 710 active handoffs, 708 decisions, 642 revalidations, 2 fresh in-flight candidates, 0 stale, 0 overdue WAIT, 0 critical/warning;
- removed temporary one-time patch/verification workflows after successful use;
- used the real power outage as evidence that hosted GitHub scanner/evaluator paths remain independent of MINI-PC/Altrady;
- refined the outcome-tracker watchdog so individual illiquid pairs with temporarily old samples do not incorrectly mark the entire tracker/feed stale when other active outcomes are sampling freshly; core Kraken/WS freshness remains separately enforced;
- prepared `tools/minipc-post-fix-verification.ps1` to bundle the remaining local verification into one command;
- Windows MINI-PC tools smoke for the bundled verifier and watchdog changes: **SUCCESS**;
- central MINI-PC status subsequently returned to **HEALTHY / operational state OK / issues none** without manual runtime intervention.

Only one local pull + bundled verification is now required before closing the strategy-runtime reconnect gate.

### Physical post-fix verification PASS 2026-10-01

The bundled local verification was run on the MINI-PC after the reconciliation/watchdog fixes.

Result:
- `MINI-PC POST-FIX VERIFICATION SUMMARY`: **PASS**;
- reconciliation audit exit: **0**;
- effectiveness watchdog exit: **0**;
- overall health: **HEALTHY**;
- operational state: **OK**;
- state reasons: **none**;
- Kraken canary/universe, WS-shadow, outcome tracker, runtime supervisor and status sync: **OK**;
- issues: **none**;
- safety remained read-only: no model, no exchange account, no orders, no strategy change.

This closes the local restart/replay/TTL reconciliation gate for the current paper/read-only architecture.

### Final runbook items — intentionally last

These checks are deliberately deferred to the end of the MINI-PC commissioning runbook:

1. **Windows firewall / malware protection review**
   - Verify Windows Defender Firewall profiles and inbound/outbound exposure for the MINI-PC.
   - Decide whether built-in Microsoft Defender Antivirus is sufficient or whether any additional antivirus is justified.
   - Avoid third-party security software that could destabilize 24/7 tasks, WebSocket connectivity, scheduled jobs, RDP/VPN, Python runtimes or API calls without a demonstrated benefit.

2. **Native Windows app review for installed/used services**
   - Review whether native Windows applications add operational value for services currently used in the project, including Altrady, Slack, GitHub/GitHub Desktop and any other regularly used component.
   - Install only apps that improve reliability, notifications, startup behavior or administration versus the existing browser/CLI path; avoid duplicate clients that add background load or competing update mechanisms.

3. **Planned automatic weekly MINI-PC restart / update window**
   - Evaluate whether one scheduled weekly restart is useful for Windows update completion and long-running service hygiene.
   - If adopted, implement it as a controlled Task Scheduler maintenance window.
   - After reboot, automatically verify recovery of required startup tasks, Kraken canary, Altrady transport heartbeat, watchdog health, network reachability and RDP availability.
   - A reboot must never silently advance strategy state or enable real-money execution.

These three items remain the **final points** of the runbook, after the deferred external-drive work and external remote-access test unless dependencies require otherwise.
